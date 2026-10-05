"""Buildium Budget existing-target reconciliation for Phase 4.14.

This bounded adapter reconciles documented Buildium rental-property budget
monthly amounts to already-existing PropertyBudgetLine records. It never
creates or updates customer budgets, GL entries, or accounting history.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
import hashlib
import json
from typing import Any

from sqlalchemy.orm import Session

from app.models.gl_account import GLAccount
from app.models.platform_migration import PlatformMigrationItem, PlatformMigrationRun
from app.models.property import Property
from app.models.property_budget import PropertyBudgetLine


class BuildiumBudgetMigrationError(ValueError):
    pass


@dataclass(frozen=True)
class BudgetDryRunResult:
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
class BudgetCommitResult:
    fingerprint: str
    replayed: bool
    matched_existing: int
    skipped_review: int
    warning_count: int
    rows: list[dict[str, Any]]


_MONTHS = (
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
)


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
    rounded = raw.quantize(Decimal("0.01"))
    if raw != rounded:
        return None, f"{field} must have no more than two decimal places."
    if rounded < 0:
        return None, f"{field} cannot be negative."
    return rounded, None


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
        raise BuildiumBudgetMigrationError(
            f"Buildium {resource} mapping for source ID {source_id} is inconsistent."
        )
    return row


def _budget_period(record: dict[str, Any]) -> tuple[int | None, str | None]:
    start_text = _clean(record.get("StartDate"))
    end_text = _clean(record.get("EndDate"))
    if start_text is None or end_text is None:
        return None, "Buildium Budget StartDate and EndDate are required."
    try:
        start = date.fromisoformat(start_text)
        end = date.fromisoformat(end_text)
    except ValueError:
        return None, "Buildium Budget dates must be ISO dates (YYYY-MM-DD)."
    if start.year != end.year or start.month != 1 or start.day != 1 or end.month != 12 or end.day != 31:
        return None, (
            "This bounded migration supports calendar-year Buildium Budgets only "
            "(January 1 through December 31 of the same year)."
        )
    if not 2000 <= start.year <= 2100:
        return None, "Buildium Budget calendar year must be between 2000 and 2100."
    return start.year, None


def _source_line_id(budget_id: str, gl_account_id: str, year: int, month: int) -> str:
    return f"{budget_id}:{gl_account_id}:{year}:{month}"


def _normalize_resolutions(items) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for item in items or []:
        source_id = _clean(item.get("source_id"))
        if source_id is None or len(source_id) > 255 or source_id in result:
            raise BuildiumBudgetMigrationError(
                "Budget review requires unique nonblank source_id values."
            )
        action = _clean(item.get("action"))
        if action not in {"MATCH_EXISTING", "SKIP"}:
            raise BuildiumBudgetMigrationError(
                "Budget review supports only MATCH_EXISTING or SKIP."
            )
        target = item.get("target_property_budget_line_id")
        if action == "MATCH_EXISTING":
            if isinstance(target, bool):
                raise BuildiumBudgetMigrationError(
                    "MATCH_EXISTING requires a positive Property Budget Line ID."
                )
            try:
                target = int(target)
            except (TypeError, ValueError):
                raise BuildiumBudgetMigrationError(
                    "MATCH_EXISTING requires a positive Property Budget Line ID."
                )
            if target < 1:
                raise BuildiumBudgetMigrationError(
                    "MATCH_EXISTING requires a positive Property Budget Line ID."
                )
        elif target is not None:
            raise BuildiumBudgetMigrationError(
                "target_property_budget_line_id is only valid for MATCH_EXISTING."
            )
        result[source_id] = {
            "source_id": source_id,
            "action": action,
            "target_property_budget_line_id": target,
        }
    return result


def _dependency_snapshot(
    db: Session,
    *,
    run: PlatformMigrationRun,
    records: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for record in records:
        budget_id = _positive_id(record.get("Id"))
        prop = record.get("Property") if isinstance(record.get("Property"), dict) else {}
        property_source_id = _positive_id(prop.get("Id"))
        prop_map = (
            _mapping(
                db, run=run, resource="PROPERTIES",
                source_id=property_source_id, target_entity="PROPERTY",
            )
            if property_source_id else None
        )
        details: list[dict[str, Any]] = []
        for detail in record.get("Details") if isinstance(record.get("Details"), list) else []:
            if not isinstance(detail, dict):
                continue
            gl_source_id = _positive_id(detail.get("GLAccountId"))
            gl_map = (
                _mapping(
                    db, run=run, resource="GL_ACCOUNTS",
                    source_id=gl_source_id, target_entity="GL_ACCOUNT",
                )
                if gl_source_id else None
            )
            details.append({
                "gl_account_source_id": gl_source_id,
                "mapping": (
                    {"target_id": gl_map.target_id, "source_fingerprint": gl_map.source_fingerprint}
                    if gl_map else None
                ),
            })
        result.append({
            "budget_source_id": budget_id,
            "property_source_id": property_source_id,
            "property_mapping": (
                {"target_id": prop_map.target_id, "source_fingerprint": prop_map.source_fingerprint}
                if prop_map else None
            ),
            "gl_account_mappings": details,
        })
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
        "resource": "BUDGET_LINES",
        "organization_id": run.organization_id,
        "source_account_ref": run.source_account_ref,
        "records": records,
        "resolutions": [review[key] for key in sorted(review)],
        "dependency_mappings": _dependency_snapshot(db, run=run, records=records),
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


def _target_line(
    db: Session, *, run: PlatformMigrationRun, target_id: int
) -> PropertyBudgetLine | None:
    return (
        db.query(PropertyBudgetLine)
        .join(Property, Property.id == PropertyBudgetLine.property_id)
        .join(GLAccount, GLAccount.id == PropertyBudgetLine.gl_account_id)
        .filter(
            PropertyBudgetLine.id == target_id,
            PropertyBudgetLine.organization_id == run.organization_id,
            Property.organization_id == run.organization_id,
            Property.is_active.is_(True),
            Property.deleted_at.is_(None),
            GLAccount.organization_id == run.organization_id,
            GLAccount.deleted_at.is_(None),
            GLAccount.account_type.in_(("INCOME", "EXPENSE")),
        )
        .first()
    )


def _matches(line: PropertyBudgetLine, mapped: dict[str, Any]) -> bool:
    return (
        line.property_id == mapped["target_property_id"]
        and line.gl_account_id == mapped["target_gl_account_id"]
        and line.calendar_year == mapped["calendar_year"]
        and line.month == mapped["month"]
        and Decimal(line.amount).quantize(Decimal("0.01")) == Decimal(mapped["amount"])
    )


def _normalized_lines(
    db: Session,
    *,
    run: PlatformMigrationRun,
    records: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    good: list[dict[str, Any]] = []
    bad: list[dict[str, Any]] = []
    seen_budget_ids: set[str] = set()
    seen_line_ids: set[str] = set()

    for record in records:
        budget_id = _positive_id(record.get("Id"))
        if budget_id is None:
            bad.append({"source_id": None, "reason": "Buildium Budget Id must be a positive integer."})
            continue
        if budget_id in seen_budget_ids:
            bad.append({"source_id": budget_id, "reason": "Duplicate Buildium Budget Id in this dry run."})
            continue
        seen_budget_ids.add(budget_id)

        year, period_error = _budget_period(record)
        if period_error:
            bad.append({"source_id": budget_id, "reason": period_error})
            continue

        prop = record.get("Property")
        if not isinstance(prop, dict):
            bad.append({"source_id": budget_id, "reason": "Buildium Budget Property object is required."})
            continue
        if (_clean(prop.get("Type")) or "").lower() != "rental":
            bad.append({
                "source_id": budget_id,
                "reason": "This bounded budget migration supports Rental property budgets only.",
            })
            continue
        property_source_id = _positive_id(prop.get("Id"))
        if property_source_id is None:
            bad.append({"source_id": budget_id, "reason": "Buildium Budget Property.Id must be positive."})
            continue
        property_mapping = _mapping(
            db, run=run, resource="PROPERTIES",
            source_id=property_source_id, target_entity="PROPERTY",
        )
        if property_mapping is None:
            bad.append({
                "source_id": budget_id,
                "reason": f"Budget reconciliation requires durable Buildium Property mapping {property_source_id}.",
            })
            continue
        target_property = (
            db.query(Property)
            .filter(
                Property.id == property_mapping.target_id,
                Property.organization_id == run.organization_id,
                Property.is_active.is_(True),
                Property.deleted_at.is_(None),
            )
            .first()
        )
        if target_property is None:
            bad.append({"source_id": budget_id, "reason": "Mapped Buildium Property is not active in target scope."})
            continue

        details = record.get("Details")
        if not isinstance(details, list) or not details:
            bad.append({"source_id": budget_id, "reason": "Buildium Budget Details must be a nonempty array."})
            continue

        seen_gl: set[str] = set()
        record_invalid = False
        record_lines: list[dict[str, Any]] = []
        for detail in details:
            if not isinstance(detail, dict):
                bad.append({"source_id": budget_id, "reason": "Buildium Budget Details entries must be objects."})
                record_invalid = True
                break
            gl_source_id = _positive_id(detail.get("GLAccountId"))
            if gl_source_id is None or gl_source_id in seen_gl:
                bad.append({
                    "source_id": budget_id,
                    "reason": "Each Buildium Budget detail requires a unique positive GLAccountId.",
                })
                record_invalid = True
                break
            seen_gl.add(gl_source_id)
            gl_mapping = _mapping(
                db, run=run, resource="GL_ACCOUNTS",
                source_id=gl_source_id, target_entity="GL_ACCOUNT",
            )
            if gl_mapping is None:
                bad.append({
                    "source_id": budget_id,
                    "reason": f"Budget reconciliation requires durable Buildium GL Account mapping {gl_source_id}.",
                })
                record_invalid = True
                break
            gl = (
                db.query(GLAccount)
                .filter(
                    GLAccount.id == gl_mapping.target_id,
                    GLAccount.organization_id == run.organization_id,
                    GLAccount.deleted_at.is_(None),
                    GLAccount.account_type.in_(("INCOME", "EXPENSE")),
                )
                .first()
            )
            if gl is None:
                bad.append({
                    "source_id": budget_id,
                    "reason": "Mapped Buildium budget GL account must be an in-scope INCOME or EXPENSE account.",
                })
                record_invalid = True
                break

            monthly = detail.get("MonthlyAmounts")
            if not isinstance(monthly, dict) or any(name not in monthly for name in _MONTHS):
                bad.append({
                    "source_id": budget_id,
                    "reason": "Buildium Budget MonthlyAmounts must explicitly contain January through December.",
                })
                record_invalid = True
                break
            amounts: list[Decimal] = []
            for month_name in _MONTHS:
                amount, error = _money(monthly.get(month_name), field=f"MonthlyAmounts.{month_name}")
                if error:
                    bad.append({"source_id": budget_id, "reason": error})
                    record_invalid = True
                    break
                amounts.append(amount)
            if record_invalid:
                break

            total, error = _money(detail.get("TotalAmount"), field="Details.TotalAmount")
            if error:
                bad.append({"source_id": budget_id, "reason": error})
                record_invalid = True
                break
            if sum(amounts, Decimal("0.00")) != total:
                bad.append({
                    "source_id": budget_id,
                    "reason": "Buildium Budget detail TotalAmount must equal the twelve MonthlyAmounts.",
                })
                record_invalid = True
                break

            for month, amount in enumerate(amounts, start=1):
                source_line_id = _source_line_id(budget_id, gl_source_id, year, month)
                if source_line_id in seen_line_ids:
                    bad.append({"source_id": source_line_id, "reason": "Duplicate Buildium Budget monthly source identity."})
                    record_invalid = True
                    break
                seen_line_ids.add(source_line_id)
                record_lines.append({
                    "source_id": source_line_id,
                    "budget_source_id": budget_id,
                    "property_source_id": property_source_id,
                    "gl_account_source_id": gl_source_id,
                    "target_property_id": target_property.id,
                    "target_gl_account_id": gl.id,
                    "calendar_year": year,
                    "month": month,
                    "amount": f"{amount:.2f}",
                })
            if record_invalid:
                break
        if not record_invalid:
            good.extend(record_lines)

    return good, bad


def dry_run_budgets(
    db: Session,
    *,
    run: PlatformMigrationRun,
    records: list[dict[str, Any]],
    resolutions=None,
) -> BudgetDryRunResult:
    if run.provider != "BUILDIUM" or not records:
        raise BuildiumBudgetMigrationError(
            "A Buildium run with at least one Budget record is required."
        )
    review = _normalize_resolutions(resolutions)
    fingerprint = _fingerprint(db, run=run, records=records, resolutions=resolutions)
    replayed = run.last_dry_run_fingerprint == fingerprint
    normalized, bad = _normalized_lines(db, run=run, records=records)

    rows: list[dict[str, Any]] = [
        {
            "source_id": item["source_id"],
            "reviewable": False,
            "reason": item["reason"],
            "mapped": None,
            "warnings": [],
        }
        for item in bad
    ]
    reviewable = skipped = warning_count = 0
    normalized_ids = {item["source_id"] for item in normalized}
    unknown = set(review) - normalized_ids
    if unknown:
        raise BuildiumBudgetMigrationError(
            "Budget review contains source_id values that are not valid monthly rows in this payload."
        )

    for mapped in normalized:
        source_id = mapped["source_id"]
        durable = _mapping(
            db, run=run, resource="BUDGET_LINES",
            source_id=source_id, target_entity="PROPERTY_BUDGET_LINE",
        )
        resolution = review.get(source_id)
        action = resolution["action"] if resolution else None
        target_id = resolution["target_property_budget_line_id"] if resolution else None
        warnings = [
            "This batch reconciles Buildium Budget monthly amounts to existing Property Budget Lines only; it never changes customer budget targets.",
            "No GLTransaction, GLEntry, actuals, forecasts, opening balances, or accounting history are created.",
        ]

        if durable is not None:
            if resolution is not None and (
                action != "MATCH_EXISTING" or target_id != durable.target_id
            ):
                raise BuildiumBudgetMigrationError(
                    f"Buildium Budget line {source_id} already has a durable mapping and cannot be re-resolved."
                )
            target = _target_line(db, run=run, target_id=durable.target_id)
            if target is None or not _matches(target, mapped):
                raise BuildiumBudgetMigrationError(
                    "Previously mapped Property Budget Line no longer matches the Buildium Budget contract."
                )
            action = "ALREADY_MAPPED"
            target_id = durable.target_id
            warnings.append(
                f"Already durably mapped to Property Budget Line #{durable.target_id}; commit will replay."
            )
        elif action == "MATCH_EXISTING":
            target = _target_line(db, run=run, target_id=target_id)
            if target is None or not _matches(target, mapped):
                raise BuildiumBudgetMigrationError(
                    "Reviewed Property Budget Line does not exactly match the Buildium monthly budget contract."
                )
            warnings.append(
                f"Reviewed MATCH_EXISTING target: Property Budget Line #{target.id}; commit creates mapping metadata only."
            )
        elif action == "SKIP":
            rows.append({
                "source_id": source_id,
                "reviewable": False,
                "reason": "Explicitly skipped after Buildium Budget review.",
                "mapped": mapped,
                "warnings": warnings,
                "resolution_action": "SKIP",
                "resolution_target_property_budget_line_id": None,
            })
            skipped += 1
            warning_count += len(warnings)
            continue
        else:
            candidates = (
                db.query(PropertyBudgetLine)
                .filter(
                    PropertyBudgetLine.organization_id == run.organization_id,
                    PropertyBudgetLine.property_id == mapped["target_property_id"],
                    PropertyBudgetLine.gl_account_id == mapped["target_gl_account_id"],
                    PropertyBudgetLine.calendar_year == mapped["calendar_year"],
                    PropertyBudgetLine.month == mapped["month"],
                    PropertyBudgetLine.amount == Decimal(mapped["amount"]),
                )
                .order_by(PropertyBudgetLine.id.asc())
                .limit(2)
                .all()
            )
            if len(candidates) == 1:
                warnings.append(
                    f"Possible exact existing Property Budget Line match: #{candidates[0].id}; explicit MATCH_EXISTING review is required."
                )
            elif len(candidates) > 1:
                warnings.append(
                    "Multiple target Property Budget Lines match; explicit review is required and no automatic selection is allowed."
                )

        rows.append({
            "source_id": source_id,
            "reviewable": True,
            "reason": None if action in {"MATCH_EXISTING", "ALREADY_MAPPED"} else "Explicit MATCH_EXISTING or SKIP review is required.",
            "mapped": mapped,
            "warnings": warnings,
            "resolution_action": action,
            "resolution_target_property_budget_line_id": target_id,
        })
        reviewable += 1
        warning_count += len(warnings)

    summary = {
        "resource": "BUDGET_LINES",
        "total": len(normalized) + len(bad),
        "reviewable": reviewable,
        "skipped_review": skipped,
        "invalid": len(bad),
        "warning_count": warning_count,
    }
    if not replayed:
        run.last_dry_run_fingerprint = fingerprint
        run.last_dry_run_summary = summary
        run.status = "DRY_RUN_READY"
        db.flush()

    return BudgetDryRunResult(
        fingerprint=fingerprint,
        replayed=replayed,
        total=summary["total"],
        reviewable=reviewable,
        skipped_review=skipped,
        invalid=len(bad),
        warning_count=warning_count,
        rows=rows,
        summary=summary,
    )


def commit_budgets(
    db: Session,
    *,
    run: PlatformMigrationRun,
    records: list[dict[str, Any]],
    expected_fingerprint: str,
    platform_user_id: int,
    resolutions=None,
) -> BudgetCommitResult:
    fingerprint = _fingerprint(db, run=run, records=records, resolutions=resolutions)
    if fingerprint != expected_fingerprint or run.last_dry_run_fingerprint != fingerprint:
        raise BuildiumBudgetMigrationError(
            "Buildium Budget commit requires the exact current dry-run fingerprint."
        )
    preview = dry_run_budgets(db, run=run, records=records, resolutions=resolutions)
    if preview.invalid:
        raise BuildiumBudgetMigrationError(
            "Buildium Budget commit is blocked while invalid source rows remain."
        )
    unresolved = [
        row for row in preview.rows
        if row.get("reviewable") and row.get("resolution_action") not in {"MATCH_EXISTING", "ALREADY_MAPPED"}
    ]
    if unresolved:
        raise BuildiumBudgetMigrationError(
            "Every Buildium Budget monthly row must be explicitly matched or skipped before commit."
        )

    matched = skipped = warning_count = 0
    committed_rows: list[dict[str, Any]] = []
    review = _normalize_resolutions(resolutions)

    for row in preview.rows:
        warning_count += len(row.get("warnings") or [])
        if row.get("resolution_action") == "SKIP":
            skipped += 1
            continue
        source_id = row["source_id"]
        mapped = row["mapped"]
        durable = _mapping(
            db, run=run, resource="BUDGET_LINES",
            source_id=source_id, target_entity="PROPERTY_BUDGET_LINE",
        )
        if durable is not None:
            target_id = durable.target_id
            replayed_row = True
        else:
            resolution = review.get(source_id)
            if resolution is None or resolution["action"] != "MATCH_EXISTING":
                raise BuildiumBudgetMigrationError(
                    "Buildium Budget monthly row lost its explicit review decision."
                )
            target_id = resolution["target_property_budget_line_id"]
            target = _target_line(db, run=run, target_id=target_id)
            if target is None or not _matches(target, mapped):
                raise BuildiumBudgetMigrationError(
                    "Reviewed Property Budget Line changed after dry run; commit is stale."
                )
            db.add(PlatformMigrationItem(
                run_id=run.id,
                organization_id=run.organization_id,
                provider="BUILDIUM",
                resource="BUDGET_LINES",
                source_id=source_id,
                target_entity="PROPERTY_BUDGET_LINE",
                target_id=target_id,
                source_fingerprint=hashlib.sha256(
                    json.dumps(mapped, sort_keys=True, separators=(",", ":")).encode()
                ).hexdigest(),
                created_by_platform_user_id=platform_user_id,
            ))
            replayed_row = False
            matched += 1
        committed_rows.append({
            "source_id": source_id,
            "target_property_budget_line_id": target_id,
            "replayed": replayed_row,
        })

    db.flush()
    run.status = "COMMITTED"
    return BudgetCommitResult(
        fingerprint=fingerprint,
        replayed=matched == 0 and bool(committed_rows),
        matched_existing=matched,
        skipped_review=skipped,
        warning_count=warning_count,
        rows=committed_rows,
    )
