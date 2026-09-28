"""Phase 4.5: read-only property RUBs readiness, not billing or allocation.

Existing utility bills are not necessarily chargeable to tenants. This API
deliberately does not expose utility account numbers or bill amounts.
"""
from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.property import Property, PropertyAssignment
from app.models.utility import PaidBy, PropertyUtility, UtilityBill
from app.models.user import User, UserRole
from app.routers.auth import get_current_user
from app.services.menu_resolver import permission_allows_user
from app.services.customer_features import resolve_customer_features

router = APIRouter(prefix="/api/properties", tags=["RUBs readiness"])
FEATURE_KEY = "release.properties.rubs"


@router.get("/{property_id}/rubs-readiness")
def rubs_readiness(
    property_id: int, response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if (current_user.organization_id is None or not current_user.is_active
        or current_user.deleted_at is not None
        or current_user.role not in {UserRole.ADMIN, UserRole.OWNER, UserRole.MANAGER}
        or not permission_allows_user(db, user=current_user, menu_key="PROPERTIES.ALL")):
        raise HTTPException(status_code=403, detail="Property permission required.")
    decision = next(
        (item for item in resolve_customer_features(db, user=current_user)
         if item.key == FEATURE_KEY), None,
    )
    if decision is None or not decision.allowed:
        raise HTTPException(status_code=404, detail="RUBs is not available.")
    prop = db.query(Property).filter(
        Property.id == property_id,
        Property.organization_id == current_user.organization_id,
        Property.is_active.is_(True),
        Property.deleted_at.is_(None),
    ).first()
    if prop is None:
        raise HTTPException(status_code=404, detail="Property not found.")
    if current_user.role == UserRole.MANAGER and not db.query(PropertyAssignment.id).filter(
        PropertyAssignment.property_id == prop.id,
        PropertyAssignment.user_id == current_user.id,
        PropertyAssignment.is_active.is_(True),
        PropertyAssignment.deleted_at.is_(None),
    ).first():
        raise HTTPException(status_code=404, detail="Property not found.")
    utilities = db.query(PropertyUtility).filter(
        PropertyUtility.property_id == prop.id,
        PropertyUtility.is_active.is_(True),
        PropertyUtility.deleted_at.is_(None),
        PropertyUtility.paid_by == PaidBy.SHARED,
    ).order_by(PropertyUtility.id).limit(101).all()
    if len(utilities) > 100:
        raise HTTPException(status_code=422, detail="Too many shared utilities for preview.")
    ids = [u.id for u in utilities]
    bills = (db.query(UtilityBill).filter(UtilityBill.utility_id.in_(ids))
             .order_by(UtilityBill.id.desc()).limit(501).all()) if ids else []
    if len(bills) > 500:
        raise HTTPException(status_code=422, detail="Too many utility bills for preview.")
    by_utility: dict[int, dict[str, object]] = {}
    for u in utilities:
        by_utility[u.id] = {
            "utility_id": u.id, "utility_type": u.utility_type.value,
            "bill_count": 0, "periods_complete": 0, "periods_missing_or_invalid": 0,
        }
    for bill in bills:
        item = by_utility[bill.utility_id]
        item["bill_count"] += 1
        if (bill.billing_period_start is not None and bill.billing_period_end is not None
            and bill.billing_period_start <= bill.billing_period_end):
            item["periods_complete"] += 1
        else:
            item["periods_missing_or_invalid"] += 1
    response.headers["Cache-Control"] = "no-store"
    return {
        "property_id": prop.id,
        "utility_count": len(by_utility),
        "items": list(by_utility.values()),
        "allocation_available": False,
        "billing_available": False,
        "meaning": "Read-only shared-utility inventory; periods do not establish allocation eligibility, permitted tenant charges or regulatory compliance.",
    }
