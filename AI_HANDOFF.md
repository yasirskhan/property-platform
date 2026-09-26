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
Last VERIFIED source HEAD: 788010f4b1c3609fb74a98b6bf48b0f037bc4bad
Always fetch current branch HEAD again; this handoff-only commit will
change the HEAD. Do not edit main, create/switch branches, force-push,
or merge draft PR #2 without approval.

CURRENT PHASE: 3.7 — Reports + Universal Attachments, IN PROGRESS.
LATEST COMPLETED BATCH: 1099 readiness UI and sensitive-profile access restrictions.
EXACT NEXT BATCH: secure signed paper W-9 archive / vetted provider e-W-9 intake,
then tax-year-specific IRS/provider 1099 filing validation and review.
Original Generate 1099 Forms & Reports remains IN PROGRESS, not VERIFIED.
The verified universal attachments, standard/enhanced report framework,
shared Print / Email / CSV delivery, saved configurations, labels report,
and encrypted tax-profile foundation/readiness UI must NOT be repeated. Phases 3.4.S and 3.4.3–3.4.26, compatibility pass
3.5.5, and Accounting Polish 3.6 are previously completed/verified.

# LAST VERIFIED CI AND SCHEMA

Verified source commit: 788010f4b1c3609fb74a98b6bf48b0f037bc4bad
GitHub Actions run 36249841377 — SUCCESS; all six jobs:
  backend, frontend, platform-admin, security, e2e, staging-config.
Backend exact summary:
  400 passed, 3 deselected, 3507 warnings in 46.80s
E2E exact summary: 3 passed in 9.58s
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

# 1099 PREPARATION UI + SECURITY BATCH — VERIFIED 2026-09-26

UI/report catalog commit 5a22b59ed0f3d0c8b877c8b038c5ac2fe67bbeea;
follow-up form-error usability caaca02d519cc3c3b47edfc734ec2c705e0cadb2;
generic-notes-and-attachments denylist + regression tests
488b6b93a00df9788eaaf90d7c9f07b2eb5f1b41;
inactive-admin authorization guard + regression test
788010f4b1c3609fb74a98b6bf48b0f037bc4bad.
Current source CI 36249841377 SUCCESS all six jobs; backend 400 passed,
3 deselected, 3507 warnings in 46.80s; E2E 3 passed in 9.58s;
frontend, security, platform-admin, staging-config SUCCESS.
Earlier superseded runs 36249424436, 36249502551,
36249516416, 36249764959 were CANCELLED by newer pushes; do not
represent them as failing test regressions or passed full CI.
No migration or new model in this batch. Still c5f7a9b1d3e6 and 101 tables.

New customer page: Reports > Tax > 1099 Preparation,
frontend/src/app/dashboard/reporting/1099/page.tsx.
Catalog entry tax.1099_preparation is a navigation-only "preparation"
slot, not an IRS-filing report key; it is NOT registered for CSV/email
in REPORT_PERMISSIONS. Only organization ADMIN may use the live
encrypted-profile intake; client displays only last-four TIN digits,
paper W-9 status and received date. It links to official IRS W-9,
explains signed paper W-9 must be retained separately and warns that
no IRS file, 1099 recipient copy, e-signature or tax return is created.
The UI does not upload documents or send any tax ID to generic report
delivery. Recoverable validation errors leave the form visible.
GET/PUT tax-profile routes set Cache-Control: no-store.

Security enforcement:
- app/services/entity_notes.py denies tax_profiles target altogether;
  generic notes and generic unencrypted attachment routes cannot use
  tax_profiles targets, verified with actual-record regression tests.
  This is a route scope exclusion, NOT a content scanner capable of
  detecting mislabeled W-9s uploaded to unrelated entities. UI warns
  admins not to use generic attachments for W-9s.
- app/services/tax_profiles.py denies inactive/deleted admins, even
  if a direct session were passed; targeted regression test included.
- Existing organization-scoped ADMIN + REPORTING.ALL authorization,
  fail-closed dedicated TAX_PROFILE_ENCRYPTION_KEY and ciphertext
  fields remain mandatory. A live environment must provision a unique
  tax key through secret management before using tax-profile routes;
  requests return 503 until configured. No real key is stored in repo.

Current IRS regulatory planning checks (verify again before filing):
- IRS reports FIRE last filing Nov. 19, 2026, with IRIS exclusively
  receiving tax-year-2026 information returns for filing season 2027.
  https://www.irs.gov/e-file-providers/filing-information-returns-electronically-fire
- The IRS identifies $2,000 as the tax-year-2026 threshold for
  specified 1099-NEC services and 1099-MISC rent and other covered
  payments, with exceptions (for example backup withholding and some
  payment types). Do not apply a universal $2,000 rule.
  https://www.irs.gov/businesses/small-businesses-self-employed/am-i-required-to-file-a-form-1099-or-other-information-return
  https://www.irs.gov/publications/p1099
- IRIS Taxpayer Portal requires IRIS TCC, currently supports manual
  entry and IRS-specific CSV templates; A2A requires a separate IRIS
  TCC, API client ID, schema package and ATS clearance. As checked
  Sept. 26, 2026, public taxpayer-portal CSV template list shows
  through tax year 2025, not tax year 2026; do NOT invent 2026 CSV
  columns or mark IRIS export production-ready before availability.
  https://www.irs.gov/filing/e-file-information-returns-with-iris
- An IRS-compliant electronic W-9 requires recipient authentication,
  original certification language, perjury statement and final
  verified electronic signature, plus submission records and hard-copy
  retrieval. Present paper W-9 receipt is NOT e-W9 certification.
  https://www.irs.gov/instructions/iw9

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

1. Read full root handoff, verify branch and CI. Do not repeat previous
   labels, saved reports, encrypted tax profiles or 1099 readiness UI.
   Keep original Phase 3.7 1099 forms/filing IN PROGRESS.
2. Safe next bounded batch: secure signed paper W-9 archival OR vetted
   provider-hosted e-W9 intake, using dedicated encrypted storage
   and restrictive access, audited access, retention/key rotation,
   no generic attachments. Verify real signed W9 evidence; do not
   label admin paper W9 checkbox as electronic signature. Include tests.
3. Next approved IRS IRIS/provider filing work requires current
   tax-year-specific official schema/template and payer/recipient
   verification, valid payer and recipient TINs, explicit classification
   of reportable payments, statutory thresholds and exceptions,
   explicit review/approval, valid IRIS TCC or provider account,
   electronic submission receipts, recipient copies and corrections.
   No generic GL/owner payout inference, no fabricated tax filings,
   no filing metadata marked sent before actual provider confirmation.
   Current IRS tax-year-2026 portal template was NOT publicly listed
   at last review; check for updates rather than guessing. Never paste
   provider API secrets or TINs in this chat; use secret management.
4. User authorized narrow 1099 modernization in frozen docs/ only;
   otherwise frozen docs unchanged. CI after bounded commits,
   applicable regression tests and counts; mark VERIFIED only
   after every relevant CI job succeeds. Fix failures, stop after
   three repeated failures of same assertion. Refresh this handoff
   after each meaningful verified batch.
5. Only after full 1099 feature is verified, resume Section 38
   roadmap: Letters, Send Owner Packets, tenant/property/owner/
   accounting/transaction reports. Do not skip original tasks,
   create branches, force-push or modify main.

# NEXT SESSION START PROMPT

Continue yasirskhan/property-platform on
chatgpt/checkpoint-005-safety. Read entire root AI_HANDOFF.md and
verify current HEAD and CI. Last VERIFIED source:
788010f4b1c3609fb74a98b6bf48b0f037bc4bad,
CI 36249841377 SUCCESS (400 backend passed, 3 deselected;
3 E2E passed; all six jobs green).
Alembic c5f7a9b1d3e6; 101 tables. 1099 IRS-IRIS modernization,
encrypted tax profiles, paper W-9 metadata, admin readiness UI
and generic-attachment/notes denylist are VERIFIED.
Full 1099 filing/recipient copies are NOT yet implemented.
Next batch: secure signed W-9 paper archive or vetted e-W9 provider,
then verified tax-year-specific IRIS/provider filing workflows.
Preserve all verified architecture, no main/new branch or unapproved
docs edits. User approved commit-then-GitHub-CI verification.
Do not request Work mode, create fictitious tax filings, or
expose tax identifiers. Refresh handoff after every meaningful batch.
