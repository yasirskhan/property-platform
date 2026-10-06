from __future__ import annotations

import pytest
from fastapi import HTTPException, Response
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import init_db  # noqa: F401
from app.core.database import Base
from app.core.security import hash_password
from app.models.audit_log import AuditLog
from app.models.charge import Charge
from app.models.gl_transaction import GLTransaction
from app.models.hoa_association import HOAAssociation, HOAPropertyMembership
from app.models.platform_migration import PlatformMigrationItem, PlatformMigrationRun
from app.models.platform_user import PlatformUser, PlatformUserRole
from app.models.user import Organization
from app.routers import buildium_association_migrations as api
from app.routers import buildium_migrations as base_api
from app.schemas.buildium_association_migration import (
    BuildiumAssociationCommitIn,
    BuildiumAssociationDryRunIn,
    BuildiumAssociationResolutionIn,
)


def _session():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, expire_on_commit=False)(), engine


def _admin(db):
    row = PlatformUser(
        email="buildium-association-admin@example.com",
        hashed_password=hash_password("test-password"),
        first_name="Buildium",
        last_name="Association",
        role=PlatformUserRole.PLATFORM_ADMIN,
        is_active=True,
    )
    db.add(row)
    db.commit()
    return row


def _org(db, name="Association Migration Org"):
    row = Organization(
        name=name,
        slug=name.lower().replace(" ", "-"),
        is_active=True,
    )
    db.add(row)
    db.commit()
    return row


def _association(db, org, *, name="Lakeview HOA", active=True):
    row = HOAAssociation(
        organization_id=org.id,
        name=name,
        name_key=name.strip().casefold(),
        is_active=active,
    )
    db.add(row)
    db.commit()
    return row


def _run(db, org):
    row = PlatformMigrationRun(
        organization_id=org.id,
        provider="BUILDIUM",
        source_account_ref="buildium-associations",
        status="DRAFT",
    )
    db.add(row)
    db.commit()
    return row


def _record(**changes):
    row = {
        "Id": 9401,
        "Name": "Lakeview HOA",
        "IsActive": True,
        "OperatingBankAccountId": 501,
        "Reserve": 12500.00,
        "Description": "DO-NOT-AUDIT-PRIVATE-ASSOCIATION-DESCRIPTION",
        "YearBuilt": 2004,
        "TaxInformation": {
            "TaxPayerId": "DO-NOT-AUDIT-TAX-ID",
        },
        "Address": {
            "AddressLine1": "100 Lake Ave",
            "City": "Cleveland",
            "State": "OH",
            "PostalCode": "44113",
        },
    }
    row.update(changes)
    return row


def test_buildium_association_existing_identity_reconciles_and_replays_without_customer_mutation():
    db, engine = _session()
    try:
        admin = _admin(db)
        org = _org(db)
        target = _association(db, org)
        run = _run(db, org)

        associations_before = db.query(HOAAssociation).count()
        memberships_before = db.query(HOAPropertyMembership).count()
        charges_before = db.query(Charge).count()
        gl_before = db.query(GLTransaction).count()

        preview = api.dry_run_buildium_associations(
            run.id,
            BuildiumAssociationDryRunIn(records=[_record()]),
            db=db,
            current_user=admin,
        )
        assert preview.invalid == 0
        assert preview.reviewable == 1
        assert preview.rows[0].mapped["name"] == "Lakeview HOA"

        resolution = BuildiumAssociationResolutionIn(
            source_id=9401,
            action="MATCH_EXISTING",
            target_hoa_association_id=target.id,
        )
        reviewed = api.dry_run_buildium_associations(
            run.id,
            BuildiumAssociationDryRunIn(
                records=[_record()],
                resolutions=[resolution],
            ),
            db=db,
            current_user=admin,
        )
        committed = api.commit_buildium_associations(
            run.id,
            BuildiumAssociationCommitIn(
                fingerprint=reviewed.fingerprint,
                records=[_record()],
                resolutions=[resolution],
            ),
            db=db,
            current_user=admin,
        )
        assert committed.matched_existing == 1

        mapping = (
            db.query(PlatformMigrationItem)
            .filter(PlatformMigrationItem.resource == "HOA_ASSOCIATIONS")
            .one()
        )
        assert mapping.target_entity == "HOA_ASSOCIATION"
        assert mapping.target_id == target.id

        assert db.query(HOAAssociation).count() == associations_before
        assert db.query(HOAPropertyMembership).count() == memberships_before
        assert db.query(Charge).count() == charges_before
        assert db.query(GLTransaction).count() == gl_before

        replay_preview = api.dry_run_buildium_associations(
            run.id,
            BuildiumAssociationDryRunIn(
                records=[_record()],
                resolutions=[resolution],
            ),
            db=db,
            current_user=admin,
        )
        replay = api.commit_buildium_associations(
            run.id,
            BuildiumAssociationCommitIn(
                fingerprint=replay_preview.fingerprint,
                records=[_record()],
                resolutions=[resolution],
            ),
            db=db,
            current_user=admin,
        )
        assert replay.replayed is True
        assert replay.rows[0].replayed is True

        items = base_api.list_migration_items(
            run.id,
            response=Response(),
            resource="hoa_associations",
            limit=20,
            db=db,
            current_user=admin,
        )
        assert len(items) == 1
        assert items[0].target_exists is True
        assert items[0].target_label == target.name

        audit_text = "\n".join(
            str(row.new_value or "")
            for row in db.query(AuditLog)
            .filter(AuditLog.entity_type == "platform_migration_run")
            .all()
        )
        assert "DO-NOT-AUDIT-PRIVATE-ASSOCIATION-DESCRIPTION" not in audit_text
        assert "DO-NOT-AUDIT-TAX-ID" not in audit_text
        assert "100 Lake Ave" not in audit_text
    finally:
        db.close()
        engine.dispose()


def test_buildium_association_review_is_scoped_and_target_drift_invalidates_fingerprint():
    db, engine = _session()
    try:
        admin = _admin(db)
        org = _org(db)
        target = _association(db, org)
        run = _run(db, org)
        foreign_org = _org(db, "Foreign Association Org")
        foreign = _association(db, foreign_org)

        with pytest.raises(HTTPException) as exc:
            api.dry_run_buildium_associations(
                run.id,
                BuildiumAssociationDryRunIn(
                    records=[_record()],
                    resolutions=[
                        BuildiumAssociationResolutionIn(
                            source_id=9401,
                            action="MATCH_EXISTING",
                            target_hoa_association_id=foreign.id,
                        )
                    ],
                ),
                db=db,
                current_user=admin,
            )
        assert exc.value.status_code == 409

        wrong_status = _association(
            db,
            org,
            name="Inactive Lakeview HOA",
            active=False,
        )
        with pytest.raises(HTTPException) as exc:
            api.dry_run_buildium_associations(
                run.id,
                BuildiumAssociationDryRunIn(
                    records=[_record(Name="Inactive Lakeview HOA", IsActive=True)],
                    resolutions=[
                        BuildiumAssociationResolutionIn(
                            source_id=9401,
                            action="MATCH_EXISTING",
                            target_hoa_association_id=wrong_status.id,
                        )
                    ],
                ),
                db=db,
                current_user=admin,
            )
        assert exc.value.status_code == 409

        resolution = BuildiumAssociationResolutionIn(
            source_id=9401,
            action="MATCH_EXISTING",
            target_hoa_association_id=target.id,
        )
        reviewed = api.dry_run_buildium_associations(
            run.id,
            BuildiumAssociationDryRunIn(
                records=[_record()],
                resolutions=[resolution],
            ),
            db=db,
            current_user=admin,
        )

        target.name = "Changed HOA"
        target.name_key = "changed hoa"
        db.commit()

        with pytest.raises(HTTPException) as exc:
            api.commit_buildium_associations(
                run.id,
                BuildiumAssociationCommitIn(
                    fingerprint=reviewed.fingerprint,
                    records=[_record()],
                    resolutions=[resolution],
                ),
                db=db,
                current_user=admin,
            )
        assert exc.value.status_code == 409
        assert "fingerprint" in exc.value.detail.lower()
        assert (
            db.query(PlatformMigrationItem)
            .filter(PlatformMigrationItem.resource == "HOA_ASSOCIATIONS")
            .count()
            == 0
        )
    finally:
        db.close()
        engine.dispose()


def test_buildium_association_skip_validation_and_routes():
    from app.main import app

    db, engine = _session()
    try:
        admin = _admin(db)
        org = _org(db)
        _association(db, org)
        run = _run(db, org)

        skip = BuildiumAssociationResolutionIn(
            source_id=9401,
            action="SKIP",
        )
        reviewed = api.dry_run_buildium_associations(
            run.id,
            BuildiumAssociationDryRunIn(
                records=[_record()],
                resolutions=[skip],
            ),
            db=db,
            current_user=admin,
        )
        result = api.commit_buildium_associations(
            run.id,
            BuildiumAssociationCommitIn(
                fingerprint=reviewed.fingerprint,
                records=[_record()],
                resolutions=[skip],
            ),
            db=db,
            current_user=admin,
        )
        assert result.matched_existing == 0
        assert result.skipped_review == 1
        assert (
            db.query(PlatformMigrationItem)
            .filter(PlatformMigrationItem.resource == "HOA_ASSOCIATIONS")
            .count()
            == 0
        )

        invalid = api.dry_run_buildium_associations(
            run.id,
            BuildiumAssociationDryRunIn(
                records=[_record(IsActive="true")]
            ),
            db=db,
            current_user=admin,
        )
        assert invalid.invalid == 1

        duplicate = api.dry_run_buildium_associations(
            run.id,
            BuildiumAssociationDryRunIn(
                records=[_record(), _record(Name="Duplicate")]
            ),
            db=db,
            current_user=admin,
        )
        assert duplicate.invalid == 1

        with pytest.raises(ValidationError):
            BuildiumAssociationDryRunIn(
                records=[_record()],
                client_secret="secret",
            )

        paths = set(app.openapi()["paths"])
        assert (
            "/api/platform/migrations/buildium/runs/{run_id}/hoa-associations/dry-run"
            in paths
        )
        assert (
            "/api/platform/migrations/buildium/runs/{run_id}/hoa-associations/commit"
            in paths
        )
    finally:
        db.close()
        engine.dispose()
