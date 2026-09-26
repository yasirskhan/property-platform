# AI_HANDOFF.md — Property Platform, 2026-09-26

**READ THIS WHOLE FILE FIRST.** This is the repo-ROOT authoritative session handoff;
it does NOT belong under docs/. Refresh after every meaningful CI-verified batch.
Do not ask Yasir to repeat verified state. Never paste real tax secrets/TINs.

- Private repository: `yasirskhan/property-platform`
- ONLY working branch: `chatgpt/checkpoint-005-safety`. Do not edit `main`,
  create a branch, force-push, or merge the draft PR without permission.
- Last VERIFIED **product source**: `26cc939f0ca39eb7219b3dad6c3ce4b527ff9a9b`
- Source GitHub Actions run **36277862050: SUCCESS, all six jobs** (backend,
  frontend, platform-admin, security, authenticated E2E, staging-config).
  Backend: **471 passed, 3 deselected, 6212 warnings in 71.33s**.
  E2E: **3 passed in 9.20s**. Lint, typecheck, production build, security
  and staging: SUCCESS. These counts apply to this exact source commit only.
  This handoff update itself is docs-only; TESTS NOT RUN locally. Verify
  current branch HEAD and latest CI before continuing.
- Alembic head: **a9c1e3f5b7d0**. SQLAlchemy expected model tables: **104**.
  Previous head f8c0d2e4a6b9 / 103 tables. Schema/test guards changed
  with the tax-profile revision migration; no new model table. All three
  PostgreSQL/bootstrap/legacy CI paths passed.
- Phase 3.7 Reports + Universal Attachments: IN PROGRESS.
  **Latest completed batch: Tenant Unpaid Charges (standalone current Charge balances). VERIFIED.**
- **1099 Phase 3.7 internal preparation/security is VERIFIED through local preflight,
  NEC/MISC sandbox payload mapping, explicit consent, redacted status/history and
  no-submission guarantees. Actual external sandbox acceptance requires operator
  Avalara subscription/credentials/issuer; production filing/IRS acceptance and
  recipient copies remain NOT IMPLEMENTED and belong to the external provider path.**
- **Exact NEXT executable original-plan task: Tenant Unpaid Charges Summary (catalog tenant.summary).**
  Tenant Delinquency, Security Deposit Funds Detail, Tenant Directory, Tenant Ledger, Tenant Tickler, Tenant Unpaid Charges and Owner Packets VERIFIED. Do not repeat verified preflight,
  manual review, register, revision guards, tax profiles or W-9 archive.

## Verification chronology — don't reimplement

| Batch | Source commits | Last full SUCCESS CI | Evidence |
| --- | --- | --- | --- |
| Universal Attachments | 90e54eb834047038f01959c5a2a20c9e4155e999 | 36219990832 | VERFIED |
| Standard/enhanced reports framework | 3afb0d3d2b41a222225e5ca20fb9c976fee77742 | 36221727596 | VERIFIED |
| Shared Print / Email / CSV delivery | f5c8a5177db003c5d6d1b2eb2fbf8510791d31d6, fad5066aa2bc4498156179fad6bb5c8ad1cfcf65 | 36222494517 | VERIFIED |
| Custom Report Builder saved configurations | 5f235e3bdc098885965c227a68956b69ea5f5307, b70be63af5195fe88f7bcadf2d6599732d24ce59, cf6f9aa1a54d276200c310f3b3d8f870cad64e97 | 36246789775 | 383 backend passed / 3 E2E |
| Labels Report CSV mail merge | 02641ebab30e24880b5ab61194f20ad8f0aea2cc, 5a2ee8acc5ea9dc81b4a48ec6d043879b6a7b5df | 36248197021 | 389 backend passed / 3 E2E |
| 1099 IRIS modernization + encrypted tax profiles | 3aca0f64b1f58e8bb7afef32ae6ceda368dbc9ca | 36249130022 | 395 backend passed / 3 E2E |
| Admin 1099 readiness + notes/attachments protection | 5a22b59ed0f3d0c8b877c8b038c5ac2fe67bbeea, caaca02d519cc3c3b47edfc734ec2c705e0cadb2, 488b6b93a00df9788eaaf90d7c9f07b2eb5f1b41, 788010f4b1c3609fb74a98b6bf48b0f037bc4bad | 36249841377 | 400 backend passed / 3 E2E |
| Encrypted signed-paper W-9 archive backend | 18f024a0a1d932f6c2b327c38b2954c6930cd356 | 36250903803 | 406 backend passed / 3 E2E |
| Admin W-9 upload/list/download UI | fe0a7cd39a22a60f4378db50ad85583c8bc45bfc | 36251266775 | 406 backend passed / 3 E2E |
| Sentry request-body and stack-local exclusion | e8552318fcbd85663c678acb0d8f2948f6ebdecb | 36251597787 | 407 backend passed / 3 E2E |
| Bounded ciphertext key rotation | 10eff9806ce1890afadb04afb62ad7849d45258b | 36251944098 | 409 backend passed / 3 E2E |
| Manual NEC/MISC preparation, review and approval | 1ac7a5a6ef2949e0a905f4b354cbb3a80eb63551, 935d24002ee0d9568dd6434948d4a42360302a88, 8fbb07afc1d95ab22eea7a5bb8d7d05e141acb82 | 36266540061 | 416 backend passed / 3 E2E |
| Internal redacted 1099 register | 4a96cd00d098dd82b646dc0e7bc00dc2c4cd3a87, f68e06169b4b8c33f335e97d84dfa00034493c33 | 36267589323 | 418 backend passed / 3 E2E |
| Substantive tax-profile revision and approval staleness guard | 48dc20d6d52d163954cc00956714090d3d2dcae9 | 36268034674 | 423 backend passed / 3 E2E |
| Redacted provider-handoff preflight without submission | 329e106709457647adb8b160a13d44695c102fd3 | 36268470769 | 426 backend passed / 3 E2E |
| Source-text redaction + competing approval guard | 53c26c97c8a6f7f1a4ed16014eb9c80e68ca04f8, 6aa0a0414341d1a7cfc90fa3fcb119beb470f4e7 | 36269106237 | 428 backend passed / 3 E2E |
| Avalara sandbox dry-run adapter | 85a6180a9fce3258d2bda90e878cfb30d4a891ec | 36270582328 | 431 backend passed / 3 E2E |
| Provider status + explicit sandbox UI | 4a54c602966a795a8b399893f3d5fc46a6324ab3 | 36270979448 | 432 backend passed / 3 E2E |
| Avalara 1099-MISC rents sandbox mapping | 49dd9e5129df94e3721f3a97caa0415738bc24bb | 36271476212 | 432 backend passed / 3 E2E |
| Immutable redacted provider dry-run history | 1560b0ec2c436ad363bf6c742036aaf94fd6892e | 36271931432 | 433 backend passed / 3 E2E |
| Letters backend: scoped templates, text merge, reviewed notice send | 0afaec13accb9594d782cd088feca2ef5f92c927 | 36273058209 | 438 backend passed / 3 E2E |
| Letters UI + preview/email digest binding | a896605e16a37d5c5d778043545997b828ab8c7a, 5d9b4142275cdb759ca2701cd1f567f776616100 | 36273560029 | 440 backend passed / 3 E2E |
| Tenant Tickler | f97b2c9c4078076ebd3c1d19d7107068bf49bb42 | 36277065122 | 467 backend passed / 3 E2E |
| Tenant Unpaid Charges | 26cc939f0ca39eb7219b3dad6c3ce4b527ff9a9b | 36277862050 | 471 backend passed / 3 E2E |
| Tenant Ledger current balances and Charges authorization | a12e0f1af94b7e74e03e9e81988bba98d98cb016, 33902846eab82304299f383001de682081091eec | 36276682654 | 463 backend passed / 3 E2E |
| Tenant Directory | 873219e0be9e41a7c68ec52e4da604a882dc90c2 | 36275843531 | 458 backend passed / 3 E2E |
| Security Deposit Funds Detail GL liability report | 60ee5a986d670b4e3af18d01060e971c163c522f | 36275464600 | 454 backend passed / 3 E2E |
| Owner Packet frozen CSV backend + customer UI | 563596a7baf15ef3e8d5e46c8b8f71f2de29e47a, e170aeba1aa725d8d3c3c2a5c536351dcdc3386b, 2ff688a0c9b20a31cc2cf0ca39b886a8b565cc0f | 36274518298 | 446 backend passed / 3 E2E |
| Tenant delinquency live overdue rent invoices | 8a6a27ef3c248e394546bdb4e8a65c8ffa43e6b7, a644bd803787d3ffc9be36de4318a67915248364 | 36274961962 | 450 backend passed / 3 E2E |


All listed full CI runs were successful. Older superseded CI runs may be
CANCELLED, not necessarily failed. Do not transfer test totals to later code.

## Existing verified design contracts

1. Hybrid Capability Gating separates release gate, plan entitlement, org
   configuration, role/menu permission and user preference; backend decides.
   Do not add unrelated per-field flags.
2. Keep all accounting changes on the central immutable GL and respect locked
   periods, idempotency, org/owner/property scope and immutable audit.
   Reporting basis ACCRUAL (default) vs CASH changes reports, not GL.
3. Customer JWT/identity and platform-admin JWT/identity stay separate.
4. Universal notes/attachments are the shared services for ordinary business
   entities; do not create parallel generic storage. Their resolver expressly
   FORBIDS `tax_profiles` and `tax_w9_documents`. They are not safe for
   W-9 content uploaded under another entity name either.
5. Canonical report catalog under REPORTING.ALL, standard BUTTON and enhanced
   TAB, shared ReportActions, server rerendered CSV/email, report-level
   permissions + release.reporting.export gate, CSV formula escaping and
   org scope remain intact. Saved configurations belong to creator and
   organization, with permission rechecks. No arbitrary SQL/report builder.
6. Do not represent planning parity/status as behavioral test evidence.
   Last reported parity metadata before 1099 modernization was
   628 total / 264 built / 364 scheduled / 0 in progress; counts and
   status NOT updated since. `reporting.1099` remains SCHEDULED.

## 1099 modernization and exactly what is implemented

User expressly authorized 2026-09-26 IRIS / approved-provider route instead
of obsolete FIRE and bringing secure W-9/tax profiles into Phase 3.7.
ONLY the 1099 requirement wording in frozen docs/PROJECT_MASTER.md,
docs/PLAN_GAPS.md and docs/APPFOLIO_PARITY_CHECKLIST.json was updated
at 3aca0f64. ALL other docs/ source-of-truth content remains frozen and
must NOT be modified without separate authorization.

**Taxpayer profiles**:
- `backend/app/models/tax_profile.py`, `services/tax_profiles.py`,
  `schemas/tax_profile.py`, `routers/tax_profiles.py`.
- `GET/PUT /api/reporting/tax-profiles`: org-specific ADMIN plus
  REPORTING.ALL, active/not-deleted, actual role/same-org recipient.
- Typed payer ORGANIZATION and OWNER/VENDOR recipient, validated tax ID,
  classification, legal name, business name, mailing address encrypted
  as one Fernet payload. Only masked TIN last four and W-9 status/date
  in output. Audit excludes taxpayer identifiers and mailing contents.
  No data in generic reporting actions or raw field exports.
- No default tax key. `TAX_PROFILE_ENCRYPTION_KEY` must be externally
  provisioned, independent of ordinary `ENCRYPTION_KEY`; fail closed
  with 503 when absent. A live operator must configure it in their
  secret manager, not in source or chat.

**Signed-paper W-9 archive**:
- `backend/app/models/tax_w9_document.py`, migration
  `d6a8b0c2e4f7_add_tax_w9_archive.py`,
  `services/tax_w9.py`, `routers/tax_w9.py`, `schemas/tax_w9.py`,
  `backend/tests/test_tax_w9.py`.
- `GET/POST /api/reporting/tax-w9/{profile_id}` and
  `GET /api/reporting/tax-w9/{profile_id}/{document_id}/download`.
- Raw `application/pdf` streaming, max 5MB, PDF marker/EOF checks,
  no multipart temp-file spool. Encrypted PDF ciphertext in the
  `tax_w9_documents` database table, never unencrypted general
  attachment storage. No-store, forced download, `nosniff`, sandbox CSP,
  org/user/role/REPORTING.ALL scope and audit (archive, metadata list,
  download). Staff attests paper signature review; NOT e-signature,
  signature OCR, PDF antivirus screening or a filing system.
- Page `frontend/src/app/dashboard/reporting/1099/page.tsx` embeds
  `TaxW9Archive.tsx`: secure upload/list/download and paper-W-9
  status, masked taxpayer profile intake, clearly says filing disabled.
  Backend code does not generate IRS filing or recipient copies.
- `TAX_PROFILE_PREVIOUS_KEYS_JSON` (secret manager JSON list, default [])
  permits decrypting older profiles/documents while current key encrypts
  new data. Bounded `POST /api/reporting/tax-profiles/rotate-encryption`
  rewraps up to ten profiles + ten PDFs per call, uses cursors, is org
  and admin scoped, audited without decrypted content, rolls back on
  corruption/missing historical key. See `services/tax_key_rotation.py`,
  `schemas/tax_rotation.py`, tests.
- `app/core/observability.py`: Sentry does not collect HTTP bodies
  (`max_request_body_size="never"`) or exception frame locals,
  `send_default_pii=False`, with regression test. This is not a
  substitute for W-9 PDF malware scanning or complete DLP.

**Manually sourced 1099 preparation, review, approval (VERIFIED)**:
- Migration `e7b9c1d3f5a8_add_tax_1099_reviews.py` adds one
  `tax_1099_reviews` table; SQLAlchemy 103 tables. Backend services
  `app/services/tax_1099_reviews.py`, router
  `app/routers/tax_1099_reviews.py`; frontend
  `components/reporting/Tax1099ReviewPanel.tsx` on Reports > 1099.
- Supports explicit tax-year 1099-NEC nonemployee compensation VENDOR,
  1099-MISC rents OWNER, organization payer plus matching recipient
  encrypted tax profiles, user-entered positive amounts, documented
  source/type/reference. Does NOT infer tax amounts from GL, bills,
  checks, payees or owner payouts; admin checks threshold and exceptions.
- PREPARED -> REVIEWED (requires encrypted archived signed W-9) ->
  APPROVED (three explicit human confirmations); approved records lock.
  Scoped ADMIN/REPORTING.ALL, cross-org isolation, redacted last-four
  TIN output, append-only audit, idempotency key fingerprint,
  no-store, deliberately no filing endpoint. 7 focused backend tests
  and E2E smoke coverage. Earlier 935d2400 test-only scope correction
  passed CI. Full source 8fbb07af had CI 36266540061 SUCCESS.
- An approved record currently references mutable live taxpayer
  profiles: a later tax-profile replacement can change live last-four
  data while its review still says APPROVED. NEXT: add explicit
  profile-revision review/approval invalidation. Do not silently allow
  changed taxpayer data to inherit old approval; key rotation must
  NOT count as a substantive profile change.

**Redacted internal 1099 register (VERIFIED)**:
- Source 4a96cd00d098dd82b646dc0e7bc00dc2c4cd3a87,
  test-only fix f68e06169b4b8c33f335e97d84dfa00034493c33;
  CI 36267589323 SUCCESS all six jobs (418 backend passed,
  3 deselected, 3993 warnings in 79.47s; E2E 3 passed in 7.09s).
- `GET /api/reporting/tax-1099-reviews/register.csv?tax_year=2026`
  uses the verified `ReportPayload` / `report_csv_bytes` renderer.
  ADMIN/REPORTING.ALL plus release.reporting.export required, full
  live-org scope, encrypted profile access, audit of download metadata
  without tax IDs, no-store, nosniff, CSV formula escaping.
  No names/addresses/raw TINs/source notes; last-four masked.
  Includes review status and source reference; every data row says
  "NOT FOR IRS SUBMISSION", filename `1099-internal-review-not-for-irs-<year>.csv`.
  Frontend has an explicit internal CSV download, never a file action.
  New tests prove cross-org exclusion, formula escaping, audit,
  export-gate revocation and 2020-2100 year validation.
- NO filing submission, IRS/IRIS/provider schema, recipient copy or
  state filing is generated. Docs/ other than ROOT HANDOFF unmodified.

**1099 approval integrity safeguard (VERIFIED)**:
- Source `48dc20d6d52d163954cc00956714090d3d2dcae9`,
  CI 36268034674 SUCCESS six jobs, 423 backend passed, 3 deselected,
  4189 warnings in 66.98s; E2E 3 passed in 10.43s.
  Migration `f8c0d2e4a6b9_tax_profile_review_revisions.py` adds
  `tax_profiles.profile_revision` and per-review payer/recipient revision
  snapshots, head f8c0d2e4a6b9, same 103 model tables.
- Tax-profile substantive changes increment revision; normalized
  identical upserts and ciphertext-only key rotation do NOT. New
  signed-paper W-9 archive evidence increments revision.
- Marking REVIEWED captures current payer/recipient revision. Later
  corrections stale existing REVIEWED/APPROVED records; approval
  refuses stale review with 409 until explicitly re-reviewed.
  Historical APPROVED stays immutable but is visibly stale and
  not eligible for downstream submission. Legacy approved rows with
  missing revision snapshot fail closed rather than inheriting
  approval. Live UI and internal CSV explicitly flag re-review need.
- Tests cover correction before approval, immutable stale approval,
  repeat identical upsert, newer signed W-9, key rotation unchanged,
  and legacy rows; no full TINs stored in approval records or export.
- This remains internal review; no IRS tax return or recipient
  copy was generated. Docs/ unchanged. Product code VERIFIED.
  Source CI is more relevant than handoff-only CI.

**Provider-handoff local preflight — VERIFIED 2026-09-26**:
- Product commit `329e106709457647adb8b160a13d44695c102fd3`,
  all-six-job CI 36268470769 SUCCESS. Backend 426 passed,
  3 deselected, 4305 warnings in 65.25s; E2E 3 passed in 9.29s.
  No migration; Alembic f8c0d2e4a6b9 and 103 model tables.
- Authenticated ADMIN/REPORTING.ALL-scoped
  `GET /api/reporting/tax-1099-reviews/{id}/preflight` rechecks
  APPROVED status, current payer/recipient substantive revisions,
  all manual review attestations, archived signed W-9, payer and
  recipient encrypted-identity completeness, positive documented
  amount/source. It fails closed on cross-org/permission revocation.
- Response returns only record ID, tax year/form, review status,
  redacted blockers, boolean local `ready_for_provider_handoff`,
  `filing_enabled=false`, `submission_status=NOT_SUBMITTED`.
  Never serializes TIN, legal name, mailing address, source notes,
  IRS upload file or fake provider success. No-store response,
  metadata-only append-only audit. Frontend review panel has
  "Check provider prerequisites" and a clear no-filing disclosure.
- Three new tests cover incomplete-vs-ready state after explicit
  reapproval, no raw secrets in response/audit, cross-org/revocation,
  missing W-9 evidence; existing test suites remain green.
- The source reference/note fields are user-entered plaintext.
  Potential accidental full tax-ID entry into source fields and
  multiple competing approved records for one payer/recipient/year
  need additional fail-closed safeguards BEFORE provider integration.
  Next bounded batch should validate/redact such source input and
  flag competing current approved records, with tests.
- IRS IRIS taxpayer portal offers official CSV formatting guidelines
  inside authenticated portal, but no public tax-year-2026 template
  was verified here. NEVER label internal register an IRIS import.
  Original docs/PLAN_GAPS.md C9 reserves actual e-filing, corrections
  and recipient delivery for provider Phase 4.5. Do not falsely
  complete full 1099 or create a provider delivery bypass in 3.7.


**Provider-preflight source safety — VERIFIED 2026-09-26**:
- Product commits `53c26c97c8a6f7f1a4ed16014eb9c80e68ca04f8` and
  `6aa0a0414341d1a7cfc90fa3fcb119beb470f4e7`; CI 36269106237
  SUCCESS all six jobs. Backend 428 passed, 3 deselected, 4398 warnings
  in 84.14s; E2E 3 passed in 9.08s. No migration; head remains
  f8c0d2e4a6b9 and 103 tables.
- New PREPARED/updated source reference/note rejects SSN/EIN-like
  identifiers with a generic 422 message. Existing legacy source text is
  redacted in API/CSV output instead of exposed. Private source validation
  still sees original stored text so preflight fails closed until cleaned.
- Provider preflight blocks a CURRENT APPROVED competing record for the
  same organization/payer/recipient/form/income category/tax year. Stale
  historical approvals remain immutable audit history and are not treated
  as a current competing filing. Nothing is auto-selected or submitted.
- Tests cover new input rejection, legacy redaction, private-source
  validation, current duplicate approval, stale historical approval,
  cross-org/status invariants and existing encryption/revision safeguards.


**Avalara sandbox dry-run provider adapter — VERIFIED 2026-09-26**:
- Product commit `85a6180a9fce3258d2bda90e878cfb30d4a891ec`;
  CI 36270582328 SUCCESS all six jobs. Backend 431 passed,
  3 deselected, 4505 warnings in 84.11s; E2E 3 passed in 8.83s.
  No migration; Alembic f8c0d2e4a6b9, 103 tables.
- Server-only config: TAX_1099_PROVIDER defaults `disabled`; the only
  supported provider mode is `avalara_sandbox`. Client ID, client secret,
  issuer ID and API version are environment secrets/config; no repo defaults.
  Settings refuse a partially configured enabled sandbox provider.
- `POST /api/reporting/tax-1099-reviews/{id}/provider/avalara-sandbox/validate`
  requires ADMIN/REPORTING.ALL and an explicit
  `confirm_external_tax_data_sandbox=true`. Existing local preflight,
  revision, W-9, duplicate-approval and source-safety gates run first.
- Adapter obtains an OAuth client-credentials token from Avalara sandbox and
  calls the official `/1099/forms/$bulk-upsert?dryRun=true` endpoint.
  It forces federalEFile=false, stateEFile=false and postalMail=false;
  no production URLs, filing/scheduling endpoint or recipient delivery.
  API/audit response is redacted and NEVER includes provider response body,
  raw TIN, name, address, token, client secret or source notes.
- Initial adapter commit supported only 1099-NEC. Subsequent verified
  commit 49dd9e5129df94e3721f3a97caa0415738bc24bb added official
  1099-MISC rents mapping. Tests mock all external requests; CI did NOT
  contact Avalara or claim sandbox credentials.
- Official Avalara docs checked 2026-09-26 document an active subscription,
  OAuth client credentials, sandbox token/API URLs and bulk-upsert dryRun.
  A real operator must provision sandbox credentials/issuer before any
  external validation can occur. This is NOT an IRS filing or acceptance.


**Provider status + explicit sandbox validation UI — VERIFIED 2026-09-26**:
- Product commit `4a54c602966a795a8b399893f3d5fc46a6324ab3`;
  CI 36270979448 SUCCESS all six jobs. Backend 432 passed,
  3 deselected, 4531 warnings in 82.97s; E2E 3 passed in 8.59s.
  No migration; Alembic f8c0d2e4a6b9 and 103 model tables.
- `GET /api/reporting/tax-1099-reviews/provider/status` requires live
  tax-admin authorization and exposes only DISABLED vs AVALARA_SANDBOX,
  configured boolean, sandbox_only=true, filing_enabled=false and supported
  forms. It never exposes client ID/secret or issuer ID; no-store response.
- Admin review UI loads the redacted status. After local preflight is ready,
  a configured supported form shows a separate sandbox disclosure checkbox
  and validation button. The admin must explicitly acknowledge that taxpayer
  data will be transmitted to the configured Avalara sandbox for dry-run
  validation. UI explicitly says no federal/state filing, postal mail,
  e-delivery or IRS acceptance occurs.
- Disabled/unconfigured provider or unsupported form shows a no-transmission
  message instead of an action. Current supported mapping remains 1099-NEC.
- Regression test proves status is no-store, permission-scoped and excludes
  all provider secrets. Frontend lint/typecheck/build and full CI green.


**Avalara 1099-MISC rents sandbox mapping — VERIFIED 2026-09-26**:
- Product commit `49dd9e5129df94e3721f3a97caa0415738bc24bb`;
  CI 36271476212 SUCCESS all six jobs. Backend 432 passed,
  3 deselected, 4532 warnings in 87.23s; E2E 3 passed in 9.99s.
  No migration; Alembic f8c0d2e4a6b9 and 103 model tables.
- Avalara's official v2 SDK model documents 1099-MISC `rents` and the
  same bulk-upsert form envelope used by 1099-NEC. The sandbox dry-run
  adapter now supports MISC/RENTS with `rents=<manually reviewed amount>`.
- Provider payload now keeps federalEfileDate, stateEfileDate and
  recipientEdeliveryDate null, postalMail=false, tinMatch=false and
  addressVerification=false. `dryRun=true` remains mandatory.
- Both NEC and MISC are shown as supported by the redacted sandbox status.
  Tests prove MISC uses `rents`, never NEC compensation, never schedules
  delivery/filing, and does not echo provider body/TIN/secret to output/audit.
- Existing deprecated-but-supported Avalara `recipientName` is retained
  because the current verified tax profile stores one legal tax name, not
  structured individual first/last tax-name fields. Do not invent a split.


**Immutable redacted provider dry-run history — VERIFIED 2026-09-26**:
- Product commit `1560b0ec2c436ad363bf6c742036aaf94fd6892e`;
  CI 36271931432 SUCCESS all six jobs. Backend 433 passed,
  3 deselected, 4562 warnings in 63.07s; E2E 3 passed in 8.50s.
  No migration; Alembic f8c0d2e4a6b9 and 103 model tables.
- Existing append-only `audit_log` is the single history store; no duplicate
  provider-attempt table was added. Each provider dry-run audit now stores
  only provider, dry_run=true, HTTP status, validated bool, submitted=false
  and the app-generated correlation UUID.
- Admin no-store endpoint
  `GET /api/reporting/tax-1099-reviews/{id}/provider/attempts` rechecks org/
  tax-admin access and returns only safe parsed audit metadata. Malformed,
  non-dry-run or submitted-looking legacy audit payloads are ignored.
- Review UI loads history after preflight/validation and labels every entry
  NOT SUBMITTED. Provider response bodies, tax IDs, names, addresses,
  credentials, issuer ID and tokens are never persisted/exposed by history.
- External provider boundary: CI uses mocked requests only. A real Avalara
  sandbox validation requires operator-provisioned active subscription,
  sandbox client credentials and issuer ID. Missing those external credentials
  blocks only real provider verification, not continuing Phase 3.7.

**CURRENTLY NOT IMPLEMENTED**: provider-hosted e-W9 consent/signature,
backend PDF malware scanning/retention purge, automatic reportable-payment
identification, official IRS tax-year submission template mapping, live
provider/TCC credentials, real transmission, IRS/provider acceptance receipts,
corrections, recipient copies or e-delivery. Manual NEC/MISC preparation,
review/approval and sandbox request mapping ARE implemented and verified.
Do not claim any unimplemented external filing behavior or enable "file".

## Phase 3.7 Letters backend — VERIFIED 2026-09-26

Product commit 0afaec13accb9594d782cd088feca2ef5f92c927;
CI 36273058209 SUCCESS all six jobs. Backend **438 passed,
3 deselected, 4712 warnings in 87.86s**; E2E **3 passed in 9.08s**.
Frontend lint/typecheck/build, security, platform admin and staging GREEN.
Migration a9c1e3f5b7d0 adds letter_templates; expected 104 tables.
Three schema/bootstrap guards adjusted and passed. Frozen docs/ unchanged.

Backend files: models/letter_template.py, schemas/letter.py,
services/letters.py, routers/letters.py, app/main.py, init_db.py;
catalog now links standard "Letters" to /dashboard/reporting/letters.
Five focused backend tests in tests/test_letters.py validate org isolation,
manager property assignment, inactive/deleted tenant/lease scope,
plain-text tag allowlist/no HTML/no arbitrary expressions, immutable
metadata-only audit, explicit notice legal review, recipient sourced
exclusively from live scoped lease, and rechecked release.reporting.export.
Routes under /api/reporting/letters support list/create/read/update/
deactivate, scoped tenant preview and explicit confirmed email delivery.
Only org ADMIN may modify templates; ADMIN/MANAGER with REPORTING.ALL
and LEASING may preview/email for scoped active leases. Emails reuse
existing core email service. No parallel generic attachment store,
no accounting posting, no legal jurisdiction template fabricated.
3-DAY notice category is an editable draft only; email requires
confirm_recipient, confirm_content_reviewed, confirm_legal_review.
No automatic statutory deadline, proof of service, physical delivery
or legal sufficiency claim.

**NEXT**: customer Letters UI with template overview/editor,
tenant lease picker, live server preview, printable plain text,
explicit email review confirmations and 3-day legal-review disclosure.
Do not mark full Letters VERIFIED until UI CI succeeds. Consider
preview-to-send content revision binding before treating legal
notice workflow as production-safe; current confirmations are
boolean-only and a template might change between preview and send.
No changes to main or frozen docs/.

## Phase 3.7 Letters customer UI — VERIFIED 2026-09-26

Signed preview / send review integrity:
a896605e16a37d5c5d778043545997b828ab8c7a.
Overview/editor/print/email customer page:
5d9b4142275cdb759ca2701cd1f567f776616100.
Final source CI **36273560029 SUCCESS** all six jobs.
Backend **440 passed, 3 deselected, 4788 warnings in 48.62s**;
browser E2E **3 passed in 6.63s**; frontend lint/typecheck/build,
platform-admin, security, staging-config SUCCESS.
Two focused backend tests added to the previous five-letter suite.
No migration in this batch: Alembic a9c1e3f5b7d0, 104 tables.
Handoff-only update TESTS NOT RUN locally. No docs/ changed.

Customer Reports > Mailings > Letters page now:
- Lists org templates; ADMIN can create, view/edit and deactivate
  CUSTOM and THREE_DAY_NOTICE text-only templates.
- User picks an active lease, server checks live org/tenant/property
  assignment and authorization and returns rendered text.
- A preview HMAC tied to requesting staff user, org, template ID,
  lease ID, category, exact rendered subject/body and live recipient
  email is required on email send. Changed content/recipient/lease
  produces HTTP 409 and requires fresh preview/review. Not a legal
  service signature; only review-integrity control.
- Browser offers printable plain-text preview; recipient/content
  confirmations and extra legal-review checkbox for 3-day draft.
  No jurisdiction-specific statutory language/dates or assumption
  that emailing equals valid notice service.
- Email reuses existing core SMTP/console service and writes
  metadata-only immutable audit. Existing REPORTING.ALL + LEASING
  and release.reporting.export gates apply. MANAGER scope uses active
  assigned properties. No arbitrary recipient email accepted.
- Current E2E CI smoke remains 3 existing browser tests; new
  feature-specific coverage is in focused backend regression tests.
  Do not misrepresent those three as dedicated Letters browser tests.

FULL LETTERS ORIGINAL PHASE 3.7 BATCH VERIFIED.
NEXT original-plan task: Send Owner Packets. Preserve verified
owner statement snapshot, owner packet settings, export and email.
External Avalara sandbox/IRS acceptance remains unverified,
not a reason to block owner packet/reporting work.


## Phase 3.7 Send Owner Packets — VERIFIED 2026-09-26

Owner packet backend: commit 563596a7baf15ef3e8d5e46c8b8f71f2de29e47a,
CI 36273951824 SUCCESS all six jobs (445 backend passed,
3 deselected, 4939 warnings in 88.84s; 3 E2E passed in 7.18s).
Customer page and regression tests: e170aeba1aa725d8d3c3c2a5c536351dcdc3386b;
admin-only directory-load scope correction:
2ff688a0c9b20a31cc2cf0ca39b886a8b565cc0f.
Final CI 36274518298 SUCCESS all six jobs:
446 backend passed, 3 deselected, 4969 warnings in 86.94s;
3 E2E passed in 8.51s, frontend lint/typecheck/build,
platform-admin/security/staging-config PASS. No migration.
Alembic a9c1e3f5b7d0 / 104 SQLAlchemy tables unchanged.

Backend /api/accounting/owner-packets/{statement_id}/preview and
/email use frozen OwnerStatement.property_data and existing
ReportPayload/report_csv_bytes; configured OWNER_STATEMENT and/or
PROPERTY_CASH_SUMMARY, selected via existing OwnerPacketSettings.
Only ADMIN or assigned MANAGER with REPORTING.ALL and
ACCOUNTING.OWNER_STATEMENTS, packet-customizer, export and
cash-summary gates may preview/send. Managers require ALL
snapshot properties assigned; other-org owner, deleted/inactive
owner/statement and unsupported settings fail closed.
Recipient email always resolved from the live scoped OWNER user,
not arbitrary client input. A signed HMAC preview binds actor,
organization, statement, owner, recipient, selected CSV content,
email-enabled preference, cover message and subject. Email requires
two explicit confirmed checkboxes and same live preview token;
recipient/config/snapshot changes reject 409. Metadata-only audited
email; no fresh GL posting or recomputation. Attachment format
is CSV, NOT a PDF. Console-mode email remains the normal development
delivery backend, not proof of physical inbox receipt.

UI: /dashboard/accounting/owner-statements/packets, linked from
Reports catalog, Owner Statement detail and Packet Settings.
Shows frozen statement selection, current scoped recipient,
period, cover note, attachment names, CSV-format disclosure,
recipient and snapshot review confirmations, gated send and
success/failure messages. ADMIN loads org statement directory.
MANAGER does NOT request that org-wide directory, uses explicit
statement ID; backend still reauthorizes every preview/email.
Any invalidated preview clears checkboxes and requires fresh review.
Packet Settings old "not yet available" wording corrected.
Focused new backend test covers no-store preview and inactive owner;
existing tests cover cross-org, manager assignment, live email,
HMAC stale changes, entitlement revocation and CSV escaping.
Existing authenticated E2E smoke now visits packet page and
asserts no blind send action. Existing three browser tests remain
three (not three dedicated owner-packet tests).

FULL SEND OWNER PACKETS ORIGINAL PHASE 3.7 BATCH VERIFIED.
NEXT original roadmap Section 38: Tenant Reports, first
Delinquency then Security Deposit Funds Detail, Tenant Directory,
Ledger, Tickler, Unpaid Charges, Summary. Inspect report catalog
and actual invoice/charge/deposit models; preserve balance
accuracy, reporting basis, org/property scope and export gates.


## Phase 3.7 Tenant Delinquency — VERIFIED 2026-09-26

Source 8a6a27ef3c248e394546bdb4e8a65c8ffa43e6b7;
focused test-fixture correction
a644bd803787d3ffc9be36de4318a67915248364.
Final full CI 36274961962 SUCCESS all six jobs:
450 backend passed, 3 deselected, 5190 warnings in 90.27s;
authenticated E2E 3 passed in 7.07s; frontend lint/typecheck/
build, platform admin, security and staging-config success.
The first superseded CI 36274941584 was cancelled after the
fixture correction. No schema migration; Alembic a9c1e3f5b7d0,
104 tables unchanged. No frozen docs/ files modified.

Report catalog enhanced TAB tenant.delinquency now links to
/dashboard/reporting/delinquency. Backend
services/tenant_delinquency.py reports TODAY's overdue rent
invoice balances from recorded RentInvoice.amount_due + late_fee
- amount_paid; excludes due-today/future, VOID and fully paid
balances. Uses live invoice balances ONLY (not a historical-as-of
AR snapshot); distinct unpaid tenant charges are explicitly
excluded and remain a separate roadmap report. No GL writes.
Each row: tenant/property/unit/invoice, due date, days overdue,
rent, late fee, paid and outstanding. Server CSV/email use the
existing authorized ReportPayload/report_csv_bytes renderer.
GET /api/reporting/delinquency/preview is no-store, requires
REPORTING.ALL, LEASING, release.reporting.export, and current
active ADMIN or MANAGER; manager rows restricted to assigned
nondeleted properties, tenants and units org/active scoped.
Optional property_id probing returns same not-found response for
foreign/unassigned properties. Unknown historical-as-of or SQL
filters fail closed. New focused tests cover current balance
math, scope, CSV formula escaping, invalid filters, permission/
export revocation and preview no-store. Existing authenticated
browser smoke now visits Delinquency route; not a dedicated
interactive export E2E test.

Next Section 38 report Security Deposit Funds Detail. Source
evidence: Lease.security_deposit is a contract amount, not proof
funds were held. Existing posted GL liability 2101 and org
owner-held DEPOSIT_LIABILITY Key Accounts can support an
accurate ledger-based detail, but GLEntry may not have a
tenant ID and unallocated property entries must be disclosed.
Do not falsely label contract amount or inferred owner/tenant
attribution as reconciled bank-held cash. Preserve org/manager
scope, reporting and accounting permissions, booked GL
immutability and CSV/export gates; add focused tests.

## Phase 3.7 Security Deposit Funds Detail — VERIFIED 2026-09-26

Source commit 60ee5a986d670b4e3af18d01060e971c163c522f;
CI 36275464600 SUCCESS all six jobs: backend 454 passed,
3 deselected, 5451 warnings in 79.84s; E2E 3 passed in 9.45s;
frontend lint/typecheck/build, security, platform-admin and
staging-config SUCCESS. No migration: Alembic a9c1e3f5b7d0,
104 model tables unchanged. No frozen docs/ changed.

Backend services/security_deposit_funds.py and existing report
catalog/delivery/reporting router supply standard
tenant.security_deposit_funds_detail, Reports > Tenant >
Security Deposit Funds Detail and customer route
/dashboard/reporting/security-deposits. Backend preview:
GET /api/reporting/security-deposits/preview, no-store.
Shared server-generated CSV/email delivery and ReportActions
are reused. Optional posted-through as_of date and property_id.
REPORTING.ALL, ACCOUNTING.GL_ACCOUNTS, release.reporting.export
must authorize each preview/export/email. Service additionally
requires active ADMIN or MANAGER within same organization. Managers
see only nondeleted, actively assigned properties; admins may
review explicitly labeled unallocated entries. Foreign/unassigned
property probes fail closed. Cross-org account/transaction/entry
rows excluded.

Detail is posted GL LIABILITY account 2101 plus configured
DEPOSIT_LIABILITY key accounts only, credit-minus-debit movements.
Original entries and posted reversals BOTH count by business date;
future entries and other GL accounts do not. Includes entry ID,
date, account, reference, property, coherent unit tag, debit/credit,
net movement, allocation warning. No tenant attribution is inferred
from GL entries. No lease contract security_deposit is counted as
cash received. No bank-held cash/reconciliation claim, no GL writes.
Four focused new backend tests cover reversal and date accuracy,
owner-held account inclusion, manager/org isolation, formula-safe
CSV, preview no-store, permission/export revocation and server email.
Existing browser smoke remains 3 general tests, not feature-specific.

NEXT exact original report: Tenant Directory, then Tenant Ledger,
Tickler, Tenant Unpaid Charges and Summary. Preserve tenant
organization and manager-assigned property scope; do not expose
unassigned tenants to managers. Read actual User/Lease/Unit/Property
models before coding. Build only report data and customer view,
reusing existing report permissions, catalog, CSV/email. Add focused
security and CSV tests; commit then CI; update this handoff after
verification.

## Phase 3.7 Tenant Directory — VERIFIED 2026-09-26

Source 873219e0be9e41a7c68ec52e4da604a882dc90c2.
CI 36275843531 SUCCESS six jobs. Backend 458 passed,
3 deselected, 5652 warnings in 90.10s; E2E 3 passed in
9.28s. Frontend lint/typecheck/build, security, platform-admin,
staging-config passed. No migration, head a9c1e3f5b7d0,
104 tables. No frozen docs/ edits.

Standard catalog entry tenant.directory links to
/dashboard/reporting/tenants; read-only preview endpoint
GET /api/reporting/tenants/preview returns no-store. Shared
ReportPayload/CSV/email and ReportActions reused. Report requires
REPORTING.ALL, LEASING, release.reporting.export; active ADMIN
or MANAGER, same org. Managers see only eligible current leases
on their actively assigned properties, not unassigned tenant
contact details. Admin sees all active tenant users, including
those lacking an eligible current lease (clearly labeled) and
current associations, excluding terminated/future and noncurrent
leases, deleted/inactive users/units/properties and foreign orgs.
A tenant with more than one current lease has one association row
per eligible lease. Optional property_id is validated against
live visible properties; other-org/unassigned property probes
fail closed. CSV formula escaping stays server-side.
Four focused backend tests cover isolation, two-property scope,
inactive/future/terminated exclusions, unassigned contacts,
invalid filters, preview no-store, email/CSV and entitlement/
permission revocation. Existing browser E2E smoke remains three
general tests, not dedicated directory tests.

NEXT Tenant Ledger. IMPORTANT: tenant rent invoice payments in
Lease.Payment records and accounting Receipt/ReceiptLine entries
are independent data paths; do not blindly sum both. Charge
amount_paid is a current snapshot, not a dated transaction log.
Investigate real payment/receipt/reversal semantics first and
avoid inventing a historically reconciled running balance or
claiming all payments posted through GL. Securely scope all
tenant/property selection; preserve existing reports/GL.

## Phase 3.7 Tenant Ledger — VERIFIED 2026-09-26

Source a12e0f1af94b7e74e03e9e81988bba98d98cb016,
follow-up security 33902846eab82304299f383001de682081091eec.
First source run 36276282964 SUCCESS: backend 462 passed,
3 deselected; 3 E2E passed. Follow-up source run
36276682654 SUCCESS six jobs: backend 463 passed, 3 deselected,
5898 warnings in 91.44s; E2E 3 passed in 9.50s;
frontend lint/typecheck/build, platform-admin, security and
staging-config passed. Alembic a9c1e3f5b7d0, 104 tables;
no migrations, no frozen docs edits.

Enhanced TAB catalog key tenant.ledger, route
/dashboard/reporting/tenant-ledger and
GET /api/reporting/tenant-ledger/preview (no-store) implement a
CURRENT invoice and standalone-charge balance schedule, not
a historical/reconciled GL ledger. The invoice paid snapshot and
charge paid snapshot are authoritative for their own rows.
Independent Payment and Receipt/ReceiptLine events are not
concatenated because there is no confirmed foreign-key linkage
and doing so could double-count money. VOID invoices excluded.
No invented rent/charge payments or GL postings.
Admin may see same-org historical properties/unallocated charges;
managers are limited to active, nondeleted assigned properties.
Tenant IDs/foreign property filters fail closed. Authenticated
active ADMIN/MANAGER, REPORTING.ALL, LEASING and
release.reporting.export are enforced, with CSV formula escape
and shared email delivery. Follow-up regression requires
ACCOUNTING.CHARGES (matching standalone Charge API permission)
because ledger exposes Charge balances; denial fails closed.
Source tests verify snapshots/no double count, manager/org scope,
bad filters/actor and release/menu revocation plus charge
permission revocation. Current browser E2E remains generic smoke.

Next Tenant Tickler from original Section 38. Original
AppFolio guide defines Tickler as tenant contact information
and most recent event; external reference (check separately):
https://formspal.com/wp-content/uploads/2021/08/appfolio-manager-guide.pdf
Use only actually recorded lease events, tenant/lease notes or
documented milestones; do not invent move-out/notice dates
or claim inferred event activity is a verified external event.
Enforce org/manager assignment and live export permissions.
Then Tenant Unpaid Charges and Unpaid Charges Summary.

## Phase 3.7 Tenant Tickler — VERIFIED 2026-09-26

Source f97b2c9c4078076ebd3c1d19d7107068bf49bb42.
CI 36277065122 SUCCESS all six jobs:
467 backend passed, 3 deselected, 6027 warnings in 92.34s;
3 browser E2E passed in 8.94s.
No migration; Alembic a9c1e3f5b7d0, 104 tables.
No frozen docs/ changes. Scoped tenant contact report takes only
actually recorded lease creation/update/signature/timestamped note
events; does not infer actual move-out/notices from contract dates
or publish private note bodies. Authenticated admin/manager,
manager-assigned live property scope, report/LEASING/export
permissions, standard CSV/email/report page and focused tests.

## Phase 3.7 Tenant Unpaid Charges — VERIFIED 2026-09-26

Source 26cc939f0ca39eb7219b3dad6c3ce4b527ff9a9b.
CI 36277862050 SUCCESS all six jobs:
471 backend passed, 3 deselected, 6212 warnings in 71.33s;
3 browser E2E passed in 9.20s; frontend lint/typecheck/build,
security, platform-admin, staging-config SUCCESS.
No migration; Alembic a9c1e3f5b7d0 / 104 tables.
No frozen docs/ changes.

New standard catalog key tenant.unpaid_charges links to
/dashboard/reporting/unpaid-charges. API
GET /api/reporting/unpaid-charges/preview returns no-store;
server CSV/email via canonical ReportPayload/ReportActions.
Current positive (Charge.amount - Charge.amount_paid) snapshot
from standalone organization-scoped Charge only, NOT rent invoices
or invoice late fees. Fully paid, credit/overpaid, inactive/deleted
and cross-org charges excluded. Recorded charge balances are
not historical account reconciliation or separate GL posting.
Positive propertyless org charges are explicitly labeled for
ADMIN only; managers see only live actively assigned properties.
Active tenant and property scope, tenant_id/property_id probe
guards, REPORTING.ALL, ACCOUNTING.CHARGES and LEASING
permissions plus release.reporting.export gate enforced; CSV
formula escaping. Focused tests include arithmetic/no double
counting, cross-org and manager isolation, foreign filters, denied
roles/permissions, no-store preview, CSV/email/revoked export.
The existing generic three browser smoke tests are NOT dedicated
feature-specific E2E for Unpaid Charges.

NEXT exact original Section 38: Tenant Unpaid Charges Summary
(catalog tenant.summary); aggregate ONLY these same authorized
standalone positive Charge snapshot rows per tenant, reuse service
scope and CSV/email, never mix in rent invoices or assume
GL-reconciled collections. Follow with Property & Unit reports.
Do not skip and do not reimplement verified tenant reports.

## Exact next work: continue, don't stop at phase boundary

1. Read this root handoff; verify branch HEAD and latest full CI.
   Do not repeat verified reporting/1099/letters/owner packets
   or any tenant detail report through Unpaid Charges.
2. Implement Tenant Unpaid Charges Summary next, reusing
   existing scoped tenant_unpaid_charges service as the
   authoritative data source, grouping current positive Charge
   balances per tenant. Preserve org/assignment/security
   checks, LEASING + ACCOUNTING.CHARGES, REPORTING.ALL and
   release.reporting.export for preview, CSV and email.
   Add focused tests; no historical or reconciled-GL claim.
3. Then original Property & Unit, Owner/Vendor, Accounting,
   Transaction reports per Section 38, with prerequisite checks.
4. Bounded product commits + tests then GitHub Actions;
   VERIFIED only after all six jobs succeed. If CI fails, fix
   autonomously before next feature. Record exact source SHA,
   CI run/test counts, migrations and next task in this ROOT
   handoff. Do not modify frozen docs/, main or create branches.
5. External Avalara/IRS acceptance needs operator credentials;
   preserve 1099 internal no-submission boundary. No Work request.

## Session start for successor

Continue yasirskhan/property-platform branch
chatgpt/checkpoint-005-safety. Read complete root handoff and
verify actual branch HEAD/CI. Last VERIFIED product source
26cc939f0ca39eb7219b3dad6c3ce4b527ff9a9b, GitHub CI
36277862050 SUCCESS (471 backend passed, 3 deselected,
6212 warnings; 3 E2E passed in 9.20s; all six jobs green).
Alembic a9c1e3f5b7d0 / 104 model tables.
Tenant Tickler and standalone Tenant Unpaid Charges detail VERIFIED;
do not repeat. Exact next original task is Tenant Unpaid Charges
Summary (catalog tenant.summary) using only scoped positive Charge
snapshots and verified delivery/gates. Then Property & Unit reports.
Commit+CI, update root handoff per batch, frozen docs unchanged;
no main/new branch/force-push/Work request.
