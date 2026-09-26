# AI_HANDOFF.md — Property Platform, 2026-09-26

**READ THIS WHOLE FILE FIRST.** This is the repo-ROOT authoritative session handoff;
it does NOT belong under docs/. Refresh after every meaningful CI-verified batch.
Do not ask Yasir to repeat verified state. Never paste real tax secrets/TINs.

- Private repository: `yasirskhan/property-platform`
- ONLY working branch: `chatgpt/checkpoint-005-safety`. Do not edit `main`,
  create a branch, force-push, or merge the draft PR without permission.
- Last VERIFIED **product source**: `10eff9806ce1890afadb04afb62ad7849d45258b`
- Source GitHub Actions run **36251944098: SUCCESS, all six jobs** (backend,
  frontend, platform-admin, security, authenticated E2E, staging-config).
  Backend: **409 passed, 3 deselected, 3715 warnings in 76.20s**.
  E2E: **3 passed in 7.55s**. Lint, typecheck, production build, security
  and staging: SUCCESS. These counts apply to this exact source commit only.
  This handoff update itself is docs-only; TESTS NOT RUN locally. Verify
  current branch HEAD and latest CI before continuing.
- Alembic head: **d6a8b0c2e4f7**. SQLAlchemy expected model tables: **102**.
  Previous head c5f7a9b1d3e6 / 101 tables. Schema/test guards changed
  together. All three PostgreSQL/bootstrap/legacy migration CI paths passed.
- Phase 3.7 Reports + Universal Attachments: IN PROGRESS.
  **Latest completed batch: encrypted signed-paper W-9 archival, admin
  UI, remote telemetry redaction, and bounded key rotation. VERIFIED.**
- **Exact NEXT original-plan task: Generate 1099 Forms & Reports,
  continuing with documented tax-year-specific form data selection,
  classification and approval workflow, then IRIS/approved-provider
  handoff. Full filing/recipient copies remain NOT IMPLEMENTED.**
  Secure payer/recipient tax profiles and the paper-W-9 archive have
  now been built and verified; do not repeat them.

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

**CURRENTLY NOT IMPLEMENTED**: provider-hosted e-W9 consent/signature,
backend PDF malware scanning/retention purge, completed 1099-NEC/MISC
reportable-payment identification, review and approval, official IRS
tax-year template mapping, TCC / provider credentials, transmission,
filing receipts, corrections, recipient copies or e-delivery. Do not
claim any of these verified or enable "file" from a prototype.

## Exact next work: continue, don't stop at phase boundary

1. Re-read root handoff and current branch HEAD; check latest source
   CI. Inspect real payer/owner/vendor/bill/payment/owner-payout models,
   accounting journal and reporting permission patterns before changes.
2. Next bounded Phase 3.7 batch: *1099 tax-year-specific data review
   foundation*. For explicit 1099-NEC/MISC recipient type and payer/
   recipient combination, take only validated manually entered
   tax-year amounts with documented supporting source/reference and
   clear classification. No guessed totals from GL, bill payee names
   or owner distributions, no implicit filing eligibility from a
   checkbox. Validate year/amount/type, tax-profile existence and
   signed W-9 evidence, scope + permissions, append-only audit,
   prepare/review/approve transition, idempotency and locked approval.
   Review output MUST redact TIN; leave submission disabled. Keep
   report preview separate from actually filing.
3. Then IRS-current tax-year-specific IRIS CSV mapping or approved
   Avalara/Track1099 provider handoff. IRS IRIS Taxpayer Portal needs
   IRIS TCC and published exact CSV template per tax year; official
   page https://www.irs.gov/filing/e-file-information-returns-with-iris
   listed portal templates only through tax year 2025 as of 2026-09-26.
   Do NOT invent tax-year-2026 CSV columns or label a speculative CSV
   IRS-compatible. IRIS A2A needs distinct IRS API credentials, schema
   and testing. Avalara 1099 & W-9 publishes a provider API
   https://developer.avalara.com/products/avalara-1099-and-w9/api/
   but requires an actual subscription and securely stored credentials;
   web-app review/scheduling/corrections may still be needed. No
   mocked "sent" result may be represented as production filing.
4. Form selection, tax-year thresholds, backup-withholding exceptions,
   tax classification, state filings and reportable-payment source
   must be explicitly reviewed. IRS rules for 2026 changed for
   specified 1099-NEC/MISC payments; do NOT apply a universal threshold.
   See https://www.irs.gov/publications/p1099 and official form
   instructions. No actual transmission without provider/TCC approval,
   no fabricated addresses/TINs or unverified tax amounts.
5. Tests with each bounded source batch, commit only this branch,
   verify all six GitHub CI jobs before marking VERIFIED. If red,
   fix before next feature batch; stop if the same assertion fails
   three consecutive times. Report true test counts, commits, schema,
   failure context and update this root handoff each meaningful batch.
6. After full 1099 feature verified, Section 38 next tasks **Letters**,
   then **Send Owner Packets**, then original tenant/property/
   owner/accounting/transaction reports. Do not skip original order.

## Session start for successor

Continue yasirskhan/property-platform on
`chatgpt/checkpoint-005-safety`. Read this entire root AI_HANDOFF.md;
fetch actual HEAD and full CI. Last VERIFIED product source
`10eff9806ce1890afadb04afb62ad7849d45258b`;
run 36251944098 SUCCESS (409 backend passed, 3 deselected;
3 E2E passed). Alembic `d6a8b0c2e4f7`, 102 model tables.
Encrypted paper W-9 archival, UI, Sentry privacy and scoped key
rotation are VERIFIED; DO NOT repeat. 1099 forms/filing NOT DONE.
Immediate batch is documented manually sourced 1099-NEC/MISC
review/approval foundation; then official template/provider.
No Work mode, no main/new branches, no invented test results or
fake filing. Keep root handoff current.
