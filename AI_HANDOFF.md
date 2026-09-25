─────────────────────────────────────────────────────────
AI_HANDOFF.md LOCATION RULE (READ FIRST)
─────────────────────────────────────────────────────────
This file lives at the REPO ROOT and is the single resume point.
Keep it here and overwrite it after every meaningful batch.
─────────────────────────────────────────────────────────

# Current Resume State

Branch: chatgpt/checkpoint-005-safety

Current HEAD:
- 000005157c8f1754ba92855b5f0ae51671a7f0f6
- "Phase 3.6 Bank Adjustments: add schemas"

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

Next product batch remains Bank Adjustments:
- release gate: release.accounting.bank_adjustments
- permission: ACCOUNTING.BANK_ACCOUNTS
- then continue directly to Bank Feed import

Source inspection is complete. Existing contracts to reuse:
- bank account organization scope and ACCOUNTING.BANK_ACCOUNTS authorization
- customer feature resolver for release/entitlement/org-config/permission composition
- central post_transaction() for all GL writes
- reverse_transaction() for immutable reversals
- locked-period enforcement in post_transaction()
- GL account posting restrictions in post_transaction()
- reconciliation already discovers qualifying GL transactions that touch the bank GL account

Chosen implementation design:
- Use GLTransaction itself as the durable adjustment entity.
- Do NOT add a duplicate bank-adjustments table or migration.
- Add BANK_ADJUSTMENT to VALID_TRANSACTION_TYPES.
- source_type = "bank_adjustment"
- source_id = bank_account.id
- INCREASE: debit bank GL, credit selected offset GL.
- DECREASE: debit selected offset GL, credit bank GL.
- Reversal must use reverse_transaction().
- Listing filters org + BANK_ADJUSTMENT + source_type/source_id.
- This automatically makes adjustments visible to reconciliation without synchronization state.

Intended files:
- backend/app/schemas/bank_adjustment.py
- backend/app/services/bank_adjustments.py
- backend/app/routers/bank_adjustments.py
- backend/tests/test_bank_adjustments.py
- backend/app/main.py
- backend/app/services/gl_posting.py
- frontend/src/lib/bankAdjustments.ts
- frontend/src/app/dashboard/accounting/bank-accounts/[id]/adjustments/page.tsx
- frontend/src/app/dashboard/accounting/bank-accounts/page.tsx

Partial implementation currently present:
- backend/app/schemas/bank_adjustment.py ONLY
- added by commit 000005157c8f1754ba92855b5f0ae51671a7f0f6

No Bank Adjustments service, router, UI, tests, migration, or GL transaction-type
change has been committed.

# Current True Blocker

The connected GitHub safety layer rejected the bookkeeping service write that calls
the existing GL posting/reversal services. A second attempt explicitly documenting
that the code is internal bookkeeping only and does not move external funds was also
rejected. The same layer also rejected deleting the schema-only partial file.

Do not disguise or bypass that safety control.

When an edit path that permits the legitimate internal-accounting code is available:
1. Re-read this file and resolve current branch HEAD.
2. Continue Bank Adjustments from the schema-only partial state, or remove that file
   first if replacing the design.
3. Implement the ledger-native design above.
4. Add regression coverage for increase/decrease, org-scoped offset validation,
   locked-period rejection, and reversal immutability.
5. Add the customer-visible per-bank Adjustments workflow.
6. Run hosted CI and fix reds autonomously.
7. After green, update FEATURE_REGISTRY, APPFOLIO parity, FILE_CATALOG,
   PROJECT_MASTER where possible, and this handoff.
8. Continue directly to Bank Feed import.

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
