# ============================================================
# stripe_client.py
# ------------------------------------------------------------
# Wraps Stripe SDK calls.
#
# Inactive until Stripe keys are set in config.py or .env.
# No code changes needed when you go live — just new keys.
# ============================================================

from typing import Optional

import stripe

from app.core.config import settings


if settings.STRIPE_SECRET_KEY:
    stripe.api_key = settings.STRIPE_SECRET_KEY


def is_stripe_configured() -> bool:
    """True if a Stripe secret key has been set."""
    return bool(settings.STRIPE_SECRET_KEY)


def create_checkout_session(
    *,
    invoice_id: int,
    amount_cents: int,
    currency: str = "usd",
    description: str = "",
    success_url: str,
    cancel_url: str,
    customer_email: Optional[str] = None,
) -> dict:
    """
    Create a Stripe Checkout Session for a rent invoice payment.
    Returns {'id': session_id, 'url': checkout_url}.
    """
    if not is_stripe_configured():
        raise RuntimeError(
            "Stripe is not configured. Add STRIPE_SECRET_KEY to config.py or .env"
        )

    session = stripe.checkout.Session.create(
        mode="payment",
        payment_method_types=["card"],
        line_items=[
            {
                "price_data": {
                    "currency": currency,
                    "product_data": {
                        "name": f"Rent Invoice #{invoice_id}",
                        "description": description or "Monthly rent",
                    },
                    "unit_amount": amount_cents,
                },
                "quantity": 1,
            }
        ],
        success_url=success_url,
        cancel_url=cancel_url,
        customer_email=customer_email,
        metadata={"invoice_id": str(invoice_id)},
    )

    return {"id": session.id, "url": session.url}


def verify_webhook(payload: bytes, sig_header: str) -> dict:
    """
    Verify a webhook came from Stripe and return the parsed event.
    """
    if not settings.STRIPE_WEBHOOK_SECRET:
        raise RuntimeError("STRIPE_WEBHOOK_SECRET is not configured")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
        return event
    except stripe.error.SignatureVerificationError as e:
        raise ValueError(f"Invalid signature: {e}")