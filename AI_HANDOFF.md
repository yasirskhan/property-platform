─────────────────────────────────────────────────────────
AI_HANDOFF.md LOCATION RULE (READ FIRST)
─────────────────────────────────────────────────────────
This file lives at the REPO ROOT and is the single resume point.
Keep it here and overwrite it after every meaningful batch.
─────────────────────────────────────────────────────────

# Current Resume State

Branch: chatgpt/checkpoint-005-safety

Latest verified product commits:
- dc84db4602b2de4e04c93ac35dc6a4ff29525bad — backend ledger workflow
- 4d037b6608c07d142974c758e2aecee406f373d7 — customer workflow

Resolve the branch HEAD again before any write. This handoff file is committed
after the product batch, so it does not embed its own final hash.

IMPORTANT:
- Do NOT resume old Phase 3.4.x work.
- Phase 3.4.S and Phases 3.4.3 through 3.4.26 are COMPLETE/VERIFIED.
- Phase 3.5.5 compatibility pass is COMPLETE.
- Current work is Phase 3.6 — Accounting Polish, Bank Accounts subsection.

# Newly Verified Green Checkpoint

Parity bookkeeping repair commit:
- 863f0f98729c86de2f0ab7f5b3c6a8f7598b5e34
- "Docs: reconcile parity metadata"

Hosted CI:
- Run 36095431108: SUCCESS
- Backend: 290 passed, 3 deselected, 2039 warnings in 47.66s
- E2E: 3 passed in 11.84s
- Frontend: SUCCESS
- Platform admin: SUCCESS
- Security: SUCCESS
- Staging build/start/health: SUCCESS
- Parity/registry consistency: CLEAN
- Secret-pattern scan: CLEAN

Current parity source-of-truth counts:
- total_items: 628
- built_count: 235
- scheduled_count: 393
- in_progress_count: 0
- migration_head metadata: f2a4c6e8b0d5

Verified current migration state remains:
- Alembic head: f2a4c6e8b0d5
- Expected model-table count: 89

# Planning Metadata Note

docs/APPFOLIO_PARITY_CHECKLIST.json is repaired and CI-green.

docs/PROJECT_MASTER.md still contains stale top-level text:
- parity 238 built / 390 scheduled
- migration head c7d9e1f3a5b2

The connected GitHub write path refused the required full-file PROJECT_MASTER rewrite.
Do not change feature statuses to compensate. Reconcile only the stale PROJECT_MASTER
summary text when an edit path is available.

# Bank Adjustments Current State

Backend ledger workflow is now implemented:
- release gate: release.accounting.bank_adjustments
- permission: ACCOUNTING.BANK_ACCOUNTS
- durable entity: GLTransaction, no duplicate adjustment table or migration
- transaction_type = BANK_ADJUSTMENT
- source_type = "bank_adjustment"
- source_id = bank_account.id
- INCREASE: debit bank GL, credit selected offset GL
- DECREASE: debit selected offset GL, credit bank GL
- reversal uses reverse_transaction() and preserves immutable history
- listing is org + bank scoped
- reconciliation discovers the GL transaction automatically

Implemented by dc84db4602b2de4e04c93ac35dc6a4ff29525bad:
- backend/app/services/bank_adjustments.py
- backend/app/routers/bank_adjustments.py
- backend/tests/test_bank_adjustments.py
- backend/app/main.py
- backend/app/services/gl_posting.py
- existing backend/app/schemas/bank_adjustment.py is reused

Regression coverage added for:
- increase/decrease bank-side posting
- cross-organization offset rejection
- locked-period rejection
- immutable one-time reversal
- disabled customer feature rejection

Current verification state:
- Hosted CI for the backend batch is pending/being checked.
- TESTS NOT RUN locally in this connector-only session.

Frontend Bank Adjustments workflow is implemented by:
- 4d037b6608c07d142974c758e2aecee406f373d7
- "Phase 3.6 Bank Adjustments: add customer workflow"

Frontend files:
- frontend/src/lib/bankAdjustments.ts
- frontend/src/app/dashboard/accounting/bank-accounts/[id]/adjustments/page.tsx
- frontend/src/app/dashboard/accounting/bank-accounts/page.tsx

Bank Adjustments verification:
- Hosted CI run 36097448099: SUCCESS
- Backend: 295 passed, 3 deselected, 2121 warnings in 51.57s
- E2E: 3 passed in 13.46s
- Frontend: SUCCESS
- Platform admin: SUCCESS
- Security: SUCCESS
- Staging build/start/health: SUCCESS
- PostgreSQL bootstrap + backup/restore: SUCCESS
- Parity after closeout: 236 built / 392 scheduled / 628 total

Bank Adjustments is COMPLETE/VERIFIED.

Next product batch:
1. Bank Feed import (Phase 3.6).
2. Keep Phase 3.6 provider-neutral: durable/manual feed import and matching.
3. Do not pull live Plaid connectivity forward; that remains Phase 8.
4. Preserve release.accounting.bank_feed, bank_feeds entitlement,
   ACCOUNTING.BANK_ACCOUNTS permission, org isolation, and no implicit GL mutation.
5. Run hosted CI, fix reds autonomously, update planning docs and this handoff.

# Verified Foundation / Contracts to Preserve

Verified Phase 3.6 work includes:
- Chart of Accounts
- Journal Entries
- Receipts
- Charges
- Bills lifecycle
- Recurring Bills/Credits
- Post Codes
- Manually Post Bills
- Vendor Credits
- Write Checks / Checks
- Bank Deposits polish
- Bank Reconciliation
- QIF Import
- Check Setup
- ACH File Generation

Existing VERIFIED behavior is a contract.
Backend authorization is authoritative; UI hiding is never security.
Release control, entitlement, org configuration, role permission, and user preference
remain independent layers.
Every GL posting goes through the central posting service.
Never write financial GL state directly.
Customer/platform identity boundaries and organization isolation are permanent.
Never use Alembic autogenerate.

# Working Rules

- Work only on chatgpt/checkpoint-005-safety.
- Never touch main.
- Never create or switch branches.
- Inspect real source before editing.
- Fix CI reds autonomously.
- Keep AI_HANDOFF.md current after meaningful batches.
- Use real test counts only.
- If tests did not run, say TESTS NOT RUN.
- Do not stop at phase boundaries.
- Stop only for a true blocker that cannot be resolved.
