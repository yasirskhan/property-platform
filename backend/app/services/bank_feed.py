"""Provider-neutral bank-feed CSV import and exact activity matching.

Phase 3.6 owns the durable inbox and manual import workflow. Live provider
connectivity (for example Plaid) remains Phase 8 and can insert into the same
table later. Import and matching are read-only with respect to accounting:
this service never creates, changes, or reverses GL transactions.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.bank_account import BankAccount
from app.models.bank_feed import BankFeedTransaction
from app.models.check import Check
from app.models.deposit import Deposit
from app.models.gl_entry import GLEntry
from app.models.gl_transaction import GLTransaction
from app.models.user import User

CENT = Decimal("0.01")


class BankFeedError(ValueError):
    pass


@dataclass(frozen=True)
class ParsedFeedRow:
    posted_date: date
    amount: Decimal
    payee: str | None
    description: str | None
    memo: str | None
    reference_number: str | None
    external_id: str | None
    import_key: str


@dataclass(frozen=True)
class ActivityCandidate:
    source_type: str
    source_id: int
    transaction_date: date
    amount: Decimal


def money(value) -> Decimal:
    return Decimal(value or 0).quantize(CENT)


def _clean(value: object | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _parse_date(value: str, row_number: int) -> date:
    raw = value.strip()
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    raise BankFeedError(
        f"CSV row {row_number}: unsupported date {raw!r}; use YYYY-MM-DD or MM/DD/YYYY."
    )


def _parse_amount(value: str, row_number: int) -> Decimal:
    raw = value.strip().replace("$", "").replace(",", "")
    if raw.startswith("(") and raw.endswith(")"):
        raw = "-" + raw[1:-1]
    try:
        amount = Decimal(raw).quantize(CENT)
    except (InvalidOperation, ValueError):
        raise BankFeedError(f"CSV row {row_number}: invalid amount {value!r}.")
    if amount == 0:
        raise BankFeedError(f"CSV row {row_number}: amount cannot be zero.")
    return amount


def _first(row: dict[str, str], names: tuple[str, ...]) -> str | None:
    for name in names:
        value = _clean(row.get(name))
        if value is not None:
            return value
    return None


def parse_bank_feed_csv(content: str) -> list[ParsedFeedRow]:
    try:
        reader = csv.DictReader(io.StringIO(content.lstrip("\ufeff")))
    except csv.Error as exc:
        raise BankFeedError(f"Could not read CSV: {exc}") from exc

    if not reader.fieldnames:
        raise BankFeedError("CSV must contain a header row.")

    normalized_headers = {
        str(name).strip().lower().replace(" ", "_"): name
        for name in reader.fieldnames
        if name is not None
    }
    date_aliases = ("date", "posted_date", "transaction_date")
    amount_aliases = ("amount", "signed_amount")
    if not any(name in normalized_headers for name in date_aliases):
        raise BankFeedError("CSV requires a date column (date, posted_date, or transaction_date).")
    if not any(name in normalized_headers for name in amount_aliases):
        raise BankFeedError("CSV requires an amount column.")

    rows: list[ParsedFeedRow] = []
    occurrence: Counter[str] = Counter()
    seen_external: set[str] = set()

    for row_number, source in enumerate(reader, start=2):
        normalized = {
            str(key).strip().lower().replace(" ", "_"): value
            for key, value in source.items()
            if key is not None
        }
        date_value = _first(normalized, date_aliases)
        amount_value = _first(normalized, amount_aliases)
        if date_value is None and amount_value is None and not any(_clean(v) for v in source.values()):
            continue
        if date_value is None:
            raise BankFeedError(f"CSV row {row_number}: date is required.")
        if amount_value is None:
            raise BankFeedError(f"CSV row {row_number}: amount is required.")

        posted_date = _parse_date(date_value, row_number)
        amount = _parse_amount(amount_value, row_number)
        payee = _first(normalized, ("payee", "merchant"))
        description = _first(normalized, ("description", "name", "transaction"))
        memo = _first(normalized, ("memo", "notes"))
        reference = _first(
            normalized,
            ("reference_number", "reference", "check_number"),
        )
        external_id = _first(
            normalized,
            ("external_id", "transaction_id", "provider_id"),
        )

        signature = json.dumps(
            {
                "posted_date": posted_date.isoformat(),
                "amount": str(amount),
                "payee": payee,
                "description": description,
                "memo": memo,
                "reference": reference,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        if external_id is not None:
            raw_key = f"external:{external_id}"
            if raw_key in seen_external:
                # Keep the duplicate in the parsed stream with the same key so
                # import accounting reports it as a duplicate rather than
                # creating a second durable transaction.
                pass
            seen_external.add(raw_key)
        else:
            occurrence[signature] += 1
            raw_key = f"row:{signature}:occurrence:{occurrence[signature]}"

        import_key = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()
        rows.append(
            ParsedFeedRow(
                posted_date=posted_date,
                amount=amount,
                payee=payee,
                description=description,
                memo=memo,
                reference_number=reference,
                external_id=external_id,
                import_key=import_key,
            )
        )

    if not rows:
        raise BankFeedError("CSV contains no transaction rows.")
    return rows


def _activity_candidates(
    db: Session,
    *,
    organization_id: int,
    bank_account: BankAccount,
    date_from: date,
    date_to: date,
) -> list[ActivityCandidate]:
    candidates: list[ActivityCandidate] = []

    deposits = (
        db.query(Deposit)
        .filter(
            Deposit.organization_id == organization_id,
            Deposit.bank_gl_account_id == bank_account.gl_account_id,
            Deposit.is_active.is_(True),
            Deposit.deposit_date >= date_from,
            Deposit.deposit_date <= date_to,
        )
        .all()
    )
    candidates.extend(
        ActivityCandidate("DEPOSIT", row.id, row.deposit_date, money(row.total))
        for row in deposits
    )

    checks = (
        db.query(Check)
        .filter(
            Check.organization_id == organization_id,
            Check.bank_account_id == bank_account.id,
            Check.status == "ISSUED",
            Check.check_date >= date_from,
            Check.check_date <= date_to,
        )
        .all()
    )
    candidates.extend(
        ActivityCandidate("CHECK", row.id, row.check_date, -money(row.amount))
        for row in checks
    )

    transactions = (
        db.query(GLTransaction)
        .join(GLEntry, GLEntry.transaction_id == GLTransaction.id)
        .filter(
            GLTransaction.organization_id == organization_id,
            GLEntry.organization_id == organization_id,
            GLEntry.gl_account_id == bank_account.gl_account_id,
            GLTransaction.transaction_date >= date_from,
            GLTransaction.transaction_date <= date_to,
            GLTransaction.transaction_type != "CHECK",
            func.coalesce(GLTransaction.source_type, "").notin_(["receipt", "check"]),
        )
        .distinct()
        .all()
    )
    for transaction in transactions:
        net = sum(
            (
                money(entry.debit) - money(entry.credit)
                for entry in transaction.entries
                if entry.gl_account_id == bank_account.gl_account_id
            ),
            Decimal("0"),
        )
        if net != 0:
            candidates.append(
                ActivityCandidate(
                    "GL",
                    transaction.id,
                    transaction.transaction_date,
                    money(net),
                )
            )

    return candidates


def _used_matches(
    db: Session,
    *,
    organization_id: int,
    bank_account_id: int,
) -> set[tuple[str, int]]:
    rows = (
        db.query(
            BankFeedTransaction.matched_source_type,
            BankFeedTransaction.matched_source_id,
        )
        .filter(
            BankFeedTransaction.organization_id == organization_id,
            BankFeedTransaction.bank_account_id == bank_account_id,
            BankFeedTransaction.status == "MATCHED",
            BankFeedTransaction.matched_source_type.isnot(None),
            BankFeedTransaction.matched_source_id.isnot(None),
        )
        .all()
    )
    return {(str(source_type), int(source_id)) for source_type, source_id in rows}


def _match_row(
    row: BankFeedTransaction,
    *,
    candidates: list[ActivityCandidate],
    used: set[tuple[str, int]],
) -> bool:
    matches = [
        candidate
        for candidate in candidates
        if candidate.transaction_date == row.posted_date
        and money(candidate.amount) == money(row.amount)
        and (candidate.source_type, candidate.source_id) not in used
    ]
    if len(matches) != 1:
        return False
    match = matches[0]
    row.status = "MATCHED"
    row.matched_source_type = match.source_type
    row.matched_source_id = match.source_id
    used.add((match.source_type, match.source_id))
    return True


def import_bank_feed_csv(
    db: Session,
    *,
    organization_id: int,
    bank_account: BankAccount,
    content: str,
    created_by: User,
) -> tuple[int, int, int, int]:
    if bank_account.organization_id != organization_id or not bank_account.is_active:
        raise BankFeedError("Bank account not found in your organization.")

    parsed = parse_bank_feed_csv(content)
    keys = [row.import_key for row in parsed]
    existing = {
        key
        for (key,) in db.query(BankFeedTransaction.import_key)
        .filter(
            BankFeedTransaction.organization_id == organization_id,
            BankFeedTransaction.bank_account_id == bank_account.id,
            BankFeedTransaction.import_key.in_(keys),
        )
        .all()
    }
    seen = set(existing)
    new_rows: list[BankFeedTransaction] = []
    duplicates = 0

    for source in parsed:
        if source.import_key in seen:
            duplicates += 1
            continue
        seen.add(source.import_key)
        row = BankFeedTransaction(
            organization_id=organization_id,
            bank_account_id=bank_account.id,
            source_provider="CSV",
            external_id=source.external_id,
            import_key=source.import_key,
            posted_date=source.posted_date,
            amount=source.amount,
            payee=source.payee,
            description=source.description,
            memo=source.memo,
            reference_number=source.reference_number,
            status="UNMATCHED",
            created_by_id=created_by.id,
        )
        db.add(row)
        new_rows.append(row)

    matched = 0
    if new_rows:
        date_from = min(row.posted_date for row in new_rows)
        date_to = max(row.posted_date for row in new_rows)
        candidates = _activity_candidates(
            db,
            organization_id=organization_id,
            bank_account=bank_account,
            date_from=date_from,
            date_to=date_to,
        )
        used = _used_matches(
            db,
            organization_id=organization_id,
            bank_account_id=bank_account.id,
        )
        for row in new_rows:
            if _match_row(row, candidates=candidates, used=used):
                matched += 1

    try:
        db.commit()
    except Exception as exc:
        db.rollback()
        raise BankFeedError(f"Failed to import bank feed: {exc}") from exc

    total = (
        db.query(BankFeedTransaction)
        .filter(
            BankFeedTransaction.organization_id == organization_id,
            BankFeedTransaction.bank_account_id == bank_account.id,
        )
        .count()
    )
    return len(new_rows), duplicates, matched, total


def rematch_bank_feed(
    db: Session,
    *,
    organization_id: int,
    bank_account: BankAccount,
) -> tuple[int, int]:
    rows = (
        db.query(BankFeedTransaction)
        .filter(
            BankFeedTransaction.organization_id == organization_id,
            BankFeedTransaction.bank_account_id == bank_account.id,
            BankFeedTransaction.status == "UNMATCHED",
        )
        .order_by(BankFeedTransaction.posted_date.asc(), BankFeedTransaction.id.asc())
        .all()
    )
    if not rows:
        return 0, 0

    candidates = _activity_candidates(
        db,
        organization_id=organization_id,
        bank_account=bank_account,
        date_from=min(row.posted_date for row in rows),
        date_to=max(row.posted_date for row in rows),
    )
    used = _used_matches(
        db,
        organization_id=organization_id,
        bank_account_id=bank_account.id,
    )
    matched = sum(
        1 for row in rows if _match_row(row, candidates=candidates, used=used)
    )
    try:
        db.commit()
    except Exception as exc:
        db.rollback()
        raise BankFeedError(f"Failed to rematch bank feed: {exc}") from exc
    remaining = sum(1 for row in rows if row.status == "UNMATCHED")
    return matched, remaining
