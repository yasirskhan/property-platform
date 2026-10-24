# ============================================================
# owner_statements.py (router)
# ------------------------------------------------------------
#   POST /api/accounting/owner-statements/preview    compute (no save)
#   POST /api/accounting/owner-statements/generate   freeze & save
#   GET  /api/accounting/owner-statements            list
#   GET  /api/accounting/owner-statements/{id}       detail (expanded)
# ============================================================

import json
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload

from app.core.database import get_db
from app.routers.auth import get_current_user
from app.models.user import User
from app.models.owner_statement import OwnerPacketSettings, OwnerStatement
from app.schemas.owner_statement import (
    OwnerStatementDetailOut,
    OwnerStatementListOut,
    OwnerStatementOut,
    StatementGenerateIn,
    StatementPreviewIn,
    StatementPreviewOut,
    StatementPropertyBlock,
    PropertyCashSummaryLine,
    OwnerStatementCashSummaryOut,
    OwnerPacketSettingsOut,
    OwnerPacketSettingsUpdate,
)
from app.services.gl_posting import PostingError
from app.services.audit import append_audit_log
from app.services.menu_resolver import permission_allows_user
from app.services.customer_features import resolve_customer_features
from app.services.owner_statements import (
    preview_owner_statement,
    generate_owner_statement,
)


router = APIRouter(
    prefix="/api/accounting/owner-statements",
    tags=["Owner Statements"],
)

WRITE_ROLES = {"ADMIN", "OWNER", "MANAGER"}
CASH_SUMMARY_FEATURE = "release.accounting.owner_statements.cash_summary"
PACKET_CUSTOMIZER_FEATURE = "release.owner_portal.packet_customizer"
PACKET_WRITE_ROLES = {"ADMIN", "MANAGER"}
DEFAULT_PACKET_REPORTS = ["OWNER_STATEMENT", "PROPERTY_CASH_SUMMARY"]


def _require_org(current_user: User) -> int:
    if current_user.organization_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User has no organization.",
        )
    return current_user.organization_id


def _norm_role(role) -> str:
    if role is None:
        return ""
    value = role.value if hasattr(role, "value") else str(role)
    return value.upper()


def _require_owner_statements_access(db: Session, current_user: User) -> int:
    org_id = _require_org(current_user)
    if not permission_allows_user(
        db, user=current_user, menu_key="ACCOUNTING.OWNER_STATEMENTS"
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Owner Statements permission required.",
        )
    return org_id


def _require_cash_summary_feature(db: Session, current_user: User) -> int:
    org_id = _require_owner_statements_access(db, current_user)
    decision = next(
        (
            item
            for item in resolve_customer_features(db, user=current_user)
            if item.key == CASH_SUMMARY_FEATURE
        ),
        None,
    )
    if decision is None or not decision.allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Property Cash Summary is not enabled.",
        )
    return org_id


def _require_packet_customizer_feature(db: Session, current_user: User) -> int:
    org_id = _require_owner_statements_access(db, current_user)
    decision = next(
        (
            item
            for item in resolve_customer_features(db, user=current_user)
            if item.key == PACKET_CUSTOMIZER_FEATURE
        ),
        None,
    )
    if decision is None or not decision.allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Owner Packet customizer is not enabled.",
        )
    return org_id


def _require_packet_settings_write(current_user: User) -> None:
    if _norm_role(current_user.role) not in PACKET_WRITE_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators and managers may change owner packet settings.",
        )


def _packet_settings_out(
    organization_id: int, row: Optional[OwnerPacketSettings]
) -> OwnerPacketSettingsOut:
    reports = DEFAULT_PACKET_REPORTS
    if row is not None:
        try:
            parsed = json.loads(row.included_reports or "[]")
            if isinstance(parsed, list) and parsed:
                reports = [str(item) for item in parsed]
        except Exception:
            reports = DEFAULT_PACKET_REPORTS
    return OwnerPacketSettingsOut(
        organization_id=organization_id,
        included_reports=reports,
        email_owner=bool(row.email_owner) if row is not None else False,
        cover_message=row.cover_message if row is not None else None,
    )


def _require_write(current_user: User) -> None:
    if _norm_role(current_user.role) not in WRITE_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not allowed to generate owner statements.",
        )


def _stmt_to_out(s: OwnerStatement) -> OwnerStatementOut:
    return OwnerStatementOut(
        id=s.id,
        organization_id=s.organization_id,
        owner_id=s.owner_id,
        owner_email=s.owner.email if s.owner else None,
        owner_name=(
            getattr(s.owner, "full_name", None) if s.owner else None
        ),
        period_start=s.period_start,
        period_end=s.period_end,
        generated_at=s.generated_at,
        total_beginning_cash=s.total_beginning_cash,
        total_ending_cash=s.total_ending_cash,
        total_income=s.total_income,
        total_expense=s.total_expense,
        total_net=s.total_net,
        pdf_url=s.pdf_url,
        notes=s.notes,
        is_active=s.is_active,
        generated_by_id=s.generated_by_id,
        created_at=s.created_at,
        updated_at=s.updated_at,
    )


def _stmt_to_detail(s: OwnerStatement) -> OwnerStatementDetailOut:
    base = _stmt_to_out(s)

    try:
        raw = json.loads(s.property_data or "[]")
    except Exception:
        raw = []

    blocks = []
    for b in raw:
        try:
            blocks.append(StatementPropertyBlock(**b))
        except Exception:
            continue

    total_required_reserves = sum((b.required_reserves for b in blocks), start=0)
    total_prepaid_rent = sum((b.prepaid_rent for b in blocks), start=0)
    total_available_cash = sum((b.available_cash for b in blocks), start=0)
    return OwnerStatementDetailOut(
        **base.model_dump(),
        properties=blocks,
        total_required_reserves=total_required_reserves,
        total_prepaid_rent=total_prepaid_rent,
        total_available_cash=total_available_cash,
    )


# ============================================================
# GET/PUT /packet-settings
# ============================================================

@router.get("/packet-settings", response_model=OwnerPacketSettingsOut)
def get_packet_settings(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org_id = _require_packet_customizer_feature(db, current_user)
    row = db.get(OwnerPacketSettings, org_id)
    return _packet_settings_out(org_id, row)


@router.put("/packet-settings", response_model=OwnerPacketSettingsOut)
def update_packet_settings(
    payload: OwnerPacketSettingsUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_packet_settings_write(current_user)
    org_id = _require_packet_customizer_feature(db, current_user)
    row = db.get(OwnerPacketSettings, org_id)
    old_value = None
    if row is None:
        row = OwnerPacketSettings(organization_id=org_id)
        db.add(row)
    else:
        old_value = json.dumps(
            {
                "included_reports": _packet_settings_out(org_id, row).included_reports,
                "email_owner": bool(row.email_owner),
                "cover_message": row.cover_message,
            },
            sort_keys=True,
        )

    row.included_reports = json.dumps(payload.included_reports, separators=(",", ":"))
    row.email_owner = payload.email_owner
    row.cover_message = payload.cover_message.strip() if payload.cover_message else None
    db.flush()
    new_value = json.dumps(
        {
            "included_reports": payload.included_reports,
            "email_owner": payload.email_owner,
            "cover_message": row.cover_message,
        },
        sort_keys=True,
    )
    append_audit_log(
        db,
        user_id=current_user.id,
        organization_id=org_id,
        entity_type="owner_packet_settings",
        entity_id=org_id,
        action="owner_packet_settings_updated",
        old_value=old_value,
        new_value=new_value,
    )
    db.commit()
    db.refresh(row)
    return _packet_settings_out(org_id, row)


# ============================================================
# POST /preview
# ============================================================

@router.post("/preview", response_model=StatementPreviewOut)
def preview_statement(
    payload: StatementPreviewIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_write(current_user)
    org_id = _require_owner_statements_access(db, current_user)
    try:
        result = preview_owner_statement(
            db,
            organization_id=org_id,
            owner_id=payload.owner_id,
            period_start=payload.period_start,
            period_end=payload.period_end,
        )
    except PostingError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Convert property dicts to schema objects
    blocks = [StatementPropertyBlock(**b) for b in result["properties"]]

    return StatementPreviewOut(
        owner_id=result["owner_id"],
        owner_email=result["owner_email"],
        owner_name=result["owner_name"],
        period_start=result["period_start"],
        period_end=result["period_end"],
        total_beginning_cash=result["total_beginning_cash"],
        total_ending_cash=result["total_ending_cash"],
        total_income=result["total_income"],
        total_expense=result["total_expense"],
        total_net=result["total_net"],
        total_required_reserves=result["total_required_reserves"],
        total_prepaid_rent=result["total_prepaid_rent"],
        total_available_cash=result["total_available_cash"],
        properties=blocks,
        can_generate=result["can_generate"],
        reason=result["reason"],
    )


# ============================================================
# POST /generate
# ============================================================

@router.post(
    "/generate",
    response_model=OwnerStatementDetailOut,
    status_code=status.HTTP_201_CREATED,
)
def generate_statement(
    payload: StatementGenerateIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_write(current_user)
    org_id = _require_owner_statements_access(db, current_user)
    try:
        stmt = generate_owner_statement(
            db,
            organization_id=org_id,
            owner_id=payload.owner_id,
            period_start=payload.period_start,
            period_end=payload.period_end,
            notes=payload.notes,
            created_by=current_user,
        )
    except PostingError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Reload with relationship
    stmt = (
        db.query(OwnerStatement)
        .options(joinedload(OwnerStatement.owner))
        .filter(OwnerStatement.id == stmt.id)
        .first()
    )
    return _stmt_to_detail(stmt)


# ============================================================
# GET ""
# ============================================================

@router.get("", response_model=OwnerStatementListOut)
def list_statements(
    owner_id: Optional[int] = Query(None),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    limit: int = Query(200, ge=1, le=2000),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org_id = _require_owner_statements_access(db, current_user)

    q = (
        db.query(OwnerStatement)
        .options(joinedload(OwnerStatement.owner))
        .filter(OwnerStatement.organization_id == org_id)
        .filter(OwnerStatement.is_active.is_(True))
    )
    if owner_id is not None:
        q = q.filter(OwnerStatement.owner_id == owner_id)
    if date_from is not None:
        q = q.filter(OwnerStatement.period_end >= date_from)
    if date_to is not None:
        q = q.filter(OwnerStatement.period_start <= date_to)

    total = q.count()
    rows = (
        q.order_by(
            OwnerStatement.period_end.desc(),
            OwnerStatement.id.desc(),
        )
        .limit(limit)
        .all()
    )

    return OwnerStatementListOut(
        items=[_stmt_to_out(r) for r in rows],
        total=total,
    )


# ============================================================
# GET /{id}/cash-summary
# ============================================================

@router.get("/{statement_id}/cash-summary", response_model=OwnerStatementCashSummaryOut)
def get_statement_cash_summary(
    statement_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org_id = _require_cash_summary_feature(db, current_user)
    stmt = (
        db.query(OwnerStatement)
        .options(joinedload(OwnerStatement.owner))
        .filter(
            OwnerStatement.id == statement_id,
            OwnerStatement.organization_id == org_id,
        )
        .first()
    )
    if stmt is None:
        raise HTTPException(status_code=404, detail="Statement not found.")

    detail = _stmt_to_detail(stmt)
    return OwnerStatementCashSummaryOut(
        statement_id=stmt.id,
        total_ending_cash=detail.total_ending_cash,
        total_required_reserves=detail.total_required_reserves,
        total_prepaid_rent=detail.total_prepaid_rent,
        total_available_cash=detail.total_available_cash,
        properties=[
            PropertyCashSummaryLine(
                property_id=row.property_id,
                property_name=row.property_name,
                ending_cash=row.ending_cash,
                required_reserves=row.required_reserves,
                prepaid_rent=row.prepaid_rent,
                available_cash=row.available_cash,
            )
            for row in detail.properties
        ],
    )


# ============================================================
# GET /{id}
# ============================================================

@router.get("/{statement_id}", response_model=OwnerStatementDetailOut)
def get_statement(
    statement_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org_id = _require_owner_statements_access(db, current_user)
    stmt = (
        db.query(OwnerStatement)
        .options(joinedload(OwnerStatement.owner))
        .filter(
            OwnerStatement.id == statement_id,
            OwnerStatement.organization_id == org_id,
        )
        .first()
    )
    if stmt is None:
        raise HTTPException(status_code=404, detail="Statement not found.")
    return _stmt_to_detail(stmt)