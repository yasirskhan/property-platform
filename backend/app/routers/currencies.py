# ============================================================
# currencies.py
# ------------------------------------------------------------
# Per-org currency CRUD.
#
#   GET    /api/settings/currencies            list
#   POST   /api/settings/currencies            add
#   PATCH  /api/settings/currencies/{id}       edit name/symbol/locale
#   DELETE /api/settings/currencies/{id}       soft delete (is_active=0)
#
# Rules:
#   - Read: any logged-in user in the org.
#   - Write: ADMIN or OWNER only.
#   - Cannot delete is_system=True rows.
#   - Cannot delete the currency currently selected on the org.
#   - Cannot add a duplicate code within the same org.
#
# See PROJECT_MASTER.md Section 68.
# ============================================================

import re
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.routers.auth import get_current_user
from app.models.user import User, Organization
from app.models.currency import Currency
from app.services.menu_resolver import permission_allows_user


router = APIRouter(prefix="/api/settings/currencies", tags=["currencies"])


CODE_RE = re.compile(r"^[A-Z]{3}$")


# ------------------------------------------------------------
# Helpers
# ------------------------------------------------------------
def _role(user: User) -> str:
    return (user.role.value if hasattr(user.role, "value") else str(user.role)).upper()


def _require_writer(user: User) -> None:
    if _role(user) not in ("ADMIN", "OWNER"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only ADMIN or OWNER can manage currencies.",
        )


def _get_org(db: Session, user: User) -> Organization:
    if user.organization_id is None:
        raise HTTPException(status_code=400, detail="User has no organization.")
    org = db.query(Organization).filter(Organization.id == user.organization_id).first()
    if org is None:
        raise HTTPException(status_code=404, detail="Organization not found.")
    return org


def _require_currency_access(db: Session, user: User) -> Organization:
    org = _get_org(db, user)
    if not permission_allows_user(
        db,
        user=user,
        menu_key="SETTINGS.CURRENCIES",
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Currencies permission required.",
        )
    return org


def _find_currency(db: Session, org_id: int, code: str) -> Currency | None:
    return (
        db.query(Currency)
        .filter(Currency.organization_id == org_id, Currency.code == code)
        .first()
    )


# ------------------------------------------------------------
# Schemas
# ------------------------------------------------------------
class CurrencyOut(BaseModel):
    id: int
    code: str
    name: str
    symbol: str
    locale: str
    decimal_places: int
    is_system: bool
    is_active: bool

    class Config:
        from_attributes = True


class CurrencyCreateIn(BaseModel):
    code: str = Field(..., min_length=3, max_length=3)
    name: str = Field(..., min_length=1, max_length=100)
    symbol: str = Field(..., min_length=1, max_length=10)
    locale: str = Field(..., min_length=2, max_length=20)
    decimal_places: int = Field(2, ge=0, le=4)


class CurrencyUpdateIn(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    symbol: str | None = Field(None, min_length=1, max_length=10)
    locale: str | None = Field(None, min_length=2, max_length=20)
    decimal_places: int | None = Field(None, ge=0, le=4)
    is_active: bool | None = None


# ------------------------------------------------------------
# GET /api/settings/currencies
# ------------------------------------------------------------
@router.get("", response_model=list[CurrencyOut])
def list_currencies(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    org = _require_currency_access(db, user)
    rows = (
        db.query(Currency)
        .filter(Currency.organization_id == org.id)
        .order_by(Currency.code.asc())
        .all()
    )
    return rows


# ------------------------------------------------------------
# POST /api/settings/currencies
# ------------------------------------------------------------
@router.post("", response_model=CurrencyOut, status_code=status.HTTP_201_CREATED)
def create_currency(
    payload: CurrencyCreateIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_writer(user)
    org = _require_currency_access(db, user)

    code = payload.code.upper()
    if not CODE_RE.match(code):
        raise HTTPException(status_code=422, detail="Currency code must be 3 uppercase letters.")

    if _find_currency(db, org.id, code) is not None:
        raise HTTPException(status_code=409, detail=f"Currency {code} already exists in your org.")

    row = Currency(
        organization_id=org.id,
        code=code,
        name=payload.name,
        symbol=payload.symbol,
        locale=payload.locale,
        decimal_places=payload.decimal_places,
        is_system=False,
        is_active=True,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


# ------------------------------------------------------------
# PATCH /api/settings/currencies/{currency_id}
# ------------------------------------------------------------
@router.patch("/{currency_id}", response_model=CurrencyOut)
def update_currency(
    currency_id: int,
    payload: CurrencyUpdateIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_writer(user)
    org = _require_currency_access(db, user)

    row = (
        db.query(Currency)
        .filter(Currency.id == currency_id, Currency.organization_id == org.id)
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Currency not found.")

    if payload.name is not None:
        row.name = payload.name
    if payload.symbol is not None:
        row.symbol = payload.symbol
    if payload.locale is not None:
        row.locale = payload.locale
    if payload.decimal_places is not None:
        row.decimal_places = payload.decimal_places
    if payload.is_active is not None:
        # refuse to deactivate the org's current currency
        if not payload.is_active and row.code == (getattr(org, "currency", None) or "USD"):
            raise HTTPException(
                status_code=400,
                detail="Cannot deactivate the currency currently in use by your organization.",
            )
        row.is_active = payload.is_active

    row.updated_at = datetime.utcnow()
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


# ------------------------------------------------------------
# DELETE /api/settings/currencies/{currency_id}
# ------------------------------------------------------------
@router.delete("/{currency_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_currency(
    currency_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_writer(user)
    org = _require_currency_access(db, user)

    row = (
        db.query(Currency)
        .filter(Currency.id == currency_id, Currency.organization_id == org.id)
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Currency not found.")

    if row.is_system:
        raise HTTPException(status_code=400, detail="System currencies cannot be deleted.")

    if row.code == (getattr(org, "currency", None) or "USD"):
        raise HTTPException(
            status_code=400,
            detail="Cannot delete the currency currently in use by your organization.",
        )

    row.is_active = False
    row.updated_at = datetime.utcnow()
    db.add(row)
    db.commit()
    return None