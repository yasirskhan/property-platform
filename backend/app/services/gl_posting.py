# ============================================================
# gl_posting.py
# ------------------------------------------------------------
# The single entry point for writing to the General Ledger.
#
# Every module that touches money — receipts, bills, journal
# entries, bank deposits, management fees, owner draws,
# reversals, transfers — calls post_transaction(). NOTHING
# else writes to gl_transactions or gl_entries.
#
# This gives us:
#   * One place to enforce double-entry balance
#   * One place to enforce org scope
#   * One place to write audit logs
#   * One place to change if the schema evolves
#
# If you ever feel tempted to write directly to the tables,
# stop. Add a feature to post_transaction() instead.
#
# As of Step 8a (Phase 2), each line also carries an optional
# owner_id tag (AppFolio parity — powers the trust sub-ledger
# and 3-way reconciliation).
# ============================================================

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.audit import log_action
from app.models.user import Organization, User
from app.models.gl_account import GLAccount, GLAccountPostingRestriction
from app.models.organization_feature_setting import OrganizationFeatureSetting
from app.models.gl_transaction import GLTransaction
from app.models.gl_entry import GLEntry
from app.models.property import Property, Unit
from app.schemas.gl_transaction import PostingLine
from app.services.release_gate_resolver import release_gate_allows_org

GL_ACCOUNT_PERMISSIONS_GATE = "release.accounting.gl_account_permissions"


# Valid transaction types. Extend this list as new modules
# are built. If a caller passes something not in here, the
# posting is rejected — this prevents typos from silently
# creating garbage transaction types.
VALID_TRANSACTION_TYPES = {
    "RECEIPT",
    "BILL",
    "CHECK",
    "VENDOR_CREDIT",
    "JOURNAL_ENTRY",
    "DEPOSIT",
    "BANK_ADJUSTMENT",
    "MGMT_FEE",
    "OWNER_DRAW",
    "TRANSFER",
    "NSF",
    "REVERSAL",
    "REFUND_NEGATIVE_DIAGNOSTIC",
    "OWNER_CONTRIBUTION",
}


# ------------------------------------------------------------
# Exceptions
# ------------------------------------------------------------

class PostingError(Exception):
    """Raised when a posting fails validation. Callers can
    catch this and turn it into an HTTP 400."""
    pass


def _norm_role(role) -> str:
    value = getattr(role, "value", role)
    return str(value or "").upper()

def _gl_account_restrictions_enabled(db: Session, *, organization_id: int) -> bool:
    if not release_gate_allows_org(db, gate_key=GL_ACCOUNT_PERMISSIONS_GATE, organization_id=organization_id):
        return False
    setting = db.query(OrganizationFeatureSetting).filter(
        OrganizationFeatureSetting.organization_id == organization_id,
        OrganizationFeatureSetting.feature_key == GL_ACCOUNT_PERMISSIONS_GATE,
    ).first()
    return setting is None or bool(setting.enabled)

def _enforce_gl_account_posting_restrictions(
    db: Session, *, organization_id: int, account_ids: set[int],
    created_by: User, accounts: list[GLAccount],
) -> None:
    if not account_ids or created_by is None or not _gl_account_restrictions_enabled(db, organization_id=organization_id):
        return
    role = _norm_role(created_by.role)
    if not role:
        return
    denied_ids = {row.gl_account_id for row in db.query(GLAccountPostingRestriction).filter(
        GLAccountPostingRestriction.organization_id == organization_id,
        GLAccountPostingRestriction.role == role,
        GLAccountPostingRestriction.gl_account_id.in_(account_ids),
    ).all()}
    if denied_ids:
        number_by_id = {account.id: account.gl_number for account in accounts}
        denied_numbers = sorted(number_by_id.get(account_id, str(account_id)) for account_id in denied_ids)
        raise PostingError(f"Role {role} is not allowed to post to GL account(s): {', '.join(denied_numbers)}")

# ------------------------------------------------------------
# The one public function
# ------------------------------------------------------------

def post_transaction(
    db: Session,
    *,
    organization_id: int,
    transaction_date: date,
    transaction_type: str,
    memo: Optional[str],
    lines: List[PostingLine],
    created_by: User,
    reference_number: Optional[str] = None,
    source_type: Optional[str] = None,
    source_id: Optional[int] = None,
    reversal_of_id: Optional[int] = None,
    commit: bool = True,
    write_audit: bool = True,
) -> GLTransaction:
    """Post a balanced transaction to the General Ledger.

    Raises PostingError on any validation failure. By default, commits
    and audits the posting. Compound financial workflows may pass
    commit=False and write_audit=False so related state changes can
    commit atomically in the caller.

    Rules enforced here (in order):
      1. transaction_type must be valid
      2. At least 2 lines
      3. Each line: exactly one of debit/credit is > 0
      4. Sum of debits == Sum of credits (nonzero)
      5. All gl_account_ids belong to organization_id
      6. All property_ids belong to organization_id
      7. All unit_ids belong to the given property
      8. created_by is the current user (caller responsibility)
    """
    # -----------------------------------------------------------------
    # 0. Closed accounting period
    # -----------------------------------------------------------------
    organization = db.get(Organization, organization_id)
    if organization is None:
        raise PostingError(f"Organization {organization_id} was not found.")

    locked_through = organization.locked_through_date
    if locked_through is not None and transaction_date <= locked_through:
        raise PostingError(
            f"Accounting period is locked through {locked_through.isoformat()}; "
            f"cannot post transaction dated {transaction_date.isoformat()}."
        )

    # -----------------------------------------------------------------
    # 1. Validate transaction type
    # -----------------------------------------------------------------
    ttype = (transaction_type or "").strip().upper()
    if ttype not in VALID_TRANSACTION_TYPES:
        raise PostingError(
            f"Unknown transaction_type '{transaction_type}'. "
            f"Valid types: {', '.join(sorted(VALID_TRANSACTION_TYPES))}"
        )

    # -----------------------------------------------------------------
    # 2. At least two lines
    # -----------------------------------------------------------------
    if not lines or len(lines) < 2:
        raise PostingError("A transaction must have at least two lines.")

    # -----------------------------------------------------------------
    # 3. Per-line validation + totals
    # -----------------------------------------------------------------
    total_debit = Decimal("0")
    total_credit = Decimal("0")

    for i, line in enumerate(lines):
        d = Decimal(line.debit or 0)
        c = Decimal(line.credit or 0)

        if d < 0 or c < 0:
            raise PostingError(
                f"Line {i + 1}: debit and credit must be >= 0."
            )
        if d == 0 and c == 0:
            raise PostingError(
                f"Line {i + 1}: exactly one of debit or credit must be "
                f"greater than zero."
            )
        if d > 0 and c > 0:
            raise PostingError(
                f"Line {i + 1}: cannot have both debit and credit on the "
                f"same line."
            )

        total_debit += d
        total_credit += c

    # -----------------------------------------------------------------
    # 4. Balance check
    # -----------------------------------------------------------------
    if total_debit == 0 or total_credit == 0:
        raise PostingError("Transaction total is zero. Nothing to post.")

    # Allow a tiny rounding tolerance (e.g. 0.01) to protect
    # against float weirdness when callers pass floats.
    if abs(total_debit - total_credit) > Decimal("0.01"):
        raise PostingError(
            f"Transaction does not balance. "
            f"Total debits = {total_debit}, total credits = {total_credit}."
        )

    # -----------------------------------------------------------------
    # 5. GL accounts belong to this org
    # -----------------------------------------------------------------
    account_ids = {line.gl_account_id for line in lines}
    accounts = (
        db.query(GLAccount)
        .filter(
            GLAccount.organization_id == organization_id,
            GLAccount.id.in_(account_ids),
        )
        .all()
    )
    found_ids = {a.id for a in accounts}
    missing = account_ids - found_ids
    if missing:
        raise PostingError(
            f"GL account(s) not found in your organization: {sorted(missing)}"
        )

    inactive = [a.id for a in accounts if not a.is_active]
    if inactive:
        raise PostingError(
            f"Cannot post to inactive GL account(s): {sorted(inactive)}"
        )

    _enforce_gl_account_posting_restrictions(
        db,
        organization_id=organization_id,
        account_ids=account_ids,
        created_by=created_by,
        accounts=accounts,
    )

    # -----------------------------------------------------------------
    # 6. Properties belong to this org (if given)
    # -----------------------------------------------------------------
    property_ids = {
        line.property_id for line in lines if line.property_id is not None
    }
    if property_ids:
        props = (
            db.query(Property)
            .filter(
                Property.organization_id == organization_id,
                Property.id.in_(property_ids),
            )
            .all()
        )
        found_props = {p.id for p in props}
        missing_props = property_ids - found_props
        if missing_props:
            raise PostingError(
                f"Property(ies) not found in your organization: "
                f"{sorted(missing_props)}"
            )

    # -----------------------------------------------------------------
    # 7. Units belong to the given property (if given)
    # -----------------------------------------------------------------
    unit_ids = {line.unit_id for line in lines if line.unit_id is not None}
    if unit_ids:
        units = db.query(Unit).filter(Unit.id.in_(unit_ids)).all()
        unit_by_id = {u.id: u for u in units}
        missing_units = unit_ids - set(unit_by_id.keys())
        if missing_units:
            raise PostingError(
                f"Unit(s) not found: {sorted(missing_units)}"
            )
        for line in lines:
            if line.unit_id is None:
                continue
            u = unit_by_id[line.unit_id]
            if line.property_id is None or u.property_id != line.property_id:
                raise PostingError(
                    f"Line for unit {line.unit_id} has mismatched "
                    f"property_id (expected {u.property_id}, "
                    f"got {line.property_id})."
                )

    # -----------------------------------------------------------------
    # 8. Write parent + children in one transaction
    # -----------------------------------------------------------------
    try:
        txn = GLTransaction(
            organization_id=organization_id,
            transaction_date=transaction_date,
            posted_at=datetime.utcnow(),
            transaction_type=ttype,
            reference_number=reference_number,
            memo=memo,
            source_type=source_type,
            source_id=source_id,
            created_by_id=created_by.id if created_by else None,
            is_reversed=False,
            reversal_of_id=reversal_of_id,
        )
        db.add(txn)
        db.flush()  # assigns txn.id

        for line in lines:
            entry = GLEntry(
                organization_id=organization_id,
                transaction_id=txn.id,
                gl_account_id=line.gl_account_id,
                property_id=line.property_id,
                unit_id=line.unit_id,
                owner_id=line.owner_id,
                description=line.description,
                debit=Decimal(line.debit or 0),
                credit=Decimal(line.credit or 0),
            )
            db.add(entry)

        if commit:
            db.commit()
            db.refresh(txn)
        else:
            # Keep this posting inside the caller's transaction. txn.id is
            # already assigned by flush(), but nothing is durable yet.
            db.flush()
    except Exception:
        db.rollback()
        raise

    # -----------------------------------------------------------------
    # 9. Audit log (best-effort — never breaks the post)
    # -----------------------------------------------------------------
    if commit and write_audit:
        try:
            log_action(
                db=db,
                user=created_by,
                entity_type="gl_transaction",
                entity_id=txn.id,
                action="post",
                field_name=ttype,
                old_value=None,
                new_value=f"{total_debit} / {total_credit}",
            )
        except Exception:
            # audit failures must never undo a successful posting
            pass

    return txn


# ------------------------------------------------------------
# Reversal helper — thin wrapper around post_transaction
# ------------------------------------------------------------

def reverse_transaction(
    db: Session,
    *,
    original: GLTransaction,
    reversal_date: date,
    created_by: User,
    memo: Optional[str] = None,
) -> GLTransaction:
    """Reverse a posted transaction.

    Creates a new transaction with every line flipped
    (debit <-> credit). Marks the original is_reversed=True.
    The two transactions net to zero.

    owner_id is carried forward on each flipped line so the
    owner sub-ledger nets to zero too.
    """
    if original.is_reversed:
        raise PostingError("This transaction has already been reversed.")

    # Build flipped lines
    flipped: List[PostingLine] = []
    for e in original.entries:
        flipped.append(
            PostingLine(
                gl_account_id=e.gl_account_id,
                property_id=e.property_id,
                unit_id=e.unit_id,
                owner_id=e.owner_id,
                description=f"Reversal: {e.description or ''}".strip(),
                debit=Decimal(e.credit or 0),
                credit=Decimal(e.debit or 0),
            )
        )

    # The reversal posting and original-state flip are one financial
    # transaction. A failure must leave neither half durable.
    try:
        reversal = post_transaction(
            db=db,
            organization_id=original.organization_id,
            transaction_date=reversal_date,
            transaction_type="REVERSAL",
            memo=memo or f"Reversal of transaction #{original.id}",
            lines=flipped,
            created_by=created_by,
            reference_number=original.reference_number,
            source_type=original.source_type,
            source_id=original.source_id,
            reversal_of_id=original.id,
            commit=False,
            write_audit=False,
        )
        original.is_reversed = True
        db.commit()
        db.refresh(reversal)
        db.refresh(original)
    except Exception:
        db.rollback()
        raise

    # Audit only after the financial transaction is durable.
    try:
        log_action(
            db=db,
            user=created_by,
            entity_type="gl_transaction",
            entity_id=reversal.id,
            action="post",
            field_name="REVERSAL",
            old_value=None,
            new_value=f"reversal_of={original.id}",
        )
    except Exception:
        pass

    return reversal