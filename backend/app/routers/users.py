# ============================================================
# routers/users.py
# ------------------------------------------------------------
# Team management routes:
#
#   POST   /users/managers      owner/admin creates a manager
#   POST   /users/crew          owner/manager/admin creates crew
#   POST   /users/tenants       owner/manager/admin creates tenant
#   POST   /users/owners        admin creates owner
#   GET    /users               list users (filtered by role)
#   GET    /users/{user_id}     get one user
#   PATCH  /users/{user_id}     update user info
#   DELETE /users/{user_id}     deactivate user
#
#   POST   /properties/{id}/assignments      assign user to property
#   GET    /properties/{id}/assignments      list assignments
#   DELETE /assignments/{assignment_id}      remove assignment
#
# PERMISSION RULES:
#   - Admin can manage anyone.
#   - Owner can manage managers, crew, tenants within their org.
#   - Manager can manage crew and tenants within their org.
#   - Crew/Tenant: no access to these routes.
# ============================================================

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core import auth as auth_logic
from app.core.database import get_db
from app.models.property import Property, PropertyAssignment
from app.models.user import User, UserRole
from app.routers.auth import get_current_user
from app.routers.properties import check_property_access
from app.schemas.user import UserCreate, UserOut, UserUpdate


router = APIRouter(tags=["User Management"])


# ------------------------------------------------------------
# HELPERS
# ------------------------------------------------------------
def _require_role(current_user: User, *allowed: UserRole):
    """Raise 403 if the current user's role isn't in the allowed set."""
    if current_user.role not in allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Requires one of: {[r.value for r in allowed]}",
        )


def _scoped_org_id(current_user: User, provided_org_id: Optional[int]) -> int:
    """Force all customer-side staff to their own organization."""
    if current_user.organization_id is None:
        raise HTTPException(status_code=400, detail="User has no organization")
    if provided_org_id is not None and provided_org_id != current_user.organization_id:
        raise HTTPException(status_code=403, detail="Cannot create users outside your organization")
    return current_user.organization_id


# ------------------------------------------------------------
# CREATE MANAGERS
# ------------------------------------------------------------
@router.post("/users/managers", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_manager(
    payload: UserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Create a manager.
    - Admin: any organization.
    - Owner: their own organization.
    """
    _require_role(current_user, UserRole.ADMIN, UserRole.OWNER)

    # Force the role to MANAGER regardless of what was sent
    payload.role = UserRole.MANAGER
    payload.organization_id = _scoped_org_id(current_user, payload.organization_id)

    try:
        return auth_logic.create_user(db, payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ------------------------------------------------------------
# CREATE CREW
# ------------------------------------------------------------
@router.post("/users/crew", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_crew(
    payload: UserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Create a crew member.
    - Admin: any organization.
    - Owner: their own organization.
    - Manager: their own organization.
    """
    _require_role(current_user, UserRole.ADMIN, UserRole.OWNER, UserRole.MANAGER)

    payload.role = UserRole.CREW
    payload.organization_id = _scoped_org_id(current_user, payload.organization_id)

    try:
        return auth_logic.create_user(db, payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ------------------------------------------------------------
# CREATE TENANT
# ------------------------------------------------------------
@router.post("/users/tenants", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_tenant(
    payload: UserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Create a tenant.
    - Admin: any organization.
    - Owner: their own organization.
    - Manager: their own organization.
    """
    _require_role(current_user, UserRole.ADMIN, UserRole.OWNER, UserRole.MANAGER)

    payload.role = UserRole.TENANT
    payload.organization_id = _scoped_org_id(current_user, payload.organization_id)

    try:
        return auth_logic.create_user(db, payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ------------------------------------------------------------
# CREATE OWNERS (admin only)
# ------------------------------------------------------------
@router.post("/users/owners", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_owner(
    payload: UserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Create an owner. Admin only.
    """
    _require_role(current_user, UserRole.ADMIN)

    payload.role = UserRole.OWNER
    payload.organization_id = _scoped_org_id(current_user, payload.organization_id)

    try:
        return auth_logic.create_user(db, payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ------------------------------------------------------------
# LIST USERS
# ------------------------------------------------------------
@router.get("/users", response_model=List[UserOut])
def list_users(
    role: Optional[UserRole] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List users. Filter by role with ?role=manager etc.

    Visibility:
    - Admin: sees all users.
    - Owner: sees users in their organization (except other owners).
    - Manager: sees users in their organization with role crew.
    - Crew/Tenant: no access.
    """
    _require_role(current_user, UserRole.ADMIN, UserRole.OWNER, UserRole.MANAGER)

    q = db.query(User)

    if current_user.role == UserRole.ADMIN:
        q = q.filter(User.organization_id == current_user.organization_id)

    elif current_user.role == UserRole.OWNER:
        q = q.filter(User.organization_id == current_user.organization_id)
        q = q.filter(User.role != UserRole.OWNER)  # don't show other owners

    elif current_user.role == UserRole.MANAGER:
        q = q.filter(User.organization_id == current_user.organization_id)
        q = q.filter(User.role == UserRole.CREW)  # managers only see crew

    if role is not None:
        q = q.filter(User.role == role)

    return q.all()


# ------------------------------------------------------------
# GET ONE USER
# ------------------------------------------------------------
@router.get("/users/{user_id}", response_model=UserOut)
def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get a single user.
    Users can always get themselves. Otherwise same visibility as list_users.
    """
    target = auth_logic.get_user_by_id(db, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    # Users can view themselves
    if target.id == current_user.id:
        return target

    _require_role(current_user, UserRole.ADMIN, UserRole.OWNER, UserRole.MANAGER)

    if current_user.role == UserRole.ADMIN:
        if target.organization_id != current_user.organization_id:
            raise HTTPException(status_code=403, detail="Not in your organization")
        return target

    if current_user.role == UserRole.OWNER:
        if target.organization_id != current_user.organization_id:
            raise HTTPException(status_code=403, detail="Not in your organization")
        return target

    if current_user.role == UserRole.MANAGER:
        if target.organization_id != current_user.organization_id or target.role != UserRole.CREW:
            raise HTTPException(status_code=403, detail="Managers can only view crew in their organization")
        return target

    raise HTTPException(status_code=403, detail="Access denied")


# ------------------------------------------------------------
# UPDATE USER
# ------------------------------------------------------------
@router.patch("/users/{user_id}", response_model=UserOut)
def update_user(
    user_id: int,
    payload: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Update user details.
    Admin/Owner can update team members in scope. Users can update themselves.
    """
    target = auth_logic.get_user_by_id(db, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    # Users can edit their own basic info
    if target.id == current_user.id:
        allowed_fields = {"first_name", "last_name", "phone", "profile_photo_url"}
        updates = {k: v for k, v in payload.model_dump(exclude_unset=True).items() if k in allowed_fields}
        for field, value in updates.items():
            setattr(target, field, value)
        db.commit()
        db.refresh(target)
        return target

    _require_role(current_user, UserRole.ADMIN, UserRole.OWNER, UserRole.MANAGER)

    if current_user.role == UserRole.ADMIN:
        if target.organization_id != current_user.organization_id:
            raise HTTPException(status_code=403, detail="Not in your organization")
    elif current_user.role == UserRole.OWNER:
        if target.organization_id != current_user.organization_id:
            raise HTTPException(status_code=403, detail="Not in your organization")
    elif current_user.role == UserRole.MANAGER:
        if target.organization_id != current_user.organization_id or target.role != UserRole.CREW:
            raise HTTPException(status_code=403, detail="Managers can only update crew in their organization")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(target, field, value)

    db.commit()
    db.refresh(target)
    return target


# ------------------------------------------------------------
# DEACTIVATE USER (soft delete)
# ------------------------------------------------------------
@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def deactivate_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Deactivate a user (set is_active=False). Admin/Owner."""
    _require_role(current_user, UserRole.ADMIN, UserRole.OWNER)

    target = auth_logic.get_user_by_id(db, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    if target.id == current_user.id:
        raise HTTPException(status_code=400, detail="You cannot deactivate yourself")

    if target.organization_id != current_user.organization_id:
        raise HTTPException(status_code=403, detail="Not in your organization")

    target.is_active = False
    db.commit()
    return None


# ============================================================
# PROPERTY ASSIGNMENTS
# ============================================================

@router.post("/properties/{property_id}/assignments", response_model=dict, status_code=status.HTTP_201_CREATED)
def assign_user_to_property(
    property_id: int,
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Assign a manager or crew member to a property.
    - Admin: any property.
    - Owner: properties in their org.
    - Manager: properties they're already assigned to.
    """
    _require_role(current_user, UserRole.ADMIN, UserRole.OWNER, UserRole.MANAGER)

    prop = check_property_access(db, current_user, property_id)

    # Target user must exist and be manager or crew
    target = auth_logic.get_user_by_id(db, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    if target.role not in (UserRole.MANAGER, UserRole.CREW):
        raise HTTPException(status_code=400, detail="Can only assign managers and crew to properties")
    if target.organization_id != prop.organization_id:
        raise HTTPException(status_code=403, detail="User is not in this organization")

    # Already assigned?
    existing = (
        db.query(PropertyAssignment)
        .filter(
            PropertyAssignment.property_id == property_id,
            PropertyAssignment.user_id == user_id,
        )
        .first()
    )
    if existing:
        existing.is_active = True
        db.commit()
        return {"status": "already_assigned", "assignment_id": existing.id}

    assignment = PropertyAssignment(
        property_id=property_id,
        user_id=user_id,
        role=target.role,
    )
    db.add(assignment)
    db.commit()
    db.refresh(assignment)

    return {"status": "assigned", "assignment_id": assignment.id}


@router.get("/properties/{property_id}/assignments", response_model=List[dict])
def list_assignments(
    property_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all people assigned to a property."""
    _require_role(current_user, UserRole.ADMIN, UserRole.OWNER, UserRole.MANAGER)

    check_property_access(db, current_user, property_id)

    assignments = (
        db.query(PropertyAssignment)
        .filter(
            PropertyAssignment.property_id == property_id,
            PropertyAssignment.is_active == True,  # noqa: E712
        )
        .all()
    )

    result = []
    for a in assignments:
        u = auth_logic.get_user_by_id(db, a.user_id)
        if u:
            result.append({
                "assignment_id": a.id,
                "user_id": u.id,
                "email": u.email,
                "name": f"{u.first_name} {u.last_name}",
                "role": u.role.value,
            })
    return result


@router.delete("/assignments/{assignment_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_assignment(
    assignment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Remove a user from a property. Admin/Owner."""
    _require_role(current_user, UserRole.ADMIN, UserRole.OWNER)

    assignment = db.query(PropertyAssignment).filter(PropertyAssignment.id == assignment_id).first()
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")
    check_property_access(db, current_user, assignment.property_id)

    assignment.is_active = False
    db.commit()
    return None
