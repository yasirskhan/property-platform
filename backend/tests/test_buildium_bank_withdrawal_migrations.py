from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from fastapi import HTTPException, Response
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import init_db  # noqa: F401
from app.core.database import Base
from app.core.security import hash_password
from app.models.audit_log import AuditLog
from app.models.bank_account import BankAccount
from app.models.gl_account import GLAccount
from app.models.gl_entry import GLEntry
from app.models.gl_transaction import GLTransaction
from app.models.platform_migration import PlatformMigrationItem, PlatformMigrationRun
from app.models.platform_user import PlatformUser, PlatformUserRole
from app.models.user import Organization
from app.routers import buildium_bank_withdrawal_migrations as api
from app.routers import buildium_migrations as base_api
from app.schemas.buildium_bank_withdrawal_migration import (
    BuildiumBankWithdrawalCommitIn,
    BuildiumBankWithdrawalDryRunIn,
    BuildiumBankWithdrawalResolutionIn,
)


def _session():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, expire_on_commit=False)(), engine


def _admin(db):
    row = PlatformUser(
        email="buildium-bank-withdrawal-admin@example.com",
        hashed_password=hash_password("test-password"),
        first_name="Buildium",
        last_name="Withdrawal",
        role=PlatformUserRole.PLATFORM_ADMIN,
        is_active=True,
    )
    db.add(row)
    db.commit()
    return row


def _fixture(db):
    org = Organization(name="Buildium Withdrawal Org", slug="buildium-withdrawal-org", is_active=True)
    db.add(org)
    db.flush()
    bank_gl = GLAccount(organization_id=org.id, gl_number="1100", name="Operating Cash", account_type="ASSET", is_active=True)
    offset_gl = GLAccount(organization_id=org.id, gl_number="6100", name="Bank Fee Expense", account_type="EXPENSE", is_active=True)
    db.add_all([bank_gl, offset_gl])
    db.flush()
    bank = BankAccount(organization_id=org.id, name="Operating", account_type="OPERATING", gl_account_id=bank_gl.id, is_active=True)
    db.add(bank)
    db.flush()
    txn = GLTransaction(
        organization_id=org.id,
        transaction_date=date(2026, 10, 2),
        transaction_type="BANK_ADJUSTMENT",
        reference_number="WD-9101",
        memo="Existing withdrawal",
        source_type="bank_adjustment",
        source_id=bank.id,
        is_reversed=False,
    )
    db.add(txn)
    db.flush()
    db.add_all([
        GLEntry(organization_id=org.id, transaction_id=txn.id, gl_account_id=offset_gl.id, debit=Decimal("75.25"), credit=Decimal("0.00")),
        GLEntry(organization_id=org.id, transaction_id=txn.id, gl_account_id=bank_gl.id, debit=Decimal("0.00"), credit=Decimal("75.25")),
    ])
    run = PlatformMigrationRun(
        organization_id=org.id, provider="BUILDIUM",
        source_account_ref="buildium-withdrawal-source", status="DRAFT",
    )
    db.add(run)
    db.flush()
    mappings = [
        PlatformMigrationItem(
            run_id=run.id, organization_id=org.id, provider="BUILDIUM",
            resource="BANK_ACCOUNTS", source_id="7001", target_entity="BANK_ACCOUNT",
            target_id=bank.id, source_fingerprint="1" * 64,
        ),
        PlatformMigrationItem(
            run_id=run.id, organization_id=org.id, provider="BUILDIUM",
            resource="GL_ACCOUNTS", source_id="8100", target_entity="GL_ACCOUNT",
            target_id=offset_gl.id, source_fingerprint="2" * 64,
        ),
    ]
    db.add_all(mappings)
    db.commit()
    return bank, offset_gl, txn, run, mappings


def _record(**changes):
    row = {
        "Id": 9101,
        "SourceBankAccountId": 7001,
        "EntryDate": "2026-10-02",
        "Memo": "DO-NOT-PERSIST-RAW-WITHDRAWAL",
        "TotalAmount": 75.25,
        "AccountingEntity": {
            "Id": 44,
            "AccountingEntityType": "Company",
            "Href": "/companies/44",
        },
        "OffsetGLAccountId": 8100,
    }
    row.update(changes)
    return row


def test_buildium_bank_withdrawal_maps_exact_existing_adjustment_and_replays_without_mutation():
    db, engine = _session()
    try:
        admin = _admin(db)
        bank, offset_gl, txn, run, _ = _fixture(db)
        before = {
            "transactions": db.query(GLTransaction).count(),
            "entries": db.query(GLEntry).count(),
            "banks": db.query(BankAccount).count(),
        }

        preview = api.dry_run_buildium_bank_withdrawals(
            run.id, BuildiumBankWithdrawalDryRunIn(records=[_record()]),
            db=db, current_user=admin,
        )
        assert preview.invalid == 0
        assert preview.reviewable == 1
        assert preview.rows[0].mapped["source_target_bank_account_id"] == bank.id
        assert preview.rows[0].mapped["target_offset_gl_account_id"] == offset_gl.id
        assert any("Possible exact existing target bank adjustment" in warning for warning in preview.rows[0].warnings)

        resolution = BuildiumBankWithdrawalResolutionIn(
            source_id=9101, action="MATCH_EXISTING", target_gl_transaction_id=txn.id,
        )
        reviewed = api.dry_run_buildium_bank_withdrawals(
            run.id,
            BuildiumBankWithdrawalDryRunIn(records=[_record()], resolutions=[resolution]),
            db=db, current_user=admin,
        )
        committed = api.commit_buildium_bank_withdrawals(
            run.id,
            BuildiumBankWithdrawalCommitIn(
                fingerprint=reviewed.fingerprint, records=[_record()], resolutions=[resolution],
            ),
            db=db, current_user=admin,
        )
        assert committed.matched_existing == 1
        assert committed.replayed is False

        mapping = db.query(PlatformMigrationItem).filter(
            PlatformMigrationItem.run_id == run.id,
            PlatformMigrationItem.resource == "BANK_WITHDRAWALS",
        ).one()
        assert mapping.target_entity == "GL_TRANSACTION_BANK_ADJUSTMENT_RELATIONSHIP"
        assert mapping.target_id == txn.id

        replay_preview = api.dry_run_buildium_bank_withdrawals(
            run.id,
            BuildiumBankWithdrawalDryRunIn(records=[_record()], resolutions=[resolution]),
            db=db, current_user=admin,
        )
        replay = api.commit_buildium_bank_withdrawals(
            run.id,
            BuildiumBankWithdrawalCommitIn(
                fingerprint=replay_preview.fingerprint, records=[_record()], resolutions=[resolution],
            ),
            db=db, current_user=admin,
        )
        assert replay.replayed is True
        assert replay.rows[0].replayed is True
        assert {
            "transactions": db.query(GLTransaction).count(),
            "entries": db.query(GLEntry).count(),
            "banks": db.query(BankAccount).count(),
        } == before

        response = Response()
        items = base_api.list_migration_items(
            run.id, response=response, resource="bank_withdrawals", limit=20,
            db=db, current_user=admin,
        )
        assert items[0].target_exists is True
        assert items[0].target_label == f"Bank adjustment GL transaction #{txn.id}: 2026-10-02"
        assert response.headers["cache-control"] == "no-store"

        audit_text = "\n".join(
            str(row.new_value or "")
            for row in db.query(AuditLog).filter(AuditLog.entity_type == "platform_migration_run").all()
        )
        assert "DO-NOT-PERSIST-RAW-WITHDRAWAL" not in audit_text
    finally:
        db.close()
        engine.dispose()


def test_buildium_bank_withdrawal_fails_closed_for_dependency_or_target_drift():
    db, engine = _session()
    try:
        admin = _admin(db)
        _, _, txn, run, mappings = _fixture(db)

        bad = _record(TotalAmount="75.251")
        preview = api.dry_run_buildium_bank_withdrawals(
            run.id, BuildiumBankWithdrawalDryRunIn(records=[bad]),
            db=db, current_user=admin,
        )
        assert preview.invalid == 1
        assert "two decimal places" in preview.rows[0].reason

        resolution = BuildiumBankWithdrawalResolutionIn(
            source_id=9101, action="MATCH_EXISTING", target_gl_transaction_id=txn.id,
        )
        reviewed = api.dry_run_buildium_bank_withdrawals(
            run.id,
            BuildiumBankWithdrawalDryRunIn(records=[_record()], resolutions=[resolution]),
            db=db, current_user=admin,
        )
        mappings[1].source_fingerprint = "9" * 64
        db.commit()
        with pytest.raises(HTTPException) as exc:
            api.commit_buildium_bank_withdrawals(
                run.id,
                BuildiumBankWithdrawalCommitIn(
                    fingerprint=reviewed.fingerprint, records=[_record()], resolutions=[resolution],
                ),
                db=db, current_user=admin,
            )
        assert exc.value.status_code == 409
        assert "stale" in exc.value.detail.lower()

        mappings[1].source_fingerprint = "2" * 64
        bank_line = db.query(GLEntry).filter(
            GLEntry.transaction_id == txn.id,
            GLEntry.credit > 0,
        ).one()
        bank_line.credit = Decimal("0.00")
        bank_line.debit = Decimal("75.25")
        db.commit()
        with pytest.raises(HTTPException) as exc:
            api.dry_run_buildium_bank_withdrawals(
                run.id,
                BuildiumBankWithdrawalDryRunIn(records=[_record()], resolutions=[resolution]),
                db=db, current_user=admin,
            )
        assert exc.value.status_code == 409
        assert "no longer matches" in exc.value.detail.lower()
    finally:
        db.close()
        engine.dispose()


def test_buildium_bank_withdrawal_blocks_rental_scope_allows_skip_and_registers_routes():
    from app.main import app

    db, engine = _session()
    try:
        admin = _admin(db)
        _, _, _, run, _ = _fixture(db)

        unsupported = _record()
        unsupported["AccountingEntity"] = {"Id": 501, "AccountingEntityType": "Rental"}
        result = api.dry_run_buildium_bank_withdrawals(
            run.id, BuildiumBankWithdrawalDryRunIn(records=[unsupported]),
            db=db, current_user=admin,
        )
        assert result.invalid == 1
        assert "only Buildium Company" in result.rows[0].reason

        skip = BuildiumBankWithdrawalResolutionIn(source_id=9101, action="SKIP")
        reviewed = api.dry_run_buildium_bank_withdrawals(
            run.id,
            BuildiumBankWithdrawalDryRunIn(records=[_record()], resolutions=[skip]),
            db=db, current_user=admin,
        )
        committed = api.commit_buildium_bank_withdrawals(
            run.id,
            BuildiumBankWithdrawalCommitIn(
                fingerprint=reviewed.fingerprint, records=[_record()], resolutions=[skip],
            ),
            db=db, current_user=admin,
        )
        assert committed.matched_existing == 0
        assert committed.skipped_review == 1
        assert db.query(PlatformMigrationItem).filter(
            PlatformMigrationItem.resource == "BANK_WITHDRAWALS"
        ).count() == 0

        paths = set(app.openapi()["paths"])
        assert "/api/platform/migrations/buildium/runs/{run_id}/bank-withdrawals/dry-run" in paths
        assert "/api/platform/migrations/buildium/runs/{run_id}/bank-withdrawals/commit" in paths
    finally:
        db.close()
        engine.dispose()
