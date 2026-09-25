from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import init_db  # noqa: F401
from app.core.database import Base
from app.models.bank_account import BankAccount
from app.models.gl_account import GLAccount
from app.models.gl_entry import GLEntry
from app.models.gl_transaction import GLTransaction
from app.models.user import Organization
from app.services.diagnostics import (
    check_bank_account_gl_mappings,
    check_unbalanced_gl_transactions,
)


def _session():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, expire_on_commit=False)(), engine


def test_unbalanced_transaction_diagnostic_detects_corruption_and_scopes_org():
    db, engine = _session()
    try:
        org = Organization(name="Integrity", slug="integrity")
        other = Organization(name="Other Integrity", slug="other-integrity")
        db.add_all([org, other])
        db.flush()

        cash = GLAccount(
            organization_id=org.id,
            gl_number="1150",
            name="Trust Cash",
            account_type="ASSET",
            is_active=True,
        )
        income = GLAccount(
            organization_id=org.id,
            gl_number="4100",
            name="Rent Income",
            account_type="INCOME",
            is_active=True,
        )
        other_cash = GLAccount(
            organization_id=other.id,
            gl_number="1150",
            name="Other Cash",
            account_type="ASSET",
            is_active=True,
        )
        db.add_all([cash, income, other_cash])
        db.flush()

        good = GLTransaction(
            organization_id=org.id,
            transaction_date=date(2026, 9, 25),
            transaction_type="JOURNAL_ENTRY",
            reference_number="GOOD",
        )
        bad = GLTransaction(
            organization_id=org.id,
            transaction_date=date(2026, 9, 25),
            transaction_type="JOURNAL_ENTRY",
            reference_number="BAD",
        )
        foreign = GLTransaction(
            organization_id=other.id,
            transaction_date=date(2026, 9, 25),
            transaction_type="JOURNAL_ENTRY",
            reference_number="FOREIGN",
        )
        db.add_all([good, bad, foreign])
        db.flush()
        db.add_all(
            [
                GLEntry(
                    organization_id=org.id,
                    transaction_id=good.id,
                    gl_account_id=cash.id,
                    debit=Decimal("25.00"),
                    credit=Decimal("0"),
                ),
                GLEntry(
                    organization_id=org.id,
                    transaction_id=good.id,
                    gl_account_id=income.id,
                    debit=Decimal("0"),
                    credit=Decimal("25.00"),
                ),
                GLEntry(
                    organization_id=org.id,
                    transaction_id=bad.id,
                    gl_account_id=cash.id,
                    debit=Decimal("30.00"),
                    credit=Decimal("0"),
                ),
                GLEntry(
                    organization_id=org.id,
                    transaction_id=bad.id,
                    gl_account_id=income.id,
                    debit=Decimal("0"),
                    credit=Decimal("20.00"),
                ),
                GLEntry(
                    organization_id=other.id,
                    transaction_id=foreign.id,
                    gl_account_id=other_cash.id,
                    debit=Decimal("99.00"),
                    credit=Decimal("0"),
                ),
            ]
        )
        db.commit()

        report = check_unbalanced_gl_transactions(db, org.id)

        assert report["passed"] is False
        assert report["severity"] == "error"
        assert len(report["details"]) == 1
        detail = report["details"][0]
        assert detail["transaction_id"] == bad.id
        assert detail["debits"] == "30.00"
        assert detail["credits"] == "20.00"
        assert detail["difference"] == "10.00"
    finally:
        db.close()
        engine.dispose()


def test_bank_mapping_diagnostic_flags_inactive_nonasset_and_cross_org_mappings():
    db, engine = _session()
    try:
        org = Organization(name="Bank Mapping", slug="bank-mapping")
        other = Organization(name="Other Bank Mapping", slug="other-bank-mapping")
        db.add_all([org, other])
        db.flush()

        good_gl = GLAccount(
            organization_id=org.id,
            gl_number="1150",
            name="Operating Cash",
            account_type="ASSET",
            is_active=True,
        )
        inactive_gl = GLAccount(
            organization_id=org.id,
            gl_number="1160",
            name="Inactive Escrow",
            account_type="ASSET",
            is_active=False,
        )
        liability_gl = GLAccount(
            organization_id=org.id,
            gl_number="2101",
            name="Deposit Liability",
            account_type="LIABILITY",
            is_active=True,
        )
        foreign_gl = GLAccount(
            organization_id=other.id,
            gl_number="1150",
            name="Foreign Cash",
            account_type="ASSET",
            is_active=True,
        )
        db.add_all([good_gl, inactive_gl, liability_gl, foreign_gl])
        db.flush()

        banks = [
            BankAccount(
                organization_id=org.id,
                name="Good",
                gl_account_id=good_gl.id,
                account_type="OPERATING",
                is_active=True,
            ),
            BankAccount(
                organization_id=org.id,
                name="Inactive Mapping",
                gl_account_id=inactive_gl.id,
                account_type="ESCROW",
                is_active=True,
            ),
            BankAccount(
                organization_id=org.id,
                name="Non Asset Mapping",
                gl_account_id=liability_gl.id,
                account_type="OPERATING",
                is_active=True,
            ),
            BankAccount(
                organization_id=org.id,
                name="Cross Org Mapping",
                gl_account_id=foreign_gl.id,
                account_type="OPERATING",
                is_active=True,
            ),
        ]
        db.add_all(banks)
        db.commit()

        report = check_bank_account_gl_mappings(db, org.id)

        assert report["passed"] is False
        assert report["severity"] == "error"
        details = {row["bank_account"]: row["reason"] for row in report["details"]}
        assert details == {
            "Inactive Mapping": "INACTIVE_GL_ACCOUNT",
            "Non Asset Mapping": "GL_ACCOUNT_NOT_ASSET",
            "Cross Org Mapping": "CROSS_ORGANIZATION_GL",
        }
        assert "Good" not in details
    finally:
        db.close()
        engine.dispose()


def test_additional_diagnostics_pass_for_clean_or_empty_data():
    db, engine = _session()
    try:
        org = Organization(name="Clean Diagnostics", slug="clean-diagnostics")
        db.add(org)
        db.commit()

        gl_report = check_unbalanced_gl_transactions(db, org.id)
        bank_report = check_bank_account_gl_mappings(db, org.id)

        assert gl_report["passed"] is True
        assert gl_report["details"] == []
        assert bank_report["passed"] is True
        assert bank_report["details"] == []
    finally:
        db.close()
        engine.dispose()
