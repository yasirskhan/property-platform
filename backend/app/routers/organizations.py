# ============================================================
# organizations.py (router)
# ------------------------------------------------------------
# Read-only endpoints for the current user's organization.
#
#   GET /organizations/{id}  -> {id, name}
#
# Security:
#   A user can ONLY fetch their own organization. Requesting a
#   different org's id returns 404 (not 403 — we don't even
#   confirm the other org exists). This keeps the isolation wall
#   solid.
# ============================================================

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.routers.auth import get_current_user
from app.models.user import User, Organization

router = APIRouter(prefix="/organizations", tags=["Organizations"])


@router.get("/{org_id}")
def get_organization(
    org_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # A user without an org can't fetch any org.
    if current_user.organization_id is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        )

    # Only your own org. Anything else looks like it doesn't exist.
    if current_user.organization_id != org_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        )

    org = (
        db.query(Organization)
        .filter(Organization.id == org_id)
        .first()
    )
    if org is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        )

    return {"id": org.id, "name": org.name}