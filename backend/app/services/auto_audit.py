"""Authenticated ORM mutation fallback for the universal audit log.

Explicit semantic audit events remain preferred. This listener fills coverage gaps
for authenticated customer/platform requests without storing business-field values.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import event, inspect
from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.models.entity_note import EntityNote
from app.models.platform_user import PlatformUser
from app.models.user import Organization, User


_AUDIT_ACTOR_KEY = "_audit_actor"
_AUDIT_PENDING_KEY = "_audit_pending"
_AUDIT_WRITING_KEY = "_audit_writing"


@dataclass(frozen=True)
class AuditActor:
    user_id: int | None = None
    platform_user_id: int | None = None
    organization_id: int | None = None


@dataclass
class PendingAudit:
    obj: Any
    entity_type: str
    action: str
    field_name: str | None
    organization_id: int | None


def bind_customer_audit_actor(db: Session, user: User) -> None:
    """Bind the authenticated customer actor to this request session."""
    db.info[_AUDIT_ACTOR_KEY] = AuditActor(
        user_id=int(user.id),
        organization_id=(
            int(user.organization_id) if user.organization_id is not None else None
        ),
    )


def bind_platform_audit_actor(db: Session, user: PlatformUser) -> None:
    """Bind the authenticated internal-platform actor to this request session."""
    db.info[_AUDIT_ACTOR_KEY] = AuditActor(platform_user_id=int(user.id))


def _entity_type(obj: Any) -> str | None:
    table = getattr(obj, "__table__", None)
    name = getattr(table, "name", None)
    if not name:
        return None
    return str(name)[:50]


def _entity_id(obj: Any) -> int | None:
    state = inspect(obj)
    identity = state.identity
    if not identity or len(identity) != 1:
        value = getattr(obj, "id", None)
    else:
        value = identity[0]
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _organization_id(obj: Any, actor: AuditActor) -> int | None:
    value = getattr(obj, "organization_id", None)
    if value is not None:
        try:
            return int(value)
        except (TypeError, ValueError):
            pass
    if isinstance(obj, Organization):
        value = getattr(obj, "id", None)
        if value is not None:
            return int(value)
    return actor.organization_id


def _changed_fields(obj: Any) -> list[str]:
    state = inspect(obj)
    changed: list[str] = []
    for attr in state.mapper.column_attrs:
        if attr.key in {"updated_at"}:
            continue
        history = state.attrs[attr.key].history
        if history.has_changes():
            changed.append(attr.key)
    return sorted(changed)


def _action_for_update(obj: Any, changed: list[str]) -> str:
    if "deleted_at" in changed:
        value = getattr(obj, "deleted_at", None)
        if value is not None:
            return "soft_deleted"
        return "restored"
    if "is_active" in changed and getattr(obj, "is_active", None) is False:
        return "deactivated"
    if "is_active" in changed and getattr(obj, "is_active", None) is True:
        return "reactivated"
    return "updated"


def _manual_targets(session: Session) -> set[tuple[str, int]]:
    targets: set[tuple[str, int]] = set()
    for row in session.new:
        if not isinstance(row, AuditLog):
            continue
        if row.entity_id is None:
            continue
        targets.add((str(row.entity_type).lower(), int(row.entity_id)))
    return targets


def _manually_covered(
    obj: Any,
    entity_type: str,
    manual_targets: set[tuple[str, int]],
) -> bool:
    entity_id = _entity_id(obj)
    if entity_id is None:
        return False
    class_name = obj.__class__.__name__.lower()
    candidates = {
        entity_type.lower(),
        class_name,
        class_name.rstrip("s"),
        entity_type.lower().rstrip("s"),
    }
    return any((name, entity_id) in manual_targets for name in candidates)


def _eligible(obj: Any) -> bool:
    if isinstance(obj, (AuditLog, EntityNote)):
        return False
    return _entity_type(obj) is not None


@event.listens_for(Session, "before_flush")
def _capture_authenticated_mutations(
    session: Session,
    _flush_context: Any,
    _instances: Any,
) -> None:
    actor = session.info.get(_AUDIT_ACTOR_KEY)
    if actor is None or session.info.get(_AUDIT_WRITING_KEY):
        return

    manual_targets = _manual_targets(session)
    pending: list[PendingAudit] = []

    for obj in list(session.new):
        if not _eligible(obj):
            continue
        entity_type = _entity_type(obj)
        if entity_type is None:
            continue
        pending.append(
            PendingAudit(
                obj=obj,
                entity_type=entity_type,
                action="created",
                field_name=None,
                organization_id=_organization_id(obj, actor),
            )
        )

    for obj in list(session.dirty):
        if not _eligible(obj) or not session.is_modified(obj, include_collections=False):
            continue
        entity_type = _entity_type(obj)
        if entity_type is None or _manually_covered(obj, entity_type, manual_targets):
            continue
        changed = _changed_fields(obj)
        if not changed:
            continue
        pending.append(
            PendingAudit(
                obj=obj,
                entity_type=entity_type,
                action=_action_for_update(obj, changed),
                field_name=",".join(changed)[:100],
                organization_id=_organization_id(obj, actor),
            )
        )

    for obj in list(session.deleted):
        if not _eligible(obj):
            continue
        entity_type = _entity_type(obj)
        if entity_type is None or _manually_covered(obj, entity_type, manual_targets):
            continue
        pending.append(
            PendingAudit(
                obj=obj,
                entity_type=entity_type,
                action="deleted",
                field_name=None,
                organization_id=_organization_id(obj, actor),
            )
        )

    if pending:
        session.info.setdefault(_AUDIT_PENDING_KEY, []).extend(pending)


@event.listens_for(Session, "after_flush_postexec")
def _write_authenticated_audit_rows(session: Session, _flush_context: Any) -> None:
    actor = session.info.get(_AUDIT_ACTOR_KEY)
    pending = session.info.pop(_AUDIT_PENDING_KEY, [])
    if actor is None or not pending:
        return

    session.info[_AUDIT_WRITING_KEY] = True
    try:
        seen: set[tuple[str, int, str, str | None]] = set()
        for item in pending:
            entity_id = _entity_id(item.obj)
            if entity_id is None:
                continue
            key = (item.entity_type, entity_id, item.action, item.field_name)
            if key in seen:
                continue
            seen.add(key)
            session.add(
                AuditLog(
                    user_id=actor.user_id,
                    platform_user_id=actor.platform_user_id,
                    organization_id=item.organization_id,
                    entity_type=item.entity_type,
                    entity_id=entity_id,
                    action=item.action,
                    field_name=item.field_name,
                )
            )
    finally:
        session.info[_AUDIT_WRITING_KEY] = False


@event.listens_for(Session, "after_rollback")
def _clear_pending_after_rollback(session: Session) -> None:
    session.info.pop(_AUDIT_PENDING_KEY, None)
    session.info.pop(_AUDIT_WRITING_KEY, None)
