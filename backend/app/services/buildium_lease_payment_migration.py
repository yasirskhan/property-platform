"""Buildium lease-ledger payment existing-target reconciliation.

This Phase 4.14 adapter maps a documented Buildium lease payment to an
already-existing, internally consistent TENANT Receipt. It never creates or
updates Receipt, ReceiptLine, GLTransaction, GLEntry, invoice, charge, deposit,
or bank history.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
import hashlib
import json
from typing import Any

from sqlalchemy.orm import Session

from app.models.gl_account import GLAccount
from app.models.gl_entry import GLEntry
from app.models.gl_transaction import GLTransaction
from app.models.lease import Lease
from app.models.platform_migration import PlatformMigrationItem, PlatformMigrationRun
from app.models.property import Property, Unit
from app.models.receipt import Receipt
from app.models.receipt_line import ReceiptLine
from app.models.user import User, UserRole


class BuildiumLeasePaymentMigrationError(ValueError):
    pass


@dataclass(frozen=True)
class LeasePaymentDryRunResult:
    fingerprint: str
    replayed: bool
    total: int
    reviewable: int
    skipped_review: int
    invalid: int
    warning_count: int
    rows: list[dict[str, Any]]


@dataclass(frozen=True)
class LeasePaymentCommitResult:
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


def _date(value: Any) -> tuple[date | None, str | None]:
    text = _clean(value)
    if text is None:
        return None, "Buildium lease payment Date is required."
    try:
        return date.fromisoformat(text), None
    except ValueError:
        return None, "Buildium lease payment Date must be ISO YYYY-MM-DD."


def _money(value: Any, *, field: str) -> tuple[Decimal | None, str | None]:
    if value is None or isinstance(value, bool):
        return None, f"{field} must be an explicit positive decimal amount."
    try:
        raw = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None, f"{field} must be an explicit positive decimal amount."
    if not raw.is_finite():
        return None, f"{field} must be finite."
    rounded = raw.quantize(Decimal("0.01"))
    if raw != rounded or rounded <= 0:
        return None, f"{field} must be positive with no more than two decimal places."
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
        raise BuildiumLeasePaymentMigrationError(
            f"Buildium {resource} mapping for source ID {source_id} is inconsistent."
        )
    return row


def _normalize_resolutions(items) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for item in items or []:
        raw_source = item.get("source_id") if isinstance(item, dict) else getattr(item, "source_id", None)
        source_id = _positive_id(raw_source)
        if source_id is None or source_id in result:
            raise BuildiumLeasePaymentMigrationError(
                "Lease payment review requires unique positive source_id values."
            )
        action = item.get("action") if isinstance(item, dict) else getattr(item, "action", None)
        target = item.get("target_receipt_id") if isinstance(item, dict) else getattr(item, "target_receipt_id", None)
        if action not in {"MATCH_EXISTING", "SKIP"}:
            raise BuildiumLeasePaymentMigrationError(
                "Lease payment review supports only MATCH_EXISTING or SKIP."
            )
        if action == "MATCH_EXISTING":
            if isinstance(target, bool):
                raise BuildiumLeasePaymentMigrationError(
                    "MATCH_EXISTING requires a positive Receipt ID."
                )
            try:
                target = int(target)
            except (TypeError, ValueError):
                raise BuildiumLeasePaymentMigrationError(
                    "MATCH_EXISTING requires a positive Receipt ID."
                )
            if target < 1:
                raise BuildiumLeasePaymentMigrationError(
                    "MATCH_EXISTING requires a positive Receipt ID."
                )
        elif target is not None:
            raise BuildiumLeasePaymentMigrationError(
                "target_receipt_id is only valid for MATCH_EXISTING."
            )
        result[source_id] = {
            "source_id": int(source_id),
            "action": action,
            "target_receipt_id": target,
        }
    return result


def _source_dependency_ids(record: dict[str, Any]) -> dict[str, Any]:
    journal = record.get("Journal") if isinstance(record.get("Journal"), dict) else {}
    lines = journal.get("Lines") if isinstance(journal.get("Lines"), list) else []
    pay_detail = record.get("PaymentDetail") if isinstance(record.get("PaymentDetail"), dict) else {}
    payee = pay_detail.get("Payee") if isinstance(pay_detail.get("Payee"), dict) else {}
    deps = {
        "payment_source_id": _positive_id(record.get("Id")),
        "lease_source_id": _positive_id(record.get("LeaseId")),
        "tenant_source_id": _positive_id(payee.get("Id")),
        "lines": [],
    }
    for line in lines:
        if not isinstance(line, dict):
            continue
        gl = line.get("GLAccount") if isinstance(line.get("GLAccount"), dict) else {}
        entity = line.get("AccountingEntity") if isinstance(line.get("AccountingEntity"), dict) else {}
        unit = entity.get("Unit") if isinstance(entity.get("Unit"), dict) else {}
        deps["lines"].append({
            "gl_account_source_id": _positive_id(gl.get("Id")),
            "property_source_id": _positive_id(entity.get("Id")),
            "unit_source_id": _positive_id(unit.get("Id")),
        })
    return deps


def _dependency_snapshot(
    db: Session, *, run: PlatformMigrationRun, records: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for record in records:
        deps = _source_dependency_ids(record)
        item: dict[str, Any] = {
            "payment_source_id": deps["payment_source_id"],
            "lease_source_id": deps["lease_source_id"],
            "tenant_source_id": deps["tenant_source_id"],
            "lease": None,
            "tenant": None,
            "lines": [],
        }
        for key, resource, source_id, entity in (
            ("lease", "LEASES", deps["lease_source_id"], "LEASE_RELATIONSHIP"),
            ("tenant", "TENANTS", deps["tenant_source_id"], "TENANT_USER"),
        ):
            mapped = (
                _mapping(db, run=run, resource=resource, source_id=source_id, target_entity=entity)
                if source_id else None
            )
            item[key] = (
                {"target_id": mapped.target_id, "source_fingerprint": mapped.source_fingerprint}
                if mapped else None
            )
        for line in deps["lines"]:
            snap = dict(line)
            for key, resource, source_id, entity in (
                ("gl", "GL_ACCOUNTS", line["gl_account_source_id"], "GL_ACCOUNT"),
                ("property", "PROPERTIES", line["property_source_id"], "PROPERTY"),
                ("unit", "UNITS", line["unit_source_id"], "UNIT"),
            ):
                mapped = (
                    _mapping(db, run=run, resource=resource, source_id=source_id, target_entity=entity)
                    if source_id else None
                )
                snap[key] = (
                    {"target_id": mapped.target_id, "source_fingerprint": mapped.source_fingerprint}
                    if mapped else None
                )
            item["lines"].append(snap)
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
        "resource": "LEASE_PAYMENTS",
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
    return row if row is not None else (None, None, None, None)


def _line_mapping(
    db: Session,
    *,
    run: PlatformMigrationRun,
    line: dict[str, Any],
    lease_unit: Unit,
    lease_property: Property,
) -> tuple[dict[str, Any] | None, str | None]:
    gl_source = line.get("GLAccount") if isinstance(line.get("GLAccount"), dict) else {}
    entity = line.get("AccountingEntity") if isinstance(line.get("AccountingEntity"), dict) else {}
    entity_unit = entity.get("Unit") if isinstance(entity.get("Unit"), dict) else {}

    if (_clean(entity.get("AccountingEntityType")) or "").lower() != "rental":
        return None, "Buildium lease payment journal lines must use Rental accounting entities."

    gl_source_id = _positive_id(gl_source.get("Id"))
    property_source_id = _positive_id(entity.get("Id"))
    unit_source_id = _positive_id(entity_unit.get("Id"))
    if not gl_source_id or not property_source_id or not unit_source_id:
        return None, "Each Buildium lease payment journal line requires GL, Property, and Unit source IDs."

    gl_map = _mapping(
        db, run=run, resource="GL_ACCOUNTS", source_id=gl_source_id, target_entity="GL_ACCOUNT"
    )
    property_map = _mapping(
        db, run=run, resource="PROPERTIES", source_id=property_source_id, target_entity="PROPERTY"
    )
    unit_map = _mapping(
        db, run=run, resource="UNITS", source_id=unit_source_id, target_entity="UNIT"
    )
    if gl_map is None or property_map is None or unit_map is None:
        return None, "Lease payment reconciliation requires current GL Account, Property, and Unit mappings for every journal line."
    if property_map.target_id != lease_property.id or unit_map.target_id != lease_unit.id:
        return None, "Buildium lease payment journal scope does not match the mapped Lease property/unit."

    gl = (
        db.query(GLAccount)
        .filter(
            GLAccount.id == gl_map.target_id,
            GLAccount.organization_id == run.organization_id,
            GLAccount.deleted_at.is_(None),
        )
        .first()
    )
    if gl is None:
        return None, "Mapped Buildium GL Account is missing, deleted, or foreign."

    amount, error = _money(line.get("Amount"), field="Journal.Lines.Amount")
    if error:
        return None, error

    cash = line.get("IsCashPosting")
    if not isinstance(cash, bool):
        return None, "Buildium lease payment journal line IsCashPosting must be explicit."

    return {
        "target_gl_account_id": gl.id,
        "target_property_id": lease_property.id,
        "target_unit_id": lease_unit.id,
        "amount": f"{amount:.2f}",
        "is_cash_posting": cash,
    }, None


def _validate_source(
    db: Session, *, run: PlatformMigrationRun, record: dict[str, Any]
) -> tuple[dict[str, Any] | None, str | None, list[str]]:
    source_id = _positive_id(record.get("Id"))
    if source_id is None:
        return None, "Buildium lease payment Id must be a positive integer.", []

    lease_source_id = _positive_id(record.get("LeaseId"))
    if lease_source_id is None:
        return None, "LeaseId must be supplied from the parent Buildium lease-ledger context.", []
    lease_map = _mapping(
        db, run=run, resource="LEASES", source_id=lease_source_id, target_entity="LEASE_RELATIONSHIP"
    )
    if lease_map is None:
        return None, f"Lease payment reconciliation requires durable Buildium Lease mapping {lease_source_id}.", []
    lease, unit, prop, tenant = _target_lease(db, run=run, mapping=lease_map)
    if lease is None:
        return None, "Mapped Buildium Lease is no longer active and in organization scope.", []

    transaction_type = _clean(record.get("TransactionTypeEnum"))
    if transaction_type != "Payment":
        return None, "This bounded batch supports Buildium TransactionTypeEnum Payment only.", []

    tx_date, error = _date(record.get("Date"))
    if error:
        return None, error, []
    total, error = _money(record.get("TotalAmount"), field="TotalAmount")
    if error:
        return None, error, []

    payment_detail = record.get("PaymentDetail")
    if not isinstance(payment_detail, dict):
        return None, "Buildium PaymentDetail is required.", []
    payee = payment_detail.get("Payee")
    if not isinstance(payee, dict) or (_clean(payee.get("Type")) or "").lower() != "tenant":
        return None, "Buildium lease payment Payee must be an explicit Tenant.", []
    tenant_source_id = _positive_id(payee.get("Id"))
    if tenant_source_id is None:
        return None, "Buildium lease payment Tenant payee Id must be positive.", []
    tenant_map = _mapping(
        db, run=run, resource="TENANTS", source_id=tenant_source_id, target_entity="TENANT_USER"
    )
    if tenant_map is None or tenant_map.target_id != tenant.id:
        return None, "Buildium payment Tenant mapping must match the mapped Lease tenant.", []

    internal_status = payment_detail.get("InternalTransactionStatus")
    if isinstance(internal_status, dict) and internal_status.get("IsPending") is True:
        return None, "Pending Buildium internal payment transactions cannot be reconciled as received receipts.", []

    journal = record.get("Journal")
    if not isinstance(journal, dict):
        return None, "Buildium lease payment Journal is required.", []
    source_lines = journal.get("Lines")
    if not isinstance(source_lines, list) or len(source_lines) < 2:
        return None, "Buildium lease payment Journal must contain cash and allocation lines.", []

    mapped_lines: list[dict[str, Any]] = []
    for line in source_lines:
        if not isinstance(line, dict):
            return None, "Buildium lease payment Journal lines must be objects.", []
        mapped_line, line_error = _line_mapping(
            db, run=run, line=line, lease_unit=unit, lease_property=prop
        )
        if line_error:
            return None, line_error, []
        mapped_lines.append(mapped_line)

    cash_lines = [line for line in mapped_lines if line["is_cash_posting"]]
    applied_lines = [line for line in mapped_lines if not line["is_cash_posting"]]
    if len(cash_lines) != 1 or not applied_lines:
        return None, "Buildium lease payment requires exactly one cash-posting line and at least one non-cash allocation line.", []

    cash_amount = Decimal(cash_lines[0]["amount"])
    applied_total = sum((Decimal(line["amount"]) for line in applied_lines), Decimal("0.00"))
    if cash_amount != total or applied_total != total:
        return None, "Buildium lease payment cash and allocation line totals must each equal TotalAmount.", []

    mapped = {
        "lease_source_id": lease_source_id,
        "tenant_source_id": tenant_source_id,
        "target_lease_id": lease.id,
        "target_tenant_user_id": tenant.id,
        "target_property_id": prop.id,
        "target_unit_id": unit.id,
        "payment_date": tx_date.isoformat(),
        "amount": f"{total:.2f}",
        "target_cash_gl_account_id": cash_lines[0]["target_gl_account_id"],
        "allocation_lines": [
            {
                "target_gl_account_id": line["target_gl_account_id"],
                "target_property_id": line["target_property_id"],
                "target_unit_id": line["target_unit_id"],
                "amount": line["amount"],
            }
            for line in applied_lines
        ],
    }

    warnings = [
        "This batch reconciles one Buildium lease-ledger Payment to an already-existing target TENANT Receipt only; it never creates or updates money movement.",
        "Buildium PaymentMethod, check/reference text, deposit grouping, processor state, refund, credit, reversal, and outstanding-balance history are not converted into target state by this batch.",
        "The Buildium IsCashPosting flag is used only to match the target Receipt cash account versus allocation lines; no historical debit/credit direction is synthesized.",
        "Target Receipt and immutable GL integrity are rechecked before durable migration metadata is committed.",
    ]
    return mapped, None, warnings


def _target_receipt(db: Session, *, run: PlatformMigrationRun, receipt_id: int) -> Receipt | None:
    return (
        db.query(Receipt)
        .filter(
            Receipt.id == receipt_id,
            Receipt.organization_id == run.organization_id,
            Receipt.type == "TENANT",
            Receipt.is_active.is_(True),
            Receipt.deleted_at.is_(None),
            Receipt.is_reversed.is_(False),
            Receipt.reversal_of_id.is_(None),
        )
        .first()
    )


def _receipt_matches(
    db: Session, *, run: PlatformMigrationRun, receipt: Receipt, mapped: dict[str, Any]
) -> bool:
    if (
        receipt.tenant_user_id != mapped["target_tenant_user_id"]
        or receipt.property_id != mapped["target_property_id"]
        or receipt.unit_id != mapped["target_unit_id"]
        or receipt.cash_gl_account_id != mapped["target_cash_gl_account_id"]
        or receipt.receipt_date.isoformat() != mapped["payment_date"]
        or Decimal(receipt.amount).quantize(Decimal("0.01")) != Decimal(mapped["amount"])
        or receipt.gl_transaction_id is None
    ):
        return False

    receipt_lines = (
        db.query(ReceiptLine)
        .filter(
            ReceiptLine.receipt_id == receipt.id,
            ReceiptLine.organization_id == run.organization_id,
        )
        .all()
    )
    if not receipt_lines or any(line.is_prepayment for line in receipt_lines):
        return False
    actual_allocations = Counter(
        (
            line.gl_account_id,
            line.property_id,
            line.unit_id,
            f"{Decimal(line.amount_to_pay).quantize(Decimal('0.01')):.2f}",
        )
        for line in receipt_lines
    )
    expected_allocations = Counter(
        (
            line["target_gl_account_id"],
            line["target_property_id"],
            line["target_unit_id"],
            line["amount"],
        )
        for line in mapped["allocation_lines"]
    )
    if actual_allocations != expected_allocations:
        return False

    txn = (
        db.query(GLTransaction)
        .filter(
            GLTransaction.id == receipt.gl_transaction_id,
            GLTransaction.organization_id == run.organization_id,
            GLTransaction.transaction_type == "RECEIPT",
            GLTransaction.source_type == "receipt",
            GLTransaction.source_id == receipt.id,
            GLTransaction.transaction_date == receipt.receipt_date,
            GLTransaction.is_reversed.is_(False),
            GLTransaction.reversal_of_id.is_(None),
        )
        .first()
    )
    if txn is None:
        return False
    entries = (
        db.query(GLEntry)
        .filter(
            GLEntry.transaction_id == txn.id,
            GLEntry.organization_id == run.organization_id,
        )
        .all()
    )
    expected_entries = Counter()
    expected_entries[
        (
            receipt.cash_gl_account_id,
            receipt.property_id,
            receipt.unit_id,
            f"{Decimal(receipt.amount).quantize(Decimal('0.01')):.2f}",
            "0.00",
        )
    ] += 1
    for line in receipt_lines:
        expected_entries[
            (
                line.gl_account_id,
                line.property_id,
                line.unit_id,
                "0.00",
                f"{Decimal(line.amount_to_pay).quantize(Decimal('0.01')):.2f}",
            )
        ] += 1
    actual_entries = Counter(
        (
            entry.gl_account_id,
            entry.property_id,
            entry.unit_id,
            f"{Decimal(entry.debit).quantize(Decimal('0.01')):.2f}",
            f"{Decimal(entry.credit).quantize(Decimal('0.01')):.2f}",
        )
        for entry in entries
    )
    return actual_entries == expected_entries


def dry_run_lease_payments(
    db: Session,
    *,
    run: PlatformMigrationRun,
    records: list[dict[str, Any]],
    resolutions=None,
) -> LeasePaymentDryRunResult:
    if run.provider != "BUILDIUM" or not records:
        raise BuildiumLeasePaymentMigrationError(
            "A Buildium run with at least one Lease Payment record is required."
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
                "reason": "Duplicate Buildium Lease Payment Id in this dry run.",
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
            db, run=run, resource="LEASE_PAYMENTS",
            source_id=source_id, target_entity="RECEIPT_RELATIONSHIP",
        )
        resolution = review.get(source_id)
        action = resolution["action"] if resolution else None
        target_id = resolution["target_receipt_id"] if resolution else None

        if durable is not None:
            if resolution is not None and (
                action != "MATCH_EXISTING" or target_id != durable.target_id
            ):
                raise BuildiumLeasePaymentMigrationError(
                    f"Buildium Lease Payment {source_id} already has a durable mapping and cannot be re-resolved."
                )
            target = _target_receipt(db, run=run, receipt_id=durable.target_id)
            if target is None or not _receipt_matches(db, run=run, receipt=target, mapped=mapped):
                raise BuildiumLeasePaymentMigrationError(
                    "Previously mapped target Receipt no longer matches the Buildium Lease Payment contract."
                )
            action = "ALREADY_MAPPED"
            target_id = durable.target_id
            warnings.append(
                f"Buildium Lease Payment {source_id} is already durably mapped to Receipt #{durable.target_id}; commit will replay."
            )
        elif action == "MATCH_EXISTING":
            target = _target_receipt(db, run=run, receipt_id=target_id)
            if target is None or not _receipt_matches(db, run=run, receipt=target, mapped=mapped):
                raise BuildiumLeasePaymentMigrationError(
                    "Reviewed target Receipt does not exactly match the Buildium Lease Payment and immutable receipt/GL contract."
                )
            warnings.append(
                f"Reviewed MATCH_EXISTING target: Receipt #{target.id}; commit creates migration metadata only."
            )
        elif action == "SKIP":
            rows.append({
                "source_id": source_id,
                "reviewable": False,
                "reason": "Explicitly skipped after Buildium Lease Payment review.",
                "mapped": mapped,
                "warnings": warnings,
                "resolution_action": "SKIP",
                "resolution_target_receipt_id": None,
            })
            skipped += 1
            warning_count += len(warnings)
            continue
        else:
            candidates = (
                db.query(Receipt)
                .filter(
                    Receipt.organization_id == run.organization_id,
                    Receipt.type == "TENANT",
                    Receipt.tenant_user_id == mapped["target_tenant_user_id"],
                    Receipt.property_id == mapped["target_property_id"],
                    Receipt.unit_id == mapped["target_unit_id"],
                    Receipt.cash_gl_account_id == mapped["target_cash_gl_account_id"],
                    Receipt.receipt_date == date.fromisoformat(mapped["payment_date"]),
                    Receipt.amount == Decimal(mapped["amount"]),
                    Receipt.is_active.is_(True),
                    Receipt.deleted_at.is_(None),
                    Receipt.is_reversed.is_(False),
                )
                .order_by(Receipt.id.asc())
                .limit(5)
                .all()
            )
            exact = [
                candidate for candidate in candidates
                if _receipt_matches(db, run=run, receipt=candidate, mapped=mapped)
            ]
            if len(exact) == 1:
                warnings.append(
                    f"Possible exact existing target Receipt match: Receipt #{exact[0].id}; explicit MATCH_EXISTING review is required."
                )
            elif len(exact) > 1:
                warnings.append(
                    "Multiple exact target Receipts match this Buildium payment; no candidate is auto-selected."
                )
            else:
                warnings.append(
                    "No exact target Receipt exists; this bounded batch does not create one."
                )

        rows.append({
            "source_id": source_id,
            "reviewable": True,
            "reason": None,
            "mapped": mapped,
            "warnings": warnings,
            "resolution_action": action,
            "resolution_target_receipt_id": target_id,
        })
        reviewable += 1
        warning_count += len(warnings)

    extra = sorted(set(review) - seen, key=int)
    if extra:
        raise BuildiumLeasePaymentMigrationError(
            "Lease Payment review contains source IDs not present in this dry run: "
            + ", ".join(extra)
        )

    if not replayed:
        run.last_dry_run_fingerprint = fingerprint
        run.last_dry_run_summary = {
            "resource": "LEASE_PAYMENTS",
            "total": len(records),
            "reviewable": reviewable,
            "skipped_review": skipped,
            "invalid": invalid,
            "warning_count": warning_count,
            "target_receipt_created": False,
            "gl_history_created": False,
            "deposit_reconciled": False,
        }
        run.status = "LEASE_PAYMENTS_DRY_RUN_READY"
        db.flush()

    return LeasePaymentDryRunResult(
        fingerprint=fingerprint,
        replayed=replayed,
        total=len(records),
        reviewable=reviewable,
        skipped_review=skipped,
        invalid=invalid,
        warning_count=warning_count,
        rows=rows,
    )


def commit_lease_payments(
    db: Session,
    *,
    run: PlatformMigrationRun,
    records: list[dict[str, Any]],
    expected_fingerprint: str,
    platform_user_id: int,
    resolutions=None,
) -> LeasePaymentCommitResult:
    current = _fingerprint(db, run=run, records=records, resolutions=resolutions)
    if current != expected_fingerprint or run.last_dry_run_fingerprint != expected_fingerprint:
        raise BuildiumLeasePaymentMigrationError(
            "Buildium Lease Payment dry run is stale; run exact review again before commit."
        )

    preview = dry_run_lease_payments(
        db, run=run, records=records, resolutions=resolutions
    )
    if preview.invalid:
        raise BuildiumLeasePaymentMigrationError(
            "Buildium Lease Payment commit is blocked while invalid records remain."
        )
    missing = [
        row["source_id"] for row in preview.rows
        if row.get("resolution_action") is None
    ]
    if missing:
        raise BuildiumLeasePaymentMigrationError(
            "Lease Payment migration requires explicit review for source IDs: "
            + ", ".join(missing)
        )

    review = _normalize_resolutions(resolutions)
    rows: list[dict[str, Any]] = []
    matched = skipped = 0
    changed = reviewed_only = False

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
                "target_receipt_id": row["resolution_target_receipt_id"],
                "replayed": True,
            })
            continue

        target_id = int(review[source_id]["target_receipt_id"])
        target = _target_receipt(db, run=run, receipt_id=target_id)
        if target is None or not _receipt_matches(db, run=run, receipt=target, mapped=row["mapped"]):
            raise BuildiumLeasePaymentMigrationError(
                "Reviewed target Receipt changed after dry run."
            )
        db.add(
            PlatformMigrationItem(
                run_id=run.id,
                organization_id=run.organization_id,
                provider="BUILDIUM",
                resource="LEASE_PAYMENTS",
                source_id=source_id,
                target_entity="RECEIPT_RELATIONSHIP",
                target_id=target.id,
                source_fingerprint=preview.fingerprint,
                created_by_platform_user_id=platform_user_id,
            )
        )
        rows.append({
            "source_id": source_id,
            "target_receipt_id": target.id,
            "replayed": False,
        })
        matched += 1
        changed = True

    if changed:
        run.status = "LEASE_PAYMENTS_RECONCILED"
        db.flush()
    elif reviewed_only and not rows:
        run.status = "LEASE_PAYMENTS_REVIEWED"
        db.flush()

    return LeasePaymentCommitResult(
        fingerprint=preview.fingerprint,
        replayed=not changed and not reviewed_only,
        matched_existing=matched,
        skipped_review=skipped,
        warning_count=preview.warning_count,
        rows=rows,
    )
