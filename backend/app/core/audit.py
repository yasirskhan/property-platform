# ============================================================
# audit.py
# ------------------------------------------------------------
# Helper to write audit log entries.
# ============================================================

import json
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.audit_log import AuditLog
from app.models.user import User


def log_action(
    db: Session,
    user: Optional[User],
    entity_type: str,
    entity_id: int,
    action: str,
    field_name: Optional[str] = None,
    old_value: Optional[Any] = None,
    new_value: Optional[Any] = None,
    ip_address: Optional[str] = None,
):
    """
    Write one audit log entry. Silent on error — logging failures
    should never break the main operation.
    """
    try:
        entry = AuditLog(
            user_id=user.id if user else None,
            organization_id=user.organization_id if user else None,
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            field_name=field_name,
            old_value=_to_json(old_value),
            new_value=_to_json(new_value),
            ip_address=ip_address,
        )
        db.add(entry)
        db.commit()
    except Exception as e:
        print(f"⚠️  Audit log failed: {e}")
        try:
            db.rollback()
        except Exception:
            pass


def _to_json(value: Any) -> Optional[str]:
    if value is None:
        return None
    try:
        return json.dumps(value, default=str)
    except Exception:
        return str(value)