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
Last VERIFIED source HEAD: 5a2ee8acc5ea9dc81b4a48ec6d043879b6a7b5df
Always fetch current branch HEAD again; this handoff-only commit will
change the HEAD. Do not edit main, create/switch branches, force-push,
or merge draft PR #2 without approval.

CURRENT PHASE: 3.7 — Reports + Universal Attachments, IN PROGRESS.
LATEST COMPLETED BATCH: Create Labels Report (CSV mail merge).
EXACT NEXT BATCH: Generate 1099 Forms & Reports (see tax prerequisites).
The verified universal attachments, standard/enhanced report framework,
shared Print / Email / CSV delivery, saved configurations, and labels report
must NOT be repeated. Phases 3.4.S and 3.4.3–3.4.26, compatibility pass
3.5.5, and Accounting Polish 3.6 are previously completed/verified.

# LAST VERIFIED CI AND SCHEMA

Verified source commit: 5a2ee8acc5ea9dc81b4a48ec6d043879b6a7b5df
GitHub Actions run 36248197021 — SUCCESS; all six jobs:
  backend, frontend, platform-admin, security, e2e, staging-config.
Backend exact summary:
  389 passed, 3 deselected, 3334 warnings in 70.34s
E2E exact summary: 3 passed in 8.23s
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


# CREATE LABELS REPORT — VERIFIED 2026-09-26

Source implementation: 02641ebab30e24880b5ab61194f20ad8f0aea2cc.
Follow-up lint correction: 5a2ee8acc5ea9dc81b4a48ec6d043879b6a7b5df.
First source CI 36248146232 exposed one new JSX apostrophe lint error;
that was fixed in the follow-up source commit.
Final CI 36248197021: SUCCESS (six jobs), backend 389 passed,
3 deselected, 3334 warnings in 70.34s; E2E 3 passed in 8.23s;
frontend, platform-admin, security and staging-config SUCCESS.
Six new focused label-report backend tests were added.
No migration; Alembic b4e6a8c0d2f5 / 100 model tables unchanged.
Frozen docs/ files were not modified, and planning parity metadata
was not advanced. Earlier docs-only run 36247104460 passed on
attempt 2 after a transient platform-admin E2E login timeout.

Source changed (labels batch):
- backend/app/services/label_report.py
- backend/app/services/report_delivery.py (opt-in actor-scoped label dispatch)
- backend/app/services/report_catalog.py (canonical standard report link)
- backend/app/routers/reporting.py (authorized live labels preview)
- backend/tests/test_label_report.py
- frontend/src/app/dashboard/reporting/labels/page.tsx

Behavior:
- Standard Reports > Mailings > Create Labels Report.
- Print preview; server-generated mail-merge CSV; shared ReportActions
  and email delivery; property and active-tenant recipient modes.
- Tenant labels use the recorded property address plus unit identifier,
  not a fictitious independent tenant mailing address. Owner/vendor
  contact address labels are NOT fabricated; user records do not
  currently store mailing addresses.
- REPORTING.ALL, PROPERTIES.ALL, release.reporting.export enforced
  on preview, CSV and email. Tenant recipient mode additionally
  requires LEASING. Only ADMIN/OWNER/MANAGER staff are allowed;
  managers see only their active property assignments.
- Cross-org and unassigned property ID probes fail closed. Only active
  properties, units, tenants and active leases contribute records.
- CSV uses the verified formula-escaping report_csv_bytes path.
- No new settings/entitlements, GL change, table, or parallel report
  delivery service. Saved Report Builder is unchanged.

# NEXT BATCH REQUIRES TAX-SPECIFICATION RESOLUTION

The ORIGINAL Section 38 next item is Generate 1099 Forms & Reports
(FIRE file + print). Do not silently skip this item or mark it complete.

Critical dated IRS change: IRS Publication 1099 (2026) states that
for tax year 2026 / filing season 2027, IRIS is the only information-
return intake, and FIRE shuts down at the end of 2026. Current IRS
reference: https://www.irs.gov/publications/p1099
IRIS reference: https://www.irs.gov/filing/e-file-information-returns-with-iris

Project docs/PLAN_GAPS.md §C9 already plans provider-based Track1099
or equivalent and W-9 collection in Phase 4.5, whereas original
docs/PROJECT_MASTER.md Section 38 says FIRE-file output in Phase 3.7.
This dependency/regulatory mismatch has NOT been resolved. Frozen
docs/ MUST NOT be changed without Yasir's explicit authorization.

Current customer User/Organization models do not have complete
payer/recipient TINs, W-9 records or independent mailing-address data.
Vendor and owner filing classifications must be validated, not inferred
from ordinary GL or owner-payout totals. Do NOT generate or transmit
purportedly IRS-valid 1099/FIRE files, store tax IDs in plaintext,
invent addresses, or alter posted accounting to fill missing data.
A secure tax-profile/W-9 collection and supported IRIS/provider
filing route is a prerequisite for completed real forms.

Decision needed before full filing implementation: authorize a safe
IRS-current IRIS/provider route and secure W-9 / tax-profile dependency
in place of the obsolete FIRE output, without editing frozen docs/.
This is a real tax/security dependency, not a completed 1099 batch.

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

1. Read this root handoff fully; verify current branch HEAD and CI.
   Read-only consult docs/PROJECT_MASTER.md Section 38 and Section 82,
   docs/PLAN_GAPS.md C9, FEATURE_REGISTRY, parity and FILE_CATALOG.
   Do not regress to completed phases or modify frozen docs/.
2. Next original roadmap batch: Generate 1099 Forms & Reports.
   Resolve the recorded FIRE-to-IRIS 2026 change and the absent secure
   payer/recipient tax profiles / W-9 dependency FIRST. Do not silently
   output an obsolete FIRE file, invent TINs, or infer taxable
   compensation from unrelated property/accounting transactions.
   If the security/tax specification cannot be resolved under the
   frozen roadmap, report the concrete decision needed. Keep 1099
   IN PROGRESS / NOT VERIFIED rather than misrepresenting delivery.
3. User explicitly authorized bounded commit-then-GitHub-CI verification
   in normal Chat. Include focused tests in every product-code batch,
   and mark VERIFIED only after relevant CI jobs pass. Fix CI failures,
   stop if same assertion fails three consecutive times, and record
   exact commit SHA, run IDs, counts and migration inventory.
4. After a correctly implemented and verified 1099 batch, Section 38
   orders Letters, then Send Owner Packets, then tenant/property/
   owner/accounting/transaction reports. Do not skip original tasks.
5. Update THIS repo-root handoff after each meaningful batch. Do not
   edit frozen docs/ source-of-truth without explicit authorization;
   no main edits/branch creation/force pushes, no Work mode request.

# NEXT SESSION START PROMPT

Continue yasirskhan/property-platform on branch
chatgpt/checkpoint-005-safety. Read entire repo-root AI_HANDOFF.md
before coding, then verify actual HEAD and GitHub Actions.
Last VERIFIED source: 5a2ee8acc5ea9dc81b4a48ec6d043879b6a7b5df;
CI 36248197021 SUCCESS (389 backend passed, 3 deselected;
3 E2E passed; all six jobs success). Labels Report and CSV mail
merge are VERIFIED. Alembic b4e6a8c0d2f5; 100 model tables.
Exact next original task: Generate 1099 Forms & Reports. IMPORTANT
read the IRIS/FIRE tax-year-2026 change and missing tax-profile/W-9
dependency above; do not fabricate tax identifiers or tax returns,
and do not edit frozen docs/ without explicit authorization.
Preserve verified architecture, no main changes, update root handoff
after every meaningful, CI-verified product batch.
