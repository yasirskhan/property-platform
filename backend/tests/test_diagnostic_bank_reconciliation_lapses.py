from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.bank_account import BankAccount
from app.models.bank_reconciliation import (
    BankReconciliation,
    BankReconciliationItem,
    BankStatementLine,
)
from app.models.gl_account import GLAccount
from app.models.user import Organization, User
from app.services.diagnostics import check_bank_reconciliation_lapses


TABLES = [
    Organization.__table__,
    User.__table__,
    GLAccount.__table__,
    BankAccount.__table__,
    BankReconciliation.__table__,
    BankReconciliationItem.__table__,
    BankStatementLine.__table__,
]


def _session():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine, tables=TABLES)
    return sessionmaker(bind=engine, expire_on_commit=False)(), engine


def _bank(db, org: Organization, number: str, name: str, created_at: datetime, *, active: bool = True):
    gl = GLAccount(
        organization_id=org.id,
        gl_number=number,
        name=f"{name} Cash",
        account_type="ASSET",
        is_active=True,
    )
    db.add(gl)
    db.flush()
    bank = BankAccount(
        organization_id=org.id,
        name=name,
        gl_account_id=gl.id,
        account_type="OPERATING",
        is_active=active,
        created_at=created_at,
    )
    db.add(bank)
    db.flush()
    return bank


def _reconciled(db, org: Organization, bank: BankAccount, statement_date: date):
    row = BankReconciliation(
        organization_id=org.id,
        bank_account_id=bank.id,
        statement_date=statement_date,
        beginning_balance=0,
        ending_statement_balance=0,
        status="RECONCILED",
    )
    db.add(row)
    db.flush()
    return row


def test_bank_reconciliation_lapses_flags_only_active_same_org_accounts_over_60_days():
    db, engine = _session()
    try:
        org = Organization(name="Diagnostics", slug="diagnostics-lapses")
        other = Organization(name="Other", slug="other-lapses")
        db.add_all([org, other])
        db.flush()

        overdue = _bank(
            db, org, "1150", "Old Trust", datetime(2026, 1, 1)
        )
        recent = _bank(
            db, org, "1160", "Recent Escrow", datetime(2026, 1, 1)
        )
        never_old = _bank(
            db, org, "1170", "Never Old", datetime(2026, 6, 1)
        )
        never_new = _bank(
            db, org, "1180", "Never New", datetime(2026, 9, 1)
        )
        exactly_sixty = _bank(
            db, org, "1190", "Exactly Sixty", datetime(2026, 1, 1)
        )
        inactive = _bank(
            db,
            org,
            "1200",
            "Inactive",
            datetime(2026, 1, 1),
            active=False,
        )
        other_bank = _bank(
            db, other, "1150", "Other Old", datetime(2026, 1, 1)
        )

        _reconciled(db, org, overdue, date(2026, 6, 1))
        _reconciled(db, org, recent, date(2026, 8, 10))
        _reconciled(db, org, exactly_sixty, date(2026, 7, 27))
        _reconciled(db, other, other_bank, date(2026, 1, 1))
        db.commit()

        report = check_bank_reconciliation_lapses(
            db,
            org.id,
            as_of=date(2026, 9, 25),
        )

        assert report["passed"] is False
        assert report["severity"] == "warning"
        details = {row["bank_account"]: row for row in report["details"]}
        assert set(details) == {"Old Trust", "Never Old"}
        assert details["Old Trust"]["status"] == "OVERDUE"
        assert details["Old Trust"]["last_reconciled_statement_date"] == "2026-06-01"
        assert details["Never Old"]["status"] == "NEVER_RECONCILED"
        assert details["Never Old"]["last_reconciled_statement_date"] is None
        assert "Recent Escrow" not in details
        assert "Never New" not in details
        assert "Exactly Sixty" not in details
        assert "Inactive" not in details
    finally:
        db.close()
        engine.dispose()


def test_bank_reconciliation_lapses_passes_with_no_active_bank_accounts():
    db, engine = _session()
    try:
        org = Organization(name="Empty", slug="diagnostics-empty")
        db.add(org)
        db.commit()

        report = check_bank_reconciliation_lapses(
            db,
            org.id,
            as_of=date(2026, 9, 25),
        )

        assert report["passed"] is True
        assert report["details"] == []
        assert "0 active bank account" in report["message"]
    finally:
        db.close()
        engine.dispose()
