# AI_HANDOFF.md — Property Platform, 2026-09-26

**READ THIS WHOLE FILE FIRST.** This is the repo-ROOT authoritative session handoff;
it does NOT belong under docs/. Refresh after every meaningful CI-verified batch.
Do not ask Yasir to repeat verified state. Never paste real tax secrets/TINs.

- Private repository: `yasirskhan/property-platform`
- ONLY working branch: `chatgpt/checkpoint-005-safety`. Do not edit `main`,
  create a branch, force-push, or merge the draft PR without permission.
- Last VERIFIED **product source**: `4a54c602966a795a8b399893f3d5fc46a6324ab3`
- Source GitHub Actions run **36270979448: SUCCESS, all six jobs** (backend,
  frontend, platform-admin, security, authenticated E2E, staging-config).
  Backend: **432 passed, 3 deselected, 4531 warnings in 82.97s**.
  E2E: **3 passed in 8.59s**. Lint, typecheck, production build, security
  and staging: SUCCESS. These counts apply to this exact source commit only.
  This handoff update itself is docs-only; TESTS NOT RUN locally. Verify
  current branch HEAD and latest CI before continuing.
- Alembic head: **f8c0d2e4a6b9**. SQLAlchemy expected model tables: **103**.
  Previous head e7b9c1d3f5a8 / 103 tables. Schema/test guards changed
  with the tax-profile revision migration; no new model table. All three
  PostgreSQL/bootstrap/legacy CI paths passed.
- Phase 3.7 Reports + Universal Attachments: IN PROGRESS.
  **Latest completed batch: redacted provider status + explicit admin sandbox dry-run UI. VERIFIED.**
- **Exact NEXT original-plan task: Generate 1099 Forms & Reports,
  verify and implement 1099-MISC rents sandbox mapping, then provider result/receipt
  persistence without enabling production filing. Full filing/recipient copies remain
  NOT IMPLEMENTED.** Do not repeat verified preflight,
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
- Current verified provider mapping is deliberately only 1099-NEC
  NONEMPLOYEE_COMPENSATION. 1099-MISC rents fails closed with 422 until
  its official provider mapping is separately verified. Tests mock all
  external requests; CI did NOT contact Avalara or claim sandbox credentials.
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

**CURRENTLY NOT IMPLEMENTED**: provider-hosted e-W9 consent/signature,
backend PDF malware scanning/retention purge, completed 1099-NEC/MISC
reportable-payment identification, review and approval, official IRS
tax-year template mapping, TCC / provider credentials, transmission,
filing receipts, corrections, recipient copies or e-delivery. Do not
claim any of these verified or enable "file" from a prototype.

## Exact next work: continue, don't stop at phase boundary

1. Read entire root handoff, fetch actual HEAD/latest CI. Do not
   repeat verified preflight, manual 1099 review, encrypted tax
   profiles/W-9, revision checks, redacted internal register.
2. NEXT bounded batch: verify 1099-MISC rents field mapping against current
   official Avalara API documentation/specification. Enable it only when exact
   provider fields are confirmed; tests must keep dryRun=true and all filing/
   delivery flags false. If official mapping remains ambiguous, fail closed.
3. Then add redacted persistence of provider dry-run attempt/result metadata
   (provider, validation status, provider-side opaque ID only if safe, timestamps)
   without raw response/TIN/name/address or any claim of IRS acceptance. A real
   Avalara subscription, sandbox credentials and issuer ID remain external
   prerequisites for an actual sandbox call; never put secrets in source/chat. Avalara 1099/W-9 publishes
   OAuth client-credentials API, sandbox environment, and 1099
   form creation/readiness endpoints; active subscription and
   server-only secrets are required. IRIS taxpayer-portal CSV
   requires an IRIS TCC and exact tax-year formatting guidelines
   from authenticated portal; A2A requires client ID, approved
   schema and ATS testing. Do not invent 2026 IRIS CSV, output
   FIRE, or mark simulated provider responses as filing.
   https://www.irs.gov/filing/e-file-information-returns-with-iris
   https://developer.avalara.com/products/avalara-1099-and-w9/api/
4. The original docs/PLAN_GAPS.md C9 assigns actual provider
   transmission, recipient delivery and corrections to Phase
   4.5. Continue safe Phase 3.7 form/report preparation but do
   not bypass the roadmap or claim 1099 filing COMPLETE while
   external integration/recipient delivery are unverified.
   Only after complete 1099 original-plan dependencies are
   accounted for proceed to Section 38 Letters, Owner Packets,
   tenant/property/owner/accounting reports in order.
5. Include focused regression tests with each bounded source
   commit, use GitHub Actions verification only AFTER commit
   as user authorized; don't call VERIFIED until all six jobs
   pass. Fix red CI autonomously; halt after three repeats
   of the same assertion. Update root handoff after meaningful
   verified batches with exact numbers, SHA and Alembic head.
   Frozen docs/ unchanged without explicit authorization,
   no main or new branches, no unverified live tax filings.

## Session start for successor

Continue yasirskhan/property-platform on `chatgpt/checkpoint-005-safety`.
Read complete repo-root AI_HANDOFF.md; verify current HEAD and CI.
Last VERIFIED product source `4a54c602966a795a8b399893f3d5fc46a6324ab3`,
CI 36270979448 SUCCESS (432 backend passed, 3 deselected,
4531 warnings; E2E 3 passed; all six jobs success).
Alembic `f8c0d2e4a6b9`, 103 tables. Manually sourced NEC/MISC
review/approval, redacted internal CSV, encrypted W-9/tax profiles,
revision lock, redacted no-submission provider preflight are
VERIFIED. Full IRS/approved-provider 1099 filing and recipient
copies are NOT IMPLEMENTED. Immediate batch: verify and implement 1099-MISC rents mapping only from
current official Avalara docs/spec; remain sandbox dry-run only. Preserve original Phase 3.7/4.5 dependency order and
frozen docs. Bounded code+CI, no Work/main/new branch.
