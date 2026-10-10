from __future__ import annotations
from datetime import date
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload
from app.core.database import get_db
from app.models.bank_account import BankAccount
from app.models.bill import Bill
from app.models.check import Check, CheckBillAllocation
from app.models.user import User
from app.routers.auth import get_current_user
from app.schemas.check import CheckBankAccountOut, CheckIssueIn, CheckListOut, CheckMemoIn, CheckOut, CheckAllocationOut, CheckVoidIn, EligibleBillOut
from app.services.checks import issue_check, void_check
from app.services.customer_features import resolve_customer_features
from app.services.gl_posting import PostingError
router=APIRouter(prefix="/api/accounting/checks",tags=["Checks"])
def _org(user:User)->int:
    if user.organization_id is None: raise HTTPException(400,"User has no organization.")
    return user.organization_id
def _require(db:Session,user:User,key:str="release.accounting.write_checks")->int:
    org=_org(user); d=next((x for x in resolve_customer_features(db,user=user) if x.key==key),None)
    if d is None or not d.allowed: raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,detail="Check writing is not enabled.")
    return org
def _query(db:Session,org:int): return db.query(Check).options(joinedload(Check.bank_account),joinedload(Check.allocations).joinedload(CheckBillAllocation.bill)).filter(Check.organization_id==org)
def _out(r:Check)->CheckOut:
    return CheckOut(id=r.id,organization_id=r.organization_id,bank_account_id=r.bank_account_id,bank_account_name=r.bank_account.name if r.bank_account else None,check_number=r.check_number,check_date=r.check_date,payee_name=r.payee_name,memo=r.memo,amount=r.amount,status=r.status,gl_transaction_id=r.gl_transaction_id,void_gl_transaction_id=r.void_gl_transaction_id,void_reason=r.void_reason,voided_at=r.voided_at,created_by_id=r.created_by_id,created_at=r.created_at,updated_at=r.updated_at,allocations=[CheckAllocationOut(id=a.id,bill_id=a.bill_id,bill_number=a.bill.bill_number if a.bill else None,amount=a.amount) for a in r.allocations])
@router.get("/eligible-bills",response_model=list[EligibleBillOut])
def eligible_bills(payee_name:str|None=Query(None),due_before:date|None=Query(None),db:Session=Depends(get_db),current_user:User=Depends(get_current_user)):
    org=_require(db,current_user); q=db.query(Bill).filter(Bill.organization_id==org,Bill.is_active.is_(True),Bill.is_reversed.is_(False),Bill.status.in_(["UNPAID","PARTIAL"]))
    if payee_name:q=q.filter(Bill.payee_name.ilike(f"%{payee_name}%"))
    if due_before:q=q.filter(Bill.due_date<=due_before)
    return [EligibleBillOut(id=b.id,bill_number=b.bill_number,payee_name=b.payee_name,bill_date=b.bill_date,due_date=b.due_date,amount=b.amount,amount_paid=b.amount_paid,outstanding=Decimal(b.amount)-Decimal(b.amount_paid),property_id=b.property_id) for b in q.order_by(Bill.payee_name.asc(),Bill.due_date.asc(),Bill.id.asc()).all()]
@router.get("/bank-accounts",response_model=list[CheckBankAccountOut])
def bank_accounts(db:Session=Depends(get_db),current_user:User=Depends(get_current_user)):
    org=_require(db,current_user); return [CheckBankAccountOut(id=x.id,name=x.name,account_type=x.account_type,gl_account_id=x.gl_account_id) for x in db.query(BankAccount).filter(BankAccount.organization_id==org,BankAccount.is_active.is_(True)).order_by(BankAccount.name).all()]
@router.get("",response_model=CheckListOut)
def list_checks(date_from:date|None=Query(None),date_to:date|None=Query(None),status_filter:str|None=Query(None,alias="status"),db:Session=Depends(get_db),current_user:User=Depends(get_current_user)):
    org=_require(db,current_user); q=_query(db,org)
    if date_from:q=q.filter(Check.check_date>=date_from)
    if date_to:q=q.filter(Check.check_date<=date_to)
    if status_filter:q=q.filter(Check.status==status_filter.upper())
    return CheckListOut(items=[_out(x) for x in q.order_by(Check.check_date.desc(),Check.id.desc()).all()],total=q.count())
@router.post("",response_model=CheckOut,status_code=201)
def create_check(payload:CheckIssueIn,db:Session=Depends(get_db),current_user:User=Depends(get_current_user)):
    org=_require(db,current_user)
    try:r=issue_check(db,organization_id=org,payload=payload,created_by=current_user)
    except PostingError as exc:raise HTTPException(400,str(exc))
    return _out(_query(db,org).filter(Check.id==r.id).one())
@router.get("/{check_id}",response_model=CheckOut)
def get_check(check_id:int,db:Session=Depends(get_db),current_user:User=Depends(get_current_user)):
    org=_require(db,current_user); r=_query(db,org).filter(Check.id==check_id).first()
    if r is None:raise HTTPException(404,"Check not found.")
    return _out(r)
@router.patch("/{check_id}/memo",response_model=CheckOut)
def update_memo(check_id:int,payload:CheckMemoIn,db:Session=Depends(get_db),current_user:User=Depends(get_current_user)):
    org=_require(db,current_user); r=_query(db,org).filter(Check.id==check_id).first()
    if r is None:raise HTTPException(404,"Check not found.")
    r.memo=payload.memo;db.commit()
    return _out(_query(db,org).filter(Check.id==r.id).one())
@router.post("/{check_id}/void",response_model=CheckOut)
def void_check_endpoint(check_id:int,payload:CheckVoidIn,db:Session=Depends(get_db),current_user:User=Depends(get_current_user)):
    org=_require(db,current_user); r=_query(db,org).filter(Check.id==check_id).first()
    if r is None:raise HTTPException(404,"Check not found.")
    try:void_check(db,check=r,void_date=payload.void_date,reason=payload.reason,created_by=current_user)
    except PostingError as exc:raise HTTPException(400,str(exc))
    return _out(_query(db,org).filter(Check.id==r.id).one())
@router.get("/{check_id}/print",response_model=CheckOut)
def print_check(check_id:int,db:Session=Depends(get_db),current_user:User=Depends(get_current_user)):
    org=_require(db,current_user,"release.accounting.check_printing");r=_query(db,org).filter(Check.id==check_id).first()
    if r is None:raise HTTPException(404,"Check not found.")
    return _out(r)
