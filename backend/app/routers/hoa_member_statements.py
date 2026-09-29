"""Read-only, actually posted HOA member account statements across proposals.

Only accounting-authorized organization staff can read this private ledger.
Amounts are derived from the existing posted assessment and receipt rows;
no tenant Charge, separate GL, inferred member liability or sending occurs.
"""
from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.hoa_member_assessment import (
    HOAAssessmentDecision, HOAMemberAssessmentCharge,
)
from app.models.hoa_member_assessment_payment import HOAMemberAssessmentPayment
from app.models.user import User
from app.routers.auth import get_current_user
from app.routers.hoa_member_assessments import _accountant
from app.schemas.hoa_member_statement import (
    HOAMemberStatementOut, HOAMemberStatementChargeOut,
    HOAMemberStatementPaymentOut,
)

router = APIRouter(prefix="/api/hoa/associations", tags=["HOA posted member statements"])


@router.get("/{association_id}/member-statements",
            response_model=list[HOAMemberStatementOut])
def member_statements(
    association_id: int, response: Response,
    property_id: int = Query(ge=1),
    member_user_id: Annotated[int | None, Query(ge=1)] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org, association = _accountant(
        db, actor=current_user, assoc=association_id, prop=property_id,
    )
    query = db.query(HOAMemberAssessmentCharge, HOAAssessmentDecision.proposal_id).join(
        HOAAssessmentDecision,
        HOAAssessmentDecision.id == HOAMemberAssessmentCharge.decision_id,
    ).filter(
        HOAMemberAssessmentCharge.organization_id == org,
        HOAMemberAssessmentCharge.association_id == association.id,
        HOAMemberAssessmentCharge.property_id == property_id,
        HOAAssessmentDecision.organization_id == org,
        HOAAssessmentDecision.association_id == association.id,
        HOAAssessmentDecision.property_id == property_id,
    )
    if member_user_id is not None:
        query = query.filter(HOAMemberAssessmentCharge.member_user_id == member_user_id)
    charges = query.order_by(HOAMemberAssessmentCharge.id).limit(501).all()
    if len(charges) > 500:
        raise HTTPException(status_code=422, detail="Statement exceeds 500 assessments; narrow the member filter.")
    if not charges:
        response.headers["Cache-Control"] = "no-store"
        return []
    ids = [charge.id for charge, _ in charges]
    receipts = db.query(HOAMemberAssessmentPayment).filter(
        HOAMemberAssessmentPayment.organization_id == org,
        HOAMemberAssessmentPayment.association_id == association.id,
        HOAMemberAssessmentPayment.property_id == property_id,
        HOAMemberAssessmentPayment.charge_id.in_(ids),
    ).order_by(HOAMemberAssessmentPayment.id).limit(1501).all()
    if len(receipts) > 1500:
        raise HTTPException(status_code=422, detail="Statement receipt history exceeds 1500 entries.")
    by_charge = defaultdict(list)
    for payment in receipts:
        by_charge[payment.charge_id].append(payment)

    by_member = {}
    for charge, proposal_id in charges:
        payments = by_charge[charge.id]
        paid = sum((p.amount for p in payments if p.status == "POSTED"), Decimal("0.00"))
        if charge.amount_paid != paid:
            raise HTTPException(status_code=409, detail="Member statement needs accounting reconciliation.")
        if charge.status == "REVERSED":
            if paid != Decimal("0.00"):
                raise HTTPException(status_code=409, detail="Reversed member statement has live receipts.")
            assessed = Decimal("0.00")
            outstanding = Decimal("0.00")
        else:
            assessed = charge.amount
            outstanding = charge.amount - charge.amount_paid
            if outstanding < 0:
                raise HTTPException(status_code=409, detail="Assessment receipt exceeds posted amount.")
        account = by_member.setdefault(charge.member_user_id, {
            "member_user_id": charge.member_user_id,
            "total_assessed": Decimal("0.00"),
            "total_paid": Decimal("0.00"),
            "outstanding": Decimal("0.00"),
            "charges": [],
        })
        account["total_assessed"] += assessed
        account["total_paid"] += charge.amount_paid
        account["outstanding"] += outstanding
        account["charges"].append(HOAMemberStatementChargeOut(
            id=charge.id, proposal_id=proposal_id, amount=charge.amount,
            amount_paid=charge.amount_paid, outstanding=outstanding,
            due_on=charge.due_on, status=charge.status,
            gl_transaction_id=charge.gl_transaction_id,
            reversal_transaction_id=charge.reversal_transaction_id,
            payments=[HOAMemberStatementPaymentOut(
                id=p.id, amount=p.amount, received_on=p.received_on,
                status=p.status, receipt_id=p.receipt_id,
                reversal_receipt_id=p.reversal_receipt_id,
            ) for p in payments],
        ))
    response.headers["Cache-Control"] = "no-store"
    return [HOAMemberStatementOut(**row) for _, row in sorted(by_member.items())]
