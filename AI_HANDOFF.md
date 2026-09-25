─────────────────────────────────────────────────────────
AI_HANDOFF.md LOCATION RULE (READ FIRST)
─────────────────────────────────────────────────────────
This file lives at the REPO ROOT.

Not in docs/.
Not in backend/.
Not in frontend/.

Every future ChatGPT session that works on this repo MUST keep
this file at the repo root and MUST overwrite it (not append)
after every BATCH DONE.

Why: this file is the single resume point between sessions.
If it moves, the next session will not find it.

The source-of-truth planning files live under docs/. Update them
when roadmap/capability state actually changes and keep registry /
parity consistency checks green.
─────────────────────────────────────────────────────────

# Current Resume State

Branch: chatgpt/checkpoint-005-safety

Handoff prepared from parent HEAD:
- 41d771ad3d4c262c57a53f4bda1391ede722bc34
- "Phase 3.6: close out ACH file generation"

Resolve the branch HEAD again before any write. This handoff file is
committed as part of HEAD, so it does not embed its own final commit hash.

IMPORTANT:
- Do NOT resume from Phase 3.4.9. The repository has already advanced far beyond it.
- Phase 3.4.S and Phases 3.4.3 through 3.4.26 are COMPLETE/VERIFIED.
- Phase 3.5.5 compatibility pass is COMPLETE.
- Current work is Phase 3.6 — Accounting Polish, Bank Accounts subsection.

# Last Fully Green Checkpoint

ACH File Generation implementation commit:
- c0b63283f410edeb5f7761d0666ce781a8518a13

Verified CI:
- Run 36091648909: SUCCESS
- Backend: 290 passed, 3 deselected, 2039 warnings in 51.71s
- E2E: 3 passed in 11.18s
- Frontend: SUCCESS
- Platform admin: SUCCESS
- Security: SUCCESS
- Staging build/start/health: SUCCESS

Verified ACH behavior:
- Org-scoped transient CSV/NACHA credit-file generation.
- ABA routing validation.
- NACHA company identity required where applicable.
- No payment creation and no GL/accounting-state mutation.
- Customer-visible ACH workflow exists.
- Preserve this as VERIFIED behavior.

# Current HEAD / Known CI Red

Current source parent before this handoff commit:
- 41d771ad3d4c262c57a53f4bda1391ede722bc34

CI run 36093311424: FAILURE.

The failure is bookkeeping only:
- backend job failed at "Run parity/registry consistency"
- backend tests were skipped after that gate
- E2E and staging were skipped
- frontend, platform-admin, and security all succeeded

Exact parity output at current source:
- total items: 628
- actual built: 235
- actual scheduled: 393
- in progress: 0

Exact consistency errors:
- docs/APPFOLIO_PARITY_CHECKLIST.json _meta.built_count=234, actual=235
- docs/APPFOLIO_PARITY_CHECKLIST.json _meta.scheduled_count=394, actual=393

Also stale in planning metadata:
- PROJECT_MASTER currently states parity 238 built / 390 scheduled; actual checklist status count is 235 / 393.
- PROJECT_MASTER A1 currently states migration head c7d9e1f3a5b2; this is stale.
- APPFOLIO_PARITY_CHECKLIST.json _meta.migration_head also still says c7d9e1f3a5b2.

Verified current migration state from the real migration chain and current test guards:
- Alembic head: f2a4c6e8b0d5
- Expected model-table count: 89
- Chain tail: c7d9e1f3a5b2 -> d8e0f2a4b6c3 -> f2a4c6e8b0d5
- test_migrations.py, test_postgres_smoke.py, and test_prepare_database.py all currently guard f2a4c6e8b0d5 / 89.

# Exact Next Action

FIRST, repair the known documentation/parity bookkeeping red before product work:
1. Re-read this file completely and inspect the current branch HEAD.
2. Re-run/inspect check_parity.py logic and the current checklist before editing.
3. Reconcile docs/APPFOLIO_PARITY_CHECKLIST.json _meta to the actual current item statuses:
   - built_count 235
   - scheduled_count 393
   - in_progress_count 0
   - total_items 628
   - migration_head f2a4c6e8b0d5
4. Reconcile PROJECT_MASTER current-state parity and migration-head text to the same verified values where stale.
5. Do not change feature item statuses merely to make the counts match. The item statuses are the source counted by check_parity.py.
6. Commit that bookkeeping fix as one coherent docs/test-gate repair and let hosted CI verify it. Fix any CI red autonomously.

THEN continue Phase 3.6 Bank Accounts without waiting for user approval:

Bank Adjustments is the next product batch.
- Capability/release boundary: release.accounting.bank_adjustments
- Permission: ACCOUNTING.BANK_ACCOUNTS
- Keep organization scope authoritative.
- Use the central GL posting service for every financial posting.
- Preserve locked-period enforcement, immutable GL behavior, and reversal contracts.
- Inspect existing bank-account, GL, reconciliation, checks, deposits, and capability-gating source before implementation.
- Add the customer-visible Bank Adjustments sub-tab/workflow plus regression coverage.
- Build it as one coherent batch, not tiny one-file commits.
- Verify hosted CI and fix reds autonomously.
- Update AI_HANDOFF.md and all roadmap/parity/catalog state required by the original plan.
- After Bank Adjustments is green, continue directly to Bank Feed import.

Documented Bank Accounts order from PROJECT_MASTER B1:
1. ACH File Generation — COMPLETE/VERIFIED
2. Bank Adjustments — NEXT
3. Bank Feed import — AFTER Bank Adjustments

# Verified Foundation / Contracts to Preserve

- Phase 3.4.S and 3.4.3 through 3.4.26: COMPLETE/VERIFIED.
- Phase 3.5.5 compatibility pass: COMPLETE.
- Phase 3.6 verified work includes:
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
- Existing VERIFIED behavior is a contract. Do not rebuild or redesign it unless a test proves it broken, a compatible refactor is required, or the user explicitly asks.
- Backend authorization is authoritative; UI hiding is never security.
- Release control, plan entitlement, org configuration, role permission, and user preference remain independent concerns.
- Not every capability needs every access layer.
- Routine field/column/filter changes do not automatically get feature flags.
- Every GL posting goes through the central posting service; never write financial GL state directly.
- Customer/platform identity boundaries and organization isolation are permanent security contracts.
- Never use Alembic autogenerate; migrations are hand-written.

# Working Rules

- Work only on branch chatgpt/checkpoint-005-safety.
- Never touch main.
- Never create or switch branches.
- Read AI_HANDOFF.md completely before every batch.
- Read PROJECT_MASTER.md, FEATURE_REGISTRY.md, APPFOLIO_PARITY_CHECKLIST.json, PLAN_GAPS.md as needed.
- Use FILE_CATALOG.md to locate existing code.
- Inspect real source before changing anything.
- Follow the original plan and revised roadmap ordering.
- One coherent batch per implementation commit, with safe checkpoints.
- Run applicable tests through the available execution path.
- Fix CI reds yourself. Do not wait for the user.
- Keep AI_HANDOFF.md fully current after every meaningful batch.
- Update PROJECT_MASTER / FEATURE_REGISTRY / APPFOLIO_PARITY_CHECKLIST / FILE_CATALOG when roadmap, capability, parity, migration, or file inventory state actually changes.
- Record real test counts only.
- Do not write "0 tests pass." If tests do not run, state TESTS NOT RUN.
- The user has authorized continuing through phase boundaries. Do NOT wait for "go" between phases.
- Stop only for a true blocker that cannot be resolved, or when context is running out and a new handoff is required.

# Open Blockers

No product blocker.

Known immediate CI blocker:
- parity/checklist metadata mismatch described above.
- This is a documentation/test-gate repair, not a product-code defect.

# Resume Prompt for the Next Session

Read AI_HANDOFF.md at the repo root completely before doing anything.
Work only on branch chatgpt/checkpoint-005-safety and resolve the current
HEAD before writes. Do not touch main or create/switch branches.

The repo is already in Phase 3.6 Accounting Polish. Do not resume old
Phase 3.4.x work. First repair the known parity bookkeeping CI red:
current actual checklist counts are 235 built / 393 scheduled / 0 in
progress / 628 total, while _meta is stale at 234 / 394. Also reconcile
the stale migration metadata to the verified current Alembic head
f2a4c6e8b0d5 with expected model-table count 89. Verify hosted CI and
fix reds autonomously.

After green, continue the exact next product batch: Phase 3.6 Bank
Accounts — Bank Adjustments, then Bank Feed import. Preserve all VERIFIED
accounting, isolation, gating, and immutability contracts. Keep
AI_HANDOFF.md current after every batch and continue through phase
boundaries without waiting for user approval.
