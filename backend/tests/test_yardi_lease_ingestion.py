"""Yardi lease occupancy staging must not create business records."""
from app.models.platform_migration import PlatformMigrationRun, PlatformMigrationStagedRow
from app.models.platform_user import PlatformUserRole
from app.models.lease import Lease
from app.services.yardi_file_ingestion import stage_yardi_file
from test_yardi_migrations import _session, _org, _platform_user


def test_lease_source_relationships_remain_review_only():
    db, engine = _session()
    try:
        actor = _platform_user(db, PlatformUserRole.PLATFORM_ADMIN)
        org = _org(db, "yardi-lease-stage")
        run = PlatformMigrationRun(
            organization_id=org.id, provider="YARDI",
            source_account_ref="yardi-lease-source", status="DRAFT",
        )
        db.add(run)
        db.commit()
        before = db.query(Lease).count()
        content = b"Lease Ref,Resident Ref,Property Ref,Unit Ref\nL-1,T-1,P-1,U-1\n"
        mapping = {
            "source_id": "Lease Ref",
            "source_tenant_id": "Resident Ref",
            "source_property_id": "Property Ref",
            "source_unit_id": "Unit Ref",
        }
        staged = stage_yardi_file(
            db, run=run, filename="leases.csv",
            content=content, resource_override="LEASE_OCCUPANCY",
            sheet_name=None, explicit_mapping=mapping,
            platform_user_id=actor.id,
        )
        row = db.query(PlatformMigrationStagedRow).filter(
            PlatformMigrationStagedRow.upload_id == staged.upload.id
        ).one()
        assert row.provider == "YARDI"
        assert row.disposition == "REVIEW"
        assert sum("commit blocked" in warning for warning in row.warnings) == 3
        assert db.query(Lease).count() == before
        replay = stage_yardi_file(
            db, run=run, filename="leases.csv", content=content,
            resource_override="LEASE_OCCUPANCY", sheet_name=None,
            explicit_mapping=mapping, platform_user_id=actor.id,
        )
        assert replay.replayed and replay.upload.id == staged.upload.id
        assert db.query(Lease).count() == before
    finally:
        db.close()
        engine.dispose()


def test_yardi_lease_parent_source_mapping_diagnostics_use_one_scoped_batch():
    """Reconcile each resource separately, without per-lease parent SQL scans."""
    from sqlalchemy import event
    from app.models.platform_migration import PlatformMigrationItem

    db, engine = _session()
    try:
        actor = _platform_user(db, PlatformUserRole.PLATFORM_ADMIN)
        org = _org(db, "yardi-lease-parent-batched")
        run = PlatformMigrationRun(
            organization_id=org.id, provider="YARDI",
            source_account_ref="source-lease-parent-batch", status="DRAFT",
        )
        other_run = PlatformMigrationRun(
            organization_id=org.id, provider="YARDI",
            source_account_ref="separate-run", status="DRAFT",
        )
        db.add_all([run, other_run])
        db.flush()
        # Three legitimate links belong to the current run; same-org but
        # different-run source mappings do NOT satisfy a missing relationship.
        for owner_run, resource, source_id, entity, provider in (
            (run, "TENANTS", "T1", "TENANT_USER", "YARDI"),
            (run, "PROPERTIES", "P1", "PROPERTY", "YARDI"),
            (run, "UNITS", "U1", "UNIT", "YARDI"),
            (other_run, "PROPERTIES", "P2", "PROPERTY", "YARDI"),
            # Legacy provider-mismatched metadata in a Yardi run must not
            # make T2 appear resolved: a source identity is provider-qualified.
            (run, "TENANTS", "T2", "TENANT_USER", "APPFOLIO"),
            # Wrong target entity is not a verified Unit source parent.
            (run, "UNITS", "U2", "PROPERTY", "YARDI"),
        ):
            db.add(PlatformMigrationItem(
                run_id=owner_run.id, organization_id=org.id, provider=provider,
                resource=resource, source_id=source_id,
                target_entity=entity, target_id=1,
                source_fingerprint="fixture-only-" + source_id,
            ))
        db.commit()
        before = db.query(Lease).count()
        selects = []

        def observe(connection, cursor, statement, parameters, context, executemany):
            sql = " ".join(statement.lower().split())
            if (
                " from platform_migration_items " in sql
                and "platform_migration_items.resource in (" in sql
                and "platform_migration_items.source_id in (" in sql
            ):
                selects.append(sql)

        event.listen(engine, "before_cursor_execute", observe)
        try:
            staged = stage_yardi_file(
                db, run=run, filename="multiple-leases.csv",
                content=(
                    b"Lease,Tenant,Property,Unit\n"
                    b"L1,T1,P1,U1\n"
                    b"L2,T2,P2,U2\n"
                    b"L3,T1,P1,U2\n"
                ),
                resource_override="LEASE_OCCUPANCY", sheet_name=None,
                explicit_mapping={
                    "source_id": "Lease", "source_tenant_id": "Tenant",
                    "source_property_id": "Property", "source_unit_id": "Unit",
                },
                platform_user_id=actor.id,
            )
        finally:
            event.remove(engine, "before_cursor_execute", observe)
        assert len(selects) == 1, "Parent mapping queries must not grow per staged Lease"
        rows = db.query(PlatformMigrationStagedRow).filter(
            PlatformMigrationStagedRow.upload_id == staged.upload.id,
        ).order_by(PlatformMigrationStagedRow.row_number).all()
        assert len(rows) == 3
        assert [sum("commit blocked" in warning for warning in row.warnings) for row in rows] == [0, 3, 1]
        assert all(row.disposition == "REVIEW" for row in rows)
        assert db.query(Lease).count() == before
        assert staged.upload.validation_summary["lease_occupancy_auto_created"] is False
    finally:
        db.close()
        engine.dispose()


def test_yardi_lease_parent_batch_is_bounded_across_300_source_keys():
    """An export beyond one SQL-IN batch stays scoped and staging-only."""
    from sqlalchemy import event

    db, engine = _session()
    try:
        actor = _platform_user(db, PlatformUserRole.PLATFORM_ADMIN)
        org = _org(db, "yardi-lease-batch-chunks")
        run = PlatformMigrationRun(
            organization_id=org.id, provider="YARDI",
            source_account_ref="chunked-parent-source-check", status="DRAFT",
        )
        db.add(run)
        db.commit()
        before = db.query(Lease).count()
        content = (
            "Lease,Tenant,Property,Unit\n"
            + "".join(f"L{i},T{i},P{i},U{i}\n" for i in range(101))
        ).encode("utf-8")
        observed = []

        def observe(connection, cursor, statement, parameters, context, executemany):
            sql = " ".join(statement.lower().split())
            if (
                " from platform_migration_items " in sql
                and "platform_migration_items.resource in (" in sql
                and "platform_migration_items.source_id in (" in sql
            ):
                observed.append(statement)

        event.listen(engine, "before_cursor_execute", observe)
        try:
            staged = stage_yardi_file(
                db, run=run, filename="101-lease-export.csv", content=content,
                resource_override="LEASE_OCCUPANCY", sheet_name=None,
                explicit_mapping={
                    "source_id": "Lease", "source_tenant_id": "Tenant",
                    "source_property_id": "Property", "source_unit_id": "Unit",
                },
                platform_user_id=actor.id,
            )
        finally:
            event.remove(engine, "before_cursor_execute", observe)
        assert len(observed) == 2, "303 distinct source keys require exactly two bounded reads"
        assert staged.upload.row_count == 101
        assert staged.upload.status == "REVIEW_REQUIRED"
        rows = db.query(PlatformMigrationStagedRow).filter(
            PlatformMigrationStagedRow.upload_id == staged.upload.id,
        ).all()
        assert len(rows) == 101
        assert all(row.disposition == "REVIEW" for row in rows)
        assert all(sum("commit blocked" in warning for warning in row.warnings) == 3 for row in rows)
        assert db.query(Lease).count() == before
    finally:
        db.close()
        engine.dispose()
