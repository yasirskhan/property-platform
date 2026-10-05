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
from app.models.audit import AuditLog
from app.models.bank_account import BankAccount
from app.models.bank_reconciliation import BankReconciliation
from app.models.gl_account import GLAccount
from app.models.gl_transaction import GLTransaction
from app.models.platform_migration import PlatformMigrationItem, PlatformMigrationRun
from app.models.platform_user import PlatformUser, PlatformUserRole
from app.models.user import Organization
from app.routers import buildium_bank_reconciliation_migrations as api
from app.routers import buildium_migrations as base_api
from app.schemas.buildium_bank_reconciliation_migration import (
    BuildiumBankReconciliationCommitIn,
    BuildiumBankReconciliationDryRunIn,
    BuildiumBankReconciliationResolutionIn,
)


def _session():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, expire_on_commit=False)(), engine


def _admin(db):
    row = PlatformUser(
        email="buildium-bank-recon-admin@example.com",
        hashed_password=hash_password("test-password"),
        first_name="Buildium",
        last_name="Recon",
        role=PlatformUserRole.PLATFORM_ADMIN,
        is_active=True,
    )
    db.add(row)
    db.commit()
    return row


def _fixture(db):
    org = Organization(
        name="Buildium Reconciliation Org",
        slug="buildium-reconciliation-org",
        is_active=True,
    )
    db.add(org)
    db.flush()
    gl = GLAccount(
        organization_id=org.id,
        gl_number="1100",
        name="Operating Cash",
        account_type="ASSET",
        is_active=True,
    )
    db.add(gl)
    db.flush()
    bank = BankAccount(
        organization_id=org.id,
        name="Operating",
        account_type="OPERATING",
        gl_account_id=gl.id,
        is_active=True,
    )
    db.add(bank)
    db.flush()
    reconciliation = BankReconciliation(
        organization_id=org.id,
        bank_account_id=bank.id,
        statement_date=date(2026, 9, 30),
        beginning_balance=Decimal("100.00"),
        ending_statement_balance=Decimal("100.00"),
        status="RECONCILED",
    )
    db.add(reconciliation)
    db.flush()
    run = PlatformMigrationRun(
        organization_id=org.id,
        provider="BUILDIUM",
        source_account_ref="buildium-bank-reconciliation-source",
        status="DRAFT",
    )
    db.add(run)
    db.flush()
    mapping = PlatformMigrationItem(
        run_id=run.id,
        organization_id=org.id,
        provider="BUILDIUM",
        resource="BANK_ACCOUNTS",
        source_id="7001",
        target_entity="BANK_ACCOUNT",
        target_id=bank.id,
        source_fingerprint="a" * 64,
    )
    db.add(mapping)
    db.commit()
    return org, gl, bank, reconciliation, run, mapping


def _record(**changes):
    row = {
        "Id": 8001,
        "BankAccountId": 7001,
        "IsFinished": True,
        "StatementEndingDate": "2026-09-30",
        "Balance": {
            "Difference": 0,
            "StatementBalance": {
                "TotalChecksAndWithdrawals": 0,
                "TotalDepositsAndAdditions": 0,
                "EndingBalance": 100,
                "BeginningBalance": 100,
            },
            "ClearedBalance": {
                "TotalChecksAndWithdrawals": 0,
                "TotalDepositsAndAdditions": 0,
                "EndingBalance": 100,
                "BeginningBalance": 100,
            },
        },
        "ProviderDebugMemo": "DO-NOT-PERSIST-RAW",
    }
    row.update(changes)
    return row


def test_buildium_bank_reconciliation_maps_exact_existing_target_and_replays_without_mutation():
    db, engine = _session()
    try:
        admin = _admin(db)
        org, gl, bank, target, run, _ = _fixture(db)
        before = {
            "reconciliations": db.query(BankReconciliation).count(),
            "gl": db.query(GLTransaction).count(),
        }

        preview = api.dry_run_buildium_bank_reconciliations(
            run.id,
            BuildiumBankReconciliationDryRunIn(records=[_record()]),
            db=db,
            current_user=admin,
        )
        assert preview.invalid == 0
        assert preview.reviewable == 1
        assert preview.rows[0].mapped["target_bank_account_id"] == bank.id
        assert preview.rows[0].resolution_action is None
        assert any(
            "Possible exact existing target reconciliation" in warning
            for warning in preview.rows[0].warnings
        )

        resolution = BuildiumBankReconciliationResolutionIn(
            source_id=8001,
            action="MATCH_EXISTING",
            target_reconciliation_id=target.id,
        )
        reviewed = api.dry_run_buildium_bank_reconciliations(
            run.id,
            BuildiumBankReconciliationDryRunIn(
                records=[_record()], resolutions=[resolution]
            ),
            db=db,
            current_user=admin,
        )
        committed = api.commit_buildium_bank_reconciliations(
            run.id,
            BuildiumBankReconciliationCommitIn(
                fingerprint=reviewed.fingerprint,
                records=[_record()],
                resolutions=[resolution],
            ),
            db=db,
            current_user=admin,
        )
        assert committed.matched_existing == 1
        assert committed.replayed is False
        assert committed.rows[0].target_reconciliation_id == target.id

        mapping = db.query(PlatformMigrationItem).filter(
            PlatformMigrationItem.run_id == run.id,
            PlatformMigrationItem.resource == "BANK_RECONCILIATIONS",
        ).one()
        assert mapping.target_entity == "BANK_RECONCILIATION"
        assert mapping.target_id == target.id

        replay_preview = api.dry_run_buildium_bank_reconciliations(
            run.id,
            BuildiumBankReconciliationDryRunIn(
                records=[_record()], resolutions=[resolution]
            ),
            db=db,
            current_user=admin,
        )
        replay = api.commit_buildium_bank_reconciliations(
            run.id,
            BuildiumBankReconciliationCommitIn(
                fingerprint=replay_preview.fingerprint,
                records=[_record()],
                resolutions=[resolution],
            ),
            db=db,
            current_user=admin,
        )
        assert replay.replayed is True
        assert replay.rows[0].replayed is True

        after = {
            "reconciliations": db.query(BankReconciliation).count(),
            "gl": db.query(GLTransaction).count(),
        }
        assert after == before

        response = Response()
        items = base_api.list_migration_items(
            run.id,
            response=response,
            resource="bank_reconciliations",
            limit=20,
            db=db,
            current_user=admin,
        )
        assert items[0].target_exists is True
        assert items[0].target_label == f"Bank Reconciliation #{target.id}: 2026-09-30"
        assert response.headers["cache-control"] == "no-store"

        audit_text = "\n".join(
            str(row.new_value or "")
            for row in db.query(AuditLog)
            .filter(AuditLog.entity_type == "platform_migration_run")
            .all()
        )
        assert "DO-NOT-PERSIST-RAW" not in audit_text
    finally:
        db.close()
        engine.dispose()


def test_buildium_bank_reconciliation_fails_closed_for_balance_or_dependency_drift():
    db, engine = _session()
    try:
        admin = _admin(db)
        _, _, _, target, run, bank_mapping = _fixture(db)

        bad = _record()
        bad["Balance"]["StatementBalance"]["EndingBalance"] = "100.001"
        preview = api.dry_run_buildium_bank_reconciliations(
            run.id,
            BuildiumBankReconciliationDryRunIn(records=[bad]),
            db=db,
            current_user=admin,
        )
        assert preview.invalid == 1
        assert "two decimal places" in preview.rows[0].reason

        resolution = BuildiumBankReconciliationResolutionIn(
            source_id=8001,
            action="MATCH_EXISTING",
            target_reconciliation_id=target.id,
        )
        reviewed = api.dry_run_buildium_bank_reconciliations(
            run.id,
            BuildiumBankReconciliationDryRunIn(
                records=[_record()], resolutions=[resolution]
            ),
            db=db,
            current_user=admin,
        )
        bank_mapping.source_fingerprint = "b" * 64
        db.commit()
        with pytest.raises(HTTPException) as exc:
            api.commit_buildium_bank_reconciliations(
                run.id,
                BuildiumBankReconciliationCommitIn(
                    fingerprint=reviewed.fingerprint,
                    records=[_record()],
                    resolutions=[resolution],
                ),
                db=db,
                current_user=admin,
            )
        assert exc.value.status_code == 409
        assert "stale" in exc.value.detail.lower()
        assert db.query(PlatformMigrationItem).filter(
            PlatformMigrationItem.resource == "BANK_RECONCILIATIONS"
        ).count() == 0

        # A source-finished reconciliation cannot map to an OPEN target.
        bank_mapping.source_fingerprint = "a" * 64
        target.status = "OPEN"
        db.commit()
        with pytest.raises(HTTPException) as exc:
            api.dry_run_buildium_bank_reconciliations(
                run.id,
                BuildiumBankReconciliationDryRunIn(
                    records=[_record()], resolutions=[resolution]
                ),
                db=db,
                current_user=admin,
            )
        assert exc.value.status_code == 409
        assert "no longer matches" in exc.value.detail.lower()
    finally:
        db.close()
        engine.dispose()


def test_buildium_bank_reconciliation_skip_missing_dependency_and_routes():
    from app.main import app

    db, engine = _session()
    try:
        admin = _admin(db)
        _, _, _, _, run, bank_mapping = _fixture(db)

        db.delete(bank_mapping)
        db.commit()
        missing = api.dry_run_buildium_bank_reconciliations(
            run.id,
            BuildiumBankReconciliationDryRunIn(records=[_record()]),
            db=db,
            current_user=admin,
        )
        assert missing.invalid == 1
        assert "Bank Account mapping" in missing.rows[0].reason

        # Restore a dependency and verify an explicit skip records no durable target mapping.
        db.add(
            PlatformMigrationItem(
                run_id=run.id,
                organization_id=run.organization_id,
                provider="BUILDIUM",
                resource="BANK_ACCOUNTS",
                source_id="7001",
                target_entity="BANK_ACCOUNT",
                target_id=1,
                source_fingerprint="c" * 64,
            )
        )
        db.commit()
        skip = BuildiumBankReconciliationResolutionIn(
            source_id=8001,
            action="SKIP",
        )
        reviewed = api.dry_run_buildium_bank_reconciliations(
            run.id,
            BuildiumBankReconciliationDryRunIn(
                records=[_record()], resolutions=[skip]
            ),
            db=db,
            current_user=admin,
        )
        result = api.commit_buildium_bank_reconciliations(
            run.id,
            BuildiumBankReconciliationCommitIn(
                fingerprint=reviewed.fingerprint,
                records=[_record()],
                resolutions=[skip],
            ),
            db=db,
            current_user=admin,
        )
        assert result.matched_existing == 0
        assert result.skipped_review == 1
        assert db.query(PlatformMigrationItem).filter(
            PlatformMigrationItem.resource == "BANK_RECONCILIATIONS"
        ).count() == 0

        paths = set(app.openapi()["paths"])
        assert "/api/platform/migrations/buildium/runs/{run_id}/bank-reconciliations/dry-run" in paths
        assert "/api/platform/migrations/buildium/runs/{run_id}/bank-reconciliations/commit" in paths
    finally:
        db.close()
        engine.dispose()
