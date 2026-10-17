"""Lease identity acceptance batches reviewed source claims without losing NULL evidence."""
import pytest
from fastapi import HTTPException, Response
from sqlalchemy import event

from app.models.lease import Lease
from app.models.platform_migration import PlatformMigrationRun, PlatformMigrationUpload, PlatformMigrationStagedRow
from app.routers.yardi_migrations import (
    accept_yardi_staged_lease_relationship, get_yardi_reconciliation,
    list_yardi_lease_relationships, dry_run_yardi_review,
    get_yardi_review_dry_run_status,
)
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
        baseline = get_yardi_reconciliation(run.id, Response(), db, actor)
        assert baseline["lease_relationship_readiness"]["source_review_ready"] == 1

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
            stale = get_yardi_reconciliation(run.id, Response(), db, actor)
            readiness = stale["lease_relationship_readiness"]
            assert readiness["identity_target_review_collisions"] == 1, resource
            assert readiness["accepted_relationship_stale"] == 1, resource
            assert readiness["complete_identity_links"] == 0, resource
            assert stale["review_fingerprint"] != baseline["review_fingerprint"]
            preview = list_yardi_lease_relationships(
                run.id, Response(), offset=0, limit=10,
                db=db, current_user=actor,
            )["items"][0]
            assert resource[:-1] + "_TARGET_REVIEW_COLLISION" in preview["blockers"], resource
            assert preview["relationship_review_current"] is False

            # A recoverable but DIFFERENT provider source ID is also a
            # competing claim; only the exact original source may recover.
            historical.source_id = "OTHER-" + resource
            db.commit()
            with pytest.raises(HTTPException) as different_source:
                accept_yardi_staged_lease_relationship(run.id, lease.id, db, actor)
            assert different_source.value.status_code == 409, resource

            historical.source_id = original_source
            db.commit()
            replay = accept_yardi_staged_lease_relationship(
                run.id, lease.id, db, actor,
            )
            assert replay["replayed"] is True, resource
            recovered = get_yardi_reconciliation(run.id, Response(), db, actor)
            assert recovered["lease_relationship_readiness"]["identity_target_review_collisions"] == 0
            assert recovered["lease_relationship_readiness"]["accepted_relationship_stale"] == 0
            assert recovered["lease_relationship_readiness"]["source_review_ready"] == 1
            assert recovered["review_fingerprint"] == baseline["review_fingerprint"]
            restored_preview = list_yardi_lease_relationships(
                run.id, Response(), offset=0, limit=10,
                db=db, current_user=actor,
            )["items"][0]
            assert restored_preview["relationship_review_current"] is True
            assert restored_preview["blockers"] == []

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


def _assert_yardi_lease_review_is_current(db, actor, run):
    """Read-only acceptance/preview/reconciliation parity across isolation cases."""
    summary = get_yardi_reconciliation(run.id, Response(), db, actor)
    readiness = summary["lease_relationship_readiness"]
    assert readiness["identity_target_review_collisions"] == 0
    assert readiness["accepted_relationship_stale"] == 0
    assert readiness["complete_identity_links"] == 1
    assert readiness["source_review_ready"] == 1
    assert summary["customer_business_mutation"] is False
    preview = list_yardi_lease_relationships(
        run.id, Response(), offset=0, limit=10, db=db, current_user=actor,
    )["items"][0]
    assert preview["blockers"] == []
    assert preview["relationship_review_current"] is True
    assert preview["occupancy_or_lease_authorized"] is False
    return summary["review_fingerprint"]


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
        baseline_fingerprint = _assert_yardi_lease_review_is_current(
            db, actor, run,
        )

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
        assert _assert_yardi_lease_review_is_current(
            db, actor, run,
        ) == baseline_fingerprint
        db.refresh(prop)
        db.refresh(unit)
        db.refresh(tenant)
        assert prop.name == "Original" and unit.property_id == prop.id
        assert tenant.hashed_password == "unchanged-password-hash"
        assert db.query(Lease).count() == before_leases
    finally:
        db.close()
        engine.dispose()


def test_other_provider_historical_claim_cannot_block_yardi_lease_acceptance():
    """Historical AppFolio review of the same customer target stays isolated."""
    db, engine = _session()
    try:
        actor, org, run, prop, alternate, unit, tenant, lease = _seed(
            db, slug="yardi-lease-cross-provider-target-claim",
        )
        before_leases = db.query(Lease).count()
        assert accept_yardi_staged_lease_relationship(
            run.id, lease.id, db, actor,
        )["replayed"] is False
        baseline_fingerprint = _assert_yardi_lease_review_is_current(
            db, actor, run,
        )

        other_run = PlatformMigrationRun(
            organization_id=org.id, provider="APPFOLIO",
            source_account_ref="separate-provider", status="DRAFT",
        )
        db.add(other_run)
        db.flush()
        upload = PlatformMigrationUpload(
            organization_id=org.id, run_id=other_run.id, provider="APPFOLIO",
            filename="appfolio-historical-property.csv", file_format="CSV",
            file_sha256="a" * 64, normalized_fingerprint="b" * 64,
            detected_resource="PROPERTIES", sheet_name="",
            headers=["id"], column_mapping={"source_id": "id"},
            validation_summary={}, status="STAGED", row_count=1,
            created_by_platform_user_id=actor.id,
        )
        db.add(upload)
        db.flush()
        retained = PlatformMigrationStagedRow(
            upload_id=upload.id, run_id=other_run.id, organization_id=org.id,
            provider="APPFOLIO", resource="PROPERTIES", row_number=1,
            source_id=None, disposition="READY", row_fingerprint="c" * 64,
            normalized_data={"source_id": None}, correction_evidence=[],
            warnings=[], errors=[], resolution_action="MATCH_EXISTING",
            resolution_target_id=prop.id,
        )
        db.add(retained)
        db.commit()
        assert accept_yardi_staged_lease_relationship(
            run.id, lease.id, db, actor,
        )["replayed"] is True
        assert _assert_yardi_lease_review_is_current(
            db, actor, run,
        ) == baseline_fingerprint
        db.refresh(prop)
        db.refresh(unit)
        db.refresh(tenant)
        assert prop.name == "Original" and unit.property_id == prop.id
        assert tenant.hashed_password == "unchanged-password-hash"
        assert db.query(Lease).count() == before_leases
    finally:
        db.close()
        engine.dispose()


def test_changed_competing_lease_review_source_invalidates_exact_fingerprint():
    """Different historical source claims must not share one stale fingerprint."""
    db, engine = _session()
    try:
        actor, org, run, prop, alternate, unit, tenant, lease = _seed(
            db, slug="yardi-lease-competing-source-swap-fingerprint",
        )
        before_leases = db.query(Lease).count()
        assert accept_yardi_staged_lease_relationship(
            run.id, lease.id, db, actor,
        )["replayed"] is False
        baseline = get_yardi_reconciliation(run.id, Response(), db, actor)
        assert baseline["lease_relationship_readiness"]["source_review_ready"] == 1

        other_run = PlatformMigrationRun(
            organization_id=org.id, provider="YARDI",
            source_account_ref="historical-swapped-property-source", status="DRAFT",
        )
        db.add(other_run)
        db.flush()
        upload = stage_yardi_file(
            db, run=other_run, filename="historical-property-swaps.csv",
            content=b"ID,Name,Street,City,State,Zip\nOLD-1,Historical,1 Main,Cleveland,OH,44113\n",
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
        db.commit()

        fingerprints = []
        saved_dry_run_fingerprint = None
        for historical_source in ("OLD-1", "OLD-2", None):
            historical.source_id = historical_source
            db.commit()
            stale = get_yardi_reconciliation(run.id, Response(), db, actor)
            readiness = stale["lease_relationship_readiness"]
            assert readiness["identity_target_review_collisions"] == 1
            assert readiness["accepted_relationship_stale"] == 1
            assert readiness["complete_identity_links"] == 0
            assert readiness["source_review_ready"] == 0
            with pytest.raises(HTTPException) as blocked:
                accept_yardi_staged_lease_relationship(run.id, lease.id, db, actor)
            assert blocked.value.status_code == 409
            fingerprints.append(stale["review_fingerprint"])
            if saved_dry_run_fingerprint is None:
                recorded = dry_run_yardi_review(run.id, db, actor)
                assert recorded["replayed"] is False
                saved_dry_run_fingerprint = recorded["review_fingerprint"]
                assert get_yardi_review_dry_run_status(
                    run.id, Response(), db, actor,
                )["is_current"] is True
            else:
                dry_status = get_yardi_review_dry_run_status(
                    run.id, Response(), db, actor,
                )
                assert dry_status["saved_review_fingerprint"] == saved_dry_run_fingerprint
                assert dry_status["current_review_fingerprint"] == stale["review_fingerprint"]
                assert dry_status["is_current"] is False

        assert len(set(fingerprints)) == 3
        assert baseline["review_fingerprint"] not in fingerprints
        historical.source_id = "P1"
        db.commit()
        recovered = get_yardi_reconciliation(run.id, Response(), db, actor)
        assert recovered["lease_relationship_readiness"]["identity_target_review_collisions"] == 0
        assert recovered["lease_relationship_readiness"]["source_review_ready"] == 1
        assert recovered["review_fingerprint"] == baseline["review_fingerprint"]
        expired_snapshot = get_yardi_review_dry_run_status(
            run.id, Response(), db, actor,
        )
        assert expired_snapshot["is_current"] is False
        renewed = dry_run_yardi_review(run.id, db, actor)
        assert renewed["replayed"] is False
        assert renewed["review_fingerprint"] == baseline["review_fingerprint"]
        assert get_yardi_review_dry_run_status(
            run.id, Response(), db, actor,
        )["is_current"] is True
        assert accept_yardi_staged_lease_relationship(
            run.id, lease.id, db, actor,
        )["replayed"] is True

        db.refresh(prop)
        db.refresh(unit)
        db.refresh(tenant)
        db.refresh(lease)
        assert prop.name == "Original" and unit.property_id == prop.id
        assert tenant.hashed_password == "unchanged-password-hash"
        assert lease.resolution_action == "ACCEPT_RELATIONSHIP"
        assert db.query(Lease).count() == before_leases
    finally:
        db.close()
        engine.dispose()


@pytest.mark.parametrize("resource,unavailable_field", [
    ("PROPERTIES", "is_active"), ("PROPERTIES", "deleted_at"),
    ("UNITS", "is_active"), ("UNITS", "deleted_at"),
    ("TENANTS", "is_active"), ("TENANTS", "deleted_at"),
    ("TENANTS", "role"),
])
def test_inactive_lease_tenant_keeps_exact_historical_review_source_evidence(
    resource, unavailable_field,
):
    """Unavailable exact targets must preserve retained historic source disputes."""
    from datetime import datetime
    from app.models.user import UserRole

    db, engine = _session()
    try:
        actor, org, run, prop, alternate, unit, tenant, lease = _seed(
            db, slug=(
                f"yardi-inactive-{resource.lower()}-{unavailable_field}-historic-source-swap"
            ),
        )
        options = {
            "PROPERTIES": {
                "target": prop, "missing": "missing_property",
                "content": b"ID,Name,Street,City,State,Zip\nP-OLD-1,Historical,1 Main,Cleveland,OH,44113\n",
                "mapping": {
                    "source_id": "ID", "name": "Name", "address_line1": "Street",
                    "city": "City", "state": "State", "zip_code": "Zip",
                },
                "field": "resolution_target_id", "old": "P-OLD-1", "current": "P1",
            },
            "UNITS": {
                "target": unit, "missing": "missing_unit",
                "content": b"ID,Parent,Label\nU-OLD-1,P1,101\n",
                "mapping": {
                    "source_id": "ID", "source_property_id": "Parent",
                    "unit_name": "Label",
                },
                "field": "resolution_target_unit_id", "old": "U-OLD-1", "current": "U1",
            },
            "TENANTS": {
                "target": tenant, "missing": "missing_tenant",
                "content": b"Resident Ref,Full Name\nT-OLD-1,Historical Resident\n",
                "mapping": {"source_id": "Resident Ref", "name": "Full Name"},
                "field": "resolution_target_tenant_user_id", "old": "T-OLD-1",
                "current": "T1",
            },
        }[resource]
        target = options["target"]
        before_leases = db.query(Lease).count()
        assert accept_yardi_staged_lease_relationship(
            run.id, lease.id, db, actor,
        )["replayed"] is False
        baseline = get_yardi_reconciliation(run.id, Response(), db, actor)
        assert baseline["lease_relationship_readiness"]["source_review_ready"] == 1

        # Change only the linked customer's eligibility in the fixture.
        original_eligibility = getattr(target, unavailable_field)
        invalid_eligibility = (
            False if unavailable_field == "is_active" else
            datetime.utcnow() if unavailable_field == "deleted_at" else
            UserRole.OWNER
        )
        setattr(target, unavailable_field, invalid_eligibility)
        db.commit()
        unavailable = get_yardi_reconciliation(run.id, Response(), db, actor)
        assert unavailable["lease_relationship_readiness"][options["missing"]] == 1
        assert unavailable["lease_relationship_readiness"]["accepted_relationship_stale"] == 1
        assert unavailable["lease_relationship_readiness"]["identity_target_review_collisions"] == 0

        other_run = PlatformMigrationRun(
            organization_id=org.id, provider="YARDI",
            source_account_ref=f"historical-unavailable-{resource.lower()}", status="DRAFT",
        )
        db.add(other_run)
        db.flush()
        upload = stage_yardi_file(
            db, run=other_run,
            filename=f"historical-unavailable-{resource.lower()}.csv",
            content=options["content"],
            resource_override=resource, sheet_name=None,
            explicit_mapping=options["mapping"],
            platform_user_id=actor.id,
        )
        db.commit()
        historical = db.query(PlatformMigrationStagedRow).filter(
            PlatformMigrationStagedRow.upload_id == upload.upload.id,
        ).one()
        historical.resolution_action = "MATCH_EXISTING"
        setattr(historical, options["field"], target.id)
        db.commit()

        fingerprints = []
        saved_fp = None
        for source_id in (options["old"], options["old"].replace("-1", "-2"), None):
            historical.source_id = source_id
            db.commit()
            stale = get_yardi_reconciliation(run.id, Response(), db, actor)
            lease_status = stale["lease_relationship_readiness"]
            assert lease_status[options["missing"]] == 1
            assert lease_status["identity_target_review_collisions"] == 1
            assert lease_status["accepted_relationship_stale"] == 1
            assert lease_status["complete_identity_links"] == 0
            assert lease_status["source_review_ready"] == 0
            fingerprints.append(stale["review_fingerprint"])
            if saved_fp is None:
                saved = dry_run_yardi_review(run.id, db, actor)
                saved_fp = saved["review_fingerprint"]
                assert saved_fp == stale["review_fingerprint"]
                assert get_yardi_review_dry_run_status(
                    run.id, Response(), db, actor,
                )["is_current"] is True
            else:
                check = get_yardi_review_dry_run_status(
                    run.id, Response(), db, actor,
                )
                assert check["saved_review_fingerprint"] == saved_fp
                assert check["is_current"] is False

        assert len(set(fingerprints)) == 3
        collision_blocker = {
            "PROPERTIES": "PROPERTY_TARGET_REVIEW_COLLISION",
            "UNITS": "UNIT_TARGET_REVIEW_COLLISION",
            "TENANTS": "TENANT_TARGET_REVIEW_COLLISION",
        }[resource]
        preview = list_yardi_lease_relationships(
            run.id, Response(), offset=0, limit=10, db=db, current_user=actor,
        )["items"][0]
        assert collision_blocker in preview["blockers"]
        assert preview["relationship_review_current"] is False
        assert preview["occupancy_or_lease_authorized"] is False

        historical.source_id = options["old"]
        db.commit()
        assert get_yardi_reconciliation(
            run.id, Response(), db, actor,
        )["review_fingerprint"] == saved_fp
        assert get_yardi_review_dry_run_status(
            run.id, Response(), db, actor,
        )["is_current"] is True

        historical.source_id = options["current"]
        db.commit()
        recovered_inactive = get_yardi_reconciliation(
            run.id, Response(), db, actor,
        )
        assert recovered_inactive["review_fingerprint"] == unavailable["review_fingerprint"]
        assert recovered_inactive["lease_relationship_readiness"]["identity_target_review_collisions"] == 0
        inactive_preview = list_yardi_lease_relationships(
            run.id, Response(), offset=0, limit=10, db=db, current_user=actor,
        )["items"][0]
        assert collision_blocker not in inactive_preview["blockers"]
        assert inactive_preview["relationship_review_current"] is False

        setattr(target, unavailable_field, original_eligibility)
        db.commit()
        recovered = get_yardi_reconciliation(run.id, Response(), db, actor)
        assert recovered["review_fingerprint"] == baseline["review_fingerprint"]
        assert recovered["lease_relationship_readiness"]["source_review_ready"] == 1
        assert recovered["customer_business_mutation"] is False
        current_preview = list_yardi_lease_relationships(
            run.id, Response(), offset=0, limit=10, db=db, current_user=actor,
        )["items"][0]
        assert current_preview["blockers"] == []
        assert current_preview["relationship_review_current"] is True
        assert accept_yardi_staged_lease_relationship(
            run.id, lease.id, db, actor,
        )["replayed"] is True
        db.refresh(tenant)
        db.refresh(prop)
        db.refresh(unit)
        assert getattr(target, unavailable_field) == original_eligibility
        assert target.is_active is True
        assert tenant.hashed_password == "unchanged-password-hash"
        assert prop.name == "Original" and unit.property_id == prop.id
        assert db.query(Lease).count() == before_leases
    finally:
        db.close()
        engine.dispose()


@pytest.mark.parametrize("other_scope", ["FOREIGN_ORGANIZATION", "OTHER_PROVIDER"])
def test_unavailable_lease_tenant_ignores_foreign_historical_target_claim(
    other_scope,
):
    """Even an unavailable linked customer cannot import foreign review evidence."""
    db, engine = _session()
    try:
        actor, org, run, prop, alternate, unit, tenant, lease = _seed(
            db, slug=f"yardi-unavailable-lease-cross-scope-{other_scope.lower()}",
        )
        before_leases = db.query(Lease).count()
        assert accept_yardi_staged_lease_relationship(
            run.id, lease.id, db, actor,
        )["replayed"] is False
        original = get_yardi_reconciliation(run.id, Response(), db, actor)
        assert original["lease_relationship_readiness"]["source_review_ready"] == 1
        tenant.is_active = False
        db.commit()
        unavailable = get_yardi_reconciliation(run.id, Response(), db, actor)
        assert unavailable["lease_relationship_readiness"]["missing_tenant"] == 1
        assert unavailable["lease_relationship_readiness"]["identity_target_review_collisions"] == 0
        saved = dry_run_yardi_review(run.id, db, actor)
        assert saved["review_fingerprint"] == unavailable["review_fingerprint"]

        foreign = other_scope == "FOREIGN_ORGANIZATION"
        other_org = _org(db, "yardi-inactive-tenant-external-claim-foreign") if foreign else org
        provider = "YARDI" if foreign else "APPFOLIO"
        other_run = PlatformMigrationRun(
            organization_id=other_org.id, provider=provider,
            source_account_ref="out-of-scope-inactive-tenant", status="DRAFT",
        )
        db.add(other_run)
        db.flush()
        upload = PlatformMigrationUpload(
            organization_id=other_org.id, run_id=other_run.id, provider=provider,
            filename="out-of-scope-tenant.csv", file_format="CSV",
            file_sha256="a" * 64, normalized_fingerprint="b" * 64,
            detected_resource="TENANTS", sheet_name="",
            headers=["id"], column_mapping={"source_id": "id"},
            validation_summary={}, status="STAGED", row_count=1,
            created_by_platform_user_id=actor.id,
        )
        db.add(upload)
        db.flush()
        old_review = PlatformMigrationStagedRow(
            upload_id=upload.id, run_id=other_run.id,
            organization_id=other_org.id, provider=provider,
            resource="TENANTS", row_number=1, source_id=None,
            disposition="READY", row_fingerprint="c" * 64,
            normalized_data={"source_id": None},
            correction_evidence=[], warnings=[], errors=[],
            resolution_action="MATCH_EXISTING",
            # Deliberately inconsistent historical target to prove
            # organization/provider scopes are enforced at the data query.
            resolution_target_tenant_user_id=tenant.id,
        )
        db.add(old_review)
        db.commit()

        # Out-of-scope retained historical sources must remain isolated
        # even when the linked Yardi Tenant was already made unavailable.
        for historical_source in (None, "FOREIGN-SOURCE-1", "FOREIGN-SOURCE-2", "T1"):
            old_review.source_id = historical_source
            db.commit()
            unchanged = get_yardi_reconciliation(run.id, Response(), db, actor)
            assert unchanged["lease_relationship_readiness"] == unavailable["lease_relationship_readiness"]
            assert unchanged["review_fingerprint"] == unavailable["review_fingerprint"]
            assert get_yardi_review_dry_run_status(
                run.id, Response(), db, actor,
            )["is_current"] is True
            # Page-level review parity must remain current in source scope:
            # the genuine inactive customer blocker remains, but an unrelated
            # foreign-provider/organization/source claim must not leak in.
            page = list_yardi_lease_relationships(
                run.id, Response(), offset=0, limit=10, db=db,
                current_user=actor,
            )["items"][0]
            assert "TENANT_TARGET_REVIEW_COLLISION" not in page["blockers"]
            assert "TENANT_IDENTITY_UNMAPPED_OR_INACTIVE" in page["blockers"]
            assert page["relationship_review_current"] is False
            assert page["occupancy_or_lease_authorized"] is False

        inactive_preview = list_yardi_lease_relationships(
            run.id, Response(), offset=0, limit=10, db=db, current_user=actor,
        )["items"][0]
        assert "TENANT_TARGET_REVIEW_COLLISION" not in inactive_preview["blockers"]
        assert "TENANT_IDENTITY_UNMAPPED_OR_INACTIVE" in inactive_preview["blockers"]
        assert inactive_preview["relationship_review_current"] is False
        status = get_yardi_review_dry_run_status(run.id, Response(), db, actor)
        assert status["is_current"] is True
        assert status["saved_review_fingerprint"] == saved["review_fingerprint"]
        assert dry_run_yardi_review(run.id, db, actor)["replayed"] is True

        tenant.is_active = True
        db.commit()
        recovered = get_yardi_reconciliation(run.id, Response(), db, actor)
        assert recovered["review_fingerprint"] == original["review_fingerprint"]
        assert recovered["lease_relationship_readiness"]["source_review_ready"] == 1
        current_preview = list_yardi_lease_relationships(
            run.id, Response(), offset=0, limit=10, db=db, current_user=actor,
        )["items"][0]
        assert current_preview["blockers"] == []
        assert current_preview["relationship_review_current"] is True
        assert recovered["customer_business_mutation"] is False
        assert accept_yardi_staged_lease_relationship(
            run.id, lease.id, db, actor,
        )["replayed"] is True
        db.refresh(tenant)
        db.refresh(prop)
        db.refresh(unit)
        assert tenant.is_active is True
        assert tenant.hashed_password == "unchanged-password-hash"
        assert prop.name == "Original" and unit.property_id == prop.id
        assert db.query(Lease).count() == before_leases
    finally:
        db.close()
        engine.dispose()


def test_unavailable_lease_tenant_ignores_other_customer_historical_source_claim():
    """Retained same-org review claims on unrelated targets cannot expire a Lease."""
    from app.models.user import User, UserRole

    db, engine = _session()
    try:
        actor, org, run, prop, alternate, unit, tenant, lease = _seed(
            db, slug="yardi-unavailable-tenant-unreferenced-history",
        )
        original_leases = db.query(Lease).count()
        assert accept_yardi_staged_lease_relationship(
            run.id, lease.id, db, actor,
        )["replayed"] is False
        original = get_yardi_reconciliation(run.id, Response(), db, actor)
        assert original["lease_relationship_readiness"]["source_review_ready"] == 1
        tenant.is_active = False
        db.commit()
        baseline = get_yardi_reconciliation(run.id, Response(), db, actor)
        assert baseline["lease_relationship_readiness"]["missing_tenant"] == 1
        assert baseline["lease_relationship_readiness"]["accepted_relationship_stale"] == 1
        assert baseline["lease_relationship_readiness"]["identity_target_review_collisions"] == 0
        saved = dry_run_yardi_review(run.id, db, actor)
        assert saved["review_fingerprint"] == baseline["review_fingerprint"]

        unrelated = User(
            organization_id=org.id, role=UserRole.TENANT,
            email="yardi-unavailable-unrelated-review@example.test",
            hashed_password="unchanged-unrelated-hash",
            first_name="Unreferenced", last_name="Tenant", is_active=True,
        )
        other_run = PlatformMigrationRun(
            organization_id=org.id, provider="YARDI",
            source_account_ref="same-org-unrelated-target", status="DRAFT",
        )
        db.add_all([unrelated, other_run])
        db.flush()
        upload = stage_yardi_file(
            db, run=other_run, filename="other-tenant-claim.csv",
            content=b"Resident Ref,Full Name\nT-OTHER,Unrelated Resident\n",
            resource_override="TENANTS", sheet_name=None,
            explicit_mapping={"source_id": "Resident Ref", "name": "Full Name"},
            platform_user_id=actor.id,
        )
        db.commit()
        historical = db.query(PlatformMigrationStagedRow).filter(
            PlatformMigrationStagedRow.upload_id == upload.upload.id,
        ).one()
        historical.resolution_action = "MATCH_EXISTING"
        historical.resolution_target_tenant_user_id = unrelated.id
        historical.source_id = None
        db.commit()

        # A same-organization but UNREFERENCED historical review may change
        # source identity repeatedly without affecting this Lease's evidence.
        for historical_source in (None, "T-OTHER-2", "T-OTHER-3", "T1"):
            historical.source_id = historical_source
            db.commit()
            unchanged = get_yardi_reconciliation(run.id, Response(), db, actor)
            assert unchanged["lease_relationship_readiness"] == baseline["lease_relationship_readiness"]
            assert unchanged["review_fingerprint"] == baseline["review_fingerprint"]
            assert get_yardi_review_dry_run_status(
                run.id, Response(), db, actor,
            )["is_current"] is True
            # Page-level review parity must remain current in source scope:
            # the genuine inactive customer blocker remains, but an unrelated
            # foreign-provider/organization/source claim must not leak in.
            page = list_yardi_lease_relationships(
                run.id, Response(), offset=0, limit=10, db=db,
                current_user=actor,
            )["items"][0]
            assert "TENANT_TARGET_REVIEW_COLLISION" not in page["blockers"]
            assert "TENANT_IDENTITY_UNMAPPED_OR_INACTIVE" in page["blockers"]
            assert page["relationship_review_current"] is False
            assert page["occupancy_or_lease_authorized"] is False

        inactive_preview = list_yardi_lease_relationships(
            run.id, Response(), offset=0, limit=10, db=db, current_user=actor,
        )["items"][0]
        assert "TENANT_TARGET_REVIEW_COLLISION" not in inactive_preview["blockers"]
        assert "TENANT_IDENTITY_UNMAPPED_OR_INACTIVE" in inactive_preview["blockers"]
        assert inactive_preview["relationship_review_current"] is False
        saved_status = get_yardi_review_dry_run_status(
            run.id, Response(), db, actor,
        )
        assert saved_status["is_current"] is True
        assert saved_status["saved_review_fingerprint"] == saved["review_fingerprint"]
        replayed = dry_run_yardi_review(run.id, db, actor)
        assert replayed["replayed"] is True

        tenant.is_active = True
        db.commit()
        recovered = get_yardi_reconciliation(run.id, Response(), db, actor)
        assert recovered["review_fingerprint"] == original["review_fingerprint"]
        assert recovered["lease_relationship_readiness"]["source_review_ready"] == 1
        current_preview = list_yardi_lease_relationships(
            run.id, Response(), offset=0, limit=10, db=db, current_user=actor,
        )["items"][0]
        assert current_preview["blockers"] == []
        assert current_preview["relationship_review_current"] is True
        assert recovered["customer_business_mutation"] is False
        assert accept_yardi_staged_lease_relationship(
            run.id, lease.id, db, actor,
        )["replayed"] is True
        db.refresh(tenant)
        db.refresh(unrelated)
        db.refresh(prop)
        db.refresh(unit)
        assert tenant.is_active is True
        assert tenant.hashed_password == "unchanged-password-hash"
        assert unrelated.hashed_password == "unchanged-unrelated-hash"
        assert prop.name == "Original" and unit.property_id == prop.id
        assert db.query(Lease).count() == original_leases
    finally:
        db.close()
        engine.dispose()


@pytest.mark.parametrize("resource", ["PROPERTIES", "UNITS"])
def test_unavailable_lease_unit_ignores_unrelated_property_or_unit_history(resource):
    """Unrelated same-org Yardi source swaps cannot stale another blocked Lease."""
    from app.models.platform_migration import PlatformMigrationItem
    from app.models.property import Property, Unit

    db, engine = _session()
    try:
        actor, org, run, prop, alternate, unit, tenant, lease = _seed(
            db, slug=f"yardi-unavailable-lease-unrelated-{resource.lower()}",
        )
        before_leases = db.query(Lease).count()
        before_bindings = db.query(PlatformMigrationItem).filter(
            PlatformMigrationItem.run_id == run.id,
        ).count()
        assert accept_yardi_staged_lease_relationship(
            run.id, lease.id, db, actor,
        )["replayed"] is False
        baseline = get_yardi_reconciliation(run.id, Response(), db, actor)
        assert baseline["lease_relationship_readiness"]["source_review_ready"] == 1

        unit.is_active = False
        db.commit()
        unavailable = get_yardi_reconciliation(run.id, Response(), db, actor)
        assert unavailable["lease_relationship_readiness"]["missing_unit"] == 1
        assert unavailable["lease_relationship_readiness"]["accepted_relationship_stale"] == 1
        assert unavailable["lease_relationship_readiness"]["identity_target_review_collisions"] == 0
        saved = dry_run_yardi_review(run.id, db, actor)
        assert saved["review_fingerprint"] == unavailable["review_fingerprint"]

        other_run = PlatformMigrationRun(
            organization_id=org.id, provider="YARDI",
            source_account_ref=f"unrelated-{resource.lower()}-history", status="DRAFT",
        )
        db.add(other_run)
        db.flush()
        if resource == "PROPERTIES":
            unrelated = Property(
                organization_id=org.id, name="Unreferenced Third Property",
                address_line1="3 Other", city="Cleveland", state="OH", zip_code="44113",
            )
            filename = "unreferenced-property.csv"
            content = b"ID,Name,Street,City,State,Zip\nH-P,Unrelated,3 Other,Cleveland,OH,44113\n"
            mapping = {
                "source_id": "ID", "name": "Name", "address_line1": "Street",
                "city": "City", "state": "State", "zip_code": "Zip",
            }
            target_field = "resolution_target_id"
        else:
            unrelated = Unit(property_id=alternate.id, unit_number="999")
            filename = "unreferenced-unit.csv"
            content = b"Unit,Parent,Label\nH-U,P2,999\n"
            mapping = {"source_id": "Unit", "source_property_id": "Parent",
                       "unit_name": "Label"}
            target_field = "resolution_target_unit_id"
        db.add(unrelated)
        db.commit()
        upload = stage_yardi_file(
            db, run=other_run, filename=filename, content=content,
            resource_override=resource, sheet_name=None,
            explicit_mapping=mapping, platform_user_id=actor.id,
        )
        db.commit()
        historic = db.query(PlatformMigrationStagedRow).filter(
            PlatformMigrationStagedRow.upload_id == upload.upload.id,
        ).one()
        historic.resolution_action = "MATCH_EXISTING"
        setattr(historic, target_field, unrelated.id)
        db.commit()

        for source in (None, "HIST-OLD-1", "HIST-OLD-2", "HIST-OLD-3"):
            historic.source_id = source
            db.commit()
            still_blocked = get_yardi_reconciliation(run.id, Response(), db, actor)
            assert still_blocked["lease_relationship_readiness"] == unavailable["lease_relationship_readiness"]
            assert still_blocked["review_fingerprint"] == saved["review_fingerprint"]
            status = get_yardi_review_dry_run_status(run.id, Response(), db, actor)
            assert status["is_current"] is True
            assert dry_run_yardi_review(run.id, db, actor)["replayed"] is True
            preview = list_yardi_lease_relationships(
                run.id, Response(), offset=0, limit=10, db=db, current_user=actor,
            )["items"][0]
            assert preview["relationship_review_current"] is False
            assert "UNIT_IDENTITY_UNMAPPED_OR_INACTIVE" in preview["blockers"]
            assert "PROPERTY_TARGET_REVIEW_COLLISION" not in preview["blockers"]
            assert "UNIT_TARGET_REVIEW_COLLISION" not in preview["blockers"]
            assert preview["occupancy_or_lease_authorized"] is False

        unit.is_active = True
        db.commit()
        restored = get_yardi_reconciliation(run.id, Response(), db, actor)
        assert restored["review_fingerprint"] == baseline["review_fingerprint"]
        assert restored["lease_relationship_readiness"]["source_review_ready"] == 1
        assert accept_yardi_staged_lease_relationship(
            run.id, lease.id, db, actor,
        )["replayed"] is True
        assert list_yardi_lease_relationships(
            run.id, Response(), offset=0, limit=10, db=db, current_user=actor,
        )["items"][0]["blockers"] == []
        assert db.query(Lease).count() == before_leases
        assert db.query(PlatformMigrationItem).filter(
            PlatformMigrationItem.run_id == run.id,
        ).count() == before_bindings
        assert restored["customer_business_mutation"] is False
        db.refresh(prop)
        db.refresh(unit)
        db.refresh(tenant)
        assert prop.name == "Original" and unit.property_id == prop.id
        assert unit.is_active is True and unit.unit_number == "101"
        assert tenant.hashed_password == "unchanged-password-hash"
    finally:
        db.close()
        engine.dispose()


@pytest.mark.parametrize("profile_field,new_value", [
    ("first_name", "Updated Existing"),
    ("last_name", "Tenant Profile Update"),
    ("hashed_password", "rotated-tenant-fixture-password-hash"),
])
def test_accepted_lease_review_survives_eligible_tenant_profile_only_update(
    profile_field, new_value,
):
    """Customer profile changes cannot silently expire a source-exact Lease review."""
    from app.models.platform_migration import PlatformMigrationItem

    db, engine = _session()
    try:
        actor, org, run, prop, alternate, unit, tenant, lease = _seed(
            db, slug=f"yardi-lease-valid-tenant-profile-{profile_field}",
        )
        before_leases = db.query(Lease).count()
        before_mappings = db.query(PlatformMigrationItem).filter(
            PlatformMigrationItem.run_id == run.id,
        ).count()
        assert accept_yardi_staged_lease_relationship(
            run.id, lease.id, db, actor,
        )["replayed"] is False
        baseline = get_yardi_reconciliation(run.id, Response(), db, actor)
        assert baseline["lease_relationship_readiness"]["source_review_ready"] == 1
        assert baseline["lease_relationship_readiness"]["accepted_relationship_stale"] == 0
        saved = dry_run_yardi_review(run.id, db, actor)
        assert saved["review_fingerprint"] == baseline["review_fingerprint"]

        previous_value = getattr(tenant, profile_field)
        setattr(tenant, profile_field, new_value)
        db.commit()
        assert getattr(tenant, profile_field) == new_value
        changed = get_yardi_reconciliation(run.id, Response(), db, actor)
        assert changed["review_fingerprint"] == baseline["review_fingerprint"]
        assert changed["lease_relationship_readiness"] == baseline["lease_relationship_readiness"]
        assert changed["customer_business_mutation"] is False
        preview = list_yardi_lease_relationships(
            run.id, Response(), offset=0, limit=10,
            db=db, current_user=actor,
        )["items"][0]
        assert preview["blockers"] == []
        assert preview["relationship_review_current"] is True
        assert preview["occupancy_or_lease_authorized"] is False
        snapshot = get_yardi_review_dry_run_status(
            run.id, Response(), db, actor,
        )
        assert snapshot["is_current"] is True
        assert snapshot["saved_review_fingerprint"] == saved["review_fingerprint"]
        replay = dry_run_yardi_review(run.id, db, actor)
        assert replay["replayed"] is True
        assert accept_yardi_staged_lease_relationship(
            run.id, lease.id, db, actor,
        )["replayed"] is True

        setattr(tenant, profile_field, previous_value)
        db.commit()
        db.refresh(tenant)
        db.refresh(prop)
        db.refresh(unit)
        assert getattr(tenant, profile_field) == previous_value
        restored = get_yardi_reconciliation(run.id, Response(), db, actor)
        assert restored["review_fingerprint"] == baseline["review_fingerprint"]
        assert db.query(Lease).count() == before_leases
        assert db.query(PlatformMigrationItem).filter(
            PlatformMigrationItem.run_id == run.id,
        ).count() == before_mappings
        assert lease.resolution_action == "ACCEPT_RELATIONSHIP"
        assert prop.name == "Original"
        assert unit.property_id == prop.id
    finally:
        db.close()
        engine.dispose()


@pytest.mark.parametrize("profile_field,replacement", [
    ("first_name", "Renamed Tenant While Contested"),
    ("last_name", "Updated Contested Last Name"),
    ("hashed_password", "rotated-contested-fixture-hash"),
])
def test_contested_lease_historic_identity_stays_blocked_after_tenant_profile_update(
    profile_field, replacement,
):
    """Cosmetic or credential edits cannot resolve another Yardi run's target claim."""
    db, engine = _session()
    try:
        actor, org, run, prop, alternate, unit, tenant, lease = _seed(
            db, slug=f"yardi-lease-contested-profile-{profile_field}",
        )
        before_leases = db.query(Lease).count()
        assert accept_yardi_staged_lease_relationship(
            run.id, lease.id, db, actor,
        )["replayed"] is False
        baseline = get_yardi_reconciliation(run.id, Response(), db, actor)
        assert baseline["lease_relationship_readiness"]["source_review_ready"] == 1

        other_run = PlatformMigrationRun(
            organization_id=org.id, provider="YARDI",
            source_account_ref="historic-competing-tenant-review", status="DRAFT",
        )
        db.add(other_run)
        db.flush()
        upload = stage_yardi_file(
            db, run=other_run, filename="competing-tenant-review.csv",
            content=b"Resident Ref,Full Name\nT-OTHER,Another Tenant Source\n",
            resource_override="TENANTS", sheet_name=None,
            explicit_mapping={"source_id": "Resident Ref", "name": "Full Name"},
            platform_user_id=actor.id,
        )
        db.commit()
        historical = db.query(PlatformMigrationStagedRow).filter(
            PlatformMigrationStagedRow.upload_id == upload.upload.id,
        ).one()
        historical.resolution_action = "MATCH_EXISTING"
        historical.resolution_target_tenant_user_id = tenant.id
        db.commit()

        contested = get_yardi_reconciliation(run.id, Response(), db, actor)
        readiness = contested["lease_relationship_readiness"]
        assert readiness["identity_target_review_collisions"] == 1
        assert readiness["accepted_relationship_stale"] == 1
        assert readiness["source_review_ready"] == 0
        assert readiness["complete_identity_links"] == 0
        saved = dry_run_yardi_review(run.id, db, actor)
        assert saved["review_fingerprint"] == contested["review_fingerprint"]

        previous_value = getattr(tenant, profile_field)
        setattr(tenant, profile_field, replacement)
        db.commit()
        current = get_yardi_reconciliation(run.id, Response(), db, actor)
        assert current["lease_relationship_readiness"] == contested["lease_relationship_readiness"]
        assert current["review_fingerprint"] == contested["review_fingerprint"]
        status = get_yardi_review_dry_run_status(
            run.id, Response(), db, actor,
        )
        assert status["is_current"] is True
        assert status["saved_review_fingerprint"] == saved["review_fingerprint"]
        assert dry_run_yardi_review(run.id, db, actor)["replayed"] is True
        preview = list_yardi_lease_relationships(
            run.id, Response(), offset=0, limit=10,
            db=db, current_user=actor,
        )["items"][0]
        assert "TENANT_TARGET_REVIEW_COLLISION" in preview["blockers"]
        assert preview["relationship_review_current"] is False
        assert preview["occupancy_or_lease_authorized"] is False
        with pytest.raises(HTTPException) as still_blocked:
            accept_yardi_staged_lease_relationship(run.id, lease.id, db, actor)
        assert still_blocked.value.status_code == 409
        assert current["customer_business_mutation"] is False

        # A genuine change to WHICH historical source contests the Tenant
        # must expire this same saved review, even during a benign profile edit.
        historical.source_id = "T-OTHER-2"
        db.commit()
        changed_claim = get_yardi_reconciliation(run.id, Response(), db, actor)
        assert changed_claim["lease_relationship_readiness"] == contested["lease_relationship_readiness"]
        assert changed_claim["review_fingerprint"] != saved["review_fingerprint"]
        expired = get_yardi_review_dry_run_status(
            run.id, Response(), db, actor,
        )
        assert expired["is_current"] is False
        assert expired["saved_review_fingerprint"] == saved["review_fingerprint"]
        assert "TENANT_TARGET_REVIEW_COLLISION" in list_yardi_lease_relationships(
            run.id, Response(), offset=0, limit=10, db=db, current_user=actor,
        )["items"][0]["blockers"]
        with pytest.raises(HTTPException) as changed_source_still_blocked:
            accept_yardi_staged_lease_relationship(run.id, lease.id, db, actor)
        assert changed_source_still_blocked.value.status_code == 409

        historical.source_id = "T-OTHER"
        db.commit()
        assert get_yardi_reconciliation(
            run.id, Response(), db, actor,
        )["review_fingerprint"] == saved["review_fingerprint"]
        assert get_yardi_review_dry_run_status(
            run.id, Response(), db, actor,
        )["is_current"] is True

        setattr(tenant, profile_field, previous_value)
        historical.source_id = "T1"
        db.commit()
        restored = get_yardi_reconciliation(run.id, Response(), db, actor)
        assert restored["review_fingerprint"] == baseline["review_fingerprint"]
        assert restored["lease_relationship_readiness"]["source_review_ready"] == 1
        assert restored["lease_relationship_readiness"]["identity_target_review_collisions"] == 0
        assert get_yardi_review_dry_run_status(
            run.id, Response(), db, actor,
        )["is_current"] is False
        assert accept_yardi_staged_lease_relationship(
            run.id, lease.id, db, actor,
        )["replayed"] is True
        db.refresh(tenant)
        db.refresh(unit)
        db.refresh(prop)
        assert getattr(tenant, profile_field) == previous_value
        assert unit.property_id == prop.id and prop.name == "Original"
        assert db.query(Lease).count() == before_leases
    finally:
        db.close()
        engine.dispose()
