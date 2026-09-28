"""HOA reserve book tracing through the existing immutable GL, never new posts."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.bank_account import BankAccount
from app.models.gl_account import GLAccount
from app.models.gl_entry import GLEntry
from app.models.gl_transaction import GLTransaction
from app.models.hoa_reserve_account import HOAReserveAccount
from app.models.user import User, UserRole
from app.routers.auth import get_current_user
from app.routers.hoa_assessments import _scope
from app.schemas.hoa_reserve_account import HOAReserveIn, HOAReserveOut, HOAReserveBookOut, HOAReserveOptionOut
from app.services.audit import append_audit_log
from app.services.cash_flow import _account_totals
from app.services.menu_resolver import permission_allows_user

router = APIRouter(prefix="/api/hoa/associations", tags=["HOA reserve GL book readiness"])
_ACCOUNTING_PERMISSIONS = (
    "ACCOUNTING.GL_ACCOUNTS", "ACCOUNTING.BANK_ACCOUNTS", "REPORTING.ALL",
)


def _scope_with_accounting(
    db: Session, *, actor: User, association_id: int, property_id: int,
    write: bool,
) -> tuple[int, object]:
    org_id, assoc = _scope(
        db, actor=actor, association_id=association_id,
        property_id=property_id, write=write,
    )
    if any(not permission_allows_user(db, user=actor, menu_key=key)
           for key in _ACCOUNTING_PERMISSIONS):
        raise HTTPException(status_code=403, detail="Reserve accounting access required.")
    return org_id, assoc


def _reserve(db: Session, *, org_id: int, association_id: int, property_id: int):
    return db.query(HOAReserveAccount).filter(
        HOAReserveAccount.organization_id == org_id,
        HOAReserveAccount.association_id == association_id,
        HOAReserveAccount.property_id == property_id,
    ).first()


def _accounts(db: Session, *, org_id: int, row: HOAReserveAccount):
    gl = db.query(GLAccount).filter(
        GLAccount.id == row.gl_account_id,
        GLAccount.organization_id == org_id,
        GLAccount.account_type == "ASSET",
        GLAccount.include_on_cash_flow.is_(True),
    ).first()
    if gl is None:
        raise HTTPException(status_code=409, detail="Reserve GL mapping requires review.")
    bank = None
    if row.bank_account_id is not None:
        bank = db.query(BankAccount).filter(
            BankAccount.id == row.bank_account_id,
            BankAccount.organization_id == org_id,
            BankAccount.gl_account_id == gl.id,
            BankAccount.account_type.in_(("OPERATING", "ESCROW")),
        ).first()
        if bank is None:
            raise HTTPException(status_code=409, detail="Reserve bank-to-GL mapping requires review.")
    return gl, bank


def _out(row: HOAReserveAccount, gl: GLAccount, bank: BankAccount | None) -> HOAReserveOut:
    healthy = gl.is_active and gl.deleted_at is None and (
        bank is None or (bank.is_active and bank.deleted_at is None)
    )
    status = (
        "BOOK_ASSET_NO_BANK_MAPPED" if bank is None and healthy
        else "RECORDED_BANK_GL_NOT_RECONCILED" if healthy
        else "ARCHIVED_MAPPING_NEEDS_REVIEW"
    )
    return HOAReserveOut(
        id=row.id, association_id=row.association_id, property_id=row.property_id,
        gl_account_id=gl.id, gl_number=gl.gl_number, gl_name=gl.name,
        bank_account_id=bank.id if bank else None,
        bank_display_name=bank.name if bank else None,
        mapping_status=status,
    )


@router.get("/{association_id}/reserve-account", response_model=HOAReserveOut | None)
def get_reserve(
    association_id: int, response: Response,
    property_id: int = Query(ge=1),
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    org_id, assoc = _scope_with_accounting(
        db, actor=current_user, association_id=association_id,
        property_id=property_id, write=False,
    )
    row = _reserve(db, org_id=org_id, association_id=assoc.id, property_id=property_id)
    response.headers["Cache-Control"] = "no-store"
    if row is None or not row.is_active:
        return None
    gl, bank = _accounts(db, org_id=org_id, row=row)
    return _out(row, gl, bank)


@router.put("/{association_id}/reserve-account", response_model=HOAReserveOut)
def put_reserve(
    association_id: int, payload: HOAReserveIn,
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    org_id, assoc = _scope_with_accounting(
        db, actor=current_user, association_id=association_id,
        property_id=payload.property_id, write=True,
    )
    gl = db.query(GLAccount).filter(
        GLAccount.id == payload.gl_account_id,
        GLAccount.organization_id == org_id,
        GLAccount.account_type == "ASSET",
        GLAccount.include_on_cash_flow.is_(True),
        GLAccount.is_active.is_(True),
        GLAccount.deleted_at.is_(None),
    ).first()
    if gl is None:
        raise HTTPException(status_code=404, detail="Active cash-like ASSET GL not found.")
    bank = None
    if payload.bank_account_id is not None:
        bank = db.query(BankAccount).filter(
            BankAccount.id == payload.bank_account_id,
            BankAccount.organization_id == org_id,
            BankAccount.gl_account_id == gl.id,
            BankAccount.account_type.in_(("OPERATING", "ESCROW")),
            BankAccount.is_active.is_(True),
            BankAccount.deleted_at.is_(None),
        ).first()
        if bank is None:
            raise HTTPException(status_code=404, detail="Bank-to-GL mapping not found.")
    row = db.query(HOAReserveAccount).filter(
        HOAReserveAccount.organization_id == org_id,
        HOAReserveAccount.association_id == assoc.id,
        HOAReserveAccount.property_id == payload.property_id,
    ).with_for_update().first()
    if row is not None and row.gl_account_id != gl.id:
        raise HTTPException(status_code=409, detail="Changing historical reserve GL requires separate accounting review.")
    if row is None:
        row = HOAReserveAccount(
            organization_id=org_id, association_id=assoc.id,
            property_id=payload.property_id, gl_account_id=gl.id,
            created_by_id=current_user.id,
        )
        db.add(row)
    row.bank_account_id = bank.id if bank else None
    row.is_active = True
    row.updated_by_id = current_user.id
    try:
        db.flush()
        append_audit_log(
            db, organization_id=org_id, user_id=current_user.id,
            entity_type="hoa_reserve_account", entity_id=row.id,
            action="staff_reserve_mapping_recorded",
            new_value={"association_id": assoc.id, "property_id": row.property_id,
                       "gl_account_id": gl.id, "bank_mapping_present": bank is not None},
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Reserve GL already assigned or mapping changed concurrently.") from exc
    db.refresh(row)
    return _out(row, gl, bank)


@router.get("/{association_id}/reserve-book", response_model=HOAReserveBookOut)
def reserve_book(
    association_id: int, response: Response,
    property_id: int = Query(ge=1), as_of: date = Query(),
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    org_id, assoc = _scope_with_accounting(
        db, actor=current_user, association_id=association_id,
        property_id=property_id, write=False,
    )
    # An org-wide GL balance can contain movements from other properties.
    # Managers assigned to just one property must not see these figures.
    if current_user.role not in {UserRole.ADMIN, UserRole.OWNER}:
        raise HTTPException(status_code=403, detail="Organization-wide reserve book access required.")
    row = _reserve(db, org_id=org_id, association_id=assoc.id, property_id=property_id)
    if row is None or not row.is_active:
        raise HTTPException(status_code=404, detail="Reserve GL mapping not found.")
    gl, bank = _accounts(db, org_id=org_id, row=row)
    totals = _account_totals(
        db, organization_id=org_id, gl_ids=(gl.id,), date_to=as_of,
    )
    debit, credit = totals.get(gl.id, (Decimal("0"), Decimal("0")))
    account_total = debit - credit
    common = db.query(
        func.coalesce(func.sum(GLEntry.debit), 0),
        func.coalesce(func.sum(GLEntry.credit), 0),
    ).join(GLTransaction, GLTransaction.id == GLEntry.transaction_id).filter(
        GLEntry.organization_id == org_id,
        GLTransaction.organization_id == org_id,
        GLEntry.gl_account_id == gl.id,
        GLTransaction.transaction_date <= as_of,
    )
    tagged_debit, tagged_credit = common.filter(
        GLEntry.property_id == property_id,
    ).one()
    other_gross = db.query(
        func.coalesce(func.sum(GLEntry.debit + GLEntry.credit), 0),
    ).join(GLTransaction, GLTransaction.id == GLEntry.transaction_id).filter(
        GLEntry.organization_id == org_id,
        GLTransaction.organization_id == org_id,
        GLEntry.gl_account_id == gl.id,
        GLTransaction.transaction_date <= as_of,
        or_(GLEntry.property_id.is_(None), GLEntry.property_id != property_id),
    ).scalar()
    tagged = Decimal(tagged_debit or 0) - Decimal(tagged_credit or 0)
    response.headers["Cache-Control"] = "no-store"
    return HOAReserveBookOut(
        **_out(row, gl, bank).model_dump(), as_of=as_of,
        account_wide_book_balance=account_total,
        property_tagged_book_balance=tagged,
        unallocated_or_other_property_balance=account_total - tagged,
        attribution_status=(
            "OTHER_OR_UNTAGGED_POSTINGS_PRESENT"
            if Decimal(other_gross or 0) != 0
            else "ALL_GROSS_ACTIVITY_PROPERTY_TAGGED"
        ),
    )


@router.get("/{association_id}/reserve-options", response_model=list[HOAReserveOptionOut])
def reserve_options(
    association_id: int, response: Response, property_id: int = Query(ge=1),
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    """Only safe display fields. Never send routing/account number or ACH data."""
    org_id, assoc = _scope_with_accounting(
        db, actor=current_user, association_id=association_id,
        property_id=property_id, write=True,
    )
    records = db.query(GLAccount).filter(
        GLAccount.organization_id == org_id,
        GLAccount.account_type == "ASSET",
        GLAccount.include_on_cash_flow.is_(True),
        GLAccount.is_active.is_(True),
        GLAccount.deleted_at.is_(None),
    ).order_by(GLAccount.gl_number, GLAccount.id).limit(501).all()
    if len(records) > 500:
        raise HTTPException(status_code=422, detail="Too many cash-like accounts to select.")
    current = _reserve(db, org_id=org_id, association_id=assoc.id, property_id=property_id)
    reserved = db.query(HOAReserveAccount.gl_account_id).filter(
        HOAReserveAccount.organization_id == org_id,
    )
    if current is not None:
        reserved = reserved.filter(HOAReserveAccount.id != current.id)
    in_use = {int(gl_id) for (gl_id,) in reserved.all()}
    bank_records = db.query(BankAccount).filter(
        BankAccount.organization_id == org_id,
        BankAccount.is_active.is_(True),
        BankAccount.deleted_at.is_(None),
    ).all()
    banks_by_gl = {
        bank.gl_account_id: bank for bank in bank_records
        if bank.account_type in ("OPERATING", "ESCROW")
    }
    response.headers["Cache-Control"] = "no-store"
    return [
        HOAReserveOptionOut(
            gl_account_id=gl.id, gl_number=gl.gl_number, gl_name=gl.name,
            bank_account_id=banks_by_gl[gl.id].id if gl.id in banks_by_gl else None,
            bank_display_name=banks_by_gl[gl.id].name if gl.id in banks_by_gl else None,
        )
        for gl in records if gl.id not in in_use
        and (current is None or current.gl_account_id == gl.id)
    ]
