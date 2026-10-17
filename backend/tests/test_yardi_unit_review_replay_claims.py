"""Yardi Unit identity review replay must revalidate later source and target evidence."""
import pytest
from fastapi import HTTPException

from app.models.platform_migration import PlatformMigrationItem, PlatformMigrationRun, PlatformMigrationStagedRow
from app.models.platform_user import PlatformUserRole
from app.models.property import Property, Unit
from app.routers.yardi_migrations import YardiUnitMatchIn, match_yardi_staged_unit
from app.services.yardi_file_ingestion import stage_yardi_file
from test_yardi_migrations import _org, _platform_user, _session


def test_unit_review_replay_blocks_competing_review_and_fingerprint_drift():
    db, engine = _session()
    try:
        actor = _platform_user(db, PlatformUserRole.PLATFORM_ADMIN)
        org = _org(db, "yardi-unit-replay-stale")
        prop = Property(organization_id=org.id, name="Customer Property",
                        address_line1="1 Main", city="Cleveland", state="OH", zip_code="44113")
        run = PlatformMigrationRun(organization_id=org.id, provider="YARDI",
                                   source_account_ref="unit-original", status="DRAFT")
        other_run = PlatformMigrationRun(organization_id=org.id, provider="YARDI",
                                         source_account_ref="unit-other", status="DRAFT")
        db.add_all([prop, run, other_run])
        db.flush()
        unit = Unit(property_id=prop.id, unit_number="Original-101", is_active=True)
        db.add(unit)
        db.add(PlatformMigrationItem(
            run_id=run.id, organization_id=org.id, provider="YARDI",
            resource="PROPERTIES", source_id="P-1", target_entity="PROPERTY",
            target_id=prop.id, source_fingerprint="verified-property-parent",
        ))
        db.commit()
        mapping = {"source_id": "ID", "source_property_id": "Parent", "unit_name": "Label"}

        def stage(active_run, name, unit_ref):
            upload = stage_yardi_file(
                db, run=active_run, filename="units.csv",
                content=f"ID,Parent,Label\n{unit_ref},P-1,{name}\n".encode(),
                resource_override="UNITS", sheet_name=None,
                explicit_mapping=mapping, platform_user_id=actor.id,
            )
            db.commit()
            return db.query(PlatformMigrationStagedRow).filter(
                PlatformMigrationStagedRow.upload_id == upload.upload.id
            ).one()

        source = stage(run, "Original-101", "U-1")
        request = YardiUnitMatchIn(target_unit_id=unit.id)
        assert match_yardi_staged_unit(run.id, source.id, request, db, actor)["replayed"] is False
        assert match_yardi_staged_unit(run.id, source.id, request, db, actor)["replayed"] is True

        other_source = stage(other_run, "Other-102", "U-other")
        other_source.resolution_action = "MATCH_EXISTING"
        other_source.resolution_target_unit_id = unit.id
        db.commit()
        with pytest.raises(HTTPException) as staff_conflict:
            match_yardi_staged_unit(run.id, source.id, request, db, actor)
        assert staff_conflict.value.status_code == 409
        other_source.resolution_action = None
        other_source.resolution_target_unit_id = None
        db.commit()
        assert match_yardi_staged_unit(run.id, source.id, request, db, actor)["replayed"] is True

        # Exact same-run identity claim with changed source evidence is stale.
        bad_mapping = PlatformMigrationItem(
            run_id=run.id, organization_id=org.id, provider="YARDI",
            resource="UNITS", source_id=source.source_id, target_entity="UNIT",
            target_id=unit.id, source_fingerprint="stale-source-fingerprint",
        )
        db.add(bad_mapping)
        db.commit()
        with pytest.raises(HTTPException) as changed_fingerprint:
            match_yardi_staged_unit(run.id, source.id, request, db, actor)
        assert changed_fingerprint.value.status_code == 409
        bad_mapping.source_fingerprint = source.row_fingerprint
        db.commit()
        assert match_yardi_staged_unit(run.id, source.id, request, db, actor)["replayed"] is True

        db.refresh(unit)
        db.refresh(source)
        assert unit.unit_number == "Original-101"
        assert source.resolution_action == "MATCH_EXISTING"
    finally:
        db.close()
        engine.dispose()
