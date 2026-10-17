"""Buildium lease-ledger charge relationship reconciliation for Phase 4.14.

This bounded adapter reconciles a documented Buildium lease-ledger charge to
one already-existing target standalone Charge. It does not create or update a
Charge, RentInvoice, receipt, payment, GL entry, or historical balance.

The transport layer is expected to attach the parent LeaseId from the Buildium
lease-ledger endpoint path to each retrieved charge record before calling this
service. Provider credentials and raw response envelopes are not persisted.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
import hashlib
import json
from typing import Any

from sqlalchemy.orm import Session

from app.models.charge import Charge
from app.models.gl_account import GLAccount
from app.models.lease import Lease
from app.models.platform_migration import PlatformMigrationItem, PlatformMigrationRun
from app.models.property import Property, Unit
from app.models.user import User, UserRole


class BuildiumLeaseChargeMigrationError(ValueError):
    pass


@dataclass(frozen=True)
class LeaseChargeDryRunResult:
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
class LeaseChargeCommitResult:
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


def _money(value: Any, *, field: str) -> tuple[Decimal | None, str | None]:
    if value is None or isinstance(value, bool):
        return None, f"{field} must be an explicit decimal amount."
    try:
        raw = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None, f"{field} must be an explicit decimal amount."
    if not raw.is_finite():
        return None, f"{field} must be finite."
    value = raw.quantize(Decimal("0.01"))
    if raw != value:
        return None, f"{field} must have no more than two decimal places."
    if value <= 0:
        return None, f"{field} must be greater than zero."
    return value, None


def _date(value: Any) -> tuple[date | None, str | None]:
    text = _clean(value)
    if text is None:
        return None, "Buildium charge Date is required."
    try:
        return date.fromisoformat(text), None
    except ValueError:
        return None, "Buildium charge Date must be an ISO date (YYYY-MM-DD)."


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
        raise BuildiumLeaseChargeMigrationError(
            f"Buildium {resource} mapping for source ID {source_id} is inconsistent."
        )
    return row


def _normalize_resolutions(items) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for item in items or []:
        source_id = _positive_id(item.get("source_id"))
        if source_id is None or source_id in result:
            raise BuildiumLeaseChargeMigrationError(
                "Lease Charge review requires unique positive source_id values."
            )
        action = _clean(item.get("action"))
        if action not in {"MATCH_EXISTING", "SKIP"}:
            raise BuildiumLeaseChargeMigrationError(
                "Lease Charge review supports only MATCH_EXISTING or SKIP."
            )
        target = item.get("target_charge_id")
        if action == "MATCH_EXISTING":
            if isinstance(target, bool):
                raise BuildiumLeaseChargeMigrationError(
                    "MATCH_EXISTING requires a positive target Charge ID."
                )
            try:
                target = int(target)
            except (TypeError, ValueError):
                raise BuildiumLeaseChargeMigrationError(
                    "MATCH_EXISTING requires a positive target Charge ID."
                )
            if target < 1:
                raise BuildiumLeaseChargeMigrationError(
                    "MATCH_EXISTING requires a positive target Charge ID."
                )
        elif target is not None:
            raise BuildiumLeaseChargeMigrationError(
                "target_charge_id is only valid for MATCH_EXISTING."
            )
        result[source_id] = {
            "source_id": int(source_id),
            "action": action,
            "target_charge_id": target,
        }
    return result


def _source_ids(record: dict[str, Any]) -> tuple[str | None, str | None, str | None]:
    charge_id = _positive_id(record.get("Id"))
    lease_id = _positive_id(record.get("LeaseId"))
    lines = record.get("Lines")
    gl_id = None
    if isinstance(lines, list) and len(lines) == 1 and isinstance(lines[0], dict):
        gl_id = _positive_id(lines[0].get("GLAccountId"))
    return charge_id, lease_id, gl_id


def _dependency_snapshot(
    db: Session,
    *,
    run: PlatformMigrationRun,
    records: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for record in records:
        charge_id, lease_id, gl_id = _source_ids(record)
        line = record.get("Lines")[0] if isinstance(record.get("Lines"), list) and len(record.get("Lines")) == 1 and isinstance(record.get("Lines")[0], dict) else {}
        unit_id = _positive_id(line.get("UnitId"))
        item: dict[str, Any] = {
            "charge_source_id": charge_id,
            "lease_source_id": lease_id,
            "gl_account_source_id": gl_id,
            "unit_source_id": unit_id,
        }
        for key, resource, source_id, entity in (
            ("lease", "LEASES", lease_id, "LEASE_RELATIONSHIP"),
            ("gl_account", "GL_ACCOUNTS", gl_id, "GL_ACCOUNT"),
            ("unit", "UNITS", unit_id, "UNIT"),
        ):
            mapped = (
                _mapping(
                    db,
                    run=run,
                    resource=resource,
                    source_id=source_id,
                    target_entity=entity,
                )
                if source_id is not None
                else None
            )
            item[key] = (
                {"target_id": mapped.target_id, "source_fingerprint": mapped.source_fingerprint}
                if mapped is not None
                else None
            )
        result.append(item)
    return result


def _fingerprint(
    db: Session,
    *,
    run: PlatformMigrationRun,
    records: list[dict[str, Any]],
    resolutions,
) -> str:
    review = _normalize_resolutions(resolutions)
    payload = {
        "provider": "BUILDIUM",
        "resource": "LEASE_CHARGES",
        "organization_id": run.organization_id,
        "source_account_ref": run.source_account_ref,
        "records": records,
        "resolutions": [review[key] for key in sorted(review, key=int)],
        "dependency_mappings": _dependency_snapshot(db, run=run, records=records),
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


def _target_lease(
    db: Session, *, run: PlatformMigrationRun, mapping: PlatformMigrationItem
) -> tuple[Lease | None, Unit | None, Property | None, User | None]:
    row = (
        db.query(Lease, Unit, Property, User)
        .join(Unit, Unit.id == Lease.unit_id)
        .join(Property, Property.id == Unit.property_id)
        .join(User, User.id == Lease.tenant_id)
        .filter(
            Lease.id == mapping.target_id,
            Property.organization_id == run.organization_id,
            Property.is_active.is_(True),
            Property.deleted_at.is_(None),
            Unit.is_active.is_(True),
            User.organization_id == run.organization_id,
            User.role == UserRole.TENANT,
            User.is_active.is_(True),
            User.deleted_at.is_(None),
        )
        .first()
    )
    if row is None:
        return None, None, None, None
    return row


def _target_charge(db: Session, *, run: PlatformMigrationRun, charge_id: int) -> Charge | None:
    return (
        db.query(Charge)
        .filter(
            Charge.id == charge_id,
            Charge.organization_id == run.organization_id,
            Charge.is_active.is_(True),
            Charge.deleted_at.is_(None),
        )
        .first()
    )


def _validate_source(
    db: Session,
    *,
    run: PlatformMigrationRun,
    record: dict[str, Any],
) -> tuple[dict[str, Any] | None, str | None, list[str]]:
    source_id = _positive_id(record.get("Id"))
    if source_id is None:
        return None, "Buildium Lease Charge Id must be a positive integer.", []

    lease_source_id = _positive_id(record.get("LeaseId"))
    if lease_source_id is None:
        return None, (
            "LeaseId must be supplied from the parent Buildium lease-ledger endpoint context."
        ), []

    lease_mapping = _mapping(
        db,
        run=run,
        resource="LEASES",
        source_id=lease_source_id,
        target_entity="LEASE_RELATIONSHIP",
    )
    if lease_mapping is None:
        return None, (
            f"Lease Charge reconciliation requires durable Buildium Lease mapping {lease_source_id}."
        ), []

    lease, target_unit, target_property, target_tenant = _target_lease(
        db, run=run, mapping=lease_mapping
    )
    if lease is None:
        return None, "Mapped Buildium Lease is no longer active and in organization scope.", []

    charge_date, error = _date(record.get("Date"))
    if error:
        return None, error, []

    total, error = _money(record.get("TotalAmount"), field="TotalAmount")
    if error:
        return None, error, []

    memo = _clean(record.get("Memo"))
    if memo is None:
        return None, (
            "Buildium charge Memo is required for exact target Charge relationship matching."
        ), []
    if len(memo) > 500:
        return None, "Buildium charge Memo exceeds the target Charge description limit.", []

    bill_id = record.get("BillId")
    if bill_id not in (None, "", 0, "0"):
        return None, (
            "Buildium lease charges linked to a Bill are outside this bounded target Charge contract."
        ), []

    lines = record.get("Lines")
    if not isinstance(lines, list) or len(lines) != 1 or not isinstance(lines[0], dict):
        return None, (
            "This bounded migration supports exactly one Buildium charge line because target Charge stores one GL account."
        ), []
    line = lines[0]
    line_amount, error = _money(line.get("Amount"), field="Lines[0].Amount")
    if error:
        return None, error, []
    if line_amount != total:
        return None, "Single Buildium charge line amount must exactly equal TotalAmount.", []

    gl_source_id = _positive_id(line.get("GLAccountId"))
    if gl_source_id is None:
        return None, "Buildium charge line GLAccountId must be a positive integer.", []
    gl_mapping = _mapping(
        db,
        run=run,
        resource="GL_ACCOUNTS",
        source_id=gl_source_id,
        target_entity="GL_ACCOUNT",
    )
    if gl_mapping is None:
        return None, (
            f"Lease Charge reconciliation requires durable Buildium GL Account mapping {gl_source_id}."
        ), []
    gl = (
        db.query(GLAccount)
        .filter(
            GLAccount.id == gl_mapping.target_id,
            GLAccount.organization_id == run.organization_id,
            GLAccount.deleted_at.is_(None),
        )
        .first()
    )
    if gl is None:
        return None, "Mapped Buildium GL Account is missing, deleted, or foreign.", []

    unit_source_id = _positive_id(line.get("UnitId"))
    if unit_source_id is None:
        return None, (
            "Buildium charge line UnitId is required for exact lease/unit relationship reconciliation."
        ), []
    unit_mapping = _mapping(
        db,
        run=run,
        resource="UNITS",
        source_id=unit_source_id,
        target_entity="UNIT",
    )
    if unit_mapping is None:
        return None, (
            f"Lease Charge reconciliation requires durable Buildium Unit mapping {unit_source_id}."
        ), []
    if unit_mapping.target_id != target_unit.id:
        return None, "Buildium charge Unit mapping does not match the mapped Lease unit.", []

    mapped = {
        "lease_source_id": lease_source_id,
        "target_lease_id": lease.id,
        "target_tenant_user_id": target_tenant.id,
        "target_unit_id": target_unit.id,
        "target_property_id": target_property.id,
        "target_gl_account_id": gl.id,
        "charge_date": charge_date.isoformat(),
        "amount": f"{total:.2f}",
        "description": memo,
    }
    warnings = [
        "This batch reconciles one Buildium lease-ledger charge to an already-existing target Charge; it never creates or updates a Charge.",
        "Buildium payment, credit, refund, reversal, outstanding-balance and receipt history are not inferred from this charge relationship.",
        "Target Charge amount_paid and is_paid are current target metadata and are not validated as Buildium payment history by this batch.",
        "No GLTransaction or GLEntry relationship is inferred from the Buildium charge line.",
    ]
    return mapped, None, warnings


def _matches(charge: Charge, mapped: dict[str, Any]) -> bool:
    return (
        charge.tenant_user_id == mapped["target_tenant_user_id"]
        and charge.unit_id == mapped["target_unit_id"]
        and charge.property_id == mapped["target_property_id"]
        and charge.gl_account_id == mapped["target_gl_account_id"]
        and charge.charge_date.isoformat() == mapped["charge_date"]
        and Decimal(charge.amount).quantize(Decimal("0.01")) == Decimal(mapped["amount"])
        and _clean(charge.description) == mapped["description"]
    )


def dry_run_lease_charges(
    db: Session,
    *,
    run: PlatformMigrationRun,
    records: list[dict[str, Any]],
    resolutions=None,
) -> LeaseChargeDryRunResult:
    if run.provider != "BUILDIUM" or not records:
        raise BuildiumLeaseChargeMigrationError(
            "A Buildium run with at least one Lease Charge record is required."
        )

    review = _normalize_resolutions(resolutions)
    fingerprint = _fingerprint(db, run=run, records=records, resolutions=resolutions)
    replayed = run.last_dry_run_fingerprint == fingerprint
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    reviewable = skipped = invalid = warning_count = 0

    for record in records:
        source_id = _positive_id(record.get("Id"))
        if source_id is not None and source_id in seen:
            rows.append({
                "source_id": source_id,
                "reviewable": False,
                "reason": "Duplicate Buildium Lease Charge Id in this dry run.",
                "mapped": None,
                "warnings": [],
            })
            invalid += 1
            continue
        if source_id is not None:
            seen.add(source_id)

        mapped, reason, warnings = _validate_source(db, run=run, record=record)
        if mapped is None:
            rows.append({
                "source_id": source_id,
                "reviewable": False,
                "reason": reason,
                "mapped": None,
                "warnings": warnings,
            })
            invalid += 1
            continue

        durable = _mapping(
            db,
            run=run,
            resource="LEASE_CHARGES",
            source_id=source_id,
            target_entity="CHARGE_RELATIONSHIP",
        )
        resolution = review.get(source_id)
        action = resolution["action"] if resolution else None
        target_charge_id = resolution["target_charge_id"] if resolution else None

        if durable is not None:
            if resolution is not None and (
                action != "MATCH_EXISTING" or target_charge_id != durable.target_id
            ):
                raise BuildiumLeaseChargeMigrationError(
                    f"Buildium Lease Charge {source_id} already has a durable mapping and cannot be re-resolved."
                )
            target = _target_charge(db, run=run, charge_id=durable.target_id)
            if target is None or not _matches(target, mapped):
                raise BuildiumLeaseChargeMigrationError(
                    "Previously mapped target Charge no longer matches the Buildium Lease Charge contract."
                )
            action = "ALREADY_MAPPED"
            target_charge_id = durable.target_id
            warnings.append(
                f"Buildium Lease Charge {source_id} is already durably mapped to local Charge #{durable.target_id}; commit will replay."
            )
        elif action == "MATCH_EXISTING":
            target = _target_charge(db, run=run, charge_id=target_charge_id)
            if target is None:
                raise BuildiumLeaseChargeMigrationError(
                    "Reviewed target Charge is not active and in the target organization."
                )
            if not _matches(target, mapped):
                raise BuildiumLeaseChargeMigrationError(
                    "Reviewed target Charge does not exactly match the mapped Buildium lease charge contract."
                )
            warnings.append(
                f"Reviewed MATCH_EXISTING target: local Charge #{target.id}; commit creates durable mapping metadata only."
            )
        elif action == "SKIP":
            rows.append({
                "source_id": source_id,
                "reviewable": False,
                "reason": "Explicitly skipped after Buildium Lease Charge review.",
                "mapped": mapped,
                "warnings": warnings,
                "resolution_action": "SKIP",
                "resolution_target_charge_id": None,
            })
            skipped += 1
            warning_count += len(warnings)
            continue
        else:
            candidates = (
                db.query(Charge)
                .filter(
                    Charge.organization_id == run.organization_id,
                    Charge.tenant_user_id == mapped["target_tenant_user_id"],
                    Charge.unit_id == mapped["target_unit_id"],
                    Charge.property_id == mapped["target_property_id"],
                    Charge.gl_account_id == mapped["target_gl_account_id"],
                    Charge.charge_date == date.fromisoformat(mapped["charge_date"]),
                    Charge.amount == Decimal(mapped["amount"]),
                    Charge.description == mapped["description"],
                    Charge.is_active.is_(True),
                    Charge.deleted_at.is_(None),
                )
                .order_by(Charge.id.asc())
                .limit(3)
                .all()
            )
            if len(candidates) == 1:
                warnings.append(
                    f"Possible exact existing target Charge match: local Charge #{candidates[0].id}; explicit MATCH_EXISTING review is required."
                )
            elif len(candidates) > 1:
                warnings.append(
                    "Multiple exact target Charges match this source relationship; no candidate is auto-selected."
                )
            else:
                warnings.append(
                    "No exact target Charge exists; this bounded batch does not create one."
                )

        rows.append({
            "source_id": source_id,
            "reviewable": True,
            "reason": None,
            "mapped": mapped,
            "warnings": warnings,
            "resolution_action": action,
            "resolution_target_charge_id": target_charge_id,
        })
        reviewable += 1
        warning_count += len(warnings)

    extra = sorted(set(review) - seen, key=int)
    if extra:
        raise BuildiumLeaseChargeMigrationError(
            "Lease Charge review contains source IDs not present in this dry run: "
            + ", ".join(extra)
        )

    summary = {
        "total": len(records),
        "reviewable": reviewable,
        "skipped_review": skipped,
        "invalid": invalid,
        "warning_count": warning_count,
        "target_charge_created": False,
        "payment_history_reconciled": False,
        "gl_history_created": False,
    }
    if not replayed:
        run.last_dry_run_fingerprint = fingerprint
        run.last_dry_run_summary = {"resource": "LEASE_CHARGES", **summary}
        run.status = "LEASE_CHARGES_DRY_RUN_READY"
        db.flush()

    return LeaseChargeDryRunResult(
        fingerprint=fingerprint,
        replayed=replayed,
        total=len(records),
        reviewable=reviewable,
        skipped_review=skipped,
        invalid=invalid,
        warning_count=warning_count,
        rows=rows,
        summary=summary,
    )


def commit_lease_charges(
    db: Session,
    *,
    run: PlatformMigrationRun,
    records: list[dict[str, Any]],
    expected_fingerprint: str,
    platform_user_id: int,
    resolutions=None,
) -> LeaseChargeCommitResult:
    current = _fingerprint(db, run=run, records=records, resolutions=resolutions)
    if current != expected_fingerprint:
        raise BuildiumLeaseChargeMigrationError(
            "Buildium Lease Charge dry run is stale; run review again before commit."
        )
    if run.last_dry_run_fingerprint != expected_fingerprint:
        raise BuildiumLeaseChargeMigrationError(
            "Commit requires the exact latest Buildium Lease Charge dry run."
        )

    preview = dry_run_lease_charges(
        db, run=run, records=records, resolutions=resolutions
    )
    if preview.invalid:
        raise BuildiumLeaseChargeMigrationError(
            "Buildium Lease Charge commit is blocked while invalid records remain."
        )
    missing = [
        row["source_id"]
        for row in preview.rows
        if row.get("resolution_action") is None
    ]
    if missing:
        raise BuildiumLeaseChargeMigrationError(
            "Lease Charge migration requires explicit review for source IDs: "
            + ", ".join(missing)
        )

    review = _normalize_resolutions(resolutions)
    rows: list[dict[str, Any]] = []
    matched = skipped = 0
    changed = False
    reviewed_only = False

    for row in preview.rows:
        source_id = row["source_id"]
        action = row.get("resolution_action")
        if action == "SKIP":
            skipped += 1
            reviewed_only = True
            continue
        if action == "ALREADY_MAPPED":
            rows.append({
                "source_id": source_id,
                "target_charge_id": row["resolution_target_charge_id"],
                "replayed": True,
            })
            continue
        resolution = review[source_id]
        target_id = int(resolution["target_charge_id"])
        target = _target_charge(db, run=run, charge_id=target_id)
        if target is None or not _matches(target, row["mapped"]):
            raise BuildiumLeaseChargeMigrationError(
                "Reviewed target Charge changed after dry run."
            )
        db.add(
            PlatformMigrationItem(
                run_id=run.id,
                organization_id=run.organization_id,
                provider="BUILDIUM",
                resource="LEASE_CHARGES",
                source_id=source_id,
                target_entity="CHARGE_RELATIONSHIP",
                target_id=target.id,
                source_fingerprint=preview.fingerprint,
                created_by_platform_user_id=platform_user_id,
            )
        )
        rows.append({
            "source_id": source_id,
            "target_charge_id": target.id,
            "replayed": False,
        })
        matched += 1
        changed = True

    if changed:
        run.status = "LEASE_CHARGES_RECONCILED"
        db.flush()
    elif reviewed_only and not rows:
        run.status = "LEASE_CHARGES_REVIEWED"
        db.flush()

    return LeaseChargeCommitResult(
        fingerprint=preview.fingerprint,
        replayed=not changed and not reviewed_only,
        matched_existing=matched,
        skipped_review=skipped,
        warning_count=preview.warning_count,
        rows=rows,
    )
