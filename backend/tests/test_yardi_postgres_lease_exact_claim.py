"""PostgreSQL-specific NULL-safe Yardi Lease historical staff-claim check.

Most Yardi route regressions use isolated in-memory SQLite sessions. This
test also executes the critical SQL query and review flow on actual PostgreSQL.
All fixture data is rolled back inside an outer transaction.
"""
import os

import pytest
from fastapi import HTTPException, Response
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models.lease import Lease
from app.models.platform_migration import PlatformMigrationRun, PlatformMigrationStagedRow
from app.routers.yardi_migrations import (
    accept_yardi_staged_lease_relationship, dry_run_yardi_review,
    get_yardi_reconciliation, get_yardi_review_dry_run_status,
    list_yardi_lease_relationships,
)
from app.services.yardi_file_ingestion import stage_yardi_file
from test_yardi_lease_identity_acceptance import _seed


def test_postgresql_null_source_historical_tenant_review_blocks_lease_reaccept():
    """Real PostgreSQL IS DISTINCT FROM must include NULL historical sources."""
    url = os.environ.get("TEST_DATABASE_URL") or os.environ.get("DATABASE_URL", "")
    if not url.startswith(("postgresql://", "postgresql+")):
        pytest.skip("PostgreSQL test database URL not configured")
    # Never create schema or fixtures against an accidentally supplied
    # production database, even if its driver happens to be PostgreSQL.
    database_name = (make_url(url).database or "").lower()
    if "test" not in database_name:
        pytest.fail("Refuse PostgreSQL fixture writes outside a named test database")
    engine = create_engine(url)
    connection = engine.connect()
    outer = connection.begin()
    # PostgreSQL DDL is transactional; keep schema bootstrapping inside
    # the same outer rollback as every fixture mutation. Never leave
    # newly created test tables behind for later CI test modules.
    Base.metadata.create_all(bind=connection)
    db = sessionmaker(
        bind=connection, expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )()
    try:
        actor, org, run, prop, alternate, unit, tenant, lease = _seed(
            db, slug="yardi-pg-null-historic-tenant-claim",
        )
        before_leases = db.query(Lease).count()
        assert accept_yardi_staged_lease_relationship(
            run.id, lease.id, db, actor,
        )["replayed"] is False
        baseline = get_yardi_reconciliation(run.id, Response(), db, actor)
        assert baseline["lease_relationship_readiness"]["source_review_ready"] == 1
        saved = dry_run_yardi_review(run.id, db, actor)
        assert saved["review_fingerprint"] == baseline["review_fingerprint"]

        other_run = PlatformMigrationRun(
            organization_id=org.id, provider="YARDI",
            source_account_ref="pgsql-historical-staff-claim", status="DRAFT",
        )
        db.add(other_run)
        db.flush()
        upload = stage_yardi_file(
            db, run=other_run, filename="pgsql-old-tenant.csv",
            content=b"Resident Ref,Full Name\nT-OLDER,Historical Tenant\n",
            resource_override="TENANTS", sheet_name=None,
            explicit_mapping={"source_id": "Resident Ref", "name": "Full Name"},
            platform_user_id=actor.id,
        )
        db.commit()
        historical = db.query(PlatformMigrationStagedRow).filter(
            PlatformMigrationStagedRow.upload_id == upload.upload.id,
        ).one()
        historical.resolution_action = "MATCH_EXISTING"
        historical.resolution_target_tenant_user_id = tenant.id
        historical.source_id = None
        db.commit()

        blocked = get_yardi_reconciliation(run.id, Response(), db, actor)
        readiness = blocked["lease_relationship_readiness"]
        assert readiness["identity_target_review_collisions"] == 1
        assert readiness["accepted_relationship_stale"] == 1
        assert readiness["source_review_ready"] == 0
        assert readiness["complete_identity_links"] == 0
        assert blocked["review_fingerprint"] != baseline["review_fingerprint"]
        assert get_yardi_review_dry_run_status(
            run.id, Response(), db, actor,
        )["is_current"] is False
        preview = list_yardi_lease_relationships(
            run.id, Response(), offset=0, limit=10,
            db=db, current_user=actor,
        )["items"][0]
        assert "TENANT_TARGET_REVIEW_COLLISION" in preview["blockers"]
        assert preview["relationship_review_current"] is False
        assert preview["occupancy_or_lease_authorized"] is False
        with pytest.raises(HTTPException) as conflict:
            accept_yardi_staged_lease_relationship(run.id, lease.id, db, actor)
        assert conflict.value.status_code == 409

        # PostgreSQL should preserve WHICH historical source contested
        # this mapped Tenant even with identical stale aggregate counts.
        historical.source_id = "T-OLDER-2"
        db.commit()
        changed_claim = get_yardi_reconciliation(run.id, Response(), db, actor)
        assert changed_claim["lease_relationship_readiness"] == blocked["lease_relationship_readiness"]
        assert changed_claim["review_fingerprint"] != blocked["review_fingerprint"]
        historical.source_id = None
        db.commit()
        restored_blocked = get_yardi_reconciliation(run.id, Response(), db, actor)
        assert restored_blocked["review_fingerprint"] == blocked["review_fingerprint"]
        assert restored_blocked["lease_relationship_readiness"] == blocked["lease_relationship_readiness"]

        historical.source_id = "T1"
        db.commit()
        recovered = get_yardi_reconciliation(run.id, Response(), db, actor)
        assert recovered["review_fingerprint"] == baseline["review_fingerprint"]
        assert recovered["lease_relationship_readiness"]["source_review_ready"] == 1
        assert recovered["lease_relationship_readiness"]["identity_target_review_collisions"] == 0
        assert accept_yardi_staged_lease_relationship(
            run.id, lease.id, db, actor,
        )["replayed"] is True
        assert db.query(Lease).count() == before_leases
        assert recovered["customer_business_mutation"] is False
        assert tenant.hashed_password == "unchanged-password-hash"
        assert prop.name == "Original"
        assert unit.property_id == prop.id
    finally:
        db.close()
        outer.rollback()
        connection.close()
        engine.dispose()
