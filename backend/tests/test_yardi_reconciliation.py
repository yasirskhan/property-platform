"""Yardi reconciliation is strictly read-only and scoped to the Yardi run."""
from fastapi import Response
from app.models.platform_migration import PlatformMigrationRun, PlatformMigrationItem, PlatformMigrationStagedRow
from app.models.platform_user import PlatformUserRole
from app.models.property import Property
from app.services.yardi_file_ingestion import stage_yardi_file
from app.routers.yardi_migrations import get_yardi_reconciliation
from test_yardi_migrations import _session, _org, _platform_user


def test_yardi_empty_reconciliation_is_stable_and_not_committable():
    db, engine = _session()
    try:
        actor = _platform_user(db, PlatformUserRole.PLATFORM_ADMIN)
        org = _org(db, "yardi-reconciliation")
        run = PlatformMigrationRun(
            organization_id=org.id, provider="YARDI",
            source_account_ref="reconcile", status="DRAFT",
        )
        db.add(run)
        db.commit()
        response = Response()
        result = get_yardi_reconciliation(run.id, response, db, actor)
        repeat = get_yardi_reconciliation(run.id, Response(), db, actor)
        assert result["provider"] == "YARDI"
        assert result["staged_rows"] == 0
        assert result["durable_mapping_count"] == 0
        assert result["unresolved_rows"] == 0
        assert result["review_fingerprint"] == repeat["review_fingerprint"]
        assert result["controlled_commit_enabled"] is False
        assert result["customer_business_mutation"] is False
        assert response.headers["cache-control"] == "no-store"
    finally:
        db.close()
        engine.dispose()

def test_unreviewed_source_requires_exact_durable_version_and_entity():
    db, engine = _session()
    try:
        actor = _platform_user(db, PlatformUserRole.PLATFORM_ADMIN)
        org = _org(db, "yardi-unreviewed-version")
        target = Property(
            organization_id=org.id, name="Existing Customer Property",
            address_line1="1 Main", city="Cleveland", state="OH", zip_code="44113",
        )
        run = PlatformMigrationRun(
            organization_id=org.id, provider="YARDI",
            source_account_ref="unreviewed-version", status="DRAFT",
        )
        db.add_all([target, run])
        db.commit()
        upload = stage_yardi_file(
            db, run=run, filename="properties.csv",
            content=b"ID,Name,Street,City,State,Zip\nP1,Imported Source,2 Main,Cleveland,OH,44113\n",
            resource_override="PROPERTIES", sheet_name=None,
            explicit_mapping={
                "source_id": "ID", "name": "Name", "address_line1": "Street",
                "city": "City", "state": "State", "zip_code": "Zip",
            }, platform_user_id=actor.id,
        )
        db.commit()
        row = db.query(PlatformMigrationStagedRow).filter(
            PlatformMigrationStagedRow.upload_id == upload.upload.id,
        ).one()
        assert row.resolution_action is None
        binding = PlatformMigrationItem(
            run_id=run.id, organization_id=org.id, provider="YARDI",
            resource="PROPERTIES", source_id="P1", target_entity="PROPERTY",
            target_id=target.id, source_fingerprint="different-export-version",
        )
        db.add(binding)
        db.commit()
        stale = get_yardi_reconciliation(run.id, Response(), db, actor)
        assert stale["resource_coverage"]["PROPERTIES"]["mapped"] == 0
        assert stale["resource_coverage"]["PROPERTIES"]["needs_review"] == 1
        binding.source_fingerprint = row.row_fingerprint
        db.commit()
        current = get_yardi_reconciliation(run.id, Response(), db, actor)
        assert current["resource_coverage"]["PROPERTIES"]["mapped"] == 1
        binding.target_entity = "UNIT"
        db.commit()
        wrong_type = get_yardi_reconciliation(run.id, Response(), db, actor)
        assert wrong_type["resource_coverage"]["PROPERTIES"]["mapped"] == 0
        assert wrong_type["resource_coverage"]["PROPERTIES"]["needs_review"] == 1
        assert wrong_type["review_fingerprint"] != current["review_fingerprint"]
        binding.target_entity = "PROPERTY"
        db.commit()
        restored = get_yardi_reconciliation(run.id, Response(), db, actor)
        assert restored["resource_coverage"]["PROPERTIES"]["mapped"] == 1
        assert restored["review_fingerprint"] == current["review_fingerprint"]
        db.refresh(target)
        db.refresh(row)
        assert target.name == "Existing Customer Property"
        assert row.resolution_action is None
    finally:
        db.close()
        engine.dispose()
