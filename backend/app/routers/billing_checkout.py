"""Customer-side Stripe Checkout and signed webhook endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.user import User, UserRole
from app.routers.auth import get_current_user
from app.schemas.billing_checkout import CheckoutSessionCreate, CheckoutSessionOut
from app.schemas.billing_read import BillingCatalogOut, BillingStateOut
from app.services.billing_read import (
    get_active_billing_catalog,
    get_organization_billing_state,
)
from app.services.stripe_billing import (
    BillingWebhookIntegrityError,
    CheckoutIdempotencyConflict,
    InvalidStripeWebhook,
    StripeBillingUnavailable,
    StripeProviderError,
    construct_stripe_event,
    create_checkout_session,
    process_stripe_event,
)


router = APIRouter(prefix="/api/billing", tags=["Billing"])


def _billing_admin_organization_id(current_user: User) -> int:
    if current_user.organization_id is None:
        raise HTTPException(status_code=400, detail="Organization is required")
    if current_user.role not in {UserRole.ADMIN, UserRole.OWNER}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Organization admin or owner only",
        )
    return current_user.organization_id


@router.get("/catalog", response_model=BillingCatalogOut)
def read_billing_catalog(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _billing_admin_organization_id(current_user)
    return get_active_billing_catalog(db)


@router.get("/state", response_model=BillingStateOut)
def read_billing_state(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    organization_id = _billing_admin_organization_id(current_user)
    return get_organization_billing_state(
        db,
        organization_id=organization_id,
    )


@router.post("/checkout-session", response_model=CheckoutSessionOut)
def start_checkout_session(
    payload: CheckoutSessionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    organization_id = _billing_admin_organization_id(current_user)

    try:
        return create_checkout_session(
            db,
            organization_id=organization_id,
            pricing_tier_id=payload.pricing_tier_id,
            billing_email=current_user.email,
            requested_by_user_id=current_user.id,
            idempotency_key=payload.idempotency_key,
        )
    except ValueError as exc:
        db.rollback()
        status_code = (
            status.HTTP_409_CONFLICT
            if isinstance(exc, CheckoutIdempotencyConflict)
            else status.HTTP_400_BAD_REQUEST
        )
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    except StripeBillingUnavailable as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except StripeProviderError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc


@router.post("/webhooks/stripe")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    signature = request.headers.get("stripe-signature")
    if not signature:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing Stripe-Signature header",
        )
    payload = await request.body()

    try:
        event = construct_stripe_event(payload, signature)
        result = process_stripe_event(db, event)
        db.commit()
        return {"received": True, "result": result}
    except InvalidStripeWebhook as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except StripeBillingUnavailable as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except BillingWebhookIntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
