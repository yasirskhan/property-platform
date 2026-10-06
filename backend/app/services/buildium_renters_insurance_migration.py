"""Buildium renters-insurance existing-target reconciliation for Phase 4.14.

The Buildium policy resource is retrieved under a specific Lease path. This
bounded adapter requires that source Lease id as explicit retrieval context,
supports only one insured tenant per policy because the target policy model is
tenant-specific, and reconciles only to an already-existing TenantInsurance
record. It never creates or edits insurance, lease, tenant, document, payment,
or accounting data.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
import hashlib
import json
from typing import Any

from sqlalchemy.orm import Session

from app.models.lease import Lease
from app.models.platform_migration import PlatformMigrationItem, PlatformMigrationRun
from app.models.property import Property, Unit
from app.models.tenant_insurance import TenantInsurance
from app.models.user import User, UserRole


class BuildiumRentersInsuranceMigrationError(ValueError):
    pass


@dataclass(frozen=True)
class RentersInsuranceDryRunResult:
    fingerprint: str
    replayed: bool
    total: int
    reviewable: int
    skipped_review: int
    invalid: int
    warning_count: int
    rows: list[dict[str, Any]]
    summary: dict[str, Any]


@dataclass(frozen=True)
class RentersInsuranceCommitResult:
    fingerprint: str
    replayed: bool
    matched_existing: int
    skipped_review: int
    warning_count: int
    rows: list[dict[str, Any]]


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _positive_id(value: Any) -> str | None:
    if isinstance(value, bool):
        return None
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return str(number) if number > 0 else None


def _date_value(value: Any, *, field: str) -> tuple[date | None, str | None]:
    text = _clean(value)
    if text is None:
        return None, None
    try:
        return date.fromisoformat(text), None
    except ValueError:
        return None, f"{field} must be an ISO date (YYYY-MM-DD) when supplied."


def _mapping(
    db: Session,
    *,
    run: PlatformMigrationRun,
    resource: str,
    source_id: str,
    target_entity: str,
) -> PlatformMigrationItem | None:
    row = (
        db.query(PlatformMigrationItem)
        .filter(
            PlatformMigrationItem.run_id == run.id,
            PlatformMigrationItem.organization_id == run.organization_id,
            PlatformMigrationItem.provider == "BUILDIUM",
            PlatformMigrationItem.resource == resource,
            PlatformMigrationItem.source_id == source_id,
        )
        .first()
    )
    if row is not None and row.target_entity != target_entity:
        raise BuildiumRentersInsuranceMigrationError(
            f"Buildium {resource} mapping for source ID {source_id} is inconsistent."
        )
    return row


def _normalize_resolutions(
    items: list[dict[str, Any]] | None,
) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for item in items or []:
        source_id = _positive_id(item.get("source_id"))
        if source_id is None or source_id in result:
            raise BuildiumRentersInsuranceMigrationError(
                "Renters Insurance review requires unique positive source_id values."
            )
        action = _clean(item.get("action"))
        if action not in {"MATCH_EXISTING", "SKIP"}:
            raise BuildiumRentersInsuranceMigrationError(
                "Renters Insurance review supports only MATCH_EXISTING or SKIP."
            )
        target_id = item.get("target_tenant_insurance_id")
        if action == "MATCH_EXISTING":
            if isinstance(target_id, bool):
                target_id = None
            try:
                target_id = int(target_id)
            except (TypeError, ValueError):
                target_id = None
            if target_id is None or target_id < 1:
                raise BuildiumRentersInsuranceMigrationError(
                    "MATCH_EXISTING requires a positive target_tenant_insurance_id."
                )
        elif target_id is not None:
            raise BuildiumRentersInsuranceMigrationError(
                "target_tenant_insurance_id is only valid for MATCH_EXISTING."
            )
        result[source_id] = {
            "source_id": int(source_id),
            "action": action,
            "target_tenant_insurance_id": target_id,
        }
    return result


def _target_policy(
    db: Session,
    *,
    run: PlatformMigrationRun,
    target_id: int,
) -> TenantInsurance | None:
    return (
        db.query(TenantInsurance)
        .join(Lease, Lease.id == TenantInsurance.lease_id)
        .join(Unit, Unit.id == Lease.unit_id)
        .join(Property, Property.id == Unit.property_id)
        .filter(
            TenantInsurance.id == target_id,
            Property.organization_id == run.organization_id,
        )
        .first()
    )


def _target_snapshot(
    db: Session,
    *,
    run: PlatformMigrationRun,
    target_id: int,
) -> dict[str, Any] | None:
    row = _target_policy(db, run=run, target_id=target_id)
    if row is None:
        return None
    status = row.status.value if hasattr(row.status, "value") else str(row.status)
    return {
        "id": row.id,
        "lease_id": row.lease_id,
        "tenant_id": row.tenant_id,
        "property_id": row.property_id,
        "provider": row.provider,
        "policy_number": row.policy_number,
        "coverage_amount": (
            str(Decimal(row.coverage_amount).quantize(Decimal("0.01")))
            if row.coverage_amount is not None
            else None
        ),
        "effective_date": row.effective_date.isoformat() if row.effective_date else None,
        "expiration_date": row.expiration_date.isoformat() if row.expiration_date else None,
        "status": status,
        "document_url": row.document_url,
    }


def _source_record(
    db: Session,
    *,
    run: PlatformMigrationRun,
    record: dict[str, Any],
) -> tuple[dict[str, Any] | None, str | None, list[str]]:
    source_id = _positive_id(record.get("Id"))
    lease_source_id = _positive_id(record.get("SourceLeaseId"))
    if source_id is None:
        return None, "Buildium Renters Insurance Id must be a positive integer.", []
    if lease_source_id is None:
        return None, "SourceLeaseId retrieval context must be a positive integer.", []

    cancellation_date, cancellation_error = _date_value(
        record.get("CancellationDate"),
        field="CancellationDate",
    )
    if cancellation_error:
        return None, cancellation_error, []
    if cancellation_date is not None:
        return None, (
            "Cancelled Buildium renters-insurance policies are blocked because the "
            "target TenantInsurance contract has no cancellation-date field and the "
            "source cancellation fact must not be discarded."
        ), []

    effective_date, effective_error = _date_value(
        record.get("EffectiveDate"),
        field="EffectiveDate",
    )
    expiration_date, expiration_error = _date_value(
        record.get("ExpirationDate"),
        field="ExpirationDate",
    )
    if effective_error:
        return None, effective_error, []
    if expiration_error:
        return None, expiration_error, []
    if (
        effective_date is not None
        and expiration_date is not None
        and expiration_date < effective_date
    ):
        return None, "ExpirationDate cannot be before EffectiveDate.", []

    insured = record.get("InsuredTenants")
    if not isinstance(insured, list) or len(insured) != 1 or not isinstance(insured[0], dict):
        return None, (
            "This bounded renters-insurance batch requires exactly one documented "
            "InsuredTenant because the target policy stores one tenant_id."
        ), []
    tenant_source_id = _positive_id(insured[0].get("Id"))
    if tenant_source_id is None:
        return None, "InsuredTenant Id must be a positive integer.", []

    lease_mapping = _mapping(
        db,
        run=run,
        resource="LEASES",
        source_id=lease_source_id,
        target_entity="LEASE_RELATIONSHIP",
    )
    if lease_mapping is None:
        return None, (
            "Renters Insurance reconciliation requires a durable same-run "
            "Buildium Lease mapping."
        ), []
    tenant_mapping = _mapping(
        db,
        run=run,
        resource="TENANTS",
        source_id=tenant_source_id,
        target_entity="TENANT_USER",
    )
    if tenant_mapping is None:
        return None, (
            "Renters Insurance reconciliation requires a durable same-run "
            "Buildium Tenant mapping."
        ), []

    lease = (
        db.query(Lease)
        .join(Unit, Unit.id == Lease.unit_id)
        .join(Property, Property.id == Unit.property_id)
        .filter(
            Lease.id == lease_mapping.target_id,
            Property.organization_id == run.organization_id,
            Property.deleted_at.is_(None),
        )
        .first()
    )
    if lease is None:
        return None, "Mapped target Lease is no longer in the target organization.", []
    tenant = (
        db.query(User)
        .filter(
            User.id == tenant_mapping.target_id,
            User.organization_id == run.organization_id,
            User.role == UserRole.TENANT,
            User.deleted_at.is_(None),
        )
        .first()
    )
    if tenant is None:
        return None, "Mapped target Tenant is no longer in the target organization.", []
    if lease.tenant_id != tenant.id:
        return None, (
            "Mapped Buildium Lease and Tenant no longer point to the same target "
            "lease relationship."
        ), []

    unit = (
        db.query(Unit)
        .join(Property, Property.id == Unit.property_id)
        .filter(
            Unit.id == lease.unit_id,
            Property.organization_id == run.organization_id,
            Property.deleted_at.is_(None),
        )
        .first()
    )
    if unit is None:
        return None, "Mapped target Lease Unit/Property is no longer in scope.", []

    insurance_company = _clean(record.get("InsuranceCompany"))
    policy_identifier = _clean(record.get("PolicyIdentifier"))
    carrier_type = _clean(record.get("CarrierType"))
    warnings = [
        "This batch reconciles an existing tenant-insurance record only; it never creates or updates a policy.",
        "Buildium does not supply target coverage_amount, document_url, or local verification status in this policy contract; those target-only fields are not inferred or overwritten.",
    ]
    if carrier_type is not None:
        warnings.append(
            "Buildium CarrierType is source metadata not represented by the target TenantInsurance model; it remains fingerprint-bound but is not copied."
        )

    return {
        "source_id": source_id,
        "source_lease_id": lease_source_id,
        "target_lease_id": lease.id,
        "lease_mapping_fingerprint": lease_mapping.source_fingerprint,
        "source_tenant_id": tenant_source_id,
        "target_tenant_id": tenant.id,
        "tenant_mapping_fingerprint": tenant_mapping.source_fingerprint,
        "target_property_id": unit.property_id,
        "insurance_company": insurance_company,
        "carrier_type": carrier_type,
        "policy_identifier": policy_identifier,
        "effective_date": effective_date,
        "expiration_date": expiration_date,
    }, None, warnings


def _policy_match_reason(
    *,
    policy: TenantInsurance,
    mapped: dict[str, Any],
) -> str | None:
    if policy.lease_id != mapped["target_lease_id"]:
        return "Target TenantInsurance Lease does not match the durable Buildium Lease mapping."
    if policy.tenant_id != mapped["target_tenant_id"]:
        return "Target TenantInsurance tenant does not match the durable Buildium Tenant mapping."
    if policy.property_id != mapped["target_property_id"]:
        return "Target TenantInsurance property does not match the mapped Lease property."
    if _clean(policy.provider) != mapped["insurance_company"]:
        return "Target TenantInsurance provider does not match Buildium InsuranceCompany."
    if _clean(policy.policy_number) != mapped["policy_identifier"]:
        return "Target TenantInsurance policy number does not match Buildium PolicyIdentifier."
    if policy.effective_date != mapped["effective_date"]:
        return "Target TenantInsurance effective date does not match Buildium EffectiveDate."
    if policy.expiration_date != mapped["expiration_date"]:
        return "Target TenantInsurance expiration date does not match Buildium ExpirationDate."
    return None


def _dependency_snapshot(
    db: Session,
    *,
    run: PlatformMigrationRun,
    records: list[dict[str, Any]],
    resolution_map: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for record in records:
        source_id = _positive_id(record.get("Id"))
        lease_source_id = _positive_id(record.get("SourceLeaseId"))
        insured = record.get("InsuredTenants")
        tenant_source_id = (
            _positive_id(insured[0].get("Id"))
            if isinstance(insured, list)
            and len(insured) == 1
            and isinstance(insured[0], dict)
            else None
        )
        lease_mapping = (
            _mapping(
                db,
                run=run,
                resource="LEASES",
                source_id=lease_source_id,
                target_entity="LEASE_RELATIONSHIP",
            )
            if lease_source_id is not None
            else None
        )
        tenant_mapping = (
            _mapping(
                db,
                run=run,
                resource="TENANTS",
                source_id=tenant_source_id,
                target_entity="TENANT_USER",
            )
            if tenant_source_id is not None
            else None
        )
        durable = (
            _mapping(
                db,
                run=run,
                resource="RENTERS_INSURANCE",
                source_id=source_id,
                target_entity="TENANT_INSURANCE_RELATIONSHIP",
            )
            if source_id is not None
            else None
        )
        resolution = resolution_map.get(source_id or "")
        reviewed_target_id = (
            resolution.get("target_tenant_insurance_id")
            if resolution and resolution.get("action") == "MATCH_EXISTING"
            else None
        )
        snapshot_target_id = durable.target_id if durable is not None else reviewed_target_id
        result.append(
            {
                "source_id": source_id,
                "lease_mapping": (
                    {
                        "target_id": lease_mapping.target_id,
                        "source_fingerprint": lease_mapping.source_fingerprint,
                    }
                    if lease_mapping is not None
                    else None
                ),
                "tenant_mapping": (
                    {
                        "target_id": tenant_mapping.target_id,
                        "source_fingerprint": tenant_mapping.source_fingerprint,
                    }
                    if tenant_mapping is not None
                    else None
                ),
                "durable_target_id": durable.target_id if durable is not None else None,
                "target_snapshot": (
                    _target_snapshot(db, run=run, target_id=snapshot_target_id)
                    if snapshot_target_id is not None
                    else None
                ),
            }
        )
    return result


def _fingerprint(
    db: Session,
    *,
    run: PlatformMigrationRun,
    records: list[dict[str, Any]],
    resolutions: list[dict[str, Any]] | None,
) -> str:
    resolution_map = _normalize_resolutions(resolutions)
    payload = {
        "provider": "BUILDIUM",
        "resource": "RENTERS_INSURANCE",
        "organization_id": run.organization_id,
        "source_account_ref": run.source_account_ref,
        "records": records,
        "resolutions": [
            resolution_map[key] for key in sorted(resolution_map, key=int)
        ],
        "dependencies": _dependency_snapshot(
            db,
            run=run,
            records=records,
            resolution_map=resolution_map,
        ),
    }
    return hashlib.sha256(
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        ).encode("utf-8")
    ).hexdigest()


def dry_run_renters_insurance(
    db: Session,
    *,
    run: PlatformMigrationRun,
    records: list[dict[str, Any]],
    resolutions: list[dict[str, Any]] | None = None,
) -> RentersInsuranceDryRunResult:
    if run.provider != "BUILDIUM":
        raise BuildiumRentersInsuranceMigrationError("Migration run is not a Buildium run.")
    if not records:
        raise BuildiumRentersInsuranceMigrationError(
            "At least one Buildium renters-insurance policy is required."
        )

    resolution_map = _normalize_resolutions(resolutions)
    fingerprint = _fingerprint(
        db,
        run=run,
        records=records,
        resolutions=resolutions,
    )
    replayed = run.last_dry_run_fingerprint == fingerprint

    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    valid: set[str] = set()
    reviewable = skipped = invalid = warning_count = 0

    for record in records:
        source_id = _positive_id(record.get("Id"))
        if source_id is not None and source_id in seen:
            rows.append(
                {
                    "source_id": source_id,
                    "reviewable": False,
                    "reason": "Duplicate Buildium Renters Insurance Id in this dry run.",
                    "mapped": None,
                    "warnings": [],
                }
            )
            invalid += 1
            continue
        if source_id is not None:
            seen.add(source_id)

        mapped, error, warnings = _source_record(db, run=run, record=record)
        if error is not None or mapped is None:
            rows.append(
                {
                    "source_id": source_id,
                    "reviewable": False,
                    "reason": error,
                    "mapped": None,
                    "warnings": warnings,
                }
            )
            invalid += 1
            warning_count += len(warnings)
            continue

        valid.add(source_id)
        resolution = resolution_map.get(source_id)
        action = resolution["action"] if resolution else None
        target_id = resolution["target_tenant_insurance_id"] if resolution else None
        durable = _mapping(
            db,
            run=run,
            resource="RENTERS_INSURANCE",
            source_id=source_id,
            target_entity="TENANT_INSURANCE_RELATIONSHIP",
        )
        if durable is not None:
            if resolution is not None and (
                action != "MATCH_EXISTING" or target_id != durable.target_id
            ):
                raise BuildiumRentersInsuranceMigrationError(
                    f"Buildium renters-insurance policy {source_id} already has a "
                    "durable mapping and cannot be re-resolved."
                )
            target = _target_policy(db, run=run, target_id=durable.target_id)
            if target is None:
                raise BuildiumRentersInsuranceMigrationError(
                    "Previously reconciled TenantInsurance target is missing or out of organization scope."
                )
            reason = _policy_match_reason(policy=target, mapped=mapped)
            if reason is not None:
                raise BuildiumRentersInsuranceMigrationError(
                    "Previously reconciled TenantInsurance target no longer matches: " + reason
                )
            warnings.append(
                f"Buildium renters-insurance policy {source_id} is already durably "
                f"reconciled to TenantInsurance #{target.id}; commit will replay."
            )

        if action == "SKIP":
            rows.append(
                {
                    "source_id": source_id,
                    "reviewable": False,
                    "reason": "Explicitly skipped after Buildium renters-insurance review.",
                    "mapped": None,
                    "warnings": warnings,
                    "resolution_action": "SKIP",
                    "resolution_target_tenant_insurance_id": None,
                }
            )
            skipped += 1
            warning_count += len(warnings)
            continue

        if action == "MATCH_EXISTING":
            target = _target_policy(db, run=run, target_id=target_id)
            if target is None:
                raise BuildiumRentersInsuranceMigrationError(
                    f"Reviewed target TenantInsurance #{target_id} is not in the target organization."
                )
            reason = _policy_match_reason(policy=target, mapped=mapped)
            if reason is not None:
                raise BuildiumRentersInsuranceMigrationError(reason)
            warnings.append(
                f"Reviewed MATCH_EXISTING target TenantInsurance #{target.id}; commit records migration metadata only."
            )
        else:
            candidates = (
                db.query(TenantInsurance)
                .filter(
                    TenantInsurance.lease_id == mapped["target_lease_id"],
                    TenantInsurance.tenant_id == mapped["target_tenant_id"],
                    TenantInsurance.property_id == mapped["target_property_id"],
                )
                .order_by(TenantInsurance.id.asc())
                .limit(100)
                .all()
            )
            exact = [
                row for row in candidates if _policy_match_reason(policy=row, mapped=mapped) is None
            ]
            if len(exact) == 1:
                warnings.append(
                    f"Possible exact existing TenantInsurance match: #{exact[0].id}; explicit MATCH_EXISTING review is required."
                )
            elif len(exact) > 1:
                warnings.append(
                    "Multiple exact target TenantInsurance records match this source policy; explicit review is required."
                )
            else:
                warnings.append(
                    "No exact existing TenantInsurance record matches this source policy; this bounded batch does not create one."
                )

        rows.append(
            {
                "source_id": source_id,
                "reviewable": True,
                "reason": None,
                "mapped": {
                    "source_lease_id": mapped["source_lease_id"],
                    "target_lease_id": mapped["target_lease_id"],
                    "source_tenant_id": mapped["source_tenant_id"],
                    "target_tenant_id": mapped["target_tenant_id"],
                    "target_property_id": mapped["target_property_id"],
                    "insurance_company": mapped["insurance_company"],
                    "carrier_type": mapped["carrier_type"],
                    "policy_identifier": mapped["policy_identifier"],
                    "effective_date": (
                        mapped["effective_date"].isoformat()
                        if mapped["effective_date"] is not None
                        else None
                    ),
                    "expiration_date": (
                        mapped["expiration_date"].isoformat()
                        if mapped["expiration_date"] is not None
                        else None
                    ),
                    "target_tenant_insurance_id": target_id,
                },
                "warnings": warnings,
                "resolution_action": action,
                "resolution_target_tenant_insurance_id": target_id,
            }
        )
        reviewable += 1
        warning_count += len(warnings)

    unknown = sorted(set(resolution_map) - valid, key=int)
    if unknown:
        raise BuildiumRentersInsuranceMigrationError(
            "Renters Insurance review decisions may reference only otherwise-valid source rows: "
            + ", ".join(unknown)
        )

    summary = {
        "resource": "RENTERS_INSURANCE",
        "transport": "BUILDIUM_API_V1_RECORDS",
        "total": len(records),
        "reviewable": reviewable,
        "skipped_review": skipped,
        "invalid": invalid,
        "warning_count": warning_count,
        "tenant_insurance_created": False,
        "tenant_insurance_updated": False,
        "coverage_amount_inferred": False,
        "verification_status_inferred": False,
        "documents_copied": False,
        "financial_history_created": False,
        "raw_payload_stored": False,
        "provider_credentials_stored": False,
    }
    if not replayed:
        run.last_dry_run_fingerprint = fingerprint
        run.last_dry_run_summary = summary
        run.status = "DRY_RUN_READY"

    return RentersInsuranceDryRunResult(
        fingerprint,
        replayed,
        len(records),
        reviewable,
        skipped,
        invalid,
        warning_count,
        rows,
        summary,
    )


def commit_renters_insurance(
    db: Session,
    *,
    run: PlatformMigrationRun,
    records: list[dict[str, Any]],
    expected_fingerprint: str,
    platform_user_id: int,
    resolutions: list[dict[str, Any]] | None = None,
) -> RentersInsuranceCommitResult:
    fingerprint = _fingerprint(
        db,
        run=run,
        records=records,
        resolutions=resolutions,
    )
    if expected_fingerprint != fingerprint:
        raise BuildiumRentersInsuranceMigrationError(
            "Commit payload, dependency mappings, review decisions or target policy "
            "state no longer match the supplied dry-run fingerprint."
        )
    if run.last_dry_run_fingerprint != fingerprint:
        raise BuildiumRentersInsuranceMigrationError(
            "Commit requires the exact latest successful Buildium renters-insurance dry run."
        )

    preview = dry_run_renters_insurance(
        db,
        run=run,
        records=records,
        resolutions=resolutions,
    )
    if preview.invalid:
        raise BuildiumRentersInsuranceMigrationError(
            "Renters Insurance reconciliation commit is blocked while the dry run contains invalid records."
        )

    resolution_map = _normalize_resolutions(resolutions)
    valid_rows = [row for row in preview.rows if row["reviewable"]]
    missing: list[str] = []
    for row in valid_rows:
        source_id = str(row["source_id"])
        prior = _mapping(
            db,
            run=run,
            resource="RENTERS_INSURANCE",
            source_id=source_id,
            target_entity="TENANT_INSURANCE_RELATIONSHIP",
        )
        if prior is None and row["resolution_action"] != "MATCH_EXISTING":
            missing.append(source_id)
    if missing:
        raise BuildiumRentersInsuranceMigrationError(
            "Renters Insurance reconciliation requires explicit MATCH_EXISTING or SKIP "
            "review for every valid source row: "
            + ", ".join(missing)
        )

    rows: list[dict[str, Any]] = []
    matched = 0
    changed = False
    for row in valid_rows:
        source_id = str(row["source_id"])
        mapped, error, _ = _source_record(
            db,
            run=run,
            record=next(
                item for item in records if _positive_id(item.get("Id")) == source_id
            ),
        )
        if error is not None or mapped is None:
            raise BuildiumRentersInsuranceMigrationError(
                "Renters Insurance source or dependency state changed after dry run."
            )
        prior = _mapping(
            db,
            run=run,
            resource="RENTERS_INSURANCE",
            source_id=source_id,
            target_entity="TENANT_INSURANCE_RELATIONSHIP",
        )
        if prior is not None:
            target = _target_policy(db, run=run, target_id=prior.target_id)
            if target is None or _policy_match_reason(policy=target, mapped=mapped) is not None:
                raise BuildiumRentersInsuranceMigrationError(
                    "Previously reconciled TenantInsurance target changed after dry run."
                )
            rows.append(
                {
                    "source_id": source_id,
                    "target_tenant_insurance_id": target.id,
                    "replayed": True,
                }
            )
            continue

        target_id = resolution_map[source_id]["target_tenant_insurance_id"]
        target = _target_policy(db, run=run, target_id=target_id)
        if target is None:
            raise BuildiumRentersInsuranceMigrationError(
                f"Reviewed target TenantInsurance #{target_id} is no longer in scope."
            )
        reason = _policy_match_reason(policy=target, mapped=mapped)
        if reason is not None:
            raise BuildiumRentersInsuranceMigrationError(
                "Reviewed target TenantInsurance changed after dry run: " + reason
            )
        db.add(
            PlatformMigrationItem(
                run_id=run.id,
                organization_id=run.organization_id,
                provider="BUILDIUM",
                resource="RENTERS_INSURANCE",
                source_id=source_id,
                target_entity="TENANT_INSURANCE_RELATIONSHIP",
                target_id=target.id,
                source_fingerprint=fingerprint,
                created_by_platform_user_id=platform_user_id,
            )
        )
        rows.append(
            {
                "source_id": source_id,
                "target_tenant_insurance_id": target.id,
                "replayed": False,
            }
        )
        matched += 1
        changed = True

    review_recorded = False
    if changed:
        run.status = "RENTERS_INSURANCE_RECONCILED"
        db.flush()
    elif preview.skipped_review and not rows and run.status == "DRY_RUN_READY":
        run.status = "RENTERS_INSURANCE_REVIEWED"
        db.flush()
        review_recorded = True

    return RentersInsuranceCommitResult(
        fingerprint,
        not changed and not review_recorded,
        matched,
        preview.skipped_review,
        preview.warning_count,
        rows,
    )
