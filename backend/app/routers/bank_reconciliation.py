from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload
from app.core.database import get_db
from app.models.bank_account import BankAccount
from app.models.bank_reconciliation import BankReconciliation, BankReconciliationItem
from app.models.user import User
from app.routers.auth import get_current_user
from app.schemas.bank_reconciliation import QIFImportIn,QIFImportOut,ReconciliationOut,ReconciliationItemOut,ReconciliationSelectionIn,ReconciliationStartIn,StatementLineOut
from app.services.bank_reconciliation import cleared_balance,difference,finish_reconciliation,import_qif,set_cleared_items,start_reconciliation
from app.services.customer_features import resolve_customer_features
from app.services.gl_posting import PostingError
router=APIRouter(prefix="/api/accounting/bank-accounts",tags=["Bank Reconciliation"])

def _feature(db:Session,user:User,key:str)->int:
    if user.organization_id is None:raise HTTPException(400,"User has no organization.")
    d=next((x for x in resolve_customer_features(db,user=user) if x.key==key),None)
    if d is None or not d.allowed:raise HTTPException(status.HTTP_403_FORBIDDEN,"Bank reconciliation capability is not enabled.")
    return user.organization_id
def _bank(db,org,bank_id):
    b=db.query(BankAccount).filter(BankAccount.id==bank_id,BankAccount.organization_id==org,BankAccount.is_active.is_(True)).first()
    if b is None:raise HTTPException(404,"Bank account not found.")
    return b
def _load(db,org,bank_id,recon_id):
    r=db.query(BankReconciliation).options(joinedload(BankReconciliation.bank_account),joinedload(BankReconciliation.items),joinedload(BankReconciliation.statement_lines)).filter(BankReconciliation.id==recon_id,BankReconciliation.organization_id==org,BankReconciliation.bank_account_id==bank_id).first()
    if r is None:raise HTTPException(404,"Reconciliation not found.")
    return r
def _out(r):
    cb=cleared_balance(r);diff=difference(r)
    return ReconciliationOut(id=r.id,organization_id=r.organization_id,bank_account_id=r.bank_account_id,bank_account_name=r.bank_account.name if r.bank_account else None,statement_date=r.statement_date,beginning_balance=r.beginning_balance,ending_statement_balance=r.ending_statement_balance,cleared_balance=cb,difference=diff,balanced=abs(diff)<=0.01,status=r.status,finished_at=r.finished_at,items=[ReconciliationItemOut(id=x.id,source_type=x.source_type,source_id=x.source_id,transaction_date=x.transaction_date,description=x.description,reference_number=x.reference_number,signed_amount=x.signed_amount,cleared=x.cleared) for x in r.items],statement_lines=[StatementLineOut(id=x.id,posted_date=x.posted_date,amount=x.amount,payee=x.payee,memo=x.memo,reference_number=x.reference_number,matched_item_id=x.matched_item_id) for x in r.statement_lines])

@router.get("/{bank_id}/reconciliations/current",response_model=ReconciliationOut)
def current(bank_id:int,db:Session=Depends(get_db),current_user:User=Depends(get_current_user)):
    org=_feature(db,current_user,"release.accounting.bank_reconciliation");_bank(db,org,bank_id)
    r=db.query(BankReconciliation).options(joinedload(BankReconciliation.bank_account),joinedload(BankReconciliation.items),joinedload(BankReconciliation.statement_lines)).filter(BankReconciliation.organization_id==org,BankReconciliation.bank_account_id==bank_id,BankReconciliation.status=="OPEN").first()
    if r is None:raise HTTPException(404,"No open reconciliation.")
    return _out(r)
@router.post("/{bank_id}/reconciliations",response_model=ReconciliationOut,status_code=201)
def start(bank_id:int,payload:ReconciliationStartIn,db:Session=Depends(get_db),current_user:User=Depends(get_current_user)):
    org=_feature(db,current_user,"release.accounting.bank_reconciliation");b=_bank(db,org,bank_id)
    try:r=start_reconciliation(db,organization_id=org,bank_account=b,statement_date=payload.statement_date,ending_balance=payload.ending_statement_balance,created_by=current_user)
    except PostingError as e:raise HTTPException(400,str(e))
    return _out(_load(db,org,bank_id,r.id))
@router.get("/{bank_id}/reconciliations/{recon_id}",response_model=ReconciliationOut)
def get_one(bank_id:int,recon_id:int,db:Session=Depends(get_db),current_user:User=Depends(get_current_user)):
    org=_feature(db,current_user,"release.accounting.bank_reconciliation");_bank(db,org,bank_id);return _out(_load(db,org,bank_id,recon_id))
@router.put("/{bank_id}/reconciliations/{recon_id}/selection",response_model=ReconciliationOut)
def selection(bank_id:int,recon_id:int,payload:ReconciliationSelectionIn,db:Session=Depends(get_db),current_user:User=Depends(get_current_user)):
    org=_feature(db,current_user,"release.accounting.bank_reconciliation");r=_load(db,org,bank_id,recon_id)
    try:set_cleared_items(db,reconciliation=r,item_ids=payload.cleared_item_ids)
    except PostingError as e:raise HTTPException(400,str(e))
    return _out(_load(db,org,bank_id,recon_id))
@router.post("/{bank_id}/reconciliations/{recon_id}/finish",response_model=ReconciliationOut)
def finish(bank_id:int,recon_id:int,db:Session=Depends(get_db),current_user:User=Depends(get_current_user)):
    org=_feature(db,current_user,"release.accounting.bank_reconciliation");r=_load(db,org,bank_id,recon_id)
    try:finish_reconciliation(db,reconciliation=r,user=current_user)
    except PostingError as e:raise HTTPException(400,str(e))
    return _out(_load(db,org,bank_id,recon_id))
@router.post("/{bank_id}/reconciliations/{recon_id}/qif",response_model=QIFImportOut)
def qif(bank_id:int,recon_id:int,payload:QIFImportIn,db:Session=Depends(get_db),current_user:User=Depends(get_current_user)):
    org=_feature(db,current_user,"release.accounting.bank_reconciliation.qif");r=_load(db,org,bank_id,recon_id)
    try:count,matched=import_qif(db,reconciliation=r,content=payload.content)
    except (PostingError,ValueError) as e:raise HTTPException(400,str(e))
    return QIFImportOut(imported=count,matched=matched,reconciliation=_out(_load(db,org,bank_id,recon_id)))
