"""Bank reconciliation candidate snapshot, calculator, finish guard and QIF matching."""
from __future__ import annotations
from datetime import date, datetime
from decimal import Decimal
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload
from app.models.bank_account import BankAccount
from app.models.bank_reconciliation import BankReconciliation, BankReconciliationItem, BankStatementLine
from app.models.check import Check
from app.models.deposit import Deposit
from app.models.gl_entry import GLEntry
from app.models.gl_transaction import GLTransaction
from app.models.user import User
from app.services.gl_posting import PostingError
CENT=Decimal("0.01")
def money(v):return Decimal(v or 0).quantize(CENT)

def _last_reconciled(db:Session,org:int,bank_id:int):
    return db.query(BankReconciliation).filter(BankReconciliation.organization_id==org,BankReconciliation.bank_account_id==bank_id,BankReconciliation.status=="RECONCILED").order_by(BankReconciliation.statement_date.desc(),BankReconciliation.id.desc()).first()

def _window(q,col,after:date|None,through:date):
    q=q.filter(col<=through)
    if after is not None:q=q.filter(col>after)
    return q

def start_reconciliation(db:Session,*,organization_id:int,bank_account:BankAccount,statement_date:date,ending_balance:Decimal,created_by:User)->BankReconciliation:
    open_row=db.query(BankReconciliation).filter(BankReconciliation.organization_id==organization_id,BankReconciliation.bank_account_id==bank_account.id,BankReconciliation.status=="OPEN").first()
    if open_row:raise PostingError("This bank account already has an open reconciliation.")
    last=_last_reconciled(db,organization_id,bank_account.id)
    if last and statement_date<=last.statement_date:raise PostingError("Statement date must be after the last reconciled statement.")
    after=last.statement_date if last else None
    row=BankReconciliation(organization_id=organization_id,bank_account_id=bank_account.id,statement_date=statement_date,beginning_balance=money(last.ending_statement_balance if last else 0),ending_statement_balance=money(ending_balance),status="OPEN",created_by_id=created_by.id)
    try:
        db.add(row);db.flush()
        deposits=_window(db.query(Deposit).filter(Deposit.organization_id==organization_id,Deposit.bank_gl_account_id==bank_account.gl_account_id,Deposit.is_active.is_(True)),Deposit.deposit_date,after,statement_date).all()
        for d in deposits:db.add(BankReconciliationItem(reconciliation_id=row.id,organization_id=organization_id,source_type="DEPOSIT",source_id=d.id,transaction_date=d.deposit_date,description=d.description or "Bank deposit",reference_number=d.deposit_number,signed_amount=money(d.total),cleared=False))
        checks=_window(db.query(Check).filter(Check.organization_id==organization_id,Check.bank_account_id==bank_account.id,Check.status=="ISSUED"),Check.check_date,after,statement_date).all()
        for c in checks:db.add(BankReconciliationItem(reconciliation_id=row.id,organization_id=organization_id,source_type="CHECK",source_id=c.id,transaction_date=c.check_date,description=c.payee_name,reference_number=c.check_number,signed_amount=-money(c.amount),cleared=False))
        txq=db.query(GLTransaction).join(GLEntry,GLEntry.transaction_id==GLTransaction.id).filter(GLTransaction.organization_id==organization_id,GLEntry.gl_account_id==bank_account.gl_account_id,GLTransaction.transaction_type!="CHECK",func.coalesce(GLTransaction.source_type,"").notin_(["receipt","check"]))
        txq=_window(txq,GLTransaction.transaction_date,after,statement_date).distinct().all()
        for txn in txq:
            net=sum((money(e.debit)-money(e.credit) for e in txn.entries if e.gl_account_id==bank_account.gl_account_id),Decimal("0"))
            if net==0:continue
            db.add(BankReconciliationItem(reconciliation_id=row.id,organization_id=organization_id,source_type="GL",source_id=txn.id,transaction_date=txn.transaction_date,description=txn.memo or txn.transaction_type,reference_number=txn.reference_number,signed_amount=money(net),cleared=False))
        db.commit();db.refresh(row);return row
    except Exception as exc:
        db.rollback()
        if isinstance(exc,PostingError):raise
        raise PostingError(f"Failed to start reconciliation: {exc}")

def set_cleared_items(db:Session,*,reconciliation:BankReconciliation,item_ids:list[int])->BankReconciliation:
    if reconciliation.status!="OPEN":raise PostingError("Only an open reconciliation can be changed.")
    valid={x.id for x in db.query(BankReconciliationItem).filter(BankReconciliationItem.reconciliation_id==reconciliation.id,BankReconciliationItem.organization_id==reconciliation.organization_id).all()}
    requested=set(item_ids)
    if not requested.issubset(valid):raise PostingError("One or more reconciliation items are invalid.")
    db.query(BankReconciliationItem).filter(BankReconciliationItem.reconciliation_id==reconciliation.id).update({BankReconciliationItem.cleared:False},synchronize_session=False)
    if requested:db.query(BankReconciliationItem).filter(BankReconciliationItem.reconciliation_id==reconciliation.id,BankReconciliationItem.id.in_(requested)).update({BankReconciliationItem.cleared:True},synchronize_session=False)
    db.commit();db.refresh(reconciliation);return reconciliation

def cleared_balance(reconciliation:BankReconciliation)->Decimal:
    return money(reconciliation.beginning_balance)+sum((money(x.signed_amount) for x in reconciliation.items if x.cleared),Decimal("0"))
def difference(reconciliation:BankReconciliation)->Decimal:return money(reconciliation.ending_statement_balance)-money(cleared_balance(reconciliation))

def finish_reconciliation(db:Session,*,reconciliation:BankReconciliation,user:User)->BankReconciliation:
    if reconciliation.status!="OPEN":raise PostingError("Only an open reconciliation can be finished.")
    db.refresh(reconciliation)
    if abs(difference(reconciliation))>CENT:raise PostingError(f"Reconciliation is not balanced. Difference: {difference(reconciliation)}")
    reconciliation.status="RECONCILED";reconciliation.finished_at=datetime.utcnow();reconciliation.finished_by_id=user.id
    db.commit();db.refresh(reconciliation);return reconciliation

def _parse_qif_date(value:str)->date:
    value=value.strip().replace("'","/")
    parts=value.split("/")
    if len(parts)!=3:raise ValueError(f"Unsupported QIF date: {value}")
    m,d,y=[int(x) for x in parts]
    if y<100:y+=2000 if y<70 else 1900
    return date(y,m,d)

def parse_qif(content:str):
    rows=[];cur={}
    for raw in content.replace("\r","").split("\n"):
        line=raw.strip()
        if not line:continue
        if line=="^":
            if "date" in cur and "amount" in cur:rows.append(cur)
            cur={};continue
        code,val=line[0],line[1:].strip()
        if code=="D":cur["date"]=_parse_qif_date(val)
        elif code=="T":cur["amount"]=money(val.replace(",",""))
        elif code=="P":cur["payee"]=val
        elif code=="M":cur["memo"]=val
        elif code=="N":cur["reference"]=val
    if cur and "date" in cur and "amount" in cur:rows.append(cur)
    return rows

def import_qif(db:Session,*,reconciliation:BankReconciliation,content:str):
    if reconciliation.status!="OPEN":raise PostingError("QIF can only be imported into an open reconciliation.")
    parsed=parse_qif(content);matched=0
    try:
        existing_matches={x.matched_item_id for x in reconciliation.statement_lines if x.matched_item_id}
        items=[x for x in reconciliation.items if x.id not in existing_matches]
        for src in parsed:
            candidates=[x for x in items if x.transaction_date==src["date"] and money(x.signed_amount)==money(src["amount"])]
            match=candidates[0] if len(candidates)==1 else None
            line=BankStatementLine(reconciliation_id=reconciliation.id,organization_id=reconciliation.organization_id,posted_date=src["date"],amount=src["amount"],payee=src.get("payee"),memo=src.get("memo"),reference_number=src.get("reference"),matched_item_id=match.id if match else None)
            db.add(line)
            if match:match.cleared=True;items.remove(match);matched+=1
        db.commit();db.refresh(reconciliation);return len(parsed),matched
    except Exception as exc:
        db.rollback();raise PostingError(f"Failed to import QIF: {exc}")
