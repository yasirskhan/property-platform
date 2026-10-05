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
from app.models.property import Property, Unit
from app.models.user import Organization
from app.routers import buildium_bank_transfer_migrations as api
from app.routers import buildium_migrations as base_api
from app.schemas.buildium_bank_transfer_migration import (
    BuildiumBankTransferCommitIn,
    BuildiumBankTransferDryRunIn,
    BuildiumBankTransferResolutionIn,
)


def _session():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, expire_on_commit=False)(), engine


def _admin(db):
    row = PlatformUser(
        email="buildium-bank-transfer-admin@example.com",
        hashed_password=hash_password("test-password"),
        first_name="Buildium",
        last_name="Transfer",
        role=PlatformUserRole.PLATFORM_ADMIN,
        is_active=True,
    )
    db.add(row)
    db.commit()
    return row


def _fixture(db):
    org = Organization(
        name="Buildium Bank Transfer Org",
        slug="buildium-bank-transfer-org",
        is_active=True,
    )
    db.add(org)
    db.flush()
    prop = Property(
        organization_id=org.id,
        name="Transfer Property",
        address_line1="10 Transfer Ave",
        city="Cleveland",
        state="OH",
        zip_code="44113",
        country="USA",
        is_active=True,
    )
    db.add(prop)
    db.flush()
    unit = Unit(
        property_id=prop.id,
        unit_number="1A",
        monthly_rent=Decimal("1000.00"),
        is_active=True,
    )
    source_gl = GLAccount(
        organization_id=org.id,
        gl_number="1100",
        name="Operating Cash",
        account_type="ASSET",
        is_active=True,
    )
    destination_gl = GLAccount(
        organization_id=org.id,
        gl_number="1150",
        name="Trust Cash",
        account_type="ASSET",
        is_active=True,
    )
    db.add_all([unit, source_gl, destination_gl])
    db.flush()
    source_bank = BankAccount(
        organization_id=org.id,
        name="Operating",
        account_type="OPERATING",
        gl_account_id=source_gl.id,
        is_active=True,
    )
    destination_bank = BankAccount(
        organization_id=org.id,
        name="Trust",
        account_type="ESCROW",
        gl_account_id=destination_gl.id,
        is_active=True,
    )
    db.add_all([source_bank, destination_bank])
    db.flush()
    txn = GLTransaction(
        organization_id=org.id,
        transaction_date=date(2026, 10, 1),
        transaction_type="TRANSFER",
        reference_number="TR-9001",
        memo="Existing bank transfer",
        is_reversed=False,
    )
    db.add(txn)
    db.flush()
    db.add_all([
        GLEntry(
            organization_id=org.id,
            transaction_id=txn.id,
            gl_account_id=source_gl.id,
            property_id=prop.id,
            unit_id=unit.id,
            debit=Decimal("0.00"),
            credit=Decimal("250.00"),
        ),
        GLEntry(
            organization_id=org.id,
            transaction_id=txn.id,
            gl_account_id=destination_gl.id,
            property_id=prop.id,
            unit_id=unit.id,
            debit=Decimal("250.00"),
            credit=Decimal("0.00"),
        ),
    ])
    run = PlatformMigrationRun(
        organization_id=org.id,
        provider="BUILDIUM",
        source_account_ref="buildium-bank-transfer-source",
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
            target_id=source_bank.id,
            source_fingerprint="1" * 64,
        ),
        PlatformMigrationItem(
            run_id=run.id,
            organization_id=org.id,
            provider="BUILDIUM",
            resource="BANK_ACCOUNTS",
            source_id="7002",
            target_entity="BANK_ACCOUNT",
            target_id=destination_bank.id,
            source_fingerprint="2" * 64,
        ),
        PlatformMigrationItem(
            run_id=run.id,
            organization_id=org.id,
            provider="BUILDIUM",
            resource="PROPERTIES",
            source_id="501",
            target_entity="PROPERTY",
            target_id=prop.id,
            source_fingerprint="3" * 64,
        ),
        PlatformMigrationItem(
            run_id=run.id,
            organization_id=org.id,
            provider="BUILDIUM",
            resource="UNITS",
            source_id="601",
            target_entity="UNIT",
            target_id=unit.id,
            source_fingerprint="4" * 64,
        ),
    ]
    db.add_all(mappings)
    db.commit()
    return prop, unit, source_bank, destination_bank, txn, run, mappings


def _record(**changes):
    row = {
        "Id": 9001,
        "SourceBankAccountId": 7001,
        "EntryDate": "2026-10-01",
        "Memo": "DO-NOT-PERSIST-RAW",
        "AccountingEntity": {
            "Id": 501,
            "AccountingEntityType": "Rental",
            "Href": "/rentals/501",
            "Unit": {"Id": 601, "Href": "/rentals/501/units/601"},
        },
        "TotalAmount": 250,
        "TransferToBankAccountId": 7002,
    }
    row.update(changes)
    return row


def test_buildium_bank_transfer_maps_exact_existing_transfer_and_replays_without_mutation():
    db, engine = _session()
    try:
        admin = _admin(db)
        prop, unit, source_bank, destination_bank, txn, run, _ = _fixture(db)
        before = {
            "transactions": db.query(GLTransaction).count(),
            "entries": db.query(GLEntry).count(),
            "banks": db.query(BankAccount).count(),
        }

        preview = api.dry_run_buildium_bank_transfers(
            run.id,
            BuildiumBankTransferDryRunIn(records=[_record()]),
            db=db,
            current_user=admin,
        )
        assert preview.invalid == 0
        assert preview.reviewable == 1
        assert preview.rows[0].mapped["source_target_bank_account_id"] == source_bank.id
        assert preview.rows[0].mapped["destination_target_bank_account_id"] == destination_bank.id
        assert preview.rows[0].mapped["target_property_id"] == prop.id
        assert preview.rows[0].mapped["target_unit_id"] == unit.id
        assert any(
            "Possible exact existing target GL transfer" in warning
            for warning in preview.rows[0].warnings
        )

        resolution = BuildiumBankTransferResolutionIn(
            source_id=9001,
            action="MATCH_EXISTING",
            target_gl_transaction_id=txn.id,
        )
        reviewed = api.dry_run_buildium_bank_transfers(
            run.id,
            BuildiumBankTransferDryRunIn(
                records=[_record()],
                resolutions=[resolution],
            ),
            db=db,
            current_user=admin,
        )
        committed = api.commit_buildium_bank_transfers(
            run.id,
            BuildiumBankTransferCommitIn(
                fingerprint=reviewed.fingerprint,
                records=[_record()],
                resolutions=[resolution],
            ),
            db=db,
            current_user=admin,
        )
        assert committed.matched_existing == 1
        assert committed.replayed is False
        assert committed.rows[0].target_gl_transaction_id == txn.id

        mapping = db.query(PlatformMigrationItem).filter(
            PlatformMigrationItem.run_id == run.id,
            PlatformMigrationItem.resource == "BANK_TRANSFERS",
        ).one()
        assert mapping.target_entity == "GL_TRANSACTION_TRANSFER_RELATIONSHIP"
        assert mapping.target_id == txn.id

        replay_preview = api.dry_run_buildium_bank_transfers(
            run.id,
            BuildiumBankTransferDryRunIn(
                records=[_record()],
                resolutions=[resolution],
            ),
            db=db,
            current_user=admin,
        )
        replay = api.commit_buildium_bank_transfers(
            run.id,
            BuildiumBankTransferCommitIn(
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
            "transactions": db.query(GLTransaction).count(),
            "entries": db.query(GLEntry).count(),
            "banks": db.query(BankAccount).count(),
        } == before

        response = Response()
        items = base_api.list_migration_items(
            run.id,
            response=response,
            resource="bank_transfers",
            limit=20,
            db=db,
            current_user=admin,
        )
        assert items[0].target_exists is True
        assert items[0].target_label == f"Transfer GL transaction #{txn.id}: 2026-10-01"
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


def test_buildium_bank_transfer_fails_closed_for_direction_dependency_or_target_drift():
    db, engine = _session()
    try:
        admin = _admin(db)
        _, _, _, _, txn, run, mappings = _fixture(db)

        bad = _record(TotalAmount="250.001")
        preview = api.dry_run_buildium_bank_transfers(
            run.id,
            BuildiumBankTransferDryRunIn(records=[bad]),
            db=db,
            current_user=admin,
        )
        assert preview.invalid == 1
        assert "two decimal places" in preview.rows[0].reason

        resolution = BuildiumBankTransferResolutionIn(
            source_id=9001,
            action="MATCH_EXISTING",
            target_gl_transaction_id=txn.id,
        )
        reviewed = api.dry_run_buildium_bank_transfers(
            run.id,
            BuildiumBankTransferDryRunIn(
                records=[_record()],
                resolutions=[resolution],
            ),
            db=db,
            current_user=admin,
        )
        mappings[0].source_fingerprint = "9" * 64
        db.commit()
        with pytest.raises(HTTPException) as exc:
            api.commit_buildium_bank_transfers(
                run.id,
                BuildiumBankTransferCommitIn(
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
            PlatformMigrationItem.resource == "BANK_TRANSFERS"
        ).count() == 0

        mappings[0].source_fingerprint = "1" * 64
        source_line = db.query(GLEntry).filter(
            GLEntry.transaction_id == txn.id,
            GLEntry.credit > 0,
        ).one()
        source_line.credit = Decimal("0.00")
        source_line.debit = Decimal("250.00")
        db.commit()
        with pytest.raises(HTTPException) as exc:
            api.dry_run_buildium_bank_transfers(
                run.id,
                BuildiumBankTransferDryRunIn(
                    records=[_record()],
                    resolutions=[resolution],
                ),
                db=db,
                current_user=admin,
            )
        assert exc.value.status_code == 409
        assert "no longer matches" in exc.value.detail.lower()
    finally:
        db.close()
        engine.dispose()


def test_buildium_bank_transfer_blocks_unsupported_entity_allows_skip_and_registers_routes():
    from app.main import app

    db, engine = _session()
    try:
        admin = _admin(db)
        _, _, _, _, _, run, _ = _fixture(db)

        unsupported = _record()
        unsupported["AccountingEntity"] = {
            "Id": 501,
            "AccountingEntityType": "Association",
        }
        result = api.dry_run_buildium_bank_transfers(
            run.id,
            BuildiumBankTransferDryRunIn(records=[unsupported]),
            db=db,
            current_user=admin,
        )
        assert result.invalid == 1
        assert "only Buildium Rental" in result.rows[0].reason

        skip = BuildiumBankTransferResolutionIn(
            source_id=9001,
            action="SKIP",
        )
        reviewed = api.dry_run_buildium_bank_transfers(
            run.id,
            BuildiumBankTransferDryRunIn(
                records=[_record()],
                resolutions=[skip],
            ),
            db=db,
            current_user=admin,
        )
        committed = api.commit_buildium_bank_transfers(
            run.id,
            BuildiumBankTransferCommitIn(
                fingerprint=reviewed.fingerprint,
                records=[_record()],
                resolutions=[skip],
            ),
            db=db,
            current_user=admin,
        )
        assert committed.matched_existing == 0
        assert committed.skipped_review == 1
        assert db.query(PlatformMigrationItem).filter(
            PlatformMigrationItem.resource == "BANK_TRANSFERS"
        ).count() == 0

        paths = set(app.openapi()["paths"])
        assert "/api/platform/migrations/buildium/runs/{run_id}/bank-transfers/dry-run" in paths
        assert "/api/platform/migrations/buildium/runs/{run_id}/bank-transfers/commit" in paths
    finally:
        db.close()
        engine.dispose()
