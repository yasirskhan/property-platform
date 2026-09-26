"""Avalara 1099 sandbox dry-run validation.

This adapter cannot file returns. It only calls Avalara's sandbox bulk-upsert
endpoint with dryRun=true after the existing local 1099 preflight succeeds.
No provider response body is returned or logged because validation errors may
reflect taxpayer data.
"""
from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import requests
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.tax_1099_review import Tax1099Review
from app.models.user import User
from app.schemas.tax_1099_review import Tax1099ProviderDryRunIn, Tax1099ProviderDryRunOut
from app.services.audit import append_audit_log
from app.services.tax_1099_reviews import (
    _payload_from_row, _profiles, _row, preflight_review,
)
from app.services.tax_profiles import _crypto, _decode, require_tax_admin

TOKEN_URL = "https://ai-sbx.avlr.sh/connect/token"
API_BASE = "https://api.sbx.avalara.com/avalara1099"
CLIENT_HEADER = "PropertyPlatform/1099-sandbox-validation"


def _config() -> tuple[str, str, str, str]:
    if settings.TAX_1099_PROVIDER.strip().lower() != "avalara_sandbox":
        raise HTTPException(status_code=503, detail="1099 provider sandbox validation is not configured.")
    values = (
        settings.AVALARA_1099_CLIENT_ID.strip(),
        settings.AVALARA_1099_CLIENT_SECRET.strip(),
        settings.AVALARA_1099_ISSUER_ID.strip(),
        settings.AVALARA_1099_API_VERSION.strip(),
    )
    if not all(values):
        raise HTTPException(status_code=503, detail="1099 provider sandbox validation is not configured.")
    return values


def _country_code(value: object) -> str:
    text = str(value or "").strip().upper()
    if text in {"US", "USA", "UNITED STATES", "UNITED STATES OF AMERICA"}:
        return "US"
    # Current Phase 3.7 mapping is deliberately US-only until a verified
    # foreign-address provider schema is implemented.
    raise HTTPException(status_code=422, detail="Provider sandbox validation currently supports US addresses only.")


def _nec_form(
    *, row: Tax1099Review, issuer_id: str,
    recipient: dict[str, object],
) -> dict[str, object]:
    if row.form_type != "1099-NEC" or row.income_category != "NONEMPLOYEE_COMPENSATION":
        raise HTTPException(
            status_code=422,
            detail="Avalara sandbox mapping is currently verified only for 1099-NEC nonemployee compensation.",
        )
    legal_name = str(recipient.get("legal_name") or "").strip()
    tin = str(recipient.get("tin") or "").strip()
    tin_type = str(recipient.get("tin_type") or "").strip().upper()
    if tin_type not in {"SSN", "EIN", "ITIN"}:
        raise HTTPException(status_code=422, detail="Recipient taxpayer ID type is not supported by provider mapping.")
    form = {
        "type": "1099-NEC",
        "issuerId": issuer_id,
        "taxYear": row.tax_year,
        "referenceId": f"property-platform-{row.organization_id}-{row.id}",
        "tin": tin,
        "recipientName": legal_name,
        "tinType": tin_type,
        "address": str(recipient.get("address_line1") or "").strip(),
        "address2": str(recipient.get("address_line2") or "").strip() or None,
        "city": str(recipient.get("city") or "").strip(),
        "state": str(recipient.get("state") or "").strip(),
        "zip": str(recipient.get("postal_code") or "").strip(),
        "countryCode": _country_code(recipient.get("country")),
        "nonemployeeCompensation": float(Decimal(row.amount).quantize(Decimal("0.01"))),
        # Never schedule filing or delivery from the validation endpoint.
        "federalEFile": False,
        "stateEFile": False,
        "postalMail": False,
    }
    if not all((form["recipientName"], form["tin"], form["address"], form["city"], form["state"], form["zip"])):
        raise HTTPException(status_code=422, detail="Recipient provider fields are incomplete.")
    return form


def _token(client_id: str, client_secret: str) -> str:
    try:
        response = requests.post(
            TOKEN_URL,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data={
                "grant_type": "client_credentials",
                "client_id": client_id,
                "client_secret": client_secret,
            },
            timeout=15,
        )
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail="Provider sandbox authentication is unavailable.") from exc
    if response.status_code != 200:
        raise HTTPException(status_code=502, detail="Provider sandbox authentication failed.")
    try:
        token = response.json().get("access_token")
    except ValueError as exc:
        raise HTTPException(status_code=502, detail="Provider sandbox authentication response was invalid.") from exc
    if not isinstance(token, str) or not token:
        raise HTTPException(status_code=502, detail="Provider sandbox authentication response was invalid.")
    return token


def validate_avalara_sandbox_dry_run(
    db: Session, *, current_user: User, record_id: int,
    payload: Tax1099ProviderDryRunIn,
) -> Tax1099ProviderDryRunOut:
    """Send an already-approved record only to Avalara sandbox dry-run validation."""
    organization_id = require_tax_admin(db, current_user)
    client_id, client_secret, issuer_id, api_version = _config()

    preflight = preflight_review(db, current_user=current_user, record_id=record_id)
    if not preflight.ready_for_provider_handoff:
        raise HTTPException(status_code=409, detail="Local 1099 prerequisites must pass before provider validation.")

    row = _row(db, organization_id=organization_id, record_id=record_id)
    review_payload = _payload_from_row(row)
    _payer, recipient_row, _payer_last4, _recipient_last4, _w9 = _profiles(
        db, organization_id=organization_id, payload=review_payload,
        require_current_subject=True, require_w9=True,
    )
    recipient = _decode(recipient_row, _crypto())
    form = _nec_form(row=row, issuer_id=issuer_id, recipient=recipient)
    correlation_id = str(uuid4())
    token = _token(client_id, client_secret)

    try:
        response = requests.post(
            f"{API_BASE}/1099/forms/$bulk-upsert",
            params={"dryRun": "true"},
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "avalara-version": api_version,
                "X-Avalara-Client": CLIENT_HEADER,
                "X-Correlation-Id": correlation_id,
            },
            json={"type": "1099-NEC", "forms": [form]},
            timeout=20,
        )
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail="Provider sandbox validation is unavailable.") from exc

    # Never echo body/text; providers may include field values in validation errors.
    validated = 200 <= response.status_code < 300
    if response.status_code in {401, 403}:
        message = "Provider sandbox rejected the configured credentials."
    elif validated:
        message = "Avalara sandbox dry-run accepted the record for validation. Nothing was filed or scheduled."
    else:
        message = "Avalara sandbox dry-run rejected the record. Review the provider sandbox directly for details."

    append_audit_log(
        db, user_id=current_user.id, organization_id=organization_id,
        entity_type="tax_1099_review", entity_id=row.id,
        action="provider_sandbox_dry_run",
        new_value={
            "provider": "AVALARA_SANDBOX",
            "dry_run": True,
            "http_status": response.status_code,
            "validated": validated,
            "submitted": False,
        },
    )
    db.commit()
    return Tax1099ProviderDryRunOut(
        record_id=row.id, provider="AVALARA_SANDBOX",
        validated=validated, provider_http_status=response.status_code,
        message=message,
    )



def provider_status(db: Session, *, current_user: User):
    """Redacted operator status; never serialize credentials or issuer identifiers."""
    require_tax_admin(db, current_user)
    mode = settings.TAX_1099_PROVIDER.strip().lower()
    configured = mode == "avalara_sandbox" and all((
        settings.AVALARA_1099_CLIENT_ID.strip(),
        settings.AVALARA_1099_CLIENT_SECRET.strip(),
        settings.AVALARA_1099_ISSUER_ID.strip(),
        settings.AVALARA_1099_API_VERSION.strip(),
    ))
    from app.schemas.tax_1099_review import Tax1099ProviderStatusOut
    return Tax1099ProviderStatusOut(
        provider="AVALARA_SANDBOX" if mode == "avalara_sandbox" else "DISABLED",
        configured=bool(configured),
        supported_forms=["1099-NEC"] if configured else [],
    )
