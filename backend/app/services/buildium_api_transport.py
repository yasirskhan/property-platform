"""Server-to-server Buildium Open API transport for Phase 4.14.

The migration pipeline owns staging, review, exact fingerprints, mappings and
commits. This module only retrieves bounded provider records. Credentials are
read from server settings, never accepted from migration request payloads, and
provider response bodies are never copied into errors or audit logs.
"""
from __future__ import annotations

from dataclasses import dataclass
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
_MAX_REVIEW_RECORDS = 500
_PAGE_LIMIT = 500
_TIMEOUT_SECONDS = 20


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
) -> list[dict[str, Any]]:
    try:
        response = requests.get(
            f"{profile.base_url}{path}",
            headers={
                "x-buildium-client-id": profile.client_id,
                "x-buildium-client-secret": profile.client_secret,
                "Accept": "application/json",
            },
            params={"offset": offset, "limit": limit},
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
