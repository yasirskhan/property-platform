"""Buildium property-reserve migration for Phase 4.14.

Buildium Rental Property records expose Reserve as cash retained by the
property manager. The target Property.required_reserve_amount is the platform's
configured minimum cash retained before owner distributions.

This adapter never silently overwrites that customer setting. A reviewer must
explicitly MATCH_EXISTING, APPLY_SOURCE, or SKIP after reviewing the exact
current target reserve. The expected target value is revalidated at commit.
No GL, bank balance, owner distribution, or accounting history is created.
"""
from __future__ import annotations

import hashlib
import json
from decimal import Decimal, InvalidOperation
from types import SimpleNamespace
from typing import Any

from sqlalchemy.orm import Session

from app.models.platform_migration import PlatformMigrationItem, PlatformMigrationRun
from app.models.property import Property


class BuildiumPropertyReserveMigrationError(ValueError):
    pass


_MAX_RESERVE = Decimal("999999999999.99")


def _id(value: Any) -> str | None:
    if isinstance(value, bool):
        return None
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return str(number) if number > 0 else None


def _money(value: Any) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None
    if not amount.is_finite() or amount < 0 or amount > _MAX_RESERVE:
        return None
    normalized = amount.quantize(Decimal("0.01"))
    if normalized != amount:
        return None
    return normalized


def _money_text(value: Decimal) -> str:
    return format(value, ".2f")


def _mapping(
    db: Session,
    run: PlatformMigrationRun,
    resource: str,
    source_id: str,
    entity: str,
):
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
    if row is not None and row.target_entity != entity:
        raise BuildiumPropertyReserveMigrationError(
            f"Buildium {resource} mapping for source ID {source_id} is inconsistent."
        )
    return row


def _target_property(db: Session, run: PlatformMigrationRun, source_id: str):
    mapping = _mapping(db, run, "PROPERTIES", source_id, "PROPERTY")
    if mapping is None:
        return None, None
    target = (
        db.query(Property)
        .filter(
            Property.id == mapping.target_id,
            Property.organization_id == run.organization_id,
            Property.is_active.is_(True),
            Property.deleted_at.is_(None),
        )
        .first()
    )
    if target is None:
        raise BuildiumPropertyReserveMigrationError(
            "Mapped Buildium Property is no longer active and in organization scope."
        )
    return target, mapping


def _resolutions(items):
    output: dict[str, dict[str, Any]] = {}
    for item in items or []:
        source_id = _id(item.get("source_id"))
        if source_id is None or source_id in output:
            raise BuildiumPropertyReserveMigrationError(
                "Property Reserve review requires unique positive source_id values."
            )
        action = str(item.get("action") or "").strip()
        if action not in {"MATCH_EXISTING", "APPLY_SOURCE", "SKIP"}:
            raise BuildiumPropertyReserveMigrationError(
                "Property Reserve review supports only MATCH_EXISTING, APPLY_SOURCE, or SKIP."
            )
        expected = item.get("expected_target_reserve")
        if action == "SKIP":
            if expected is not None:
                raise BuildiumPropertyReserveMigrationError(
                    "expected_target_reserve is not valid for SKIP."
                )
            expected_text = None
        else:
            expected_money = _money(expected)
            if expected_money is None:
                raise BuildiumPropertyReserveMigrationError(
                    "MATCH_EXISTING and APPLY_SOURCE require a valid expected target reserve."
                )
            expected_text = _money_text(expected_money)
        output[source_id] = {
            "source_id": int(source_id),
            "action": action,
            "expected_target_reserve": expected_text,
        }
    return output


def _source_record(record: dict[str, Any]):
    source_id = _id(record.get("Id"))
    if source_id is None:
        return None, "Buildium Property Id must be a positive integer."
    amount = _money(record.get("Reserve"))
    if amount is None:
        return None, (
            "Buildium Reserve must be an explicit nonnegative amount with no more "
            "than two decimal places."
        )
    return {"source_id": source_id, "source_reserve": amount}, None


def _fingerprint(
    db: Session,
    run: PlatformMigrationRun,
    records,
    resolutions,
) -> str:
    review = _resolutions(resolutions)
    dependencies = []
    for record in records:
        source_id = _id(record.get("Id"))
        target, mapping = _target_property(db, run, source_id) if source_id else (None, None)
        dependencies.append(
            {
                "source_id": source_id,
                "property_mapping_target_id": mapping.target_id if mapping else None,
                "property_mapping_source_fingerprint": mapping.source_fingerprint if mapping else None,
            }
        )
    payload = {
        "provider": "BUILDIUM",
        "resource": "PROPERTY_RESERVES",
        "organization_id": run.organization_id,
        "source_account_ref": run.source_account_ref,
        "records": records,
        "resolutions": [review[key] for key in sorted(review, key=int)],
        "dependencies": dependencies,
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


def dry_run_property_reserves(
    db: Session,
    *,
    run: PlatformMigrationRun,
    records,
    resolutions=None,
):
    if run.provider != "BUILDIUM" or not records:
        raise BuildiumPropertyReserveMigrationError(
            "A Buildium run with at least one Property Reserve record is required."
        )
    review = _resolutions(resolutions)
    fingerprint = _fingerprint(db, run, records, resolutions)
    replayed = run.last_dry_run_fingerprint == fingerprint
    rows = []
    seen: set[str] = set()
    reviewable = matched = apply_source = skipped = invalid = warnings_total = 0

    for record in records:
        source, reason = _source_record(record)
        source_id = _id(record.get("Id"))
        if source_id and source_id in seen:
            rows.append(
                {
                    "source_id": source_id,
                    "reviewable": False,
                    "reason": "Duplicate Buildium Property Id in this dry run.",
                    "mapped": None,
                    "warnings": [],
                    "resolution_action": None,
                }
            )
            invalid += 1
            continue
        if source_id:
            seen.add(source_id)
        if source is None:
            rows.append(
                {
                    "source_id": source_id,
                    "reviewable": False,
                    "reason": reason,
                    "mapped": None,
                    "warnings": [],
                    "resolution_action": None,
                }
            )
            invalid += 1
            continue

        target, dependency = _target_property(db, run, source["source_id"])
        if dependency is None or target is None:
            rows.append(
                {
                    "source_id": source["source_id"],
                    "reviewable": False,
                    "reason": (
                        "Property Reserve migration requires a durable same-run "
                        "Buildium Property mapping."
                    ),
                    "mapped": None,
                    "warnings": [],
                    "resolution_action": None,
                }
            )
            invalid += 1
            continue

        source_amount = source["source_reserve"]
        current = Decimal(target.required_reserve_amount or 0).quantize(Decimal("0.01"))
        prior = _mapping(db, run, "PROPERTY_RESERVES", source["source_id"], "PROPERTY")
        warnings = []
        resolution = review.get(source["source_id"])

        if prior is not None:
            if prior.target_id != target.id:
                rows.append(
                    {
                        "source_id": source["source_id"],
                        "reviewable": False,
                        "reason": "Previously mapped Property Reserve target no longer matches the Property mapping.",
                        "mapped": None,
                        "warnings": [],
                        "resolution_action": None,
                    }
                )
                invalid += 1
                continue
            if current != source_amount:
                rows.append(
                    {
                        "source_id": source["source_id"],
                        "reviewable": False,
                        "reason": (
                            "Previously migrated Property Reserve no longer equals the "
                            "Buildium source; manual review is required."
                        ),
                        "mapped": {
                            "target_property_id": target.id,
                            "source_reserve": _money_text(source_amount),
                            "target_required_reserve": _money_text(current),
                        },
                        "warnings": [],
                        "resolution_action": None,
                    }
                )
                invalid += 1
                continue
            action = "ALREADY_MAPPED"
            matched += 1
        elif resolution is None:
            action = None
            warnings.append(
                "Explicit MATCH_EXISTING, APPLY_SOURCE, or SKIP review is required."
            )
        elif resolution["action"] == "SKIP":
            action = "SKIP"
            skipped += 1
        else:
            expected = Decimal(resolution["expected_target_reserve"])
            if current != expected:
                raise BuildiumPropertyReserveMigrationError(
                    "Target Property reserve changed after review; run the dry run again."
                )
            action = resolution["action"]
            if action == "MATCH_EXISTING":
                if current != source_amount:
                    raise BuildiumPropertyReserveMigrationError(
                        "MATCH_EXISTING requires the target Property reserve to equal the Buildium source."
                    )
                matched += 1
            elif action == "APPLY_SOURCE":
                apply_source += 1

        mapped = {
            "target_property_id": target.id,
            "source_reserve": _money_text(source_amount),
            "target_required_reserve": _money_text(current),
            "property_mapping_source_fingerprint": dependency.source_fingerprint,
        }
        reviewable += 1
        warnings_total += len(warnings)
        rows.append(
            {
                "source_id": source["source_id"],
                "reviewable": True,
                "reason": None,
                "mapped": mapped,
                "warnings": warnings,
                "resolution_action": action,
            }
        )

    summary = {
        "total": len(records),
        "reviewable": reviewable,
        "matched_existing": matched,
        "apply_source": apply_source,
        "skipped_review": skipped,
        "invalid": invalid,
        "warning_count": warnings_total,
        "target_reserve_updates_require_explicit_review": True,
        "gl_history_created": False,
    }
    if not replayed:
        run.last_dry_run_fingerprint = fingerprint
        run.last_dry_run_summary = summary
        run.status = "PROPERTY_RESERVES_DRY_RUN_READY"
        db.flush()
    return SimpleNamespace(
        fingerprint=fingerprint,
        replayed=replayed,
        total=len(records),
        reviewable=reviewable,
        matched_existing=matched,
        apply_source=apply_source,
        skipped_review=skipped,
        invalid=invalid,
        warning_count=warnings_total,
        rows=rows,
        summary=summary,
    )


def commit_property_reserves(
    db: Session,
    *,
    run: PlatformMigrationRun,
    records,
    expected_fingerprint: str,
    platform_user_id: int,
    resolutions=None,
):
    current_fingerprint = _fingerprint(db, run, records, resolutions)
    if current_fingerprint != expected_fingerprint:
        raise BuildiumPropertyReserveMigrationError(
            "Buildium Property Reserve dry run is stale; run review again before commit."
        )
    if run.last_dry_run_fingerprint != expected_fingerprint:
        raise BuildiumPropertyReserveMigrationError(
            "Commit requires the exact latest Property Reserve dry run."
        )

    preview = dry_run_property_reserves(
        db,
        run=run,
        records=records,
        resolutions=resolutions,
    )
    if preview.invalid:
        raise BuildiumPropertyReserveMigrationError(
            "Buildium Property Reserve commit is blocked while invalid records remain."
        )

    review = _resolutions(resolutions)
    missing = [
        row["source_id"]
        for row in preview.rows
        if row["resolution_action"] is None
    ]
    if missing:
        raise BuildiumPropertyReserveMigrationError(
            "Property Reserve migration requires explicit review for source IDs: "
            + ", ".join(missing)
        )

    rows = []
    updated = matched = skipped = 0
    changed = False
    review_recorded = False

    for row in preview.rows:
        source_id = row["source_id"]
        target_id = int(row["mapped"]["target_property_id"])
        source_amount = Decimal(row["mapped"]["source_reserve"])
        prior = _mapping(db, run, "PROPERTY_RESERVES", source_id, "PROPERTY")
        if prior is not None:
            target = (
                db.query(Property)
                .filter(
                    Property.id == prior.target_id,
                    Property.organization_id == run.organization_id,
                    Property.is_active.is_(True),
                    Property.deleted_at.is_(None),
                )
                .first()
            )
            if target is None or Decimal(target.required_reserve_amount or 0).quantize(Decimal("0.01")) != source_amount:
                raise BuildiumPropertyReserveMigrationError(
                    "Previously mapped Property Reserve changed after migration."
                )
            rows.append(
                {
                    "source_id": source_id,
                    "target_property_id": prior.target_id,
                    "action": "ALREADY_MAPPED",
                    "replayed": True,
                }
            )
            continue

        resolution = review[source_id]
        if resolution["action"] == "SKIP":
            skipped += 1
            continue

        target = (
            db.query(Property)
            .filter(
                Property.id == target_id,
                Property.organization_id == run.organization_id,
                Property.is_active.is_(True),
                Property.deleted_at.is_(None),
            )
            .first()
        )
        if target is None:
            raise BuildiumPropertyReserveMigrationError(
                "Target Property is no longer active and in organization scope."
            )
        current = Decimal(target.required_reserve_amount or 0).quantize(Decimal("0.01"))
        expected = Decimal(resolution["expected_target_reserve"])
        if current != expected:
            raise BuildiumPropertyReserveMigrationError(
                "Target Property reserve changed after review; run the dry run again."
            )

        action = resolution["action"]
        if action == "MATCH_EXISTING":
            if current != source_amount:
                raise BuildiumPropertyReserveMigrationError(
                    "Target Property reserve no longer matches Buildium."
                )
            matched += 1
        elif action == "APPLY_SOURCE":
            target.required_reserve_amount = source_amount
            updated += 1
        else:
            raise BuildiumPropertyReserveMigrationError(
                "Unsupported Property Reserve review action."
            )

        db.add(
            PlatformMigrationItem(
                run_id=run.id,
                organization_id=run.organization_id,
                provider="BUILDIUM",
                resource="PROPERTY_RESERVES",
                source_id=source_id,
                target_entity="PROPERTY",
                target_id=target.id,
                source_fingerprint=preview.fingerprint,
                created_by_platform_user_id=platform_user_id,
            )
        )
        rows.append(
            {
                "source_id": source_id,
                "target_property_id": target.id,
                "action": action,
                "replayed": False,
            }
        )
        changed = True

    if changed:
        run.status = "PROPERTY_RESERVES_RECONCILED"
        db.flush()
    elif skipped and not rows:
        run.status = "PROPERTY_RESERVES_REVIEWED"
        db.flush()
        review_recorded = True

    return SimpleNamespace(
        fingerprint=preview.fingerprint,
        replayed=not changed and not review_recorded,
        updated=updated,
        matched_existing=matched,
        skipped_review=skipped,
        warning_count=preview.warning_count,
        rows=rows,
    )
