# ============================================================
# diagnostics.py
# ------------------------------------------------------------
# Financial health checks over the General Ledger.
#
# Nine checks (Section 35 + Phase 3.6 additions in PROJECT_MASTER):
#   1. Security Deposit Funds Mismatch
#   2. Escrow Cash Account Balance Mismatch
#   3. Non-Zero Security Clearing Account Balances
#   4. Negative Balance on Fee GL Accounts
#   5. Positive Balance on Fee GL Accounts
#   6. Bank Reconciliation Lapses
#   7. Unbalanced Posted GL Transactions
#   8. Bank Account GL Mapping Health
#   9. Trust Account 3-Way Reconciliation
#
# Each check is a function that returns:
#   {
#     "key":       "SECURITY_DEPOSIT_MISMATCH",
#     "label":     "Security Deposit Funds Mismatch",
#     "passed":    bool,
#     "severity":  "ok" | "warning" | "error",
#     "message":   str,
#     "details":   [ {...}, ... ]
#   }
#
# The report is read-only — it never posts anything. Corrective
# postings (e.g. "Refund Negative Diagnostic") will come later.
#
# AppFolio parity: check 6 is the real 3-way reconciliation —
# bank statement balance must equal trust GL cash, which must
# equal the sum of every owner sub-ledger.
# ============================================================

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.bank_account import BankAccount
from app.models.bank_reconciliation import BankReconciliation
from app.models.gl_account import GLAccount
from app.models.gl_entry import GLEntry
from app.models.gl_transaction import GLTransaction
from app.schemas.gl_transaction import PostingLine
from app.services.gl_posting import PostingError, post_transaction
from app.services.owner_ledger import get_owner_subledger_total


# ============================================================
# Helpers
# ============================================================

def _balance_of(
    db: Session,
    organization_id: int,
    gl_account: GLAccount,
    as_of=None,
) -> Decimal:
    """Return debit-minus-credit for one GL account."""
    q = (
        db.query(
            func.coalesce(func.sum(GLEntry.debit), 0),
            func.coalesce(func.sum(GLEntry.credit), 0),
        )
        .join(GLTransaction, GLTransaction.id == GLEntry.transaction_id)
        .filter(
            GLEntry.organization_id == organization_id,
            GLEntry.gl_account_id == gl_account.id,
        )
    )
    if as_of is not None:
        q = q.filter(GLTransaction.transaction_date <= as_of)
    debit_total, credit_total = q.one()
    return Decimal(debit_total or 0) - Decimal(credit_total or 0)


def _balance_of_number(
    db: Session,
    organization_id: int,
    gl_number: str,
    as_of=None,
) -> Optional[Decimal]:
    """Balance of a GL account looked up by its number (e.g. "1150").
    Returns None if the account doesn't exist in this org."""
    acct = (
        db.query(GLAccount)
        .filter(
            GLAccount.organization_id == organization_id,
            GLAccount.gl_number == gl_number,
        )
        .first()
    )
    if acct is None:
        return None
    return _balance_of(db, organization_id, acct, as_of=as_of)


def _is_zero(value: Decimal, tolerance: Decimal = Decimal("0.01")) -> bool:
    return abs(value) <= tolerance


# ============================================================
# CHECK 1 — Security Deposit Funds Mismatch
# ------------------------------------------------------------
# GL 2101 (Security Deposits liability) must equal GL 1160
# (Security Deposit Cash asset). If they don't match, some
# security deposit money was moved without a corresponding
# liability entry.
# ============================================================

def check_security_deposit_mismatch(
    db: Session, organization_id: int
) -> Dict:
    liability = _balance_of_number(db, organization_id, "2101")
    cash = _balance_of_number(db, organization_id, "1160")

    if liability is None or cash is None:
        return {
            "key": "SECURITY_DEPOSIT_MISMATCH",
            "label": "Security Deposit Funds Mismatch",
            "passed": True,
            "severity": "ok",
            "message": "Security deposit accounts not yet in use.",
            "details": [],
        }

    # Liability has natural credit balance; cash has natural debit.
    # Compare their magnitudes.
    liability_mag = abs(liability)
    cash_mag = abs(cash)

    if _is_zero(liability_mag - cash_mag):
        return {
            "key": "SECURITY_DEPOSIT_MISMATCH",
            "label": "Security Deposit Funds Mismatch",
            "passed": True,
            "severity": "ok",
            "message": (
                f"Security deposit liability (${liability_mag}) "
                f"matches cash (${cash_mag})."
            ),
            "details": [],
        }

    diff = liability_mag - cash_mag
    return {
        "key": "SECURITY_DEPOSIT_MISMATCH",
        "label": "Security Deposit Funds Mismatch",
        "passed": False,
        "severity": "error",
        "message": (
            f"Security deposit liability (${liability_mag}) does not "
            f"match cash (${cash_mag}). Difference: ${diff}."
        ),
        "details": [
            {"gl": "2101", "name": "Security Deposits", "balance": str(liability_mag)},
            {"gl": "1160", "name": "Security Deposit Cash", "balance": str(cash_mag)},
            {"difference": str(diff)},
        ],
    }


# ============================================================
# CHECK 2 — Escrow Cash Account Balance Mismatch
# ------------------------------------------------------------
# In AppFolio, the escrow cash account must equal the sum of
# liabilities it's offsetting. For our simple model, the escrow
# side is 1160 (Security Deposit Cash). We already check that
# against 2101 in check 1, so here we check the OTHER direction:
# the offset_account field on GL 1160 must be configured and
# match. If 1160 has no offset_account set, that's the issue.
# ============================================================

def check_escrow_cash_mismatch(
    db: Session, organization_id: int
) -> Dict:
    escrow = (
        db.query(GLAccount)
        .filter(
            GLAccount.organization_id == organization_id,
            GLAccount.gl_number == "1160",
        )
        .first()
    )
    if escrow is None:
        return {
            "key": "ESCROW_CASH_MISMATCH",
            "label": "Escrow Cash Account Balance Mismatch",
            "passed": True,
            "severity": "ok",
            "message": "Escrow cash account not yet in use.",
            "details": [],
        }

    if not escrow.offset_account:
        return {
            "key": "ESCROW_CASH_MISMATCH",
            "label": "Escrow Cash Account Balance Mismatch",
            "passed": False,
            "severity": "warning",
            "message": (
                "Escrow cash account (1160) has no offset account "
                "configured. Set one so it can be reconciled."
            ),
            "details": [
                {"gl": "1160", "name": escrow.name, "offset_account": None}
            ],
        }

    escrow_balance = _balance_of(db, organization_id, escrow)
    offset_balance = _balance_of_number(
        db, organization_id, escrow.offset_account
    )
    if offset_balance is None:
        return {
            "key": "ESCROW_CASH_MISMATCH",
            "label": "Escrow Cash Account Balance Mismatch",
            "passed": False,
            "severity": "error",
            "message": (
                f"Escrow offset account {escrow.offset_account} not "
                f"found in the Chart of Accounts."
            ),
            "details": [],
        }

    # Escrow cash is an asset (debit nature), offset is a liability
    # (credit nature). They should have equal magnitudes.
    if _is_zero(abs(escrow_balance) - abs(offset_balance)):
        return {
            "key": "ESCROW_CASH_MISMATCH",
            "label": "Escrow Cash Account Balance Mismatch",
            "passed": True,
            "severity": "ok",
            "message": (
                f"Escrow cash (${abs(escrow_balance)}) matches "
                f"offset {escrow.offset_account} "
                f"(${abs(offset_balance)})."
            ),
            "details": [],
        }

    return {
        "key": "ESCROW_CASH_MISMATCH",
        "label": "Escrow Cash Account Balance Mismatch",
        "passed": False,
        "severity": "error",
        "message": (
            f"Escrow cash (${abs(escrow_balance)}) does not match "
            f"offset {escrow.offset_account} (${abs(offset_balance)})."
        ),
        "details": [
            {"gl": "1160", "name": escrow.name, "balance": str(abs(escrow_balance))},
            {
                "gl": escrow.offset_account,
                "name": "Offset account",
                "balance": str(abs(offset_balance)),
            },
        ],
    }


# ============================================================
# CHECK 3 — Non-Zero Security Clearing Account Balances
# ------------------------------------------------------------
# A "clearing" account is a pass-through. Every deposit into it
# must be matched by a withdrawal. If its balance isn't $0 at
# the end of the period, something is stuck.
#
# Convention: any account with "Clearing" in its name (case-
# insensitive) should net to $0.
# ============================================================

def check_clearing_accounts(
    db: Session, organization_id: int
) -> Dict:
    clearing_accounts = (
        db.query(GLAccount)
        .filter(
            GLAccount.organization_id == organization_id,
            GLAccount.is_active.is_(True),
            func.lower(GLAccount.name).like("%clearing%"),
        )
        .all()
    )

    if not clearing_accounts:
        return {
            "key": "CLEARING_ACCOUNTS",
            "label": "Non-Zero Clearing Account Balances",
            "passed": True,
            "severity": "ok",
            "message": "No clearing accounts configured.",
            "details": [],
        }

    bad = []
    for acct in clearing_accounts:
        bal = _balance_of(db, organization_id, acct)
        if not _is_zero(bal):
            bad.append(
                {
                    "gl": acct.gl_number,
                    "name": acct.name,
                    "balance": str(bal),
                }
            )

    if not bad:
        return {
            "key": "CLEARING_ACCOUNTS",
            "label": "Non-Zero Clearing Account Balances",
            "passed": True,
            "severity": "ok",
            "message": (
                f"All {len(clearing_accounts)} clearing account(s) "
                f"are at $0."
            ),
            "details": [],
        }

    return {
        "key": "CLEARING_ACCOUNTS",
        "label": "Non-Zero Clearing Account Balances",
        "passed": False,
        "severity": "error",
        "message": (
            f"{len(bad)} clearing account(s) have non-zero balances."
        ),
        "details": bad,
    }


# ============================================================
# CHECK 4 — Negative Balance on Fee GL Accounts
# ------------------------------------------------------------
# Fee accounts (44xx range) should never go negative — a
# negative balance means we refunded more than we collected.
# ============================================================

def check_negative_fee_accounts(
    db: Session, organization_id: int
) -> Dict:
    fee_accounts = (
        db.query(GLAccount)
        .filter(
            GLAccount.organization_id == organization_id,
            GLAccount.is_active.is_(True),
            GLAccount.account_type == "INCOME",
            GLAccount.gl_number.like("44%"),
        )
        .all()
    )

    if not fee_accounts:
        return {
            "key": "NEGATIVE_FEE_ACCOUNTS",
            "label": "Negative Balance on Fee GL Accounts",
            "passed": True,
            "severity": "ok",
            "message": "No fee accounts configured.",
            "details": [],
        }

    bad = []
    for acct in fee_accounts:
        # Income accounts are credit-nature: balance = credit - debit.
        # A "negative income" means debit exceeds credit.
        raw = _balance_of(db, organization_id, acct)
        income_balance = -raw  # natural income balance
        if income_balance < -Decimal("0.01"):
            bad.append(
                {
                    "gl_account_id": acct.id,
                    "gl": acct.gl_number,
                    "name": acct.name,
                    "balance": str(income_balance),
                    "offset_account": acct.offset_account,
                }
            )

    if not bad:
        return {
            "key": "NEGATIVE_FEE_ACCOUNTS",
            "label": "Negative Balance on Fee GL Accounts",
            "passed": True,
            "severity": "ok",
            "message": f"All {len(fee_accounts)} fee account(s) are healthy.",
            "details": [],
        }

    return {
        "key": "NEGATIVE_FEE_ACCOUNTS",
        "label": "Negative Balance on Fee GL Accounts",
        "passed": False,
        "severity": "error",
        "message": (
            f"{len(bad)} fee account(s) have negative balances — "
            f"likely over-refunded."
        ),
        "details": bad,
    }


# ============================================================
# CORRECTIVE ACTION — Refund Negative Diagnostic
# ============================================================

def refund_negative_fee_account(
    db: Session,
    *,
    organization_id: int,
    gl_account_id: int,
    transaction_date: date,
    created_by,
):
    """Bring one negative 44xx fee-income account back to zero."""
    fee_account = (
        db.query(GLAccount)
        .filter(
            GLAccount.id == gl_account_id,
            GLAccount.organization_id == organization_id,
            GLAccount.is_active.is_(True),
            GLAccount.account_type == "INCOME",
            GLAccount.gl_number.like("44%"),
        )
        .first()
    )
    if fee_account is None:
        raise PostingError("Active fee income account was not found in this organization.")

    raw_balance = _balance_of(db, organization_id, fee_account)
    income_balance = -raw_balance
    if income_balance >= -Decimal("0.01"):
        raise PostingError("This fee account no longer has a negative balance.")

    offset_number = (fee_account.offset_account or "").strip()
    if not offset_number:
        raise PostingError(
            f"Fee account {fee_account.gl_number} has no offset account configured."
        )
    if offset_number == fee_account.gl_number:
        raise PostingError("A fee account cannot use itself as its diagnostic offset.")

    offset_account = (
        db.query(GLAccount)
        .filter(
            GLAccount.organization_id == organization_id,
            GLAccount.gl_number == offset_number,
            GLAccount.is_active.is_(True),
        )
        .first()
    )
    if offset_account is None:
        raise PostingError(
            f"Configured offset account {offset_number} was not found or is inactive."
        )

    amount = abs(income_balance)
    txn = post_transaction(
        db=db,
        organization_id=organization_id,
        transaction_date=transaction_date,
        transaction_type="REFUND_NEGATIVE_DIAGNOSTIC",
        memo=f"Refund Negative Diagnostic: zero negative fee account {fee_account.gl_number}",
        reference_number=f"RND-{fee_account.gl_number}",
        source_type="financial_diagnostic",
        source_id=fee_account.id,
        created_by=created_by,
        lines=[
            PostingLine(
                gl_account_id=offset_account.id,
                description=f"Refund Negative Diagnostic offset for {fee_account.gl_number}",
                debit=amount,
            ),
            PostingLine(
                gl_account_id=fee_account.id,
                description=f"Refund Negative Diagnostic correction for {fee_account.gl_number}",
                credit=amount,
            ),
        ],
    )
    return {
        "transaction_id": txn.id,
        "gl_account_id": fee_account.id,
        "gl_number": fee_account.gl_number,
        "offset_gl_account_id": offset_account.id,
        "offset_gl_number": offset_account.gl_number,
        "amount": amount,
    }


# ============================================================
# CHECK 5 — Positive Balance on Fee GL Accounts
# ------------------------------------------------------------
# Some fee accounts should clear to $0 after each cycle.
# AppFolio flags accounts that carry a positive balance when
# they shouldn't. For now we treat this as a soft warning —
# ANY fee account with a positive balance is flagged so the
# manager knows to review. (Refine later if needed.)
#
# Only active income accounts explicitly marked must_clear are
# evaluated. The flag is configured on the Chart of Accounts.
# ============================================================

def check_positive_fee_accounts(
    db: Session, organization_id: int
) -> Dict:
    must_clear_accounts = (
        db.query(GLAccount)
        .filter(
            GLAccount.organization_id == organization_id,
            GLAccount.is_active.is_(True),
            GLAccount.account_type == "INCOME",
            GLAccount.must_clear.is_(True),
        )
        .order_by(GLAccount.gl_number.asc(), GLAccount.id.asc())
        .all()
    )

    if not must_clear_accounts:
        return {
            "key": "POSITIVE_FEE_ACCOUNTS",
            "label": "Positive Balance on Fee GL Accounts",
            "passed": True,
            "severity": "ok",
            "message": "No active income accounts are marked as must-clear.",
            "details": [],
        }

    bad = []
    for acct in must_clear_accounts:
        raw = _balance_of(db, organization_id, acct)
        income_balance = -raw
        if income_balance > Decimal("0.01"):
            bad.append(
                {
                    "gl_account_id": acct.id,
                    "gl": acct.gl_number,
                    "name": acct.name,
                    "balance": str(income_balance),
                }
            )

    if not bad:
        return {
            "key": "POSITIVE_FEE_ACCOUNTS",
            "label": "Positive Balance on Fee GL Accounts",
            "passed": True,
            "severity": "ok",
            "message": (
                f"All {len(must_clear_accounts)} must-clear income "
                "account(s) are at zero or below."
            ),
            "details": [],
        }

    return {
        "key": "POSITIVE_FEE_ACCOUNTS",
        "label": "Positive Balance on Fee GL Accounts",
        "passed": False,
        "severity": "warning",
        "message": (
            f"{len(bad)} must-clear income account(s) have positive "
            "balances that should be reviewed."
        ),
        "details": bad,
    }


# ============================================================
# CHECK 6 — Bank Reconciliation Lapses
# ------------------------------------------------------------
# Active bank accounts should be reconciled at least every
# 60 days. Accounts that have never been reconciled are flagged
# once they have existed for more than 60 days.
# ============================================================

def check_bank_reconciliation_lapses(
    db: Session,
    organization_id: int,
    *,
    as_of: date | None = None,
) -> Dict:
    as_of = as_of or date.today()
    cutoff = as_of - timedelta(days=60)
    bank_accounts = (
        db.query(BankAccount)
        .filter(
            BankAccount.organization_id == organization_id,
            BankAccount.is_active.is_(True),
        )
        .order_by(BankAccount.id.asc())
        .all()
    )

    overdue = []
    for account in bank_accounts:
        last = (
            db.query(BankReconciliation)
            .filter(
                BankReconciliation.organization_id == organization_id,
                BankReconciliation.bank_account_id == account.id,
                BankReconciliation.status == "RECONCILED",
            )
            .order_by(
                BankReconciliation.statement_date.desc(),
                BankReconciliation.id.desc(),
            )
            .first()
        )

        if last is not None:
            days_since = (as_of - last.statement_date).days
            if last.statement_date < cutoff:
                overdue.append(
                    {
                        "bank_account_id": account.id,
                        "bank_account": account.name,
                        "last_reconciled_statement_date": last.statement_date.isoformat(),
                        "days_since_reconciliation": days_since,
                        "status": "OVERDUE",
                    }
                )
            continue

        created_date = account.created_at.date() if account.created_at else as_of
        days_since = (as_of - created_date).days
        if created_date < cutoff:
            overdue.append(
                {
                    "bank_account_id": account.id,
                    "bank_account": account.name,
                    "last_reconciled_statement_date": None,
                    "days_since_reconciliation": days_since,
                    "status": "NEVER_RECONCILED",
                }
            )

    if not overdue:
        return {
            "key": "BANK_RECONCILIATION_LAPSES",
            "label": "Bank Reconciliation Lapses",
            "passed": True,
            "severity": "ok",
            "message": (
                f"All {len(bank_accounts)} active bank account(s) are within "
                "the 60-day reconciliation window."
            ),
            "details": [],
        }

    return {
        "key": "BANK_RECONCILIATION_LAPSES",
        "label": "Bank Reconciliation Lapses",
        "passed": False,
        "severity": "warning",
        "message": (
            f"{len(overdue)} active bank account(s) have not been reconciled "
            "within 60 days."
        ),
        "details": overdue,
    }


# ============================================================
# CHECK 7 — Unbalanced Posted GL Transactions
# ------------------------------------------------------------
# Central posting rejects unbalanced transactions, but this
# integrity check detects legacy/import/manual database corruption.
# It is read-only and scoped to the current organization.
# ============================================================

def check_unbalanced_gl_transactions(
    db: Session, organization_id: int
) -> Dict:
    rows = (
        db.query(
            GLTransaction.id,
            GLTransaction.transaction_date,
            GLTransaction.transaction_type,
            GLTransaction.reference_number,
            func.count(GLEntry.id).label("entry_count"),
            func.coalesce(func.sum(GLEntry.debit), 0).label("debit_total"),
            func.coalesce(func.sum(GLEntry.credit), 0).label("credit_total"),
        )
        .outerjoin(
            GLEntry,
            (GLEntry.transaction_id == GLTransaction.id)
            & (GLEntry.organization_id == organization_id),
        )
        .filter(GLTransaction.organization_id == organization_id)
        .group_by(
            GLTransaction.id,
            GLTransaction.transaction_date,
            GLTransaction.transaction_type,
            GLTransaction.reference_number,
        )
        .order_by(GLTransaction.id.asc())
        .all()
    )

    bad = []
    for row in rows:
        debit_total = Decimal(row.debit_total or 0)
        credit_total = Decimal(row.credit_total or 0)
        entry_count = int(row.entry_count or 0)
        if (
            entry_count < 2
            or debit_total <= Decimal("0")
            or credit_total <= Decimal("0")
            or abs(debit_total - credit_total) > Decimal("0.01")
        ):
            bad.append(
                {
                    "transaction_id": row.id,
                    "transaction_date": row.transaction_date.isoformat(),
                    "transaction_type": row.transaction_type,
                    "reference_number": row.reference_number,
                    "entry_count": entry_count,
                    "debits": str(debit_total),
                    "credits": str(credit_total),
                    "difference": str(debit_total - credit_total),
                }
            )

    if not bad:
        return {
            "key": "UNBALANCED_GL_TRANSACTIONS",
            "label": "Posted GL Transaction Integrity",
            "passed": True,
            "severity": "ok",
            "message": f"All {len(rows)} posted GL transaction(s) are balanced.",
            "details": [],
        }

    return {
        "key": "UNBALANCED_GL_TRANSACTIONS",
        "label": "Posted GL Transaction Integrity",
        "passed": False,
        "severity": "error",
        "message": (
            f"{len(bad)} posted GL transaction(s) are missing lines or do not balance."
        ),
        "details": bad,
    }


# ============================================================
# CHECK 8 — Bank Account GL Mapping Health
# ------------------------------------------------------------
# Every active physical bank account must map to an active ASSET
# GL account owned by the same organization.
# ============================================================

def check_bank_account_gl_mappings(
    db: Session, organization_id: int
) -> Dict:
    bank_accounts = (
        db.query(BankAccount)
        .filter(
            BankAccount.organization_id == organization_id,
            BankAccount.is_active.is_(True),
        )
        .order_by(BankAccount.id.asc())
        .all()
    )

    bad = []
    for bank in bank_accounts:
        gl_account = db.get(GLAccount, bank.gl_account_id)
        reason = None
        if gl_account is None:
            reason = "GL_ACCOUNT_NOT_FOUND"
        elif gl_account.organization_id != organization_id:
            reason = "CROSS_ORGANIZATION_GL"
        elif not gl_account.is_active:
            reason = "INACTIVE_GL_ACCOUNT"
        elif gl_account.account_type != "ASSET":
            reason = "GL_ACCOUNT_NOT_ASSET"

        if reason:
            bad.append(
                {
                    "bank_account_id": bank.id,
                    "bank_account": bank.name,
                    "gl_account_id": bank.gl_account_id,
                    "gl_number": gl_account.gl_number if gl_account else None,
                    "gl_account_type": gl_account.account_type if gl_account else None,
                    "reason": reason,
                }
            )

    if not bad:
        return {
            "key": "BANK_ACCOUNT_GL_MAPPINGS",
            "label": "Bank Account GL Mapping Health",
            "passed": True,
            "severity": "ok",
            "message": (
                f"All {len(bank_accounts)} active bank account(s) map to active "
                "same-organization ASSET GL accounts."
            ),
            "details": [],
        }

    return {
        "key": "BANK_ACCOUNT_GL_MAPPINGS",
        "label": "Bank Account GL Mapping Health",
        "passed": False,
        "severity": "error",
        "message": f"{len(bad)} active bank account mapping(s) require correction.",
        "details": bad,
    }


# ============================================================
# CHECK 9 — Trust Account 3-Way Reconciliation
# ------------------------------------------------------------
# THE critical check. Three numbers must agree:
#
#   1. Bank statement balance (manually entered, not tracked yet)
#   2. Trust GL cash balance (GL 1150 Rental Trust)
#   3. Sum of every owner sub-ledger
#
# Since we don't track bank statement balances yet, we compare
# (2) and (3). If they don't match, either:
#   - Some owner-scoped entries are missing an owner_id, OR
#   - Some company-level activity shouldn't be in the trust, OR
#   - There's a real bookkeeping error.
# ============================================================

def check_three_way_reconciliation(
    db: Session, organization_id: int
) -> Dict:
    trust_cash = _balance_of_number(db, organization_id, "1150")
    if trust_cash is None:
        return {
            "key": "THREE_WAY_RECONCILIATION",
            "label": "Trust Account 3-Way Reconciliation",
            "passed": True,
            "severity": "ok",
            "message": "Trust account (1150) not yet in use.",
            "details": [],
        }

    owner_total = get_owner_subledger_total(
        db, organization_id=organization_id
    )

    # Trust cash is debit-nature (positive balance = money in bank).
    # Owner sub-ledger total is what we OWE to owners.
    # For the trust to be in balance:
    #     trust_cash >= owner_total
    # The difference is the broker's own funds or unallocated income.

    diff = trust_cash - owner_total

    if _is_zero(diff):
        return {
            "key": "THREE_WAY_RECONCILIATION",
            "label": "Trust Account 3-Way Reconciliation",
            "passed": True,
            "severity": "ok",
            "message": (
                f"Trust cash (${trust_cash}) matches owner "
                f"sub-ledger total (${owner_total})."
            ),
            "details": [],
        }

    return {
        "key": "THREE_WAY_RECONCILIATION",
        "label": "Trust Account 3-Way Reconciliation",
        "passed": False,
        "severity": "warning",
        "message": (
            f"Trust cash (${trust_cash}) does not match the sum of "
            f"owner sub-ledgers (${owner_total}). "
            f"Unallocated: ${diff}. This is normal until every "
            f"posting carries an owner_id."
        ),
        "details": [
            {"gl": "1150", "name": "Rental Trust (cash)", "balance": str(trust_cash)},
            {"owner_subledger_total": str(owner_total)},
            {"unallocated": str(diff)},
        ],
    }


# ============================================================
# Run all checks
# ============================================================

def run_all_diagnostics(
    db: Session, organization_id: int
) -> Dict:
    """Run every diagnostic and return a summary."""
    checks: List[Dict] = [
        check_security_deposit_mismatch(db, organization_id),
        check_escrow_cash_mismatch(db, organization_id),
        check_clearing_accounts(db, organization_id),
        check_negative_fee_accounts(db, organization_id),
        check_positive_fee_accounts(db, organization_id),
        check_bank_reconciliation_lapses(db, organization_id),
        check_unbalanced_gl_transactions(db, organization_id),
        check_bank_account_gl_mappings(db, organization_id),
        check_three_way_reconciliation(db, organization_id),
    ]

    passed = sum(1 for c in checks if c["passed"])
    errors = sum(1 for c in checks if c["severity"] == "error")
    warnings = sum(1 for c in checks if c["severity"] == "warning")
    all_ok = passed == len(checks)

    return {
        "checks": checks,
        "passed_count": passed,
        "failed_count": len(checks) - passed,
        "error_count": errors,
        "warning_count": warnings,
        "all_passed": all_ok,
    }