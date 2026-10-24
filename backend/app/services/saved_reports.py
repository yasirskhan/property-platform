"""Validation for presets; execution stays in the existing report delivery service."""
from __future__ import annotations

from collections.abc import Mapping

from app.services.report_delivery import (
    REPORT_PERMISSIONS,
    ReportDeliveryError,
    _bool_param,
    _date_param,
    _int_param,
)

PARAMETERS: dict[str, set[str]] = {
    "accounting.chart_of_accounts": {"include_inactive"},
    "accounting.trial_balance": {"as_of", "include_zero"},
    "accounting.general_ledger": {"account_id", "date_from", "date_to", "property_id"},
    "owner.statement": {"statement_id"},
}
BOOLEAN_KEYS = {"include_inactive", "include_zero"}
DATE_KEYS = {"as_of", "date_from", "date_to"}
INTEGER_KEYS = {"account_id", "property_id", "statement_id"}


def validate_saved_parameters(report_key: str, parameters: Mapping[str, object]) -> dict[str, str | int | bool]:
    """Accept only the parameter contract of an implemented report."""
    if report_key not in REPORT_PERMISSIONS or report_key not in PARAMETERS:
        raise ReportDeliveryError("Report is not available for delivery")
    unexpected = set(parameters) - PARAMETERS[report_key]
    if unexpected:
        raise ReportDeliveryError("Unsupported report parameter")
    clean: dict[str, str | int | bool] = {}
    for key, raw in parameters.items():
        if raw is None or raw == "":
            continue
        if key in BOOLEAN_KEYS:
            clean[key] = _bool_param(parameters, key)
        elif key in INTEGER_KEYS:
            value = _int_param(parameters, key)
            if value is not None:
                clean[key] = value
        elif key in DATE_KEYS:
            value = _date_param(parameters, key)
            if value is not None:
                clean[key] = value.isoformat()
    if report_key == "accounting.general_ledger" and "account_id" not in clean:
        raise ReportDeliveryError("account_id is required")
    if report_key == "owner.statement" and "statement_id" not in clean:
        raise ReportDeliveryError("statement_id is required")
    if clean.get("date_from") and clean.get("date_to") and clean["date_from"] > clean["date_to"]:
        raise ReportDeliveryError("date_from cannot be after date_to")
    return clean
