# AI_HANDOFF.md — Property Platform, 2026-09-26

**READ THIS WHOLE FILE FIRST.** This is the repo-ROOT authoritative session handoff;
it does NOT belong under docs/. Refresh after every meaningful CI-verified batch.
Do not ask Yasir to repeat verified state. Never paste real tax secrets/TINs.

- Private repository: `yasirskhan/property-platform`
- ONLY working branch: `chatgpt/checkpoint-005-safety`. Do not edit `main`,
  create a branch, force-push, or merge the draft PR without permission.
- Last VERIFIED **product source**: `48dc20d6d52d163954cc00956714090d3d2dcae9`
- Source GitHub Actions run **36268034674: SUCCESS, all six jobs** (backend,
  frontend, platform-admin, security, authenticated E2E, staging-config).
  Backend: **423 passed, 3 deselected, 4189 warnings in 66.98s**.
  E2E: **3 passed in 10.43s**. Lint, typecheck, production build, security
  and staging: SUCCESS. These counts apply to this exact source commit only.
  This handoff update itself is docs-only; TESTS NOT RUN locally. Verify
  current branch HEAD and latest CI before continuing.
- Alembic head: **f8c0d2e4a6b9**. SQLAlchemy expected model tables: **103**.
  Previous head e7b9c1d3f5a8 / 103 tables. Schema/test guards changed
  with the tax-profile revision migration; no new model table. All three
  PostgreSQL/bootstrap/legacy CI paths passed.
- Phase 3.7 Reports + Universal Attachments: IN PROGRESS.
  **Latest completed batch: tax-profile revision and stale-approval
  integrity safeguard. VERIFIED.**
- **Exact NEXT original-plan task: Generate 1099 Forms & Reports,
  continuing with internal no-TIN-leak provider preflight and then
  IRS-current IRIS/approved-provider handoff. Full filing/recipient
  copies remain NOT IMPLEMENTED.** Do not repeat manual review, the
  register, revision guards, tax profiles or the W-9 archive.

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

**CURRENTLY NOT IMPLEMENTED**: provider-hosted e-W9 consent/signature,
backend PDF malware scanning/retention purge, completed 1099-NEC/MISC
reportable-payment identification, review and approval, official IRS
tax-year template mapping, TCC / provider credentials, transmission,
filing receipts, corrections, recipient copies or e-delivery. Do not
claim any of these verified or enable "file" from a prototype.

## Exact next work: continue, don't stop at phase boundary

1. Read complete root handoff and verify current branch HEAD and CI.
   Do not repeat verified review/approval, encrypted W-9, internal
   register or substantive-profile revision locking.
2. NEXT bounded Phase 3.7 batch: provider-handoff PRECHECK,
   read-only/admin-only, with no raw TIN in HTTP, audit, log or CSV.
   Recheck approved current revision, signed archived W-9, required
   legal-name/address fields, explicit classification/amount/source
   and manual threshold/exception attestations. Return redacted
   readiness/blocking reasons; distinguish "internally reviewed"
   from "IRS filing enabled". Keep filing disabled absent a real
   IRS-current verified adapter. Include focused tests and CI.
3. Then IRS IRIS or an approved provider integration. Official IRIS
   public 2026 Taxpayer Portal CSV template has NOT appeared as of
   2026-09-26; never guess a 2026 IRS CSV or output a FIRE file.
   IRS A2A requires IRS TCC, developer API Client ID, secure XML schema
   and successful Assurance Testing System transmissions. Avalara
   1099/W-9 provides an API requiring active subscription/credentials.
   No live client secrets in git or chat. Real authenticated sandbox
   testing and acknowledgment handling are prerequisites to marking
   production submission/recipient copies verified.
   https://www.irs.gov/filing/e-file-information-returns-with-iris
   https://developer.avalara.com/products/avalara-1099-and-w9/api/
4. Continue tax-year thresholds/exceptions, state filing and recipient
   delivery only with verified current rules; never infer amounts
   from the GL, bill payee text or owner distributions.
5. Commit bounded code + regression tests to this branch only;
   all six hosted CI jobs must pass before VERIFIED. Fix CI reds,
   stop after three repeats of same assertion, report exact counts,
   migration and commit; refresh root handoff after each meaningful
   verified batch. Frozen docs remain unchanged without authorization.
6. After actual 1099 forms/filing are completed and verified, follow
   Section 38 Letters, Owner Packets, and remaining reports; do not
   create/switch branches, touch main or force-push.

## Session start for successor

Continue yasirskhan/property-platform on `chatgpt/checkpoint-005-safety`.
Read the entire repo-root AI_HANDOFF.md, verify current HEAD and CI.
Last VERIFIED product source `48dc20d6d52d163954cc00956714090d3d2dcae9`,
CI 36268034674 SUCCESS (423 backend passed, 3 deselected,
4189 warnings; 3 E2E passed; all six jobs green).
Alembic `f8c0d2e4a6b9`, 103 tables. Manual NEC/MISC review
and approval, redacted internal CSV, W-9/tax encryption, and tax-profile
revision stale-approval checks VERIFIED. Real IRS/provider filing and
recipient copies NOT IMPLEMENTED. Next: redacted provider-handoff
preflight, then IRS-current IRIS/provider integration requiring official
2026 format/TCC or provider sandbox account. No invented IRS CSV,
raw tax IDs in UI/logs, main/new branch, or unapproved frozen docs edits.
Continue bounded commit+CI, update root handoff on verified work.
