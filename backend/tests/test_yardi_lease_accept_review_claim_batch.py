"""Lease identity acceptance batches reviewed source claims without losing NULL evidence."""
import pytest
from fastapi import HTTPException
from sqlalchemy import event

from app.models.lease import Lease
from app.models.platform_migration import PlatformMigrationRun, PlatformMigrationStagedRow
from app.routers.yardi_migrations import accept_yardi_staged_lease_relationship
from app.services.yardi_file_ingestion import stage_yardi_file
from test_yardi_lease_identity_acceptance import _seed
from test_yardi_migrations import _org, _session


def _is_batched_review_claim_select(statement: str) -> bool:
    """Count the batched competing-claim read, not other staged-row SELECTs.

    Full ORM entity projections include all three resolution targets too.
    Inspect WHERE predicates, without depending on a generated SELECT alias.
    """
    sql = " ".join(statement.lower().split())
    projection, from_keyword, from_sql = sql.partition(" from ")
    if not from_keyword or not projection.startswith("select "):
        return False
    targets = (
        "resolution_target_id",
        "resolution_target_unit_id",
        "resolution_target_tenant_user_id",
    )
    if any(field in projection for field in targets):
        return False
    return (
        "platform_migration_staged_rows.id" in projection
        and "platform_migration_staged_rows" in from_sql
        and " where " in from_sql
        and all(field in from_sql for field in targets)
        and "resolution_action" in from_sql
        and "organization_id" in from_sql
        and "provider" in from_sql
    )


def test_acceptance_batched_review_claim_query_blocks_unknown_source_and_recovers():
    db, engine = _session()
    try:
        actor, org, run, prop, alternate, unit, tenant, lease = _seed(
            db, slug="yardi-lease-batched-reviewed-target-claims"
        )
        before_leases = db.query(Lease).count()

        def accept_and_count():
            statements = []
            def observe(connection, cursor, statement, parameters, context, executemany):
                sql = " ".join(statement.lower().split())
                if _is_batched_review_claim_select(statement):
                    statements.append(sql)
            event.listen(engine, "before_cursor_execute", observe)
            try:
                result = accept_yardi_staged_lease_relationship(
                    run.id, lease.id, db, actor,
                )
            finally:
                event.remove(engine, "before_cursor_execute", observe)
            return result, len(statements)

        first, first_queries = accept_and_count()
        assert first["replayed"] is False and first_queries == 1

        other_run = PlatformMigrationRun(
            organization_id=org.id, provider="YARDI",
            source_account_ref="historical-staff-review", status="DRAFT",
        )
        db.add(other_run)
        db.flush()
        upload = stage_yardi_file(
            db, run=other_run, filename="historical-property.csv",
            content=b"ID,Name,Street,City,State,Zip\nP-OLD,Other Source,1 Main,Cleveland,OH,44113\n",
            resource_override="PROPERTIES", sheet_name=None,
            explicit_mapping={
                "source_id": "ID", "name": "Name", "address_line1": "Street",
                "city": "City", "state": "State", "zip_code": "Zip",
            }, platform_user_id=actor.id,
        )
        db.commit()
        historical = db.query(PlatformMigrationStagedRow).filter(
            PlatformMigrationStagedRow.upload_id == upload.upload.id,
        ).one()
        historical.resolution_action = "MATCH_EXISTING"
        historical.resolution_target_id = prop.id
        historical.source_id = None  # Old retained review with unknown provider ID.
        db.commit()

        statements = []
        def observe_blocked(connection, cursor, statement, parameters, context, executemany):
            sql = " ".join(statement.lower().split())
            if _is_batched_review_claim_select(statement):
                statements.append(sql)
        event.listen(engine, "before_cursor_execute", observe_blocked)
        try:
            with pytest.raises(HTTPException) as conflict:
                accept_yardi_staged_lease_relationship(run.id, lease.id, db, actor)
        finally:
            event.remove(engine, "before_cursor_execute", observe_blocked)
        assert conflict.value.status_code == 409
        assert len(statements) == 1, "all 3 current targets must share one guarded SQL read"

        # Another Yardi run reviewing exactly the same stable source and
        # customer target is not a different source identity claim.
        historical.source_id = "P1"
        db.commit()
        restored, restored_queries = accept_and_count()
        assert restored["replayed"] is True and restored_queries == 1
        db.refresh(prop)
        db.refresh(unit)
        db.refresh(tenant)
        db.refresh(lease)
        assert prop.name == "Original"
        assert unit.property_id == prop.id
        assert tenant.hashed_password == "unchanged-password-hash"
        assert lease.resolution_action == "ACCEPT_RELATIONSHIP"
        assert db.query(Lease).count() == before_leases
    finally:
        db.close()
        engine.dispose()


def test_batched_claims_refuse_unknown_unit_and_tenant_sources_then_recover():
    """Each of the three OR branches must retain historical NULL-source safety."""
    db, engine = _session()
    try:
        actor, org, run, prop, alternate, unit, tenant, lease = _seed(
            db, slug="yardi-lease-null-unit-tenant-claim-branches",
        )
        before_leases = db.query(Lease).count()
        first = accept_yardi_staged_lease_relationship(run.id, lease.id, db, actor)
        assert first["replayed"] is False

        other_run = PlatformMigrationRun(
            organization_id=org.id, provider="YARDI",
            source_account_ref="retained-unit-tenant-reviews", status="DRAFT",
        )
        db.add(other_run)
        db.flush()
        # A retained review with no recoverable provider ID must still block
        # the reviewed customer target. This is true for Unit and Tenant as
        # well as the Property covered in the preceding regression.
        for resource, filename, content, mapping, target_field, target_id, original_source in (
            (
                "UNITS", "old-unit.csv",
                b"Unit,Parent,Label\nU-OLD,P1,101\n",
                {"source_id": "Unit", "source_property_id": "Parent",
                 "unit_name": "Label"},
                "resolution_target_unit_id", unit.id, "U1",
            ),
            (
                "TENANTS", "old-resident.csv",
                b"Resident Ref,Full Name\nT-OLD,Source Resident\n",
                {"source_id": "Resident Ref", "name": "Full Name"},
                "resolution_target_tenant_user_id", tenant.id, "T1",
            ),
        ):
            upload = stage_yardi_file(
                db, run=other_run, filename=filename, content=content,
                resource_override=resource, sheet_name=None,
                explicit_mapping=mapping, platform_user_id=actor.id,
            )
            db.commit()
            historical = db.query(PlatformMigrationStagedRow).filter(
                PlatformMigrationStagedRow.upload_id == upload.upload.id,
            ).one()
            historical.resolution_action = "MATCH_EXISTING"
            setattr(historical, target_field, target_id)
            historical.source_id = None
            db.commit()
            with pytest.raises(HTTPException) as conflict:
                accept_yardi_staged_lease_relationship(run.id, lease.id, db, actor)
            assert conflict.value.status_code == 409, resource

            historical.source_id = original_source
            db.commit()
            replay = accept_yardi_staged_lease_relationship(
                run.id, lease.id, db, actor,
            )
            assert replay["replayed"] is True, resource

        db.refresh(prop)
        db.refresh(unit)
        db.refresh(tenant)
        db.refresh(lease)
        assert prop.name == "Original"
        assert unit.property_id == prop.id
        assert tenant.hashed_password == "unchanged-password-hash"
        assert lease.resolution_action == "ACCEPT_RELATIONSHIP"
        assert db.query(Lease).count() == before_leases
    finally:
        db.close()
        engine.dispose()


def test_historical_claim_from_other_organization_does_not_block_lease_replay():
    """A foreign organization's NULL-source claim must not leak into this run."""
    db, engine = _session()
    try:
        actor, org, run, prop, alternate, unit, tenant, lease = _seed(
            db, slug="yardi-lease-cross-org-review-claim",
        )
        before_leases = db.query(Lease).count()
        assert accept_yardi_staged_lease_relationship(
            run.id, lease.id, db, actor,
        )["replayed"] is False

        foreign_org = _org(db, "yardi-lease-cross-org-review-claim-foreign")
        foreign_run = PlatformMigrationRun(
            organization_id=foreign_org.id, provider="YARDI",
            source_account_ref="unrelated-org-retained-review", status="DRAFT",
        )
        db.add(foreign_run)
        db.flush()
        upload = stage_yardi_file(
            db, run=foreign_run, filename="foreign-property.csv",
            content=b"ID,Name,Street,City,State,Zip\nX1,Other,1 Main,Cleveland,OH,44113\n",
            resource_override="PROPERTIES", sheet_name=None,
            explicit_mapping={
                "source_id": "ID", "name": "Name", "address_line1": "Street",
                "city": "City", "state": "State", "zip_code": "Zip",
            }, platform_user_id=actor.id,
        )
        db.commit()
        foreign_review = db.query(PlatformMigrationStagedRow).filter(
            PlatformMigrationStagedRow.upload_id == upload.upload.id,
        ).one()
        # The relationship is intentionally inconsistent to ensure a
        # corrupted foreign-organization review cannot claim this org's target.
        foreign_review.resolution_action = "MATCH_EXISTING"
        foreign_review.source_id = None
        foreign_review.resolution_target_id = prop.id
        db.commit()
        assert accept_yardi_staged_lease_relationship(
            run.id, lease.id, db, actor,
        )["replayed"] is True
        db.refresh(prop)
        db.refresh(unit)
        db.refresh(tenant)
        assert prop.name == "Original" and unit.property_id == prop.id
        assert tenant.hashed_password == "unchanged-password-hash"
        assert db.query(Lease).count() == before_leases
    finally:
        db.close()
        engine.dispose()
