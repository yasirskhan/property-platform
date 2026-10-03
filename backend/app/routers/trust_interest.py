"""Trust-interest configuration readiness only; no funds movement."""
from __future__ import annotations
from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.user import User
from app.routers.auth import get_current_user
from app.schemas.trust_interest import TrustInterestInput, TrustInterestOut
from app.services.trust_interest import read_interest, save_interest

router = APIRouter(prefix="/api/accounting/bank-accounts", tags=["Trust interest readiness"])


@router.get("/{bank_id}/interest-readiness", response_model=TrustInterestOut)
def get_interest_readiness(
    bank_id: int,
    response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = read_interest(db, bank_id=bank_id, current_user=current_user)
    response.headers["Cache-Control"] = "no-store"
    return result


@router.put("/{bank_id}/interest-readiness", response_model=TrustInterestOut)
def put_interest_readiness(
    bank_id: int,
    payload: TrustInterestInput,
    response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = save_interest(db, bank_id=bank_id, payload=payload, current_user=current_user)
    response.headers["Cache-Control"] = "no-store"
    return result
