"""Platform-audience-only organization, plan, and staff-audit controls."""

from __future__ import annotations

import re
from typing import Iterable

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.regional_database import RegionRoutingError, get_database_url_for_region
from app.models.audit_log import AuditLog
from app.models.billing import Plan, PricingTier, Subscription
from app.models.platform_user import PlatformUser, PlatformUserRole
from app.models.user import Organization, SELF_SERVE_PENDING_BILLING_STATE
from app.routers.platform_auth import get_current_platform_user
from app.schemas.platform_admin import (
    PlatformAuditOut,
    PlatformOrganizationCreateIn,
    PlatformOrganizationOut,
    PlatformPlanCreateIn,
    PlatformPlanOut,
    PlatformPlanUpdateIn,
)
from app.services.audit import append_audit_log
from app.services.menu_seed import seed_menu_permissions_for_org


router = APIRouter(prefix="/api/platform/admin", tags=["Platform Admin"])

_ORG_VIEWERS = set(PlatformUserRole)
_ORG_CREATORS = {
    PlatformUserRole.PLATFORM_ADMIN,
    PlatformUserRole.PLATFORM_SALES,
}
_PLAN_VIEWERS = {
    PlatformUserRole.PLATFORM_ADMIN,
    PlatformUserRole.PLATFORM_SALES,
    PlatformUserRole.PLATFORM_BILLING,
}
_PLAN_MANAGERS = {
    PlatformUserRole.PLATFORM_ADMIN,
    PlatformUserRole.PLATFORM_BILLING,
}
_AUDIT_VIEWERS = {
    PlatformUserRole.PLATFORM_ADMIN,
    PlatformUserRole.PLATFORM_BILLING,
    PlatformUserRole.PLATFORM_TECH,
    PlatformUserRole.PLATFORM_SUPPORT,
    PlatformUserRole.PLATFORM_DEV,
}


def _require_role(user: PlatformUser, allowed: set[PlatformUserRole], detail: str) -> None:
    if user.role not in allowed:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


def _slugify(name: str) -> str:
    value = re.sub(r"[^a-z0-9]+", "-", name.strip().lower())
    value = re.sub(r"-+", "-", value).strip("-")
    return value or "org"


def _unique_slug(db: Session, base: str) -> str:
    if not db.query(Organization.id).filter(Organization.slug == base).first():
        return base
    suffix = 2
    while db.query(Organization.id).filter(
        Organization.slug == f"{base}-{suffix}"
    ).first():
        suffix += 1
    return f"{base}-{suffix}"


def _subscription_map(db: Session, organization_ids: Iterable[int]) -> dict[int, Subscription]:
    ids = list(organization_ids)
    if not ids:
        return {}
    rows = (
        db.query(Subscription)
        .filter(Subscription.organization_id.in_(ids))
        .all()
    )
    return {row.organization_id: row for row in rows}


def _organization_out(
    organization: Organization,
    subscription: Subscription | None,
) -> PlatformOrganizationOut:
    subscription_status = None
    plan_id = None
    plan_name = None
    if subscription is not None:
        subscription_status = (
            subscription.status.value
            if hasattr(subscription.status, "value")
            else str(subscription.status)
        )
        plan_id = subscription.plan_id
        plan_name = subscription.plan.name if subscription.plan is not None else None
    return PlatformOrganizationOut(
        id=organization.id,
        name=organization.name,
        slug=organization.slug,
        state=organization.state,
        currency=organization.currency,
        data_region=organization.data_region,
        is_active=bool(organization.is_active),
        subscription_status=subscription_status,
        plan_id=plan_id,
        plan_name=plan_name,
        created_at=organization.created_at,
    )


def _plan_out(plan: Plan) -> PlatformPlanOut:
    return PlatformPlanOut(
        id=plan.id,
        code=plan.code,
        name=plan.name,
        description=plan.description,
        is_active=bool(plan.is_active),
        module_keys=sorted(
            row.module.key for row in plan.modules if row.module is not None
        ),
        pricing_tiers=sorted(
            plan.pricing_tiers,
            key=lambda tier: (tier.min_properties, tier.id),
        ),
        created_at=plan.created_at,
        updated_at=plan.updated_at,
    )


def _validate_tiers(payload: PlatformPlanCreateIn) -> None:
    tiers = sorted(payload.pricing_tiers, key=lambda tier: tier.min_properties)
    previous_max: int | None = 0
    for index, tier in enumerate(tiers):
        if tier.max_properties is not None and tier.max_properties < tier.min_properties:
            raise HTTPException(
                status_code=400,
                detail="pricing tier max_properties must be >= min_properties",
            )
        if index and previous_max is None:
            raise HTTPException(
                status_code=400,
                detail="an open-ended pricing tier must be the final tier",
            )
        if index and previous_max is not None and tier.min_properties <= previous_max:
            raise HTTPException(
                status_code=400,
                detail="pricing tiers must not overlap",
            )
        previous_max = tier.max_properties


@router.get("/organizations", response_model=list[PlatformOrganizationOut])
def list_platform_organizations(
    q: str | None = Query(default=None, max_length=255),
    organization_state: str | None = Query(default=None, alias="state", max_length=20),
    limit: int = Query(default=100, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
) -> list[PlatformOrganizationOut]:
    _require_role(current_user, _ORG_VIEWERS, "Platform organization access required")
    query = db.query(Organization)
    if q:
        term = f"%{q.strip()}%"
        query = query.filter(or_(Organization.name.ilike(term), Organization.slug.ilike(term)))
    if organization_state:
        query = query.filter(Organization.state == organization_state.strip().upper())
    organizations = query.order_by(Organization.created_at.desc(), Organization.id.desc()).limit(limit).all()
    subscriptions = _subscription_map(db, (org.id for org in organizations))
    return [_organization_out(org, subscriptions.get(org.id)) for org in organizations]


@router.get("/organizations/{organization_id}", response_model=PlatformOrganizationOut)
def get_platform_organization(
    organization_id: int,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
) -> PlatformOrganizationOut:
    _require_role(current_user, _ORG_VIEWERS, "Platform organization access required")
    organization = db.get(Organization, organization_id)
    if organization is None:
        raise HTTPException(status_code=404, detail="Organization not found")
    subscription = (
        db.query(Subscription)
        .filter(Subscription.organization_id == organization.id)
        .first()
    )
    return _organization_out(organization, subscription)


@router.post(
    "/organizations",
    response_model=PlatformOrganizationOut,
    status_code=status.HTTP_201_CREATED,
)
def create_platform_organization(
    payload: PlatformOrganizationCreateIn,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
) -> PlatformOrganizationOut:
    _require_role(
        current_user,
        _ORG_CREATORS,
        "Platform admin or sales role required to create organizations",
    )
    try:
        get_database_url_for_region(payload.data_region)
    except RegionRoutingError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    organization = Organization(
        name=payload.name.strip(),
        slug=_unique_slug(db, _slugify(payload.name)),
        state=SELF_SERVE_PENDING_BILLING_STATE,
        currency=payload.currency,
        data_region=payload.data_region,
        is_active=True,
    )
    db.add(organization)
    db.flush()
    seed_menu_permissions_for_org(db, organization.id)
    append_audit_log(
        db,
        platform_user_id=current_user.id,
        organization_id=organization.id,
        entity_type="organization",
        entity_id=organization.id,
        action="platform_created",
        new_value={
            "name": organization.name,
            "slug": organization.slug,
            "state": organization.state,
            "currency": organization.currency,
            "data_region": organization.data_region,
        },
    )
    db.commit()
    db.refresh(organization)
    return _organization_out(organization, None)


@router.get("/plans", response_model=list[PlatformPlanOut])
def list_platform_plans(
    include_inactive: bool = Query(default=True),
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
) -> list[PlatformPlanOut]:
    _require_role(current_user, _PLAN_VIEWERS, "Platform plan access required")
    query = db.query(Plan)
    if not include_inactive:
        query = query.filter(Plan.is_active.is_(True))
    return [_plan_out(row) for row in query.order_by(Plan.id.asc()).all()]


@router.post("/plans", response_model=PlatformPlanOut, status_code=status.HTTP_201_CREATED)
def create_platform_plan(
    payload: PlatformPlanCreateIn,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
) -> PlatformPlanOut:
    _require_role(current_user, _PLAN_MANAGERS, "Platform admin or billing role required")
    _validate_tiers(payload)
    if db.query(Plan.id).filter(Plan.code == payload.code).first():
        raise HTTPException(status_code=409, detail="Plan code already exists")

    plan = Plan(
        code=payload.code,
        name=payload.name.strip(),
        description=payload.description,
        is_active=True,
    )
    db.add(plan)
    db.flush()
    for tier in sorted(payload.pricing_tiers, key=lambda row: row.min_properties):
        db.add(
            PricingTier(
                plan_id=plan.id,
                min_properties=tier.min_properties,
                max_properties=tier.max_properties,
                monthly_price_cents=tier.monthly_price_cents,
                currency=tier.currency,
            )
        )
    db.flush()
    append_audit_log(
        db,
        platform_user_id=current_user.id,
        entity_type="plan",
        entity_id=plan.id,
        action="platform_created",
        new_value={
            "code": plan.code,
            "name": plan.name,
            "is_active": plan.is_active,
            "pricing_tiers": [
                {
                    "min_properties": tier.min_properties,
                    "max_properties": tier.max_properties,
                    "monthly_price_cents": tier.monthly_price_cents,
                    "currency": tier.currency,
                }
                for tier in payload.pricing_tiers
            ],
        },
    )
    db.commit()
    db.refresh(plan)
    return _plan_out(plan)


@router.patch("/plans/{plan_id}", response_model=PlatformPlanOut)
def update_platform_plan(
    plan_id: int,
    payload: PlatformPlanUpdateIn,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
) -> PlatformPlanOut:
    _require_role(current_user, _PLAN_MANAGERS, "Platform admin or billing role required")
    plan = db.get(Plan, plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Plan not found")

    before = {
        "name": plan.name,
        "description": plan.description,
        "is_active": bool(plan.is_active),
    }
    if "name" in payload.model_fields_set:
        plan.name = (payload.name or "").strip()
    if "description" in payload.model_fields_set:
        plan.description = payload.description
    if "is_active" in payload.model_fields_set:
        plan.is_active = bool(payload.is_active)

    after = {
        "name": plan.name,
        "description": plan.description,
        "is_active": bool(plan.is_active),
    }
    append_audit_log(
        db,
        platform_user_id=current_user.id,
        entity_type="plan",
        entity_id=plan.id,
        action="platform_updated",
        old_value=before,
        new_value=after,
    )
    db.commit()
    db.refresh(plan)
    return _plan_out(plan)


@router.get("/audit", response_model=list[PlatformAuditOut])
def list_platform_audit(
    entity_type: str | None = Query(default=None, max_length=50),
    organization_id: int | None = Query(default=None, ge=1),
    platform_user_id: int | None = Query(default=None, ge=1),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
) -> list[PlatformAuditOut]:
    _require_role(current_user, _AUDIT_VIEWERS, "Platform audit access required")
    query = db.query(AuditLog).filter(AuditLog.platform_user_id.is_not(None))
    if entity_type:
        query = query.filter(AuditLog.entity_type == entity_type.strip())
    if organization_id is not None:
        query = query.filter(AuditLog.organization_id == organization_id)
    if platform_user_id is not None:
        query = query.filter(AuditLog.platform_user_id == platform_user_id)

    rows = query.order_by(AuditLog.created_at.desc(), AuditLog.id.desc()).limit(limit).all()
    return [
        PlatformAuditOut(
            id=row.id,
            platform_user_id=row.platform_user_id,
            platform_user_email=row.platform_user.email if row.platform_user else None,
            organization_id=row.organization_id,
            entity_type=row.entity_type,
            entity_id=row.entity_id,
            action=row.action,
            field_name=row.field_name,
            old_value=row.old_value,
            new_value=row.new_value,
            ip_address=row.ip_address,
            created_at=row.created_at,
        )
        for row in rows
    ]
