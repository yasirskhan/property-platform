"""Yardi staged source-ID collisions are audited as read-only metadata."""
import pytest
from fastapi import HTTPException, Response

from app.models.lease import Lease
from app.models.platform_migration import PlatformMigrationRun, PlatformMigrationUpload, PlatformMigrationStagedRow
from app.models.platform_user import PlatformUserRole
from app.models.user import User
from app.routers.yardi_migrations import list_yardi_source_collisions, skip_yardi_staged_row, YardiRowSkipIn
from app.services.yardi_file_ingestion import stage_yardi_file
from test_yardi_migrations import _org, _platform_user, _session


def _stage(db, actor, run, resource, body, *, optional_email=False):
    mapping = {"source_id": "ID", "name": "Name"}
    if optional_email:
        mapping["email"] = "Email"
    result = stage_yardi_file(
        db, run=run, filename=resource.lower() + ".csv",
        content=body, resource_override=resource, sheet_name=None,
        explicit_mapping=mapping, platform_user_id=actor.id,
    )
    db.commit()
    return result.upload.id


def test_yardi_run_collision_inventory_distinguishes_changed_source_from_identical_rows():
    db, engine = _session()
    try:
        admin = _platform_user(db, PlatformUserRole.PLATFORM_ADMIN)
        support = _platform_user(db, PlatformUserRole.PLATFORM_SUPPORT)
        org = _org(db, "yardi-collision-review")
        outside = _org(db, "yardi-collision-external")
        run = PlatformMigrationRun(
            organization_id=org.id, provider="YARDI",
            source_account_ref="export-review", status="DRAFT",
        )
        other = PlatformMigrationRun(
            organization_id=outside.id, provider="YARDI",
            source_account_ref="another-organization", status="DRAFT",
        )
        buildium = PlatformMigrationRun(
            organization_id=org.id, provider="BUILDIUM",
            source_account_ref="another-provider", status="DRAFT",
        )
        db.add_all([run, other, buildium])
        db.commit()
        before_leases, before_users = db.query(Lease).count(), db.query(User).count()
        first = _stage(
            db, admin, run, "TENANTS",
            b"ID,Name,Email\nT1,Alice,alice@example.test\n",
        )
        second = _stage(
            db, admin, run, "TENANTS",
            b"ID,Name,Email\nT1,Alicia,alice@example.test\n",
        )
        third = _stage(
            db, admin, run, "TENANTS",
            b"ID,Name,Email\nT1,Alicia,alice@example.test\n",
            optional_email=True,
        )
        assert len({first, second, third}) == 3
        _stage(db, admin, run, "OWNERS", b"ID,Name,Email\nT1,Owner,owner@example.test\n")
        _stage(db, admin, other, "TENANTS", b"ID,Name,Email\nT1,Other,other@example.test\n")
        _stage(db, admin, run, "VENDORS", b"ID,Name,Email\nV1,Vendor A,a@example.test\n")
        _stage(db, admin, run, "VENDORS", b"ID,Name,Email\nV1,Vendor B,b@example.test\n")
        response = Response()
        results = list_yardi_source_collisions(
            run.id, response, resource=None, offset=0, limit=10,
            db=db, current_user=support,
        )
        assert response.headers["cache-control"] == "no-store"
        assert results["total"] == 2
        assert results["auto_merge_enabled"] is False
        assert results["customer_business_mutation"] is False
        assert [item["resource"] for item in results["items"]] == ["TENANTS", "VENDORS"]
        tenant = results["items"][0]
        assert tenant["source_id"] == "T1"
        assert tenant["row_count"] == tenant["upload_count"] == 3
        assert tenant["source_versions"] == 2
        assert tenant["conflicting_source_versions"] is True
        assert tenant["requires_manual_reconciliation"] is True
        assert tenant["skipped_rows"] == 0
        assert tenant["remaining_unskipped_rows"] == 3
        assert tenant["disposition_status"] == "UNRESOLVED_MULTIPLE"
        assert [r["upload_id"] for r in tenant["sampled_rows"]] == [first, second, third]
        assert tenant["sample_truncated"] is False
        # Two explicit audit-reason SKIPs leave exactly one unskipped source
        # without erasing prior versions or making any customer change.
        for upload_id in (second, third):
            duplicate = db.query(PlatformMigrationStagedRow).filter(
                PlatformMigrationStagedRow.upload_id == upload_id,
                PlatformMigrationStagedRow.run_id == run.id,
            ).one()
            decision = skip_yardi_staged_row(
                run.id, duplicate.id, YardiRowSkipIn(reason_code="DUPLICATE_SOURCE"),
                db, admin,
            )
            assert decision["replayed"] is False
        reconciled = list_yardi_source_collisions(
            run.id, Response(), resource="TENANTS", offset=0, limit=10,
            db=db, current_user=support,
        )["items"][0]
        assert reconciled["source_versions"] == 2
        assert reconciled["row_count"] == 3
        assert reconciled["skipped_rows"] == 2
        assert reconciled["remaining_unskipped_rows"] == 1
        assert reconciled["disposition_status"] == "ONE_UNSKIPPED"
        assert [x["resolution_action"] for x in reconciled["sampled_rows"]] == [
            None, "SKIP", "SKIP",
        ]
        assert [x["skip_reason_code"] for x in reconciled["sampled_rows"]] == [
            None, "DUPLICATE_SOURCE", "DUPLICATE_SOURCE",
        ]
        original = db.query(PlatformMigrationStagedRow).filter(
            PlatformMigrationStagedRow.upload_id == first,
        ).one()
        skip_yardi_staged_row(
            run.id, original.id, YardiRowSkipIn(reason_code="NOT_IN_SCOPE"),
            db, admin,
        )
        all_skipped = list_yardi_source_collisions(
            run.id, Response(), resource="TENANTS", offset=0, limit=10,
            db=db, current_user=support,
        )["items"][0]
        assert all_skipped["skipped_rows"] == 3
        assert all_skipped["remaining_unskipped_rows"] == 0
        assert all_skipped["disposition_status"] == "ALL_SKIPPED"
        assert db.query(Lease).count() == before_leases
        assert db.query(User).count() == before_users
        assert "alice@example.test" not in str(results)
        assert "Alicia" not in str(results)
        assert db.query(Lease).count() == before_leases
        assert db.query(User).count() == before_users
        page = list_yardi_source_collisions(
            run.id, Response(), resource=None, offset=1, limit=1,
            db=db, current_user=admin,
        )
        assert page["total"] == 2
        assert len(page["items"]) == 1 and page["items"][0]["source_id"] == "V1"
        filtered = list_yardi_source_collisions(
            run.id, Response(), resource="OWNERS", offset=0, limit=10,
            db=db, current_user=admin,
        )
        assert filtered["total"] == 0 and filtered["items"] == []
        foreign = list_yardi_source_collisions(
            other.id, Response(), resource=None, offset=0, limit=10,
            db=db, current_user=admin,
        )
        assert foreign["total"] == 0
        with pytest.raises(HTTPException) as wrong_provider:
            list_yardi_source_collisions(
                buildium.id, Response(), resource=None, offset=0, limit=10,
                db=db, current_user=admin,
            )
        assert wrong_provider.value.status_code == 404
    finally:
        db.close()
        engine.dispose()


def test_yardi_disposition_uses_all_versions_when_sample_is_truncated():
    """The first ten references must not mask later explicit skip decisions."""
    db, engine = _session()
    try:
        actor = _platform_user(db, PlatformUserRole.PLATFORM_ADMIN)
        org = _org(db, "yardi-collision-truncated-sample")
        run = PlatformMigrationRun(
            organization_id=org.id, provider="YARDI",
            source_account_ref="many-versions", status="DRAFT",
        )
        db.add(run)
        db.commit()
        upload_id = _stage(
            db, actor, run, "VENDORS", b"ID,Name\nV1,Existing Vendor\n",
        )
        first = db.query(PlatformMigrationStagedRow).filter(
            PlatformMigrationStagedRow.upload_id == upload_id,
        ).one()
        for index in range(11):
            db.add(PlatformMigrationStagedRow(
                upload_id=upload_id, run_id=run.id, organization_id=org.id,
                provider="YARDI", resource="VENDORS",
                row_number=first.row_number + index + 1,
                source_id="V1", disposition="REVIEW",
                row_fingerprint="different-fingerprint-" + str(index),
                normalized_data={"source_id": "V1", "name": "private value"},
                correction_evidence=[], warnings=[], errors=[],
            ))
        db.commit()
        rows = db.query(PlatformMigrationStagedRow).filter(
            PlatformMigrationStagedRow.run_id == run.id,
            PlatformMigrationStagedRow.source_id == "V1",
        ).order_by(PlatformMigrationStagedRow.id.asc()).all()
        assert len(rows) == 12
        for duplicate in rows[1:]:
            skip_yardi_staged_row(
                run.id, duplicate.id,
                YardiRowSkipIn(reason_code="DUPLICATE_SOURCE"),
                db, actor,
            )
        response = list_yardi_source_collisions(
            run.id, Response(), resource="VENDORS", offset=0, limit=10,
            db=db, current_user=actor,
        )
        group = response["items"][0]
        assert group["row_count"] == 12
        assert len(group["sampled_rows"]) == 10
        assert group["sample_truncated"] is True
        assert group["skipped_rows"] == 11
        assert group["remaining_unskipped_rows"] == 1
        assert group["disposition_status"] == "ONE_UNSKIPPED"
        assert "private value" not in str(response)
        assert db.query(Lease).count() == 0
    finally:
        db.close()
        engine.dispose()


def test_yardi_collision_inventory_denies_unpermitted_platform_staff():
    db, engine = _session()
    try:
        sales = _platform_user(db, PlatformUserRole.PLATFORM_SALES)
        org = _org(db, "yardi-collision-access")
        run = PlatformMigrationRun(
            organization_id=org.id, provider="YARDI",
            source_account_ref="collision-access", status="DRAFT",
        )
        db.add(run)
        db.commit()
        with pytest.raises(HTTPException) as denied:
            list_yardi_source_collisions(
                run.id, Response(), resource=None, offset=0, limit=10,
                db=db, current_user=sales,
            )
        assert denied.value.status_code == 403
    finally:
        db.close()
        engine.dispose()
