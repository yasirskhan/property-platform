"""Lease identity acceptance batches reviewed source claims without losing NULL evidence."""
import pytest
from fastapi import HTTPException
from sqlalchemy import event

from app.models.lease import Lease
from app.models.platform_migration import PlatformMigrationRun, PlatformMigrationStagedRow
from app.routers.yardi_migrations import accept_yardi_staged_lease_relationship
from app.services.yardi_file_ingestion import stage_yardi_file
from test_yardi_lease_identity_acceptance import _seed
from test_yardi_migrations import _session


def _is_batched_review_claim_select(statement: str) -> bool:
    """Match the ID-only conflicting-target lookup, not full staged-row loads.

    Other legitimate ORM SELECTs name all three target columns in their
    projections; they must not count as extra competing-claim lookups.
    """
    sql = " ".join(statement.lower().split())
    select_clause, separator, remainder = sql.partition(" from ")
    if not separator or select_clause != (
        "select platform_migration_staged_rows.id as platform_migration_staged_rows_id"
    ):
        return False
    if not remainder.startswith("platform_migration_staged_rows "):
        return False
    return (
        " where " in remainder
        and "platform_migration_staged_rows.organization_id" in remainder
        and "platform_migration_staged_rows.provider" in remainder
        and "platform_migration_staged_rows.resolution_action" in remainder
        and "platform_migration_staged_rows.resolution_target_id" in remainder
        and "platform_migration_staged_rows.resolution_target_unit_id" in remainder
        and "platform_migration_staged_rows.resolution_target_tenant_user_id" in remainder
        and sql.count(" is distinct from ") == 3
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
