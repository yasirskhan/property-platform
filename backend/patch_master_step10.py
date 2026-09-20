"""Patch PROJECT_MASTER.md for Phase 2 Step 10 (Owner Statements)."""
from pathlib import Path

MASTER = Path(r"C:\Projects\property-platform\docs\PROJECT_MASTER.md")
text = MASTER.read_text(encoding="utf-8")

def replace_once(old, new, label):
    global text
    if old not in text:
        print(f"[skip] {label}")
        return
    text = text.replace(old, new, 1)
    print(f"[ok]   {label}")

replace_once(
    "**Current activity:** Phase 2 (Accounting). Steps 1, 2, 5, 6, 7, 8, 9 COMPLETE. Next is Step 10 (Owner Statements).",
    "**Current activity:** Phase 2 (Accounting). Steps 1, 2, 5, 6, 7, 8, 9, 10 COMPLETE. Next is Step 4 (Bank Accounts) then Step 2b (Manual Journal Entry).",
    "A1 current activity",
)

replace_once(
    """- Phase 2 Step 9 (Management Fees) — AppFolio-parity two-step
  flow: Run creates a Bill (DR 6001 Management Fees / CR 2100
  Accounts Payable), the manager pays the Bill separately
  (existing Bills flow → DR 2100 AP / CR 1150 Rental Trust).
  Two-tier rate (9% rent + 100% other eligible income).
  Respects subject_to_mgmt_fees, exclude_from_mgmt_fee,
  mgmt_fee_end_date, and mgmt_fee_flat/min overrides.
  new management_fee_runs table; ACCOUNTING.MANAGEMENT_FEES
  menu key.""",
    """- Phase 2 Step 9 (Management Fees) — AppFolio-parity two-step
  flow: Run creates a Bill (DR 6001 Management Fees / CR 2100
  Accounts Payable), the manager pays the Bill separately
  (existing Bills flow → DR 2100 AP / CR 1150 Rental Trust).
  Two-tier rate (9% rent + 100% other eligible income).
  Respects subject_to_mgmt_fees, exclude_from_mgmt_fee,
  mgmt_fee_end_date, and mgmt_fee_flat/min overrides.
  new management_fee_runs table; ACCOUNTING.MANAGEMENT_FEES
  menu key.
- Phase 2 Step 10 (Owner Statements) — frozen snapshot per
  owner per period. One section per property (AppFolio default;
  no consolidated view). Per-property beginning cash, running
  balance per transaction, ending cash. Global print CSS hides
  sidebar/top bar so Print gives a clean statement. New
  owner_statements table; ACCOUNTING.OWNER_STATEMENTS menu key.""",
    "A1 last completed",
)

replace_once(
    """- Phase 2 remaining: Universal Notes + Attachments (Step 3),
  Bank Accounts (Step 4), Owner Statements (Step 10),
  Manual Journal Entry form (Step 2b)""",
    """- Phase 2 remaining: Universal Notes + Attachments (Step 3),
  Bank Accounts (Step 4), Manual Journal Entry form (Step 2b)""",
    "A1 not built yet",
)

replace_once(
    "- Phase 2 Step 9 — Management Fees (AppFolio-parity two-step:\n  Run creates a Bill (DR Expense / CR AP), pay the Bill\n  separately (DR AP / CR Trust); two-tier rate 9% rent +\n  100% other; property-level config + overrides; new\n  management_fee_runs table; ACCOUNTING.MANAGEMENT_FEES menu key)",
    """- Phase 2 Step 9 — Management Fees (AppFolio-parity two-step:
  Run creates a Bill (DR Expense / CR AP), pay the Bill
  separately (DR AP / CR Trust); two-tier rate 9% rent +
  100% other; property-level config + overrides; new
  management_fee_runs table; ACCOUNTING.MANAGEMENT_FEES menu key)
- Phase 2 Step 10 — Owner Statements (frozen snapshot model;
  one block per property; running balance per transaction;
  global print CSS; new owner_statements table;
  ACCOUNTING.OWNER_STATEMENTS menu key)""",
    "A2 what's built",
)

# B1 — replace with Step 4
old_b1_marker = "## B1. IMMEDIATE NEXT ACTION"
idx = text.find(old_b1_marker)
if idx != -1:
    next_section = text.find("## B2.", idx)
    if next_section != -1:
        new_b1 = """## B1. IMMEDIATE NEXT ACTION

**Phase 2 Step 4: Bank Accounts.**

Model the two physical trust accounts (Client Trust / Operating
and Security Deposit Trust / Escrow) that map to GL 1150 and
1160. Track bank name, routing #, account #, and (later) ACH
format.

Deliverable:
- `bank_accounts` table (id, organization_id, name,
  bank_name, routing_number, account_number, gl_account_id,
  account_type (OPERATING | ESCROW), ach_format (CSV | NACHA),
  is_active, timestamps)
- Migration: seed the two standard accounts (Client Trust ↔ 1150,
  Security Deposit Trust ↔ 1160) for every existing org
- Backend: model + schema + router
- Frontend: Bank Accounts list + edit pages
- Wire into ACCOUNTING.BANK_ACCOUNTS menu link

Design notes (from Section 13, Section 33):
- Routing # and Account # are sensitive → mark in UI, but
  store plaintext for now (dev). Encrypt at rest in Phase 11.
- ACH setup fields (File Format, Header Options) come with
  the Bank Reconciliation step later; leave columns nullable.
- Link to GL account is required and unique per (org, gl).

Roughly 1 session.

## B1b. AFTER BANK ACCOUNTS

**Phase 2 Step 2b: Manual Journal Entry form.**

The public "create a transaction" endpoint we deferred from
Step 2. Manager picks a date, memo, and at least two lines
(account, debit OR credit, property/unit optional). Must
balance. POST /api/accounting/journal-entries.

Frontend: /dashboard/accounting/journal-entries/new

Roughly 1 session.

That closes Phase 2. Then Phase 3 (Property Detail placeholders).

"""
        text = text[:idx] + new_b1 + text[next_section:]
        print("[ok]   B1 rewritten for Step 4 + 2b")
    else:
        print("[skip] B1 — B2 marker not found")
else:
    print("[skip] B1 — section marker not found")

replace_once(
    """9. DONE: Management Fees (Step 9)
10. **Owner Statements (Step 10) — NEXT**""",
    """9. DONE: Management Fees (Step 9)
10. DONE: Owner Statements (Step 10)
4. Bank Accounts (Step 4) — NEXT
11. Manual Journal Entry form (Step 2b) — after Step 4""",
    "B2 step list",
)

replace_once(
    "Fees: management_fee_runs (one row per property per fee period)",
    """Fees: management_fee_runs (one row per property per fee period)
Statements: owner_statements (frozen snapshot documents)""",
    "Section 10 table list",
)

replace_once(
    """- 0cf6edacce77_add_management_fee_runs_and_property_fee_fields
- HEAD: 0cf6edacce77""",
    """- 0cf6edacce77_add_management_fee_runs_and_property_fee_fields
- 4aa1c77e213c_add_owner_statements
- HEAD: 4aa1c77e213c""",
    "Section 11 migration chain",
)

replace_once(
    " 10. Owner Statements <- NEXT",
    " 10. DONE Owner Statements",
    "Section 38 step 10",
)
replace_once(
    "  4. Bank Accounts (Operating + Escrow)",
    "  4. Bank Accounts (Operating + Escrow) <- NEXT",
    "Section 38 step 4",
)

if "SECTION 54 — OWNER STATEMENTS" not in text:
    new_section = """
---

# SECTION 54 — OWNER STATEMENTS (BUILT — Phase 2 Step 10)

Frozen snapshot model — matches AppFolio.

Flow:
  1. Pick owner + period -> Preview (read-only)
  2. Generate -> freezes a snapshot row in owner_statements
  3. View / Print -> clean print layout (sidebar hidden via
     global print CSS)
  4. Owner receives PDF

Snapshot semantics:
  * Once generated, the statement NEVER changes — even if GL
    is corrected later. This is the AppFolio behavior and the
    correct accounting practice.
  * To "regenerate," create a new statement with a new ID.

Structure:
  * One section per property the owner has a stake in
    (Property.owner_id + property_owners join table)
  * Per property: Beginning Cash, per-transaction running
    balance, Ending Cash, Income, Expense, Net
  * Top summary: Total Beginning Cash / Income / Expense /
    Ending Cash across all properties

Where numbers come from:
  * Beginning Cash = sum of (debit - credit) on 11xx ASSET
    accounts for that property BEFORE period_start
  * Transactions = every GL transaction in the period that
    touches that property, with its cash movement and
    income/expense movement per row
  * Running balance starts at Beginning Cash and accumulates
    cash movement row by row
  * Ending Cash = Beginning Cash + sum of cash movement in
    period

Table: owner_statements
- id, organization_id, owner_id
- period_start, period_end, generated_at
- total_beginning_cash, total_ending_cash
- total_income, total_expense, total_net
- property_data (JSON snapshot of the per-property breakdown
  and full transaction list)
- pdf_url (nullable), notes
- is_active, generated_by_id, timestamps

Migration: 4aa1c77e213c_add_owner_statements
(down_revision = 0cf6edacce77). Also seeds
ACCOUNTING.OWNER_STATEMENTS menu key.

Service: app/services/owner_statements.py
- preview_owner_statement()    -> read-only calculation
- generate_owner_statement()   -> freezes snapshot
- helpers: _properties_for_owner(), _cash_account_ids(),
  _cash_activity_for_property(), _transactions_for_property()

Endpoints under /api/accounting/owner-statements:
- POST /preview             compute (no save)
- POST /generate            freeze & save
- GET  ""                   list
- GET  /{statement_id}      detail (expanded)

Frontend:
- /dashboard/accounting/owner-statements        list
- /dashboard/accounting/owner-statements/new    preview + generate
- /dashboard/accounting/owner-statements/{id}   detail/print

Print CSS:
- src/app/globals.css @media print block hides aside/nav/
  header/footer so Print gives a clean statement.
- Print/Save as PDF button calls window.print().

Menu: ACCOUNTING.OWNER_STATEMENTS -> Owner Statements
(href /dashboard/accounting/owner-statements).

"""
    eof = "# END OF PROJECT_MASTER.md"
    text = text.replace(eof, new_section + eof, 1)
    print("[ok]   Section 54 added")

MASTER.write_text(text, encoding="utf-8")
print()
print(f"Wrote {len(text):,} bytes to {MASTER}")