─────────────────────────────────────────────────────────
AI_HANDOFF.md LOCATION RULE (READ FIRST)
─────────────────────────────────────────────────────────
This file lives at the REPO ROOT, not under docs/.
It is the single source of truth for resuming AI development.
Refresh it after every meaningful batch with exact verification
evidence, Git/migration state, and the next task. Do not ask
Yasir to reconstruct project context.
─────────────────────────────────────────────────────────

# RESUME HERE — 2026-09-26

Repository: yasirskhan/property-platform (private)
Only working branch: chatgpt/checkpoint-005-safety
Last VERIFIED source HEAD: cf6f9aa1a54d276200c310f3b3d8f870cad64e97
Always fetch current branch HEAD again; this handoff-only commit will
change the HEAD. Do not edit main, create/switch branches, force-push,
or merge draft PR #2 without approval.

CURRENT PHASE: 3.7 — Reports + Universal Attachments, IN PROGRESS.
LATEST COMPLETED BATCH: Custom Report Builder (saved configurations).
EXACT NEXT BATCH: Create Labels Report (mail merge via CSV).
The verified universal attachments, standard/enhanced report framework,
shared Print / Email / CSV report delivery, and saved configuration builder
must NOT be repeated. Phases 3.4.S and 3.4.3–3.4.26, compatibility pass
3.5.5, and Accounting Polish 3.6 are previously completed/verified.

# LAST VERIFIED CI AND SCHEMA

Verified source commit: cf6f9aa1a54d276200c310f3b3d8f870cad64e97
GitHub Actions run 36246789775 — SUCCESS; all six jobs:
  backend, frontend, platform-admin, security, e2e, staging-config.
Backend exact summary:
  383 passed, 3 deselected, 3149 warnings in 72.54s
E2E exact summary: 3 passed in 7.30s
Frontend lint, TypeScript and production build: SUCCESS.
Platform admin, security, staging-config: SUCCESS.
Backend CI includes PostgreSQL bootstrap and schema/registry/parity
checks. E2E includes the existing authenticated browser flow.
These counts describe THIS source HEAD only; never transfer them to
a subsequent code change. Handoff-only edit: TESTS NOT RUN.

Alembic head: b4e6a8c0d2f5
Expected SQLAlchemy model tables: 100.
Previous head: a3d5f7b9c1e4; previous model tables: 99.
Planning checklist was NOT edited; the last reported metadata remains
628 total / 264 built / 364 scheduled / 0 in progress.
Do NOT represent that metadata as updated for this batch.
Do not edit frozen source-of-truth docs under docs/ without Yasir's
explicit authorization. No docs/ files were changed in this batch.

# PHASE 3.7 VERIFIED WORK

- Universal Attachments: 90e54eb834047038f01959c5a2a20c9e4155e999;
  CI 36219990832 SUCCESS.
- Report framework: 3afb0d3d2b41a222225e5ca20fb9c976fee77742;
  CI 36221727596 SUCCESS.
- Shared Print / Email / CSV: f5c8a5177db003c5d6d1b2eb2fbf8510791d31d6;
  CI 36222255513 SUCCESS.
- Delivery docs closeout: fad5066aa2bc4498156179fad6bb5c8ad1cfcf65;
  CI 36222494517 SUCCESS.
- Prior handoff-only commit: 0d34982036e38bf6c9f5804da098da277a1ce5de;
  CI 36245454580 SUCCESS.
- Custom Report Builder backend / migration / focused regression tests:
  5f235e3bdc098885965c227a68956b69ea5f5307.
- Custom Report Builder customer UI:
  b70be63af5195fe88f7bcadf2d6599732d24ce59.
- Schema-guard test fixes:
  cf6f9aa1a54d276200c310f3b3d8f870cad64e97.
  Earlier CI 36246620511 FAILED only on two stale 99-table guards
  (381 passed / 2 failed / 3 deselected); both guards were corrected
  to head b4e6a8c0d2f5 / 100 tables and next CI 36246789775 passed.
  Original earlier run 36246560776 was cancelled after a newer push.

Custom builder shipped behavior:
  * organization + current-user-private persisted saved configurations;
    CRUD at /api/reporting/saved and /api/reporting/saved/{id}.
  * Only implemented canonical report keys can be saved: Chart of
    Accounts, Trial Balance, per-account General Ledger, Owner Statement.
  * Parameters validated against report-specific allowlists, date,
    integer and boolean rules; arbitrary SQL/report execution forbidden.
  * REPORTING.ALL and underlying report menu permission rechecked on
    save, read, update, delete; list filters inaccessible report keys.
  * Existing server-side CSV and email report delivery rechecks
    report permissions and release.reporting.export; no client-side
    data execution or change to GL.
  * Immutable audit logging for create/update/delete.
  * Saved configuration form plus edit/delete, existing ReportActions
    reuse on the customer Reporting page.
  * Focused tests cover scope, per-user privacy, invalid parameters,
    permissions, audit-compatible CRUD, and existing export access.
  * No generic report-field query language, shared presets, or arbitrary
    SQL builder was introduced. Only four already-implemented reports
    have executable saved presets; other reports stay on their roadmap.

Changed source files include:
  backend/app/models/saved_report.py
  backend/alembic/versions/b4e6a8c0d2f5_add_saved_reports.py
  backend/app/services/saved_reports.py
  backend/app/routers/reporting.py
  backend/app/schemas/reporting.py
  backend/init_db.py
  backend/tests/test_saved_reports.py
  backend/tests/test_migrations.py
  backend/tests/test_postgres_smoke.py
  backend/tests/test_prepare_database.py
  frontend/src/components/reporting/SavedReportBuilder.tsx
  frontend/src/app/dashboard/reporting/page.tsx
  frontend/src/lib/reporting.ts

# VERIFIED CONTRACTS TO PRESERVE

1. Hybrid Capability Gating keeps release, plan entitlement,
   organization config, role/menu permission and preference distinct;
   backend authoritative. No per-field feature flags for routine UI.
2. All accounting posts through central immutable GL; preserve org,
   owner, property isolation, locked periods, atomicity, immutable audit,
   and idempotency where required.
3. Customer and internal platform identity/JWT audiences remain separate.
4. Universal Notes and Attachments are shared org-scoped services;
   no duplicate parallel stores.
5. Reporting basis ACCRUAL default or CASH is a report-layer setting;
   do not alter GL postings.
6. Canonical report catalog: GET /api/reporting/catalog under REPORTING.ALL;
   existing Chart of Accounts, Trial Balance, per-account GL, frozen Owner
   Statement are the current deliverable keys. CSV/email server rerender,
   authorize each report plus release.reporting.export, escape CSV formulas,
   enforce org scope, and fail closed for unsupported keys.
7. Existing customer reporting page retains standard BUTTON vs enhanced
   TAB and catalog search/grouping; shared ReportActions stay intact.
8. Saved configurations are private to the creating user and organization;
   serving any saved preset rechecks current underlying permissions.
9. Never mistake planning parity check for behavioral test evidence.

# EXACT NEXT WORK

1. Read this entire root handoff; verify actual branch HEAD and latest CI.
   Read docs/PROJECT_MASTER.md Section 38 Phase 3.7 order and Section 82.
   Consult docs/FEATURE_REGISTRY.md, docs/PLAN_GAPS.md, parity JSON and
   docs/FILE_CATALOG.md READ-ONLY. Older master Part A/B1 has historic
   phase instructions; do not regress to older Phase 3.4/3.6 batches.
2. Implement Create Labels Report (mail merge via CSV) next, reusing
   canonical report infrastructure, org/record authorization, shared
   delivery and verified export gate. Inspect real tenant/owner/property
   models and routes before designing. Do not fabricate address records,
   expose other organizations, or duplicate existing delivery functions.
3. Add focused tests, then verify via hosted GitHub Actions. Yasir
   expressly authorized commit-then-GitHub-CI verification in this
   normal Chat session, replacing the former precommit-local-test
   requirement. Source commits are NOT verified until CI reports success.
   Fix CI reds autonomously; stop on the same assertion failing three
   consecutive times. Record exact counts, commit SHA, run ID,
   Alembic/table guards, and affected parity metadata.
4. After Create Labels, follow Section 38 in order: Generate 1099
   Forms & Reports; Letters; Send Owner Packets; tenant/property/
   owner/accounting/transaction reports. Inspect existing verified
   work before any batch. Continue phase boundaries unless true blocker.
5. Do not edit frozen docs/ source-of-truth files without explicit
   authorization. Update THIS root handoff after each meaningful
   batch, including honest partial status and test results. No Work
   mode request, no user code-writing tasks, no duplicate audits,
   no forced branch updates, no speculative success claims.

# NEXT SESSION START PROMPT

Continue yasirskhan/property-platform on
chatgpt/checkpoint-005-safety. Read root AI_HANDOFF.md fully and verify
current HEAD and GitHub CI. Last VERIFIED source is
cf6f9aa1a54d276200c310f3b3d8f870cad64e97; CI 36246789775
SUCCESS (383 passed, 3 deselected backend; 3 E2E passed).
Custom Report Builder saved configurations are VERIFIED; do not repeat.
Exact next Phase 3.7 task is Create Labels Report (mail merge via CSV).
Preserve verified contracts, do not touch main or frozen docs/, and
keep root AI_HANDOFF.md current after each meaningful batch.
