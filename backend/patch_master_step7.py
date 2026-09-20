"""
patch_master_step7.py
Targeted find-and-replace edits to PROJECT_MASTER.md for Step 7
(Bank Deposits) completion. Follows Section 48's pattern.

Adds:
  - Part A1: Step 7 complete, Step 8 is next
  - Part A2: Deposits added to "what's built"
  - Part A5: remove stale deposits bullet if any
  - Part B1: rewrite for Step 8 (Financial Diagnostics)
  - Part B2: mark Step 7 done, Step 8 next
  - Section 10: table count and list updated (add deposits, deposit_lines)
  - Section 11: add e266f7c76a7c to migration chain
  - Section 38: mark Step 7 done, Step 8 next
  - Section 48/49 unchanged
  - New Section 50 — BANK DEPOSITS (BUILT)
"""

from pathlib import Path

MASTER = Path(r"C:\Projects\property-platform\docs\PROJECT_MASTER.md")
text = MASTER.read_text(encoding="utf-8")

def replace_once(old: str, new: str, label: str) -> None:
    global text
    if old not in text:
        print(f"[skip] {label} — pattern not found")
        return
    text = text.replace(old, new, 1)
    print(f"[ok]   {label}")

# ------------------------------------------------------------
# A1: current activity
# ------------------------------------------------------------
replace_once(
    "**Current activity:** Phase 2 (Accounting). Steps 1, 2, 5, 6 COMPLETE. Next is Step 7 (Bank Deposits).",
    "**Current activity:** Phase 2 (Accounting). Steps 1, 2, 5, 6, 7 COMPLETE. Next is Step 8 (Financial Diagnostics).",
    "A1 current activity",
)

# ------------------------------------------------------------
# A1: last completed work — add a Step 7 line
# ------------------------------------------------------------
replace_once(
    """- Phase 2 Step 6 (Bills) — two-step accrual payables, multi-line,
  enter bill + pay bill + reverse, added GL account 2100
  Accounts Payable, list + new pages, centered detail modal,
  wired into ACCOUNTING.PAYABLES menu link (labelled "Bills")""",
    """- Phase 2 Step 6 (Bills) — two-step accrual payables, multi-line,
  enter bill + pay bill + reverse, added GL account 2100
  Accounts Payable, list + new pages, centered detail modal,
  wired into ACCOUNTING.PAYABLES menu link (labelled "Bills")
- Phase 2 Step 7 (Bank Deposits) — group un-deposited receipts
  into batches, tag receipts as deposited via deposit_lines,
  list + new pages with centered detail modal, new
  ACCOUNTING.DEPOSITS menu key added. Deposits do NOT post
  to the GL (receipts already credited cash).""",
    "A1 last completed work",
)

# ------------------------------------------------------------
# A1: NOT built yet — remove Step 7 mention
# ------------------------------------------------------------
replace_once(
    """- Phase 2 remaining: Universal Notes + Attachments (Step 3), Bank
  Accounts (Step 4), Bank Deposits (Step 7),
  Diagnostics (Step 8), Management Fees (Step 9),
  Owner Statements (Step 10), Manual Journal Entry form (Step 2b)""",
    """- Phase 2 remaining: Universal Notes + Attachments (Step 3), Bank
  Accounts (Step 4), Diagnostics (Step 8),
  Management Fees (Step 9), Owner Statements (Step 10),
  Manual Journal Entry form (Step 2b)""",
    "A1 not built yet",
)

# ------------------------------------------------------------
# A2: what's built — add Step 7
# ------------------------------------------------------------
replace_once(
    """- Phase 2 Step 6 — Bills (two-step accrual: enter + pay + reverse,
  2 tables, `post_bill()` + `pay_bill()` + `reverse_bill()`
  services, list + new pages, centered detail modal with inline pay form,
  GL account 2100 Accounts Payable seeded)""",
    """- Phase 2 Step 6 — Bills (two-step accrual: enter + pay + reverse,
  2 tables, `post_bill()` + `pay_bill()` + `reverse_bill()`
  services, list + new pages, centered detail modal with inline pay form,
  GL account 2100 Accounts Payable seeded)
- Phase 2 Step 7 — Bank Deposits (2 tables: deposits, deposit_lines;
  `create_deposit()` + `list_undeposited_receipts()` services;
  list + new pages with centered detail modal;
  deposit_lines is the single source of truth for "is this receipt
  deposited?" — no columns on receipts)""",
    "A2 what's built",
)

# ------------------------------------------------------------
# A5: replace the open decisions block
# ------------------------------------------------------------
replace_once(
    """## A5. CURRENT OPEN DECISIONS

- Auto-description rules for Receipt lines: currently rent rows get
  "{Month} rent", fee rows get "{Fee} — {tenant name}". Revisit
  later for finer control (owner-paid insurance, etc.).
- Bill auto-description: not yet built. Could add a similar rule
  later ("Plumbing — kitchen sink" from GL account + free text).
- Reverse confirmation still uses window.confirm(). Fine for now;
  upgrade to a styled modal when we do the polish pass.
- Back-navigation: Trial Balance has a smart-back button (browser
  history if present, else /dashboard). Roll this pattern out to
  other pages during the polish pass.
- Mobile: desktop-first for manager app; portals mobile-first
  (Phase 7); native app = Phase 12 (see Section 46).""",
    """## A5. CURRENT OPEN DECISIONS

- Auto-description rules for Receipt lines: currently rent rows get
  "{Month} rent", fee rows get "{Fee} — {tenant name}". Revisit
  later for finer control (owner-paid insurance, etc.).
- Bill auto-description: not yet built. Could add a similar rule
  later ("Plumbing — kitchen sink" from GL account + free text).
- Reverse confirmation still uses window.confirm(). Fine for now;
  upgrade to a styled modal when we do the polish pass.
- Back-navigation: Trial Balance and Deposits have a smart-back
  button (browser history if present, else /dashboard). Roll this
  out to Receipts/Bills/GL Accounts during the polish pass.
- Mobile: desktop-first for manager app; portals mobile-first
  (Phase 7); native app = Phase 12 (see Section 46).
- Bank Deposits do NOT post to the GL. If we later add a "cash on
  hand" GL account (undeposited funds), we'd add a DR Bank / CR
  Cash on Hand posting in create_deposit(). Documented in
  Section 50.""",
    "A5 open decisions",
)

# ------------------------------------------------------------
# B1: rewrite immediate next action for Step 8
# ------------------------------------------------------------
old_b1_marker = "## B1. IMMEDIATE NEXT ACTION"
idx = text.find(old_b1_marker)
if idx != -1:
    next_section = text.find("## B2.", idx)
    if next_section != -1:
        new_b1 = """## B1. IMMEDIATE NEXT ACTION

**Phase 2 Step 8: Financial Diagnostics.**

Six automatic checks that find bookkeeping problems in the
ledger. Each returns a pass/fail and, when failing, a list of
offending accounts/amounts. Some can be auto-fixed with a
"Refund Negative Diagnostic" posting.

The six checks (from Section 35):
  1. Security Deposit Funds Mismatch
  2. Escrow Cash Account Balance Mismatch
  3. Non-Zero Security Clearing Account Balances
  4. Negative Balance on Fee GL Accounts
  5. Positive Balance on Fee GL Accounts
  6. Trust Account 3-Way Reconciliation

Deliverable:
- No new tables needed (checks read existing GL data)
- Backend: `app/services/diagnostics.py` with one function per
  check, each returning {passed, severity, message, rows}
- Router: GET /api/accounting/diagnostics (returns all six)
- Router: POST /api/accounting/diagnostics/refund-negative
  (auto-posts a "Refund Negative Diagnostic" correction)
- Frontend: replace the placeholder
  /dashboard/accounting/diagnostics page with a real report

Roughly 2 sessions.

"""
        text = text[:idx] + new_b1 + text[next_section:]
        print("[ok]   B1 rewritten for Step 8")
    else:
        print("[skip] B1 — B2 marker not found")
else:
    print("[skip] B1 — section marker not found")

# ------------------------------------------------------------
# B2: mark Step 7 done, Step 8 next
# ------------------------------------------------------------
replace_once(
    """7. **Bank Deposits (Step 7) — NEXT**
8. Financial Diagnostics (Step 8)""",
    """7. DONE: Bank Deposits (Step 7)
8. **Financial Diagnostics (Step 8) — NEXT**""",
    "B2 step list",
)

# ------------------------------------------------------------
# Section 10: tables list — add deposits, deposit_lines
# ------------------------------------------------------------
replace_once(
    """Accounting: gl_accounts, gl_transactions, gl_entries, receipts,
  receipt_lines, bills, bill_lines""",
    """Accounting: gl_accounts, gl_transactions, gl_entries, receipts,
  receipt_lines, bills, bill_lines, deposits, deposit_lines""",
    "Section 10 table list",
)

# ------------------------------------------------------------
# Section 11: add e266f7c76a7c to migration chain
# ------------------------------------------------------------
replace_once(
    """- 71eda8a9ba77_add_bills_and_bill_lines_and_ap_account
- HEAD: 71eda8a9ba77""",
    """- 71eda8a9ba77_add_bills_and_bill_lines_and_ap_account
- e266f7c76a7c_add_deposits_and_deposit_lines
- HEAD: e266f7c76a7c""",
    "Section 11 migration chain",
)

# ------------------------------------------------------------
# Section 38: build order — mark Step 7 done
# ------------------------------------------------------------
replace_once(
    "  7. Bank Deposits <- NEXT",
    "  7. DONE Bank Deposits (batching, NSF)",
    "Section 38 step 7",
)
replace_once(
    "  8. Financial Diagnostics (6 checks)",
    "  8. Financial Diagnostics (6 checks) <- NEXT",
    "Section 38 step 8",
)

# ------------------------------------------------------------
# New Section 50 — BANK DEPOSITS (BUILT) — insert before EOF
# ------------------------------------------------------------
if "SECTION 50 — BANK DEPOSITS" not in text:
    new_section = """
---

# SECTION 50 — BANK DEPOSITS (BUILT — Phase 2 Step 7)

Group un-deposited receipts into a batch for the bank.

IMPORTANT: Deposits do NOT post to the GL. Receipts already
credit the cash GL account when they are posted. Deposits
simply tag receipts as deposited by inserting rows into
deposit_lines.

deposit_lines is the SINGLE SOURCE OF TRUTH for "is this
receipt deposited?". We do NOT store is_deposited on receipts.
This avoids SQLite batch_alter_table FK pain and stays
consistent on Postgres. Membership in a deposit IS the fact.

Tables:
- deposits — id, organization_id, bank_gl_account_id,
  deposit_date, deposit_number (auto D-00001 if blank),
  description, total, notes, is_active, created_by_id,
  timestamps
- deposit_lines — id, organization_id, deposit_id, receipt_id,
  created_at. UNIQUE index on receipt_id (a receipt can be in
  at most one deposit).

Migration: e266f7c76a7c_add_deposits_and_deposit_lines
(down_revision = 71eda8a9ba77). Also seeds the new
ACCOUNTING.DEPOSITS menu key for every existing org
(visible to ADMIN/OWNER/MANAGER; hidden from CREW/TENANT/
VENDOR/VENDOR_CREW/APPLICANT).

Menu key added to app/constants/menu_keys.py (MENU_KEYS
list) and to DEFAULT_MATRIX["MANAGER"]. ADMIN and OWNER see
it automatically because they use set(MENU_KEYS).

Services (app/services/deposit_posting.py):
- create_deposit() — validates receipts (exist, same org,
  not reversed, not already deposited), computes total from
  receipts, saves deposit + deposit_lines, auto-numbers as
  D-NNNNN if blank. Raises PostingError on any issue.
- list_undeposited_receipts() — returns receipts not in any
  deposit_lines row. Optional bank_gl_account_id filter.

No GL posting. Reverse not supported — corrections via
journal entry (Section 19). If we later model "cash on hand"
as a separate GL account, a DR Bank / CR Cash on Hand posting
would be added inside create_deposit().

Endpoints under /api/accounting/deposits:
- GET  ""                          list (date/bank filters)
- GET  /undeposited-receipts       picker (optional bank filter)
- GET  /{deposit_id}               detail + receipts
- POST ""                          create deposit

Note: the /undeposited-receipts route MUST be defined before
/{deposit_id} or FastAPI will try to parse the string as int.

Frontend pages:
- /dashboard/accounting/deposits        list + centered detail modal
- /dashboard/accounting/deposits/new    picker with All/None

Menu: ACCOUNTING.DEPOSITS -> Bank Deposits
(href /dashboard/accounting/deposits).

"""
    eof = "# END OF PROJECT_MASTER.md"
    text = text.replace(
        eof, new_section + eof, 1
    )
    print("[ok]   Section 50 added")

MASTER.write_text(text, encoding="utf-8")
print()
print(f"Wrote {len(text):,} bytes to {MASTER}")