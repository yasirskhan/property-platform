"""Accounting-safe check issue/void workflows."""
from __future__ import annotations
from datetime import date, datetime
from decimal import Decimal
from sqlalchemy.orm import Session, joinedload
from app.models.bank_account import BankAccount
from app.models.bill import Bill
from app.models.check import Check, CheckBillAllocation
from app.models.gl_transaction import GLTransaction
from app.models.user import User
from app.schemas.check import CheckIssueIn
from app.schemas.gl_transaction import PostingLine
from app.services.gl_posting import PostingError, post_transaction
CENT=Decimal("0.01")
def _money(v)->Decimal: return Decimal(v or 0).quantize(CENT)

def issue_check(db:Session,*,organization_id:int,payload:CheckIssueIn,created_by:User)->Check:
    bank=db.query(BankAccount).filter(BankAccount.id==payload.bank_account_id,BankAccount.organization_id==organization_id,BankAccount.is_active.is_(True)).first()
    if bank is None: raise PostingError("Active bank account not found in your organization.")
    ids=[x.bill_id for x in payload.allocations]
    if len(set(ids))!=len(ids): raise PostingError("Each bill may appear only once on a check.")
    bills=db.query(Bill).filter(Bill.organization_id==organization_id,Bill.id.in_(ids),Bill.is_active.is_(True)).all(); by_id={b.id:b for b in bills}
    if set(ids)!=set(by_id): raise PostingError("One or more bills were not found in your organization.")
    if len({b.payee_name.strip().casefold() for b in bills})!=1: raise PostingError("One check can only pay bills for the same payee.")
    posting=[]; total=Decimal("0")
    for alloc in payload.allocations:
        bill=by_id[alloc.bill_id]
        if bill.is_reversed or bill.status not in {"UNPAID","PARTIAL"}: raise PostingError(f"Bill #{bill.id} is not payable.")
        outstanding=_money(bill.amount)-_money(bill.amount_paid); amount=_money(alloc.amount)
        if amount<=0 or amount>outstanding: raise PostingError(f"Allocation for bill #{bill.id} exceeds its outstanding balance.")
        total+=amount
        posting.append(PostingLine(gl_account_id=bill.payable_gl_account_id,property_id=bill.property_id,unit_id=bill.unit_id,owner_id=bill.owner_id,description=f"Check payment: {bill.payee_name}",debit=amount,credit=Decimal("0")))
    posting.append(PostingLine(gl_account_id=bank.gl_account_id,description=f"Check payment: {bills[0].payee_name}",debit=Decimal("0"),credit=total))
    try:
        row=Check(organization_id=organization_id,bank_account_id=bank.id,check_number=payload.check_number or None,check_date=payload.check_date,payee_name=bills[0].payee_name,memo=payload.memo,amount=total,status="ISSUED",created_by_id=created_by.id)
        db.add(row); db.flush()
        if not row.check_number: row.check_number=f"CHK-{row.id:06d}"
        for alloc in payload.allocations: db.add(CheckBillAllocation(check_id=row.id,bill_id=alloc.bill_id,amount=_money(alloc.amount)))
        txn=post_transaction(db=db,organization_id=organization_id,transaction_date=payload.check_date,transaction_type="CHECK",memo=payload.memo or f"Check {row.check_number}",lines=posting,created_by=created_by,reference_number=row.check_number,source_type="check",source_id=row.id,commit=False,write_audit=False)
        row.gl_transaction_id=txn.id
        for alloc in payload.allocations:
            bill=by_id[alloc.bill_id]; bill.amount_paid=_money(bill.amount_paid)+_money(alloc.amount); bill.status="PAID" if _money(bill.amount_paid)>=_money(bill.amount) else "PARTIAL"; bill.cash_gl_account_id=bank.gl_account_id
        db.commit(); db.refresh(row); return row
    except Exception as exc:
        db.rollback()
        if isinstance(exc,PostingError): raise
        raise PostingError(f"Failed to issue check: {exc}")

def void_check(db:Session,*,check:Check,void_date:date,reason:str|None,created_by:User)->Check:
    if check.status!="ISSUED": raise PostingError("Only an issued check can be voided.")
    txn=db.query(GLTransaction).options(joinedload(GLTransaction.entries)).filter(GLTransaction.id==check.gl_transaction_id,GLTransaction.organization_id==check.organization_id).first()
    if txn is None or txn.is_reversed: raise PostingError("Underlying check GL transaction is unavailable or already reversed.")
    flipped=[PostingLine(gl_account_id=e.gl_account_id,property_id=e.property_id,unit_id=e.unit_id,owner_id=e.owner_id,description=f"Void check: {e.description or ''}".strip(),debit=Decimal(e.credit or 0),credit=Decimal(e.debit or 0)) for e in txn.entries]
    try:
        reversal=post_transaction(db=db,organization_id=check.organization_id,transaction_date=void_date,transaction_type="REVERSAL",memo=reason or f"Void check {check.check_number}",lines=flipped,created_by=created_by,reference_number=check.check_number,source_type="check_void",source_id=check.id,reversal_of_id=txn.id,commit=False,write_audit=False)
        txn.is_reversed=True
        for alloc in db.query(CheckBillAllocation).options(joinedload(CheckBillAllocation.bill)).filter(CheckBillAllocation.check_id==check.id).all():
            bill=alloc.bill; bill.amount_paid=max(_money(bill.amount_paid)-_money(alloc.amount),Decimal("0.00")); bill.status="UNPAID" if bill.amount_paid==0 else ("PAID" if _money(bill.amount_paid)>=_money(bill.amount) else "PARTIAL")
        check.status="VOID"; check.void_gl_transaction_id=reversal.id; check.void_reason=reason; check.voided_at=datetime.utcnow(); check.voided_by_id=created_by.id
        db.commit(); db.refresh(check); return check
    except Exception as exc:
        db.rollback()
        if isinstance(exc,PostingError): raise
        raise PostingError(f"Failed to void check: {exc}")
