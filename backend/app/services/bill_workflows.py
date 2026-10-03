"""Recurring bill scheduling, manual posting, and vendor-credit accounting."""
from __future__ import annotations
from datetime import date
from decimal import Decimal
from sqlalchemy.orm import Session
from app.models.bill import Bill
from app.models.bill_workflow import RecurringBill, RecurringBillLine, VendorCredit, VendorCreditLine
from app.models.gl_account import GLAccount
from app.models.organization_feature_setting import OrganizationFeatureSetting
from app.models.property import Property, Unit
from app.models.user import User, UserRole
from app.schemas.bill import BillCreateIn, BillLineIn
from app.schemas.bill_workflow import RecurringBillCreateIn, VendorCreditCreateIn
from app.schemas.gl_transaction import PostingLine
from app.services.bill_posting import _default_payable_account, _get_account, post_bill
from app.services.entitlement_resolver import entitlement_allows_feature
from app.services.gl_posting import PostingError, post_transaction
from app.services.recurring_journal_entries import first_monthly_date_on_or_after, monthly_date, next_monthly_date
from app.services.release_gate_resolver import release_gate_allows_org

RECURRING_BILLS_GATE="release.accounting.bills.recurring"
MANUAL_POST_GATE="release.accounting.bills.manual_post"
VENDOR_CREDITS_GATE="release.accounting.vendor_credits"

def _feature_enabled(db:Session,*,organization_id:int,gate_key:str,entitlement_key:str)->bool:
    if not release_gate_allows_org(db,gate_key=gate_key,organization_id=organization_id): return False
    if not entitlement_allows_feature(db,organization_id=organization_id,feature_key=entitlement_key): return False
    setting=db.query(OrganizationFeatureSetting).filter(OrganizationFeatureSetting.organization_id==organization_id,OrganizationFeatureSetting.feature_key==gate_key).first()
    return setting is None or bool(setting.enabled)
def recurring_bills_enabled_for_org(db:Session,*,organization_id:int)->bool: return _feature_enabled(db,organization_id=organization_id,gate_key=RECURRING_BILLS_GATE,entitlement_key="recurring_bills")
def manual_bill_post_enabled_for_org(db:Session,*,organization_id:int)->bool: return _feature_enabled(db,organization_id=organization_id,gate_key=MANUAL_POST_GATE,entitlement_key="manual_bill_posting")
def vendor_credits_enabled_for_org(db:Session,*,organization_id:int)->bool: return _feature_enabled(db,organization_id=organization_id,gate_key=VENDOR_CREDITS_GATE,entitlement_key="vendor_credits")

def _validate_scope(db:Session,*,organization_id:int,lines:list[BillLineIn],property_id:int|None=None,unit_id:int|None=None,owner_id:int|None=None)->None:
    for line in lines: _get_account(db,organization_id,line.gl_account_id)
    pids={p for p in [property_id,*[x.property_id for x in lines]] if p is not None}
    if pids:
        found={r.id for r in db.query(Property).filter(Property.organization_id==organization_id,Property.id.in_(pids)).all()}
        if found!=pids: raise PostingError("One or more properties are outside this organization.")
    uids={u for u in [unit_id,*[x.unit_id for x in lines]] if u is not None}
    if uids:
        units={r.id:r for r in db.query(Unit).filter(Unit.id.in_(uids)).all()}
        if set(units)!=uids: raise PostingError("One or more units do not exist.")
        for line in lines:
            su=line.unit_id or unit_id; sp=line.property_id or property_id
            if su is not None and (sp is None or units[su].property_id!=sp): raise PostingError("A bill unit must belong to its selected property.")
    if owner_id is not None:
        owner=db.query(User).filter(User.id==owner_id,User.organization_id==organization_id).first()
        if owner is None: raise PostingError("Owner is outside this organization.")

def create_recurring_bill(db:Session,*,organization_id:int,payload:RecurringBillCreateIn,created_by:User)->RecurringBill:
    _validate_scope(db,organization_id=organization_id,lines=payload.lines,property_id=payload.property_id,unit_id=payload.unit_id,owner_id=payload.owner_id)
    payable=_get_account(db,organization_id,payload.payable_gl_account_id) if payload.payable_gl_account_id is not None else _default_payable_account(db,organization_id)
    if payload.cash_gl_account_id is not None: _get_account(db,organization_id,payload.cash_gl_account_id)
    next_post=first_monthly_date_on_or_after(payload.start_date,payload.bill_day)
    if payload.end_date is not None and next_post>payload.end_date: raise PostingError("The recurring schedule has no posting date inside its date range.")
    row=RecurringBill(organization_id=organization_id,entry_type=payload.entry_type,payee_name=payload.payee_name.strip(),payee_user_id=payload.payee_user_id,start_date=payload.start_date,end_date=payload.end_date,bill_day=payload.bill_day,due_day=payload.due_day,post_code=payload.post_code.strip() if payload.post_code else None,next_post_date=next_post,reference_number=payload.reference_number,remarks=payload.remarks,payable_gl_account_id=payable.id,cash_gl_account_id=payload.cash_gl_account_id,property_id=payload.property_id,unit_id=payload.unit_id,owner_id=payload.owner_id,is_active=True,created_by_id=created_by.id)
    row.lines=[RecurringBillLine(gl_account_id=x.gl_account_id,property_id=x.property_id,unit_id=x.unit_id,description=x.description,amount=Decimal(x.amount)) for x in payload.lines]
    db.add(row); db.commit(); db.refresh(row); return row

def _due_date_for_occurrence(posting_date:date,due_day:int|None)->date|None:
    if due_day is None:return None
    candidate=monthly_date(posting_date.year,posting_date.month,due_day)
    if candidate>=posting_date:return candidate
    nm=next_monthly_date(posting_date,due_day)
    return monthly_date(nm.year,nm.month,due_day)

def post_vendor_credit(db:Session,*,organization_id:int,payload:VendorCreditCreateIn,created_by:User)->VendorCredit:
    _validate_scope(db,organization_id=organization_id,lines=payload.lines,property_id=payload.property_id,unit_id=payload.unit_id,owner_id=payload.owner_id)
    payable=_get_account(db,organization_id,payload.payable_gl_account_id) if payload.payable_gl_account_id is not None else _default_payable_account(db,organization_id)
    total=sum((Decimal(x.amount) for x in payload.lines),Decimal("0"))
    if total<=0: raise PostingError("Vendor credit total must be greater than zero.")
    lines=[PostingLine(gl_account_id=payable.id,property_id=payload.property_id,unit_id=payload.unit_id,owner_id=payload.owner_id,description=f"Vendor credit: {payload.payee_name}",debit=total,credit=Decimal("0"))]
    lines += [PostingLine(gl_account_id=x.gl_account_id,property_id=x.property_id or payload.property_id,unit_id=x.unit_id or payload.unit_id,owner_id=payload.owner_id,description=x.description or f"Vendor credit: {payload.payee_name}",debit=Decimal("0"),credit=Decimal(x.amount)) for x in payload.lines]
    txn=post_transaction(db=db,organization_id=organization_id,transaction_date=payload.credit_date,transaction_type="VENDOR_CREDIT",memo=payload.remarks,lines=lines,created_by=created_by,reference_number=payload.reference_number,source_type=payload.source_type or "vendor_credit",source_id=payload.source_id)
    try:
        credit=VendorCredit(organization_id=organization_id,credit_number=payload.credit_number,payee_name=payload.payee_name,payee_user_id=payload.payee_user_id,credit_date=payload.credit_date,reference_number=payload.reference_number,amount=total,property_id=payload.property_id,unit_id=payload.unit_id,owner_id=payload.owner_id,payable_gl_account_id=payable.id,remarks=payload.remarks,source_type=payload.source_type,source_id=payload.source_id,gl_transaction_id=txn.id,status="POSTED",is_reversed=False,is_active=True,created_by_id=created_by.id)
        db.add(credit); db.flush()
        for x in payload.lines: db.add(VendorCreditLine(vendor_credit_id=credit.id,organization_id=organization_id,gl_account_id=x.gl_account_id,property_id=x.property_id or payload.property_id,unit_id=x.unit_id or payload.unit_id,description=x.description,amount=Decimal(x.amount)))
        if not credit.credit_number: credit.credit_number=f"VC-{credit.id:05d}"
        txn.source_type="vendor_credit"; txn.source_id=credit.id
        db.commit(); db.refresh(credit); return credit
    except Exception as exc:
        db.rollback(); raise PostingError(f"Failed to save vendor credit: {exc}")

def _posting_user(db:Session,schedule:RecurringBill)->User|None:
    if schedule.created_by_id is not None:
        u=db.get(User,schedule.created_by_id)
        if u is not None and u.organization_id==schedule.organization_id and u.is_active:return u
    return db.query(User).filter(User.organization_id==schedule.organization_id,User.is_active.is_(True),User.role.in_([UserRole.ADMIN,UserRole.OWNER,UserRole.MANAGER])).order_by(User.id.asc()).first()

def _post_one_occurrence(db:Session,*,schedule:RecurringBill,posting_date:date,created_by:User)->str|None:
    if schedule.entry_type=="CREDIT":
        existing=db.query(VendorCredit).filter(VendorCredit.organization_id==schedule.organization_id,VendorCredit.source_type=="recurring_bill",VendorCredit.source_id==schedule.id,VendorCredit.credit_date==posting_date).first()
        if existing is None:
            post_vendor_credit(db,organization_id=schedule.organization_id,payload=VendorCreditCreateIn(payee_name=schedule.payee_name,payee_user_id=schedule.payee_user_id,credit_date=posting_date,reference_number=schedule.reference_number,payable_gl_account_id=schedule.payable_gl_account_id,property_id=schedule.property_id,unit_id=schedule.unit_id,owner_id=schedule.owner_id,remarks=schedule.remarks,source_type="recurring_bill",source_id=schedule.id,lines=[BillLineIn(gl_account_id=x.gl_account_id,property_id=x.property_id,unit_id=x.unit_id,description=x.description,amount=x.amount) for x in schedule.lines]),created_by=created_by)
            kind="CREDIT"
        else: kind=None
    else:
        existing=db.query(Bill).filter(Bill.organization_id==schedule.organization_id,Bill.source_type=="recurring_bill",Bill.source_id==schedule.id,Bill.bill_date==posting_date).first()
        if existing is None:
            post_bill(db=db,organization_id=schedule.organization_id,payload=BillCreateIn(payee_name=schedule.payee_name,payee_user_id=schedule.payee_user_id,bill_date=posting_date,due_date=_due_date_for_occurrence(posting_date,schedule.due_day),reference_number=schedule.reference_number,payable_gl_account_id=schedule.payable_gl_account_id,cash_gl_account_id=schedule.cash_gl_account_id,property_id=schedule.property_id,unit_id=schedule.unit_id,owner_id=schedule.owner_id,remarks=schedule.remarks,source_type="recurring_bill",source_id=schedule.id,lines=[BillLineIn(gl_account_id=x.gl_account_id,property_id=x.property_id,unit_id=x.unit_id,description=x.description,amount=x.amount) for x in schedule.lines]),created_by=created_by)
            kind="BILL"
        else: kind=None
    schedule.last_posted_date=posting_date; nxt=next_monthly_date(posting_date,schedule.bill_day); schedule.next_post_date=nxt
    if schedule.end_date is not None and nxt>schedule.end_date:schedule.is_active=False
    db.commit(); return kind

def post_due_recurring_bills(db:Session,*,as_of:date,organization_id:int|None=None,schedule_ids:list[int]|None=None,created_by:User|None=None,require_manual_gate:bool=False)->dict[str,int]:
    q=db.query(RecurringBill.id).filter(RecurringBill.is_active.is_(True),RecurringBill.next_post_date<=as_of)
    if organization_id is not None:q=q.filter(RecurringBill.organization_id==organization_id)
    if schedule_ids:q=q.filter(RecurringBill.id.in_(schedule_ids))
    result={"posted_bills":0,"posted_credits":0,"skipped_disabled":0,"failed":0}
    for sid, in q.order_by(RecurringBill.id.asc()).all():
        s=db.get(RecurringBill,sid)
        if s is None or not s.is_active:continue
        if not recurring_bills_enabled_for_org(db,organization_id=s.organization_id) or (require_manual_gate and not manual_bill_post_enabled_for_org(db,organization_id=s.organization_id)):
            result["skipped_disabled"]+=1; continue
        user=created_by if created_by is not None and created_by.organization_id==s.organization_id else _posting_user(db,s)
        if user is None: result["failed"]+=1; continue
        try:
            while s.is_active and s.next_post_date<=as_of:
                pd=s.next_post_date
                if s.end_date is not None and pd>s.end_date:s.is_active=False; db.commit(); break
                kind=_post_one_occurrence(db,schedule=s,posting_date=pd,created_by=user)
                if kind=="BILL":result["posted_bills"]+=1
                elif kind=="CREDIT":result["posted_credits"]+=1
                s=db.get(RecurringBill,sid)
                if s is None:break
        except Exception:
            db.rollback(); result["failed"]+=1
    return result
