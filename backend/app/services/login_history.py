from __future__ import annotations

import json

from fastapi import Request
from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.models.user import User
from app.schemas.login_history import LoginHistoryItem
from app.services.audit import append_audit_log

ENTITY_TYPE = "user_login"
ACTION_SUCCESS = "login_success"
ACTION_FAILED = "login_failed"

def _request_metadata(request: Request) -> tuple[str | None, str | None]:
    ip_address = request.client.host[:45] if request.client and request.client.host else None
    user_agent = request.headers.get("user-agent")
    if user_agent:
        user_agent = user_agent.strip()[:500] or None
    return ip_address, user_agent

def record_login_event(db: Session, *, user: User, request: Request, success: bool, auth_method: str, reason: str | None = None) -> AuditLog | None:
    """Append one immutable customer login event inside the caller transaction."""
    if user.organization_id is None:
        return None
    ip_address, user_agent = _request_metadata(request)
    return append_audit_log(
        db,
        user_id=user.id,
        organization_id=user.organization_id,
        entity_type=ENTITY_TYPE,
        entity_id=user.id,
        action=ACTION_SUCCESS if success else ACTION_FAILED,
        new_value={"auth_method": auth_method.strip().upper(), "reason": reason, "user_agent": user_agent},
        ip_address=ip_address,
    )

def list_login_history(db: Session, *, user: User, limit: int) -> list[LoginHistoryItem]:
    if user.organization_id is None:
        return []
    rows = (db.query(AuditLog).filter(AuditLog.organization_id == user.organization_id, AuditLog.entity_type == ENTITY_TYPE, AuditLog.entity_id == user.id).order_by(AuditLog.created_at.desc(), AuditLog.id.desc()).limit(limit).all())
    items: list[LoginHistoryItem] = []
    for row in rows:
        metadata: dict = {}
        if row.new_value:
            try:
                parsed = json.loads(row.new_value)
                if isinstance(parsed, dict):
                    metadata = parsed
            except (TypeError, ValueError, json.JSONDecodeError):
                metadata = {}
        items.append(LoginHistoryItem(id=row.id, status="SUCCESS" if row.action == ACTION_SUCCESS else "FAILED", auth_method=str(metadata.get("auth_method") or "PASSWORD"), reason=metadata.get("reason"), ip_address=row.ip_address, user_agent=metadata.get("user_agent"), created_at=row.created_at))
    return items
