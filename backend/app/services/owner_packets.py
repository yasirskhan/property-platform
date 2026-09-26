"""Owner packets made solely from frozen owner statements and existing report export."""
from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass
from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.owner_statement import OwnerPacketSettings, OwnerStatement
from app.models.property import Property, PropertyAssignment
from app.models.user import User, UserRole
from app.schemas.owner_statement import StatementPropertyBlock
from app.schemas.owner_packet import OwnerPacketPreviewOut
from app.services.customer_features import resolve_customer_features
from app.services.menu_resolver import permission_allows_user
from app.services.report_delivery import (
    ReportDeliveryError, ReportPayload, build_report_payload, report_csv_bytes,
)

FEATURE_CUSTOMIZER = "release.owner_portal.packet_customizer"
FEATURE_EXPORT = "release.reporting.export"
FEATURE_CASH = "release.accounting.owner_statements.cash_summary"
ALLOWED = frozenset({"OWNER_STATEMENT", "PROPERTY_CASH_SUMMARY"})
DEFAULT = ["OWNER_STATEMENT", "PROPERTY_CASH_SUMMARY"]


@dataclass(frozen=True)
class Packet:
    preview: OwnerPacketPreviewOut
    files: tuple[tuple[str, bytes, str], ...]
    subject: str
    body: str


def _role(user: User) -> str:
    return str(user.role.value if hasattr(user.role, "value") else user.role or "").upper()


def _feature_matrix(db: Session, user: User) -> dict[str, bool]:
    return {item.key: bool(item.allowed) for item in resolve_customer_features(db, user=user)}


def _scope(db: Session, actor: User) -> tuple[int, dict[str, bool]]:
    role = _role(actor)
    if (actor.organization_id is None or not actor.is_active or actor.deleted_at is not None
            or role not in {"ADMIN", "MANAGER"}
            or not permission_allows_user(db, user=actor, menu_key="REPORTING.ALL")
            or not permission_allows_user(db, user=actor, menu_key="ACCOUNTING.OWNER_STATEMENTS")):
        raise HTTPException(status_code=403, detail="Owner packet permission required.")
    matrix = _feature_matrix(db, actor)
    if not matrix.get(FEATURE_CUSTOMIZER, False) or not matrix.get(FEATURE_EXPORT, False):
        raise HTTPException(status_code=404, detail="Owner packets are not available.")
    return int(actor.organization_id), matrix


def _setting(db: Session, org: int) -> tuple[list[str], str | None, bool]:
    row = db.get(OwnerPacketSettings, org)
    try:
        raw: Any = json.loads(row.included_reports) if row else DEFAULT
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail="Invalid owner packet configuration.") from exc
    if not isinstance(raw, list) or not raw or any(
        not isinstance(item, str) or item not in ALLOWED for item in raw
    ) or len(set(raw)) != len(raw):
        raise HTTPException(status_code=422, detail="Invalid owner packet configuration.")
    return raw, row.cover_message if row else None, bool(row.email_owner) if row else False


def _snapshot(db: Session, org: int, actor: User, statement_id: int) -> tuple[OwnerStatement, User, list[StatementPropertyBlock]]:
    stmt = db.query(OwnerStatement).filter(
        OwnerStatement.id == statement_id,
        OwnerStatement.organization_id == org,
        OwnerStatement.is_active.is_(True),
        OwnerStatement.deleted_at.is_(None),
    ).first()
    if stmt is None:
        raise HTTPException(status_code=404, detail="Owner statement not found.")
    owner = db.query(User).filter(
        User.id == stmt.owner_id,
        User.organization_id == org,
        User.role == UserRole.OWNER,
        User.is_active.is_(True),
        User.deleted_at.is_(None),
    ).first()
    if owner is None:
        raise HTTPException(status_code=404, detail="Owner statement not found.")
    try:
        parsed = json.loads(stmt.property_data or "[]")
        if not isinstance(parsed, list) or not parsed:
            raise ValueError("No snapshot rows")
        blocks = [StatementPropertyBlock(**item) for item in parsed]
        ids = [row.property_id for row in blocks]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate property")
    except (ValueError, TypeError, KeyError) as exc:
        raise HTTPException(status_code=422, detail="Frozen statement data is invalid.") from exc
    valid = db.query(Property.id).filter(Property.id.in_(ids), Property.organization_id == org).all()
    if len(valid) != len(ids):
        raise HTTPException(status_code=404, detail="Owner statement not found.")
    if _role(actor) == "MANAGER":
        visible = db.query(PropertyAssignment.property_id).filter(
            PropertyAssignment.property_id.in_(ids),
            PropertyAssignment.user_id == actor.id,
            PropertyAssignment.is_active.is_(True),
            PropertyAssignment.deleted_at.is_(None),
        ).distinct().all()
        if {row[0] for row in visible} != set(ids):
            raise HTTPException(status_code=404, detail="Owner statement not found.")
    return stmt, owner, blocks


def build_packet(db: Session, *, actor: User, statement_id: int) -> Packet:
    org, matrix = _scope(db, actor)
    selected, cover, enabled = _setting(db, org)
    if "PROPERTY_CASH_SUMMARY" in selected and not matrix.get(FEATURE_CASH, False):
        raise HTTPException(status_code=404, detail="Property Cash Summary unavailable.")
    stmt, owner, blocks = _snapshot(db, org, actor, statement_id)
    files: list[tuple[str, bytes, str]] = []
    if "OWNER_STATEMENT" in selected:
        try:
            payload = build_report_payload(
                db, organization_id=org, report_key="owner.statement",
                parameters={"statement_id": stmt.id}, current_user=actor,
            )
        except ReportDeliveryError as exc:
            raise HTTPException(status_code=422, detail="Frozen statement cannot be rendered.") from exc
        files.append((payload.filename, report_csv_bytes(payload), "text/csv"))
    if "PROPERTY_CASH_SUMMARY" in selected:
        payload = ReportPayload(
            title="Property Cash Summary",
            filename="owner-property-cash-summary-" + str(stmt.id) + ".csv",
            headers=("Property ID", "Property", "Ending Cash", "Required Reserves",
                     "Prepaid Rent", "Available Cash"),
            rows=tuple((
                row.property_id, row.property_name, row.ending_cash,
                row.required_reserves, row.prepaid_rent, row.available_cash,
            ) for row in blocks),
        )
        files.append((payload.filename, report_csv_bytes(payload), "text/csv"))
    subject = "Owner packet: " + stmt.period_start.isoformat() + " to " + stmt.period_end.isoformat()
    body = (cover.strip() + "\n\n" if cover and cover.strip() else "")
    body += "Attached are the selected frozen owner packet reports in CSV format."
    material = json.dumps({
        "actor_id": actor.id, "organization_id": org,
        "statement_id": stmt.id, "owner_id": owner.id,
        "recipient_email": owner.email,
        "subject": subject, "body": body,
        "email_enabled": enabled,
        "attachments": [(name, hashlib.sha256(content).hexdigest()) for name, content, _ in files],
    }, sort_keys=True, separators=(",", ":")).encode("utf-8")
    token = hmac.new(settings.SECRET_KEY.encode("utf-8"), material, hashlib.sha256).hexdigest()
    preview = OwnerPacketPreviewOut(
        statement_id=stmt.id, owner_id=owner.id, recipient_email=owner.email,
        period_start=stmt.period_start, period_end=stmt.period_end,
        attachment_filenames=[name for name, _, _ in files],
        cover_message=cover, email_enabled=enabled, review_token=token,
    )
    return Packet(preview=preview, files=tuple(files), subject=subject, body=body)
