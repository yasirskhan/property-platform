"""Append Section 44 to PROJECT_MASTER.md, and update the
'57 GL' references to '60 GL'. Safe to run multiple times —
it checks before doing anything."""
from pathlib import Path

PATH = Path(r"C:\Projects\property-platform\docs\PROJECT_MASTER.md")

if not PATH.exists():
    print("ERROR: PROJECT_MASTER.md not found at", PATH)
    raise SystemExit(1)

text = PATH.read_text(encoding="utf-8")

# -----------------------------------------------------------------
# 1. Replace 57 GL -> 60 GL (only if not already replaced)
# -----------------------------------------------------------------
replaced_57 = 0
if "57 GL Accounts" in text:
    text = text.replace("57 GL Accounts", "60 GL Accounts")
    replaced_57 += 1
if "57 accounts" in text:
    text = text.replace("57 accounts", "60 accounts")
    replaced_57 += 1
if "# SECTION 12 — THE 57 GL ACCOUNTS" in text:
    text = text.replace(
        "# SECTION 12 — THE 57 GL ACCOUNTS",
        "# SECTION 12 — THE 60 GL ACCOUNTS",
    )
    replaced_57 += 1

print(f"Replaced '57' references: {replaced_57}")

# -----------------------------------------------------------------
# 2. Append Section 44 (only if not already there)
# -----------------------------------------------------------------
MARKER = "# SECTION 44 — GENERAL LEDGER (BUILT)"

SECTION_44 = """
---

# SECTION 44 — GENERAL LEDGER (BUILT)

**The GL is the single source of truth for all money movement.**

## Tables

**`gl_transactions`** — parent. One row per financial event.
- id, organization_id, transaction_date, posted_at
- transaction_type (RECEIPT | BILL | JOURNAL_ENTRY | DEPOSIT | MGMT_FEE | OWNER_DRAW | TRANSFER | NSF | REVERSAL | REFUND_NEGATIVE_DIAGNOSTIC | OWNER_CONTRIBUTION)
- reference_number, memo, source_type, source_id
- created_by_id, is_reversed, reversal_of_id
- created_at, updated_at

**`gl_entries`** — children. One row per debit or credit line.
- id, organization_id, transaction_id, gl_account_id
- property_id (optional), unit_id (optional), description
- debit, credit (exactly one is > 0 per row)
- created_at

## The rule

**All writes go through `post_transaction()` in `app/services/gl_posting.py`.**

It enforces:
1. transaction_type is in the valid list
2. At least 2 lines
3. Each line: exactly one of debit/credit > 0
4. Sum(debit) == Sum(credit) within 0.01
5. All gl_account_ids belong to the org, are active
6. All property_ids belong to the org
7. All unit_ids belong to the given property
8. On failure: entire posting rolls back

**Never write to `gl_transactions` or `gl_entries` directly from anywhere else.**

## Reversal

Never edit or delete a posted transaction. To undo:
- Call `reverse_transaction(db, original=txn, reversal_date=..., created_by=...)`
- Creates a new transaction with every line flipped
- Marks original `is_reversed=True`
- Net effect: zero

## Endpoints (under `/api/accounting`)

| Method | Path | Purpose |
|---|---|---|
| GET | `/gl-transactions` | List transactions (filters: date, type, property, source) |
| GET | `/gl-transactions/{id}` | One transaction + all its lines |
| GET | `/gl-accounts/{id}/ledger` | Ledger for one account with running balance |
| GET | `/gl-accounts/{id}/balance` | Current balance for one account |
| GET | `/reports/trial-balance` | All accounts + debit/credit totals, balance check |

## Frontend pages

- `/dashboard/accounting/gl-accounts` — Chart of Accounts (account name links to ledger)
- `/dashboard/accounting/gl-accounts/{id}/ledger` — Ledger with running balance, filters
- `/dashboard/accounting/journal-entries/{id}` — Transaction viewer (both sides)
- `/dashboard/accounting/trial-balance` — Trial Balance report
- `/dashboard/accounting/diagnostics` — placeholder (real checks in Step 8)

## Balance computation

On demand: `SUM(debit) - SUM(credit)` per account. No cached column. Add one later if reports get slow at scale.

## Not yet built in the GL

- Public "create a transaction" endpoint (manual journal entry form) — Step 2b
- Recurring journal entries
- Post GPR automation
- Actual posting flows from Receipts/Bills/etc. — Steps 5, 6, 9
"""

# Remove the old trailing "# END OF PROJECT_MASTER.md" line if present,
# so we can re-add it after Section 44.
END_MARKER = "# END OF PROJECT_MASTER.md"
if END_MARKER in text:
    text = text.replace(END_MARKER, "").rstrip() + "\n"

if MARKER in text:
    print("Section 44 already present — skipping append.")
else:
    text = text.rstrip() + "\n" + SECTION_44 + "\n" + END_MARKER + "\n"
    print("Appended Section 44.")

PATH.write_text(text, encoding="utf-8")
print("Saved:", PATH)
print("File size (bytes):", PATH.stat().st_size)