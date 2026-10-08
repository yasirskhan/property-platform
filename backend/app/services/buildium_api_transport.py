"""Server-to-server Buildium Open API transport for Phase 4.14.

The migration pipeline owns staging, review, exact fingerprints, mappings and
commits. This module only retrieves bounded provider records. Credentials are
read from server settings, never accepted from migration request payloads, and
provider response bodies are never copied into errors or audit logs.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

import requests

from app.core.config import settings

_SANDBOX_BASE = "https://apisandbox.buildium.com"
_PRODUCTION_BASE = "https://api.buildium.com"
_PROPERTY_PATH = "/v1/rentals"
_UNIT_PATH = "/v1/rentals/units"
_OWNER_PATH = "/v1/rentals/owners"
_VENDOR_PATH = "/v1/vendors"
_TENANT_PATH = "/v1/leases/tenants"
_LEASE_PATH = "/v1/leases"
_GL_ACCOUNT_PATH = "/v1/glaccounts"
_WORK_ORDER_PATH = "/v1/workorders"
_BILL_PATH = "/v1/bills"
_BANK_ACCOUNT_PATH = "/v1/bankaccounts"
_PROPERTY_GROUP_PATH = "/v1/propertygroups"
_BUDGET_PATH = "/v1/budgets"
_MAX_REVIEW_RECORDS = 500
_PAGE_LIMIT = 500
_TIMEOUT_SECONDS = 20
MAX_BILL_PAYMENT_PARENT_BILLS = 100
MAX_BILL_PAYMENT_RECORDS = _MAX_REVIEW_RECORDS
MAX_LEASE_CHARGE_PARENT_LEASES = 100
MAX_LEASE_CHARGE_RECORDS = _MAX_REVIEW_RECORDS
MAX_BUDGET_RECORDS = 100
MAX_LEASE_PAYMENT_PARENT_LEASES = 100
MAX_LEASE_PAYMENT_RECORDS = _MAX_REVIEW_RECORDS
MAX_BANK_RECONCILIATION_PARENT_BANK_ACCOUNTS = 100
MAX_BANK_RECONCILIATION_RECORDS = _MAX_REVIEW_RECORDS
MAX_BANK_TRANSFER_PARENT_BANK_ACCOUNTS = 100
MAX_BANK_TRANSFER_RECORDS = _MAX_REVIEW_RECORDS
MAX_BANK_WITHDRAWAL_PARENT_BANK_ACCOUNTS = 100
MAX_BANK_WITHDRAWAL_RECORDS = _MAX_REVIEW_RECORDS
MAX_QUICK_DEPOSIT_PARENT_BANK_ACCOUNTS = 100
MAX_QUICK_DEPOSIT_RECORDS = _MAX_REVIEW_RECORDS


class BuildiumApiTransportError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class BuildiumApiTransportStatus:
    mode: str
    configured: bool
    source_account_bound: bool


@dataclass(frozen=True)
class BuildiumApiFetchResult:
    records: list[dict[str, Any]]
    mode: str
    request_count: int
    parent_record_count: int | None = None
    detail_request_count: int | None = None


@dataclass(frozen=True)
class _Profile:
    mode: str
    base_url: str
    client_id: str
    client_secret: str
    source_account_ref: str


def transport_status() -> BuildiumApiTransportStatus:
    mode = settings.BUILDIUM_API_MODE.strip().lower()
    configured = mode in {"sandbox", "production"} and all((
        settings.BUILDIUM_API_CLIENT_ID.strip(),
        settings.BUILDIUM_API_CLIENT_SECRET.strip(),
        settings.BUILDIUM_API_SOURCE_ACCOUNT_REF.strip(),
    ))
    return BuildiumApiTransportStatus(
        mode=mode if mode in {"sandbox", "production"} else "disabled",
        configured=bool(configured),
        source_account_bound=bool(settings.BUILDIUM_API_SOURCE_ACCOUNT_REF.strip()),
    )


def _profile(expected_source_account_ref: str) -> _Profile:
    mode = settings.BUILDIUM_API_MODE.strip().lower()
    if mode not in {"sandbox", "production"}:
        raise BuildiumApiTransportError(
            "not_configured", "Buildium API transport is not configured."
        )
    client_id = settings.BUILDIUM_API_CLIENT_ID.strip()
    client_secret = settings.BUILDIUM_API_CLIENT_SECRET.strip()
    source_account_ref = settings.BUILDIUM_API_SOURCE_ACCOUNT_REF.strip()
    if not client_id or not client_secret or not source_account_ref:
        raise BuildiumApiTransportError(
            "not_configured", "Buildium API transport is not configured."
        )
    if source_account_ref != expected_source_account_ref.strip():
        raise BuildiumApiTransportError(
            "source_account_mismatch",
            "Buildium API transport is configured for a different source account.",
        )
    return _Profile(
        mode=mode,
        base_url=_SANDBOX_BASE if mode == "sandbox" else _PRODUCTION_BASE,
        client_id=client_id,
        client_secret=client_secret,
        source_account_ref=source_account_ref,
    )


def _get_json_list(
    profile: _Profile,
    *,
    path: str,
    resource_label: str,
    offset: int,
    limit: int,
    extra_params: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    try:
        response = requests.get(
            f"{profile.base_url}{path}",
            headers={
                "x-buildium-client-id": profile.client_id,
                "x-buildium-client-secret": profile.client_secret,
                "Accept": "application/json",
            },
            params={"offset": offset, "limit": limit, **(extra_params or {})},
            timeout=_TIMEOUT_SECONDS,
        )
    except requests.RequestException as exc:
        raise BuildiumApiTransportError(
            "unavailable", "Buildium API transport is unavailable."
        ) from exc

    if response.status_code == 401:
        raise BuildiumApiTransportError(
            "unauthorized", "Buildium rejected the configured API credentials."
        )
    if response.status_code == 403:
        raise BuildiumApiTransportError(
            "forbidden",
            f"Buildium API credentials lack permission for {resource_label}.",
        )
    if response.status_code == 429:
        raise BuildiumApiTransportError(
            "rate_limited",
            "Buildium API rate limit was reached; retry the migration transport request.",
        )
    if response.status_code != 200:
        raise BuildiumApiTransportError(
            "upstream_error",
            f"Buildium API request failed with HTTP {response.status_code}.",
        )
    try:
        payload = response.json()
    except ValueError as exc:
        raise BuildiumApiTransportError(
            "invalid_response", "Buildium API returned an invalid JSON response."
        ) from exc
    if not isinstance(payload, list) or any(not isinstance(item, dict) for item in payload):
        raise BuildiumApiTransportError(
            "invalid_response",
            f"Buildium API returned an unexpected {resource_label} response.",
        )
    return payload


def _fetch_bounded_collection(
    *,
    profile: _Profile,
    path: str,
    resource_label: str,
) -> BuildiumApiFetchResult:
    first = _get_json_list(
        profile,
        path=path,
        resource_label=resource_label,
        offset=0,
        limit=_PAGE_LIMIT,
    )
    requests_made = 1
    if len(first) == _PAGE_LIMIT:
        probe = _get_json_list(
            profile,
            path=path,
            resource_label=resource_label,
            offset=_PAGE_LIMIT,
            limit=1,
        )
        requests_made += 1
        if probe:
            raise BuildiumApiTransportError(
                "source_too_large",
                f"Buildium {resource_label} source exceeds the bounded "
                f"{_MAX_REVIEW_RECORDS}-record API migration review.",
            )
    if not first:
        raise BuildiumApiTransportError(
            "empty_source",
            f"Buildium API returned no {resource_label} for this source account.",
        )
    return BuildiumApiFetchResult(
        records=first,
        mode=profile.mode,
        request_count=requests_made,
    )


def fetch_rental_properties(*, expected_source_account_ref: str) -> BuildiumApiFetchResult:
    """Fetch one bounded complete rental-property set for the existing pipeline."""
    return _fetch_bounded_collection(
        profile=_profile(expected_source_account_ref),
        path=_PROPERTY_PATH,
        resource_label="rental properties",
    )


def fetch_rental_units(*, expected_source_account_ref: str) -> BuildiumApiFetchResult:
    """Fetch one bounded complete rental-unit set for the existing Unit pipeline."""
    return _fetch_bounded_collection(
        profile=_profile(expected_source_account_ref),
        path=_UNIT_PATH,
        resource_label="rental units",
    )


def fetch_rental_owners(*, expected_source_account_ref: str) -> BuildiumApiFetchResult:
    """Fetch one bounded complete rental-owner set for the existing Owner pipeline."""
    return _fetch_bounded_collection(
        profile=_profile(expected_source_account_ref),
        path=_OWNER_PATH,
        resource_label="rental owners",
    )


def fetch_vendors(*, expected_source_account_ref: str) -> BuildiumApiFetchResult:
    """Fetch one bounded complete Vendor set for the existing Vendor pipeline."""
    return _fetch_bounded_collection(
        profile=_profile(expected_source_account_ref),
        path=_VENDOR_PATH,
        resource_label="vendors",
    )


def fetch_rental_tenants(*, expected_source_account_ref: str) -> BuildiumApiFetchResult:
    """Fetch one bounded complete rental-tenant set for the existing Tenant pipeline."""
    return _fetch_bounded_collection(
        profile=_profile(expected_source_account_ref),
        path=_TENANT_PATH,
        resource_label="rental tenants",
    )


def fetch_rental_leases(*, expected_source_account_ref: str) -> BuildiumApiFetchResult:
    """Fetch one bounded complete rental-lease set for the existing Lease pipeline."""
    return _fetch_bounded_collection(
        profile=_profile(expected_source_account_ref),
        path=_LEASE_PATH,
        resource_label="rental leases",
    )


def fetch_gl_accounts(*, expected_source_account_ref: str) -> BuildiumApiFetchResult:
    """Fetch one bounded complete GL-account set for the existing GL pipeline."""
    return _fetch_bounded_collection(
        profile=_profile(expected_source_account_ref),
        path=_GL_ACCOUNT_PATH,
        resource_label="general ledger accounts",
    )



def fetch_work_orders(*, expected_source_account_ref: str) -> BuildiumApiFetchResult:
    """Fetch one bounded complete Work Order set for the existing relationship pipeline."""
    return _fetch_bounded_collection(
        profile=_profile(expected_source_account_ref),
        path=_WORK_ORDER_PATH,
        resource_label="work orders",
    )



def fetch_bills(*, expected_source_account_ref: str) -> BuildiumApiFetchResult:
    """Fetch one bounded complete Bill set for the existing Bill reconciliation pipeline."""
    return _fetch_bounded_collection(
        profile=_profile(expected_source_account_ref),
        path=_BILL_PATH,
        resource_label="bills",
    )



def fetch_bank_accounts(*, expected_source_account_ref: str) -> BuildiumApiFetchResult:
    """Fetch one bounded complete Bank Account set for the existing identity pipeline."""
    return _fetch_bounded_collection(
        profile=_profile(expected_source_account_ref),
        path=_BANK_ACCOUNT_PATH,
        resource_label="bank accounts",
    )



def fetch_property_groups(*, expected_source_account_ref: str) -> BuildiumApiFetchResult:
    """Fetch one bounded complete Property Group set for the existing reconciliation pipeline."""
    return _fetch_bounded_collection(
        profile=_profile(expected_source_account_ref),
        path=_PROPERTY_GROUP_PATH,
        resource_label="property groups",
    )


def fetch_budgets(*, expected_source_account_ref: str) -> BuildiumApiFetchResult:
    """Fetch the existing Budget contract's bounded complete provider set."""
    profile = _profile(expected_source_account_ref)
    records = _get_json_list(
        profile,
        path=_BUDGET_PATH,
        resource_label="budgets",
        offset=0,
        limit=MAX_BUDGET_RECORDS,
    )
    requests_made = 1
    if len(records) == MAX_BUDGET_RECORDS:
        probe = _get_json_list(
            profile,
            path=_BUDGET_PATH,
            resource_label="budgets",
            offset=MAX_BUDGET_RECORDS,
            limit=1,
        )
        requests_made += 1
        if probe:
            raise BuildiumApiTransportError(
                "source_too_large",
                "Buildium budgets source exceeds the bounded "
                f"{MAX_BUDGET_RECORDS}-record API migration review.",
            )
    if not records:
        raise BuildiumApiTransportError(
            "empty_source",
            "Buildium API returned no budgets for this source account.",
        )
    return BuildiumApiFetchResult(
        records=records,
        mode=profile.mode,
        request_count=requests_made,
    )


def fetch_lease_charges(
    *,
    expected_source_account_ref: str,
    parent_lease_ids: list[int | str],
) -> BuildiumApiFetchResult:
    """Fetch bounded nested Lease Charge records for already-mapped parent Leases."""
    profile = _profile(expected_source_account_ref)

    normalized_parent_ids: list[int] = []
    seen_parent_ids: set[int] = set()
    for raw_parent_id in parent_lease_ids:
        if isinstance(raw_parent_id, bool):
            raise BuildiumApiTransportError(
                "invalid_parent_scope",
                "Buildium Lease Charge parent Lease scope contains an invalid source ID.",
            )
        try:
            parent_id = int(str(raw_parent_id).strip())
        except (TypeError, ValueError):
            raise BuildiumApiTransportError(
                "invalid_parent_scope",
                "Buildium Lease Charge parent Lease scope contains an invalid source ID.",
            )
        if parent_id < 1:
            raise BuildiumApiTransportError(
                "invalid_parent_scope",
                "Buildium Lease Charge parent Lease scope contains an invalid source ID.",
            )
        if parent_id in seen_parent_ids:
            raise BuildiumApiTransportError(
                "invalid_parent_scope",
                "Buildium Lease Charge parent Lease scope contains a duplicate source ID.",
            )
        seen_parent_ids.add(parent_id)
        normalized_parent_ids.append(parent_id)

    if not normalized_parent_ids:
        raise BuildiumApiTransportError(
            "empty_parent_scope",
            "Buildium Lease Charge API migration requires at least one durably mapped parent Lease.",
        )
    if len(normalized_parent_ids) > MAX_LEASE_CHARGE_PARENT_LEASES:
        raise BuildiumApiTransportError(
            "source_too_large",
            "Buildium Lease Charge API migration exceeds the bounded "
            f"{MAX_LEASE_CHARGE_PARENT_LEASES}-parent-Lease review scope.",
        )

    records: list[dict[str, Any]] = []
    requests_made = 0
    for parent_lease_id in sorted(normalized_parent_ids):
        remaining = MAX_LEASE_CHARGE_RECORDS - len(records)
        request_limit = max(1, min(1000, remaining + 1))
        page = _get_json_list(
            profile,
            path=f"/v1/leases/{parent_lease_id}/charges",
            resource_label=f"lease charges for parent Lease {parent_lease_id}",
            offset=0,
            limit=request_limit,
        )
        requests_made += 1
        if len(page) > remaining:
            raise BuildiumApiTransportError(
                "source_too_large",
                "Buildium Lease Charge source exceeds the bounded "
                f"{MAX_LEASE_CHARGE_RECORDS}-record API migration review.",
            )
        for provider_record in page:
            record = dict(provider_record)
            record["LeaseId"] = parent_lease_id
            records.append(record)

    if not records:
        raise BuildiumApiTransportError(
            "empty_source",
            "Buildium API returned no Lease Charges for the mapped parent Leases.",
        )
    return BuildiumApiFetchResult(
        records=records,
        mode=profile.mode,
        request_count=requests_made,
        parent_record_count=len(normalized_parent_ids),
    )


def fetch_lease_payments(
    *,
    expected_source_account_ref: str,
    parent_lease_ids: list[int | str],
) -> BuildiumApiFetchResult:
    """Fetch bounded Payment transactions from already-mapped parent Lease ledgers."""
    profile = _profile(expected_source_account_ref)

    normalized_parent_ids: list[int] = []
    seen_parent_ids: set[int] = set()
    for raw_parent_id in parent_lease_ids:
        if isinstance(raw_parent_id, bool):
            raise BuildiumApiTransportError(
                "invalid_parent_scope",
                "Buildium Lease Payment parent Lease scope contains an invalid source ID.",
            )
        try:
            parent_id = int(str(raw_parent_id).strip())
        except (TypeError, ValueError):
            raise BuildiumApiTransportError(
                "invalid_parent_scope",
                "Buildium Lease Payment parent Lease scope contains an invalid source ID.",
            )
        if parent_id < 1:
            raise BuildiumApiTransportError(
                "invalid_parent_scope",
                "Buildium Lease Payment parent Lease scope contains an invalid source ID.",
            )
        if parent_id in seen_parent_ids:
            raise BuildiumApiTransportError(
                "invalid_parent_scope",
                "Buildium Lease Payment parent Lease scope contains a duplicate source ID.",
            )
        seen_parent_ids.add(parent_id)
        normalized_parent_ids.append(parent_id)

    if not normalized_parent_ids:
        raise BuildiumApiTransportError(
            "empty_parent_scope",
            "Buildium Lease Payment API migration requires at least one durably mapped parent Lease.",
        )
    if len(normalized_parent_ids) > MAX_LEASE_PAYMENT_PARENT_LEASES:
        raise BuildiumApiTransportError(
            "source_too_large",
            "Buildium Lease Payment API migration exceeds the bounded "
            f"{MAX_LEASE_PAYMENT_PARENT_LEASES}-parent-Lease review scope.",
        )

    records: list[dict[str, Any]] = []
    requests_made = 0
    for parent_lease_id in sorted(normalized_parent_ids):
        remaining = MAX_LEASE_PAYMENT_RECORDS - len(records)
        request_limit = max(1, min(1000, remaining + 1))
        page = _get_json_list(
            profile,
            path=f"/v1/leases/{parent_lease_id}/transactions",
            resource_label=f"lease Payment transactions for parent Lease {parent_lease_id}",
            offset=0,
            limit=request_limit,
            extra_params={"transactiontypes": "Payment"},
        )
        requests_made += 1
        if len(page) > remaining:
            raise BuildiumApiTransportError(
                "source_too_large",
                "Buildium Lease Payment source exceeds the bounded "
                f"{MAX_LEASE_PAYMENT_RECORDS}-record API migration review.",
            )
        for provider_record in page:
            record = dict(provider_record)
            record["LeaseId"] = parent_lease_id
            records.append(record)

    if not records:
        raise BuildiumApiTransportError(
            "empty_source",
            "Buildium API returned no Lease Payments for the mapped parent Leases.",
        )
    return BuildiumApiFetchResult(
        records=records,
        mode=profile.mode,
        request_count=requests_made,
        parent_record_count=len(normalized_parent_ids),
    )


def fetch_bill_payments(
    *,
    expected_source_account_ref: str,
    parent_bill_ids: list[int | str],
) -> BuildiumApiFetchResult:
    """Fetch a bounded nested Bill Payment source for already-mapped parent Bills."""
    profile = _profile(expected_source_account_ref)

    normalized_parent_ids: list[int] = []
    seen_parent_ids: set[int] = set()
    for raw_parent_id in parent_bill_ids:
        if isinstance(raw_parent_id, bool):
            raise BuildiumApiTransportError(
                "invalid_parent_scope",
                "Buildium Bill Payment parent Bill scope contains an invalid source ID.",
            )
        try:
            parent_id = int(str(raw_parent_id).strip())
        except (TypeError, ValueError):
            raise BuildiumApiTransportError(
                "invalid_parent_scope",
                "Buildium Bill Payment parent Bill scope contains an invalid source ID.",
            )
        if parent_id < 1:
            raise BuildiumApiTransportError(
                "invalid_parent_scope",
                "Buildium Bill Payment parent Bill scope contains an invalid source ID.",
            )
        if parent_id in seen_parent_ids:
            raise BuildiumApiTransportError(
                "invalid_parent_scope",
                "Buildium Bill Payment parent Bill scope contains a duplicate source ID.",
            )
        seen_parent_ids.add(parent_id)
        normalized_parent_ids.append(parent_id)

    if not normalized_parent_ids:
        raise BuildiumApiTransportError(
            "empty_parent_scope",
            "Buildium Bill Payment API migration requires at least one durably mapped parent Bill.",
        )
    if len(normalized_parent_ids) > MAX_BILL_PAYMENT_PARENT_BILLS:
        raise BuildiumApiTransportError(
            "source_too_large",
            "Buildium Bill Payment API migration exceeds the bounded "
            f"{MAX_BILL_PAYMENT_PARENT_BILLS}-parent-Bill review scope.",
        )

    records: list[dict[str, Any]] = []
    requests_made = 0
    for parent_bill_id in sorted(normalized_parent_ids):
        remaining = MAX_BILL_PAYMENT_RECORDS - len(records)
        # Ask for one more than the remaining review capacity so overflow is
        # detected on the same bounded parent request without paging forever.
        request_limit = max(1, min(1000, remaining + 1))
        page = _get_json_list(
            profile,
            path=f"/v1/bills/{parent_bill_id}/payments",
            resource_label=f"bill payments for parent Bill {parent_bill_id}",
            offset=0,
            limit=request_limit,
        )
        requests_made += 1
        if len(page) > remaining:
            raise BuildiumApiTransportError(
                "source_too_large",
                "Buildium Bill Payment source exceeds the bounded "
                f"{MAX_BILL_PAYMENT_RECORDS}-record API migration review.",
            )
        for provider_record in page:
            record = dict(provider_record)
            record["_ParentBillId"] = parent_bill_id
            records.append(record)

    if not records:
        raise BuildiumApiTransportError(
            "empty_source",
            "Buildium API returned no Bill Payments for the mapped parent Bills.",
        )
    return BuildiumApiFetchResult(
        records=records,
        mode=profile.mode,
        request_count=requests_made,
        parent_record_count=len(normalized_parent_ids),
    )


def _get_json_object(
    profile: _Profile,
    *,
    path: str,
    resource_label: str,
) -> dict[str, Any]:
    try:
        response = requests.get(
            f"{profile.base_url}{path}",
            headers={
                "x-buildium-client-id": profile.client_id,
                "x-buildium-client-secret": profile.client_secret,
                "Accept": "application/json",
            },
            timeout=_TIMEOUT_SECONDS,
        )
    except requests.RequestException as exc:
        raise BuildiumApiTransportError(
            "unavailable", "Buildium API transport is unavailable."
        ) from exc

    if response.status_code == 401:
        raise BuildiumApiTransportError(
            "unauthorized", "Buildium rejected the configured API credentials."
        )
    if response.status_code == 403:
        raise BuildiumApiTransportError(
            "forbidden",
            f"Buildium API credentials lack permission for {resource_label}.",
        )
    if response.status_code == 429:
        raise BuildiumApiTransportError(
            "rate_limited",
            "Buildium API rate limit was reached; retry the migration transport request.",
        )
    if response.status_code != 200:
        raise BuildiumApiTransportError(
            "upstream_error",
            f"Buildium API request failed with HTTP {response.status_code}.",
        )
    try:
        payload = response.json()
    except ValueError as exc:
        raise BuildiumApiTransportError(
            "invalid_response", "Buildium API returned an invalid JSON response."
        ) from exc
    if not isinstance(payload, dict):
        raise BuildiumApiTransportError(
            "invalid_response",
            f"Buildium API returned an unexpected {resource_label} response.",
        )
    return payload


def fetch_bank_reconciliations(
    *,
    expected_source_account_ref: str,
    parent_bank_account_ids: list[int | str],
) -> BuildiumApiFetchResult:
    """Fetch bounded nested Bank Reconciliations and documented balance payloads."""
    profile = _profile(expected_source_account_ref)

    normalized_parent_ids: list[int] = []
    seen_parent_ids: set[int] = set()
    for raw_parent_id in parent_bank_account_ids:
        if isinstance(raw_parent_id, bool):
            raise BuildiumApiTransportError(
                "invalid_parent_scope",
                "Buildium Bank Reconciliation parent Bank Account scope contains an invalid source ID.",
            )
        try:
            parent_id = int(str(raw_parent_id).strip())
        except (TypeError, ValueError):
            raise BuildiumApiTransportError(
                "invalid_parent_scope",
                "Buildium Bank Reconciliation parent Bank Account scope contains an invalid source ID.",
            )
        if parent_id < 1:
            raise BuildiumApiTransportError(
                "invalid_parent_scope",
                "Buildium Bank Reconciliation parent Bank Account scope contains an invalid source ID.",
            )
        if parent_id in seen_parent_ids:
            raise BuildiumApiTransportError(
                "invalid_parent_scope",
                "Buildium Bank Reconciliation parent Bank Account scope contains a duplicate source ID.",
            )
        seen_parent_ids.add(parent_id)
        normalized_parent_ids.append(parent_id)

    if not normalized_parent_ids:
        raise BuildiumApiTransportError(
            "empty_parent_scope",
            "Buildium Bank Reconciliation API migration requires at least one durably mapped parent Bank Account.",
        )
    if len(normalized_parent_ids) > MAX_BANK_RECONCILIATION_PARENT_BANK_ACCOUNTS:
        raise BuildiumApiTransportError(
            "source_too_large",
            "Buildium Bank Reconciliation API migration exceeds the bounded "
            f"{MAX_BANK_RECONCILIATION_PARENT_BANK_ACCOUNTS}-parent-Bank-Account review scope.",
        )

    records: list[dict[str, Any]] = []
    requests_made = 0
    detail_requests = 0
    for parent_bank_account_id in sorted(normalized_parent_ids):
        remaining = MAX_BANK_RECONCILIATION_RECORDS - len(records)
        request_limit = max(1, min(1000, remaining + 1))
        page = _get_json_list(
            profile,
            path=f"/v1/bankaccounts/{parent_bank_account_id}/reconciliations",
            resource_label=f"bank reconciliations for parent Bank Account {parent_bank_account_id}",
            offset=0,
            limit=request_limit,
        )
        requests_made += 1
        if len(page) > remaining:
            raise BuildiumApiTransportError(
                "source_too_large",
                "Buildium Bank Reconciliation source exceeds the bounded "
                f"{MAX_BANK_RECONCILIATION_RECORDS}-record API migration review.",
            )
        for provider_record in page:
            raw_reconciliation_id = provider_record.get("Id")
            if isinstance(raw_reconciliation_id, bool):
                raise BuildiumApiTransportError(
                    "invalid_response",
                    "Buildium API returned a Bank Reconciliation without a valid positive identifier.",
                )
            try:
                reconciliation_id = int(raw_reconciliation_id)
            except (TypeError, ValueError):
                raise BuildiumApiTransportError(
                    "invalid_response",
                    "Buildium API returned a Bank Reconciliation without a valid positive identifier.",
                )
            if reconciliation_id < 1:
                raise BuildiumApiTransportError(
                    "invalid_response",
                    "Buildium API returned a Bank Reconciliation without a valid positive identifier.",
                )
            balance = _get_json_object(
                profile,
                path=(
                    f"/v1/bankaccounts/{parent_bank_account_id}/reconciliations/"
                    f"{reconciliation_id}/balances"
                ),
                resource_label=f"bank reconciliation balance for parent Bank Account {parent_bank_account_id}",
            )
            requests_made += 1
            detail_requests += 1
            record = dict(provider_record)
            record["BankAccountId"] = parent_bank_account_id
            record["Balance"] = balance
            records.append(record)

    if not records:
        raise BuildiumApiTransportError(
            "empty_source",
            "Buildium API returned no Bank Reconciliations for the mapped parent Bank Accounts.",
        )
    return BuildiumApiFetchResult(
        records=records,
        mode=profile.mode,
        request_count=requests_made,
        parent_record_count=len(normalized_parent_ids),
        detail_request_count=detail_requests,
    )


def fetch_bank_transfers(
    *,
    expected_source_account_ref: str,
    parent_bank_account_ids: list[int | str],
) -> BuildiumApiFetchResult:
    """Fetch bounded nested Bank Transfers for already-mapped source Bank Accounts."""
    profile = _profile(expected_source_account_ref)

    normalized_parent_ids: list[int] = []
    seen_parent_ids: set[int] = set()
    for raw_parent_id in parent_bank_account_ids:
        if isinstance(raw_parent_id, bool):
            raise BuildiumApiTransportError(
                "invalid_parent_scope",
                "Buildium Bank Transfer parent Bank Account scope contains an invalid source ID.",
            )
        try:
            parent_id = int(str(raw_parent_id).strip())
        except (TypeError, ValueError):
            raise BuildiumApiTransportError(
                "invalid_parent_scope",
                "Buildium Bank Transfer parent Bank Account scope contains an invalid source ID.",
            )
        if parent_id < 1:
            raise BuildiumApiTransportError(
                "invalid_parent_scope",
                "Buildium Bank Transfer parent Bank Account scope contains an invalid source ID.",
            )
        if parent_id in seen_parent_ids:
            raise BuildiumApiTransportError(
                "invalid_parent_scope",
                "Buildium Bank Transfer parent Bank Account scope contains a duplicate source ID.",
            )
        seen_parent_ids.add(parent_id)
        normalized_parent_ids.append(parent_id)

    if not normalized_parent_ids:
        raise BuildiumApiTransportError(
            "empty_parent_scope",
            "Buildium Bank Transfer API migration requires at least one durably mapped parent Bank Account.",
        )
    if len(normalized_parent_ids) > MAX_BANK_TRANSFER_PARENT_BANK_ACCOUNTS:
        raise BuildiumApiTransportError(
            "source_too_large",
            "Buildium Bank Transfer API migration exceeds the bounded "
            f"{MAX_BANK_TRANSFER_PARENT_BANK_ACCOUNTS}-parent-Bank-Account review scope.",
        )

    records: list[dict[str, Any]] = []
    requests_made = 0
    for parent_bank_account_id in sorted(normalized_parent_ids):
        remaining = MAX_BANK_TRANSFER_RECORDS - len(records)
        request_limit = max(1, min(1000, remaining + 1))
        page = _get_json_list(
            profile,
            path=f"/v1/bankaccounts/{parent_bank_account_id}/transfers",
            resource_label=f"bank transfers for source Bank Account {parent_bank_account_id}",
            offset=0,
            limit=request_limit,
        )
        requests_made += 1
        if len(page) > remaining:
            raise BuildiumApiTransportError(
                "source_too_large",
                "Buildium Bank Transfer source exceeds the bounded "
                f"{MAX_BANK_TRANSFER_RECORDS}-record API migration review.",
            )
        for provider_record in page:
            record = dict(provider_record)
            record["SourceBankAccountId"] = parent_bank_account_id
            records.append(record)

    if not records:
        raise BuildiumApiTransportError(
            "empty_source",
            "Buildium API returned no Bank Transfers for the mapped parent Bank Accounts.",
        )
    return BuildiumApiFetchResult(
        records=records,
        mode=profile.mode,
        request_count=requests_made,
        parent_record_count=len(normalized_parent_ids),
    )


def fetch_bank_withdrawals(
    *,
    expected_source_account_ref: str,
    parent_bank_account_ids: list[int | str],
    start_date: date,
    end_date: date,
) -> BuildiumApiFetchResult:
    """Fetch bounded nested Bank Withdrawals for mapped source Bank Accounts."""
    profile = _profile(expected_source_account_ref)
    if not isinstance(start_date, date) or not isinstance(end_date, date):
        raise BuildiumApiTransportError(
            "invalid_date_window",
            "Buildium Bank Withdrawal API migration requires explicit start and end dates.",
        )
    if start_date > end_date:
        raise BuildiumApiTransportError(
            "invalid_date_window",
            "Buildium Bank Withdrawal API migration start date must not be after end date.",
        )

    normalized_parent_ids: list[int] = []
    seen_parent_ids: set[int] = set()
    for raw_parent_id in parent_bank_account_ids:
        if isinstance(raw_parent_id, bool):
            raise BuildiumApiTransportError(
                "invalid_parent_scope",
                "Buildium Bank Withdrawal parent Bank Account scope contains an invalid source ID.",
            )
        try:
            parent_id = int(str(raw_parent_id).strip())
        except (TypeError, ValueError):
            raise BuildiumApiTransportError(
                "invalid_parent_scope",
                "Buildium Bank Withdrawal parent Bank Account scope contains an invalid source ID.",
            )
        if parent_id < 1:
            raise BuildiumApiTransportError(
                "invalid_parent_scope",
                "Buildium Bank Withdrawal parent Bank Account scope contains an invalid source ID.",
            )
        if parent_id in seen_parent_ids:
            raise BuildiumApiTransportError(
                "invalid_parent_scope",
                "Buildium Bank Withdrawal parent Bank Account scope contains a duplicate source ID.",
            )
        seen_parent_ids.add(parent_id)
        normalized_parent_ids.append(parent_id)

    if not normalized_parent_ids:
        raise BuildiumApiTransportError(
            "empty_parent_scope",
            "Buildium Bank Withdrawal API migration requires at least one durably mapped parent Bank Account.",
        )
    if len(normalized_parent_ids) > MAX_BANK_WITHDRAWAL_PARENT_BANK_ACCOUNTS:
        raise BuildiumApiTransportError(
            "source_too_large",
            "Buildium Bank Withdrawal API migration exceeds the bounded "
            f"{MAX_BANK_WITHDRAWAL_PARENT_BANK_ACCOUNTS}-parent-Bank-Account review scope.",
        )

    records: list[dict[str, Any]] = []
    requests_made = 0
    start_text = start_date.isoformat()
    end_text = end_date.isoformat()
    for parent_bank_account_id in sorted(normalized_parent_ids):
        remaining = MAX_BANK_WITHDRAWAL_RECORDS - len(records)
        request_limit = max(1, min(1000, remaining + 1))
        page = _get_json_list(
            profile,
            path=f"/v1/bankaccounts/{parent_bank_account_id}/withdrawals",
            resource_label=f"bank withdrawals for source Bank Account {parent_bank_account_id}",
            offset=0,
            limit=request_limit,
            extra_params={"startdate": start_text, "enddate": end_text},
        )
        requests_made += 1
        if len(page) > remaining:
            raise BuildiumApiTransportError(
                "source_too_large",
                "Buildium Bank Withdrawal source exceeds the bounded "
                f"{MAX_BANK_WITHDRAWAL_RECORDS}-record API migration review.",
            )
        for provider_record in page:
            record = dict(provider_record)
            record["SourceBankAccountId"] = parent_bank_account_id
            # Bind the explicit provider query scope into the reviewed source
            # fingerprint without persisting a raw provider response body.
            record["_ApiStartDate"] = start_text
            record["_ApiEndDate"] = end_text
            records.append(record)

    if not records:
        raise BuildiumApiTransportError(
            "empty_source",
            "Buildium API returned no Bank Withdrawals for the mapped Bank Accounts and reviewed date window.",
        )
    return BuildiumApiFetchResult(
        records=records,
        mode=profile.mode,
        request_count=requests_made,
        parent_record_count=len(normalized_parent_ids),
    )


def fetch_quick_deposits(
    *,
    expected_source_account_ref: str,
    parent_bank_account_ids: list[int | str],
    start_date: date,
    end_date: date,
) -> BuildiumApiFetchResult:
    """Fetch bounded nested Quick Deposits for mapped source Bank Accounts."""
    profile = _profile(expected_source_account_ref)
    if not isinstance(start_date, date) or not isinstance(end_date, date):
        raise BuildiumApiTransportError(
            "invalid_date_window",
            "Buildium Quick Deposit API migration requires explicit start and end dates.",
        )
    if start_date > end_date:
        raise BuildiumApiTransportError(
            "invalid_date_window",
            "Buildium Quick Deposit API migration start date must not be after end date.",
        )

    normalized_parent_ids: list[int] = []
    seen_parent_ids: set[int] = set()
    for raw_parent_id in parent_bank_account_ids:
        if isinstance(raw_parent_id, bool):
            raise BuildiumApiTransportError(
                "invalid_parent_scope",
                "Buildium Quick Deposit parent Bank Account scope contains an invalid source ID.",
            )
        try:
            parent_id = int(str(raw_parent_id).strip())
        except (TypeError, ValueError):
            raise BuildiumApiTransportError(
                "invalid_parent_scope",
                "Buildium Quick Deposit parent Bank Account scope contains an invalid source ID.",
            )
        if parent_id < 1:
            raise BuildiumApiTransportError(
                "invalid_parent_scope",
                "Buildium Quick Deposit parent Bank Account scope contains an invalid source ID.",
            )
        if parent_id in seen_parent_ids:
            raise BuildiumApiTransportError(
                "invalid_parent_scope",
                "Buildium Quick Deposit parent Bank Account scope contains a duplicate source ID.",
            )
        seen_parent_ids.add(parent_id)
        normalized_parent_ids.append(parent_id)

    if not normalized_parent_ids:
        raise BuildiumApiTransportError(
            "empty_parent_scope",
            "Buildium Quick Deposit API migration requires at least one durably mapped parent Bank Account.",
        )
    if len(normalized_parent_ids) > MAX_QUICK_DEPOSIT_PARENT_BANK_ACCOUNTS:
        raise BuildiumApiTransportError(
            "source_too_large",
            "Buildium Quick Deposit API migration exceeds the bounded "
            f"{MAX_QUICK_DEPOSIT_PARENT_BANK_ACCOUNTS}-parent-Bank-Account review scope.",
        )

    records: list[dict[str, Any]] = []
    requests_made = 0
    start_text = start_date.isoformat()
    end_text = end_date.isoformat()
    for parent_bank_account_id in sorted(normalized_parent_ids):
        remaining = MAX_QUICK_DEPOSIT_RECORDS - len(records)
        request_limit = max(1, min(1000, remaining + 1))
        page = _get_json_list(
            profile,
            path=f"/v1/bankaccounts/{parent_bank_account_id}/quickdeposits",
            resource_label=f"quick deposits for source Bank Account {parent_bank_account_id}",
            offset=0,
            limit=request_limit,
            extra_params={"startdate": start_text, "enddate": end_text},
        )
        requests_made += 1
        if len(page) > remaining:
            raise BuildiumApiTransportError(
                "source_too_large",
                "Buildium Quick Deposit source exceeds the bounded "
                f"{MAX_QUICK_DEPOSIT_RECORDS}-record API migration review.",
            )
        for provider_record in page:
            record = dict(provider_record)
            record["SourceBankAccountId"] = parent_bank_account_id
            record["_ApiStartDate"] = start_text
            record["_ApiEndDate"] = end_text
            records.append(record)

    if not records:
        raise BuildiumApiTransportError(
            "empty_source",
            "Buildium API returned no Quick Deposits for the mapped Bank Accounts and reviewed date window.",
        )
    return BuildiumApiFetchResult(
        records=records,
        mode=profile.mode,
        request_count=requests_made,
        parent_record_count=len(normalized_parent_ids),
    )
