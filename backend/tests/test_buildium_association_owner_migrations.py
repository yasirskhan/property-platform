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
from app.models.platform_migration import PlatformMigrationItem, PlatformMigrationRun
from app.models.platform_user import PlatformUser, PlatformUserRole
from app.models.user import Organization, User, UserRole
from app.routers import buildium_association_owner_migrations as api
from app.routers import buildium_migrations as base_api
from app.schemas.buildium_association_owner_migration import (
    BuildiumAssociationOwnerCommitIn,
    BuildiumAssociationOwnerDryRunIn,
    BuildiumAssociationOwnerResolutionIn,
)


def _session():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, expire_on_commit=False)(), engine


def _admin(db):
    row = PlatformUser(
        email="buildium-hoa-owner-admin@example.com",
        hashed_password=hash_password("test-password"),
        first_name="Buildium",
        last_name="HoaOwner",
        role=PlatformUserRole.PLATFORM_ADMIN,
        is_active=True,
    )
    db.add(row)
    db.commit()
    return row


def _org(db, name="HOA Owner Migration Org"):
    row = Organization(name=name, slug=name.lower().replace(" ", "-"), is_active=True)
    db.add(row)
    db.commit()
    return row


def _run(db, org):
    row = PlatformMigrationRun(
        organization_id=org.id,
        provider="BUILDIUM",
        source_account_ref="buildium-hoa-owners",
        status="DRAFT",
    )
    db.add(row)
    db.commit()
    return row


def _owner(db, org, *, email="jamie.owner@example.com", first="Jamie", last="Owner"):
    row = User(
        organization_id=org.id,
        email=email,
        hashed_password=hash_password("owner-password"),
        first_name=first,
        last_name=last,
        role=UserRole.OWNER,
        is_active=True,
    )
    db.add(row)
    db.commit()
    return row


def _record(**changes):
    row = {
        "Id": 9701,
        "UserLeaseId": 8801,
        "FirstName": "Jamie",
        "LastName": "Owner",
        "Email": "jamie.owner@example.com",
        "AlternateEmail": "PRIVATE-ALT@example.com",
        "PhoneNumbers": [{"Number": "PRIVATE-PHONE", "Type": "Mobile"}],
        "PrimaryAddress": {"AddressLine1": "PRIVATE ADDRESS"},
        "BoardMemberTerm": {
            "BoardPositionType": "President",
            "TermStartDate": "2026-01-01",
            "TermEndDate": "2026-12-31",
        },
    }
    row.update(changes)
    return row


def test_buildium_hoa_owner_maps_existing_owner_and_replays_without_customer_mutation():
    db, engine = _session()
    try:
        admin = _admin(db)
        org = _org(db)
        run = _run(db, org)
        owner = _owner(db, org)

        before = (
            db.query(User).count(),
            db.query(Charge).count(),
            db.query(GLTransaction).count(),
        )

        preview = api.dry_run_buildium_association_owners(
            run.id,
            BuildiumAssociationOwnerDryRunIn(records=[_record()]),
            db=db,
            current_user=admin,
        )
        assert preview.invalid == 0
        assert preview.reviewable == 1
        assert preview.rows[0].mapped["source_user_lease_id"] == "8801"
        assert preview.rows[0].resolution_action is None

        resolution = BuildiumAssociationOwnerResolutionIn(
            source_id=9701,
            action="MATCH_EXISTING",
            target_owner_user_id=owner.id,
        )
        reviewed = api.dry_run_buildium_association_owners(
            run.id,
            BuildiumAssociationOwnerDryRunIn(
                records=[_record()],
                resolutions=[resolution],
            ),
            db=db,
            current_user=admin,
        )
        committed = api.commit_buildium_association_owners(
            run.id,
            BuildiumAssociationOwnerCommitIn(
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
            .filter(PlatformMigrationItem.resource == "HOA_OWNERS")
            .one()
        )
        assert mapping.target_entity == "OWNER_USER"
        assert mapping.target_id == owner.id
        assert before == (
            db.query(User).count(),
            db.query(Charge).count(),
            db.query(GLTransaction).count(),
        )

        replay_preview = api.dry_run_buildium_association_owners(
            run.id,
            BuildiumAssociationOwnerDryRunIn(
                records=[_record()],
                resolutions=[resolution],
            ),
            db=db,
            current_user=admin,
        )
        replay = api.commit_buildium_association_owners(
            run.id,
            BuildiumAssociationOwnerCommitIn(
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
            resource="hoa_owners",
            limit=20,
            db=db,
            current_user=admin,
        )
        assert len(items) == 1
        assert items[0].target_exists is True
        assert items[0].target_label == owner.email

        audit_text = "\n".join(
            str(row.new_value or "")
            for row in db.query(AuditLog)
            .filter(AuditLog.entity_type == "platform_migration_run")
            .all()
        )
        assert "PRIVATE ADDRESS" not in audit_text
        assert "PRIVATE-PHONE" not in audit_text
        assert "PRIVATE-ALT" not in audit_text
        assert "President" not in audit_text
    finally:
        db.close()
        engine.dispose()


def test_buildium_hoa_owner_identity_scope_and_fingerprint_stability():
    db, engine = _session()
    try:
        admin = _admin(db)
        org = _org(db)
        foreign_org = _org(db, "Foreign HOA Owner Org")
        run = _run(db, org)
        owner = _owner(db, org)
        wrong_role = User(
            organization_id=org.id,
            email="wrong.role@example.com",
            hashed_password=hash_password("tenant-password"),
            first_name="Jamie",
            last_name="Owner",
            role=UserRole.TENANT,
            is_active=True,
        )
        foreign_owner = _owner(
            db,
            foreign_org,
            email="foreign.jamie.owner@example.com",
            first="Jamie",
            last="Owner",
        )
        db.add(wrong_role)
        db.commit()

        for target_id in (wrong_role.id, foreign_owner.id):
            with pytest.raises(HTTPException) as exc:
                api.dry_run_buildium_association_owners(
                    run.id,
                    BuildiumAssociationOwnerDryRunIn(
                        records=[_record()],
                        resolutions=[
                            BuildiumAssociationOwnerResolutionIn(
                                source_id=9701,
                                action="MATCH_EXISTING",
                                target_owner_user_id=target_id,
                            )
                        ],
                    ),
                    db=db,
                    current_user=admin,
                )
            assert exc.value.status_code == 409

        resolution = BuildiumAssociationOwnerResolutionIn(
            source_id=9701,
            action="MATCH_EXISTING",
            target_owner_user_id=owner.id,
        )
        reviewed = api.dry_run_buildium_association_owners(
            run.id,
            BuildiumAssociationOwnerDryRunIn(
                records=[_record()],
                resolutions=[resolution],
            ),
            db=db,
            current_user=admin,
        )

        owner.last_name = "Changed"
        db.commit()
        with pytest.raises(HTTPException) as exc:
            api.commit_buildium_association_owners(
                run.id,
                BuildiumAssociationOwnerCommitIn(
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
            .filter(PlatformMigrationItem.resource == "HOA_OWNERS")
            .count()
            == 0
        )
    finally:
        db.close()
        engine.dispose()


def test_buildium_hoa_owner_skip_validation_and_routes():
    from app.main import app

    db, engine = _session()
    try:
        admin = _admin(db)
        org = _org(db)
        run = _run(db, org)
        _owner(db, org)

        skip = BuildiumAssociationOwnerResolutionIn(source_id=9701, action="SKIP")
        reviewed = api.dry_run_buildium_association_owners(
            run.id,
            BuildiumAssociationOwnerDryRunIn(
                records=[_record()],
                resolutions=[skip],
            ),
            db=db,
            current_user=admin,
        )
        result = api.commit_buildium_association_owners(
            run.id,
            BuildiumAssociationOwnerCommitIn(
                fingerprint=reviewed.fingerprint,
                records=[_record()],
                resolutions=[skip],
            ),
            db=db,
            current_user=admin,
        )
        assert result.matched_existing == 0
        assert result.skipped_review == 1
        assert db.query(PlatformMigrationItem).count() == 0

        duplicate = api.dry_run_buildium_association_owners(
            run.id,
            BuildiumAssociationOwnerDryRunIn(
                records=[_record(), _record(Email="other@example.com")]
            ),
            db=db,
            current_user=admin,
        )
        assert duplicate.invalid == 1

        invalid = api.dry_run_buildium_association_owners(
            run.id,
            BuildiumAssociationOwnerDryRunIn(
                records=[_record(UserLeaseId=0)]
            ),
            db=db,
            current_user=admin,
        )
        assert invalid.invalid == 1

        missing_name = api.dry_run_buildium_association_owners(
            run.id,
            BuildiumAssociationOwnerDryRunIn(
                records=[_record(FirstName="")]
            ),
            db=db,
            current_user=admin,
        )
        assert missing_name.invalid == 1

        with pytest.raises(ValidationError):
            BuildiumAssociationOwnerDryRunIn(
                records=[_record()],
                client_secret="secret",
            )

        paths = set(app.openapi()["paths"])
        assert (
            "/api/platform/migrations/buildium/runs/{run_id}/hoa-owners/dry-run"
            in paths
        )
        assert (
            "/api/platform/migrations/buildium/runs/{run_id}/hoa-owners/commit"
            in paths
        )
    finally:
        db.close()
        engine.dispose()
