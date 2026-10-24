# ============================================================
# audit.py
# ------------------------------------------------------------
# Compatibility wrapper for audit writes.
#
# New code should prefer app.services.audit.append_audit_log() when the
# audit event must share the caller's transaction. Existing callers can
# keep using log_action(), which commits by default.
# ============================================================

from __future__ import annotations

from typing import Any, Optional

from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.models.user import User
from app.services.audit import append_audit_log


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
    *,
    commit: bool = True,
) -> AuditLog | None:
    """Append one audit event through the canonical append-only service.

    Existing behavior is preserved with commit=True. Atomic workflows may
    pass commit=False and commit the business state plus audit row together.
    Audit failures remain non-fatal for this compatibility wrapper.
    """
    try:
        entry = append_audit_log(
            db,
            user_id=user.id if user else None,
            organization_id=user.organization_id if user else None,
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            field_name=field_name,
            old_value=old_value,
            new_value=new_value,
            ip_address=ip_address,
        )
        if commit:
            db.commit()
            db.refresh(entry)
        return entry
    except Exception as exc:
        print(f"Audit log failed: {exc}")
        try:
            db.rollback()
        except Exception:
            pass
        return None
