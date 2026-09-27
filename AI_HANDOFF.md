# AI_HANDOFF.md — Property Platform, 2026-09-26

**READ THIS WHOLE FILE FIRST.** This is the repo-ROOT authoritative session handoff;
it does NOT belong under docs/. Refresh after every meaningful CI-verified batch.
Do not ask Yasir to repeat verified state. Never paste real tax secrets/TINs.

- Private repository: `yasirskhan/property-platform`
- ONLY working branch: `chatgpt/checkpoint-005-safety`. Do not edit `main`,
  create a branch, force-push, or merge the draft PR without permission.
- Last VERIFIED **product source**: `05c8e4e73a9e4c93088ddf2773318179dfd0b592`
- Source GitHub Actions run **36287053275: SUCCESS, all six jobs** (backend,
  frontend, platform-admin, security, authenticated E2E, staging-config).
  Backend: **515 passed, 3 deselected, 7963 warnings in 107.66s**.
  E2E: **3 passed in 8.99s**. Lint, typecheck, production build, security
  and staging: SUCCESS. These counts apply to this exact source commit only.
  This handoff update itself is docs-only; TESTS NOT RUN locally. Verify
  current branch HEAD and latest CI before continuing.
- Alembic head: **d2f4a6c8e0b1**. SQLAlchemy expected model tables: **108**.
  Previous head c1e3f5a7b9d2 / 107 tables. One explicit
  unit_inspection_records table added; PostgreSQL/bootstrap/legacy CI paths passed.
- Phase 3.7 Reports + Universal Attachments: IN PROGRESS.
  **Latest completed batch: Owner Directory. VERIFIED.**
- **1099 Phase 3.7 internal preparation/security is VERIFIED through local preflight,
  NEC/MISC sandbox payload mapping, explicit consent, redacted status/history and
  no-submission guarantees. Actual external sandbox acceptance requires operator
  Avalara subscription/credentials/issuer; production filing/IRS acceptance and
  recipient copies remain NOT IMPLEMENTED and belong to the external provider path.**
- **Exact NEXT original-plan task: Vendor Directory (Owner Statement already VERIFIED). Owner Directory and earlier Phase 3.7 reports are VERIFIED.**
  Tenant Delinquency, Security Deposit Funds Detail, Tenant Directory, Tenant Ledger, Tenant Tickler, Tenant Unpaid Charges and Unpaid Charges Summary, plus Owner Packets VERIFIED. Do not repeat verified preflight,
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
| Tenant Unpaid Charges Summary | 1f901348d89fd173794edf651b0a143b63f5dc05 | 36278186270 | 474 backend passed / 3 E2E |
| Property Budget Comparison | 21378853fb7d7ccf31f5b62dadbccf9367e36266, c5dbc67374ebcf7d31f7b6f9ff086af47c6e50b9 | 36278686191 | 478 backend passed / 3 E2E |
| Property Budget Detail | 6b4805ee1ff99d7340026ac5322e03a58408df70 | 36279106102 | 481 backend passed / 3 E2E |
| Property Gross Potential Rent (read-only) | cb85f82c55090450798b5ef3fb941dc9bd97538b | 36279627346 | 485 backend passed / 3 E2E |
| Lease Expiration Detail / Monthly Summary | 08fb55bb470e94e1422cd6b601a28794151c1f46, d818dfbb5652c3f2d0735fa1b891a59c3be38ee2 | 36280075299 | 489 backend passed / 3 E2E |
| Property Directory | 992c949d2ae079f424a8f16bbb8fa131cadf1048 | 36280429259 | 492 backend passed / 3 E2E |
| Property Group Directory | b246d698b2da335796f9aca58ca4d067fb939cc0, 70900226383d4421193ca8f7c76da465369e01f9 | 36280886202 | 496 backend passed / 3 E2E |
| Property Performance | 5c3149c27398b2c321062263795149a594ff63ab | 36283808654 | 499 backend passed / 3 E2E |
| Rent Roll | 8636280f378db4eda2679fee75e699bae139222a, 47fddcdd761fcc434c8e8b60afca87d31800e4f0 | 36284240929 | 502 backend passed / 3 E2E |
| Unit Directory | c1f47e197a8934634b88c77d5a04f0c97609c3a7, a608b1b2e86f2378df825c53d864413c2139197a | 36284770912 | 505 backend passed / 3 E2E |
| Unit Inspection | deb6019ab889c03e8ce5a208da271cb16e16d2a5, 52369dd6ae3237fa4695d1407750c18a3847959e | 36285989151 | 509 backend passed / 3 E2E |
| Unit Vacancy Detail | e61115fd1d0a544c7cddbfd0d8e22df6054ee8da, 0567aa87b894baf41238b61838566b71bc885a9b | 36286373738 | 512 backend passed / 3 E2E |
| Owner Directory | 22bc827577e960a1e4a66203bebe14b7638df58c, 96d731902ac3b3126ab8d93f7d4881a551795609, 05c8e4e73a9e4c93088ddf2773318179dfd0b592 | 36287053275 | 515 backend passed / 3 E2E |
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

## Phase 3.7 Tenant Unpaid Charges Summary — VERIFIED 2026-09-26

Source 1f901348d89fd173794edf651b0a143b63f5dc05.
GitHub CI 36278186270 SUCCESS all six jobs: backend
474 passed, 3 deselected, 6350 warnings in 91.87s;
authenticated E2E 3 passed in 9.20s; frontend lint/typecheck/
production build, security, platform-admin, staging-config GREEN.
No migration, Alembic a9c1e3f5b7d0 / 104 tables unchanged.
Frozen docs/ unchanged. Previous handoff-only CI 36278139301
was CANCELLED by the new product push, not a test failure.

Standard catalog key tenant.summary now visibly titled
"Tenant Unpaid Charges Summary" and links to
/dashboard/reporting/unpaid-charges-summary. GET
/api/reporting/unpaid-charges-summary/preview returns no-store.
Service app/services/tenant_unpaid_summary.py reuses only
already-authorized positive Charge detail report rows,
aggregates by tenant and property (propertyless ADMIN-only
charges separate), computes count/billed/paid/outstanding.
No RentInvoice/GL addition or double counting; current
recorded Charge.amount_paid snapshots, not historical cash.
Admin/manager organization and assigned-property scope,
tenant_id and property_id validation, REPORTING.ALL,
ACCOUNTING.CHARGES, LEASING and release.reporting.export
preserved through shared detailed service/routers.
Server CSV/email canonical formula-safe ReportActions reused.
Three focused tests cover reconciled-to-detail grouping, org and
manager scope, filters, permissions and export gate. Existing three
E2E browser tests generic, not dedicated summary UI tests.

NEXT original Section 38: Property & Unit > Budget Comparison,
then Budget Detail, Gross Potential Rent, Lease Expiration
Detail/Summary, directories and other listed property reports.
REQUIRED RESEARCH: the current backend models inventory has NO
PropertyBudget or other persisted budget baseline; do NOT invent
budget numbers from estimated rent or assume current GL is a
budget. First add an explicitly editable, authorized budget data
source or identify an existing verified one before comparing
actuals, with migration/tests and reporting basis disclosure.
Preserve read-only GL and assignment boundaries.

## Phase 3.7 Property Budget Comparison — VERIFIED 2026-09-26

Product commit 21378853fb7d7ccf31f5b62dadbccf9367e36266;
focused test-only assertion correction
c5dbc67374ebcf7d31f7b6f9ff086af47c6e50b9.
Final CI 36278686191 SUCCESS all six jobs: backend
478 passed / 3 deselected / 6557 warnings in 80.69s;
E2E 3 passed in 7.86s; frontend lint/typecheck/build,
security, platform-admin and staging-config SUCCESS.
Superseded source 36278666804 and prior handoff-only CI
36278523767 CANCELLED, not valid full-green evidence.
Migration b0d2f4a6c8e1 adds property_budget_lines,
105 model tables; PostgreSQL/legacy/fresh bootstrap guards
updated and passed. No unrelated frozen docs/ edits.

Budget target model PropertyBudgetLine is organization/property/
income-or-expense GL-account/year/month-scoped, unique by scope.
No existing budget sources existed, so admin explicitly enters
nonnegative monthly amounts via restricted PUT
/api/reporting/property-budgets. GET lists authorized property/year
targets. Only active org ADMIN may write; active ADMIN/MANAGER with
REPORTING.ALL, PROPERTIES.ALL and ACCOUNTING.GL_ACCOUNTS
may read if current property scope allows; managers need live
assignment. Actor, account, property and org validated.
Budget changes are metadata-audited; never post GL transactions.
Budget Comparison enhanced TAB now links to
/dashboard/reporting/budget-comparison, which has admin budget
entry and read-only comparison, CSV/email via existing ReportActions.
GET /api/reporting/budget-comparison/preview is no-store and
requires normal report/menu/export gates. Source service sums
actual dated, property-tagged posted GL entries, including
original and reversal postings; INCOME actual credit-minus-debit,
EXPENSE debit-minus-credit, positive variance favorable.
Only rows with explicitly configured budget targets are
included; missing target is NOT assumed zero, property estimated
rent is NOT a fabricated budget. CROSS-ORG entries and
out-of-scope properties/accounts are excluded. Comparison
refuses organization CASH-basis setting rather than presenting
accrual GL movements as CASH actuals; only ACCRUAL currently
supported. No historical cash basis or journal modifications.
Focused tests cover budget amount math, income/expense favorable
sign, isolation, manager assignment, invalid account/filters,
CASH refusal, audit, no new GL entries, report preview/CSV/email,
no-store and release/menu revocation. Generic E2E smoke 3,
not dedicated budget interactive tests.

NEXT original Property & Unit task: Budget Detail. Reuse the
new explicit monthly PropertyBudgetLine records and exactly
the same property/account scope, but present an account-wise
12-month detail with unconfigured months blank (not silently zero)
and annual total over recorded months. No posted actuals needed
and no separate budget storage. Then Gross Potential Rent and
lease-expiration reports per original Section 38 order.

## Phase 3.7 Property Budget Detail — VERIFIED 2026-09-26

Source 6b4805ee1ff99d7340026ac5322e03a58408df70.
CI 36279106102 SUCCESS all six jobs: backend 481 passed,
3 deselected, 6715 warnings in 99.70s; browser E2E 3
passed in 8.81s; frontend lint/typecheck/build, security,
platform-admin, staging-config SUCCESS. No new migration:
b0d2f4a6c8e1, 105 model tables. Frozen docs/ unchanged.

Standard Property & Unit report catalog property.budget_detail
links to /dashboard/reporting/budget-detail; backend preview
GET /api/reporting/budget-detail/preview is no-store. Reuses
existing PropertyBudgetLine by org/property/income-or-expense GL
account/calendar year/month; property scope, ADMIN/MANAGER
assignment, REPORTING.ALL / PROPERTIES.ALL /
ACCOUNTING.GL_ACCOUNTS and release.reporting.export gates
rechecked. Each account row shows all 12 months, explicitly
unconfigured blank (not invented zero), recorded zero as zero,
configured annual sum and number of configured months.
No actual GL movements, cash-basis inference, or posting;
budget-only output works for ACCRUAL and CASH.
Existing ReportActions server CSV/email and formula escaping;
three focused regression tests cover blanks/zero/sums, CASH
comparison distinction, org/manager isolation, filters,
permission/release revocation and preview/delivery.
Three generic authenticated browser smoke tests, NOT
three dedicated budget UI tests.

NEXT Gross Potential Rent (GPR) report. IMPORTANT already
VERIFIED app/services/gpr_posting.py implements org-scoped
GPR candidate calculation and posting, keyed to Unit.monthly_rent
(market) and active Lease.monthly_rent (scheduled), plus
loss/gain and posted unit/month marker. The historical candidate
is derived from CURRENT editable unit/lease config, not a frozen
historical rent snapshot; do not claim as-of historical truth.
Post GPR workflow already verified (parity accounting.gl.post_gpr
marked built); do not reimplement posting. Read actual source,
scope manager to live assigned properties BEFORE calling
lease helper, distinguish candidate projected vs posted GPR.
No GL writes in report. Verify what posted source transactions
record and allow reversals, no double count.

## Phase 3.7 Gross Potential Rent report — VERIFIED 2026-09-26

Product commit cb85f82c55090450798b5ef3fb941dc9bd97538b;
CI 36279627346 SUCCESS all six jobs. Backend 485 passed,
3 deselected, 6841 warnings in 86.07s; authenticated E2E
3 passed in 8.94s. Frontend lint/typecheck/build, security,
platform-admin, staging-config GREEN. No migration:
Alembic b0d2f4a6c8e1 / 105 tables. Frozen docs/ untouched.
Previous handoff-only CI 36279482610 was superseded/cancelled,
not evidence of a source failure.

Enhanced catalog entry property.gross_potential_rent is linked at
/dashboard/reporting/gross-potential-rent. Read-only preview
GET /api/reporting/gross-potential-rent/preview sets no-store,
and canonical server CSV/email delivery reuses shared
ReportActions and formula-safe CSV renderer.
Service app/services/gpr_report.py reuses verified
gpr_posting.month_bounds/_active_lease_for_month logic,
without invoking post_gpr or writing GL.
Per active live visible unit with positive CURRENT market
Unit.monthly_rent, the reporting-month overlap of ACTIVE lease
determines CURRENT contract scheduled amount, vacancy, and
loss/gain. Multiple overlapping active leases fail closed.
An old month is NOT a frozen historical rent snapshot.
Posted GPR JOURNAL_ENTRY source/unit/month transaction markers
are separate from these changing current-config estimates;
reversed original GPR markers and reversal IDs are distinguished.
No posted accounting *amount* or reconciled GL income claimed,
no merger of projected amounts with ledger postings.
ADMIN/MANAGER only; visible_budget_property verifies active user,
same-org, property ID, live manager assignment and
REPORTING.ALL/PROPERTIES.ALL/ACCOUNTING.GL_ACCOUNTS.
Additional LEASING and ACCOUNTING.JOURNAL_ENTRIES permission
required before lease and journal reads. REPORTING.ALL and
release.reporting.export rechecked on preview/export/email.
Foreign and unassigned property ID probes fail closed.
4 focused new regression tests: occupied/vacant amount,
old-month/current rent correction, original/reversal marker,
overlap and invalid input, organization/manager visibility,
no new GL entries, CSV formula escaping, preview no-store,
email and permission/export revocation. Existing 3 E2E browser
smoke tests are general, not dedicated interactive GPR tests.

NEXT ORIGINAL Section 38: Lease Expiration Detail,
then Lease Expiration Summary by Month, then Property
Directory. Current Lease.end_date and status are contract
data and do not prove actual move-out or renewal. Build
scoped read-only detail and aggregates from authorized
lease/unit/property records, no invented tenant status or
GL changes. Reuse REPORTING.ALL/LEASING, property
visibility and shared CSV/email. Include focused tests.

## Phase 3.7 Lease Expiration Detail and Summary — VERIFIED 2026-09-26

Product source 08fb55bb470e94e1422cd6b601a28794151c1f46;
summary-link/UI route correction d818dfbb5652c3f2d0735fa1b891a59c3be38ee2.
Final full CI 36280075299 SUCCESS: backend 489 passed,
3 deselected, 7024 warnings in 100.03s; browser E2E 3 passed
in 6.11s; frontend lint/typecheck/build, platform admin,
security, staging-config GREEN. Initial code run 36280041204
and superseded docs CI 36279978195 cancelled by newer pushes;
they are NOT full CI evidence. No migration, Alembic
b0d2f4a6c8e1 and 105 model tables. Frozen docs/ unchanged.

Both standard catalog keys property.lease_expiration_detail and
property.lease_expiration_summary have working customer links.
Detail /dashboard/reporting/lease-expirations, monthly summary
/dashboard/reporting/lease-expirations/summary opens directly in
summary mode. Shared selectable UI route displays date range,
optional property filter, scheduled end dates; generic server
CSV/email via ReportActions. Preview
GET /api/reporting/lease-expirations/preview sets no-store,
strictly allowlists report_key and excludes it from filters.
Service app/services/lease_expiration_report.py reuses only
actual Lease.end_date (ACTIVE or EXPIRED recorded statuses).
TERMINATED/CANCELLED/DRAFT omitted; do not interpret scheduled
end as verified notice, renewal or move-out. Summary groups exactly
the same authorized detail rows by scheduled-end month and
property, counts lease IDs and sums recorded monthly contract rent
(not earned revenue or cash receipts). No GL writes/migrations.
Only active ADMIN/MANAGER and live org-scoped, nondeleted property,
unit, tenant records. Managers only live assigned properties;
cross-org tenant linkage refused. REPORTING.ALL/LEASING/
PROPERTIES.ALL plus release.reporting.export enforced before
preview, export and email; invalid date/filter scope fails closed.
User/customer email names and property text CSV formula-escaped.
Four focused tests cover status inclusion/exclusion, monthly
sums, foreign/unassigned scope, manager/tenant role, invalid
parameters, revocation, no GL writes and CSV/email. Three
general authenticated browser smoke tests, not dedicated report
workflow E2E.

NEXT ORIGINAL SECTION 38: Property Directory, then Property Group
Directory, Property Performance, Rent Roll, Unit Directory,
Unit Inspection, Unit Vacancy Detail. Models currently expose
Property/Unit and PropertyAssignment; NO verified PropertyGroup
model found yet. Do not invent a group classification: inspect
existing schema before building grouping report; add explicitly
maintained group membership if original feature requires it.

## Phase 3.7 Property Directory — VERIFIED 2026-09-26

Source 992c949d2ae079f424a8f16bbb8fa131cadf1048,
full CI 36280429259 SUCCESS six jobs: 492 backend passed,
3 deselected, 7112 warnings in 79.68s; authenticated E2E
3 passed in 9.11s; frontend lint/typecheck/build, security,
platform-admin and staging-config SUCCESS. No migration:
b0d2f4a6c8e1 and 105 model tables; frozen docs/ unchanged.
Superseded handoff-only CI 36280378419 cancelled; not
a product failure.

Catalog standard property.directory links to
/dashboard/reporting/property-directory. New service
app/services/property_directory.py uses only recorded
active, undeleted property identity/type/address and count
of active, undeleted Unit records. No inferred occupancy,
collected rent, owner/tenant contact or GL movement.
Admin sees own-org active property records; manager sees
only live actively assigned properties. Role status, org,
REPORTING.ALL/PROPERTIES.ALL and release.reporting.export
checked for preview/export/email. Optional property ID and
PropertyType enum filters validated; foreign/unassigned
ID probes fail closed. GET
/api/reporting/property-directory/preview no-store.
Shared ReportActions uses server-rerendered CSV/email,
CSV formula escaping; three focused backend tests for
counts, active/inactive, org/manager scope, bad params,
role/menu/export revocation, no ledger writes and delivery.
Three E2E tests are existing generic smoke, not dedicated
directory UI tests.

Exact next original Phase 3.7 report Property Group
Directory. Critical dependency: original PROJECT_MASTER
Section 15 explicitly says "Named groups for filtering,
access, reporting"; parity item properties.groups is
scheduled Phase 3.5 and settings.property_groups scheduled.
No PropertyGroup/PropertyGroupMembership model found in
backend/app/models or property.py. Properties page still has
a disabled release.properties.groups compatibility slot;
feature definition specifies entitlement property_groups,
PROPERTIES.GROUPS menu permission and org config gate.
Do NOT invent membership based on property name/type.
Build explicitly authorized named-group CRUD and real
org/property membership then report from persisted groups.
Preserve Hybrid Capability Gating and manager assignment;
report must not leak hidden member properties and should
mark filtered membership counts clearly. Migration + guards
and tests required if new group tables are added.

## Phase 3.7 Property Group Directory — VERIFIED 2026-09-26

Source b246d698b2da335796f9aca58ca4d067fb939cc0,
frontend type correction 70900226383d4421193ca8f7c76da465369e01f9.
Final CI 36280886202 SUCCESS all six jobs: 496 backend
passed, 3 deselected; E2E 3 passed in 10.46s.
Migration c1e3f5a7b9d2 adds property_groups and
property_group_memberships; 107 SQLAlchemy tables. Original
property groups prerequisite now persisted as explicit org-scoped
named groups and memberships; no invented auto-grouping.
Only authorized ADMIN can edit, scoped MANAGER sees currently
assigned property memberships. Hybrid release.properties.groups,
commercial entitlement, PROPERTIES.GROUPS and SETTINGS safeguards
apply. Canonical report preview, server CSV/email, permission/export
checks, formula-escaped CSV and manager scope included. No frozen
docs/ changes. Earlier source runs superseded/cancelled.

## Phase 3.7 Property Performance — VERIFIED 2026-09-26

Source 5c3149c27398b2c321062263795149a594ff63ab.
GitHub CI 36283808654 SUCCESS all six jobs: backend
499 passed, 3 deselected, 7403 warnings in 109.00s;
E2E 3 passed in 7.31s; frontend lint/typecheck/build,
platform-admin, security, staging-config green.
No migration from group head c1e3f5a7b9d2, 107 tables.
Frozen docs/ not changed; planning parity status not advanced.

Enhanced Property & Unit catalog key property.performance
links to /dashboard/reporting/property-performance. A mandatory
property ID and calendar year scope recorded GL income and
expense entries, including original and reversal postings.
Totals are credit-minus-debit for income and debit-minus-credit
for expenses; posted net is income less expense. Propertyless
company-level GL entries, other property/organization entries,
and asset/liability/equity lines excluded. Archived GL accounts
remain included when actual posted activity exists.
Role and live assigned-property checks reuse the VERIFIED
visible_budget_property helper: only org active ADMIN/MANAGER,
REPORTING.ALL, PROPERTIES.ALL, ACCOUNTING.GL_ACCOUNTS.
Explicit ACCRUAL basis only, CASH refuses rather than inventing
cash flow; no ROI, NOI, occupancy, rent roll or GL postings inferred.
Preview GET /api/reporting/property-performance/preview no-store;
existing ReportPayload and ReportActions provide server CSV/email
with release.reporting.export and formula escaping.
Three focused tests cover 2026 journal/reversal sums, org and
manager isolation, CASH refusal and bad parameters, no GL writes,
catalog and no-store preview/CSV/email/revoked export.
Three existing generic E2E smoke tests, not dedicated
Property Performance UI tests.

NEXT original Section 38: Rent Roll report, then Unit Directory,
Unit Inspection and Unit Vacancy Detail. Current Unit.monthly_rent
represents CURRENT configured market rent and Lease.monthly_rent
is CURRENT recorded contract rent; Lease.status and dates are
not immutable historical occupancy. Build a clearly qualified
current-config rent roll based on active scoped units and live
eligible leases. Do not claim collected rent or retroactive
historical occupancy, synthesize tenant links, ignore overlapping
active leases or bypass LEASING/property access. Only recorded
contract status/date, not live collection. Include focused tests,
preview no-store, shared CSV/email and existing export gate.
No new migrations needed if reading current tables.

## Phase 3.7 Rent Roll — VERIFIED 2026-09-26

Implementation source 8636280f378db4eda2679fee75e699bae139222a;
frontend filter typing correction
47fddcdd761fcc434c8e8b60afca87d31800e4f0.
First source CI 36284142345 reported one TypeScript error:
union optional property_id cannot be assigned to Record<string,string>;
its backend/E2E were canceled after the correction. Final
CI 36284240929 SUCCESS all six jobs: backend 502 passed,
3 deselected, 7536 warnings in 99.29s; E2E 3 passed in 7.53s;
frontend lint/typecheck/production build, security, platform-admin
and staging-config SUCCESS. No migration, Alembic c1e3f5a7b9d2
and 107 model tables. Frozen docs/ unchanged.

Enhanced catalog property.rent_roll links to
/dashboard/reporting/rent-roll. GET
/api/reporting/rent-roll/preview sets no-store.
Only current, active/undeleted org-scoped properties and unit
records are reported. Recorded Unit.monthly_rent is current
configured market rent; current eligible ACTIVE Lease with
recorded start<=today<=end gives Lease.monthly_rent and
same-org active TENANT association. No eligible lease is labeled
"not verified vacancy", not a physical occupancy claim.
Overlapping eligible active leases and invalid cross-org
tenant links fail closed rather than selecting a contract
or fabricating vacancy. Ended or terminated leases excluded.
Staff ADMIN/MANAGER, live property assignments, REPORTING.ALL,
PROPERTIES.ALL, LEASING, release.reporting.export checked;
optional property filter forbids foreign/unassigned ID probing.
No historical rent, GL income, collected payments or bank
activity inferred; no GL edits or migrations.
ReportPayload, CSV formula escaping and shared ReportActions
CSV/email delivery reused. Three focused regression tests
cover current market/contract distinction, no-lease/ended/
inactive unit, foreign and manager scopes, duplicate leases,
invalid tenant link, no GL writes, permissions, export
revocation and no-store preview/CSV/email. E2E 3 are generic
browser smoke tests, not dedicated Rent Roll E2E.

NEXT original Section 38 Unit Directory. Use recorded
active/undeleted Unit rows (layout, current configured rent,
deposit, availability flag, listing flag) from scoped active
Property; do NOT infer physical occupancy from is_available
or add unrelated lease/GL reads. Reuse existing catalog,
ReportPayload, role/menu/export gates and CSV/email delivery.

## Phase 3.7 Unit Directory — VERIFIED 2026-09-26

Source c1f47e197a8934634b88c77d5a04f0c97609c3a7;
test-only wording correction a608b1b2e86f2378df825c53d864413c2139197a.
First CI 36284591238 backend 504 passed, 1 failed,
3 deselected: test incorrectly expected literal "vacancy"
in a correctly worded disclaimer. Frontend/security/admin passed;
staging and E2E skipped. Only the incorrect assertion changed.
Final CI 36284770912 SUCCESS all six jobs:
505 backend passed, 3 deselected, 7629 warnings in 105.81s;
E2E 3 passed in 9.15s; frontend lint/typecheck/build,
security, platform-admin, staging-config green.
No migration; head c1e3f5a7b9d2, 107 model tables.
No frozen docs/ changes.

Standard catalog property.unit_directory links to
/dashboard/reporting/unit-directory. GET
/api/reporting/unit-directory/preview no-store.
Service app/services/unit_directory.py reads actual active,
undeleted Unit rows of current active, undeleted Property.
Includes only configured layout, market rent, security/pet
deposits/rent and editable is_available/is_listed and
available_from inventory flags. Flags explicitly do NOT
establish physical vacancy, occupancy, tenant or payment.
ADMIN/MANAGER only; managers only live assigned properties;
REPORTING.ALL, PROPERTIES.ALL, PROPERTIES.UNITS and
release.reporting.export gate rechecked for preview/CSV/
email. Optional property filter rejects foreign/unassigned
IDs. Existing ReportPayload, server CSV/email and formula
escaping reused; no GL changes, source screenshots or
new unrelated entitlements. Three focused tests cover
inventory values, inactive/deleted and foreign inventory,
manager/tenant scope, permission/gate revocation, no GL
writes, server delivery and no-store. Three generic
E2E browser tests (not dedicated Unit Directory interaction).

NEXT: original Section 38 Unit Inspection report.
As of this source there is no UnitInspection or
recorded inspection result model; full mobile/offline/
photo/checklist inspections are separately scheduled
in Phase 5, not verified. Do NOT fabricate inspections
from Unit.is_available, WorkOrder, tenant notes or photos.
If needed for Phase 3.7 report, pull forward only a
minimal explicit authorized inspected-date/unit/condition
and finding-record prerequisite, add scoped model/migration
and tests, and clearly differentiate it from Phase 5
inspection workflow. Unit Vacancy Detail follows Unit
Inspection in the original Section 38 order.

## Phase 3.7 Unit Inspection — VERIFIED 2026-09-26

Product implementation deb6019ab889c03e8ce5a208da271cb16e16d2a5;
focused test-only correction
52369dd6ae3237fa4695d1407750c18a3847959e.
First CI 36285181154 backend 507 passed / 2 failed /
3 deselected: direct route test omitted FastAPI Query default
and foreign-org test expected a generic permission error
instead of scoped "Property not found". Corrected tests
without weakening access control. Full CI 36285989151
SUCCESS all six jobs: backend 509 passed, 3 deselected,
7736 warnings in 109.67s; authenticated browser E2E
3 passed in 9.30s. Frontend lint/typecheck/build,
platform-admin, security and staging green. Three E2E
tests are the generic smoke flow, NOT dedicated inspection UI tests.

Migration d2f4a6c8e0b1 adds one
unit_inspection_records table; 108 model tables. New
app/models/unit_inspection.py, service
app/services/unit_inspections.py, router
app/routers/unit_inspections.py and related schemas.
The report is STANDARD property.unit_inspection at
/dashboard/reporting/unit-inspections with no-store preview
GET /api/reporting/unit-inspections/preview and shared
CSV/email ReportActions. Records are explicitly staff-entered,
append-only date/condition/findings linked to a real visible,
active, undeleted unit/property; creation is audited.
No record does NOT imply an inspection passed. This is
NOT a Phase 5 mobile/offline/photo/checklist inspection.
No work order, inventory flag or tenant note is promoted
to a verified inspection; no GL mutations.
Admin/manager only; manager requires live assignment.
REPORTING.ALL, PROPERTIES.ALL, PROPERTIES.UNITS, and
release.reporting.export rechecked for preview, CSV and
email. Foreign/unassigned property/unit IDs fail closed.
Four focused tests validate explicit rows, empty report,
audit, no GL writes, org/manager isolation, role/permission
revocation, invalid dates and recorded conditions, CSV
formula escaping, preview/export/email and gate revocation.
Frozen docs/ unchanged and parity metadata not advanced.

NEXT Unit Vacancy Detail. Existing verified Rent Roll
already distinguishes CURRENT eligible ACTIVE lease
association from absence of a recorded eligible lease;
Unit Directory separately exposes editable available/listed
flags, which do not prove physical occupancy. Reuse
these verified scoped services rather than implement
another occupancy or GL model. Report must identify only
"no eligible current recorded lease" CANDIDATES and
explicitly say physical vacancy is not verified; do not
label units "vacant" purely from is_available or
past lease date. Preserve manager/property/LEASING/
PROPERTIES.UNITS permissions and CSV/email gates.
No migration required if reusing source records.

## Phase 3.7 Unit Vacancy Detail — VERIFIED 2026-09-26

Source e61115fd1d0a544c7cddbfd0d8e22df6054ee8da;
focused test-state correction
0567aa87b894baf41238b61838566b71bc885a9b.
Final CI 36286373738 SUCCESS all six jobs:
backend 512 passed, 3 deselected, 7856 warnings
in 107.31s; authenticated E2E 3 passed in 8.86s;
frontend lint/typecheck/production build, platform
admin, security and staging-config green. The original
source run 36286344811 was superseded/cancelled after
the test correction; not a verified product CI run.
No migration: Alembic d2f4a6c8e0b1, 108 model tables.
Frozen docs/ unchanged. Planning parity metadata not advanced.

Canonical STANDARD property.unit_vacancy_detail links to
/dashboard/reporting/unit-vacancy-detail; preview
GET /api/reporting/unit-vacancy-detail/preview no-store.
Service app/services/unit_vacancy_detail.py composes
VERIFIED scoped rent_roll and unit_directory builders:
only active in-scope units with NO ELIGIBLE CURRENT
RECORDED LEASE are shown, with explicitly editable
is_available, is_listed, available_from and current
configured market rent. The report NEVER certifies
physical vacancy, historical occupancy, collected rent
or return. A FALSE is_available flag can still appear
when no eligible lease exists; the distinction is
explicit. Rent roll's duplicate active lease and
foreign-tenant guards fail closed. No GL writes.
Role ADMIN/MANAGER, org live manager assignment and
REPORTING.ALL, PROPERTIES.ALL, PROPERTIES.UNITS,
LEASING are all rechecked through the reused builders.
release.reporting.export and per-report permissions
required on preview, server-rendered CSV and email.
ReportPayload + CSV formula escaping, shared ReportActions
and safe optional property filtering reused unchanged.
Three focused tests cover current/expired/terminated
lease distinction, editable flags, inactive units,
manager org scope, invalid params, duplicate active
leases, permission/export revocation, preview CSV/email,
no GL writes. Three generic browser E2E smoke tests,
NOT dedicated vacancy interactions.

NEXT original Section 38 Owner & Vendor reports:
Owner Directory, Owner Statement, Vendor Directory,
Vendor Ledger, Work Order. Owner Statement is already
VERIFIED and must not be repeated. Source User has
only first_name, last_name, email, phone; do not
invent owner mailing addresses or use encrypted
tax profile identifiers. PropertyOwner is real
org-scoped ownership/membership if associated
property information is needed; verify active role,
org and visible property before showing owner links.
Preserve PEOPLE.OWNERS role/menu permission and
customer privacy; do not expose other owners to
ordinary owner or tenant viewers. No GL modifications.

## Phase 3.7 Owner Directory — VERIFIED 2026-09-26

Implementation 22bc827577e960a1e4a66203bebe14b7638df58c;
test-only CSV formula and foreign owner self-scope correction
96d731902ac3b3126ab8d93f7d4881a551795609;
security role-boundary correction
05c8e4e73a9e4c93088ddf2773318179dfd0b592.
Final source CI 36287053275 SUCCESS all six jobs:
515 backend passed, 3 deselected, 7963 warnings
in 107.66s; 3 authenticated browser E2E passed
in 8.99s; frontend lint/typecheck/build, security,
platform admin, staging-config green.
Superseded earlier source runs 36286827190 and
36286839810 CANCELLED, not fully verified.
No migration: d2f4a6c8e0b1, 108 model tables;
frozen docs/ unchanged, planning parity not advanced.

STANDARD owner.directory links to
/dashboard/reporting/owner-directory. Canonical preview
GET /api/reporting/owner-directory/preview with no-store;
existing ReportPayload/server CSV/email/ReportActions,
formula escaping and release.reporting.export rechecks.
Service app/services/owner_directory.py lists only
current active undeleted same-org User.role OWNER
contacts: recorded name, email, phone, Owner ID.
No invented owner mailing addresses, ACH banking,
TIN or tax profile reads. Existing users.get_user
restricts managers to crew details; therefore THIS
report denies MANAGER, even with a PEOPLE.OWNERS
menu grant. Authorized ADMIN sees same-org owners;
OWNER self sees own contact ONLY, never other owners.
REPORTING.ALL and PEOPLE.OWNERS required; tenant,
vendor, inactive/deleted and foreign scope denied.
Three focused tests cover role privacy, cross-org
owner self-only, inactive/deleted, CSV injection,
no GL writes, export-gate/menu revocation, preview
and server CSV/email. General E2E smoke count is
not owner-directory-specific coverage.

NEXT Vendor Directory (Owner Statement already VERIFIED).
Vendor is currently User.role VENDOR; there is
NO separate Vendor model, and Bill.payee_name is
unlinked free text for some records. Do NOT invent
vendor entities from unlinked bills or treat VENDOR_CREW
as a vendor business. Existing User has first/last,
email and phone, not verified vendor mailing address.
Preserve user-management role boundaries: manager
currently cannot list vendor users via GET /users
(it returns crew only); do not use report permissions
to widen that rule. ADMIN can view own-org vendor
accounts; owner sees nonowner users on existing
user-management GET /users (check current route),
but do not expose unrelated vendor contacts to
unauthorized tenant/crew/vendor roles.
Do not expose vendor tax profiles or internal payer details.

## Exact next work: continue, don't stop at phase boundary

1. Read entire root handoff and verify branch HEAD/latest CI.
   Owner Directory, Owner Statement and all earlier
   original-plan batches are VERIFIED. Do not repeat.
2. Next Section 38 Owner & Vendor task: Vendor Directory.
   Current User.role VENDOR represents a recorded vendor
   account. VENDOR_CREW is different, and many Bill payee
   names are free text; do not fabricate vendor registration.
   Directory uses recorded first/last name, email and
   optional phone only. No tax ID, W-9 or guessed
   mailing/address/insurance status.
3. Check existing GET /users role detail/list contracts.
   ADMIN can see own-org vendor users. Existing OWNER
   listing can see same-org nonowner users; handle
   OWNER with existing role/menu permissions. MANAGER
   user list is crew-only: do NOT create a report bypass.
   Require REPORTING.ALL and PEOPLE.VENDORS, active/
   not-deleted actor, org scope; avoid cross-org leak.
4. Add STANDARD report href, no-store preview, shared
   ReportPayload/CSV/email and release.reporting.export
   gate, formula escaping and role/permission tests.
   No GL writes or migration. After full green CI
   update handoff then proceed Vendor Ledger.
5. Commit bounded code with focused regression tests,
   verify all six GitHub Actions jobs and exact counts
   before VERIFIED. No main/new branch, Work mode,
   unapproved frozen docs or repeated audits.

## Session start for successor

Continue yasirskhan/property-platform ONLY on
chatgpt/checkpoint-005-safety. Read entire repo-root
AI_HANDOFF.md first, verify actual HEAD/latest CI.
Last VERIFIED source 05c8e4e73a9e4c93088ddf2773318179dfd0b592;
CI 36287053275 all six SUCCESS: backend 515 passed,
3 deselected, 7963 warnings; E2E 3 passed in 8.99s.
Alembic d2f4a6c8e0b1, 108 model tables. Unit Vacancy,
Owner Directory and prior original-plan reports VERIFIED.
Exact next Section 38 Vendor Directory; Owner Statement
already VERIFIED, then Vendor Ledger. Preserve current
user-management role boundaries, no tax IDs, no made-up
vendor/mailing entities, existing report permission and
CSV/email export gates. Add tests, green full CI, update
root handoff. No main/new branch/unapproved frozen docs.
