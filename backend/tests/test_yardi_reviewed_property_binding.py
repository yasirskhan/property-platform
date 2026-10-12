"""Yardi reviewed Property bindings create durable source maps, never Properties."""
import pytest
from fastapi import HTTPException
from app.models.platform_migration import PlatformMigrationRun, PlatformMigrationItem, PlatformMigrationStagedRow
from app.models.platform_user import PlatformUserRole
from app.models.property import Property
from app.routers.yardi_migrations import (
    bind_yardi_reviewed_property_matches, dry_run_yardi_review,
    match_yardi_staged_property, YardiPropertyMatchIn,
    YardiReviewedPropertyBindingIn,
)
from app.services.yardi_file_ingestion import stage_yardi_file
from test_yardi_migrations import _session, _org, _platform_user


def test_reviewed_property_match_binding_is_exact_and_replay_safe():
    db, engine = _session()
    try:
        actor = _platform_user(db, PlatformUserRole.PLATFORM_ADMIN)
        org = _org(db, "yardi-property-binding")
        target = Property(
            organization_id=org.id, name="Original Property",
            address_line1="1 Main", city="Cleveland", state="OH",
            zip_code="44113",
        )
        run = PlatformMigrationRun(
            organization_id=org.id, provider="YARDI",
            source_account_ref="source-1", status="DRAFT",
        )
        db.add_all([target, run])
        db.commit()
        upload = stage_yardi_file(
            db, run=run, filename="properties.csv",
            content=b"ID,Name,Street,City,State,Zip\nY-01,Other Name,2 Main,Cleveland,OH,44113\n",
            resource_override="PROPERTIES", sheet_name=None,
            explicit_mapping={
                "source_id": "ID", "name": "Name",
                "address_line1": "Street", "city": "City",
                "state": "State", "zip_code": "Zip",
            }, platform_user_id=actor.id,
        )
        db.commit()
        row = db.query(PlatformMigrationStagedRow).filter(
            PlatformMigrationStagedRow.upload_id == upload.upload.id
        ).one()
        match_yardi_staged_property(
            run.id, row.id, YardiPropertyMatchIn(target_property_id=target.id),
            db, actor,
        )
        summary = dry_run_yardi_review(run.id, db, actor)
        request = YardiReviewedPropertyBindingIn(
            review_fingerprint=summary["review_fingerprint"],
        )
        with pytest.raises(HTTPException) as stale:
            bind_yardi_reviewed_property_matches(
                run.id,
                YardiReviewedPropertyBindingIn(review_fingerprint="0" * 64),
                db, actor,
            )
        assert stale.value.status_code == 409
        assert db.query(PlatformMigrationItem).filter(
            PlatformMigrationItem.run_id == run.id,
            PlatformMigrationItem.provider == "YARDI",
        ).count() == 0
        db.refresh(target)
        assert target.name == "Original Property"
        first = bind_yardi_reviewed_property_matches(run.id, request, db, actor)
        assert first["bound"] == 1 and first["replayed"] is False
        mapped = db.query(PlatformMigrationItem).filter(
            PlatformMigrationItem.run_id == run.id,
            PlatformMigrationItem.provider == "YARDI",
            PlatformMigrationItem.resource == "PROPERTIES",
        ).one()
        assert mapped.source_id == "Y-01"
        assert mapped.target_id == target.id
        assert mapped.source_fingerprint == row.row_fingerprint
        again = bind_yardi_reviewed_property_matches(run.id, request, db, actor)
        assert again["replayed"] is True and again["bound"] == 0
        db.refresh(target)
        assert target.name == "Original Property"
        assert target.address_line1 == "1 Main"
    finally:
        db.close()
        engine.dispose()


def test_reviewed_property_binding_locks_targets_in_stable_order(monkeypatch):
    from app.routers import yardi_migrations

    db, engine = _session()
    try:
        actor = _platform_user(db, PlatformUserRole.PLATFORM_ADMIN)
        org = _org(db, "yardi-stable-lock-order")
        targets = [Property(
            organization_id=org.id, name=f"Original {n}",
            address_line1=f"{n} Main", city="Cleveland", state="OH", zip_code="44113",
        ) for n in (1, 2)]
        run = PlatformMigrationRun(
            organization_id=org.id, provider="YARDI",
            source_account_ref="stable-lock-source", status="DRAFT",
        )
        db.add_all([*targets, run])
        db.commit()
        upload = stage_yardi_file(
            db, run=run, filename="properties.csv",
            content=(b"ID,Name,Street,City,State,Zip\n"
                     b"Y-01,Other One,10 Main,Cleveland,OH,44113\n"
                     b"Y-02,Other Two,20 Main,Cleveland,OH,44113\n"),
            resource_override="PROPERTIES", sheet_name=None,
            explicit_mapping={
                "source_id": "ID", "name": "Name", "address_line1": "Street",
                "city": "City", "state": "State", "zip_code": "Zip",
            }, platform_user_id=actor.id,
        )
        db.commit()
        rows = db.query(PlatformMigrationStagedRow).filter(
            PlatformMigrationStagedRow.upload_id == upload.upload.id
        ).order_by(PlatformMigrationStagedRow.id.asc()).all()
        assert len(rows) == 2
        # Reverse target ID order relative to source row order.
        for row, target in zip(rows, reversed(targets)):
            match_yardi_staged_property(
                run.id, row.id, YardiPropertyMatchIn(target_property_id=target.id),
                db, actor,
            )
        preview = dry_run_yardi_review(run.id, db, actor)
        original_lock = yardi_migrations._locked_yardi_review_target
        locked = []

        def record_lock(session, *, organization_id, property_id):
            locked.append(property_id)
            return original_lock(session, organization_id=organization_id, property_id=property_id)

        monkeypatch.setattr(yardi_migrations, "_locked_yardi_review_target", record_lock)
        result = bind_yardi_reviewed_property_matches(
            run.id, YardiReviewedPropertyBindingIn(
                review_fingerprint=preview["review_fingerprint"]
            ), db, actor,
        )
        assert result["bound"] == 2
        assert locked == sorted(locked)
        for target, original_name in zip(targets, ("Original 1", "Original 2")):
            db.refresh(target)
            assert target.name == original_name
    finally:
        db.close()
        engine.dispose()


def test_reviewed_property_binding_missing_later_target_is_atomic():
    db, engine = _session()
    try:
        actor = _platform_user(db, PlatformUserRole.PLATFORM_ADMIN)
        org = _org(db, "yardi-missing-later-target")
        targets = [Property(
            organization_id=org.id, name=f"Untouched {n}",
            address_line1=f"{n} Main", city="Cleveland", state="OH", zip_code="44113",
        ) for n in (1, 2)]
        run = PlatformMigrationRun(
            organization_id=org.id, provider="YARDI",
            source_account_ref="missing-later-source", status="DRAFT",
        )
        db.add_all([*targets, run])
        db.commit()
        upload = stage_yardi_file(
            db, run=run, filename="properties.csv",
            content=(b"ID,Name,Street,City,State,Zip\n"
                     b"Y-01,Other One,10 Main,Cleveland,OH,44113\n"
                     b"Y-02,Other Two,20 Main,Cleveland,OH,44113\n"),
            resource_override="PROPERTIES", sheet_name=None,
            explicit_mapping={
                "source_id": "ID", "name": "Name", "address_line1": "Street",
                "city": "City", "state": "State", "zip_code": "Zip",
            }, platform_user_id=actor.id,
        )
        db.commit()
        rows = db.query(PlatformMigrationStagedRow).filter(
            PlatformMigrationStagedRow.upload_id == upload.upload.id
        ).order_by(PlatformMigrationStagedRow.id.asc()).all()
        for row, target in zip(rows, targets):
            match_yardi_staged_property(
                run.id, row.id, YardiPropertyMatchIn(target_property_id=target.id),
                db, actor,
            )
        review = dry_run_yardi_review(run.id, db, actor)
        # Target disappeared after the review snapshot, before binding.
        db.delete(targets[1])
        db.commit()
        with pytest.raises(HTTPException) as exc:
            bind_yardi_reviewed_property_matches(
                run.id, YardiReviewedPropertyBindingIn(
                    review_fingerprint=review["review_fingerprint"]
                ), db, actor,
            )
        assert exc.value.status_code == 409
        assert not any(isinstance(obj, PlatformMigrationItem) for obj in db.new)
        assert db.query(PlatformMigrationItem).filter(
            PlatformMigrationItem.run_id == run.id,
            PlatformMigrationItem.provider == "YARDI",
            PlatformMigrationItem.resource == "PROPERTIES",
        ).count() == 0
        db.refresh(targets[0])
        assert targets[0].name == "Untouched 1"
    finally:
        db.close()
        engine.dispose()


def test_reviewed_property_binding_replay_rejects_deleted_target():
    db, engine = _session()
    try:
        actor = _platform_user(db, PlatformUserRole.PLATFORM_ADMIN)
        org = _org(db, "yardi-replay-deleted-target")
        target = Property(
            organization_id=org.id, name="Original Property",
            address_line1="1 Main", city="Cleveland", state="OH", zip_code="44113",
        )
        run = PlatformMigrationRun(
            organization_id=org.id, provider="YARDI",
            source_account_ref="deleted-replay-source", status="DRAFT",
        )
        db.add_all([target, run])
        db.commit()
        upload = stage_yardi_file(
            db, run=run, filename="properties.csv",
            content=b"ID,Name,Street,City,State,Zip\nY-01,Imported,2 Main,Cleveland,OH,44113\n",
            resource_override="PROPERTIES", sheet_name=None,
            explicit_mapping={
                "source_id": "ID", "name": "Name", "address_line1": "Street",
                "city": "City", "state": "State", "zip_code": "Zip",
            }, platform_user_id=actor.id,
        )
        db.commit()
        row = db.query(PlatformMigrationStagedRow).filter(
            PlatformMigrationStagedRow.upload_id == upload.upload.id
        ).one()
        match_yardi_staged_property(
            run.id, row.id, YardiPropertyMatchIn(target_property_id=target.id), db, actor,
        )
        preview = dry_run_yardi_review(run.id, db, actor)
        payload = YardiReviewedPropertyBindingIn(review_fingerprint=preview["review_fingerprint"])
        assert bind_yardi_reviewed_property_matches(run.id, payload, db, actor)["bound"] == 1
        db.delete(target)
        db.commit()
        with pytest.raises(HTTPException) as exc:
            bind_yardi_reviewed_property_matches(run.id, payload, db, actor)
        assert exc.value.status_code == 409
        assert db.query(PlatformMigrationItem).filter(
            PlatformMigrationItem.run_id == run.id,
            PlatformMigrationItem.resource == "PROPERTIES",
        ).count() == 1
    finally:
        db.close()
        engine.dispose()
