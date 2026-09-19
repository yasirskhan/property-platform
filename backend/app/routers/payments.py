# ============================================================
# routers/payments.py
# ------------------------------------------------------------
# HTTP routes for payments:
#
#   POST   /invoices/{invoice_id}/payments              record
#   GET    /invoices/{invoice_id}/payments              list
#   GET    /invoices/{invoice_id}                       get one
#   POST   /invoices/{invoice_id}/mark-paid             full pay
#   POST   /invoices/{invoice_id}/stripe-checkout       Stripe
#   POST   /stripe/webhook                              Stripe
#
# WHO CAN DO WHAT:
#   - Admin / Owner / Manager: record payments on invoices in scope.
#   - Tenant: can pay their own invoice.
#   - Crew: no access.
#
# STRIPE: Works when STRIPE_SECRET_KEY is set in config.py.
#         Until then, stripe-checkout returns 503.
# ============================================================

from datetime import datetime
from decimal import Decimal
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core import stripe_client
from app.core.database import get_db
from app.models.lease import (
    Lease,
    RentInvoice,
    Payment,
    InvoiceStatus,
    PaymentMethod,
)
from app.models.property import Property, Unit, PropertyAssignment
from app.models.user import User, UserRole
from app.routers.auth import get_current_user
from app.schemas.lease import (
    PaymentCreate,
    PaymentOut,
    RentInvoiceOut,
    StripeCheckoutRequest,
    StripeCheckoutResponse,
)


router = APIRouter(tags=["Payments"])


# ------------------------------------------------------------
# HELPERS
# ------------------------------------------------------------
def _require_role(current_user: User, *allowed: UserRole):
    if current_user.role not in allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Requires one of: {[r.value for r in allowed]}",
        )


def _check_invoice_access(db: Session, user: User, invoice: RentInvoice) -> RentInvoice:
    """
    Return the invoice if the user can access it.
    - Tenant: only if it belongs to their lease.
    - Others: if they can access the property the unit belongs to.
    """
    lease = db.query(Lease).filter(Lease.id == invoice.lease_id).first()
    if not lease:
        raise HTTPException(status_code=404, detail="Lease not found")

    if user.role == UserRole.TENANT:
        if lease.tenant_id != user.id:
            raise HTTPException(status_code=403, detail="Not your invoice")
        return invoice

    if user.role == UserRole.CREW:
        raise HTTPException(status_code=403, detail="Crew members cannot access invoices")

    unit = db.query(Unit).filter(Unit.id == lease.unit_id).first()
    if not unit:
        raise HTTPException(status_code=404, detail="Unit not found")
    prop = db.query(Property).filter(Property.id == unit.property_id).first()
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")

    if user.role == UserRole.ADMIN:
        return invoice

    if user.role == UserRole.OWNER:
        if prop.organization_id != user.organization_id:
            raise HTTPException(status_code=403, detail="Not in your organization")
        return invoice

    if user.role == UserRole.MANAGER:
        assigned = (
            db.query(PropertyAssignment)
            .filter(
                PropertyAssignment.property_id == prop.id,
                PropertyAssignment.user_id == user.id,
                PropertyAssignment.is_active == True,  # noqa: E712
            )
            .first()
        )
        if not assigned:
            raise HTTPException(status_code=403, detail="Not assigned to this property")
        return invoice

    raise HTTPException(status_code=403, detail="Access denied")


def _recalculate_invoice_status(db: Session, invoice: RentInvoice):
    """
    Look at all payments on the invoice and update its status + amount_paid.
    """
    payments = db.query(Payment).filter(Payment.invoice_id == invoice.id).all()
    total_paid = sum((p.amount for p in payments), Decimal("0.00"))

    invoice.amount_paid = total_paid

    if total_paid == 0:
        if invoice.due_date < datetime.utcnow().date():
            invoice.status = InvoiceStatus.DUE
        else:
            invoice.status = InvoiceStatus.PENDING
    elif total_paid >= invoice.amount_due:
        invoice.status = InvoiceStatus.PAID
    else:
        invoice.status = InvoiceStatus.PARTIAL

    db.commit()
    db.refresh(invoice)


# ------------------------------------------------------------
# GET ONE INVOICE
# ------------------------------------------------------------
@router.get("/invoices/{invoice_id}", response_model=RentInvoiceOut)
def get_invoice(
    invoice_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    invoice = db.query(RentInvoice).filter(RentInvoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return _check_invoice_access(db, current_user, invoice)


# ------------------------------------------------------------
# LIST PAYMENTS FOR AN INVOICE
# ------------------------------------------------------------
@router.get("/invoices/{invoice_id}/payments", response_model=List[PaymentOut])
def list_payments(
    invoice_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    invoice = db.query(RentInvoice).filter(RentInvoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    _check_invoice_access(db, current_user, invoice)

    return (
        db.query(Payment)
        .filter(Payment.invoice_id == invoice_id)
        .order_by(Payment.paid_at)
        .all()
    )


# ------------------------------------------------------------
# RECORD A PAYMENT
# ------------------------------------------------------------
@router.post(
    "/invoices/{invoice_id}/payments",
    response_model=PaymentOut,
    status_code=status.HTTP_201_CREATED,
)
def record_payment(
    invoice_id: int,
    payload: PaymentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Record a payment against an invoice.
    """
    invoice = db.query(RentInvoice).filter(RentInvoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    _check_invoice_access(db, current_user, invoice)

    if current_user.role == UserRole.TENANT:
        if payload.method not in (
            PaymentMethod.ACH,
            PaymentMethod.CARD,
            PaymentMethod.CHECK,
            PaymentMethod.OTHER,
        ):
            raise HTTPException(status_code=400, detail="Invalid payment method")

    if invoice.status == InvoiceStatus.VOID:
        raise HTTPException(status_code=400, detail="Cannot pay a voided invoice")

    total_due = invoice.amount_due + invoice.late_fee
    remaining = total_due - invoice.amount_paid
    if payload.amount > remaining:
        raise HTTPException(
            status_code=400,
            detail=f"Payment exceeds remaining balance (${remaining})",
        )

    payment = Payment(
        invoice_id=invoice.id,
        amount=payload.amount,
        method=payload.method,
        notes=payload.notes,
        paid_at=datetime.utcnow(),
    )
    db.add(payment)
    db.commit()
    db.refresh(payment)

    _recalculate_invoice_status(db, invoice)

    return payment


# ------------------------------------------------------------
# SHORTCUT: MARK INVOICE FULLY PAID
# ------------------------------------------------------------
@router.post("/invoices/{invoice_id}/mark-paid", response_model=PaymentOut, status_code=status.HTTP_201_CREATED)
def mark_paid(
    invoice_id: int,
    method: PaymentMethod = PaymentMethod.OTHER,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Pay the remaining balance on an invoice in one step."""
    _require_role(current_user, UserRole.ADMIN, UserRole.OWNER, UserRole.MANAGER)

    invoice = db.query(RentInvoice).filter(RentInvoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    _check_invoice_access(db, current_user, invoice)

    total_due = invoice.amount_due + invoice.late_fee
    remaining = total_due - invoice.amount_paid

    if remaining <= 0:
        raise HTTPException(status_code=400, detail="Invoice already fully paid")

    payment = Payment(
        invoice_id=invoice.id,
        amount=remaining,
        method=method,
        notes="Marked as paid",
        paid_at=datetime.utcnow(),
    )
    db.add(payment)
    db.commit()
    db.refresh(payment)

    _recalculate_invoice_status(db, invoice)

    return payment


# ============================================================
# STRIPE ENDPOINTS
# ============================================================
# Work only when Stripe keys are set in config.py.
# Until then they return 503 (Service Unavailable).
# ============================================================


@router.post("/invoices/{invoice_id}/stripe-checkout", response_model=StripeCheckoutResponse)
def create_stripe_checkout(
    invoice_id: int,
    payload: StripeCheckoutRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Start a Stripe Checkout session for the remaining balance."""
    if not stripe_client.is_stripe_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Stripe is not configured. Add STRIPE_SECRET_KEY in config.py.",
        )

    invoice = db.query(RentInvoice).filter(RentInvoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    _check_invoice_access(db, current_user, invoice)

    total_due = invoice.amount_due + invoice.late_fee
    remaining = total_due - invoice.amount_paid
    if remaining <= 0:
        raise HTTPException(status_code=400, detail="Invoice already fully paid")

    amount_cents = int(remaining * 100)

    lease = db.query(Lease).filter(Lease.id == invoice.lease_id).first()
    tenant = None
    if lease:
        tenant = db.query(User).filter(User.id == lease.tenant_id).first()

    session = stripe_client.create_checkout_session(
        invoice_id=invoice.id,
        amount_cents=amount_cents,
        description=f"Rent for {invoice.period_start} to {invoice.period_end}",
        success_url=payload.success_url,
        cancel_url=payload.cancel_url,
        customer_email=tenant.email if tenant else None,
    )

    return StripeCheckoutResponse(checkout_url=session["url"], session_id=session["id"])


@router.post("/stripe/webhook")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    """Stripe webhook: records successful payments automatically."""
    if not stripe_client.is_stripe_configured():
        raise HTTPException(status_code=503, detail="Stripe not configured")

    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    try:
        event = stripe_client.verify_webhook(payload, sig_header)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Webhook error: {e}")

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        invoice_id = int(session["metadata"]["invoice_id"])
        amount_total = Decimal(session["amount_total"]) / 100
        external_id = session["payment_intent"] or session["id"]

        invoice = db.query(RentInvoice).filter(RentInvoice.id == invoice_id).first()
        if not invoice:
            return {"received": True, "warning": "invoice not found"}

        existing = (
            db.query(Payment)
            .filter(Payment.invoice_id == invoice_id, Payment.external_id == external_id)
            .first()
        )
        if existing:
            return {"received": True, "duplicate": True}

        payment = Payment(
            invoice_id=invoice_id,
            amount=amount_total,
            method=PaymentMethod.CARD,
            external_id=external_id,
            notes="Stripe checkout",
            paid_at=datetime.utcnow(),
        )
        db.add(payment)
        db.commit()
        _recalculate_invoice_status(db, invoice)

    return {"received": True}