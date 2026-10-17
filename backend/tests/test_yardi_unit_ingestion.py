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
        assert result.upload.validation_summary["disposition_counts"] == {
            "INVALID": 1, "REVIEW": 1, "ALREADY_MAPPED": 0,
            "POSSIBLE_MATCH": 0,
        }
        assert result.upload.validation_summary["blocked_parent_relationships"] == 1
        assert result.upload.validation_summary["rows_with_blocked_parents"] == 1
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



def test_yardi_unit_staging_batches_parent_source_checks():
    """Many Unit source rows require bounded mapping reads, not N per-row queries."""
    from sqlalchemy import event
    db, engine = _session()
    try:
        actor = _platform_user(db, PlatformUserRole.PLATFORM_ADMIN)
        org = _org(db, "yardi-unit-parent-batch")
        run = PlatformMigrationRun(
            organization_id=org.id, provider="YARDI",
            source_account_ref="unit-parent-batch", status="DRAFT",
        )
        db.add(run)
        db.commit()
        before = db.query(Unit).count()
        selects = []
        def observe(connection, cursor, statement, parameters, context, executemany):
            sql = " ".join(statement.lower().split())
            if (" from platform_migration_items " in sql
                    and "platform_migration_items.source_id in (" in sql
                    and "platform_migration_items.resource = " in sql):
                selects.append(statement)
        content = ("Unit,Parent,Label\n" + "".join(
            f"U{i},P{i},Unit {i}\n" for i in range(301)
        )).encode()
        event.listen(engine, "before_cursor_execute", observe)
        try:
            result = stage_yardi_file(
                db, run=run, filename="many-units.csv", content=content,
                resource_override="UNITS", sheet_name=None,
                explicit_mapping={
                    "source_id": "Unit", "source_property_id": "Parent",
                    "unit_name": "Label",
                }, platform_user_id=actor.id,
            )
        finally:
            event.remove(engine, "before_cursor_execute", observe)
        # Two Property-parent batches plus two current-Unit identity batches.
        assert len(selects) == 4
        assert result.upload.row_count == 301
        assert result.upload.status == "REVIEW_REQUIRED"
        assert result.upload.validation_summary["blocked_parent_relationships"] == 301
        assert result.upload.validation_summary["rows_with_blocked_parents"] == 301
        assert result.upload.validation_summary["blocked_parent_by_resource"] == {"TENANTS": 0, "PROPERTIES": 301, "UNITS": 0}
        assert db.query(PlatformMigrationStagedRow).filter(
            PlatformMigrationStagedRow.upload_id == result.upload.id,
        ).count() == 301
        assert db.query(Unit).count() == before
    finally:
        db.close()
        engine.dispose()



def test_yardi_unit_batch_distinguishes_same_run_and_unrelated_mappings():
    """Only exact same-run Yardi Unit IDs count as already mapped."""
    from app.models.platform_migration import PlatformMigrationItem
    db, engine = _session()
    try:
        actor = _platform_user(db, PlatformUserRole.PLATFORM_ADMIN)
        org = _org(db, "yardi-unit-batch-scope")
        run = PlatformMigrationRun(
            organization_id=org.id, provider="YARDI",
            source_account_ref="batch-scope", status="DRAFT",
        )
        other = PlatformMigrationRun(
            organization_id=org.id, provider="YARDI",
            source_account_ref="other-batch-scope", status="DRAFT",
        )
        db.add_all([run, other])
        db.flush()
        for owner_run, provider, resource, source_id, target_entity in (
            (run, "YARDI", "PROPERTIES", "P1", "PROPERTY"),
            (run, "YARDI", "UNITS", "U1", "UNIT"),
            (other, "YARDI", "UNITS", "U2", "UNIT"),
            (run, "APPFOLIO", "UNITS", "U3", "UNIT"),
            (run, "YARDI", "UNITS", "U4", "PROPERTY"),
        ):
            db.add(PlatformMigrationItem(
                run_id=owner_run.id, organization_id=org.id,
                provider=provider, resource=resource,
                source_id=source_id, target_entity=target_entity,
                target_id=1, source_fingerprint="fixture-" + source_id,
            ))
        db.commit()
        units_before = db.query(Unit).count()
        upload = stage_yardi_file(
            db, run=run, filename="scoped-units.csv",
            content=b"Unit,Parent,Label\nU1,P1,One\nU2,P1,Two\nU3,P1,Three\nU4,P1,Four\n",
            resource_override="UNITS", sheet_name=None,
            explicit_mapping={
                "source_id": "Unit", "source_property_id": "Parent",
                "unit_name": "Label",
            }, platform_user_id=actor.id,
        )
        rows = db.query(PlatformMigrationStagedRow).filter(
            PlatformMigrationStagedRow.upload_id == upload.upload.id,
        ).order_by(PlatformMigrationStagedRow.row_number).all()
        assert [row.disposition for row in rows] == [
            "ALREADY_MAPPED", "REVIEW", "REVIEW", "REVIEW",
        ]
        assert upload.upload.validation_summary["disposition_counts"] == {
            "INVALID": 0, "REVIEW": 3, "ALREADY_MAPPED": 1,
            "POSSIBLE_MATCH": 0,
        }
        assert all(row.errors == [] for row in rows)
        assert all(row.provider == "YARDI" for row in rows)
        assert db.query(Unit).count() == units_before
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
