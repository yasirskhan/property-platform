"""Yardi Units source-id and dependency staging regressions."""
from app.models.platform_migration import PlatformMigrationRun, PlatformMigrationStagedRow
from app.models.platform_user import PlatformUserRole
from app.models.property import Unit
from app.services.yardi_file_ingestion import stage_yardi_file
from test_yardi_migrations import _org, _platform_user, _session


def test_yardi_units_missing_verified_parent_remains_review_only():
    db, engine = _session()
    try:
        user = _platform_user(db, PlatformUserRole.PLATFORM_ADMIN)
        org = _org(db, "yardi-unit-stage")
        run = PlatformMigrationRun(
            organization_id=org.id, provider="YARDI",
            source_account_ref="yardi-unit-source", status="DRAFT",
            created_by_platform_user_id=user.id,
        )
        db.add(run)
        db.commit()
        prior_units = db.query(Unit).count()
        result = stage_yardi_file(
            db, run=run, filename="units.csv",
            content=b"Unit Ref,Property Ref,Unit Label\nU-1,P-1,Unit 1\nU-1,P-1,Unit 2\n",
            resource_override="UNITS", sheet_name=None,
            explicit_mapping={
                "source_id": "Unit Ref",
                "source_property_id": "Property Ref",
                "unit_name": "Unit Label",
            }, platform_user_id=user.id,
        )
        rows = db.query(PlatformMigrationStagedRow).filter(
            PlatformMigrationStagedRow.upload_id == result.upload.id
        ).order_by(PlatformMigrationStagedRow.row_number).all()
        assert result.upload.detected_resource == "UNITS"
        assert result.upload.provider == "YARDI"
        assert result.upload.validation_summary["duplicates"] == 1
        assert rows[0].disposition == "REVIEW"
        assert "relationship blocked" in rows[0].warnings[0]
        assert rows[1].disposition == "INVALID"
        assert db.query(Unit).count() == prior_units
        replay = stage_yardi_file(
            db, run=run, filename="units.csv",
            content=b"Unit Ref,Property Ref,Unit Label\nU-1,P-1,Unit 1\nU-1,P-1,Unit 2\n",
            resource_override="UNITS", sheet_name=None,
            explicit_mapping={
                "source_id": "Unit Ref",
                "source_property_id": "Property Ref",
                "unit_name": "Unit Label",
            }, platform_user_id=user.id,
        )
        assert replay.replayed and replay.upload.id == result.upload.id
    finally:
        db.close()
        engine.dispose()


def test_yardi_unit_match_requires_mapped_parent_and_preserves_customer_unit():
    import pytest
    from fastapi import HTTPException
    from app.models.property import Property
    from app.models.platform_migration import PlatformMigrationItem
    from app.routers.yardi_migrations import match_yardi_staged_unit, YardiUnitMatchIn

    db, engine = _session()
    try:
        actor = _platform_user(db, PlatformUserRole.PLATFORM_ADMIN)
        org = _org(db, "yardi-unit-reviewed")
        property_row = Property(
            organization_id=org.id, name="Existing", address_line1="1 Main",
            city="Cleveland", state="OH", zip_code="44113",
        )
        run = PlatformMigrationRun(
            organization_id=org.id, provider="YARDI",
            source_account_ref="yardi-unit-review", status="DRAFT",
        )
        db.add_all([property_row, run])
        db.flush()
        target = Unit(property_id=property_row.id, unit_number="101")
        db.add(target)
        db.commit()
        upload = stage_yardi_file(
            db, run=run, filename="units.csv",
            content=b"ID,Parent,Label\nU-1,P-1,101\n",
            resource_override="UNITS", sheet_name=None,
            explicit_mapping={
                "source_id": "ID", "source_property_id": "Parent",
                "unit_name": "Label",
            }, platform_user_id=actor.id,
        )
        db.commit()
        row = db.query(PlatformMigrationStagedRow).filter(
            PlatformMigrationStagedRow.upload_id == upload.upload.id,
        ).one()
        with pytest.raises(HTTPException) as missing:
            match_yardi_staged_unit(
                run.id, row.id, YardiUnitMatchIn(target_unit_id=target.id), db, actor,
            )
        assert missing.value.status_code == 409
        db.add(PlatformMigrationItem(
            run_id=run.id, organization_id=org.id, provider="YARDI",
            resource="PROPERTIES", source_id="P-1",
            target_entity="PROPERTY", target_id=property_row.id,
            source_fingerprint="verified-property-fingerprint",
        ))
        db.commit()
        target.is_active = False
        db.commit()
        with pytest.raises(HTTPException) as blocked:
            match_yardi_staged_unit(run.id, row.id, YardiUnitMatchIn(target_unit_id=target.id), db, actor)
        assert blocked.value.status_code == 404
        target.is_active = True
        db.commit()
        reviewed = match_yardi_staged_unit(
            run.id, row.id, YardiUnitMatchIn(target_unit_id=target.id), db, actor,
        )
        assert reviewed["action"] == "MATCH_EXISTING"
        assert reviewed["replayed"] is False
        assert match_yardi_staged_unit(
            run.id, row.id, YardiUnitMatchIn(target_unit_id=target.id), db, actor,
        )["replayed"] is True
        # A replay must revalidate its parent mapping, not trust a stale review.
        parent_mapping = db.query(PlatformMigrationItem).filter(
            PlatformMigrationItem.run_id == run.id,
            PlatformMigrationItem.resource == "PROPERTIES",
        ).one()
        db.delete(parent_mapping)
        db.commit()
        with pytest.raises(HTTPException) as missing_on_replay:
            match_yardi_staged_unit(
                run.id, row.id, YardiUnitMatchIn(target_unit_id=target.id), db, actor,
            )
        assert missing_on_replay.value.status_code == 409
        db.add(PlatformMigrationItem(
            run_id=run.id, organization_id=org.id, provider="YARDI",
            resource="PROPERTIES", source_id="P-1",
            target_entity="PROPERTY", target_id=property_row.id,
            source_fingerprint="verified-property-fingerprint",
        ))
        db.commit()
        from app.routers.yardi_migrations import (
            dry_run_yardi_review, bind_yardi_reviewed_unit_matches,
            YardiReviewedPropertyBindingIn,
        )
        snapshot = dry_run_yardi_review(run.id, db, actor)
        request = YardiReviewedPropertyBindingIn(
            review_fingerprint=snapshot["review_fingerprint"],
        )
        assert bind_yardi_reviewed_unit_matches(run.id, request, db, actor)["bound"] == 1
        assert bind_yardi_reviewed_unit_matches(run.id, request, db, actor)["replayed"] is True
        db.refresh(target)
        assert target.unit_number == "101"
        assert db.query(PlatformMigrationItem).filter(
            PlatformMigrationItem.resource == "UNITS",
        ).count() == 1
    finally:
        db.close()
        engine.dispose()


def test_yardi_unit_binding_rejects_stale_review_and_cross_run_target_collision():
    import pytest
    from fastapi import HTTPException
    from app.models.property import Property
    from app.models.platform_migration import PlatformMigrationItem
    from app.routers.yardi_migrations import (
        match_yardi_staged_unit, YardiUnitMatchIn,
        dry_run_yardi_review, bind_yardi_reviewed_unit_matches,
        YardiReviewedPropertyBindingIn,
    )
    db, engine = _session()
    try:
        actor = _platform_user(db, PlatformUserRole.PLATFORM_ADMIN)
        org = _org(db, "yardi-unit-target-collision")
        prop = Property(
            organization_id=org.id, name="Existing", address_line1="1 Main",
            city="Cleveland", state="OH", zip_code="44113",
        )
        run = PlatformMigrationRun(
            organization_id=org.id, provider="YARDI",
            source_account_ref="unit-collision-source", status="DRAFT",
        )
        other = PlatformMigrationRun(
            organization_id=org.id, provider="YARDI",
            source_account_ref="other-unit-source", status="DRAFT",
        )
        db.add_all([prop, run, other])
        db.flush()
        unit = Unit(property_id=prop.id, unit_number="202")
        db.add(unit)
        db.commit()
        upload = stage_yardi_file(
            db, run=run, filename="units.csv",
            content=b"ID,Parent,Label\nU-2,P-2,202\n",
            resource_override="UNITS", sheet_name=None,
            explicit_mapping={
                "source_id": "ID", "source_property_id": "Parent",
                "unit_name": "Label",
            }, platform_user_id=actor.id,
        )
        db.commit()
        row = db.query(PlatformMigrationStagedRow).filter(
            PlatformMigrationStagedRow.upload_id == upload.upload.id,
        ).one()
        db.add(PlatformMigrationItem(
            run_id=run.id, organization_id=org.id, provider="YARDI",
            resource="PROPERTIES", source_id="P-2",
            target_entity="PROPERTY", target_id=prop.id,
            source_fingerprint="verified-parent",
        ))
        db.commit()
        match_yardi_staged_unit(
            run.id, row.id, YardiUnitMatchIn(target_unit_id=unit.id), db, actor,
        )
        snapshot = dry_run_yardi_review(run.id, db, actor)
        with pytest.raises(HTTPException) as stale:
            bind_yardi_reviewed_unit_matches(
                run.id, YardiReviewedPropertyBindingIn(
                    review_fingerprint="0" * 64,
                ), db, actor,
            )
        assert stale.value.status_code == 409
        db.add(PlatformMigrationItem(
            run_id=other.id, organization_id=org.id, provider="YARDI",
            resource="UNITS", source_id="other-unit",
            target_entity="UNIT", target_id=unit.id,
            source_fingerprint="other-fingerprint",
        ))
        db.commit()
        with pytest.raises(HTTPException) as conflict:
            bind_yardi_reviewed_unit_matches(
                run.id, YardiReviewedPropertyBindingIn(
                    review_fingerprint=snapshot["review_fingerprint"],
                ), db, actor,
            )
        assert conflict.value.status_code == 409
        assert db.query(PlatformMigrationItem).filter(
            PlatformMigrationItem.run_id == run.id,
            PlatformMigrationItem.resource == "UNITS",
        ).count() == 0
        db.refresh(unit)
        assert unit.unit_number == "202"
    finally:
        db.close()
        engine.dispose()


def test_unit_binding_rechecks_later_staff_claim_on_initial_bind_and_replay():
    import pytest
    from fastapi import HTTPException
    from app.models.property import Property
    from app.models.platform_migration import PlatformMigrationItem
    from app.routers.yardi_migrations import (
        match_yardi_staged_unit, YardiUnitMatchIn, dry_run_yardi_review,
        bind_yardi_reviewed_unit_matches, YardiReviewedPropertyBindingIn,
    )

    db, engine = _session()
    try:
        actor = _platform_user(db, PlatformUserRole.PLATFORM_ADMIN)
        org = _org(db, "yardi-unit-binding-later-review")
        prop = Property(
            organization_id=org.id, name="Existing", address_line1="1 Main",
            city="Cleveland", state="OH", zip_code="44113",
        )
        run = PlatformMigrationRun(
            organization_id=org.id, provider="YARDI",
            source_account_ref="initial-units", status="DRAFT",
        )
        other_run = PlatformMigrationRun(
            organization_id=org.id, provider="YARDI",
            source_account_ref="later-units", status="DRAFT",
        )
        db.add_all([prop, run, other_run])
        db.flush()
        unit = Unit(property_id=prop.id, unit_number="101")
        db.add(unit)
        db.add(PlatformMigrationItem(
            run_id=run.id, organization_id=org.id, provider="YARDI",
            resource="PROPERTIES", source_id="P1", target_entity="PROPERTY",
            target_id=prop.id, source_fingerprint="verified-parent",
        ))
        db.commit()
        mapping = {
            "source_id": "ID", "source_property_id": "Parent", "unit_name": "Label",
        }

        def stage(active_run, source):
            upload = stage_yardi_file(
                db, run=active_run, filename="units.csv",
                content=f"ID,Parent,Label\n{source},P1,101\n".encode(),
                resource_override="UNITS", sheet_name=None,
                explicit_mapping=mapping, platform_user_id=actor.id,
            )
            db.commit()
            return db.query(PlatformMigrationStagedRow).filter(
                PlatformMigrationStagedRow.upload_id == upload.upload.id
            ).one()

        row = stage(run, "U1")
        match_yardi_staged_unit(
            run.id, row.id, YardiUnitMatchIn(target_unit_id=unit.id), db, actor,
        )
        snapshot = dry_run_yardi_review(run.id, db, actor)
        request = YardiReviewedPropertyBindingIn(review_fingerprint=snapshot["review_fingerprint"])
        competing = stage(other_run, "U-other")
        competing.resolution_action = "MATCH_EXISTING"
        competing.resolution_target_unit_id = unit.id
        db.commit()
        with pytest.raises(HTTPException) as blocked:
            bind_yardi_reviewed_unit_matches(run.id, request, db, actor)
        assert blocked.value.status_code == 409
        competing.resolution_action = None
        competing.resolution_target_unit_id = None
        db.commit()
        assert bind_yardi_reviewed_unit_matches(run.id, request, db, actor)["bound"] == 1
        competing.resolution_action = "MATCH_EXISTING"
        competing.resolution_target_unit_id = unit.id
        db.commit()
        with pytest.raises(HTTPException) as replay:
            bind_yardi_reviewed_unit_matches(run.id, request, db, actor)
        assert replay.value.status_code == 409
        competing.resolution_action = None
        competing.resolution_target_unit_id = None
        db.commit()
        assert bind_yardi_reviewed_unit_matches(run.id, request, db, actor)["replayed"] is True
        competing.source_id = None
        competing.resolution_action = "MATCH_EXISTING"
        competing.resolution_target_unit_id = unit.id
        db.commit()
        with pytest.raises(HTTPException) as unknown:
            bind_yardi_reviewed_unit_matches(run.id, request, db, actor)
        assert unknown.value.status_code == 409
        competing.resolution_action = None
        competing.resolution_target_unit_id = None
        db.commit()
        assert bind_yardi_reviewed_unit_matches(run.id, request, db, actor)["replayed"] is True
        db.refresh(unit)
        assert unit.unit_number == "101"
    finally:
        db.close()
        engine.dispose()
