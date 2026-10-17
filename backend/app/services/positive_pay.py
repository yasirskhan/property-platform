"""Per-bank positive-pay preflight, using the verified Check Register.

NOT a bank-specific file, electronic upload or record of bank acceptance.
No ledger, check, reconciliation or bank account updates occur.
"""
from __future__ import annotations
from datetime import date
from decimal import Decimal
from fastapi import HTTPException
from sqlalchemy.orm import Session
from app.models.bank_account import BankAccount
from app.models.gl_account import GLAccount
from app.models.user import User, UserRole
from app.services.check_register_report import build_check_register
from app.services.customer_features import resolve_customer_features
from app.services.menu_resolver import permission_allows_user
from app.services.report_delivery import ReportDeliveryError

FEATURE_KEY = "release.accounting.check_printing"


def preflight_positive_pay(
    db: Session, *, bank_id: int, current_user: User,
    date_from: date | None = None, date_to: date | None = None,
) -> dict[str, object]:
    if (
        current_user.organization_id is None or not current_user.is_active
        or current_user.deleted_at is not None or current_user.role != UserRole.ADMIN
        or not permission_allows_user(db, user=current_user, menu_key="ACCOUNTING.BANK_ACCOUNTS")
    ):
        raise HTTPException(status_code=403, detail="Bank permission required.")
    enabled = next(
        (item for item in resolve_customer_features(db, user=current_user) if item.key == FEATURE_KEY),
        None,
    )
    if enabled is None or not enabled.allowed:
        raise HTTPException(status_code=404, detail="Positive-pay review is unavailable.")
    org_id = int(current_user.organization_id)
    bank = db.query(BankAccount).filter(
        BankAccount.id == bank_id, BankAccount.organization_id == org_id,
        BankAccount.is_active.is_(True), BankAccount.deleted_at.is_(None),
    ).first()
    if bank is None:
        raise HTTPException(status_code=404, detail="Bank account not found.")
    cash = db.query(GLAccount.id).filter(
        GLAccount.id == bank.gl_account_id, GLAccount.organization_id == org_id,
        GLAccount.account_type == "ASSET", GLAccount.is_active.is_(True),
        GLAccount.deleted_at.is_(None),
    ).first()
    if cash is None:
        raise HTTPException(status_code=422, detail="Bank cash mapping needs review.")
    params: dict[str, object] = {"bank_id": bank_id}
    if date_from is not None:
        params["date_from"] = date_from
    if date_to is not None:
        params["date_to"] = date_to
    try:
        report = build_check_register(
            db, organization_id=org_id, current_user=current_user,
            parameters=params,
        )
    except ReportDeliveryError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if len(report.rows) > 500:
        raise HTTPException(status_code=422, detail="Narrow dates to at most 500 checks.")
    candidates = []
    blockers = 0
    for item in report.rows:
        # Report source validates issue/void GL provenance and same-org bank.
        check_id, check_date, number, payee, _bank_label, status, amount, *_rest = item
        reasons = []
        if not str(number or "").strip():
            reasons.append("Missing recorded check number")
        if not str(payee or "").strip():
            reasons.append("Missing payee")
        if reasons:
            blockers += 1
        candidates.append({
            "check_id": check_id, "check_date": check_date,
            "check_number": number, "recorded_payee": payee,
            "status": status, "nominal_amount": str(Decimal(amount).quantize(Decimal("0.01"))),
            "review_flags": reasons,
        })
    return {
        "bank_account_id": bank.id,
        "total": len(candidates), "issued": sum(x["status"] == "ISSUED" for x in candidates),
        "voided": sum(x["status"] == "VOID" for x in candidates),
        "needs_review": blockers,
        "items": candidates,
        "bank_file_format_configured": False,
        "bank_file_export_available": False,
        "submission_status": "NOT_SUBMITTED",
        "meaning": "Internal recorded issue/void preflight only. No bank format, upload or bank acceptance; the bank must supply an approved specification.",
    }
