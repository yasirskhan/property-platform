"""Read-only Yardi reconciliation batches live identity validity checks.

The regression exercises both unreviewed exact durable identities and explicit
reviewed target matches without creating a customer business record.
"""
from fastapi import Response
from sqlalchemy import event

from app.models.platform_migration import PlatformMigrationItem, PlatformMigrationStagedRow
from app.routers.yardi_migrations import get_yardi_reconciliation
from app.services.yardi_file_ingestion import stage_yardi_file
from test_yardi_lease_identity_acceptance import _seed
from test_yardi_migrations import _session


def test_reconciliation_batches_live_property_target_queries_and_preserves_review():
    db, engine = _session()
    try:
        actor, org, run, original, alternate, unit, tenant, lease_row = _seed(
            db, slug="yardi-reconciliation-batch-live-targets"
        )
        def stage_property(source_id, name):
            staged = stage_yardi_file(
                db, run=run, filename="source-" + source_id + ".csv",
                content=(
                    "ID,Name,Street,City,State,Zip\n"
                    + source_id + "," + name + ",1 Main,Cleveland,OH,44113\n"
                ).encode(),
                resource_override="PROPERTIES", sheet_name=None,
                explicit_mapping={
                    "source_id": "ID", "name": "Name", "address_line1": "Street",
                    "city": "City", "state": "State", "zip_code": "Zip",
                }, platform_user_id=actor.id,
            )
            db.commit()
            row = db.query(PlatformMigrationStagedRow).filter(
                PlatformMigrationStagedRow.upload_id == staged.upload.id
            ).one()
            bound = db.query(PlatformMigrationItem).filter(
                PlatformMigrationItem.run_id == run.id,
                PlatformMigrationItem.resource == "PROPERTIES",
                PlatformMigrationItem.source_id == source_id,
            ).one()
            bound.source_fingerprint = row.row_fingerprint
            db.commit()
            return row

        first_row = stage_property("P1", "First Source")
        def inspect():
            statements = []
            def observe(connection, cursor, statement, parameters, context, executemany):
                sql = " ".join(statement.lower().split())
                if (sql.startswith("select") and " from properties" in sql
                        and "properties.is_active" in sql):
                    statements.append(sql)
            event.listen(engine, "before_cursor_execute", observe)
            try:
                result = get_yardi_reconciliation(run.id, Response(), db, actor)
            finally:
                event.remove(engine, "before_cursor_execute", observe)
            return result, len(statements)

        one, count_one = inspect()
        assert one["resource_coverage"]["PROPERTIES"]["mapped"] == 1
        second_row = stage_property("P2", "Second Source")
        second_row.resolution_action = "MATCH_EXISTING"
        second_row.resolution_target_id = alternate.id
        db.commit()

        two, count_two = inspect()
        assert count_one >= 1
        assert count_two == count_one, "live Property SELECTs must be independent of row count"
        assert two["resource_coverage"]["PROPERTIES"]["mapped"] == 1
        assert two["resource_coverage"]["PROPERTIES"]["matched_existing"] == 1
        assert two["review_fingerprint"] != one["review_fingerprint"]

        alternate.is_active = False
        db.commit()
        inactive, count_inactive = inspect()
        assert count_inactive == count_two
        assert inactive["resource_coverage"]["PROPERTIES"]["matched_existing"] == 0
        assert inactive["resource_coverage"]["PROPERTIES"]["needs_review"] >= 1
        assert inactive["review_fingerprint"] != two["review_fingerprint"]
        alternate.is_active = True
        db.commit()
        recovered, count_recovered = inspect()
        assert count_recovered == count_two
        assert recovered["review_fingerprint"] == two["review_fingerprint"]
        db.refresh(original)
        db.refresh(alternate)
        db.refresh(tenant)
        db.refresh(first_row)
        db.refresh(second_row)
        assert original.name == "Original"
        assert alternate.name == "Alternate"
        assert tenant.hashed_password == "unchanged-password-hash"
        assert first_row.resolution_action is None
        assert second_row.resolution_action == "MATCH_EXISTING"
        assert db.query(PlatformMigrationItem).filter(
            PlatformMigrationItem.run_id == run.id
        ).count() == 4
    finally:
        db.close()
        engine.dispose()
