"""Organization-scoped read-only Auditing Center."""
from __future__ import annotations
import csv, io
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from sqlalchemy import or_
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.audit_log import AuditLog
from app.models.user import User
from app.routers.auth import get_current_user
from app.schemas.audit_center import AuditCenterItem, AuditCenterList
from app.services.customer_features import resolve_customer_features
from app.services.menu_resolver import permission_allows_user

router = APIRouter(prefix="/api/settings/audit", tags=["Auditing Center"])
FEATURE_KEY = "release.settings.audit"
MENU_KEY = "SETTINGS.AUDIT"

def _require_access(db: Session, user: User) -> int:
    if user.organization_id is None:
        raise HTTPException(status_code=400, detail="User has no organization.")
    if not permission_allows_user(db, user=user, menu_key=MENU_KEY):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Auditing Center permission required.")
    decision = next((x for x in resolve_customer_features(db, user=user) if x.key == FEATURE_KEY), None)
    if decision is None or not decision.allowed:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Auditing Center is not available.")
    return user.organization_id

def _query(db, *, organization_id, entity_type, action, actor_user_id, date_from, date_to, search):
    q = db.query(AuditLog).filter(AuditLog.organization_id == organization_id)
    if entity_type: q = q.filter(AuditLog.entity_type == entity_type.strip())
    if action: q = q.filter(AuditLog.action == action.strip())
    if actor_user_id is not None: q = q.filter(AuditLog.user_id == actor_user_id)
    if date_from is not None: q = q.filter(AuditLog.created_at >= date_from)
    if date_to is not None: q = q.filter(AuditLog.created_at <= date_to)
    if search:
        term = f"%{search.strip()}%"
        q = q.filter(or_(AuditLog.entity_type.ilike(term), AuditLog.action.ilike(term), AuditLog.field_name.ilike(term), AuditLog.old_value.ilike(term), AuditLog.new_value.ilike(term)))
    return q

def _item(row: AuditLog) -> AuditCenterItem:
    if row.user is not None:
        actor_type, actor_id = "customer", row.user_id
        actor_name = f"{row.user.first_name} {row.user.last_name}".strip() or row.user.email
        actor_email = row.user.email
    elif row.platform_user is not None:
        actor_type, actor_id = "platform", row.platform_user_id
        actor_name = f"{row.platform_user.first_name} {row.platform_user.last_name}".strip() or row.platform_user.email
        actor_email = row.platform_user.email
    else:
        actor_type, actor_id, actor_name, actor_email = "system", None, "System", None
    return AuditCenterItem(id=row.id, actor_type=actor_type, actor_id=actor_id, actor_name=actor_name, actor_email=actor_email, entity_type=row.entity_type, entity_id=row.entity_id, action=row.action, field_name=row.field_name, old_value=row.old_value, new_value=row.new_value, ip_address=row.ip_address, created_at=row.created_at)

@router.get("", response_model=AuditCenterList)
def list_audit_events(entity_type: Optional[str]=None, action: Optional[str]=None, actor_user_id: Optional[int]=None, date_from: Optional[datetime]=None, date_to: Optional[datetime]=None, search: Optional[str]=None, limit: int=Query(default=100, ge=1, le=200), offset: int=Query(default=0, ge=0), db: Session=Depends(get_db), current_user: User=Depends(get_current_user)):
    org_id = _require_access(db, current_user)
    q = _query(db, organization_id=org_id, entity_type=entity_type, action=action, actor_user_id=actor_user_id, date_from=date_from, date_to=date_to, search=search)
    total = q.count()
    rows = q.order_by(AuditLog.created_at.desc(), AuditLog.id.desc()).offset(offset).limit(limit).all()
    return AuditCenterList(items=[_item(r) for r in rows], total=total, limit=limit, offset=offset)

@router.get("/export.csv")
def export_audit_events(entity_type: Optional[str]=None, action: Optional[str]=None, actor_user_id: Optional[int]=None, date_from: Optional[datetime]=None, date_to: Optional[datetime]=None, search: Optional[str]=None, db: Session=Depends(get_db), current_user: User=Depends(get_current_user)):
    org_id = _require_access(db, current_user)
    rows = _query(db, organization_id=org_id, entity_type=entity_type, action=action, actor_user_id=actor_user_id, date_from=date_from, date_to=date_to, search=search).order_by(AuditLog.created_at.desc(), AuditLog.id.desc()).limit(10000).all()
    output = io.StringIO()
    w = csv.writer(output)
    w.writerow(["created_at","actor_type","actor_name","actor_email","entity_type","entity_id","action","field_name","old_value","new_value","ip_address"])
    for row in rows:
        item = _item(row)
        w.writerow([item.created_at.isoformat(), item.actor_type, item.actor_name, item.actor_email or "", item.entity_type, item.entity_id, item.action, item.field_name or "", item.old_value or "", item.new_value or "", item.ip_address or ""])
    return Response(content=output.getvalue(), media_type="text/csv; charset=utf-8", headers={"Content-Disposition": 'attachment; filename="audit-log.csv"'})
