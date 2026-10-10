from __future__ import annotations

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import init_db  # noqa: F401
from app.core.database import Base
from app.core.security import hash_password
from app.models.audit_log import AuditLog
from app.models.bank_account import BankAccount
from app.models.gl_account import GLAccount
from app.models.gl_transaction import GLTransaction
from app.models.platform_migration import PlatformMigrationItem, PlatformMigrationRun
from app.models.platform_user import PlatformUser, PlatformUserRole
from app.models.user import Organization
from app.routers import buildium_migrations as api
from app.schemas.buildium_migration import (
    BuildiumApiBankAccountCommitIn,
    BuildiumApiBankAccountDryRunIn,
    BuildiumBankAccountResolutionIn,
)
from app.services import buildium_api_transport as transport
from app.services.buildium_api_transport import BuildiumApiFetchResult


def _session():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, expire_on_commit=False)(), engine


def _admin(db):
    row = PlatformUser(
        email="buildium-api-bank-admin@example.com",
        hashed_password=hash_password("test-password"),
        first_name="Buildium", last_name="Bank",
        role=PlatformUserRole.PLATFORM_ADMIN, is_active=True,
    )
    db.add(row); db.commit(); return row


def _org(db):
    row = Organization(
        name="Buildium API Bank Target",
        slug="buildium-api-bank-target", is_active=True,
    )
    db.add(row); db.commit(); return row


def _run(db, org):
    row = PlatformMigrationRun(
        organization_id=org.id, provider="BUILDIUM",
        source_account_ref="sandbox-account-A", status="DRAFT",
    )
    db.add(row); db.commit(); return row


def _record(**changes):
    row = {
        "Id": 8101,
        "Name": "Provider Operating Account",
        "BankName": "DO-NOT-PERSIST-BANK-NAME",
        "BankAccountType": "Checking",
        "IsActive": True,
        "AccountNumber": "DO-NOT-PERSIST-ACCOUNT-NUMBER",
        "UnmaskedAccountNumber": "DO-NOT-PERSIST-UNMASKED-NUMBER",
        "RoutingNumber": "DO-NOT-PERSIST-ROUTING-NUMBER",
        "Balance": 987654.32,
        "Description": "DO-NOT-PERSIST-BANK-DESCRIPTION",
        "GLAccount": {
            "Id": 7001, "AccountNumber": "1150", "Name": "Rental Trust",
            "Description": "DO-NOT-PERSIST-GL-DESCRIPTION",
            "Type": "Asset", "IsBankAccount": True,
        },
        "CheckPrintingInfo": {
            "BankInformationLine1": "DO-NOT-PERSIST-CHECK-PRINTING"
        },
        "ElectronicPayments": {"DailyLimit": 100000},
    }
    row.update(changes)
    return row


def _target(db, run):
    gl = GLAccount(
        organization_id=run.organization_id, gl_number="1150",
        name="Rental Trust", account_type="ASSET", is_active=True,
    )
    db.add(gl); db.flush()
    bank = BankAccount(
        organization_id=run.organization_id, name="Local Client Trust",
        bank_name="Local Bank", routing_number="LOCAL-ROUTING-UNCHANGED",
        account_number="LOCAL-ACCOUNT-UNCHANGED", gl_account_id=gl.id,
        account_type="OPERATING", is_active=True,
    )
    db.add(bank); db.flush()
    db.add(PlatformMigrationItem(
        run_id=run.id, organization_id=run.organization_id,
        provider="BUILDIUM", resource="GL_ACCOUNTS", source_id="7001",
        target_entity="GL_ACCOUNT", target_id=gl.id,
        source_fingerprint="g" * 64,
    ))
    db.commit()
    return bank


class _Response:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload
    def json(self):
        return self._payload


def test_buildium_transport_fetches_bank_accounts_from_fixed_endpoint(monkeypatch):
    monkeypatch.setattr(transport.settings, "BUILDIUM_API_MODE", "sandbox")
    monkeypatch.setattr(transport.settings, "BUILDIUM_API_CLIENT_ID", "client-id")
    monkeypatch.setattr(transport.settings, "BUILDIUM_API_CLIENT_SECRET", "bank-secret")
    monkeypatch.setattr(
        transport.settings, "BUILDIUM_API_SOURCE_ACCOUNT_REF", "sandbox-account-A"
    )
    calls = []
    def fake_get(url, *, headers, params, timeout):
        calls.append((url, headers.copy(), params.copy(), timeout))
        return _Response(200, [_record()])
    monkeypatch.setattr(transport.requests, "get", fake_get)

    result = transport.fetch_bank_accounts(
        expected_source_account_ref="sandbox-account-A"
    )
    assert result.records[0]["Id"] == 8101
    assert calls[0][0] == "https://apisandbox.buildium.com/v1/bankaccounts"
    assert calls[0][1]["x-buildium-client-secret"] == "bank-secret"
    assert calls[0][2] == {"offset": 0, "limit": 500}


def test_buildium_api_bank_account_maps_existing_identity_only_and_keeps_sensitive_target_fields(monkeypatch):
    db, engine = _session()
    try:
        admin = _admin(db); org = _org(db); run = _run(db, org)
        target = _target(db, run)
        original = {
            "name": target.name, "bank_name": target.bank_name,
            "routing_number": target.routing_number,
            "account_number": target.account_number,
            "account_type": target.account_type,
            "gl_account_id": target.gl_account_id,
        }

        def fetched(*, expected_source_account_ref):
            assert expected_source_account_ref == "sandbox-account-A"
            return BuildiumApiFetchResult(
                records=[_record()], mode="sandbox", request_count=1
            )
        monkeypatch.setattr(api, "fetch_bank_accounts", fetched)

        resolution = BuildiumBankAccountResolutionIn(
            source_id=8101, action="MATCH_EXISTING",
            target_bank_account_id=target.id,
        )
        reviewed = api.api_dry_run_buildium_bank_accounts(
            run.id, BuildiumApiBankAccountDryRunIn(resolutions=[resolution]),
            db=db, current_user=admin,
        )
        assert reviewed.invalid == 0
        assert reviewed.reviewable == 1
        assert reviewed.rows[0].mapped["sensitive_bank_fields_exposed"] is False

        committed = api.api_commit_buildium_bank_accounts(
            run.id,
            BuildiumApiBankAccountCommitIn(
                fingerprint=reviewed.fingerprint, resolutions=[resolution]
            ),
            db=db, current_user=admin,
        )
        assert committed.matched_existing == 1
        mapping = db.query(PlatformMigrationItem).filter(
            PlatformMigrationItem.resource == "BANK_ACCOUNTS"
        ).one()
        assert mapping.target_entity == "BANK_ACCOUNT"
        assert mapping.target_id == target.id
        assert db.query(BankAccount).count() == 1
        assert db.query(GLTransaction).count() == 0

        db.refresh(target)
        for key, value in original.items():
            assert getattr(target, key) == value

        with pytest.raises(ValidationError):
            BuildiumApiBankAccountDryRunIn(client_secret="secret")
        with pytest.raises(ValidationError):
            BuildiumApiBankAccountCommitIn(
                fingerprint=reviewed.fingerprint, records=[_record()]
            )

        audit = "\n".join(
            str(row.new_value or "")
            for row in db.query(AuditLog).filter(
                AuditLog.entity_type == "platform_migration_run"
            ).all()
        )
        for secret in (
            "DO-NOT-PERSIST-BANK-NAME",
            "DO-NOT-PERSIST-ACCOUNT-NUMBER",
            "DO-NOT-PERSIST-UNMASKED-NUMBER",
            "DO-NOT-PERSIST-ROUTING-NUMBER",
            "DO-NOT-PERSIST-BANK-DESCRIPTION",
            "DO-NOT-PERSIST-GL-DESCRIPTION",
            "DO-NOT-PERSIST-CHECK-PRINTING",
        ):
            assert secret not in audit
        assert '"credentials_stored":false' in audit.lower()
        assert '"raw_response_stored":false' in audit.lower()
    finally:
        db.close(); engine.dispose()


def test_buildium_api_bank_account_commit_refetch_detects_drift_and_routes_exist(monkeypatch):
    from app.main import app

    db, engine = _session()
    try:
        admin = _admin(db); org = _org(db); run = _run(db, org)
        target = _target(db, run)
        resolution = BuildiumBankAccountResolutionIn(
            source_id=8101, action="MATCH_EXISTING",
            target_bank_account_id=target.id,
        )
        state = {"changed": False}
        def fetched(*, expected_source_account_ref):
            record = (
                _record(Name="Provider name changed")
                if state["changed"] else _record()
            )
            return BuildiumApiFetchResult(
                records=[record], mode="sandbox", request_count=1
            )
        monkeypatch.setattr(api, "fetch_bank_accounts", fetched)

        reviewed = api.api_dry_run_buildium_bank_accounts(
            run.id, BuildiumApiBankAccountDryRunIn(resolutions=[resolution]),
            db=db, current_user=admin,
        )
        state["changed"] = True
        with pytest.raises(HTTPException) as exc:
            api.api_commit_buildium_bank_accounts(
                run.id,
                BuildiumApiBankAccountCommitIn(
                    fingerprint=reviewed.fingerprint, resolutions=[resolution]
                ),
                db=db, current_user=admin,
            )
        assert exc.value.status_code == 409
        assert db.query(PlatformMigrationItem).filter(
            PlatformMigrationItem.resource == "BANK_ACCOUNTS"
        ).count() == 0
        assert db.query(BankAccount).count() == 1
        assert db.query(GLTransaction).count() == 0

        paths = set(app.openapi()["paths"])
        assert (
            "/api/platform/migrations/buildium/runs/{run_id}/bank-accounts/api-dry-run"
            in paths
        )
        assert (
            "/api/platform/migrations/buildium/runs/{run_id}/bank-accounts/api-commit"
            in paths
        )

        monkeypatch.setattr(transport.settings, "BUILDIUM_API_MODE", "sandbox")
        monkeypatch.setattr(transport.settings, "BUILDIUM_API_CLIENT_ID", "client-id")
        monkeypatch.setattr(transport.settings, "BUILDIUM_API_CLIENT_SECRET", "bank-secret")
        monkeypatch.setattr(
            transport.settings, "BUILDIUM_API_SOURCE_ACCOUNT_REF", "sandbox-account-A"
        )
        status = api.get_buildium_transport_status(current_user=admin)
        assert "BANK_ACCOUNTS" in status.supported_resources
    finally:
        db.close(); engine.dispose()
