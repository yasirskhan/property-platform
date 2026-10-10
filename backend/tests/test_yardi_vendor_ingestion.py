"""Yardi vendor identity staging stays review-only and replay-safe."""
from app.models.platform_migration import PlatformMigrationRun, PlatformMigrationStagedRow
from app.models.platform_user import PlatformUserRole
from app.models.vendor import Vendor
from app.services.yardi_file_ingestion import stage_yardi_file
from test_yardi_migrations import _session, _org, _platform_user


def test_vendor_identity_is_staged_without_creating_vendor_or_financial_records():
    db, engine = _session()
    try:
        user = _platform_user(db, PlatformUserRole.PLATFORM_ADMIN)
        org = _org(db, "yardi-vendor-stage")
        run = PlatformMigrationRun(
            organization_id=org.id, provider="YARDI",
            source_account_ref="yardi-vendor-source", status="DRAFT",
        )
        db.add(run)
        db.commit()
        before = db.query(Vendor).count()
        content = b"Vendor Ref,Vendor Label\nVEN-1,Acme Repairs\nVEN-1,Duplicate\n"
        mapping = {"source_id": "Vendor Ref", "name": "Vendor Label"}
        result = stage_yardi_file(
            db, run=run, filename="vendors.csv", content=content,
            resource_override="VENDORS", sheet_name=None,
            explicit_mapping=mapping, platform_user_id=user.id,
        )
        assert result.upload.provider == "YARDI"
        assert result.upload.detected_resource == "VENDORS"
        assert result.upload.validation_summary["duplicates"] == 1
        rows = db.query(PlatformMigrationStagedRow).filter(
            PlatformMigrationStagedRow.upload_id == result.upload.id,
        ).order_by(PlatformMigrationStagedRow.row_number).all()
        assert rows[0].disposition == "REVIEW"
        assert "no vendor account" in rows[0].warnings[0]
        assert rows[1].disposition == "INVALID"
        assert db.query(Vendor).count() == before
        again = stage_yardi_file(
            db, run=run, filename="vendors.csv", content=content,
            resource_override="VENDORS", sheet_name=None,
            explicit_mapping=mapping, platform_user_id=user.id,
        )
        assert again.replayed and again.upload.id == result.upload.id
        assert db.query(Vendor).count() == before
    finally:
        db.close()
        engine.dispose()
