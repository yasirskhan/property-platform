"""Gross Potential Rent candidate calculation and journal posting."""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.gl_account import GLAccount
from app.models.gl_transaction import GLTransaction
from app.models.lease import Lease, LeaseStatus
from app.models.organization_feature_setting import OrganizationFeatureSetting
from app.models.property import Property, Unit
from app.models.user import User
from app.schemas.gl_transaction import PostingLine
from app.services.audit import append_audit_log
from app.services.entitlement_resolver import entitlement_allows_feature
from app.services.gl_posting import PostingError, post_transaction
from app.services.release_gate_resolver import release_gate_allows_org


GPR_GATE = "release.accounting.journal_entries.post_gpr"
GPR_ENTITLEMENT = "gpr_posting"
RENT_GL = "4100"
GPR_GL = "4115"
LOSS_GAIN_GL = "4120"


@dataclass(frozen=True)
class GPRCandidate:
    unit_id: int
    property_id: int
    property_name: str
    unit_number: str
    lease_id: int | None
    market_rent: Decimal
    scheduled_rent: Decimal
    loss_gain: Decimal
    already_posted: bool
    transaction_id: int | None


def gpr_posting_enabled_for_org(db: Session, *, organization_id: int) -> bool:
    if not release_gate_allows_org(
        db, gate_key=GPR_GATE, organization_id=organization_id
    ):
        return False
    if not entitlement_allows_feature(
        db, organization_id=organization_id, feature_key=GPR_ENTITLEMENT
    ):
        return False
    setting = (
        db.query(OrganizationFeatureSetting)
        .filter(
            OrganizationFeatureSetting.organization_id == organization_id,
            OrganizationFeatureSetting.feature_key == GPR_GATE,
        )
        .first()
    )
    return setting is None or bool(setting.enabled)


def month_bounds(value: date) -> tuple[date, date]:
    start = date(value.year, value.month, 1)
    end = date(value.year, value.month, calendar.monthrange(value.year, value.month)[1])
    return start, end


def _active_lease_for_month(
    db: Session, *, unit_id: int, month_start: date, month_end: date
) -> Lease | None:
    rows = (
        db.query(Lease)
        .filter(
            Lease.unit_id == unit_id,
            Lease.status == LeaseStatus.ACTIVE,
            Lease.start_date <= month_end,
            Lease.end_date >= month_start,
        )
        .order_by(Lease.start_date.desc(), Lease.id.desc())
        .all()
    )
    if len(rows) > 1:
        raise PostingError(
            f"Unit {unit_id} has multiple active leases overlapping "
            f"{month_start:%Y-%m}; resolve the lease overlap before posting GPR."
        )
    return rows[0] if rows else None


def list_gpr_candidates(
    db: Session, *, organization_id: int, month: date
) -> list[GPRCandidate]:
    month_start, month_end = month_bounds(month)
    rows = (
        db.query(Unit, Property)
        .join(Property, Property.id == Unit.property_id)
        .filter(
            Property.organization_id == organization_id,
            Property.is_active.is_(True),
            Unit.is_active.is_(True),
            Unit.monthly_rent > 0,
        )
        .order_by(Property.name.asc(), Unit.unit_number.asc(), Unit.id.asc())
        .all()
    )
    posted = {
        row.source_id: row
        for row in db.query(GLTransaction)
        .filter(
            GLTransaction.organization_id == organization_id,
            GLTransaction.transaction_type == "JOURNAL_ENTRY",
            GLTransaction.source_type == "gpr",
            GLTransaction.transaction_date == month_start,
            GLTransaction.is_reversed.is_(False),
        )
        .all()
        if row.source_id is not None
    }

    result: list[GPRCandidate] = []
    for unit, prop in rows:
        lease = _active_lease_for_month(
            db, unit_id=unit.id, month_start=month_start, month_end=month_end
        )
        market = Decimal(unit.monthly_rent or 0).quantize(Decimal("0.01"))
        scheduled = Decimal(lease.monthly_rent if lease else 0).quantize(
            Decimal("0.01")
        )
        existing = posted.get(unit.id)
        result.append(
            GPRCandidate(
                unit_id=unit.id,
                property_id=prop.id,
                property_name=prop.name,
                unit_number=unit.unit_number,
                lease_id=lease.id if lease else None,
                market_rent=market,
                scheduled_rent=scheduled,
                loss_gain=(market - scheduled).quantize(Decimal("0.01")),
                already_posted=existing is not None,
                transaction_id=existing.id if existing else None,
            )
        )
    return result


def _required_accounts(db: Session, *, organization_id: int) -> dict[str, GLAccount]:
    rows = (
        db.query(GLAccount)
        .filter(
            GLAccount.organization_id == organization_id,
            GLAccount.gl_number.in_([RENT_GL, GPR_GL, LOSS_GAIN_GL]),
            GLAccount.is_active.is_(True),
        )
        .all()
    )
    by_number = {row.gl_number: row for row in rows}
    missing = [number for number in [RENT_GL, GPR_GL, LOSS_GAIN_GL] if number not in by_number]
    if missing:
        raise PostingError(
            "Post GPR requires active standard GL account(s): "
            + ", ".join(missing)
            + "."
        )
    return by_number


def post_gpr(
    db: Session,
    *,
    organization_id: int,
    month: date,
    unit_ids: list[int],
    created_by: User,
) -> list[GLTransaction]:
    if not unit_ids:
        raise PostingError("Select at least one unit to post GPR.")
    if len(set(unit_ids)) != len(unit_ids):
        raise PostingError("Each unit may only be selected once.")

    month_start, _ = month_bounds(month)
    candidates = {
        row.unit_id: row
        for row in list_gpr_candidates(
            db, organization_id=organization_id, month=month_start
        )
    }
    missing = sorted(set(unit_ids) - set(candidates))
    if missing:
        raise PostingError(
            f"GPR unit(s) are not active in this organization: {missing}"
        )
    already = sorted(
        unit_id for unit_id in unit_ids if candidates[unit_id].already_posted
    )
    if already:
        raise PostingError(
            f"GPR is already posted for unit(s) {already} in {month_start:%Y-%m}."
        )

    accounts = _required_accounts(db, organization_id=organization_id)
    transactions: list[GLTransaction] = []

    try:
        for unit_id in unit_ids:
            row = candidates[unit_id]
            prop = db.get(Property, row.property_id)
            if prop is None or prop.organization_id != organization_id:
                raise PostingError("GPR property scope changed during posting.")

            lines: list[PostingLine] = []
            if row.scheduled_rent > 0:
                lines.append(
                    PostingLine(
                        gl_account_id=accounts[RENT_GL].id,
                        property_id=row.property_id,
                        unit_id=row.unit_id,
                        owner_id=prop.owner_id,
                        description=f"GPR scheduled rent - Unit {row.unit_number}",
                        debit=row.scheduled_rent,
                        credit=Decimal("0"),
                    )
                )

            lines.append(
                PostingLine(
                    gl_account_id=accounts[GPR_GL].id,
                    property_id=row.property_id,
                    unit_id=row.unit_id,
                    owner_id=prop.owner_id,
                    description=f"Gross potential rent - Unit {row.unit_number}",
                    debit=Decimal("0"),
                    credit=row.market_rent,
                )
            )

            if row.loss_gain > 0:
                lines.append(
                    PostingLine(
                        gl_account_id=accounts[LOSS_GAIN_GL].id,
                        property_id=row.property_id,
                        unit_id=row.unit_id,
                        owner_id=prop.owner_id,
                        description=f"Loss to market/vacancy - Unit {row.unit_number}",
                        debit=row.loss_gain,
                        credit=Decimal("0"),
                    )
                )
            elif row.loss_gain < 0:
                lines.append(
                    PostingLine(
                        gl_account_id=accounts[LOSS_GAIN_GL].id,
                        property_id=row.property_id,
                        unit_id=row.unit_id,
                        owner_id=prop.owner_id,
                        description=f"Gain to market - Unit {row.unit_number}",
                        debit=Decimal("0"),
                        credit=abs(row.loss_gain),
                    )
                )

            txn = post_transaction(
                db=db,
                organization_id=organization_id,
                transaction_date=month_start,
                transaction_type="JOURNAL_ENTRY",
                memo=f"Gross Potential Rent - {month_start:%Y-%m} - "
                f"{row.property_name} / {row.unit_number}",
                lines=lines,
                created_by=created_by,
                reference_number=f"GPR-{month_start:%Y%m}-{row.unit_id}",
                source_type="gpr",
                source_id=row.unit_id,
                commit=False,
                write_audit=False,
            )
            transactions.append(txn)
            append_audit_log(
                db,
                user_id=created_by.id,
                organization_id=organization_id,
                entity_type="gl_transaction",
                entity_id=txn.id,
                action="post_gpr",
                new_value={
                    "month": month_start.isoformat(),
                    "unit_id": row.unit_id,
                    "market_rent": str(row.market_rent),
                    "scheduled_rent": str(row.scheduled_rent),
                    "loss_gain": str(row.loss_gain),
                },
            )
        db.commit()
        for txn in transactions:
            db.refresh(txn)
        return transactions
    except Exception:
        db.rollback()
        raise
