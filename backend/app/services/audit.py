"""Append-only audit logging service.

Callers add audit rows inside the same transaction as the business change.
This function flushes so failures surface immediately, but deliberately does
not commit on its own.
"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog


def _json_text(value: Any) -> str | None:
    if value is None:
        return None
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def append_audit_log(
    db: Session,
    *,
    entity_type: str,
    entity_id: int,
    action: str,
    user_id: int | None = None,
    organization_id: int | None = None,
    field_name: str | None = None,
    old_value: Any = None,
    new_value: Any = None,
    ip_address: str | None = None,
) -> AuditLog:
    """Append one immutable audit event to the caller's transaction."""
    if not entity_type.strip():
        raise ValueError("entity_type is required")
    if not action.strip():
        raise ValueError("action is required")

    row = AuditLog(
        user_id=user_id,
        organization_id=organization_id,
        entity_type=entity_type.strip(),
        entity_id=entity_id,
        action=action.strip(),
        field_name=field_name,
        old_value=_json_text(old_value),
        new_value=_json_text(new_value),
        ip_address=ip_address,
    )
    db.add(row)
    db.flush()
    return row
