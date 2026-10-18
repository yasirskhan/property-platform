"""Phase 4.16 RentManager run scope and deny-by-default regressions."""
import pytest
from fastapi import HTTPException, Response
from pydantic import ValidationError

from app.models.platform_migration import PlatformMigrationRun
from app.models.platform_user import PlatformUserRole
from app.routers.rentmanager_migrations import (
    create_rentmanager_run, get_rentmanager_run, list_rentmanager_runs,
    get_rentmanager_resource_readiness, rentmanager_run_source_readiness,
    inspect_rentmanager_source_headers, review_rentmanager_mapping, RentManagerMappingProposal,
)
from app.schemas.rentmanager_migration import RentManagerRunCreateIn
from test_yardi_migrations import _session, _org, _platform_user


def test_rentmanager_run_is_provider_scoped_and_audited_without_customer_mutation():
    from app.models.property import Property
    from app.models.audit_log import AuditLog
    db, engine = _session()
    try:
        admin = _platform_user(db, PlatformUserRole.PLATFORM_ADMIN)
        org = _org(db, "rentmanager-foundation-org")
        before = db.query(Property).count()
        result = create_rentmanager_run(
            RentManagerRunCreateIn(organization_id=org.id, source_account_ref="client-01"),
            db, admin,
        )
        assert result.provider == "RENTMANAGER"
        assert result.status == "DRAFT"
        response = Response()
        assert get_rentmanager_run(result.id, response, db, admin).id == result.id
        assert response.headers["cache-control"] == "no-store"
        rows_response = Response()
        rows = list_rentmanager_runs(rows_response, org.id, 100, db, admin)
        assert [row.id for row in rows] == [result.id]
        assert rows_response.headers["cache-control"] == "no-store"
        assert db.query(Property).count() == before
        assert db.query(AuditLog).filter(AuditLog.action == "rentmanager_migration_run_created").count() == 1
        db.add(PlatformMigrationRun(
            organization_id=org.id, provider="YARDI",
            source_account_ref="yardi-01", status="DRAFT",
        ))
        db.commit()
        assert [item.id for item in list_rentmanager_runs(Response(), None, 100, db, admin)] == [result.id]
        with pytest.raises(HTTPException) as missing:
            get_rentmanager_run(db.query(PlatformMigrationRun).filter(
                PlatformMigrationRun.provider == "YARDI",
            ).one().id, Response(), db, admin)
        assert missing.value.status_code == 404
    finally:
        db.close()
        engine.dispose()


def test_rentmanager_denies_sales_and_secret_source_reference():
    db, engine = _session()
    try:
        sales = _platform_user(db, PlatformUserRole.PLATFORM_SALES)
        org = _org(db, "rentmanager-role-gate")
        with pytest.raises(HTTPException) as forbidden:
            create_rentmanager_run(
                RentManagerRunCreateIn(organization_id=org.id, source_account_ref="account"),
                db, sales,
            )
        assert forbidden.value.status_code == 403
        assert db.query(PlatformMigrationRun).count() == 0
        with pytest.raises(ValidationError):
            RentManagerRunCreateIn(organization_id=org.id, source_account_ref="Bearer secret")
        with pytest.raises(ValidationError):
            RentManagerRunCreateIn(organization_id=org.id, source_account_ref='{"raw":"value"}')
        with pytest.raises(ValidationError):
            RentManagerRunCreateIn(organization_id=org.id, source_account_ref="ok", password="forbidden")
    finally:
        db.close()
        engine.dispose()


def test_rentmanager_resource_readiness_blocks_unverified_transports():
    db, engine = _session()
    try:
        support = _platform_user(db, PlatformUserRole.PLATFORM_SUPPORT)
        sales = _platform_user(db, PlatformUserRole.PLATFORM_SALES)
        response = Response()
        readiness = get_rentmanager_resource_readiness(response, support)
        assert response.headers["cache-control"] == "no-store"
        assert readiness["provider"] == "RENTMANAGER"
        assert readiness["run_foundation_available"] is True
        assert readiness["source_inspection_enabled"] is True
        assert readiness["file_upload_enabled"] is False
        assert readiness["official_api_enabled"] is False
        assert readiness["controlled_commit_enabled"] is False
        assert readiness["customer_business_mutation"] is False
        with pytest.raises(HTTPException) as denied:
            get_rentmanager_resource_readiness(Response(), sales)
        assert denied.value.status_code == 403
    finally:
        db.close()
        engine.dispose()


def test_rentmanager_inactive_organization_is_rejected_on_create_and_read():
    db, engine = _session()
    try:
        admin = _platform_user(db, PlatformUserRole.PLATFORM_ADMIN)
        org = _org(db, "rentmanager-inactive-org")
        run = PlatformMigrationRun(
            organization_id=org.id, provider="RENTMANAGER",
            source_account_ref="existing", status="DRAFT",
        )
        db.add(run)
        db.commit()
        org.is_active = False
        db.commit()
        with pytest.raises(HTTPException) as create_denied:
            create_rentmanager_run(
                RentManagerRunCreateIn(organization_id=org.id, source_account_ref="new"),
                db, admin,
            )
        assert create_denied.value.status_code == 404
        with pytest.raises(HTTPException) as read_denied:
            get_rentmanager_run(run.id, Response(), db, admin)
        assert read_denied.value.status_code == 404
        assert list_rentmanager_runs(Response(), None, 100, db, admin) == []
        with pytest.raises(HTTPException) as list_denied:
            list_rentmanager_runs(Response(), org.id, 100, db, admin)
        assert list_denied.value.status_code == 404
        assert db.query(PlatformMigrationRun).count() == 1
    finally:
        db.close()
        engine.dispose()


def test_rentmanager_support_read_only_and_billing_denied():
    db, engine = _session()
    try:
        support = _platform_user(db, PlatformUserRole.PLATFORM_SUPPORT)
        billing = _platform_user(db, PlatformUserRole.PLATFORM_BILLING)
        org = _org(db, "rentmanager-support-readonly")
        run = PlatformMigrationRun(
            organization_id=org.id, provider="RENTMANAGER",
            source_account_ref="existing", status="DRAFT",
        )
        db.add(run)
        db.commit()
        assert get_rentmanager_run(run.id, Response(), db, support).id == run.id
        assert len(list_rentmanager_runs(Response(), org.id, 100, db, support)) == 1
        with pytest.raises(HTTPException) as write_denied:
            create_rentmanager_run(
                RentManagerRunCreateIn(organization_id=org.id, source_account_ref="new"),
                db, support,
            )
        assert write_denied.value.status_code == 403
        with pytest.raises(HTTPException) as billing_denied:
            get_rentmanager_run(run.id, Response(), db, billing)
        assert billing_denied.value.status_code == 403
        assert db.query(PlatformMigrationRun).count() == 1
    finally:
        db.close()
        engine.dispose()


def test_rentmanager_per_run_source_gate_enforces_provider_and_view_role():
    db, engine = _session()
    try:
        admin = _platform_user(db, PlatformUserRole.PLATFORM_ADMIN)
        support = _platform_user(db, PlatformUserRole.PLATFORM_SUPPORT)
        billing = _platform_user(db, PlatformUserRole.PLATFORM_BILLING)
        org = _org(db, "rentmanager-source-readiness")
        own = PlatformMigrationRun(
            organization_id=org.id, provider="RENTMANAGER",
            source_account_ref="nonsecret-label", status="DRAFT",
        )
        other = PlatformMigrationRun(
            organization_id=org.id, provider="YARDI",
            source_account_ref="other", status="DRAFT",
        )
        db.add_all([own, other])
        db.commit()
        response = Response()
        readiness = rentmanager_run_source_readiness(own.id, response, db, support)
        assert response.headers["cache-control"] == "no-store"
        assert readiness["run_id"] == own.id
        assert readiness["source_account_bound"] is True
        assert readiness["source_inspection_enabled"] is True
        assert readiness["file_upload_enabled"] is False
        assert readiness["official_api_enabled"] is False
        assert readiness["controlled_commit_enabled"] is False
        assert readiness["customer_business_mutation"] is False
        with pytest.raises(HTTPException) as wrong_provider:
            rentmanager_run_source_readiness(other.id, Response(), db, admin)
        assert wrong_provider.value.status_code == 404
        with pytest.raises(HTTPException) as denied:
            rentmanager_run_source_readiness(own.id, Response(), db, billing)
        assert denied.value.status_code == 403
    finally:
        db.close()
        engine.dispose()


def test_rentmanager_source_inspection_is_bounded_read_only_and_provider_scoped():
    import asyncio
    from io import BytesIO
    from fastapi import UploadFile
    from app.models.platform_migration import PlatformMigrationUpload
    db, engine = _session()
    try:
        admin = _platform_user(db, PlatformUserRole.PLATFORM_ADMIN)
        support = _platform_user(db, PlatformUserRole.PLATFORM_SUPPORT)
        org = _org(db, "rentmanager-inspect-scope")
        valid = PlatformMigrationRun(
            organization_id=org.id, provider="RENTMANAGER",
            source_account_ref="export", status="DRAFT",
        )
        yardi = PlatformMigrationRun(
            organization_id=org.id, provider="YARDI",
            source_account_ref="export", status="DRAFT",
        )
        db.add_all([valid, yardi])
        db.commit()
        file = UploadFile(filename="units.csv", file=BytesIO(b"Unit,Property\n1,Alpha\n2,Beta\n"))
        response = Response()
        result = asyncio.run(inspect_rentmanager_source_headers(valid.id, response, file, None, db, admin))
        assert response.headers["cache-control"] == "no-store"
        assert result["provider"] == "RENTMANAGER"
        assert result["row_count"] == 2
        assert result["source_file_bytes"] == len(b"Unit,Property\n1,Alpha\n2,Beta\n")
        assert result["headers"] == ["Unit", "Property"]
        assert result["headers_validated_unique"] is True
        assert result["headers_require_review"] is False
        import hashlib
        assert result["source_file_sha256"] == hashlib.sha256(b"Unit,Property\n1,Alpha\n2,Beta\n").hexdigest()
        assert result["column_inventory"] == [
            {"index": 0, "source_header": "Unit", "mapping_status": "UNMAPPED"},
            {"index": 1, "source_header": "Property", "mapping_status": "UNMAPPED"},
        ]
        assert result["suggested_target_fields"] == []
        assert result["source_contract_verified"] is False
        assert result["explicit_mapping_required"] is True
        assert result["can_stage_import"] is False
        assert result["can_commit_import"] is False
        assert result["raw_source_stored"] is False
        assert result["staging_mutation"] is False
        assert result["customer_business_mutation"] is False
        assert db.query(PlatformMigrationUpload).count() == 0
        with pytest.raises(HTTPException) as wrong_provider:
            asyncio.run(inspect_rentmanager_source_headers(
                yardi.id, Response(), UploadFile(filename="data.csv", file=BytesIO(b"A\nx\n")), None, db, admin,
            ))
        assert wrong_provider.value.status_code == 404
        with pytest.raises(HTTPException) as read_only:
            asyncio.run(inspect_rentmanager_source_headers(
                valid.id, Response(), UploadFile(filename="data.csv", file=BytesIO(b"A\nx\n")), None, db, support,
            ))
        assert read_only.value.status_code == 403
    finally:
        db.close()
        engine.dispose()


def test_rentmanager_source_inspection_rejects_ambiguous_headers():
    import asyncio
    from io import BytesIO
    from fastapi import UploadFile
    db, engine = _session()
    try:
        admin = _platform_user(db, PlatformUserRole.PLATFORM_ADMIN)
        org = _org(db, "rentmanager-ambiguous-headers")
        run = PlatformMigrationRun(
            organization_id=org.id, provider="RENTMANAGER",
            source_account_ref="export", status="DRAFT",
        )
        db.add(run)
        db.commit()
        for csv_bytes in (b"Unit,UNIT\n1,2\n", b"Unit,,Property\n1,2,3\n"):
            with pytest.raises(HTTPException) as error:
                asyncio.run(inspect_rentmanager_source_headers(
                    run.id, Response(),
                    UploadFile(filename="ambiguous.csv", file=BytesIO(csv_bytes)),
                    None, db, admin,
                ))
            assert error.value.status_code == 422
    finally:
        db.close()
        engine.dispose()


def test_rentmanager_source_inspection_rejects_unsupported_formats():
    import asyncio
    from io import BytesIO
    from fastapi import UploadFile
    db, engine = _session()
    try:
        admin = _platform_user(db, PlatformUserRole.PLATFORM_ADMIN)
        org = _org(db, "rentmanager-inspect-invalid-format")
        run = PlatformMigrationRun(
            organization_id=org.id, provider="RENTMANAGER",
            source_account_ref="export", status="DRAFT",
        )
        db.add(run)
        db.commit()
        with pytest.raises(HTTPException) as err:
            asyncio.run(inspect_rentmanager_source_headers(
                run.id, Response(), UploadFile(filename="unsafe.xlsm", file=BytesIO(b"invalid")),
                None, db, admin,
            ))
        assert err.value.status_code == 422
    finally:
        db.close()
        engine.dispose()


def test_rentmanager_mapping_review_does_not_stage_or_authorize_records():
    from app.models.platform_migration import PlatformMigrationUpload
    db, engine = _session()
    try:
        admin = _platform_user(db, PlatformUserRole.PLATFORM_ADMIN)
        org = _org(db, "rentmanager-review-proposals")
        run = PlatformMigrationRun(
            organization_id=org.id, provider="RENTMANAGER",
            source_account_ref="export", status="DRAFT",
        )
        db.add(run)
        db.commit()
        result = review_rentmanager_mapping(
            run.id,
            RentManagerMappingProposal(
                source_headers=["Property ID", "Unit ID"],
                column_mapping={"source_id": "Property ID"},
            ),
            Response(), db, admin,
        )
        assert result["unmapped_headers"] == ["Unit ID"]
        assert result["mapping_stored"] is False
        assert result["mapping_authorized"] is False
        assert result["can_stage_import"] is False
        assert result["can_commit_import"] is False
        assert db.query(PlatformMigrationUpload).count() == 0
        with pytest.raises(HTTPException) as error:
            review_rentmanager_mapping(
                run.id,
                RentManagerMappingProposal(
                    source_headers=["Property ID"],
                    column_mapping={"source_id": "Unknown"},
                ),
                Response(), db, admin,
            )
        assert error.value.status_code == 422
    finally:
        db.close()
        engine.dispose()
