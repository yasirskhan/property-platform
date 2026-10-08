from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from fastapi import HTTPException, Response
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import init_db  # noqa: F401
from app.core.database import Base
from app.core.security import hash_password
from app.models.audit_log import AuditLog
from app.models.bank_account import BankAccount
from app.models.deposit import Deposit
from app.models.deposit_line import DepositLine
from app.models.gl_account import GLAccount
from app.models.gl_entry import GLEntry
from app.models.gl_transaction import GLTransaction
from app.models.platform_migration import PlatformMigrationItem, PlatformMigrationRun
from app.models.platform_user import PlatformUser, PlatformUserRole
from app.models.receipt import Receipt
from app.models.user import Organization
from app.routers import buildium_deposit_migrations as api
from app.routers import buildium_migrations as base_api
from app.schemas.buildium_deposit_migration import (
    BuildiumApiDepositCommitIn,
    BuildiumApiDepositDryRunIn,
    BuildiumDepositCommitIn,
    BuildiumDepositDryRunIn,
    BuildiumDepositResolutionIn,
)
from app.services import buildium_api_transport as transport
from app.services.buildium_api_transport import (
    BuildiumApiFetchResult,
    BuildiumApiTransportError,
)


def _session():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, expire_on_commit=False)(), engine


def _admin(db):
    row = PlatformUser(
        email="buildium-deposit-admin@example.com",
        hashed_password=hash_password("test-password"),
        first_name="Buildium",
        last_name="Deposit",
        role=PlatformUserRole.PLATFORM_ADMIN,
        is_active=True,
    )
    db.add(row)
    db.commit()
    return row


def _fixture(db):
    org = Organization(
        name="Buildium Deposit Org",
        slug="buildium-deposit-org",
        is_active=True,
    )
    db.add(org)
    db.flush()

    bank_gl = GLAccount(
        organization_id=org.id,
        gl_number="1100",
        name="Operating Cash",
        account_type="ASSET",
        is_active=True,
    )
    income_gl = GLAccount(
        organization_id=org.id,
        gl_number="4100",
        name="Rental Income",
        account_type="INCOME",
        is_active=True,
    )
    db.add_all([bank_gl, income_gl])
    db.flush()

    bank = BankAccount(
        organization_id=org.id,
        name="Operating",
        account_type="OPERATING",
        gl_account_id=bank_gl.id,
        is_active=True,
    )
    db.add(bank)
    db.flush()

    receipts = []
    for amount, day in ((Decimal("40.00"), date(2026, 10, 2)), (Decimal("60.00"), date(2026, 10, 3))):
        receipt = Receipt(
            organization_id=org.id,
            type="TENANT",
            receipt_date=day,
            amount=amount,
            cash_gl_account_id=bank_gl.id,
            is_active=True,
            is_reversed=False,
        )
        db.add(receipt)
        db.flush()
        txn = GLTransaction(
            organization_id=org.id,
            transaction_date=day,
            transaction_type="RECEIPT",
            source_type="receipt",
            source_id=receipt.id,
            is_reversed=False,
        )
        db.add(txn)
        db.flush()
        receipt.gl_transaction_id = txn.id
        db.add_all([
            GLEntry(
                organization_id=org.id,
                transaction_id=txn.id,
                gl_account_id=bank_gl.id,
                debit=amount,
                credit=Decimal("0.00"),
            ),
            GLEntry(
                organization_id=org.id,
                transaction_id=txn.id,
                gl_account_id=income_gl.id,
                debit=Decimal("0.00"),
                credit=amount,
            ),
        ])
        receipts.append(receipt)

    deposit = Deposit(
        organization_id=org.id,
        bank_gl_account_id=bank_gl.id,
        deposit_date=date(2026, 10, 4),
        deposit_number="DEP-9201",
        total=Decimal("100.00"),
        is_active=True,
    )
    db.add(deposit)
    db.flush()
    for receipt in receipts:
        db.add(
            DepositLine(
                organization_id=org.id,
                deposit_id=deposit.id,
                receipt_id=receipt.id,
            )
        )

    run = PlatformMigrationRun(
        organization_id=org.id,
        provider="BUILDIUM",
        source_account_ref="buildium-deposit-source",
        status="DRAFT",
    )
    db.add(run)
    db.flush()

    mappings = [
        PlatformMigrationItem(
            run_id=run.id,
            organization_id=org.id,
            provider="BUILDIUM",
            resource="BANK_ACCOUNTS",
            source_id="7001",
            target_entity="BANK_ACCOUNT",
            target_id=bank.id,
            source_fingerprint="1" * 64,
        ),
        PlatformMigrationItem(
            run_id=run.id,
            organization_id=org.id,
            provider="BUILDIUM",
            resource="LEASE_PAYMENTS",
            source_id="91001",
            target_entity="RECEIPT_RELATIONSHIP",
            target_id=receipts[0].id,
            source_fingerprint="2" * 64,
        ),
        PlatformMigrationItem(
            run_id=run.id,
            organization_id=org.id,
            provider="BUILDIUM",
            resource="LEASE_PAYMENTS",
            source_id="91002",
            target_entity="RECEIPT_RELATIONSHIP",
            target_id=receipts[1].id,
            source_fingerprint="3" * 64,
        ),
    ]
    db.add_all(mappings)
    db.commit()
    return org, bank, receipts, deposit, run, mappings


def _record(**changes):
    row = {
        "Id": 9201,
        "SourceBankAccountId": 7001,
        "EntryDate": "2026-10-04",
        "Memo": "DO-NOT-PERSIST-RAW-BUILDIUM-DEPOSIT",
        "TotalAmount": 100.00,
        "Lines": [],
        "PaymentTransactionIds": [91001, 91002],
    }
    row.update(changes)
    return row


def test_buildium_deposit_reconciles_exact_existing_group_and_replays_without_mutation():
    db, engine = _session()
    try:
        admin = _admin(db)
        _, bank, receipts, deposit, run, _ = _fixture(db)
        before = {
            "deposits": db.query(Deposit).count(),
            "deposit_lines": db.query(DepositLine).count(),
            "receipts": db.query(Receipt).count(),
            "transactions": db.query(GLTransaction).count(),
            "entries": db.query(GLEntry).count(),
        }

        preview = api.dry_run_buildium_deposits(
            run.id,
            BuildiumDepositDryRunIn(records=[_record()]),
            db=db,
            current_user=admin,
        )
        assert preview.invalid == 0
        assert preview.reviewable == 1
        assert preview.rows[0].mapped["target_bank_account_id"] == bank.id
        assert preview.rows[0].mapped["target_receipt_ids"] == [row.id for row in receipts]
        assert any(
            "Possible exact existing target Deposit match" in warning
            for warning in preview.rows[0].warnings
        )

        resolution = BuildiumDepositResolutionIn(
            source_id=9201,
            action="MATCH_EXISTING",
            target_deposit_id=deposit.id,
        )
        reviewed = api.dry_run_buildium_deposits(
            run.id,
            BuildiumDepositDryRunIn(
                records=[_record()],
                resolutions=[resolution],
            ),
            db=db,
            current_user=admin,
        )
        committed = api.commit_buildium_deposits(
            run.id,
            BuildiumDepositCommitIn(
                fingerprint=reviewed.fingerprint,
                records=[_record()],
                resolutions=[resolution],
            ),
            db=db,
            current_user=admin,
        )
        assert committed.matched_existing == 1
        assert committed.replayed is False

        mapping = (
            db.query(PlatformMigrationItem)
            .filter(
                PlatformMigrationItem.run_id == run.id,
                PlatformMigrationItem.resource == "BANK_DEPOSITS",
            )
            .one()
        )
        assert mapping.target_entity == "DEPOSIT_RELATIONSHIP"
        assert mapping.target_id == deposit.id

        replay_preview = api.dry_run_buildium_deposits(
            run.id,
            BuildiumDepositDryRunIn(
                records=[_record()],
                resolutions=[resolution],
            ),
            db=db,
            current_user=admin,
        )
        replay = api.commit_buildium_deposits(
            run.id,
            BuildiumDepositCommitIn(
                fingerprint=replay_preview.fingerprint,
                records=[_record()],
                resolutions=[resolution],
            ),
            db=db,
            current_user=admin,
        )
        assert replay.replayed is True
        assert replay.rows[0].replayed is True
        assert {
            "deposits": db.query(Deposit).count(),
            "deposit_lines": db.query(DepositLine).count(),
            "receipts": db.query(Receipt).count(),
            "transactions": db.query(GLTransaction).count(),
            "entries": db.query(GLEntry).count(),
        } == before

        response = Response()
        items = base_api.list_migration_items(
            run.id,
            response=response,
            resource="bank_deposits",
            limit=20,
            db=db,
            current_user=admin,
        )
        assert items[0].target_exists is True
        assert items[0].target_label.startswith(f"Deposit #{deposit.id}: 2026-10-04")
        assert response.headers["cache-control"] == "no-store"

        audit_text = "\n".join(
            str(row.new_value or "")
            for row in db.query(AuditLog)
            .filter(AuditLog.entity_type == "platform_migration_run")
            .all()
        )
        assert "DO-NOT-PERSIST-RAW-BUILDIUM-DEPOSIT" not in audit_text
    finally:
        db.close()
        engine.dispose()


def test_buildium_deposit_blocks_lines_missing_payments_and_dependency_or_target_drift():
    db, engine = _session()
    try:
        admin = _admin(db)
        _, _, receipts, deposit, run, mappings = _fixture(db)

        with_lines = _record(
            Lines=[
                {
                    "Id": 1,
                    "GLAccountId": 500,
                    "Amount": 10.00,
                    "AccountingEntity": {"Id": 44, "AccountingEntityType": "Company"},
                }
            ]
        )
        preview = api.dry_run_buildium_deposits(
            run.id,
            BuildiumDepositDryRunIn(records=[with_lines]),
            db=db,
            current_user=admin,
        )
        assert preview.invalid == 1
        assert "payment-only deposits" in preview.rows[0].reason

        no_payments = api.dry_run_buildium_deposits(
            run.id,
            BuildiumDepositDryRunIn(records=[_record(PaymentTransactionIds=[])]),
            db=db,
            current_user=admin,
        )
        assert no_payments.invalid == 1

        wrong_total = api.dry_run_buildium_deposits(
            run.id,
            BuildiumDepositDryRunIn(records=[_record(TotalAmount=99.00)]),
            db=db,
            current_user=admin,
        )
        assert wrong_total.invalid == 1
        assert "exactly equal" in wrong_total.rows[0].reason

        resolution = BuildiumDepositResolutionIn(
            source_id=9201,
            action="MATCH_EXISTING",
            target_deposit_id=deposit.id,
        )
        reviewed = api.dry_run_buildium_deposits(
            run.id,
            BuildiumDepositDryRunIn(records=[_record()], resolutions=[resolution]),
            db=db,
            current_user=admin,
        )
        mappings[1].source_fingerprint = "9" * 64
        db.commit()
        with pytest.raises(HTTPException) as exc:
            api.commit_buildium_deposits(
                run.id,
                BuildiumDepositCommitIn(
                    fingerprint=reviewed.fingerprint,
                    records=[_record()],
                    resolutions=[resolution],
                ),
                db=db,
                current_user=admin,
            )
        assert exc.value.status_code == 409
        assert "stale" in exc.value.detail.lower()

        mappings[1].source_fingerprint = "2" * 64
        receipts[0].is_reversed = True
        db.commit()
        invalid = api.dry_run_buildium_deposits(
            run.id,
            BuildiumDepositDryRunIn(records=[_record()]),
            db=db,
            current_user=admin,
        )
        assert invalid.invalid == 1
        assert "unreversed" in invalid.rows[0].reason

        receipts[0].is_reversed = False
        db.commit()
        line = db.query(DepositLine).filter(
            DepositLine.deposit_id == deposit.id,
            DepositLine.receipt_id == receipts[1].id,
        ).one()
        db.delete(line)
        db.commit()
        with pytest.raises(HTTPException) as exc:
            api.dry_run_buildium_deposits(
                run.id,
                BuildiumDepositDryRunIn(records=[_record()], resolutions=[resolution]),
                db=db,
                current_user=admin,
            )
        assert exc.value.status_code == 409
        assert "no longer matches" in exc.value.detail.lower()
    finally:
        db.close()
        engine.dispose()


def test_buildium_deposit_skip_cross_org_and_routes():
    from app.main import app

    db, engine = _session()
    try:
        admin = _admin(db)
        org, _, _, deposit, run, _ = _fixture(db)
        other = Organization(
            name="Other Buildium Deposit Org",
            slug="other-buildium-deposit-org",
            is_active=True,
        )
        db.add(other)
        db.commit()

        skip = BuildiumDepositResolutionIn(source_id=9201, action="SKIP")
        reviewed = api.dry_run_buildium_deposits(
            run.id,
            BuildiumDepositDryRunIn(records=[_record()], resolutions=[skip]),
            db=db,
            current_user=admin,
        )
        committed = api.commit_buildium_deposits(
            run.id,
            BuildiumDepositCommitIn(
                fingerprint=reviewed.fingerprint,
                records=[_record()],
                resolutions=[skip],
            ),
            db=db,
            current_user=admin,
        )
        assert committed.matched_existing == 0
        assert committed.skipped_review == 1
        assert (
            db.query(PlatformMigrationItem)
            .filter(PlatformMigrationItem.resource == "BANK_DEPOSITS")
            .count()
            == 0
        )

        deposit.organization_id = other.id
        db.commit()
        resolution = BuildiumDepositResolutionIn(
            source_id=9201,
            action="MATCH_EXISTING",
            target_deposit_id=deposit.id,
        )
        with pytest.raises(HTTPException) as exc:
            api.dry_run_buildium_deposits(
                run.id,
                BuildiumDepositDryRunIn(
                    records=[_record()],
                    resolutions=[resolution],
                ),
                db=db,
                current_user=admin,
            )
        assert exc.value.status_code == 409
        assert "not in the target organization" in exc.value.detail

        paths = set(app.openapi()["paths"])
        assert "/api/platform/migrations/buildium/runs/{run_id}/deposits/dry-run" in paths
        assert "/api/platform/migrations/buildium/runs/{run_id}/deposits/commit" in paths
    finally:
        db.close()
        engine.dispose()



class _DepositApiResponse:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


def _configure_deposit_api_transport(monkeypatch):
    monkeypatch.setattr(transport.settings, "BUILDIUM_API_MODE", "sandbox")
    monkeypatch.setattr(transport.settings, "BUILDIUM_API_CLIENT_ID", "deposit-client")
    monkeypatch.setattr(transport.settings, "BUILDIUM_API_CLIENT_SECRET", "deposit-secret")
    monkeypatch.setattr(
        transport.settings,
        "BUILDIUM_API_SOURCE_ACCOUNT_REF",
        "buildium-deposit-source",
    )


def test_buildium_transport_fetches_bounded_nested_bank_deposits(monkeypatch):
    _configure_deposit_api_transport(monkeypatch)
    calls = []

    def fake_get(url, *, headers, timeout, params=None):
        calls.append((url, headers.copy(), params.copy(), timeout))
        if url.endswith("/v1/bankaccounts/7001/deposits"):
            row = _record()
            row["SourceBankAccountId"] = 999999
            return _DepositApiResponse(200, [row])
        raise AssertionError(url)

    monkeypatch.setattr(transport.requests, "get", fake_get)
    result = transport.fetch_bank_deposits(
        expected_source_account_ref="buildium-deposit-source",
        parent_bank_account_ids=["7001"],
        start_date=date(2026, 1, 1),
        end_date=date(2026, 12, 31),
    )
    assert result.records[0]["Id"] == 9201
    assert result.records[0]["SourceBankAccountId"] == 7001
    assert result.records[0]["_ApiStartDate"] == "2026-01-01"
    assert result.records[0]["_ApiEndDate"] == "2026-12-31"
    assert result.parent_record_count == 1
    assert result.request_count == 1
    assert calls[0][0] == "https://apisandbox.buildium.com/v1/bankaccounts/7001/deposits"
    assert calls[0][2] == {
        "offset": 0,
        "limit": transport.MAX_BANK_DEPOSIT_RECORDS + 1,
        "startdate": "2026-01-01",
        "enddate": "2026-12-31",
    }
    assert calls[0][1]["x-buildium-client-secret"] == "deposit-secret"

    with pytest.raises(BuildiumApiTransportError) as exc:
        transport.fetch_bank_deposits(
            expected_source_account_ref="buildium-deposit-source",
            parent_bank_account_ids=list(
                range(1, transport.MAX_BANK_DEPOSIT_PARENT_BANK_ACCOUNTS + 2)
            ),
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
        )
    assert exc.value.code == "source_too_large"

    with pytest.raises(BuildiumApiTransportError) as exc:
        transport.fetch_bank_deposits(
            expected_source_account_ref="buildium-deposit-source",
            parent_bank_account_ids=[7001],
            start_date=date(2025, 1, 1),
            end_date=date(2026, 12, 31),
        )
    assert exc.value.code == "invalid_date_window"


def test_buildium_api_deposit_maps_existing_only_replays_and_redacts(monkeypatch):
    db, engine = _session()
    try:
        admin = _admin(db)
        _, _, _, deposit, run, _ = _fixture(db)
        before = {
            "deposits": db.query(Deposit).count(),
            "deposit_lines": db.query(DepositLine).count(),
            "receipts": db.query(Receipt).count(),
            "transactions": db.query(GLTransaction).count(),
            "entries": db.query(GLEntry).count(),
        }

        def fetched(*, expected_source_account_ref, parent_bank_account_ids, start_date, end_date):
            assert expected_source_account_ref == "buildium-deposit-source"
            assert parent_bank_account_ids == ["7001"]
            row = _record()
            row["_ApiStartDate"] = start_date.isoformat()
            row["_ApiEndDate"] = end_date.isoformat()
            return BuildiumApiFetchResult(
                records=[row], mode="sandbox", request_count=1, parent_record_count=1
            )

        monkeypatch.setattr(api, "fetch_bank_deposits", fetched)
        resolution = BuildiumDepositResolutionIn(
            source_id=9201,
            action="MATCH_EXISTING",
            target_deposit_id=deposit.id,
        )
        reviewed = api.api_dry_run_buildium_deposits(
            run.id,
            BuildiumApiDepositDryRunIn(
                start_date=date(2026, 1, 1),
                end_date=date(2026, 12, 31),
                resolutions=[resolution],
            ),
            db=db,
            current_user=admin,
        )
        assert reviewed.invalid == 0
        assert reviewed.reviewable == 1

        committed = api.api_commit_buildium_deposits(
            run.id,
            BuildiumApiDepositCommitIn(
                start_date=date(2026, 1, 1),
                end_date=date(2026, 12, 31),
                fingerprint=reviewed.fingerprint,
                resolutions=[resolution],
            ),
            db=db,
            current_user=admin,
        )
        assert committed.matched_existing == 1
        replay = api.api_commit_buildium_deposits(
            run.id,
            BuildiumApiDepositCommitIn(
                start_date=date(2026, 1, 1),
                end_date=date(2026, 12, 31),
                fingerprint=reviewed.fingerprint,
                resolutions=[resolution],
            ),
            db=db,
            current_user=admin,
        )
        assert replay.replayed is True
        assert db.query(PlatformMigrationItem).filter(
            PlatformMigrationItem.resource == "BANK_DEPOSITS"
        ).count() == 1
        assert {
            "deposits": db.query(Deposit).count(),
            "deposit_lines": db.query(DepositLine).count(),
            "receipts": db.query(Receipt).count(),
            "transactions": db.query(GLTransaction).count(),
            "entries": db.query(GLEntry).count(),
        } == before

        with pytest.raises(ValidationError):
            BuildiumApiDepositDryRunIn(
                start_date=date(2026, 1, 1),
                end_date=date(2026, 12, 31),
                records=[_record()],
            )
        with pytest.raises(ValidationError):
            BuildiumApiDepositCommitIn(
                start_date=date(2026, 1, 1),
                end_date=date(2026, 12, 31),
                fingerprint=reviewed.fingerprint,
                client_secret="secret",
            )
        with pytest.raises(ValidationError):
            BuildiumApiDepositDryRunIn(
                start_date=date(2025, 1, 1),
                end_date=date(2026, 12, 31),
            )

        audit = "\n".join(
            str(row.new_value or "")
            for row in db.query(AuditLog)
            .filter(AuditLog.entity_type == "platform_migration_run")
            .all()
        )
        assert "DO-NOT-PERSIST-RAW-BUILDIUM-DEPOSIT" not in audit
        assert "deposit-secret" not in audit
        assert "raw_payload_stored" in audit
    finally:
        db.close()
        engine.dispose()


def test_buildium_api_deposit_source_window_dependency_and_target_drift_fail_closed(monkeypatch):
    db, engine = _session()
    try:
        admin = _admin(db)
        _, _, receipts, deposit, run, mappings = _fixture(db)
        state = {"total": 100.00}

        def fetched(*, expected_source_account_ref, parent_bank_account_ids, start_date, end_date):
            row = _record(TotalAmount=state["total"])
            row["_ApiStartDate"] = start_date.isoformat()
            row["_ApiEndDate"] = end_date.isoformat()
            return BuildiumApiFetchResult(
                records=[row], mode="sandbox", request_count=1, parent_record_count=1
            )

        monkeypatch.setattr(api, "fetch_bank_deposits", fetched)
        resolution = BuildiumDepositResolutionIn(
            source_id=9201,
            action="MATCH_EXISTING",
            target_deposit_id=deposit.id,
        )
        reviewed = api.api_dry_run_buildium_deposits(
            run.id,
            BuildiumApiDepositDryRunIn(
                start_date=date(2026, 1, 1),
                end_date=date(2026, 12, 31),
                resolutions=[resolution],
            ),
            db=db,
            current_user=admin,
        )

        with pytest.raises(HTTPException) as exc:
            api.api_commit_buildium_deposits(
                run.id,
                BuildiumApiDepositCommitIn(
                    start_date=date(2026, 2, 1),
                    end_date=date(2026, 12, 31),
                    fingerprint=reviewed.fingerprint,
                    resolutions=[resolution],
                ),
                db=db,
                current_user=admin,
            )
        assert exc.value.status_code == 409

        state["total"] = 101.00
        with pytest.raises(HTTPException) as exc:
            api.api_commit_buildium_deposits(
                run.id,
                BuildiumApiDepositCommitIn(
                    start_date=date(2026, 1, 1),
                    end_date=date(2026, 12, 31),
                    fingerprint=reviewed.fingerprint,
                    resolutions=[resolution],
                ),
                db=db,
                current_user=admin,
            )
        assert exc.value.status_code == 409

        state["total"] = 100.00
        reviewed = api.api_dry_run_buildium_deposits(
            run.id,
            BuildiumApiDepositDryRunIn(
                start_date=date(2026, 1, 1),
                end_date=date(2026, 12, 31),
                resolutions=[resolution],
            ),
            db=db,
            current_user=admin,
        )
        mappings[1].source_fingerprint = "9" * 64
        db.commit()
        with pytest.raises(HTTPException) as exc:
            api.api_commit_buildium_deposits(
                run.id,
                BuildiumApiDepositCommitIn(
                    start_date=date(2026, 1, 1),
                    end_date=date(2026, 12, 31),
                    fingerprint=reviewed.fingerprint,
                    resolutions=[resolution],
                ),
                db=db,
                current_user=admin,
            )
        assert exc.value.status_code == 409

        mappings[1].source_fingerprint = "2" * 64
        receipts[0].is_reversed = True
        db.commit()
        with pytest.raises(HTTPException) as exc:
            api.api_commit_buildium_deposits(
                run.id,
                BuildiumApiDepositCommitIn(
                    start_date=date(2026, 1, 1),
                    end_date=date(2026, 12, 31),
                    fingerprint=reviewed.fingerprint,
                    resolutions=[resolution],
                ),
                db=db,
                current_user=admin,
            )
        assert exc.value.status_code == 409
        assert db.query(PlatformMigrationItem).filter(
            PlatformMigrationItem.resource == "BANK_DEPOSITS"
        ).count() == 0
    finally:
        db.close()
        engine.dispose()


def test_buildium_api_deposit_parent_scope_routes_and_status(monkeypatch):
    from app.main import app

    db, engine = _session()
    try:
        admin = _admin(db)
        _, _, _, _, run, _ = _fixture(db)
        assert api._deposit_api_parent_source_ids(db, run=run) == ["7001"]

        monkeypatch.setattr(
            base_api,
            "transport_status",
            lambda: type(
                "TransportState",
                (),
                {"mode": "sandbox", "configured": True, "source_account_bound": True},
            )(),
        )
        status = base_api.get_buildium_transport_status(current_user=admin)
        assert "BANK_DEPOSITS" in status.supported_resources

        paths = set(app.openapi()["paths"])
        assert "/api/platform/migrations/buildium/runs/{run_id}/deposits/api-dry-run" in paths
        assert "/api/platform/migrations/buildium/runs/{run_id}/deposits/api-commit" in paths
    finally:
        db.close()
        engine.dispose()
