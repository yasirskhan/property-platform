# ============================================================
# routers/utilities.py
# ------------------------------------------------------------
# Property utilities, bills, trash pickup schedule.
# ============================================================

from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.audit import log_action
from app.core.database import get_db
from app.models.utility import (
    PropertyUtility,
    UtilityBill,
    TrashPickupSchedule,
)
from app.models.user import User, UserRole
from app.routers.auth import get_current_user
from app.routers.properties import check_property_access, require_non_tenant
from app.schemas.utility import (
    PropertyUtilityCreate,
    PropertyUtilityUpdate,
    PropertyUtilityAdminOut,
    PropertyUtilityOut,
    PropertyUtilityWithBills,
    UtilityBillCreate,
    UtilityBillOut,
    TrashScheduleCreate,
    TrashScheduleUpdate,
    TrashScheduleOut,
)


router = APIRouter(tags=["Utilities"])


def _require_manage(current_user: User):
    if current_user.role not in (UserRole.ADMIN, UserRole.OWNER, UserRole.MANAGER):
        raise HTTPException(status_code=403, detail="Not allowed")


def _get_utility(db: Session, utility_id: int) -> PropertyUtility:
    u = db.query(PropertyUtility).filter(PropertyUtility.id == utility_id).first()
    if not u:
        raise HTTPException(status_code=404, detail="Utility not found")
    return u


# ============================================================
# PROPERTY UTILITIES
# ============================================================
@router.get("/properties/{property_id}/utilities", response_model=List[PropertyUtilityAdminOut])
def list_utilities(
    property_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_non_tenant(current_user)
    check_property_access(db, current_user, property_id)
    return db.query(PropertyUtility).filter(PropertyUtility.property_id == property_id).all()


@router.post(
    "/properties/{property_id}/utilities",
    response_model=PropertyUtilityAdminOut,
    status_code=status.HTTP_201_CREATED,
)
def create_utility(
    property_id: int,
    payload: PropertyUtilityCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_non_tenant(current_user)
    _require_manage(current_user)
    check_property_access(db, current_user, property_id)

    u = PropertyUtility(property_id=property_id, **payload.model_dump())
    db.add(u)
    db.commit()
    db.refresh(u)

    log_action(db, current_user, entity_type="property_utility", entity_id=u.id, action="created",
               new_value={"company": u.company_name, "type": u.utility_type.value})
    return u


@router.get("/properties/{property_id}/utilities/{utility_id}", response_model=PropertyUtilityWithBills)
def get_utility(
    property_id: int,
    utility_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_non_tenant(current_user)
    check_property_access(db, current_user, property_id)
    return _get_utility(db, utility_id)


@router.patch(
    "/properties/{property_id}/utilities/{utility_id}",
    response_model=PropertyUtilityAdminOut,
)
def update_utility(
    property_id: int,
    utility_id: int,
    payload: PropertyUtilityUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_non_tenant(current_user)
    _require_manage(current_user)
    check_property_access(db, current_user, property_id)

    u = _get_utility(db, utility_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(u, field, value)
    db.commit()
    db.refresh(u)
    return u


@router.delete("/properties/{property_id}/utilities/{utility_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_utility(
    property_id: int,
    utility_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_non_tenant(current_user)
    _require_manage(current_user)
    check_property_access(db, current_user, property_id)
    u = _get_utility(db, utility_id)
    db.delete(u)
    db.commit()
    log_action(db, current_user, entity_type="property_utility", entity_id=utility_id, action="deleted")
    return None


# ============================================================
# UTILITY BILLS
# ============================================================
@router.get("/properties/{property_id}/utilities/{utility_id}/bills", response_model=List[UtilityBillOut])
def list_bills(
    property_id: int,
    utility_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_non_tenant(current_user)
    check_property_access(db, current_user, property_id)
    return (
        db.query(UtilityBill)
        .filter(UtilityBill.utility_id == utility_id)
        .order_by(UtilityBill.billing_period_start.desc())
        .all()
    )


@router.post(
    "/properties/{property_id}/utilities/{utility_id}/bills",
    response_model=UtilityBillOut,
    status_code=status.HTTP_201_CREATED,
)
def create_bill(
    property_id: int,
    utility_id: int,
    payload: UtilityBillCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_non_tenant(current_user)
    _require_manage(current_user)
    check_property_access(db, current_user, property_id)

    b = UtilityBill(utility_id=utility_id, created_by_id=current_user.id, **payload.model_dump())
    db.add(b)
    db.commit()
    db.refresh(b)
    log_action(db, current_user, entity_type="utility_bill", entity_id=b.id, action="created",
               new_value={"amount": float(b.amount)})
    return b


# ============================================================
# TRASH PICKUP SCHEDULE
# ============================================================
@router.get("/properties/{property_id}/trash-schedule", response_model=List[TrashScheduleOut])
def list_trash_schedule(
    property_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_non_tenant(current_user)
    check_property_access(db, current_user, property_id)
    return db.query(TrashPickupSchedule).filter(TrashPickupSchedule.property_id == property_id).all()


@router.post(
    "/properties/{property_id}/trash-schedule",
    response_model=TrashScheduleOut,
    status_code=status.HTTP_201_CREATED,
)
def create_trash_schedule(
    property_id: int,
    payload: TrashScheduleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_non_tenant(current_user)
    _require_manage(current_user)
    check_property_access(db, current_user, property_id)

    s = TrashPickupSchedule(property_id=property_id, **payload.model_dump())
    db.add(s)
    db.commit()
    db.refresh(s)
    return s


@router.patch(
    "/properties/{property_id}/trash-schedule/{schedule_id}",
    response_model=TrashScheduleOut,
)
def update_trash_schedule(
    property_id: int,
    schedule_id: int,
    payload: TrashScheduleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_non_tenant(current_user)
    _require_manage(current_user)
    check_property_access(db, current_user, property_id)

    s = db.query(TrashPickupSchedule).filter(
        TrashPickupSchedule.id == schedule_id,
        TrashPickupSchedule.property_id == property_id,
    ).first()
    if not s:
        raise HTTPException(status_code=404, detail="Schedule not found")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(s, field, value)
    db.commit()
    db.refresh(s)
    return s


@router.delete("/properties/{property_id}/trash-schedule/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_trash_schedule(
    property_id: int,
    schedule_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_non_tenant(current_user)
    _require_manage(current_user)
    check_property_access(db, current_user, property_id)
    s = db.query(TrashPickupSchedule).filter(
        TrashPickupSchedule.id == schedule_id,
        TrashPickupSchedule.property_id == property_id,
    ).first()
    if not s:
        raise HTTPException(status_code=404, detail="Schedule not found")
    db.delete(s)
    db.commit()
    return None