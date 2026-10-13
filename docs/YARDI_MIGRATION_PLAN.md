# YARDI MIGRATION PLAN

Status: **PHASE 4.15 ACTIVE — FOUNDATION / SOURCE-CONTRACT DEFINITION**

Phase 4.15 must reuse the existing provider-labelled migration architecture.
Do not build a parallel Yardi migration system.

Related source of truth:
- `docs/PLAN_GAPS.md` — Phase 4.15 roadmap assignment.
- `docs/APPFOLIO_MIGRATION_IMPORT_PLAN.md` — verified file-ingestion/staging safety pattern.
- `AI_HANDOFF.md` — current verified checkpoint and exact next batch.

## 1. Provider reality and transport decision

Yardi does not publish a general public Voyager endpoint catalog comparable to
Buildium's Open API. Official Yardi material states that third-party API access
is supplied through Yardi interface programs and related agreements/sandbox
access. Yardi also documents conversion methods including Yardi ETL import
templates, Yardi-to-Yardi conversion and conversion services.

Therefore Phase 4.15 uses this transport order:

1. **Supported Yardi export / ETL files first** where the source schema can be
   independently verified.
2. **Direct/API-assisted adapter later** only when an official Yardi client or
   partner contract, credentials and source documentation are available.
3. Any later API adapter must feed the SAME staging/review/fingerprint/mapping
   pipeline. It may not bypass review or commit controls.

Do not scrape Voyager browser sessions, reverse-engineer private endpoints,
accept browser cookies as a production migration credential, or invent API
routes from third-party examples.

## 2. Product objective

A Yardi customer should be able to migrate supported data through a controlled
provider-labelled run:

`Yardi export/ETL source -> upload -> detect -> map -> stage -> validate ->
review -> reconcile -> dry run -> controlled commit -> durable source mapping`

Where an official Yardi API becomes available later:

`Yardi official API -> bounded fetch -> same normalized staging/review pipeline`

The source transport itself must never mutate customer business records.

## 3. Architecture to reuse

Phase 4.15 must reuse:

- `PlatformMigrationRun`
- `PlatformMigrationUpload`
- `PlatformMigrationStagedRow`
- `PlatformMigrationItem`
- exact normalized-source fingerprints
- explicit review decisions
- durable source-to-target mappings
- replay/idempotency
- organization isolation
- stale-preview rejection
- run-level review/coverage summaries
- controlled commit
- recovery/mapping visibility
- append-only redacted audit

The provider label for this phase is `YARDI`.

No Yardi client secret, password, token, session cookie or raw provider response
belongs in migration rows or audit logs.

## 4. First bounded implementation order

Do not attempt all Yardi objects at once.

Start with the same dependency-safe order used successfully in the earlier
migration phases:

1. Properties
2. Units
3. Owners / ownership identity where source semantics are verified
4. Vendors
5. Residents / tenants
6. Leases / occupancy relationships
7. GL Accounts
8. Open receivables / lease charges
9. Open payables / bills
10. Bank Accounts
11. Current-year budgets
12. Outstanding checks / supported open accounting controls
13. Historical accounting only where authoritative source direction and target
    posting semantics are independently proven

This order aligns with Yardi's own published implementation/conversion examples,
which include properties, owners, units, vendors, bank accounts, resident
information, lease charges, open AR/AP, outstanding checks, trial balance and
budgets.

## 5. First product batch — Yardi migration-run foundation

The first product-code batch should create the smallest first-class Yardi
provider surface around the existing migration-run model.

Required behavior:

- create/list/get Yardi provider-labelled migration runs;
- require organization scope and a bounded non-secret `source_account_ref`;
- provider is always server-assigned `YARDI`, never caller-selectable;
- reject credentials, passwords, tokens, cookies and raw provider payloads;
- no customer business records are created;
- reads are no-store and organization/role scoped;
- audit run creation without storing secrets;
- preserve all existing AppFolio and Buildium behavior;
- add no new business table and no accounting mutation.

Do not add an outbound Yardi API transport in this foundation batch.

## 6. File-ingestion direction

After the provider-run foundation is verified, add Yardi file ingestion by
reusing the proven CSV/XLSX ingestion/staging controls rather than cloning the
AppFolio router wholesale.

Required shared controls:

- bounded file size and row count;
- data-only XLSX parsing;
- no formula/macro execution;
- deterministic header normalization;
- explicit column mapping when uncertain;
- stable Yardi source IDs preserved when supplied;
- no synthetic IDs from names/row order;
- duplicate-ID detection;
- staged rows only on upload;
- exact source fingerprint;
- replay-safe re-upload;
- possible-match review instead of automatic overwrite;
- missing required data remains blocked/reviewable, never invented.

## 7. Resource safety rules

### Properties and Units

Property and Unit creation/mapping may proceed only from verified source fields.
Do not infer occupancy, ownership, lease, balance or accounting facts from a
Property/Unit row.

### Residents / Tenants

Do not create login-bearing users merely because a Yardi resident record exists.
Identity and occupancy are separate concerns. Use explicit review and durable
source identity.

### Leases / occupancy

Do not infer lease liability, rent, security deposit receipt or payment history
from status labels alone. Relationships must resolve through current mapped
Property, Unit and resident identities.

### Accounting

The permanent accounting rule applies to Yardi exactly as it does to Buildium
and AppFolio:

**Never infer debit-versus-credit direction, opening balances, settlement,
cleared state or synthetic history when the authoritative source does not prove
it.**

Open AR/AP, checks, trial balance and budgets require their own verified source
and target reconciliation contracts before controlled commit.

## 8. API adapter boundary

A Yardi direct/API-assisted adapter may be added only when the official interface
contract is available for the customer/partner context.

Before implementing any endpoint:

1. verify the official Yardi interface name and version;
2. verify authentication and tenant/account binding;
3. verify exact request/response schema;
4. define bounded retrieval and pagination;
5. prove the resource maps into an already-verified migration service;
6. keep credentials server-side;
7. fresh-fetch on commit;
8. preserve exact fingerprints and explicit review;
9. sanitize upstream errors;
10. persist no raw provider response merely for convenience.

If those facts are unavailable, leave the API adapter blocked and continue with
the supported export/ETL path.

## 9. Definition of Phase 4.15 completion

Phase 4.15 is complete when:

- the authorized Yardi export/ETL path covers every independently supportable
  resource selected for this phase;
- unresolved source-schema/accounting gaps are explicitly documented as blockers;
- any implemented official API adapter feeds the same reviewed migration
  architecture;
- exact-SHA hosted CI is green for every product batch;
- `AI_HANDOFF.md` records the final supported resource matrix and blockers;
- no undocumented Yardi endpoint or synthetic accounting history was introduced.


## Financial source gate checkpoint (2026-10-10)

GL accounts, open receivables, lease charges, payables, bank accounts, budgets, outstanding checks and historical accounting remain blocked until an independently verified Yardi export establishes source identifiers, row grain, period, debit/credit and settlement semantics and target reconciliation. Do not infer missing balances or post synthetic history.

## 10. Live resource completion matrix (2026-10-12)

Reconciled against the YARDI router, Yardi file staging service and the latest exact-product CI (fce01e99402722bb7af358ee1cda22bcafc88078, run 38200199974, six required jobs successful). The statuses below distinguish verified staging capability from completed customer-record migration. No Yardi accounting source contract is presumed.

| Resource | Current status | Verified scope and remaining gap |
| --- | --- | --- |
| Properties | PARTIAL | CSV/XLSX explicit column mapping, staging, review/dry-run and metadata-only MATCH_EXISTING durable bindings verified. No customer Property creation/overwrite or controlled commit. |
| Units | PARTIAL | Explicit mapped staging, required source Property ID and parent-mapping warning. Reviewed target Unit match, parent relationship validation, exact-fingerprint dry run and metadata-only durable binding verified at 69e65876 (CI 38267008115). No customer Unit creation/overwrite; cross-run collision and stale review regressions added provisionally at 37f742b2. |
| Owners / ownership | PARTIAL | Owner identity staging plus explicit existing OWNER-role user review and metadata-only durable source binding added; ownership relationship and login creation remain blocked without a verified source contract. |
| Vendors | PARTIAL | Vendor identity staging plus explicitly reviewed existing Vendor target and metadata-only durable binding added. No customer vendor, payment or GL account creation. |
| Residents / tenants | PARTIAL | Resident identity staging plus explicitly reviewed existing TENANT-role user and metadata-only durable binding added. No login, lease or occupancy creation. |
| Leases / occupancy | PARTIAL | Stable source identity and three required source references staged. Read-only reconciliation now counts missing Property/Unit/Tenant durable links, invalid/inactive targets and Unit-to-Property mismatches; never creates occupancy, lease, rent, deposit or liability entries. |
| GL accounts | BLOCKED BY SOURCE CONTRACT | Verified Yardi account schema and target accounting mapping absent. |
| Open receivables / lease charges | BLOCKED BY SOURCE CONTRACT | Authoritative charge grain, direction, periods, balances and reconciliation absent. |
| Open payables / bills | BLOCKED BY SOURCE CONTRACT | Authoritative payable, settlement and target posting contract absent. |
| Bank accounts | BLOCKED BY SOURCE CONTRACT | Account identity and reconciliation contract absent. |
| Current-year budgets | BLOCKED BY SOURCE CONTRACT | Period, account, amount semantics and target reconciliation absent. |
| Outstanding checks | BLOCKED BY SOURCE CONTRACT | Cleared state, bank movement and settlement semantics absent. |
| Trial balance / historical GL | BLOCKED BY SOURCE CONTRACT | Debit/credit direction, opening balances and period semantics absent. |
| Official Yardi API adapter | BLOCKED BY SOURCE CONTRACT | No verified customer/partner interface, credentials or endpoint schema. Export/ETL remains the supported transport. |

**Next product batch:** Verify new Unit cross-run collision and stale-fingerprint regressions, then proceed to owner/vendor/tenant/lease relationship review using only source-supported identities. Do not create customer records, auto-link occupancy, or enable controlled customer mutation.

**Completion interpretation:** Staging-only support is not equivalent to a completed resource import. Phase 4.15 remains IN PROGRESS until independently supportable resources are reconciled and verified, with source-contract blockers recorded explicitly.


## 11. Follow-on identity and lease reconciliation batch (2026-10-13)

Product commits on the sole feature branch added independently reviewable existing-identity metadata bindings for **VENDORS**, **TENANTS** (existing active TENANT-role users), and **OWNERS** (existing active OWNER-role users), plus a read-only **LEASE_OCCUPANCY** relationship coverage check. The source format still requires explicit customer-provided CSV/XLSX column mappings; the source does not prove ownership, lease terms, rents, charges, accounting or authenticated customer entitlement. No customer objects are created or overwritten by these paths.

The lease coverage result requires source-referenced **Property**, **Unit** and **Tenant** identities to be durably linked to valid same-organization targets and ensures the target Unit belongs to the target Property. A set of complete identity links is **not authorization** for an occupancy or lease commit. The lease endpoint continues returning `controlled_commit_enabled: false` and `customer_business_mutation: false`.

**Verification status at writing:** the preceding replay and Unit safety batch is verified at HEAD `4d7356010500552b990a245984261db887bbaaef`, GitHub Actions `38340101268` successful. The route dispatch repair and new owner/vendor/tenant/lease batches through `7ca1fbfb543b881d5f63481d78f2509e5153f179` have been committed and await their own latest-SHA hosted CI; do not mark these new batches VERIFIED until green.

**Next:** verify exact-SHA CI and fix any reds. Reconcile per-source relationship semantics and source contract blockers, then continue the next independently supportable read-only export/ETL review task. Do not infer owner-property percentages, tenant lease liability, lease payments, deposit receipts, historical balances or Yardi API credentials/endpoints.


## 12. Resource-readiness API reconciliation (2026-10-13)

After exact-SHA **b6284ed465f70282d89072cd07d6f212ce3b16ca** passed all six hosted CI jobs in run **38348501467**, the owner/vendor/tenant existing-identity bindings, property/unit binding, and read-only lease relationship coverage were verified together. Earlier phase-boundary notes that called these implementation batches provisional are historical and superseded by this checkpoint.

`GET /api/platform/migrations/yardi/resource-readiness` now exposes an explicit `resource_capabilities` matrix. The previous `supported_staging_only` key remains present for compatibility, describing the *upload* pathway, not denying that existing-target metadata bindings are separately available. Five identity resources support explicit reviewed **metadata-only MATCH_EXISTING**; LEASE_OCCUPANCY supports read-only identity-link coverage **without** any lease or occupancy commit. All customer-record-creation, ownership percentage, financial posting and unofficial Yardi API capabilities remain disabled or source-contract blocked.

**Next Phase 4.15 product priority:** operational platform-side Yardi migration workflow for staff to use authenticated run, upload, review, dry run, and reconciliation APIs, without general UX scope expansion, unsafe writes or undocumented Yardi contracts. Audit existing platform admin and backend upload contracts first. This readiness/API change itself requires new exact-SHA hosted CI verification before it is marked verified.


## 13. Operational platform-admin Yardi export workflow (2026-10-13)

The dedicated internal platform-admin `/migrations/yardi` route connects authenticated platform staff to the **existing** Yardi migration run, source staging, row-preview and reconciliation APIs. Read-only roles may view runs and reconciliations; platform admins/tech/dev may create runs, inspect source headers, manually map source columns, upload and stage bounded CSV/XLSX, and record a review dry run. The platform dashboard links to this route only for authorized migration roles.

An additional **source-header inspection** endpoint `POST /api/platform/migrations/yardi/runs/{run_id}/inspect-source` reuses the same bounded CSV/XLSX parser and validation as staging; it returns only headers, sheet, format and row count. It does not expose source row values, persist raw bytes, stage a row, or mutate customer business data. It rejects credential/session source headers and requires the same write-role and organization constraints as staging. A focused backend regression covers privacy, nonmutation, credential header rejection and access control.

The browser upload helper now leaves multipart `Content-Type` unset for `FormData` so the browser correctly supplies its own boundary. The UI offers source-header selection for required resource fields and retains explicit JSON mapping for additional fields. No auto-matching of Yardi financial fields or undocumented source schema is introduced. Identity review/bind remains a separate staff workflow and remains backend-guarded; this first UI batch primarily makes authenticated staging, preview and dry run operational.

**Verification:** This UI/inspection batch must pass its own exact-SHA CI, including platform-admin lint/typecheck/build, backend tests, security, frontend, authenticated E2E and staging. The source-contract blockers above are unchanged.

**Next bounded Phase 4.15 batch:** expose the explicit existing-target review/skip/bind operations in the authorized internal staff console with audit visibility, exact review fingerprint and no customer entity mutation.


## 14. Staff-reviewed existing-target identity controls (2026-10-13)

The authenticated internal Yardi migration console now provides per-row existing-target review for Properties, Units, Owners, Vendors and Tenants; reason-coded `SKIP` for rows outside the import (including invalid rows); and resource-specific durable metadata binding using the exact recorded review fingerprint. Invalid source rows are not accepted for MATCH_EXISTING. Successful review decisions invalidate the prior dry-run snapshot and reload the same-run reconciliation before metadata binding. Existing Yardi backend endpoints remain responsible for role authorization, target organization, target role, parent linkage, idempotency, stale fingerprints, cross-run collisions, and append-only audit. Read-only platform staff receive no write controls.

These controls do not create or modify customer Property, Unit, User, Vendor, Lease, ownership interests, GL entries, receipts, payments or historical balances. `LEASE_OCCUPANCY` is intentionally excluded from existing-target binding; its relationship preview remains strictly read-only.

**Verification:** Staff review UI commit `dcf9f6b0` and invalid-row skip fix `04768173` plus explicit authenticated-review API contract tests `6e4efb7e` remain provisional until latest exact-SHA hosted CI is successful. The previous staff upload/header-inspection checkpoint `a79b0d163175cbaf7d3df0227cf5f57df13fd266` was green in run `38358321235`. Future work after verification should address auditable staff operation feedback and row pagination, not general UX or financial source assumptions.


## 15. Staff-only existing-target candidate lookup (2026-10-13)

The previous staff review, row pagination and audit-evidence UI batch passed **all six** hosted CI jobs on exact SHA `f6dabfe4b682535893fb40c7f911c8ef82fc7c15` (GitHub Actions `38360831046`; **1253 backend tests passed, 21 deselected**). Metadata-only review/bind operations remain restricted to platform admin/tech/dev roles; no customer record creation or financial posting.

The next bounded operational batch provides `GET /api/platform/migrations/yardi/runs/{run_id}/existing-targets` with explicit **resource** and a 2–80-character **staff-entered query**. The endpoint is write-role gated despite using HTTP GET, organization-scoped to the selected migration run, redacted to bounded existing record **ID and display label** only, no-store, and limited to at most 30 results. It includes only active, non-deleted Properties, Units (under active Properties), Owner-role customer users, Tenant-role customer users and non-deleted Vendors. It never returns password hashes, email addresses, source row contents or financial details. Search treats SQL wildcard characters literally.

The staff console can search those targets and select an ID, but the actual MATCH_EXISTING decision **still requires a separate explicit review action**. No automatic target matching, tenancy, ownership linkage, customer mutation, leasing or accounting is enabled. Existing exact-reviewed dry run and binding controls remain authoritative.

**Verification:** candidate endpoint commit `a26fb3a5`, scoped/privacy regressions `8d8718f3`, platform picker `54b382ae`, authenticated API coverage `002b0132` and fast CI gate `8e454d87` are provisional until the newest exact-SHA hosted workflow succeeds.
