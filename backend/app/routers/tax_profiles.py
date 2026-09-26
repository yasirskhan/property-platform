"""Admin-only encrypted tax-profile intake and paper W-9 tracking."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.user import User
from app.routers.auth import get_current_user
from app.schemas.tax_profile import TaxProfileOut, TaxProfileUpsertIn
from app.services.tax_profiles import list_tax_profiles, upsert_tax_profile

router = APIRouter(prefix="/api/reporting/tax-profiles", tags=["Tax profile readiness"])


@router.get("", response_model=list[TaxProfileOut])
def list_profiles(
    response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    response.headers["Cache-Control"] = "no-store"
    return list_tax_profiles(db, current_user=current_user)


@router.put("", response_model=TaxProfileOut)
def save_profile(
    payload: TaxProfileUpsertIn,
    response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    response.headers["Cache-Control"] = "no-store"
    return upsert_tax_profile(db, current_user=current_user, payload=payload)
