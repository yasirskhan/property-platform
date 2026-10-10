"""Recurring journal-entry scheduling and durable due-posting."""

from __future__ import annotations

import calendar
from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.gl_account import GLAccount
from app.models.gl_transaction import GLTransaction
from app.models.organization_feature_setting import OrganizationFeatureSetting
from app.models.property import Property, Unit
from app.models.recurring_journal_entry import (
    RecurringJournalEntry,
    RecurringJournalEntryLine,
)
from app.models.user import User, UserRole
from app.schemas.gl_transaction import PostingLine
from app.services.audit import append_audit_log
from app.services.entitlement_resolver import entitlement_allows_feature
from app.services.gl_posting import PostingError, post_transaction
from app.services.release_gate_resolver import release_gate_allows_org


RECURRING_JE_GATE = "release.accounting.journal_entries.recurring"
RECURRING_JE_ENTITLEMENT = "recurring_journal_entries"


def recurring_journal_entries_enabled_for_org(
    db: Session, *, organization_id: int
) -> bool:
    if not release_gate_allows_org(
        db,
        gate_key=RECURRING_JE_GATE,
        organization_id=organization_id,
    ):
        return False
    if not entitlement_allows_feature(
        db,
        organization_id=organization_id,
        feature_key=RECURRING_JE_ENTITLEMENT,
    ):
        return False
    setting = (
        db.query(OrganizationFeatureSetting)
        .filter(
            OrganizationFeatureSetting.organization_id == organization_id,
            OrganizationFeatureSetting.feature_key == RECURRING_JE_GATE,
        )
        .first()
    )
    return setting is None or bool(setting.enabled)


def monthly_date(year: int, month: int, day_of_month: int) -> date:
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, min(day_of_month, last_day))


def first_monthly_date_on_or_after(start_date: date, day_of_month: int) -> date:
    candidate = monthly_date(start_date.year, start_date.month, day_of_month)
    if candidate >= start_date:
        return candidate
    year = start_date.year + (1 if start_date.month == 12 else 0)
    month = 1 if start_date.month == 12 else start_date.month + 1
    return monthly_date(year, month, day_of_month)


def next_monthly_date(current: date, day_of_month: int) -> date:
    year = current.year + (1 if current.month == 12 else 0)
    month = 1 if current.month == 12 else current.month + 1
    return monthly_date(year, month, day_of_month)


def _validate_template_scope(
    db: Session,
    *,
    organization_id: int,
    lines: list,
) -> None:
    account_ids = {line.gl_account_id for line in lines}
    accounts = (
        db.query(GLAccount)
        .filter(
            GLAccount.organization_id == organization_id,
            GLAccount.id.in_(account_ids),
        )
        .all()
    )
    if {row.id for row in accounts} != account_ids:
        raise PostingError("One or more GL accounts are outside this organization.")
    if any(not row.is_active for row in accounts):
        raise PostingError("Recurring journal entries cannot use inactive GL accounts.")

    property_ids = {line.property_id for line in lines if line.property_id is not None}
    if property_ids:
        found = {
            row.id
            for row in db.query(Property)
            .filter(
                Property.organization_id == organization_id,
                Property.id.in_(property_ids),
            )
            .all()
        }
        if found != property_ids:
            raise PostingError("One or more properties are outside this organization.")

    unit_ids = {line.unit_id for line in lines if line.unit_id is not None}
    if unit_ids:
        units = db.query(Unit).filter(Unit.id.in_(unit_ids)).all()
        by_id = {row.id: row for row in units}
        if set(by_id) != unit_ids:
            raise PostingError("One or more units do not exist.")
        for line in lines:
            if line.unit_id is None:
                continue
            if line.property_id is None or by_id[line.unit_id].property_id != line.property_id:
                raise PostingError("A recurring JE unit must belong to its selected property.")

    owner_ids = {line.owner_id for line in lines if line.owner_id is not None}
    if owner_ids:
        found = {
            row.id
            for row in db.query(User)
            .filter(
                User.organization_id == organization_id,
                User.id.in_(owner_ids),
            )
            .all()
        }
        if found != owner_ids:
            raise PostingError("One or more owners are outside this organization.")


def create_recurring_journal_entry(
    db: Session,
    *,
    organization_id: int,
    created_by: User,
    name: str,
    start_date: date,
    end_date: date | None,
    day_of_month: int,
    reference_number: str | None,
    memo: str | None,
    lines: list,
) -> RecurringJournalEntry:
    if end_date is not None and end_date < start_date:
        raise PostingError("End date cannot be before start date.")
    if day_of_month < 1 or day_of_month > 31:
        raise PostingError("Day of month must be between 1 and 31.")
    _validate_template_scope(
        db,
        organization_id=organization_id,
        lines=lines,
    )

    next_post = first_monthly_date_on_or_after(start_date, day_of_month)
    if end_date is not None and next_post > end_date:
        raise PostingError("The schedule has no posting date inside its date range.")

    row = RecurringJournalEntry(
        organization_id=organization_id,
        name=name.strip(),
        start_date=start_date,
        end_date=end_date,
        day_of_month=day_of_month,
        next_post_date=next_post,
        reference_number=reference_number,
        memo=memo,
        is_active=True,
        created_by_id=created_by.id,
    )
    row.lines = [
        RecurringJournalEntryLine(
            gl_account_id=line.gl_account_id,
            property_id=line.property_id,
            unit_id=line.unit_id,
            owner_id=line.owner_id,
            description=line.description,
            debit=Decimal(line.debit or 0),
            credit=Decimal(line.credit or 0),
        )
        for line in lines
    ]
    db.add(row)
    db.flush()
    append_audit_log(
        db,
        user_id=created_by.id,
        organization_id=organization_id,
        entity_type="recurring_journal_entry",
        entity_id=row.id,
        action="create",
        new_value=f"next_post_date={next_post.isoformat()}",
    )
    db.commit()
    db.refresh(row)
    return row


def _posting_user(db: Session, schedule: RecurringJournalEntry) -> User | None:
    if schedule.created_by_id is not None:
        user = db.get(User, schedule.created_by_id)
        if (
            user is not None
            and user.organization_id == schedule.organization_id
            and user.is_active
        ):
            return user
    return (
        db.query(User)
        .filter(
            User.organization_id == schedule.organization_id,
            User.is_active.is_(True),
            User.role.in_([UserRole.ADMIN, UserRole.OWNER, UserRole.MANAGER]),
        )
        .order_by(User.id.asc())
        .first()
    )


def _post_one_due_occurrence(
    db: Session,
    *,
    schedule: RecurringJournalEntry,
    posting_date: date,
) -> bool:
    existing = (
        db.query(GLTransaction)
        .filter(
            GLTransaction.organization_id == schedule.organization_id,
            GLTransaction.transaction_type == "JOURNAL_ENTRY",
            GLTransaction.source_type == "recurring_je",
            GLTransaction.source_id == schedule.id,
            GLTransaction.transaction_date == posting_date,
        )
        .first()
    )
    user = _posting_user(db, schedule)
    if user is None:
        raise PostingError("Recurring journal entry has no active posting user.")

    transaction = existing
    if transaction is None:
        transaction = post_transaction(
            db=db,
            organization_id=schedule.organization_id,
            transaction_date=posting_date,
            transaction_type="JOURNAL_ENTRY",
            memo=schedule.memo,
            lines=[
                PostingLine(
                    gl_account_id=line.gl_account_id,
                    property_id=line.property_id,
                    unit_id=line.unit_id,
                    owner_id=line.owner_id,
                    description=line.description,
                    debit=Decimal(line.debit or 0),
                    credit=Decimal(line.credit or 0),
                )
                for line in schedule.lines
            ],
            created_by=user,
            reference_number=schedule.reference_number,
            source_type="recurring_je",
            source_id=schedule.id,
            commit=False,
            write_audit=False,
        )

    schedule.last_posted_date = posting_date
    next_date = next_monthly_date(posting_date, schedule.day_of_month)
    schedule.next_post_date = next_date
    if schedule.end_date is not None and next_date > schedule.end_date:
        schedule.is_active = False

    append_audit_log(
        db,
        user_id=user.id,
        organization_id=schedule.organization_id,
        entity_type="gl_transaction",
        entity_id=transaction.id,
        action="post",
        field_name="JOURNAL_ENTRY",
        new_value=f"recurring_journal_entry={schedule.id}",
    )
    db.commit()
    return existing is None


def post_due_recurring_journal_entries(
    db: Session,
    *,
    as_of: date,
    organization_id: int | None = None,
) -> dict[str, int]:
    query = db.query(RecurringJournalEntry.id).filter(
        RecurringJournalEntry.is_active.is_(True),
        RecurringJournalEntry.next_post_date <= as_of,
    )
    if organization_id is not None:
        query = query.filter(RecurringJournalEntry.organization_id == organization_id)
    schedule_ids = [row[0] for row in query.order_by(RecurringJournalEntry.id.asc()).all()]

    posted = 0
    skipped_disabled = 0
    failed = 0

    for schedule_id in schedule_ids:
        schedule = db.get(RecurringJournalEntry, schedule_id)
        if schedule is None or not schedule.is_active:
            continue
        if not recurring_journal_entries_enabled_for_org(
            db, organization_id=schedule.organization_id
        ):
            skipped_disabled += 1
            continue

        try:
            while schedule.is_active and schedule.next_post_date <= as_of:
                posting_date = schedule.next_post_date
                if schedule.end_date is not None and posting_date > schedule.end_date:
                    schedule.is_active = False
                    db.commit()
                    break
                if _post_one_due_occurrence(
                    db,
                    schedule=schedule,
                    posting_date=posting_date,
                ):
                    posted += 1
                schedule = db.get(RecurringJournalEntry, schedule_id)
                if schedule is None:
                    break
        except Exception:
            db.rollback()
            failed += 1

    return {
        "posted": posted,
        "skipped_disabled": skipped_disabled,
        "failed": failed,
    }
