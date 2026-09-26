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
Last VERIFIED source HEAD: 3aca0f64b1f58e8bb7afef32ae6ceda368dbc9ca
Always fetch current branch HEAD again; this handoff-only commit will
change the HEAD. Do not edit main, create/switch branches, force-push,
or merge draft PR #2 without approval.

CURRENT PHASE: 3.7 — Reports + Universal Attachments, IN PROGRESS.
LATEST COMPLETED BATCH: Encrypted 1099 tax-profile foundation and IRIS roadmap update.
EXACT NEXT BATCH: 1099 preparation UI and secure signed W-9 intake/provider handoff.
Original Generate 1099 Forms & Reports remains IN PROGRESS, not VERIFIED.
The verified universal attachments, standard/enhanced report framework,
shared Print / Email / CSV delivery, saved configurations, and labels report
must NOT be repeated. Phases 3.4.S and 3.4.3–3.4.26, compatibility pass
3.5.5, and Accounting Polish 3.6 are previously completed/verified.

# LAST VERIFIED CI AND SCHEMA

Verified source commit: 3aca0f64b1f58e8bb7afef32ae6ceda368dbc9ca
GitHub Actions run 36249130022 — SUCCESS; all six jobs:
  backend, frontend, platform-admin, security, e2e, staging-config.
Backend exact summary:
  395 passed, 3 deselected, 3448 warnings in 73.27s
E2E exact summary: 3 passed in 10.04s
Frontend lint, TypeScript and production build: SUCCESS.
Platform admin, security, staging-config: SUCCESS.
Backend CI includes PostgreSQL bootstrap and schema/registry/parity
checks. E2E includes the existing authenticated browser flow.
These counts describe THIS source HEAD only; never transfer them to
a subsequent code change. Handoff-only edit: TESTS NOT RUN.

Alembic head: c5f7a9b1d3e6
Expected SQLAlchemy model tables: 101.
Previous head: b4e6a8c0d2f5; previous model tables: 100.
Planning checklist status/counts were NOT advanced; the last reported
metadata remains 628 total / 264 built / 364 scheduled / 0 in progress.
User explicitly approved the 1099 modernization on 2026-09-26; only
the 1099 requirement wording in PROJECT_MASTER, PLAN_GAPS, and the
reporting.1099 parity feature/notes was revised. No other frozen docs edits.

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

USER AUTHORIZATION 2026-09-26: IRIS/approved provider instead of FIRE,
plus bring secure W-9/tax profiles forward. Narrow 1099 wording updates
under docs/ were expressly authorized and committed. Provider credentials,
IRS-current tax-year schema, signed W-9 provenance, and filing review are
still prerequisites. Do not mark actual filing complete.

# 1099 MODERNIZATION — PREREQUISITE VERIFIED 2026-09-26

Implementation + scoped docs update:
  3aca0f64b1f58e8bb7afef32ae6ceda368dbc9ca
Hosted CI 36249130022 SUCCESS, all six jobs; backend
395 passed / 3 deselected / 3448 warnings in 73.27s;
E2E 3 passed in 10.04s. No local tests represented as run.
Migration c5f7a9b1d3e6 adds tax_profiles; model tables 101.
Existing accounting and reporting behavior unchanged.

Added dedicated encrypted taxpayer profiles for ORGANIZATION payer,
OWNER and VENDOR user recipients. Full TIN, tax classification,
legal name and address are encrypted together with Fernet.
Dedicated TAX_PROFILE_ENCRYPTION_KEY must be externally provisioned,
valid, and different from ENCRYPTION_KEY. No development fallback:
requests reject with 503 if key is missing. Never commit a real key.
Only the ADMIN customer role with REPORTING.ALL can write/read
within their organization. User recipients must be active, correct
role and same org. API output contains only subject identifier,
masked TIN last-four and staff-recorded paper W-9 status/date.
Pydantic input uses SecretStr, no raw TIN in API output or explicit
append-only audit; list/revocation and ciphertext tamper fail closed.
Backend endpoints GET/PUT /api/reporting/tax-profiles; no-store
responses. Signed W-9 PDFs are NOT stored yet: staff can record
paper W-9 receipt but cannot claim this is IRS-compliant electronic
W-9 capture. Do not put W-9 in general unencrypted attachments.
No automatic 1099 amounts, e-filing, or unverified IRIS CSV schemas.
Regression tests: six new secure-profile tests plus existing
database bootstrap/migration/schema/tenant isolation suite.

Original frozen documents: narrow user-authorized 1099 edits only:
docs/PROJECT_MASTER.md Section 38 FIRE changed to IRIS/provider,
docs/PLAN_GAPS.md C9 records pulled-forward prerequisites,
docs/APPFOLIO_PARITY_CHECKLIST.json reporting.1099 wording updated,
status still SCHEDULED. No unrelated documents changed.

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

1. Re-read this root handoff and verify branch HEAD/latest CI. Do not
   repeat verified labels, Custom Report Builder or the tax-profile
   encryption foundation. Original roadmap Phase 3.7 1099 remains
   incomplete until safe filing and recipient copies are verified.
2. Next bounded batch: admin-only 1099 preparation UI using existing
   /api/reporting/tax-profiles, with clear "not submitted" status.
   Include paper W-9 tracking, payer/recipient roster, masked TIN,
   IRS official W-9/IRIS references, and user-friendly explanation that
   dedicated encryption key must be configured by the operator.
   Do not expose TIN to generic exports, browser logs or user emails.
3. Next security/filing dependency: signed W-9 archival or vetted
   provider e-W9 intake with proper verification and retention;
   tax-year-specific payer and recipient classification/review.
   IRIS portal CSV must use IRS published template for the particular
   tax year, not a guessed schema. Automated IRIS A2A requires
   IRS TCC, API client ID, schema package and ATS approval; do not
   pretend live filing or produce purported IRS-ready forms before
   integration/testing. Customer paperwork/submission should be
   explicitly reviewed; no invented payment classifications/amounts.
4. User explicitly approved the modernized IRIS/provider scope
   and narrowly scoped docs changes. Do not expand other frozen docs,
   change main, create branches, or force push. User also approved
   commit-then-GitHub-CI product verification. Tests in every batch;
   no VERIFIED status before complete green CI. Fix CI failures
   autonomously, stop if same assertion fails three times, record
   exact run/count/migration and update THIS root handoff.
5. After the IRS-current verified 1099 batch, return to the original
   Section 38 order: Letters, Send Owner Packets, then listed reports.

# NEXT SESSION START PROMPT

Continue yasirskhan/property-platform on branch
chatgpt/checkpoint-005-safety. Read complete root AI_HANDOFF.md and
verify branch HEAD plus CI. Last VERIFIED source:
3aca0f64b1f58e8bb7afef32ae6ceda368dbc9ca;
CI 36249130022 SUCCESS (395 backend passed, 3 deselected;
3 E2E passed; all six jobs). Alembic c5f7a9b1d3e6, 101 tables.
IRIS-provider roadmap and encrypted admin-only tax-profile prerequisite
VERIFIED; 1099 filing NOT COMPLETE. The next Phase 3.7 batch is
admin 1099 readiness UI and secure signed W-9 / provider dependency.
Do not repeat existing reporting, change main or share tax IDs.
Use commit+CI verification and update root handoff after each batch.
