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
from app.models.owner_statement import OwnerStatement
from app.schemas.owner_statement import (
    OwnerStatementDetailOut,
    OwnerStatementListOut,
    OwnerStatementOut,
    StatementGenerateIn,
    StatementPreviewIn,
    StatementPreviewOut,
    StatementPropertyBlock,
)
from app.services.gl_posting import PostingError
from app.services.owner_statements import (
    preview_owner_statement,
    generate_owner_statement,
)


router = APIRouter(
    prefix="/api/accounting/owner-statements",
    tags=["Owner Statements"],
)


def _require_org(current_user: User) -> int:
    if current_user.organization_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User has no organization.",
        )
    return current_user.organization_id


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

    return OwnerStatementDetailOut(**base.model_dump(), properties=blocks)


# ============================================================
# POST /preview
# ============================================================

@router.post("/preview", response_model=StatementPreviewOut)
def preview_statement(
    payload: StatementPreviewIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org_id = _require_org(current_user)
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
    org_id = _require_org(current_user)
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
    org_id = _require_org(current_user)

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
# GET /{id}
# ============================================================

@router.get("/{statement_id}", response_model=OwnerStatementDetailOut)
def get_statement(
    statement_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org_id = _require_org(current_user)
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