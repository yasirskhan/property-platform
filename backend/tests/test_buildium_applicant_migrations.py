from __future__ import annotations
import pytest
from fastapi import HTTPException, Response
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import init_db  # noqa: F401
from app.core.database import Base
from app.core.security import hash_password
from app.models.application import ApplicationPayment, LeaseApplication
from app.models.audit_log import AuditLog
from app.models.lease import Lease
from app.models.platform_migration import PlatformMigrationItem, PlatformMigrationRun
from app.models.platform_user import PlatformUser, PlatformUserRole
from app.models.user import Organization, User, UserRole
from app.routers import buildium_applicant_migrations as api
from app.routers import buildium_migrations as base_api
from app.schemas.buildium_applicant_migration import (
    BuildiumApplicantCommitIn, BuildiumApplicantDryRunIn,
    BuildiumApplicantResolutionIn,
)

def _session():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, expire_on_commit=False)(), engine

def _admin(db):
    row = PlatformUser(
        email="buildium-applicant-admin@example.com",
        hashed_password=hash_password("test-password"),
        first_name="Buildium", last_name="Applicant",
        role=PlatformUserRole.PLATFORM_ADMIN, is_active=True,
    )
    db.add(row); db.commit(); return row

def _org(db, name="Applicant Org"):
    row = Organization(name=name, slug=name.lower().replace(" ", "-"), is_active=True)
    db.add(row); db.commit(); return row

def _applicant(db, org, *, email="jane.applicant@example.com", role=UserRole.APPLICANT):
    row = User(
        organization_id=org.id, email=email,
        hashed_password=hash_password("test-password"),
        first_name="Jane", last_name="Applicant", role=role,
        is_active=True, is_verified=True,
    )
    db.add(row); db.commit(); return row

def _run(db, org):
    row = PlatformMigrationRun(
        organization_id=org.id, provider="BUILDIUM",
        source_account_ref="buildium-applicants", status="DRAFT",
    )
    db.add(row); db.commit(); return row

def _record(**changes):
    row = {
        "Id": 8801, "FirstName": "Jane", "LastName": "Applicant",
        "Email": "jane.applicant@example.com", "Status": "Submitted",
        "TenantId": None, "DateOfBirth": "1990-01-01",
        "PrivateNote": "DO-NOT-AUDIT-APPLICANT-PRIVATE",
    }
    row.update(changes)
    return row

def test_buildium_applicant_existing_identity_reconciles_and_replays_without_customer_mutation():
    db, engine = _session()
    try:
        admin = _admin(db); org = _org(db); target = _applicant(db, org); run = _run(db, org)
        users_before = db.query(User).count()
        apps_before = db.query(LeaseApplication).count()
        payments_before = db.query(ApplicationPayment).count()
        leases_before = db.query(Lease).count()

        preview = api.dry_run_buildium_applicants(
            run.id, BuildiumApplicantDryRunIn(records=[_record()]),
            db=db, current_user=admin,
        )
        assert preview.invalid == 0 and preview.reviewable == 1
        assert preview.rows[0].mapped["source_status"] == "Submitted"
        resolution = BuildiumApplicantResolutionIn(
            source_id=8801, action="MATCH_EXISTING",
            target_applicant_user_id=target.id,
        )
        reviewed = api.dry_run_buildium_applicants(
            run.id,
            BuildiumApplicantDryRunIn(records=[_record()], resolutions=[resolution]),
            db=db, current_user=admin,
        )
        committed = api.commit_buildium_applicants(
            run.id,
            BuildiumApplicantCommitIn(
                fingerprint=reviewed.fingerprint, records=[_record()],
                resolutions=[resolution],
            ),
            db=db, current_user=admin,
        )
        assert committed.matched_existing == 1
        mapping = db.query(PlatformMigrationItem).filter(
            PlatformMigrationItem.resource == "APPLICANTS"
        ).one()
        assert mapping.target_entity == "APPLICANT_USER"
        assert mapping.target_id == target.id
        assert db.query(User).count() == users_before
        assert db.query(LeaseApplication).count() == apps_before
        assert db.query(ApplicationPayment).count() == payments_before
        assert db.query(Lease).count() == leases_before

        replay_preview = api.dry_run_buildium_applicants(
            run.id,
            BuildiumApplicantDryRunIn(records=[_record()], resolutions=[resolution]),
            db=db, current_user=admin,
        )
        replay = api.commit_buildium_applicants(
            run.id,
            BuildiumApplicantCommitIn(
                fingerprint=replay_preview.fingerprint, records=[_record()],
                resolutions=[resolution],
            ),
            db=db, current_user=admin,
        )
        assert replay.replayed is True
        assert replay.rows[0].replayed is True

        items = base_api.list_migration_items(
            run.id, response=Response(), resource="applicants", limit=20,
            db=db, current_user=admin,
        )
        assert len(items) == 1
        assert items[0].target_exists is True
        assert items[0].target_label == target.email

        audit = "\n".join(
            str(row.new_value or "")
            for row in db.query(AuditLog)
            .filter(AuditLog.entity_type == "platform_migration_run").all()
        )
        assert "DO-NOT-AUDIT-APPLICANT-PRIVATE" not in audit
        assert "1990-01-01" not in audit
        assert target.email not in audit
    finally:
        db.close(); engine.dispose()

def test_buildium_applicant_review_is_scoped_and_target_drift_invalidates_fingerprint():
    db, engine = _session()
    try:
        admin = _admin(db); org = _org(db); target = _applicant(db, org); run = _run(db, org)
        foreign_org = _org(db, "Foreign Applicant Org")
        foreign = _applicant(db, foreign_org, email="foreign.applicant@example.com")
        wrong_role = _applicant(db, org, email="tenant-shaped@example.com", role=UserRole.TENANT)

        for bad_target in (foreign.id, wrong_role.id):
            with pytest.raises(HTTPException) as exc:
                api.dry_run_buildium_applicants(
                    run.id,
                    BuildiumApplicantDryRunIn(
                        records=[_record()],
                        resolutions=[BuildiumApplicantResolutionIn(
                            source_id=8801, action="MATCH_EXISTING",
                            target_applicant_user_id=bad_target,
                        )],
                    ),
                    db=db, current_user=admin,
                )
            assert exc.value.status_code == 409

        resolution = BuildiumApplicantResolutionIn(
            source_id=8801, action="MATCH_EXISTING",
            target_applicant_user_id=target.id,
        )
        reviewed = api.dry_run_buildium_applicants(
            run.id,
            BuildiumApplicantDryRunIn(records=[_record()], resolutions=[resolution]),
            db=db, current_user=admin,
        )
        target.first_name = "Changed"
        db.commit()
        with pytest.raises(HTTPException) as exc:
            api.commit_buildium_applicants(
                run.id,
                BuildiumApplicantCommitIn(
                    fingerprint=reviewed.fingerprint, records=[_record()],
                    resolutions=[resolution],
                ),
                db=db, current_user=admin,
            )
        assert exc.value.status_code == 409
        assert "fingerprint" in exc.value.detail.lower()
        assert db.query(PlatformMigrationItem).filter(
            PlatformMigrationItem.resource == "APPLICANTS"
        ).count() == 0
    finally:
        db.close(); engine.dispose()

def test_buildium_applicant_skip_validation_and_routes():
    from app.main import app
    db, engine = _session()
    try:
        admin = _admin(db); org = _org(db); _applicant(db, org); run = _run(db, org)
        skip = BuildiumApplicantResolutionIn(source_id=8801, action="SKIP")
        reviewed = api.dry_run_buildium_applicants(
            run.id,
            BuildiumApplicantDryRunIn(records=[_record()], resolutions=[skip]),
            db=db, current_user=admin,
        )
        result = api.commit_buildium_applicants(
            run.id,
            BuildiumApplicantCommitIn(
                fingerprint=reviewed.fingerprint, records=[_record()],
                resolutions=[skip],
            ),
            db=db, current_user=admin,
        )
        assert result.matched_existing == 0 and result.skipped_review == 1
        assert db.query(PlatformMigrationItem).filter(
            PlatformMigrationItem.resource == "APPLICANTS"
        ).count() == 0

        invalid = api.dry_run_buildium_applicants(
            run.id,
            BuildiumApplicantDryRunIn(records=[_record(Email="not-an-email")]),
            db=db, current_user=admin,
        )
        assert invalid.invalid == 1

        with pytest.raises(ValidationError):
            BuildiumApplicantDryRunIn(records=[_record()], access_token="secret")

        paths = set(app.openapi()["paths"])
        assert "/api/platform/migrations/buildium/runs/{run_id}/applicants/dry-run" in paths
        assert "/api/platform/migrations/buildium/runs/{run_id}/applicants/commit" in paths
    finally:
        db.close(); engine.dispose()
