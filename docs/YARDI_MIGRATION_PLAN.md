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


## 16. Durable existing-identity mapping inspection (2026-10-13)

The target candidate picker batch is **verified** on exact SHA `0603cc2d5f22dfec071ac92374e08f16f9ac992c`, GitHub Actions `38362750313`, all six required jobs successful. Candidate lookup never authorizes automatic matching or creates customer data.

Next operational batch introduces `GET /api/platform/migrations/yardi/runs/{run_id}/bindings`: an authenticated, read-role-gated, provider/run/organization-scoped and paginated inventory of the **existing durable source-to-target identity metadata**. Filters are restricted to the five supported existing-identity resources. Returned fields include source ID, target entity and ID, audit creator/time, and a freshly checked `target_current` flag for customer records that remain active, correctly scoped and non-deleted. It does not expose names, credentials, raw CSV/XLSX rows, user emails or financial details. The staff console displays this inventory with resource filters, paging, and missing/deactivated-target warnings. The inventory never changes customer records or mappings.

The exact-SHA CI gate adds backend tests for cross-organization/provider isolation, pagination, inactive/deleted target status, staff role authorization, redaction and customer-record nonmutation; the API route contract test requires authentication and GET-only access.

**Provisional until CI:** product `747f54c3`, regression `b443a077`, staff UI `c2a72470`, API contract `b397bf8a`, fast CI suite `f4655421`. Do not mark verified before a six-job hosted run succeeds on this source and any later handoff commit. No ownership percentages, lease/occupancy records, financial postings or official Yardi API have been enabled.

## 17. Durable Unit source-parent relationship revalidation (2026-10-13)

Exact Phase 4.15 mapping-inventory checkpoint `834c373ce02b4475f30d7e98f11975d77f82dc07` was **VERIFIED** by six-job GitHub Actions run **38402880141**, with 1258 backend tests passed and 21 deselected. Its read-only durable bindings inventory shows active/nondeleted target record status, but this alone is insufficient to verify a Unit's source Property relationship.

The follow-on batch adds a separate **tri-state `unit_parent_relationship_current`** to each Unit binding. If a committed Unit mapping has an exact matching, explicitly reviewed staged source row (matching run, organization, resource, source ID, source fingerprint and reviewed target Unit), its `source_property_id` must resolve through a durable same-run YARDI Property binding and match the Unit's *current* target `property_id`. A moved Unit now gets `false` even if both old and new Properties are active in the same organization. `true` requires a current matching parent; `null` means this exact source-parent relationship is unavailable or unverified. Non-Unit resources return null for this field.

This diagnostic neither changes source-to-target mappings nor edits customer Units or Properties. The staff migration console explicitly distinguishes verified, mismatched, and unavailable parent relationship evidence; it does not automatically correct a stale mapping or infer occupancy.

Provisional product commit `695618db`, regression `f93201b1`, staff UI `1b6b1b60`; exact-SHA hosted CI must pass all six jobs before this new batch is marked VERIFIED. Financial source contracts, official Yardi API, GL, payments, lease posting and ownership percentages remain blocked pending authoritative source evidence.


## 18. Per-lease source relationship diagnostics (2026-10-13)

**Prerequisite verified:** Unit source-parent relationship diagnostics at exact source SHA `3a6ecd5101ecf52a6c1e05b7b66922a4c892799f`, GitHub Actions **38405573366 SUCCESS**, all six jobs passed, backend **1259 passed, 21 deselected**. The durable Unit inventory distinguishes exact verified source-parent relationships from an active but reparented Unit.

The next bounded operational batch adds `GET /api/platform/migrations/yardi/runs/{run_id}/lease-relationships`. It queries existing organization/run/provider-scoped `LEASE_OCCUPANCY` staged rows and same-run durable Property, Unit and Tenant metadata bindings. The endpoint reports **bounded per-row blocker codes** for missing/inactive source identity mappings, invalid/skipped source rows and active Unit-to-Property mismatches. It returns source lease identity and row number but no raw resident information, bank data, rent values, deposits, source file bytes or customer record names. Page size is capped at 100. Staff can view it in the internal Yardi console and inspect which exact lease source identities remain blocked.

Even when `identity_links_complete=true`, the response explicitly sets `occupancy_or_lease_authorized=false`, `controlled_commit_enabled=false`, and `customer_business_mutation=false`. Nothing creates a lease, changes a tenant, registers occupancy, posts charges, imports financial history or supplies unsupported Yardi source contracts.

**Provisional until exact-SHA CI:** read-only endpoint `49e3cd1a`; regression `fb12c1cd`; UI `fd8f82bc`; OpenAPI/auth contract `9e8c61bc`; fast regression suite `e558d786`. Verify all six hosted CI jobs, repair any failures before marking verified, then proceed with the next bounded Phase 4.15 review task.

 
## 19. Lease-versus-Unit original Yardi source-parent consistency (2026-10-13)

**Previous per-lease diagnostics verified:** exact product commit `194f638eb01404c0b7db0a52e8f5aa6704e10ce7`, GitHub Actions **38416611368 SUCCESS**, six jobs green, **1262 backend tests passed and 21 deselected**.

Phase 4.15 now additionally compares the `source_property_id` of a staged lease with the `source_property_id` of an **exact reviewed** Yardi Unit source row, using the same-run committed source-to-Unit target mapping and matching row fingerprint. This is independent of whether the current Unit happens to belong to the lease's target Property. When exact reviewed evidence disagrees, the read-only row preview reports `UNIT_SOURCE_PARENT_MISMATCH`, and the aggregate reconciliation increments `unit_source_parent_mismatch` rather than misclassifying the row as `complete_identity_links`. Missing or legacy reviewed Unit source-parent evidence remains explicitly unknown in the row preview; no source relationship is guessed.

The staff UI shows these source-parent conflicts both per lease and in the aggregate count. Existing role, organization, provider, pagination, no-store and nonmutation safeguards apply. No lease, occupancy, rent, payable, receivable, deposit, ownership interest or accounting entry is created or altered.

**Provisional implementation pending newest exact-SHA hosted CI:** backend `3a275cf0` and aggregate `96c34d9f`, regressions `7ab08a01` and `15d7156c`, staff UI `504edff6` and reconciliation totals `343b558b`. Verify all six CI jobs and repair reds before marking this new batch verified. Continue Phase 4.15 afterward without activating unverified financial source contracts.

## 20. Run-scoped cross-upload stable source identity collisions (2026-10-13)

**Prior verified checkpoint:** Exact SHA `6437b61e5ff58248fc3e5826b7f7a0e0e8fda611` passed GitHub Actions **38419242672**, all six jobs. Unit original Yardi source-parent comparison and aggregate lease-source mismatch reporting are VERIFIED.

A new staff-only read-only endpoint `GET /api/platform/migrations/yardi/runs/{run_id}/source-collisions` groups all staged rows by exact `(resource, source_id)` within the same organization, provider and migration run. Repeated identifiers across uploads are shown even if the same raw row appears in multiple explicitly mapped exports. Each collision group reports the number of staged rows, contributing uploads, distinct raw-row fingerprints (`source_versions`), whether versions conflict, and up to ten staged-row/upload/row-number references. Pagination is limited to 50 groups per page. No raw names, email addresses, credentials or import contents are returned; the existing source ID alone is sufficient to locate rows in the authenticated staff staging view. Identical rows are still reviewed, not auto-merged.

The platform-admin Yardi console now exposes these collision groups with resource filter, pagination, and staff-readable row locations. It never automatically selects an identity target, resolves a conflict, overwrites staged data, alters a customer account or posts financial transactions.

**New commits provisional until exact-SHA hosted CI:** endpoint `c2a8fa37`, regression `b3f40a2f`, staff state `3d4fd66b`, staff panel `d85e82ce`, authenticated contract `d7a44969`, fast regression gate `c36a2feb`. Verify backend/PostgreSQL, frontend, platform-admin, security, E2E and staging; repair reds before marking verified. Continue Phase 4.15 without guessed financial, lease or Yardi API contracts.

## 21. Explicit reviewed Yardi lease source-identity acceptance (2026-10-13)

Yardi lease/occupancy acceptance uses existing typed `PlatformMigrationStagedRow` review fields and the same migration-run, audit, and exact reviewed-source fingerprint architecture as the verified AppFolio pathway. It is a **metadata review step for later controlled import, not an actual lease commit**.

An authorized platform migration writer may explicitly record `ACCEPT_RELATIONSHIP` for one valid staged `LEASE_OCCUPANCY` source row only after same-run provider-labelled Property, Unit and Tenant durable mappings resolve to active same-organization targets. The current Unit must belong to the mapped Property. The original Unit source-parent relationship must be supported by one or more exact-fingerprint, explicitly reviewed Unit source rows, all agreeing with the lease's source Property ID. Conflicting or unverified source-parent evidence fails closed. Repeated lease source IDs across uploads must be explicitly resolved (other versions skipped with a reason) before acceptance. Accepted review replays only after revalidating current links and the original source relationship, and stale target snapshots are rejected.

Acceptance writes only staged review action, scoped target IDs, reviewer/time and redacted audit metadata; it invalidates a previous run dry-run fingerprint. Source identities are **not** customer leases, rent charges, deposit receipts, ledger postings or validated occupancy. Customer business record creation, financial posting and `controlled_commit_enabled` remain disabled. The staff migration console exposes the explicit action only for currently unreviewed, valid lease source rows, and continues to show existing per-row blocker statuses.

Prepared product source, regression tests, staff UI, authenticated API contract and fast CI changes are staged as GitHub blobs pending the previous exact-SHA collision-review green check. They must be committed to only `chatgpt/checkpoint-005-safety`, then receive their own six-job CI verification before this batch can be marked VERIFIED.


## 22. Revalidate accepted lease source reviews in read-only preview (2026-10-13)

**Prior verified:** Exact product SHA `9ea421deedd2f5a9cb11f839abf3cf5484052ba4` passed all six jobs in GitHub Actions **38495996102**. This verifies staff-reviewed `ACCEPT_RELATIONSHIP` for stable lease source identities with current same-run Property/Unit/Tenant mapping checks, original reviewed Unit source-parent evidence, collision detection, idempotent replay, audit and no customer business mutation.

**Follow-on committed but provisional:** The read-only `GET /runs/{run_id}/lease-relationships` view now provides a separate `relationship_review_current` boolean. An earlier `ACCEPT_RELATIONSHIP` decision is reported as stale if its recorded target IDs no longer match the current valid durable source mappings, the original Unit source-parent review evidence no longer agrees, or a new unskipped copy of the same lease source ID appears in another uploaded export. Cross-upload duplicate identity is reported with `LEASE_SOURCE_ID_COLLISION`, and stale accepted target/evidence with `ACCEPTED_RELATIONSHIP_STALE`. A previously accepted review **is not silently reopened**: the backend does not rewrite staged review history or create a Lease; the staff console displays the mismatch for reconciliation.

Changes: backend `6f11fc8b`, focused regression `1bacccdb` corrected CSV fixture `98531447`, staff warning `0b6902e7`. Require exact latest-SHA all-six-job hosted CI before marking this batch VERIFIED. Historical Yardi source contracts for financial fields remain unverified; do not allow leases, payments, deposits, GL, occupancy or financial postings.


## 23. Explicit source-version disposition diagnostics (2026-10-13)

The staff read-only `GET /runs/{run_id}/source-collisions` inventory now includes `skipped_rows`, `remaining_unskipped_rows` and `disposition_status` across **all** staged versions of a repeated source ID, not only the ten sampled row references. `UNRESOLVED_MULTIPLE` means more than one source row remains unskipped, `ONE_UNSKIPPED` means only one remains after explicit skip decisions, and `ALL_SKIPPED` means every version was explicitly skipped. Having one unskipped source is **not** automatic acceptance or import authorization. Distinct source fingerprints and past skipped copies remain visible and auditable.

The sampled-row references include only approved reason-code metadata for a recorded SKIP. Staff can navigate to a contributing upload in the existing platform-admin row review console to make separate authorized decisions. Existing reason-coded SKIP and audit history are authoritative; there is no auto-merge, automatic version selection, customer Lease creation, occupancy, payment, rent, deposit or accounting mutation.

**Verification (only after final confirmation):** The exact source SHA `b97164529c7ade8a8a6d07eb9330d83f4f7ab2e6`, run `38500928438`, passed all six required CI jobs. Source changes: backend `b4d137f6`, regression `dffd394a`, staff UI `19bf77dc`, navigation refresh `b9716452`. Historical financial and Yardi API contracts remain unavailable.

## 24. Accepted lease review across contradictory exact Unit parent evidence (2026-10-13)

**Provisional follow-on source pending its own exact-SHA CI:** The read-only lease relationship preview must agree with the already verified `ACCEPT_RELATIONSHIP` acceptance path when multiple staged Unit rows claim the **same exact reviewed source fingerprint and destination Unit** but provide different original source Property parents. A single-value dictionary projection can hide contradictions when a later reviewed row overwrites earlier evidence, falsely reporting an accepted lease identity relationship as current. Preserve every exact reviewed source-parent candidate, reject ambiguous or invalid exact evidence, and expose existing `UNIT_SOURCE_PARENT_MISMATCH` and `ACCEPTED_RELATIONSHIP_STALE` blockers. Legacy absent exact evidence remains unknown, not fabricated.

This is read-only preview hardening only. It does not revise old decisions, auto-merge source IDs, alter existing Property/Unit/Tenant targets, create customer leases or occupancy, or post rent, deposits or accounting. Require focused contradictory-source regression, exact-SHA hosted backend/PostgreSQL, frontend, platform-admin, security, E2E and staging CI.

## 25. Aggregate consistency for contradictory exact Unit source-parent reviews (2026-10-13)

The run-level `GET /runs/{run_id}/reconciliation` lease relationship summary must inspect **all** exact-fingerprint reviewed Unit source-parent evidence, matching the per-row preview and `ACCEPT_RELATIONSHIP` acceptance path. A single-value dictionary could silently overwrite earlier conflicting or invalid Unit source-parent records, misreporting `complete_identity_links` and `unit_source_parent_mismatch`. Conflicting or invalid exact evidence now increments `unit_source_parent_mismatch` and cannot count as complete identity links. Absent exact source evidence remains explicitly unknown and does not fabricate a source relationship.

This is a read-only correction to aggregate diagnostics. It does not change review decisions, revise durable mappings, select source versions, create leases or occupancy or post money. Provisional until focused regressions and six-job hosted exact-SHA CI pass.



## 26. Run-level coverage excludes unresolved duplicate lease source IDs (2026-10-13)

A run-level `complete_identity_links` count must agree with the per-lease `LEASE_SOURCE_ID_COLLISION` blocker. Two unskipped Yardi `LEASE_OCCUPANCY` rows with the same stable source ID must **not** be counted as independently complete just because their existing target identity mappings resolve. The reconciliation summary adds `lease_source_id_collisions`, counting each unskipped staged lease row blocked by a repeated unskipped source ID across all uploads of that organization and run. All such rows remain excluded from `complete_identity_links`. Explicit staff SKIP of unwanted versions changes the read-only count and can restore identity-link completeness for the sole remaining source row, but never automatically accepts the survivor or changes a customer record.

The Yardi staff console exposes the collision-row count next to existing source-parent and Unit/Property mismatch diagnostics. Focused regressions cover accepted source relationship before collision, a later conflicting upload, and reason-coded SKIP restoring the count. The summary remains descriptive only; it does not authorize lease, occupancy, financial posting, or import. This batch is provisional until exact-SHA six-job CI verification.

## 27. Accepted lease source-review staleness in aggregate diagnostics (2026-10-13)

An explicitly accepted source identity remains historical review evidence, not a perpetual approval. Even when updated same-run Property/Unit/Tenant mappings all point to valid active customer records, any recorded `ACCEPT_RELATIONSHIP` target snapshot mismatch must invalidate current acceptance, exactly as the per-row read-only lease relationship preview already does. The aggregate Yardi migration reconciliation now reports `accepted_relationship_stale` for previously accepted rows with altered resolved target IDs or unavailable, invalid or contradictory exact original Unit source-parent review evidence, excluding those rows from `complete_identity_links`. Duplicate source-ID blockers remain separately counted and are not automatically resolved.

Focused regression covers a later same-organization valid Tenant mapping drift that leaves dependency IDs valid but conflicts with the originally reviewed target. No prior audit history is rewritten and no customer entity, Lease, occupancy or financial transaction is created by this diagnostic. This batch is provisional until all six exact-SHA hosted CI jobs pass.


## 28. Disposition of a new duplicate after durable identity binding (2026-10-13)

The prior `/staged-rows/{row_id}/skip` guard rejected *every* source row when a durable same-run Yardi binding already existed. That prevented staff from explicitly skipping a newly uploaded duplicate source version, leaving a misleading unresolved collision after a legitimate reviewed identity mapping. Permit only a reason-coded SKIP of the separate unreviewed duplicate when an independent, valid `MATCH_EXISTING` staged row has exactly the bound run/org/provider/resource/source ID, fingerprint, destination target and resource-specific target field. Preserve the durable binding, original reviewed source row and independent decision evidence. Reject skipping the original reviewed row and orphan/stale source bindings without that anchor; preserve idempotent replay and reject changed SKIP reasons. Append retained-review metadata to the audit; invalidate prior dry-run fingerprint. No source auto-merge, new customer records, Lease/occupancy posting or accounting mutation. A focused backend regression checks ambiguous duplicate through explicit SKIP disposition, missing-anchor denial, replay, reason integrity and customer-data preservation. Verify exact source SHA six-job CI before marking complete.

## 29. Durable Unit source-parent inventory: preserve every exact review (2026-10-14)

The paginated read-only Yardi `/runs/{run_id}/bindings` Unit parent status previously fetched only the latest reviewed row by ID. This masked an earlier contradictory/invalid `MATCH_EXISTING` source-parent record sharing the durable binding's exact run, organization, provider, source ID, fingerprint and target Unit. Match the per-lease diagnostics: derive `unit_parent_relationship_current` from **all** exact reviewed records. Return `null` only for no exact reviewed evidence, `false` if any matching review is invalid, missing a source Property or disagrees with another exact review or current mapped Unit parent, and `true` only when all evidence agrees with an active target and reviewed same-run mapped source parent. A regression stages contradictory versions with a newer matching record (the former implementation's false positive), checks invalid evidence, then explicitly SKIPs the conflicting version and confirms status recovery and no customer business mutation. No automatic reconciliation, Unit movement, Lease creation or accounting operations. Full exact-SHA six-job CI is required before verification.

## 30. Invalid source precedence over historical identity review (2026-10-14)

The read-only Yardi run `/reconciliation` resource-coverage counters previously checked `MATCH_EXISTING` and `ACCEPT_RELATIONSHIP` before evaluating `row.errors` or `disposition=INVALID`. An invalidated staged source therefore still appeared as a successfully matched existing Property or accepted Lease relationship. Preserve explicit `SKIP` as its own audited disposition, then count any other invalid/errors row as `invalid` before interpreting its historical review decision. The review/audit action remains persisted but cannot inflate validated readiness. Regressions exercise invalid reviewed Property and invalid previously accepted Lease source, show current review-fingerprint changes, and assert no customer Property/Lease/User mutation. No source contract guessed or financial import enabled. Exact-SHA six-job CI required before verification.

## 31. Resource coverage rechecks active, nondeleted Property and Unit targets (2026-10-14)

The Yardi reconciliation resource counters for recorded `MATCH_EXISTING` Property and Unit rows previously validated organization membership and parent ID but omitted live `is_active` and soft-delete checks. A target could therefore remain counted as successfully matched even after Property or Unit deactivation/deletion, despite stricter durable-binding inventory and lease relationship diagnostics. Require live active/nondeleted same-organization Property for Property reviews and active/nondeleted Unit **and** parent Property for Unit review readiness. Preserve historical reviewed decisions and fingerprint reporting, classify stale identity rows as `needs_review` rather than valid `matched_existing`, and do not modify customer objects through migration. Regression checks inactive Property, soft-deleted Property, inactive Unit, and archived Unit's parent after previous valid review. CI exact SHA six-job green required.

The review fingerprint also incorporates current `resource_coverage` counts, so a Property/Unit becoming inactive, soft-deleted, or otherwise newly unresolved invalidates a previously saved Yardi dry-run even when the staged row and durable identity IDs do not change. Never treat static historical review evidence as continuing permission to migrate against changed customer targets.

## 32. Recorded identity review versus durable binding drift (2026-10-14)

Historical Yardi `MATCH_EXISTING` action alone does not prove a current exact source review. The read-only reconciliation resource readiness now checks a present durable same-run resource/source binding against the reviewed target ID and exact staged source fingerprint. If the fingerprint or target drifts (even to another active Unit in the same Property), the row is `needs_review` rather than `matched_existing`, and the review fingerprint changes. Previous audit evidence persists. A focused regression covers exact source-fingerprint drift, restoration, and same-property Unit target replacement; no customer Lease, transaction or credential mutation is authorized. Full six-job exact-SHA CI required.


## 33. Unskipped identity source versions invalidate recorded review (2026-10-14)

A durable Yardi Property, Unit, Owner, Vendor or Tenant identity binding does not
implicitly resolve a later staged upload with the same provider source ID. The
read-only reconciliation counts all unskipped versions per resource and source ID
within the same organization, provider and run. While multiple remain, historical
MATCH_EXISTING decisions and otherwise mapped identity rows show needs_review,
not matched_existing or mapped readiness. Source-review audit remains intact.
Staff must explicitly SKIP unwanted versions with the existing reason-code
audit and original review-anchor guard. Identical versions are not auto-merged.

Lease identity preview, the run-level relationship summary and the explicit
ACCEPT_RELATIONSHIP endpoint now reject competing unskipped Property, Unit or
Tenant source IDs, not just duplicate Lease source IDs. The lease summary exposes
identity_source_id_collisions and excludes ambiguous rows from complete identity
links; historical accepted rows are stale while collisions remain. Staff can
inspect a resource-specific source collision inventory and resolve duplicates
without customer business mutation. Regression tests cover new Unit source
version, stale accepted lease and dry-run fingerprint, explicit SKIP recovery,
and original customer data preservation. Verified as part of exact product SHA `e83cca4387ba1a23cefbc12f40eb49f1f205abb7`, GitHub Actions run 38673560425 SUCCESS: all six required jobs passed. No customer
Lease, occupancy, payment, financial or Yardi API mutation is enabled.


## 34. Durable binding inventory flags unresolved identity source collisions (2026-10-14)

A durably mapped Yardi source may still have multiple unskipped staged versions
across uploads. The staff read-only bindings inventory explicitly exposes
source_identity_collision for each affected Property, Unit, Owner, Vendor or
Tenant binding, separate from target_current. A Unit's original
unit_parent_relationship_current cannot remain true while any such collision
persists, even when all historical exact reviewed parents agree. In that case
the status is false pending explicit staff disposition, and the console says
that the source parent is unverified until duplicates are resolved. Target
activity continues to be reported independently. Staff also sees the
previously computed count of stale accepted lease source reviews directly in
the reconciliation summary, rather than relying on opening each lease row.

Existing regression now confirms one SKIP does not clear ambiguity while a
second duplicate remains unskipped; every unneeded version requires an audited
reason-coded SKIP and original reviewed anchor preservation. This only changes
diagnostics. It does not alter durable mappings, customer Units, Properties,
user identities, financial entries or lease records. Provisional until
dedicated exact-SHA six-job GitHub Actions CI passes.

## 35. Staff existing-target review rejects unresolved duplicate source IDs (2026-10-14)

An unskipped duplicate Yardi identity source version must not allow a staff
MATCH_EXISTING request or idempotent replay to report a current review.
All five explicitly reviewed existing-target resources (Properties, Units,
Owners, Vendors and Tenants) now check current same-provider/run/organization
duplicate source versions before reviewing or replaying a recorded match.
Staff must reason-code SKIP unwanted versions first. A regression covers
Property review blocked before a first match, recovery after SKIP, a new
duplicate making replay stale, and restoration only after another audited
SKIP, while preserving customer Property fields and prior review evidence.

This is metadata-only review safety and does not merge source versions,
alter customer business records or enable Yardi API, accounting, ownership
percentage or Lease/occupancy commit. Provisional until exact-SHA six-job
hosted CI verification.


## 36. Live Property/Unit target integrity for Yardi review and binding (2026-10-15)

Historical identity review does not guarantee that a customer target remains active. A Property review or replay now requires a currently active, non-soft-deleted organization-scoped Property. A Unit review or replay requires an active, nondeleted Unit and an active, nondeleted mapped parent Property. Unit durable binding and replay apply the same target and parent checks. This preserves prior audit decisions while preventing stale success responses; no customer business data, Lease, occupancy, financial record or unsupported Yardi API is mutated. Focused Property and Unit review regressions accompany this batch. Verify all six hosted jobs for the exact commit SHA before marking complete.

## 37. Unreviewed source-version and durable target-type readiness (2026-10-15)

A Yardi staged identity row with no explicit MATCH_EXISTING review must not be counted as `mapped` simply because a durable same-run record shares its provider source ID. Read-only reconciliation now requires the **exact staged source fingerprint** and correct resource-specific durable target entity type (Property, Unit, Owner user, Vendor, or Tenant user), in addition to the existing unresolved-source-collision guard. Stale or mistyped durable identity becomes `needs_review` and changes the review fingerprint, without editing review history or customer records. Focused regression covers unreviewed Property source-version drift, wrong entity type and restoration. Current customer target activity/parent checks for this unreviewed branch remain an independently actionable follow-on. Verify exact SHA all-six-job CI before marking complete; no Lease, occupancy, financial, ownership percentage or undocumented Yardi API operations are authorized.

## 38. Unreviewed exact durable identity requires live customer target (2026-10-15)

An unreviewed staged Yardi source may have the exact durable fingerprint and
correct target entity type but still point to a customer resource that is no
longer usable. Read-only reconciliation now counts it as `mapped` only when
the live target is valid: an active/nondeleted organization-scoped Property;
an active/nondeleted Unit whose active/nondeleted parent matches the original
source Property binding; an active, nondeleted correct-role Owner/Tenant user;
or a nondeleted Vendor. Otherwise the row is `needs_review`, and the
review dry-run fingerprint changes with the resource coverage. Historical
source decisions and durable mappings remain unchanged. Regression exercises
inactive/archived Property, inactive Unit, moved Unit, and restored readiness.
No customer business mutation, Lease, occupancy, financial posting, ownership
percentage or undocumented Yardi API is authorized. Exact-SHA six-job hosted
CI must pass before marking this batch verified.

## 39. Explicitly skipped invalid source rows cannot block safe identity binding (2026-10-15)

The five Yardi reviewed-existing identity binding endpoints previously rejected any staged source row with validation errors or INVALID disposition **before** honoring an explicit audited SKIP decision. This made it impossible to bind otherwise valid reviewed Properties, Units, Owners, Tenants or Vendors after staff had intentionally excluded an invalid source version. All five binders now check SKIP first, then reject invalid **non-skipped** rows. No invalid row is ever bound; the remaining reviewed rows still require exact-fingerprint dry-run, target checks, collision checks and replay safety. Focused Property and Vendor regressions prove invalid rows block binding before SKIP, then an audited reason-coded SKIP permits only the valid reviewed identity to bind without modifying customer records. This does not enable Lease/occupancy or financial import, or undocumented Yardi API assumptions. Verify all six hosted CI jobs at the exact source SHA before marking complete.

## 40. Property review replay must recheck current durable claims (2026-10-15)

The Yardi Property MATCH_EXISTING endpoint previously returned idempotent replay success after checking only whether its customer Property target remained active. A newer durable same-source fingerprint/target drift, a different Yardi source claiming that Property, or another reviewed row claiming it could therefore be hidden by an old review replay. Replayed reviews now recheck current durable source and target conflicts and other reviewed target claims before returning success. The regression covers an independent cross-run durable target claim appearing after the original review and confirms recovery once the conflict is resolved. The recorded review, audit and customer Property remain unchanged. No Lease/occupancy, financial, owner-percentage or undocumented API import is enabled. VERIFIED at source SHA `48d36e2c104cf23156de8a2b1ed7c262caac817d`, successful GitHub Actions run `38696745662` attempt 2 (all six jobs).

## 41. Owner, Tenant and Vendor review replay must check later staff claims (2026-10-15)

A retained MATCH_EXISTING action must not return idempotent success if another Yardi
reviewed source row in the same organization later claims the same Owner, Tenant
or Vendor customer target. The new-review checks existed, but all three replay
paths returned success before checking recorded competing staff claims. Replays
now apply the same claim guard under the existing target lock and preserve
source decisions, audit history and customer business objects. A parameterized
regression exercises the three resource types, a later competing recorded
review, refusal of stale replay and recovery once the conflict is removed.
No lease, occupancy, financial posting, automatic source merging or undocumented
Yardi API integration is authorized. VERIFIED at source SHA `a3b4ae52e97054ff692f854ca7f9400f5aec2c34`, successful GitHub Actions run `38778001779` (all six jobs).

## 42. Unit review replay rejects later staff claim and changed exact durable source (2026-10-15)

The read-only Unit MATCH_EXISTING replay must recheck any later reviewed target claim
across the organization and reject a same-run source binding whose target entity,
target ID or exact source fingerprint differs from the recorded Unit review.
The previous replay path checked competing UNIT target claims but skipped other
reviewed target evidence and permitted same-source fingerprint drift. A focused
regression simulates both independently and proves nonmutation and recovery
following resolution. No customer record, Lease, occupancy, financial posting
or undocumented Yardi API operation is authorized. VERIFIED at source SHA `1923bb64fd12a737536dc37c6d204e725eca523d`, successful GitHub Actions run `38779933369` (all six jobs).

## 44. Exact CI verification and replay regression gate checkpoint (2026-10-15)

Property identity review replay target-claim revalidation (section 40) is
VERIFIED at source SHA `48d36e2c104cf23156de8a2b1ed7c262caac817d`,
GitHub Actions run `38696745662`, successful attempt 2; all six jobs passed.
The first E2E attempt encountered an unrelated transient short-term-rentals
login navigation timeout, and rerunning the failed job passed.

Owner/Tenant/Vendor competing reviewed-target replay guards (section 41) are
VERIFIED at source SHA `a3b4ae52e97054ff692f854ca7f9400f5aec2c34`,
GitHub Actions run `38778001779`, all six jobs passed. Full backend/PostgreSQL
suite: 1296 passed, 21 deselected. A new fast CI gate now explicitly includes
the replay-claim and Unit replay regressions; the Unit replay product in section 42 was subsequently VERIFIED on exact SHA `1923bb64fd12a737536dc37c6d204e725eca523d`, GitHub Actions `38779933369` (all six jobs).


## 43. Exact durable-source fingerprint on replayed Owner, Tenant and Vendor review (2026-10-15)

A historical MATCH_EXISTING Owner, Tenant or Vendor review must not return replay
success when its same-run durable source record points at the same customer
entity but retains a different original staged fingerprint. Replays now compare
exact source fingerprint in the durable-claim conflict guard, in addition to
target entity, target ID and competing target sources. Parameterized regression
covers each resource's replay becoming stale, review persistence, customer
nonmutation and restored exact identity. No business record or financial posting
is created, amended or deleted. VERIFIED on exact SHA `79c531d8071bd088a4fbee256ba9e083f8da5f07` in successful GitHub Actions run `38803856489` (all six jobs).

## 45. Owner, Tenant and Vendor binding replay rechecks later staff claims (2026-10-15)

A later reviewed Yardi identity row from a separate run can claim an already
reviewed or durably bound Owner, Tenant or Vendor customer target. Previously
the binding endpoints only rechecked durable collisions, so initial binding or
idempotent replay could return success despite this retained staff-review
conflict. All three existing-target binders now check the organization-scoped
review claims after locking their live customer target. New binding and replay
return HTTP 409 until that claim is resolved, without rewriting audit history
or customer records. Parameterized regression tests both paths for all three
resources and verifies recovery and customer nonmutation. VERIFIED in five-resource binder checkpoint SHA `45060cd57670417370e0c9b8ff430341e3c4de2d`, GitHub Actions `38808091338` (all six jobs).

## 46. Property and Unit binding replay rechecks later staff claims (2026-10-15)

Existing Property and Unit target binders may likewise report success after a
separate same-organization Yardi run records a competing reviewed customer
target claim. Revalidate each locked live Property/Unit against all other
MATCH_EXISTING staff reviews before first durable binding and replay, not just
against committed durable source identity. Existing staff decisions and
customer resources are left intact. Dedicated regressions cover initial
binding refusal, recovery, replay refusal and nonmutation for both resource
types. VERIFIED with section 45 at exact SHA `45060cd57670417370e0c9b8ff430341e3c4de2d`, GitHub Actions `38808091338` (all six jobs).

## 46a. Repair same Yardi stable source identity across separate runs (2026-10-15)

The full PostgreSQL suite in GitHub run `38806268749` exposed a
regression missed by the fast Yardi tests:
`test_yardi_property_cross_run_binding::test_binding_blocks_same_source_id_claimed_by_another_run`.
Two historical runs with the SAME provider source ID can independently
record a review of the SAME target before any binding exists. The first
safe durable binding is allowed; the second conflicting attempt must
still be rejected by the existing durable target collision guard.
The newly added competing-staff-review check wrongly treated that same
stable source ID as a distinct customer identity claim, prematurely
blocking the first. All five binders now distinguish different source IDs
from repeated evidence for the same stable source identity. Later
different source ID reviews remain hard 409 blockers. Promote the legacy
cross-run binding test to the fast Yardi CI gate. No existing customer
or financial record is modified. VERIFIED at repaired SHA `45060cd57670417370e0c9b8ff430341e3c4de2d` in successful GitHub Actions run `38808091338` (all six jobs).

## 47. Cross-run staff target claims invalidate run-level identity readiness (2026-10-15)

Read-only Yardi reconciliation now rechecks prior MATCH_EXISTING staff claims
on the same target when a different source identity in the same organization,
provider and resource appears in another run. Previously safe reviewed and
durable mapped Property, Unit, Owner, Tenant and Vendor identity coverage is
reclassified needs_review, changing the exact review fingerprint and
invalidating stale dry-run evidence. Repeated review of the SAME stable source
ID across runs does not create a competing identity claim, matching the
existing binder safety guard in section 46a. Focused Owner/Tenant/Vendor
regressions cover reviewed and durable cases, competing claims, restoration,
same-source cross-run evidence, fingerprint drift and customer nonmutation.
The change makes no customer business mutations, does not erase prior reviews,
does not create a Lease or post financial records, and is VERIFIED at exact SHA `81a3fdcef15d04407809552fb05644ca1ae7ea0a`, successful GitHub Actions run `38810003222` (all six jobs).

## 48. Lease source acceptance rechecks competing customer-target reviews (2026-10-15)

Read-only lease source preview, aggregate readiness and explicit initial/replayed
ACCEPT_RELATIONSHIP now treat a different same-organization Yardi source ID's
retained MATCH_EXISTING staff claim on a mapped Property, Unit or Tenant target
as a collision. Diagnostic blockers and identity_target_review_collisions
counts invalidate previously accepted source relationships and fingerprinted
readiness without changing source decisions or customer records. The same
stable provider source ID reviewed again in another run is *not* a competing
identity, consistent with sections 46a and 47. Staff receive the count in
the existing internal console. Tenant-target regression covers conflicts,
stale replay, recovery, same-source evidence and no Lease/finance mutation.
VERIFIED at SHA `b73022f034852c07b79c50559ba8fbd424c20d9c`, GitHub Actions run `38812602409` SUCCESS, with backend, frontend, platform-admin, security, authenticated E2E and staging-config all passing.

## 49. Durable identity inventory flags competing reviewed customer targets (2026-10-15)

The read-only, organization-scoped durable mapping inventory now reports
target_review_collision independently of target_current and existing source
collision flags, so staff see active targets that another Yardi source claims.
Only a DIFFERENT provider source ID with retained MATCH_EXISTING review
counts as competition; another run reviewing the same stable source ID does
not make an otherwise valid binding stale. The console displays a clear
reconciliation warning. Vendor regression verifies conflict, recovery,
same-source cross-run handling and unchanged customer business data.
This does not rewrite source identities, alter customers or authorize financial
posting. Provisional until exact-SHA six-job hosted CI.

## 50. Exact identity-row readiness fingerprint, not aggregate-only (2026-10-15)

Read-only reconciliation's review_fingerprint now includes ordered, redacted
per-staged-row readiness classifications in its internal digest evidence.
Previously one customer target review conflict moving from durable source A to
source B could keep the same overall matched/needs_review counts and the same
fingerprint, silently reusing stale dry-run evidence for different safe rows.
New Vendor regression moves a competing historical review between two distinct
customer targets while resource coverage remains identical, proving the digest
changes without customer mutation. Fingerprint evidence is not exposed as raw
customer data and does not authorize creation, occupancy or financial posting.
VERIFIED on exact SHA `047da93677abaa1d088a770f942e27f4bf464971`, CI `38817670120` SUCCESS, all six required jobs.

## 51. Bounded reconciliation lookups and missing historical source claims (2026-10-15)

Run-level read-only Yardi identity reconciliation now loads same-organization
reviewed target claim metadata in one scoped projection instead of issuing one
competing-review SELECT for every staged identity row. Identity resource/target
keys map to all exact provider source IDs. Matching the same stable source ID
remains valid evidence, while a different source ID makes it contested.
Retained historical reviewed claims with missing (NULL) source IDs also fail
closed rather than disappearing under SQL three-valued inequality semantics.
Parameterized Owner/Tenant/Vendor regression checks NULL-source reviewed
target claims invalidate mapped readiness, review fingerprints and not customer
records. No official Yardi APIs, customer data mutation or financial posting
enabled. VERIFIED at exact SHA `5fc4bfca1f94912ea5a42c9c6ba6b3f182004759`, GitHub Actions `38823731721` SUCCESS (all six required jobs).

## 52. NULL-safe reviewed target claims across bind, preview and inventory (2026-10-15)

Retained historical MATCH_EXISTING claims with an unidentified (NULL) Yardi
source ID must not escape reviewed target collision guards through SQL's
three-valued NULL comparison semantics. All five reviewed existing-target
metadata binders, read-only binding inventory, lease relationship preview
and aggregate, and initial/replayed lease source acceptance now compare
source IDs with SQLAlchemy is_distinct_from, preserving valid same-provider
source-ID repetition but failing closed on unknown/different identities.
Parameterized Owner/Tenant/Vendor binding regressions, Vendor inventory
and accepted Tenant lease source regressions check historical NULL claims,
staff warning, aggregate blockers, replay refusal, and customer nonmutation.
These are metadata evidence checks only; no Lease, occupancy, accounting,
payments, or official undocumented Yardi API are enabled. VERIFIED at exact SHA
`4727e8803a028abbfc753db7b067f1e3fb89be0a`, GitHub Actions
`38826234779` SUCCESS (all six required jobs).

## 53. Per-lease readiness in review fingerprint (2026-10-15)

The Yardi reconciliation digest now includes private per-lease readiness
evidence. It changes when an external reviewed target claim moves between
two accepted lease source rows even though all aggregate counts remain
the same. A two-tenant, two-source-row regression checks the fingerprint
changes while customer records are untouched. Lease creation and financial
posting remain disabled. VERIFIED at exact SHA `3fba1305ce001ac7e83a1bcc2d54c8759a6d92c3`,
GitHub Actions `38827781535` SUCCESS (all six required jobs).

## 54. Batch reviewed target claims for lease summary and preview (2026-10-15)

The read-only per-Lease source relationship preview and reconciliation aggregate
reuse a single organization-scoped projection of retained reviewed
Property/Unit/Tenant target claims rather than issuing repeated SELECTs for
every staged Lease identity. Unknown historical (NULL) source IDs still contest
a customer target; identical source identities do not automatically become
new claims. A two-source Lease regression checks NULL-source collision warnings,
review invalidation, constant query counts, and preservation of customer data.
No Lease, occupancy, financial posting or undocumented Yardi API is enabled.
VERIFIED on exact source SHA `6cd613c2c5288e471315fb29416014179ae9e129`,
GitHub Actions `38831150479` SUCCESS: all six required jobs passed,
including 1,312 backend/PostgreSQL tests (21 deselected), authenticated
browser E2E, staging-config, frontend, security and platform-admin.

## 55. Batch retained review-claim lookups in durable identity inventory (2026-10-15)

The read-only Yardi durable binding inventory now projects retained
organization-scoped MATCH_EXISTING target claims for Properties, Units, Owners,
Vendors and Tenants once per page rather than querying each binding separately.
Historical missing (NULL) provider source IDs still contest valid target claims;
exact same-source identities, provider boundaries and organization boundaries
remain respected. A two-Vendor binding regression checks stable review-claim
SELECT count and preservation of customer vendor records. This batch does not
create, merge, delete or modify customer records, leases, occupancy, financial
posting or undocumented Yardi API behavior. VERIFIED on exact SHA `9d159a46b7b7365cbc38cc69b5a62acd760b72ea`, GitHub Actions
`38832851778` SUCCESS on all six required jobs.

## 56. Batch exact Unit parent review evidence per durable inventory page (2026-10-15)

Read-only Yardi Unit durable inventory now retrieves the exact staged Unit
source fingerprint and reviewed target matching each paginated durable binding
in one scoped query. All matching historical reviews remain evidence, including
contradictory source-parent relationships and unknown source IDs, so the source
parent cannot appear verified from a partial review. A two-Unit PostgreSQL
regression counts staged-review SELECTs independent of page size, checks live
parent classification and preservation of customer Properties/Units. This does
not create or alter any customer record, Lease/occupancy or financial posting,
nor assume undocumented Yardi API behavior. VERIFIED at exact SHA `24b702c6d517561d174f003c7f0f4844450397bd`, GitHub Actions `38836676853`
SUCCESS with backend/PostgreSQL, frontend, platform-admin, security,
authenticated E2E and staging-config all passing.

## 57. Fail closed on ambiguous mapped Property parent source (2026-10-15)

The read-only durable Unit inventory must not call the reviewed source-parent
relationship current merely because its active customer Unit still belongs to
the mapped Property when the underlying same-run Yardi Property source ID has
unskipped duplicate staged versions. Reuse organization/run-scoped unresolved
identity collisions to mark the source parent unverified until staff performs
an explicit reason-coded SKIP, without altering historical review evidence or
customer Properties/Units. A focused PostgreSQL regression exercises a new
Property source version, collision and SKIP recovery. This is source-evidence
metadata only, not customer data mutation or Lease/financial posting.
PROVISIONAL pending exact-SHA all-six-job hosted CI.


## 58. Distinguish mapped Property source collisions in durable Unit inventory (2026-10-15)

The existing read-only Unit binding inventory now returns a separate
`parent_source_identity_collision` diagnostic. It identifies unresolved
same-run, same-organization Yardi Property source-ID versions referenced by an
exact reviewed Unit source-parent relationship. The Unit's own
`source_identity_collision` remains independent of the Property diagnostic,
and the live customer target remains separately reported as `target_current`.
A focused PostgreSQL regression checks no collision, a newly uploaded differing
Property source version, and audited reason-coded SKIP recovery. The internal
staff console shows a distinct Property-parent collision warning. No customer
Property, Unit, Lease/occupancy or financial record mutation is enabled.

## 59. Original mapped Property fingerprint must remain current (2026-10-15)

Even when only one unskipped Yardi Property source version remains, the current
source-parent classification of an exact reviewed Unit cannot stay verified if
that Property version's fingerprint differs from the durable parent source
mapping. Bounded read-only inventory reads the relevant Property staged source
versions in one query per page, compares them to the exact durable Property
source fingerprint, and reports `parent_source_fingerprint_drift`. The Unit
source-parent status becomes false while drift exists, without changing customer
records or past staff reviews. Focused PostgreSQL regression checks a stale
fingerprint after duplicate SKIP, preservation of customer records, and recovery
when the correct fingerprint is restored.

## 60. Staff console identifies changed mapped Property source (2026-10-15)

The platform-admin Yardi durable identity inventory renders an explicit warning
for changed source-parent fingerprints, separately from unresolved parent
Property duplicates, Unit duplicates and genuine customer parent mismatch.
The warning is diagnostic only and does not authorize auto-matching, source
version merging, Lease creation, occupancy or financial posting.

**Verification gate for Sections 58–60:** Implemented as one cohesive source,
PostgreSQL regression and platform-admin UI batch. Provisional until exact-SHA
hosted CI verifies all six jobs. Sections 1–57 and external Yardi source
contract gates are preserved. No existing test was removed, disabled or weakened.

## 61. Page-scoped live customer target validation (2026-10-15)

The read-only durable Yardi inventory checks the current active and nondeleted state
of Property, Unit, Owner, Tenant and Vendor targets with bounded per-page queries.
Each Unit's current parent Property ID is retrieved with its live status.
Existing role, organization, entity type and original source-parent safeguards remain.

## 62. One mapped Property parent query per Unit inventory page (2026-10-15)

Original reviewed Unit parent identities are resolved through a page-batched lookup
of same-run and same-organization durable Property source mappings and fingerprints.
Conflicting historical mappings for one source identity fail closed rather than
choosing an arbitrary row. Existing source collision and fingerprint drift checks
remain independent of current customer target validity.

## 63. PostgreSQL query-count regression (2026-10-15)

An expanded two-Unit regression requires a constant one-SELECT count for the
historical exact Unit reviews, mapped Property parent identities and live Unit
parent validation when the inventory page grows from one Unit to two Units.
Prior source-parent and customer preservation assertions are retained.
All three changes are diagnostic only and require exact-SHA full CI verification.

## 64. Restrict reviewed target claim inventory to displayed targets (2026-10-15)

A durable identity inventory page now fetches retained Yardi MATCH_EXISTING
claims for the exact currently displayed resource and target IDs only. Earlier
logic projected every historical reviewed target in the organization; this
change preserves same-organization cross-run conflicts and unknown historical
source IDs while reducing unrelated database rows loaded.

## 65. Preserve historical unknown source claim evidence (2026-10-15)

Resource-specific paged target filters retain NULL provider source IDs as
competing evidence, and continue to distinguish an identical provider source
identity reviewed in another run from a genuinely different source claim.
Malformed durable target-entity metadata is not silently excluded from the
reviewed target claim collision diagnostic.

## 66. Page-boundary and scoped-claim regression (2026-10-15)

The existing Vendor inventory PostgreSQL regression now requires a targeted
historical review claim SELECT for nonempty pages, no such query for empty
pages, and different collision results when a competing source claims only
the second of two independently paged vendor targets. Existing cross-org,
same-source, unknown-source and customer data preservation checks remain.

These are metadata-only safety and query-bounding changes. Sections 64–66
require targeted backend review and exact-SHA all-six-job hosted CI before
VERIFIED. Nothing adds Lease/occupancy or financial mutations.

## Sections 57–60 exact-SHA verification checkpoint (2026-10-15)

The combined source at `94e2ebc7c30f271c5ac9d1d5044d68173df79b16`
passed GitHub Actions run `38839237751` SUCCESS with backend/PostgreSQL,
frontend, platform-admin, security, authenticated E2E and staging-config
all green. This verifies Sections 57–60 together, including the source-parent
collision and exact Property fingerprint diagnostics. Earlier run
`38838330535` was cancelled and is not independently marked successful.
Sections 61–66 remain PROVISIONAL pending their own exact-SHA hosted CI.

## 67. Restrict source collision aggregation to inventory page (2026-10-15)

Read-only durable Yardi binding inventory now computes unresolved unskipped
source-ID duplicates for the exact (resource, source ID) identities displayed
on the current page, rather than grouping every staged identity in the run.
This does not ignore any staged version of a displayed identity and never
resolves duplicate uploads automatically. Existing uncapped run-wide collision
callers continue to check the complete source population unchanged.

## 68. Preserve original Unit Property-parent collision evidence (2026-10-15)

Page-filtered Unit durable inventory includes source Property IDs recovered
from every exact reviewed Unit parent row, even when the staff filter is
`resource=UNITS` and no Property binding appears on that page. The filtered
query groups by resource and source ID, keeping overlapping Property and
Vendor source strings logically distinct. Empty pages short-circuit the
collision query without affecting the page count or staff no-store semantics.

## 69. Scoped collision inventory regression (2026-10-15)

The existing PostgreSQL tests now assert the identity key selection for a
Vendor-only page, all-resource page and empty page, and assert inclusion of
the original mapped Property source for a Unit-only page. Earlier duplicate,
reason-coded SKIP recovery, cross-run isolation and customer business record
preservation checks remain intact. No prior tests are deleted or weakened.
This is read-only metadata/query safety, not customer mutation, financial
posting, or a Yardi source contract expansion. Full exact-SHA CI is required
before marking Sections 67–69 VERIFIED.

## 70. Cross-run Property target review evidence for Unit parent (2026-10-15)

Original Unit parent readiness checks any other reviewed Yardi Property source claim on its mapped customer Property. Different or unknown source IDs fail closed, and same stable source ID across runs remains valid.

## 71. One page-batched Property parent claim query and staff diagnostic (2026-10-15)

Read-only Unit inventory uses one organization-scoped source-review query for all mapped parent Property targets in the page. The staff console distinguishes this conflict from staged duplicate source IDs, changed fingerprints and customer target activity.

## 72. Regression for Property review conflict and source identity (2026-10-15)

PostgreSQL checks conflicting Property review, recovery, identical cross-run source, unknown historical source and constant query count for multiple Units. No existing test is removed or relaxed. No customer entity, Lease, accounting entry or external Yardi API is created. Requires exact-SHA hosted CI.

## Sections 61–66 exact source verification (2026-10-15)

The page-batched customer target, exact original mapped Property parent, and paginated reviewed-claim integrity milestone passed GitHub Actions `38841035779` at exact source SHA `cc211aca54c6e9d34e22d1e39a8459d9efc08f1c`. All six required CI jobs passed: PostgreSQL/backend, frontend, platform-admin, security, authenticated E2E, and staging-config. This supersedes earlier provisional statements for Sections 61–66. Sections 67–72 are now published as the next milestone and remain provisional pending their own full exact-SHA CI. No source contract blocker has been waived.


## 73. Original Unit parent rejects competing durable Property identities (2026-10-15)

A retained durable YARDI Property binding, including historical bindings without
staged staff-review evidence, can claim the same customer parent Property as an
exact-reviewed Unit original source parent. The read-only Unit inventory now
checks all same-organization YARDI Property durable source identities assigned
to mapped parent targets. A *different* stable provider source ID fails closed,
while repeated identical source ID evidence across runs remains non-competing.
These diagnostics remain separate from reviewed-target claims, unskipped staged
source-ID collisions and exact Property source-fingerprint drift. Historical
mappings are not changed and no customer object is mutated.

## 74. Scoped page-batched durable parent claims and staff warning (2026-10-15)

One bounded query retrieves Property durable source-ID claims for the exact
customer parent target IDs referenced by the current Unit inventory page. It
filters provider and organization and does not load unrelated Yardi entities.
The `parent_target_binding_collision` field is null without an exact mapped
source-parent, false with no competing durable source, true when contested.
The internal platform-admin console explains that a different durable Yardi
Property identity claims this Unit's mapped parent. It does not auto-merge,
repair source IDs or alter customer records.

## 75. PostgreSQL collision, recovery and query-count regressions (2026-10-15)

Extend the existing original Unit parent PostgreSQL regression to verify a
competing historical cross-run durable Property source identity blocks verified
source-parent readiness, an identical stable source ID restores it, and foreign
provider/organization evidence cannot contaminate the status. The two-Unit
inventory query-count test requires one page-batched durable parent target claim
SELECT as the page grows from one Unit to two. Existing tests remain intact;
none are deleted, skipped or weakened. This is read-only identity metadata,
not Lease/occupancy creation, account posting, ownership percent inference or
unsupported Yardi API integration. Sections 73–75 remain PROVISIONAL pending
exact-SHA all-six-job hosted CI.


## 76. Detect different durable source claims for every existing-identity target (2026-10-15)

The read-only Yardi durable inventory now exposes an independent
`target_binding_collision` flag on Properties, Units, Owners, Vendors and
Tenants. A later or historical same-organization YARDI durable binding to the
same customer entity/target ID with a different stable provider source ID
makes the target contested even when no historical staged MATCH_EXISTING
review is retained. The exact same stable provider source ID across runs is
not a different customer source identity. This warning does not mutate source
mappings or customer records.

## 77. Share one page-scoped durable target-claim projection (2026-10-15)

Instead of a separate original Unit Property-parent durable binding lookup,
one bounded organization/provider-scoped query collects resource/target/source
identity triples for the displayed inventory page plus original mapped
Property parent target IDs of exact reviewed Units. Resource and target ID
are both part of the key, preventing cross-resource contamination. Existing
parent source version, reviewed target claim and parent-mapping safeguards
remain independently reported. The internal console shows the distinct
durable target claim warning on all five supported identity resources.

## 78. Five-resource collision and pagination regression (2026-10-15)

A new PostgreSQL regression covers Properties, Units, Owners, Vendors and
Tenants, each with a historical different-source durable binding, then
restoration through the same stable source ID; it checks read-only flags and
preserved customer business records. A second Vendor page is tested
independently to prevent unrelated target claim leakage. Existing original
Unit parent query-count assertions remain unchanged. No test is deleted or
weakened. These are metadata-only diagnostics with no customer Lease,
occupancy, accounting or unsupported official Yardi API mutation.

**Sections 76–78 verification:** PREPARED as one cohesive batch, pending
exact-SHA hosted backend/PostgreSQL, frontend, platform-admin, security,
authenticated E2E and staging-config CI. Never mark VERIFIED prematurely.


## 79. Conflicted durable Unit target invalidates original source-parent readiness (2026-10-15)

A currently active customer Unit can still have a different same-organization
Yardi durable source identity claiming its target. Such a contested Unit cannot
report its original source-parent relationship VERIFIED merely because the live
Unit still belongs to the same mapped Property. Keep `target_current`
independent; `unit_parent_relationship_current` fails closed when
`target_binding_collision` is true. A repeated durable source ID across
runs remains non-competing.

## 80. Retained competing Unit reviews also fail closed on parent readiness (2026-10-15)

An earlier or later MATCH_EXISTING staged Unit review with a different or
unknown source ID that claims the same Unit target independently invalidates
the original Unit parent certainty, even without a competing durable binding.
An identical stable source ID reviewed again in another run is allowed.
The staff console identifies the contested Unit target instead of presenting a
generic Property parent mismatch. No historical review or customer Unit changes.

## 81. Cross-run durable and reviewed Unit target regression (2026-10-15)

Extend the existing PostgreSQL exact Unit source-parent safety regression with
a different cross-run durable Unit binding, same-source restoration, a second
run's competing MATCH_EXISTING Unit review, same-source restoration, and NULL
historical reviewed-source fail-closed handling. Original customer Property
and Unit data and all previous regression assertions remain intact.
These are diagnostic-only safeguards, with no owner, lease, occupancy,
financial or unofficial Yardi API mutation. PREPARED pending exact-SHA all-six
GitHub Actions jobs after prerequisite Sections 73–78 have passed.


## 82. Reconcile durable Yardi source identities across runs (2026-10-15)

The original source ID for a committed Property, Unit, Owner, Vendor or
Tenant must not appear unambiguous when historical same-organization Yardi
durable bindings map that SAME provider source ID to a DIFFERENT customer
target entity or target ID. The read-only bindings inventory now reports a
distinct `source_target_binding_collision` flag without changing mappings,
source decisions or customer records. Repeated evidence mapping to the
same entity and target ID remains nonconflicting.

## 83. Batch cross-run exact-source target lookups per inventory page (2026-10-15)

One provider- and organization-scoped projection loads durable
(resource, source ID, target entity, target ID) mappings for only displayed
source IDs plus the exact original source Property parents referenced by
reviewed Unit rows. Resource is part of the key, preventing a Property ID
string from colliding with a Vendor source of the same literal name.
No broad historical database scan is needed for empty inventory pages.

## 84. Five-resource original-source divergence regression (2026-10-15)

PostgreSQL tests retain earlier durable target-claim regressions and now
check that the same stable Yardi source ID mapped to different customer
Property, Unit, Owner, Vendor and Tenant targets in another run is flagged,
even though the current customer target remains active and no distinct
source ID claims it. Restoring the exact original customer targets clears
the new diagnostic. Historical mapping evidence and customer object data
remain intact.

## 85. Original Unit Property source cannot bind a different Property elsewhere (2026-10-15)

An exactly reviewed Unit may still belong to its mapped active customer
Property while the original Yardi `source_property_id` is durably associated
with a DIFFERENT customer Property in another Yardi run. The original Unit
parent status now fails closed and exposes `parent_source_binding_collision`.
This is independent of different Yardi sources claiming the same customer
parent, and independent of staged source version collisions.

## 86. Original Unit source identity cannot diverge to a different Unit (2026-10-15)

A committed Unit source ID bound to another customer Unit elsewhere makes
the historical Unit's original source-parent certainty unverified even when
its current customer Unit is active and correctly parented. The generic
`source_target_binding_collision` flag and parent-specific status now agree,
and the staff console distinguishes both from actual Property reparenting.

## 87. Historical source-target preservation and staff diagnostic regression (2026-10-15)

Regression exercises a same-source Property bound elsewhere, an original
Unit source bound to another target, and exact target restoration, along
with the five-resource cases above. The console gives separate
source-to-target divergence warnings. No prior tests are deleted, skipped or
relaxed. All safeguards are read-only metadata and require all-six-job
exact-SHA hosted CI before VERIFIED. No Lease, occupancy, accounting,
ownership, customer business mutation or undocumented Yardi API is enabled.


## Sections 73–75 exact-SHA verification checkpoint (2026-10-15)

Source `6c8bafacd8c4bb7b616c5fc58d79498552ff1d01` passed GitHub Actions
`38844772878`: all six jobs SUCCESS (PostgreSQL/backend, frontend,
platform-admin, security, authenticated E2E, staging-config). The additional
cross-run durable Property parent review safety is VERIFIED. Earlier notes
marked PREPARED are historical. Sections 76–87 are grouped into the next
single source milestone and remain PROVISIONAL until all-six hosted exact-SHA
CI succeeds. No customer data mutation or financial/Lease posting enabled.


## Sections 76–87 fast CI fixture repair gate (2026-10-15)

GitHub Actions run `38845907917` on exact source `d8205d36` failed one
new Unit PostgreSQL regression fixture: its source CSV contained literal
backslash-n bytes instead of real CSV record separators. Corrected only the
test's CSV data literal, preserving every test and the entire product
implementation. Original fast suite had 69 passing tests and one fixture
error; frontend/platform-admin/security passed and E2E/staging skipped.
Sections 76–87 remain PROVISIONAL until the repaired product SHA passes all
six required hosted jobs. No roadmap item is skipped or treated as verified.


## 88. Lease relationships reject competing durable customer-target claims (2026-10-16)

Read-only Yardi Lease relationship preview now checks same-organization,
same-provider durable Property, Unit and Tenant bindings from other migration
runs. A different stable Yardi provider source ID mapped to the same customer
target is a collision, even if no historical staged MATCH_EXISTING row exists.
Each dependency can surface an explicit resource-specific
`*_TARGET_BINDING_COLLISION` blocker. Repetition of the SAME source ID to
the SAME entity and target across runs is not a conflict. No historical binding
is automatically merged or modified.

## 89. Lease source divergence and accepted replay fail closed (2026-10-16)

The same provider source ID must not map to a different entity or customer
target in another Yardi run. Lease preview surfaces resource-specific
`*_SOURCE_BINDING_COLLISION` blockers. Shared page/run-scoped durable-claim
projection supports the preview, aggregate reconciliation and explicit
initial/replayed ACCEPT_RELATIONSHIP checks without querying each historical
claim separately for every Lease row. The aggregate exposes separate counts
`identity_target_binding_collisions` and
`identity_source_binding_collisions`. Both deny complete identity links,
invalidate accepted source-review readiness and enter the exact per-Lease
private review fingerprint evidence. The staff console exposes the aggregate
counts. Neither a Lease, occupancy, rent, charge, bank movement, GL posting,
user entitlement, nor source identity overwrite is authorized.

## 90. Three-resource durable relationship safety regression (2026-10-16)

Eight PostgreSQL parameterized cases cover Property/Unit/Tenant target claims
and same-source divergent mappings, including a live accepted Lease replay
becoming stale, 409 refusal without historical review mutation, reasoned
restoration by reconciling the independently retained historical mapping
metadata, exact review fingerprint changes, plus provider and organization
boundaries. Customer Lease table and original Property, Unit and Tenant fields
remain unchanged. Existing regression tests are retained; no test removed,
disabled, skipped or weakened. Only the existing Yardi files, existing
applicable contracts and read-only diagnostic staff console are modified.

**Verification:** Sections 76-87 source
`76508641742b1650f00404ed2f1ac483c35fc938` is VERIFIED in
GitHub Actions run `38846302757` (all six required jobs PASS). Sections
88-90 are PROVISIONAL pending their own exact-source six-job hosted CI.
Financial and official Yardi API source contracts remain blocked.


## 91. Bound lease source-to-target mapping by preview page (2026-10-16)

The Yardi read-only Lease relationship preview now gathers the exact staged
Property, Unit and Tenant source IDs referenced by only the selected page.
Its durable identity mapping lookup is filtered by resource and source ID
instead of loading every run-level binding. Missing source IDs remain missing;
no synthetic matches or customer record updates are made. Empty pages do not
query source-to-target mappings.

## 92. Retain complete relevant Unit parent and source collision history (2026-10-16)

The same preview scopes exact historical Unit MATCH_EXISTING parent evidence
and unresolved staged Property/Unit/Tenant source collision aggregation to
source identities referenced by that page. It still considers ALL historical
same-run versions, including other uploads outside the page. It never
chooses only the newest original Unit source parent or treats explicit
SKIP as automatically merging conflicting identities.

## 93. Page-bound lease duplicate and cross-run staff claim projection (2026-10-16)

Duplicate Lease source-ID checks select all same-run source versions for only
the Lease IDs displayed in the page, retaining off-page duplicate blockers.
Reviewed Yardi source claims from ANY run in the organization are scoped to
the current page's mapped customer target IDs and resource. Unknown historical
NULL source IDs remain contested. The source/target exact durable history
checks from Sections 88–90 remain independent and active.

## 94. Pagination integrity, SQL-scope and customer preservation tests (2026-10-16)

The existing PostgreSQL Lease acceptance regression suite adds a test for
two Lease pages plus off-page duplicate version, a missing-identity page,
empty-page query filtering, and source-ID-scoped SQL. A second test confirms
a new Unit source version from a separate upload still makes the current
page's Unit mapping ambiguous. All tests are retained; no test removed,
relaxed, skipped or disabled. No customer Leases, Property/Unit details,
Tenant login/hash, payments or accounting are created or changed.

**Verification gate:** These four changes are a single provisional
read-only source and regression batch. Require full six-job GitHub Actions
at its exact published SHA before calling Sections 91–94 VERIFIED.
Sections 88–90 source `76ddbf9a9797c61e587826d77972ce9a1a1893ef`
was published before this follow-up and must be verified by its own CI
run `38850364542`; the run was in progress when this batch was prepared.

## 95. Explicit Lease source review readiness separate from identity linkage (2026-10-16)

The read-only per-Lease Yardi source relationship preview now reports
`source_review_ready` independently from `identity_links_complete`. Complete
Property, Unit and Tenant customer identity links alone are not sufficient for
an explicit staff ACCEPT_RELATIONSHIP decision. Source review readiness
additionally requires exact explicitly reviewed Unit original source-parent
evidence agreeing with the Lease's Yardi Property source, plus the absence of
the existing source, durable claim, customer and duplicate blockers. No
customer Lease or occupancy is authorized by this diagnostic flag.

## 96. Aggregate unverified parent and accepted source readiness counts (2026-10-16)

Run-level read-only reconciliation now separately reports
`unit_source_parent_unverified` when a valid linked Unit has no exact
MATCH_EXISTING source-parent evidence, and `source_review_ready` for Lease
rows whose identity links and original Unit source relationship are currently
verified. Existing `complete_identity_links` retains its original meaning
and is not silently reinterpreted or weakened. Exact per-Lease readiness
enters the private review fingerprint so old dry runs cannot mask changed
source evidence. Initial and replayed acceptance remain strictly guarded.

## 97. Staff console differentiates source readiness and identity links (2026-10-16)

The authenticated internal Yardi staff console displays both aggregate counts
and a per-Lease source review readiness indicator, explicitly warning when
otherwise resolved identity links still lack the original Unit source-parent
review or have current blockers. It never offers automatic Lease/customer
record creation or financial posting.

## 98. PostgreSQL incomplete source-review and recovery regression (2026-10-16)

A regression starts with complete Property/Unit/Tenant durable identity links,
then removes exact original Unit MATCH_EXISTING source evidence. Preview still
reports complete identity links but no source-review readiness; aggregate
counts classify the unknown parent; explicit acceptance returns HTTP 409.
Restoring original exact reviewed evidence changes the review fingerprint,
allows metadata-only acceptance and preserves customer business fields.
Moving the currently active customer Unit later makes source readiness false
even though historical source evidence remains. All earlier tests remain;
no customer Lease, GL, payment, user hash or ownership is modified.

Sections 95-98 are a single PROVISIONAL metadata-only milestone, prepared on
top of Sections 91-94; neither is VERIFIED until hosted exact-SHA CI passes
all six required jobs. The source transport contract blockers remain intact.

## 99. Aggregate reconciliation projects only involved reviewed customer targets (2026-10-16)

The run-level read-only Yardi reconciliation retains cross-run historical
MATCH_EXISTING review claims but scopes them to relevant resource/target IDs
from this run's durable identity metadata and its staged explicit source-review
decisions. Historical accepted Lease target snapshots are also included for
conservative visibility. Unrelated same-organization target review records
are no longer loaded during every run reconciliation.

## 100. Preserve cross-run unknown and different source collision semantics (2026-10-16)

The scoped review projection continues treating a different Yardi provider
source ID, including historical NULL/unknown IDs, as a conflict for the exact
customer target. A stable identical provider source ID reviewed again in a
second run remains a non-competing claim. Scope by resource and actual target
ID to avoid unrelated Property, Owner, Tenant, Vendor and Unit contamination.
All original record-level review decisions and mappings remain unmodified.

## 101. Preserve exact per-identity and per-Lease fingerprints (2026-10-16)

Read-only reconciliation continues to fingerprint the exact identity and
Lease row readiness, not merely aggregate counts, so moving a reviewed claim
between two relevant targets changes the digest even when totals do not.
Non-affecting unrelated customer target claims must not create spurious
collisions. No business data or staged historical audit evidence is edited.

## 102. Scoped reviewed-claim SQL and customer-preservation regression (2026-10-16)

A focused PostgreSQL regression uses a separately staged reviewed Tenant
source whose customer target is initially unrelated to the migration run,
then changes it to contest this run's Tenant and restores it to the same
stable Yardi source identity. It asserts SQL target-ID-scoping, same-run
Lease readiness invalidation, fingerprint changes and preserved customer
Lease records and login hashes. Existing regression assertions are retained;
no test removed, disabled or weakened.

Sections 99-102 remain PROVISIONAL pending exact-SHA six-job hosted CI after
Sections 95-98 have passed. The official Yardi source contract, accounting,
lease/occupancy business commit and customer mutation gates remain unchanged.


## Consolidated Sections 91–102 milestone gate (2026-10-16)

Sections 91–102 form three four-requirement Lease read-only safety/performance
batches in one source milestone and one intended hosted six-job CI. Existing
coverage and source-contract blockers are preserved. Source `76ddbf9a9797c61e587826d77972ce9a1a1893ef`
(Sections 88–90) must pass exact-SHA CI before publication; this consolidated
milestone remains PROVISIONAL until its own full six-job CI succeeds.


## Sections 88–90 exact-SHA verification (2026-10-16)

Source `76ddbf9a9797c61e587826d77972ce9a1a1893ef` successfully completed GitHub Actions `38850364542`:
all six required jobs passed (backend/PostgreSQL, frontend, security,
platform-admin, staging-config, authenticated E2E). The three-resource
cross-run durable Lease collision safety is VERIFIED. Sections 91–102
remain PROVISIONAL until their own exact-source hosted six-job CI passes.

## 103. Batch live reconciliation customer target validity (2026-10-16)

The read-only Yardi run-level resource reconciliation preloads active,
nondeleted, organization-scoped customer Property, Unit and Unit parent,
role-correct Owner/Tenant user, and nondeleted Vendor target IDs in bounded
resource projections. Both explicit MATCH_EXISTING review evidence and
unreviewed exact-durable-identity readiness share these current target checks.
Historical decisions, source row fingerprints and customer data stay unchanged.

## 104. Preserve original reviewed Unit parent and invalid-target semantics

The batched Unit projection includes current parent Property identity and
continues to reject inactive, deleted or wrong-organization parents and
reparented Units. A reviewed Unit still requires matching original source
Property identity, while a durable unreviewed Unit still needs the exact source
fingerprint and active mapped customer parent. User roles and Vendor deletion
status retain their previous eligibility checks. Review fingerprint changes
with readiness, never with unreviewed customer data details.

## 105. SQL-count, recovery and nonmutation PostgreSQL gate

A dedicated PostgreSQL regression stages two different Property sources, one
unreviewed exact bound and another explicitly reviewed MATCH_EXISTING row,
asserts that the count of live Property SELECTs stays constant, then archives
and restores the second Property to validate stale readiness and fingerprint
recovery. Existing tests remain untouched; the fast Yardi CI gate includes
this regression ahead of the full PostgreSQL suite.

**Status:** Sections 103-105 PROVISIONAL until all six hosted CI jobs pass at
their exact published source SHA. No existing test deleted, disabled, skipped,
or weakened; no customer Lease/occupancy or accounting posting enabled. The
original external Yardi export and API source contract restrictions remain.

## 106. Cross-run durable claims invalidate reviewed Yardi identity readiness (2026-10-16)

A retained staff MATCH_EXISTING identity is not current merely because its
customer target is active and its own same-run durable fingerprint agrees.
Reconciliation now checks independently retained same-organization Yardi durable
source-to-target history across all five identity resources. A different
provider source ID durably claiming the same target or the SAME source ID
durably mapped to a different customer target makes recorded review
`needs_review`. Exact same source/target evidence across runs is not a
competing identity. Original reviewed action and audit remain untouched.

## 107. Unreviewed exact durable identity also fails closed on history

Read-only reconciliation applies the same cross-run durable source and target
conflict guard to exact-fingerprint unreviewed durable identity coverage,
without changing existing current-target, source-duplicate, wrong-entity,
reviewed-claim or Unit parent checks. The bounded scoped historical projection
reuses the established Lease-claim helper, extended to Owner and Vendor and
optional reviewed identity records. Existing Lease callers continue limiting
their projection to Property, Unit and Tenant mapping inputs.

## 108. Five-resource cross-run collision and recovery regressions

A parameterized PostgreSQL test covers Property, Unit, Owner, Vendor and Tenant
MATCH_EXISTING readiness; every case checks unrelated provider and organization
isolation, competing different source-to-same-target refusal, same-source
same-target recovery, same-source different-target refusal, exact review
fingerprint restoration and unchanged customer data/password hashes. The
fast Yardi CI gate includes the test and all old tests remain enabled.

**Verification:** Sections 106-108 PROVISIONAL until exact-SHA all-six-job
hosted CI. No customer mutation, Lease/occupancy commit, accounting posting,
ownership change, or invented official Yardi API transport.

## 109. Reviewed Unit identity follows contested original Property source (2026-10-16)

Run-level Yardi resource reconciliation already checks a reviewed Unit's
original source Property against the current same-run durable Property target.
It now additionally fails closed when another same-organization Yardi durable
source ID claims that same customer Property, or when the original Property
source ID was mapped to a different target in another Yardi run. Independent
retained differently identified staff Property reviews likewise block current
review classification even when the customer Unit remains active and parented.

## 110. Preserve unreviewed Unit parent claim parity

An exact-fingerprint unreviewed durably mapped Unit can only count as mapped
when the original mapped Property also has no competing durable or staff
source-to-target claim. Different-source and same-source divergence are distinct
from live customer property activity and Unit reparenting, both of which remain
guarded independently. Same stable source and same customer Property evidence
across runs remains valid.

## 111. Original Unit parent reviewer/durable collision regression

A two-mode PostgreSQL test starts with exact reviewed and exact unreviewed
Unit identities, adds a competing different source-to-same-Property durable
claim, restores the same stable source, then tests same-source divergence to
another customer Property. It also simulates historical competing staff
Property review and recovery, checking per-identity readiness, review
fingerprints, preserved customer property/unit/user values and no mutations.
Fast Yardi CI includes it; no existing tests removed, disabled or weakened.

**Status:** Sections 109-111 detached and PROVISIONAL. Hosted CI must pass
all six jobs at the exact eventually published SHA. No customer creation,
Lease/occupancy mutation, accounting posting or undocumented Yardi API.

## 112. Exact resource/source lookup for Yardi run reconciliation (2026-10-16)

The provider-labelled Yardi source-to-target mapping table already enforces a
unique mapping for (run, resource, source ID). Read-only run reconciliation now
indexes those durable identities once using this exact composite key instead
of scanning every historical item list for every staged source row.
It preserves per-resource distinction even when Yardi uses identical literal
source IDs for a Property, Vendor, Unit or other resource.

## 113. Original Unit parent and Lease summary use the same identity index

Both explicit MATCH_EXISTING Unit review and unreviewed exact-fingerprint
durable Unit readiness resolve original source Property identity using the
same composite mapping index, preserving target entity checks and all original
parent collision safeguards. The Lease relationship aggregate likewise reuses
the index for exact Property, Unit and Tenant source relationships. No change
to aggregate counts, review fingerprints or business import permissions is
intended for otherwise identical inputs.

## 114. Resource collision, Unit parent and fingerprint regression

A focused PostgreSQL regression stages a Property and Vendor sharing the same
source ID literal and a Unit whose original source-parent is that Property.
It proves all three remain separately mapped, then corrupts only the Vendor
mapping target entity. Vendor readiness becomes stale while Property and Unit
remain current. Restoring the Vendor target entity restores the exact original
review fingerprint and leaves customer records unchanged. Fast Yardi CI adds
this test without removing or weakening any existing assertion.

**Status:** Sections 112-114 PREPARED and require exact-SHA six-job hosted CI
before VERIFIED. This metadata-only optimization changes no customer record,
Lease/occupancy, finance, ownership or unsupported official Yardi API.

## Exact milestone verification and next gate (2026-10-16)

Sections 103-105 exact product SHA
`ea086b7a93171955422fb7744dea4443c98e3418`, GitHub Actions
`38854378709` SUCCESS all six jobs: PostgreSQL/backend, frontend,
platform-admin, security, E2E and staging-config. VERIFIED.
Sections 106-114 comprise one three-group follow-up and remain PROVISIONAL
until six-job CI passes on their actual published source SHA. The previous
source-contract and no-customer-mutation safety restrictions apply unchanged.


## 115. Reuse verified target projections in Lease reconciliation (2026-10-16)

Run-level Yardi reconciliation already validates live organization-scoped Property,
Unit and Tenant targets for every source identity. Lease aggregate readiness now
reuses those exact existing live target projections rather than rerunning three
separate Property/Unit/Tenant SELECTs. It intersects mapped correct-entity
targets with active valid targets; unrelated or wrong-entity mappings remain
excluded, and invalid source relationships still fail closed. No target changes.

## 116. Preserve stale Lease readiness and source identity semantics

The same per-Lease checks remain in place: original Unit source parent, mapped
Property, active Unit and Tenant, same-run unskipped source collision, retained
staff reviews, cross-run durable collisions, original accepted target snapshot
and exact private review fingerprints. Missing/deactivated Property still
invalidates its dependent Unit and Lease identities. This refactor shares
the same read-only live customer snapshot, never implies authorization to post
Lease, occupancy, payment, rent, deposit or accounting history.

## 117. Strict per-call target-query regression and recovery

New PostgreSQL regression `test_yardi_reconciliation_lease_snapshot.py`
records the live target SQL projections and requires exactly one Property,
one Unit/Property and one Tenant query per reconciliation regardless of one
or two staged Leases. It verifies that temporarily inactive original Property
invalidates identity links and fingerprint, reactivation restores exact
fingerprint, second Lease source mismatch is reported, and customer Property,
Unit, tenant password hash, existing Lease count and durable identity count
remain untouched. The test is added to the fast Yardi CI gate without deleting,
disabling or weakening any other test.

**Sections 115–117 status:** PROVISIONAL until all six hosted CI jobs pass at
their exact source commit SHA. The authoritative Yardi export/API and
accounting source-contract gates remain unchanged.


## 118. Share one durable-claim history between identity and Lease readiness

Run-level Yardi reconciliation already loads cross-run historical durable
Property/Unit/Tenant and other identity source-to-target claims, including
claims from explicit current-run staff-reviewed rows. The Lease aggregate
now reuses this read-only historical projection rather than issuing a second
overlapping organization-wide lookup. This reduces duplicate historical
SELECTs while keeping the same resource/provider/organization boundaries.

## 119. Preserve both directions of historical Lease identity conflict

The shared source snapshot retains different source IDs durably claiming the
same customer Property, Unit or Tenant, and the same provider source ID
durably claiming a different customer target or target entity. Matching
source/customer evidence in another run remains non-conflicting. Historical
missing/unknown and divergent identities remain blocked, and exact private
readiness fingerprints reflect relevant changes. Neither a Lease nor a payment
nor occupancy is created from an accepted source review.

## 120. Single-projection, target/source divergence and recovery regression

A focused PostgreSQL regression instruments historical durable-claim helper
invocation and enforces exactly one scoped projection per reconciliation
request. It tests a competing Property target from another run, the
same source/target identity recovery, divergent same-source/different-target
rejection, exact review fingerprint restoration, role/organization-scoped
source evidence, customer and login preservation, and zero Lease creation.
The test is included in the fast Yardi CI gate. Previously required tests
are neither deleted, weakened nor skipped.

**Status:** Sections 118–120 PROVISIONAL until exact-SHA all-six-job hosted
CI. Preserve all Yardi source-contract, accounting, Lease and customer-mutation
prohibitions and all previously verified requirements.

## 121. Original Property exact source version guards Yardi Lease acceptance

The same-run Yardi Property source may have only ONE unskipped staged version,
yet that version can differ from the previously bound exact Property source
fingerprint. A read-only guard now compares all unskipped staged Property
versions against exact durable Property identities in the current run and
refuses current original Unit source-parent readiness where the original
Property binding is contradicted. The paginated Lease preview reports
`PROPERTY_SOURCE_VERSION_DRIFT`, and initial/replayed explicit
ACCEPT_RELATIONSHIP returns 409 rather than silently reusing an older source
review. A source version not staged in the run is never invented.

## 122. Separate original Property drift from duplicate source identities

Run-level Lease readiness now reports `parent_property_source_drift`, marks
accepted review stale when affected, excludes affected Lease rows from complete
identity links/source-review readiness, and fingerprints the exact per-Lease
drift state to prevent aggregate count-swap masking. The platform-admin
staff console presents the distinct source-version drift count. This is
separate from unskipped Property source-ID collision, target activity,
historical retained reviews, and cross-run durable claims; those independent
guards remain active. All changes are diagnostics/metadata only, not
customer Lease/occupancy or financial posting.

## 123. Single-version source drift, replay 409 and source repair regression

New fast-gated PostgreSQL regression uses an accepted Yardi Lease source with
a previously verified Unit parent and no staged Property source duplicate.
Staging one different Property source fingerprint makes current Unit and
Lease readiness stale, changes review fingerprint, and blocks accepted replay.
The existing protective rule denies skipping an unanchored mapped source as
a workaround. Simulated exact source metadata correction restores verified
readiness and idempotent replay without changing customer Property/Unit,
Tenant credentials, durable mapping count or customer Lease count. Previous
tests remain enabled with no weakenings or deletions.

**Status:** Sections 121–123 PREPARED only, pending prior 115–117 and
118–120 exact-SHA hosted CI and its own full six-job source verification.
No unofficial Yardi source/API, accounting, ownership, finance, rent,
deposit or customer business write is enabled.


## 124. Lease identity acceptance scans only its dependency source IDs

The explicit Yardi ACCEPT_RELATIONSHIP endpoint now calls the existing
reason-code/duplicate-aware unresolved identity-source query with exactly
its mapped Property, Unit and Tenant source IDs. The query still covers ALL
unskipped versions of those exact source IDs across the same run's uploads.
Unrelated Property, Owner or Vendor collisions cannot force a full-run
identity scan for every Lease acceptance or replay, and unrelated source
IDs can never be treated as missing dependency evidence.

## 125. Preserve off-upload collisions and audited recovery

A different upload's unskipped version of a referenced Unit source remains a
blocking duplicate for initial/replayed Lease identity acceptance, even if
the rest of the original Lease targets are still active and identical. Only
a separately audited reason-coded SKIP with an exact original reviewed
source binding anchor can resolve the second version; neither source
version nor customer entity is automatically merged. Existing customer
Lease/occupancy, payments, tenant credentials and accounting stay unchanged.

## 126. Scoped-query and staged-version PostgreSQL gate

New `test_yardi_lease_accept_source_scope.py` confirms that unrelated
duplicated Vendor source versions do not pollute Lease source dependency
checks, that only the three actual Property/Unit/Tenant keys reach the
existing scoped collision helper, that an additional conflicting Unit upload
blocks accepted replay with HTTP 409, and that audited duplicate SKIP restores
metadata-only replay. It asserts unchanged customer Property/Unit/Tenant and
customer Lease count. The fast Yardi CI gate includes the test with no
existing tests removed, skipped or weakened.

**Status:** Sections 124–126 PREPARED until all six hosted CI jobs verify
the final exact-SHA milestone. Earlier source contracts, Lease/occupancy
commit prohibitions, finance gate and prior safeguards remain unchanged.


## 127. Accepted Lease review is stale when another Lease source version remains

Read-only Yardi aggregate reconciliation now marks a previously accepted
source Lease relationship stale whenever another non-SKIP staged row claims
the exact same provider Lease source ID in the same run. The duplicate Lease
source counter already prevented complete links, but the accepted-review
stale counter had incorrectly stayed zero. The existing explicit duplicate
SKIP path remains audited and required before accepted readiness is restored.

## 128. Accepted Lease review is stale when customer Unit parent has moved

An original Unit may retain its exact historical reviewed source parent even
after its current customer Unit changes to another active Property. The
aggregate's `accepted_relationship_stale` now includes live Unit/Property
parent mismatch, matching the already enforced per-Lease preview blocker
and complete-link/readiness refusal. The accepted review remains in audit
history, not silently deleted or rewritten; no occupancy/Lease record
creation or automatic reparenting is authorized.

## 129. Duplicate/moved Unit stale counter and recovery PostgreSQL gate

New `test_yardi_accepted_lease_stale_count.py` covers an accepted source
Lease, a conflicting second upload with the same source ID, audited
reason-coded SKIP recovery, later active customer Unit reparenting,
exact restoration, per-Lease preview parity, fingerprint invalidation and
preservation of customer Property/Unit/Tenant and Lease records. The fast
Yardi regression gate includes the test. Every earlier test remains
enabled and unchanged.

**Status:** Sections 127–129 PREPARED, NOT VERIFIED; full exact-SHA hosted
CI must pass all six jobs after prerequisite milestones. No customer record
mutation, financial, accounting, deposit, Lease posting, ownership or
undocumented Yardi API operations enabled.


## 130. Batch three competing Lease identity target reviews into one read

First-time and replayed Yardi Lease source identity acceptance formerly
performed three separate historical MATCH_EXISTING customer target claim
SELECTs for Property, Unit and Tenant. The same access and organization guard
now resolves all three explicit resource/target/source conditions using one
scoped `OR` projection, reducing repeated network/database roundtrips.
No historical review decisions, customer records or existing mappings change.

## 131. Preserve unknown historical source ID claim blocking

Each batched resource condition uses SQLAlchemy `is_distinct_from`
rather than `!=` so a retained staff MATCH_EXISTING review with a missing
historical provider source ID remains a competing target claim. A second
Yardi run reviewing the exact same stable source and target is still
noncompeting; different or unknown source claims require explicit review
and return HTTP 409 before an accepted source relationship may be replayed.
All existing authentication, role, source, live target, original Unit parent,
cross-run durable mapping and no-customer-commit checks remain unchanged.

## 132. Query-count and unknown-source replay PostgreSQL regression

New fast-gated `test_yardi_lease_accept_review_claim_batch.py` requires
exactly one combined historical reviewed target claim SQL SELECT for an
initial acceptance, a blocked replay due to a historical NULL-source
Property review from another Yardi run, and a restored same-source replay.
It verifies organization-scoped unchanged customer Property, Unit, Tenant
credential and absence of customer Lease creation. All old tests remain
enabled and unweakened.

**Status:** Sections 130–132 PREPARED pending full exact-SHA six-job hosted
CI on their eventual consolidated product source. No financial/accounting
posting, Lease/occupancy customer mutation, ownership or unofficial API.


### Sections 118–132 exact-SHA CI fixture correction (2026-10-16)

Hosted GitHub Actions `38862212423` failed one new fast-gated SQL-count
regression because a test-only statement matching predicate did not
recognize the generated SQL text. Its other 96 focused Yardi tests passed.
Source logic is unchanged by the correction. The regression still
requires exactly one batched reviewed-target SELECT covering all three
Property/Unit/Tenant customer target columns and still exercises an
unknown historical source-ID refusal and exact same-source recovery.
No existing test removed, disabled, skipped or behavior assertion relaxed.
The Sections 118–132 milestone remains PROVISIONAL until all six hosted
jobs pass at the new exact repair SHA.

### Sections 118–132: SQL assertion repair after hosted CI 38862586342

At exact source `b30cfc702bdf531bec6930fc6d9df4c06bd6b087`, the new fast PostgreSQL test recorded three
SELECTs under an overbroad observer rather than one. The existing acceptance
endpoint's combined Property/Unit/Tenant competing reviewed-target lookup
selects only staged-row ID, while other valid full staged-row ORM reads also
include those target column names. The corrected regression counts ONLY the
ID-only guarded claim SELECT and requires all three resource-specific
`IS DISTINCT FROM` filters, while retaining first/replay query-count
assertions, historical NULL-source collision refusal, source recovery and
customer-data no-mutation checks. Production logic is unchanged. Milestone
remains **PROVISIONAL** until exact-repair-SHA six-job hosted CI succeeds.

### Follow-up SQL observer correction (hosted run 38911403325)

At `845492e2d7ebc0327b4ef26c801ebc4ee97327a7`, a too-strict SQLAlchemy SELECT alias/operator filter
matched zero statements in one new fast-gated test (96 others passed).
The observer is revised to count the id-only reviewed-target lookup whose
WHERE clause includes all three target fields, not unrelated ORM full-row
SELECTs. Original one-query, NULL-source historical collision/recovery and
customer nonmutation checks are unchanged. Product logic unchanged. Verify
the full six-job hosted CI at the exact new commit before claiming success.

### Follow-up Section 131 branch coverage (prepared, not published)

After the exact-SHA Sections 118–132 CI succeeds, extend the fast-gated
PostgreSQL regression beyond the original Property case to both Unit and
Tenant historical `MATCH_EXISTING` reviews with NULL provider source IDs.
Each target must block first/replayed Lease acceptance with 409 until the
historical source identity is corrected to the SAME original source ID;
replay then recovers. Preserve customer Property, Unit, Tenant password and
Lease count. Reuse existing staged CSV source mappings, do not modify
customer business records, and keep Sections 133–135 undefined until their
original specification is recovered. This is further coverage of §131, not
an invented new roadmap section. Prepared commit is DETACHED until its
parent is fully verified; run all six hosted jobs on its final published SHA.

### Additional prepared §131 organization-boundary negative-path regression

A historical Yardi reviewed Property claim in a DIFFERENT organization,
even if corrupted metadata references the current organization's customer
Property ID and the provider source ID is NULL, must not block a valid
same-organization replay. The additional fast-gated PostgreSQL test asserts
this scoping and unchanged customer records, without creating any customer
business relation or altering production code. This remains detached and
unverified until parent exact-SHA CI is green and the candidate is safely
published with expected-HEAD fast-forward.

### 2026-10-16 verified prerequisite and prepared §131 review hardening

Sections 118–132 were fully verified at source `74e7e33e3b331992497dd7a03415ec31225daaff`, hosted
CI `38912065447` SUCCESS all six: PostgreSQL/backend 1342 passed,
21 deselected, frontend, platform-admin, security, authenticated E2E
and staging-config. The historical Property NULL-source claim regression
and strict single combined SQL claim lookup are green. An independently
prepared follow-up increases existing §131 regression coverage for Unit and
Tenant historical NULL-source reviews, same-source replay restoration, and
foreign-organization reviewed-claim isolation. These follow-up tests remain
PROVISIONAL until their own exact published SHA succeeds in hosted CI.
No customer business, Lease, finance or undocumented API write is enabled.
Sections 133–135 have no recovered authoritative specification or source
object in the published branch and are not claimed implemented.

### Prepared §131 provider isolation regression (not yet published)

In addition to historical Yardi Property/Unit/Tenant NULL-source collisions
and foreign-organization isolation, the reviewed-target query must ignore a
retained APPFOLIO reviewed Property with a NULL source ID even within the
same organization. A focused PostgreSQL regression explicitly creates
provider-scoped migration metadata, checks successful YARDI acceptance replay
and preserves customer target and Lease count. No production code change,
unsupported API or customer record write. Candidate detached pending parent
exact-SHA six-job CI and its own future exact-SHA verification.

### Prepared §131 known-different and NULL Unit/Tenant source protection

In the detached fast-gated PostgreSQL regression, a historical YARDI
Unit or Tenant target review with an unknown NULL source AND a known
different source ID must both block accepted Lease replay (409).
Only restoration to the exact original reviewed provider source ID restores
replay, with unchanged customer records. This complements separately
prepared provider-isolation coverage. Not published or verified; no
production code changes or invented §§133–135 contracts.

### Verified §131 prerequisite, next history/isolation regression

Existing §131 historical Unit and Tenant NULL source collision refusal, exact identity recovery and foreign-organization isolation passed all six jobs at `2510bf93b48dca8bbd4dbedee99905a849016b2a` run `38914698146` (backend/PostgreSQL 1344 passed, 21 deselected). This separate next batch adds known-different source refusal and cross-provider APPFOLIO versus YARDI reviewed-claim isolation; scope is only regression, metadata fixtures and documentation. Full six-job exact new SHA CI is required. Source contracts and customer business no-write rules remain unchanged.

### Detached §131 read-only preview and aggregate consistency gate

Extend existing fast PostgreSQL history-claim tests so historical Yardi
NULL-source Unit/Tenant target claims block initial/replayed source acceptance
and produce matching `identity_target_review_collisions`, stale accepted
review, incomplete links and per-row preview reason codes. Exact original
same-source recovery must restore all three surfaces and the run-level
review fingerprint, without customer mutation. Keep distinct-source,
organization/provider isolation and existing tests active. Provisional
detached source only until the previous exact-SHA six-job CI is verified;
no §§133–135 source contract invented.

### Prepared §131 organization/provider readiness parity checks

The existing accepted-Yardi-source replay isolation tests for another
organization's retained Yardi Property target claim and the same
organization's retained AppFolio Property target claim now require matching
read-only run reconciliation and per-Lease preview results. Irrelevant
provider/organization evidence must NOT alter source readiness, accepted
review currency, collision counters or exact private readiness fingerprint,
and must never authorize Lease/occupancy creation. This candidate remains
detached pending exact parent six-job hosted CI and its own future run.

### Detached exact competing-source evidence fingerprint repair

Existing per-Lease aggregate readiness fingerprints a collision boolean,
so two distinct historical Yardi source identities competing for the
SAME customer target can keep identical review-fingerprint values. After
the prerequisite hosted CI verifies its exact source, a scoped source-level
fix includes deterministic, NULL-safe competing (resource,target,source)
detail in each Lease's private fingerprint evidence. This uses the existing
organization/provider-scoped reviewed-claim projection with zero additional
SQL queries. New fast-gated PostgreSQL regression swaps one historical
competing Property source across OLD-1, OLD-2 and NULL; all three must
remain blocked and fingerprint-distinct; exact original P1 identity
restores readiness and the initial fingerprint, with no customer Lease,
accounting or existing target mutation. Prepared and NOT VERIFIED.

### Exact historical source claim fingerprint must also invalidate saved dry run

The prepared read-only Lease fingerprint evidence correction is now
fast-regressed through the actual Yardi dry-run snapshot lifecycle.
After a saved snapshot is recorded for a stale historical OLD-1 claim,
a different historical OLD-2 or NULL competing source must invalidate
`get_yardi_review_dry_run_status().is_current` even if all readiness
counters stay unchanged. Exact source restoration to P1 restores baseline
readiness fingerprint but does not silently bless the OLD-1 snapshot;
a new explicit reviewed dry-run records the current fingerprint. This
covers stable idempotency and source-exact readiness without any customer
Lease, occupancy, balance, GL, payment or identity mutation. DETACHED,
pending prior milestone CI and own future six-job verification.

### Prepared exact historical identity reviewed-claim evidence (all five resources)

Property/Unit/Owner/Vendor/Tenant stale/current row review fingerprint
status previously recorded only a status string. The prepared source-level
change attaches deterministic NULL-safe sorted competing historical reviewed
source IDs for the exact target to the private per-row readiness evidence.
A focused existing Vendor PostgreSQL regression changes one competing
historical Vendor source ID to another without changing mapped/stale counts,
requires a changed fingerprint, then restores the original source/fingerprint
before the existing target-swap checks. No additional SELECT, user-facing
API change, customer business mutation or unsupported provider field. This
is DETACHED pending previous and own exact-SHA six-job verification.

### Verified prior source and next exact-source fingerprint hardening

Exact source `c4bd306c7e055ac991e49115e13c9ffbad5596b7` passed Actions `38945258561`
with all six hosted jobs green; backend/PostgreSQL 1345 passed,
21 deselected. That fully verifies prior §131 Unit/Tenant NULL/different
review source collisions, same-source recovery and org/provider isolation.
The next consolidated provisional batch binds read-only Lease and
five-resource reconciliation private fingerprints to exact competing
historical reviewed source identities and adds focused safe PostgreSQL
regressions for stable recovery and dry-run status. No Yardi API, customer
business, financial, ownership or occupancy posting. Exact new SHA hosted
CI is required before this milestone is VERIFIED. The further original
Unit parent historical durable source identity fingerprint candidate is
detached, and §133–135 specifications remain unavailable.

### Next detached durable-claim fingerprint batch (rebased candidate)

Parent `be8522586a711b074e7d24405bf5e03247011450` publishes the historical reviewed-source exact
fingerprint correction but requires all six hosted CI jobs green.
The follow-on detached original Unit parent durable Property source
candidate from `ce507242` was reconciled onto the new parent's
source state: no production file divergences. It binds specific
conflicting historic durable source and target metadata to the
private review digest using the existing scoped query. Existing
parameterized Unit original-parent regressions cover
ANOTHER-PROPERTY -> YET-ANOTHER-PROPERTY without changed stale
counts, and exact-source restoration. Zero customer record writes,
no new SQL read; no future numbered requirements invented.

### Next detached source-claim regression coverage across reviewed identity types

The fast-gated retained staff-reviewed target collision regression for
Owners, Tenants and Vendors now verifies an exact source-ID swap under
unchanged stale counters still changes the private review fingerprint.
Restoring the historical competing source ID restores the fingerprint.
This complements the independently prepared original Unit parent durable
Property source provenance safeguards. No tested customer business record
is changed by migration code, and no new provider API or accounting
source contract is assumed. Await parent six-job CI and its own
exact-source verification after safe publication.

### Detached original Unit parent historical staff review identity evidence

The original Unit's durable Property binding can be contested not only
by another durable source claim but by a retained staff-reviewed
Property source ID. The per-row private Unit readiness fingerprint now
includes the deterministic, NULL-safe exact historical Property review
source IDs that conflict with its original mapped Property, using the
already-scoped reviewed-claim projection. A parameterized PostgreSQL
regression for reviewed/unreviewed Units swaps PX to PY under unchanged
stale counters and requires a changed fingerprint, then exact recovery
to PX followed by authoritative parent P1. No new database query,
customer mutation or unsupported Yardi API source assumption.
This source remains detached pending prerequisite and its own CI.

### Prepared exact historical durable evidence for unbound staff reviews

An existing Yardi MATCH_EXISTING identity row need not have a current-run
durable mapping yet. Source-exact private fingerprint evidence must still
include the existing scoped historical durable source/target contradictions
for that explicit reviewed resource/customer target. The prepared source
projection unifies (run item or staff-reviewed staged identity) evidence,
with no new SQL, authorization or customer write. New fast-gated PostgreSQL
Vendor review without a durable current item changes a competing historical
source OLD-V-1 -> OLD-V-2 with unchanged stale counts, requiring a distinct
fingerprint, and verifies exact conflict and same-source recovery without
modifying customer Vendor. Detached and provisional until safe publication
and all six hosted CI jobs verify exact source.

### Exact six-job verified reviewed-source fingerprint and next durable-claim batch

Source `be8522586a711b074e7d24405bf5e03247011450` verified by hosted Actions `38947446055`
SUCCESS six jobs including complete backend/PostgreSQL 1346 passed,
21 deselected. Its scoped historical reviewed-source exact fingerprint
corrections and NULL-safe Lease/five-resource readiness, dry-run/status,
replay/preview and org/provider isolation guards are VERIFIED.
Next provisional source keeps historical durable mapping contradictions
and original Unit parent staff/durable reviewed claims source-exact in
the PRIVATE run fingerprint, including a current MATCH_EXISTING row
not yet bound durably. Existing PostgreSQL gate expands source-swap
and exact recovery regressions across staff Vendor/Owner/Tenant and
reviewed/unreviewed Unit. Zero additional SQL, customer business
record mutation, owner allocation or unsupported API/financial posting.
Full new exact-source CI required, no §§133–135 requirements invented.

### Verified historic source-exact fingerprint and unbound review dry-run guard

Source `56bd1e1e70a9e9f9e2c91d98eb75cf042fc7edc9` passed six hosted CI jobs (Actions `38949444168`).
Historical durable source/target identity evidence for current-run durable
bindings and unbound MATCH_EXISTING identity reviews, plus exact original
Unit Property parent staff and durable claims, is VERIFIED at that SHA.
The follow-up strengthens the already fast-gated unbound Vendor regression:
a staff dry-run saved with an OLD-V-1 conflicting durable source must become
stale after OLD-V-2 replaces it, even with unchanged readiness totals.
Exact OLD-V-1 source restoration must restore dry-run currency. No
production SQL, customer business mutation, unsupported Yardi API or
financial posting. Follow-up is PROVISIONAL until new exact-SHA CI passes.


### 2026-10-16 following unbound identity safety regression batch (Owner/Tenant)

The already verified Vendor unbound MATCH_EXISTING historical durable-source
source-swap protection is now extended to unbound existing Owner and Tenant
user reviews. Parameterized PostgreSQL regressions check: (1) exact historical
Yardi competing source ID changes invalidate a saved reviewed dry-run even when
needs_review and matched_existing counters are unchanged; (2) returning to the
exact competing source restores the stored fingerprint's current status;
(3) returning to the reviewed source restores original readiness without
creating a durable current-run mapping; (4) same stable source identity in
another run, same-organization APPFOLIO evidence and foreign-organization YARDI
evidence cannot falsely contest readiness; and (5) genuinely distinct
same-organization YARDI durable claims invalidate the snapshot and recover
when their source is restored. Existing owner/tenant password, identity and
staff review evidence remain unchanged; no customer creation, Lease/occupancy,
owner allocation, GL/financial posting or official Yardi API is enabled.
This regression-only batch is PROVISIONAL pending exact-SHA hosted CI.
Original Sections 133–135 remain unspecified and are not invented.


### Unbound Property exact historic durable source review regression (2026-10-16)

The same source-exact reviewed dry-run and historical durable target-claim
invalidation now has an independently staged, explicitly reviewed but UNBOUND
Property test. Historical competing YARDI Property identity OLD-1 -> OLD-2
keeps stale counters fixed yet expires saved dry-run evidence; OLD-1 restores
that saved fingerprint and exact current P-1 identity restores initial
readiness. Customer Property name/address, staff review, and the absence of a
current-run binding remain unchanged. Test-only addition; provisional until
exact-SHA hosted CI. No unsupported API or customer mutations enabled.


### Follow-up unbound reviewed Owner/Tenant live-role revalidation (2026-10-16)

Parameterized PostgreSQL regression exercises a saved staff reviewed dry-run
for unbound Owner and Tenant identities while the linked customer user's
active flag, authorization role, and soft-delete flag each independently
make the target ineligible. Readiness and exact dry-run currency must become
stale, and restoring each original customer state must restore the exact
review fingerprint without changing staff review or creating a new customer.
These are test fixture mutations, NOT migration endpoint writes. Original
customer password, source fingerprint and no-current-run-binding invariants
are preserved. No tests deleted or weakened; pending exact-SHA hosted CI.


### Unbound Vendor soft-delete dry-run fingerprint regression (2026-10-16)

An additional explicitly reviewed unbound Vendor target regression now checks
that customer-side Vendor soft-deletion invalidates existing staff dry-run
currency without editing historical review or generating a new source mapping.
Restoring that Vendor to active state restores exact private review evidence.
Existing company name and all customer financial/Lease data are preserved.
Regression-only, provisional pending exact-SHA six-job CI.


### Stale Vendor target switch with identical run-level counters (2026-10-16)

Two explicitly reviewed, unbound Yardi Vendor identities can have the same
one-current/one-stale resource totals while the archived customer target
switches from the first Vendor to the second. A focused PostgreSQL
regression now saves a dry-run at the first classification, exchanges
fixture soft-delete states, and requires a distinct exact review fingerprint
and stale status despite unchanged aggregate counters. Restoring the first
archived target restores saved current status; fully restoring both targets
restores baseline readiness. No migration customer-record mutation,
new mapping, identity overwrite, accounting/Lease/occupancy posting or
undocumented Yardi API is introduced. Test-only and provisional until CI.


### Prepared equal-counter Owner/Tenant customer-eligibility swap regression (2026-10-16)

Extends the unbound MATCH_EXISTING Owner/Tenant dry-run revocation safety
gate to TWO independently reviewed customer users of the same resource.
Parameterized active-status, customer role and soft-deletion transitions
swap WHICH target is invalid, keeping aggregate matched_existing and
needs_review exactly equal across both snapshots. The private review
fingerprint must change; restoring the original invalid target restores
the original saved dry-run and restoring both customer users to valid
recovers baseline readiness. Original passwords, staff decisions,
absence of durable current-run mappings and customer nonmutation are
asserted. Test-only and documented, no source contract or external Yardi
API, customer Lease/occupancy/finance or owner allocation enabled.
Prepared detached from the preceding eligibility regression candidate
9666ef2d866dadd1fb679ae557c4daf1f1bd96d0; publish after predecessor
passes exact-SHA hosted CI and live branch HEAD is verified. This child
requires its own all-six-job CI before VERIFIED. §§133–135 remain unspecified.


### Prepared reviewed Property/Unit equal-total target eligibility swap (2026-10-16)

Expands the existing fast-gated Yardi read-only unbound MATCH_EXISTING
source-target readiness tests to two independently reviewed existing
Properties or two existing Units under one durable original Property
parent. An inactive or soft-deleted first customer target makes one
source stale, then the identical status moves to the other reviewed
target with the SAME per-resource aggregate counters. The exact private
review fingerprint and saved dry-run status must change, and must
return to the original fingerprint when the original target is
restored to the same invalid state. Restoring both customer targets
recovers baseline ready review. Original customer names/unit numbers,
parent relationship, staff decisions and absence of newly bound identity
mappings are asserted. Regression only, no changes to production router,
Yardi source contract, Lease/occupancy or financial/ownership posting.
Prepared detached after the equal-total Owner/Tenant candidate; requires
prerequisite exact-SHA green hosted CI and its own green all-six-job CI
when published. Does not invent absent §§133–135 requirements.


### Detached unreviewed durable Owner/Tenant/Vendor equal-total status swap (2026-10-16)

The read-only status of a durably mapped identity uses a distinct
DURABLE_CURRENT/DURABLE_STALE reconciliation path from staff MATCH_EXISTING
reviews. Additional fast-gated PostgreSQL cases seed two original
source-exact unreviewed durable mappings of the same resource and switch
WHICH customer's inactive/incorrect-role/soft-delete status is invalid
while mapped/needs_review counts remain equal. The private reviewed
dry-run fingerprint must change, invalidate saved evidence and restore
exactly for the original invalid target, then return to baseline when
both are valid. Old durable mapping IDs/fingerprints and original
customer values/passwords are preserved. No new API, production write,
schema, Lease/occupancy, owner allocation or finance posting. This
candidate is detached behind the Owner/Tenant and Property/Unit staff
review eligibility swap candidates and must pass its own hosted exact
six-job CI once safely published. Missing §§133–135 are not invented.


### Detached durable Property/Unit equal-total eligibility swap (2026-10-16)

The unreviewed, already-durable identity path is additionally covered
for two Properties and two Units with their verified original Property
parent identity. Inactive/soft-delete status moving from the first to
the second target leaves aggregate mapped/needs_review equal but MUST
expire the exact private reviewed dry-run fingerprint. Restoring the
original invalid target restores the saved snapshot, and restoring
both valid targets restores original ready evidence. Assertions preserve
source-exact durable mappings, unchanged customer names, Unit number
and parent, original staging decisions and no business mutation. Four
parameterized fast-gated PostgreSQL cases only, no router/schema changes,
Yardi official API, Lease/occupancy/owner-allocation/financial writes.
Publish only after all predecessor exact-SHA full CIs are green and
live expected branch HEAD is checked. §§133–135 remain unspecified.


### Detached Unit original Property parent equal-total eligibility swap (2026-10-16)

A further fast-gated read-only regression uses two distinct source-exact
durable Property mappings and two dependent durable Unit mappings. Either
original Property being inactive or soft-deleted makes exactly one
Property and one dependent Unit stale. Exchanging WHICH original parent
is unavailable preserves identical mapped/needs_review counters across
both resources, but must invalidate the private review fingerprint and
saved staff dry-run, then restore exact evidence when the first parent
again becomes unavailable. Both restored parents must recover all four
durable source/target relationships and preserve original customer Unit
parenting and numbers. Two parameterized PostgreSQL cases. No product
router, customer Lease/occupancy, GL, allocations or unofficial Yardi
API changes; requires exact hosted six-job CI on publication after
predecessor verification. §§133–135 remain unspecified.


### Detached out-of-scope customer eligibility isolation (2026-10-16)

The exact customer eligibility fingerprint must only consider targets
actually referenced in the run's reviewed or durable identities.
Three parameterized fast-gated PostgreSQL negatives test that an
unreferenced, same-organization Owner, Tenant or Vendor becoming inactive
or archived leaves the current reviewed target, its source-exact
fingerprint and persisted staff dry-run status EXACTLY unchanged.
Original staff review, customer's password/company name and absence of
a new binding are preserved. This prevents erroneous review expiration
from unrelated customers while keeping fail-closed changes for referenced
targets. Read-only product behavior and test fixture changes only,
no Yardi API, schema, Lease/occupancy or financial/ownership mutation.
The detached child requires predecessor exact-SHA full six-job CI and
its own six-job verification after safe publication; §§133–135 remain
unavailable and are not invented.


### Detached unreferenced Property/Unit target eligibility isolation (2026-10-16)

Four fast-gated PostgreSQL cases complement the existing-target source
review fingerprint safeguards. An unreferenced, same-organization
Property or Unit becoming inactive or soft-deleted must not change
reconciliation aggregate counts, exact saved reviewed dry-run or
fingerprint for an independently reviewed Property or Unit. Original
Unit Property parent mapping remains current. Restoration also preserves
customer fields, original staff source review and absence of newly bound
identity mappings. Tests only, no authorization, Yardi API, Lease or
accounting/customer business write. Publish after green exact-SHA
predecessor and verify its own six CI jobs; no invented §§133–135 scope.


### Detached durable Owner/Tenant/Vendor unrelated eligibility isolation (2026-10-16)

Three fast-gated PostgreSQL cases protect unreviewed exact durable
identity readiness against unrelated same-organization target statuses.
An unreferenced Owner/Tenant becoming inactive or Vendor archived
must leave the original mapped source/target, aggregate readiness,
fingerprint and saved staff review current, including idempotent
dry-run replay. Exact source fingerprint and historical staff action
absence remain unchanged, and customer records are preserved.
Test-only, no customer create/update from migration product routing,
unsupported API, Lease/occupancy, ownership or accounting posting.
Follows the reviewed out-of-scope target negatives. Detached until safe
non-force publication after exact full predecessor CI and requiring
its own all-six-job hosted verification. Do not invent §§133–135.


### Detached durable unrelated Property/Unit eligibility isolation (2026-10-16)

Four additional fast-gated PostgreSQL cases ensure that an unreferenced
Property or Unit's inactive/archival change does not affect a separate
source-exact durable Property or Unit mapping in the same organization.
The original Unit Property parent stays valid; current aggregate
readiness, exact private review fingerprint and saved dry-run replay
remain unchanged. Restoring the unrelated target likewise preserves
the original mapped source ID/fingerprint, customer names/unit numbers
and no staff-review decision. No Yardi product customer mutation, API,
owner allocation, Lease/occupancy or financial posting. Prepared
detached behind previous identity eligibility coverage and awaiting
its own exact six-job hosted CI after safe publication. Original
Sections 133–135 remain unspecified.


### Consolidated reviewed/durable eligibility regression integration batch (2026-10-16)

Nine detached test-only follow-ups after published commit 9666ef2d
are a SINGLE prepared integration milestone, not nine independently
verified source releases. The consolidated source adds 35 parameterized
fast-gated PostgreSQL cases in the existing Yardi identity replay
test file. It verifies exact staff-reviewed and unreviewed durable
eligibility swaps for Properties, Units, Owners, Tenants and Vendors;
original durable Unit Property parent status swaps; and both reviewed
and durable out-of-scope customer status isolation. Exact saved dry
runs expire for changed referenced customer eligibility even when
aggregate readiness is equal, but remain current when unrelated
same-org customers change. Source bindings, decisions, passwords,
original property/unit fields and customer business records are
preserved. No existing test removed, no router behavior, schema, Yardi
API, new customer Lease/occupancy, allocation, deposit or GL/AR/AP write.

The source must NOT be published before exact predecessor
9666ef2d866dadd1fb679ae557c4daf1f1bd96d0 passes all six hosted
jobs in Actions 38963664421, with the sole branch live SHA reconfirmed.
A non-force expected-HEAD fast-forward can then publish the FINAL
consolidated Git descendant directly; its new full six-job CI alone
verifies the entire included source. Intermediate detached Git commits
are not separately published or VERIFIED; this explicitly supersedes
any earlier draft text implying each would require an individual
hosted CI before the final integration. Missing original §§133–135
remain unavailable and must not be invented.


### Cross-target role/soft-delete isolation for reviewed and durable user identities (2026-10-16)

Four additional fast-gated PostgreSQL cases each for independently reviewed
and unreviewed durable Owner/Tenant source identities verify that changing an
UNREFERENCED same-organization user to the opposite authorization role or
soft-deleting that user cannot expire another exact source-target binding's
saved reviewed dry run, source evidence, or mapping. Existing inactive-user
and Vendor-archive assertions are preserved. Recovery restores original
user state, source fingerprint, and current dry-run status. Test fixtures
only; no Yardi router or customer-business mutation, source API, ownership,
Lease/occupancy or financial posting. This follow-up is PROVISIONAL until
its own exact-SHA hosted all-six-job CI passes; Sections 133-135 remain
unavailable and must not be invented.


### Customer-profile-only edits preserve exact Yardi reviewed/durable identity evidence (2026-10-16)

Six additional fast PostgreSQL scenarios verify that updating an already
eligible referenced Owner/Tenant first name or Vendor display name does not
expire a saved source-exact staff-reviewed or unreviewed durable identity
mapping. Identity, role/activity, source row fingerprint, target linkage and
resource readiness remain unchanged; the dry run replays without a new
review. The test restores original fixture names and checks no migration
business mutations. Provisional detached successor pending predecessor
six-job exact CI; no API, Lease/occupancy, ownership or accounting enablement.


### Consolidated exact-SHA publication gate for 14 Yardi identity review regressions (2026-10-16)

The two directly-descended detached, test-only milestones described above
comprise ONE consolidated release candidate rather than two individually
published/verified release milestones. They add eight unrelated Owner/Tenant
role and soft-delete status isolation scenarios and six source-exact,
referenced eligible customer profile/name edit stability scenarios. Before
publication the 916cbdf parent must pass all six jobs of CI 38988402219,
and the live sole branch must match its parent SHA. Advance only by
non-force expected-HEAD fast-forward to the final combined SHA. Require
one full hosted six-job exact final SHA CI before marking VERIFIED;
intermediate detached Git objects are not independently verified.
The earlier detached-notes' separate-parent-CI instructions are
superseded ONLY for these two unpublished related descendants.
All previous tests and customer nonmutation guarantees remain. Missing
numbered §§133–135 and unauthorized APIs/financial/Lease/occupancy
business posting are not enabled.


### Owner/Tenant credential-hash rotation must not expire source identity dry run (2026-10-16)

Four additional fast-gated PostgreSQL cases extend the referenced-identity
profile edit tests to owner/tenant hashed-password rotation for both
staff-reviewed and durable Yardi target bindings. User credential material is
not source identity, must not enter a Yardi review fingerprint, and must not
invalidate a saved dry run or trigger a new migration audit review when
source/target identity and eligibility remain unchanged. Fixture hashes are
restored. All earlier test cases and assertions are retained; no production
credential mutation, API, Lease/occupancy, owner allocation or financial
posting. The successor is detached and PROVISIONAL until exact parent six-job
CI and then its own six-job hosted verification after safe publication.


### Unit parent reassignment swap with equal Yardi readiness totals (2026-10-16)

Two fast-gated PostgreSQL cases cover independently reviewed and durable
Unit source identities whose customer Units have been reassigned to the wrong
active Property. Reassigning which one of two originally mapped Units is
in the wrong parent leaves aggregate mapped/stale counts unchanged but MUST
change the exact saved dry-run fingerprint, then restore it when the original
bad parent is restored. Both customer Units, original parents, source rows,
review decisions and mappings are preserved. Only rolled-back test fixtures
modify Unit.property_id. No customer business operation, unsupported Yardi
API, Lease/occupancy, owner allocation or financial posting is enabled.
This follow-up is detached/unverified until exact-SHA parent and own hosted
six-job CI pass.


### Consolidated credential and Unit-parent regression integration (2026-10-16)

The two newer detached follow-ups are one integration candidate containing
six additional fast-gated PostgreSQL regressions: four user password-hash
rotation snapshots (reviewed and durable Owner/Tenant) and two changes in WHICH
reviewed or durable Unit is reassigned to the wrong valid customer Property
while resource totals remain identical. Only tests and these documents change.
Do not publish until the prior published exact SHA 74bb1a22 passes all six
jobs in CI 38989472466 and sole branch still matches it. Publish the FINAL
descendant by non-force expected-HEAD advance and require full six-job hosted
CI on that final exact SHA. Intermediate detached object commits are ancestry,
not separate verification releases, superseding earlier detached statements
about one CI per unpublished intermediate. Source target identity, user hash,
Unit Property parent restoration, customer nonmutation and all previous tests
remain enforced. Unsupported Yardi transport and §§133-135 remain blocked.


### Unreferenced same-organization Unit reparenting isolation (2026-10-16)

Two new fast-gated PostgreSQL cases confirm an unrelated Unit moving between
two valid Properties in the same customer organization does not stale a
separate exact-source reviewed or durable Unit mapping, existing saved dry
run, source binding or replay. The original unrelated Unit parent is restored
inside the isolated test fixture; no customer business writes by migration,
unsupported APIs, Lease/occupancy, financial posting or ownership allocation.
Detached provisional successor pending exact predecessor and its own hosted CI.


### Consolidated eight-case Yardi source identity/parent review gate (2026-10-16)

The three unpublished related test-only successors after published 74bb1a22
are ONE consolidated milestone requiring a single exact final-SHA six-job
hosted verification. The eight new parameterized PostgreSQL cases cover
Owner/Tenant credential-hash rotation, exact reassigned Unit source parent
swap, and unreferenced same-org Unit reparenting isolation across reviewed
and durable source bindings. Unpublished intermediate Git objects are
ancestry only, and earlier notes asking for individually verified CI on
those objects are superseded. The prior published 74bb1a22 must first
pass all six jobs in GitHub Actions 38989472466, then branch HEAD must
still match, before non-force expected-HEAD fast-forward directly to
the final combined descendant. The final exact published SHA must pass
its own six-job hosted CI before VERIFIED; no customer-business mutation
or unsupported Yardi features are authorized.


### Unavailable Lease customer still preserves exact staff source dispute (2026-10-16)

A read-only reconciliation fix retains an unavailable linked Property, Unit,
or Tenant mapping's original durable target ID for batched, organization- and
provider-scoped historical staff-claim evidence. Previously a disabled or
missing customer target could hide a changed competing historical provider
source ID; stale aggregate Lease readiness stayed identical and could reuse
an outdated saved review fingerprint. The newly added PostgreSQL regression
disables the already-linked Tenant, swaps historical retained same-org Yardi
review source IDs including NULL, asserts distinct exact dry-run fingerprints
and unchanged blocked readiness, then restores the original source and
customer status. No additional SQL fetch or actual Lease/occupancy/customer
mutation is introduced. Detached/provisional until exact preceding and own
hosted all-six-job CI, no invented source API or §§133-135 scope.


### Nine-case consolidated reviewed/durable and stale Lease safety release (2026-10-16)

Nine PostgreSQL cases are consolidated into ONE final exact-SHA integration
candidate after published 74bb1a22. Eight are reviewed/durable eligibility,
credential and Unit Property-parent positive/negative scope regressions;
the ninth covers a linked Lease Tenant becoming unavailable while the exact
historical reviewed source claim changes even though blocked readiness remains
identical. A corresponding read-only router correction retains exact
organization-scoped original durable link targets for the historical claim
projection, without extra SQL or customer business mutations. Intermediate
detached objects are not individually published or verified; this supersedes
previous intermediate CI wording. Require ALL SIX jobs successful in
38989472466 for parent 74bb1a22 and matching live branch HEAD, then
a non-force expected-HEAD fast-forward to the final descendant and its own
full six-job hosted exact-SHA CI before VERIFIED. Original unprovided
§§133-135, official API contracts, Lease/occupancy, owner allocation and
financial posting are not enabled.


### All three unavailable Lease targets retain exact historical review-source fingerprints (2026-10-16)

The existing inactive Tenant historical reviewed-claim fingerprint test is
expanded to parameterize three separate supported identity resources:
Property, Unit and Tenant. For each, an already unavailable current customer
target must still retain source-exact historical provider review conflicts,
distinguish two different old source IDs and NULL even with identical aggregate
blocked readiness, keep dry-run stale when the source changes, and recover on
identical original source restoration. The test verifies accepted Lease replay
only after original source and customer eligibility both return. Same
read-only reconciliation correction, no new query, no customer Lease/occupancy
or financial mutation, no undocumented Yardi API and no invented §§133–135.
Two additional PostgreSQL parameter cases; original Tenant assertions retained.


### Eleven-case consolidated Yardi source review and unavailable Lease fingerprint gate (2026-10-16)

The nine earlier detached regression cases and two new unavailable
Property/Unit historical review-claim variants plus the scoped read-only
reconciliation correction form one consolidated integration milestone
after the exact published parent 74bb1a22. Parameterization of the
previous Tenant case preserves all existing assertions. The source includes
a corrected newline fixture and independently checks Property, Unit and
Tenant linked targets when inactive. Unpublished intermediate commits are
only ancestry, not individually verified release milestones. The final
candidate must wait for all six green GitHub Actions jobs of 38989472466
at exact 74bb1a22, a fresh sole-branch SHA check and non-force
expected-HEAD fast-forward; final exact SHA must then pass full six-job
hosted CI before VERIFIED. No customer Lease/occupancy/financial
mutation, source API expansion or invented Yardi §§133-135.


### Unavailable linked Tenant provider/organization isolation (2026-10-16)

Two additional PostgreSQL variants guard the corrected historical Lease
identity evidence against same-customer cross-provider AppFolio reviews and
foreign-organization Yardi reviews even when the linked Tenant is inactive.
Both retained historical NULL source-ID reviews deliberately reference the
same target ID and must remain invisible to scoped Yardi reconciliation,
preserve the exact saved dry-run, and permit replay when the real customer
identity recovers. Source is no mutation of customer business records, with
all fixtures restored. No unsupported APIs, Lease/occupancy or finance writes.


### Final 13-case consolidated source-exact Yardi review safety milestone (2026-10-16)

All related unpublished follow-ups after exact published source 74bb1a22
are consolidated into ONE final descendant, adding thirteen PostgreSQL
parameter scenarios including credential rotation, referenced/unreferenced
Unit parent reassignment and unavailable Property/Unit/Tenant historical
Lease source-claim details. The original Tenant exact-source regression
is preserved and extended. Two negative tests ensure an inactive Tenant
does not leak retained APPFOLIO or foreign-organization YARDI review claims.
A read-only reconciliation correction preserves original same-run linked
targets when customer eligibility changes, without extra database queries
or customer business writes. Intermediate detached objects are ancestry
and do not require individual hosted CI. Do not publish until all six
CI jobs pass at parent 74bb1a22 in 38989472466, and sole branch matches
that exact SHA. Publish FINAL descendant only with non-force
expected-HEAD update, then verify exact final SHA by six hosted jobs.
Previous assertions, source transport boundaries, customer data and
unknown §§133-135 restrictions remain preserved.


### Same-organization unreferenced historical Tenant claim stays outside unavailable Lease snapshot (2026-10-16)

A new fast-gated PostgreSQL case creates a retained NULL-source Yardi Tenant
staff review in a different run in the SAME organization, but linked to an
unreferenced customer user. Its existence must not affect an already-inactive
current Lease Tenant's scoped historical claim projection, stale blocker
counts, exact saved dry-run or replay. Both customers retain original
password hashes and the accepted Lease source decision remains unchanged.
The test restores the linked Tenant's active state and verifies full
fingerprint recovery. No Yardi customer business writes or new source/API.


### Inactive Lease target preview parity with exact historical claims (2026-10-16)

The read-only paginated Yardi Lease preview now checks retained staff
source disputes using the original valid-entity linked Property, Unit
or Tenant ID even when that target is inactive. The live-unavailable
blocker remains, and org/provider-scoped historical source evidence
is reused without additional SQL. The three inactive target PostgreSQL
regressions now also assert preview collision, resolution of the source
collision while inactive, and final full recovery. No customer business
mutation, Lease/occupancy or financial posting.


### Consolidated unrelated history and unavailable Lease preview parity follow-up (2026-10-16)

The one new PostgreSQL unreferenced same-organization historical Tenant
claim isolation test and the read-only Lease preview/reconciliation collision
parity correction, with reinforced inactive Property/Unit/Tenant variants,
form ONE coherent unpublished follow-up integration batch after exact
published 0a0c3b. Intermediate detached objects are ancestry only, not
independently verified releases. Published ancestor must complete all SIX
GitHub Actions 38990736808 jobs SUCCESS at exact SHA, and branch HEAD must
still match, before non-force expected-HEAD publication of the FINAL
consolidated descendant. It must pass its own all-six-job hosted CI. The
corrected preview reuses the existing organization/provider-scoped historical
claim projection without new SQL, and retains the separate inactive-target
blockers. All customer data and existing tests are preserved. No new Yardi
API, Lease/occupancy, ownership, finance or invented §§133–135.


### Unavailable Lease preview non-collision parity for unrelated claims (2026-10-16)

Existing cross-provider, cross-organization and same-organization
unreferenced-target historical Tenant source regressions now explicitly
assert paginated Lease preview remains free of false target-review
collision blockers even though the actual linked Tenant is inactive.
Existing inactive-identity blockers must remain, and full valid customer
restoration must recover an empty-blocker preview and original exact
saved source evidence. Three existing test variants strengthened,
none removed; read-only Yardi correction unchanged.


### Consolidated unavailable Lease source-review and preview parity gate (2026-10-16)

The three related unpublished descendants after published 0a0c3b
constitute ONE integration milestone, containing an unrelated same-org
Tenant historical review-source isolation test, a read-only Lease
preview correction for original inactive Property/Unit/Tenant linked
identity collisions, and additional preview assertions in six existing
positive/negative variants. Prior tests remain intact. Historical claim
projection uses existing batched provider/organization filters, original
same-run durable mapping and no added SQL query. Intermediate detached
Git commits are not independently verified releases; this supersedes
lower provisional notes. Require all SIX 38990736808 jobs successful
at exact published parent 0a0c3b, plus fresh same branch-head check,
before non-force expected-HEAD fast-forward of final consolidated SHA.
Final exact SHA must pass its own complete six-job hosted CI. No Yardi
customer business writes, undocumented API, missing §133–135 scope,
Lease/occupancy, owner allocation or financial posting.


### Inactive, soft-deleted and role-invalid Lease historical staff claim parity (2026-10-16)

The previously added three-resource invalid Lease target historical reviewed
source test now runs seven targeted PostgreSQL parameter scenarios: inactive
and soft-deleted Property, Unit and Tenant plus wrong-role Tenant. In every
case identical aggregate blocked readiness must still preserve exact source
claim changes, saved dry-run expiry, historical provider-source NULL
evidence, and paginated Lease preview collisions. Exact provider source and
customer eligibility restoration returns original staff review and no
customer-business mutation. Four additional cases, no old cases removed.


### One consolidated unavailable Lease preview safety batch (2026-10-16)

The four related unpublished descendants after current published 0a0c3b
are one prepared review-only integration release candidate. They add one
unreferenced same-organization Tenant retained historical source isolation
test; a scoped read-only paginated Lease preview correction for historical
staff-source collisions on unavailable linked original Property/Unit/Tenant
targets; positive and negative preview parity assertions; and four extra
status variants for soft-deleted Property/Unit/Tenant and wrong-role Tenant.
All seven valid/inactive/deleted/role-ineligible fixture cases assert exact
saved dry-run invalidation and recovery without customer business writes.
No original assertion removed/weakened. Intermediate detached commit objects
are ancestry, not independently verified. Publish only after six green
CI jobs on exact parent 0a0c3b in 38990736808, matching live branch
HEAD and non-force expected-SHA fast-forward to the FINAL candidate.
Require own exact-SHA full six-job hosted CI, no unsupported provider
source contracts or Yardi §§133–135 invention, finance, ownership or
Lease/occupancy posting.


### Foreign provider/organization retained source-swap isolation (2026-10-16)

Extend an existing fast PostgreSQL Lease review regression to exercise
four historical source variants each for a foreign organization's YARDI
review and another provider's same-organization APPFOLIO review, targeting
a currently inactive YARDI-linked Tenant. Neither historical change should
affect the exact stored source-review dry-run fingerprint or create a Yardi
collision. Customer business endpoints remain read-only. Detached pending
exact parent `f2efb06e` all-six CI and own six-job hosted CI following
sole-branch non-force expected-HEAD publication. No unsupported API,
customer Lease/occupancy, allocations or accounting writes.


### Unavailable Lease Unit: unrelated Property/Unit historical claim isolation (2026-10-16)

Two parameterized fast PostgreSQL cases extend the exact-source negative
scope to same-organization unreferenced Property and Unit targets while a
different mapped Lease Unit is inactive. Historical staff claims against
those unrelated customer targets switch between NULL, two distinct foreign
source IDs and the Lease's own textual source ID, without changing the
current run's source-exact review fingerprint, blocked readiness, saved
dry-run replay or page-level blockers. Restoring the linked Unit exactly
recovers the original accepted read-only relationship. Test fixtures
restore customer values. No production Yardi route, customer mutation,
unofficial API, Lease creation, accounting or owner allocations.
Detached and provisional pending published parent CI, then own
full six-job hosted exact-SHA CI after non-force expected-HEAD advance.


### Consolidated unavailable Lease claim isolation gate (2026-10-16)

One final prepared test-only integration milestone covers historical source
swaps from foreign-org YARDI and same-org APPFOLIO source reviews,
and two new parametric same-org YARDI unreferenced Property/Unit targets.
Different NULL/text source IDs must not change the exact saved dry-run
of an already blocked Lease, nor remove its true inactive blocker;
restoring the linked customer status must restore source review readiness.
No product routing, schema, customer Lease, financial or ownership writes.
Intermediate detached commits are ancestry only. Exact parent source
f2efb06e must succeed in ALL SIX hosted jobs of CI 38993664402
and sole branch HEAD must still match before the FINAL consolidated
commit is non-force expected-SHA published. Its exact new SHA must
pass its own six-job GitHub Actions before VERIFIED. All existing tests
remain. Do not invent unavailable §§133–135 scope.


### Page-level cross-scope parity on each historical source variant (2026-10-16)

The same-organizational-unreferenced Tenant and provider/foreign-organization
Tenant historical source-swap regressions now verify the paginated Lease
preview on EACH NULL, foreign, and equal-text retained source variant, not
merely at the final variant. The real inactive Tenant blocker remains,
and no TARGET_REVIEW_COLLISION leaks from those out-of-scope claims.
Read-only fixture tests only. No business writes, new source API,
Lease/occupancy, ownership or financial posting. Detached and
provisional until parent exact six-job CI and own hosted verification.


### Consolidated source-exact unavailable Lease review isolation gate (2026-10-16)

This final prepared test-only batch contains four related unpublished
descendant object commits after exact published f2efb06e, including the
two new parametric same-organization unreferenced Property/Unit historical
target cases and per-source page blocker checks added to retained foreign
YARDI, AppFolio and unrelated Tenant review negatives. It verifies that
unavailable customer targets keep their genuine blocker but do not
import unrelated or foreign historical provider source claims, and that
saved dry runs remain current through all four source variants. No
production customer mutation or unsupported source/financial/Lease write.

Only publish the FINAL consolidated descendant when CI 38993664402
for predecessor f2efb06e finishes all six successful jobs, and live
authorized sole branch HEAD still equals that SHA. Use non-force
expected-HEAD fast-forward and require six-job exact hosted CI on the
new final SHA before VERIFIED. Intermediate unpublished Git commits
are ancestry, not independently verified source. All prior regressions
are preserved; original §§133–135 remain unsupported.


### Scope clarification for unrelated historical source-negative tests (2026-10-16)

The new same-organization unreferenced Property/Unit historical source
negative test varies only NULL and three genuinely different historical
IDs. It does NOT claim same YARDI source ID may safely map to different
targets in different runs: that is independently collision-sensitive and
must not be weakened or implicitly permitted by unrelated-target
isolation tests. Older notes suggesting equal source text for this
specific new Property/Unit pair are superseded by this explicit
collision-safety distinction. Existing foreign provider/organization
scope coverage remains. This is test-only; no product mutation.


### Exact accepted Lease snapshot stays current for ordinary Tenant profile edits (2026-10-16)

Three PostgreSQL parameter cases verify that first name, last name, and
password-hash updates on an otherwise eligible mapped Tenant do not
invalidate a Yardi accepted Lease relationship's saved review fingerprint,
read-only paginated preview, or idempotent dry-run/acceptance replay.
Only test fixtures change customer fields and restore them. The Yardi
migration itself never updates customer credentials or business records.
Existing source identity, mapped Unit/Property/Tenant, Lease count and
all prior assertions are preserved. New source is provisional until
exact hosted six-job CI. Unsupported API, Lease/occupancy creation,
owner allocations, GL/AR/AP and unprovided §§133–135 remain blocked.


### Profile-only changes cannot clear genuine historical Tenant source disputes (2026-10-16)

Two additional PostgreSQL cases cover an accepted Yardi Lease whose
original linked Tenant is historically contested by a different
same-organization YARDI staff-reviewed source in another run.
Changing that Tenant's first name or password hash must preserve the
exact contested source fingerprint, stale accepted relationship,
paginated review-collision blocker, and 409 refusal to reaccept.
Restoring the original exact historic source ID recovers the baseline
without creating customer Leases or changing business records through
Yardi endpoints. No previous assertion or security gate is relaxed.
Prepared detached follow-up; needs exact predecessor six-job hosted CI
and its own all-six job verification after non-force expected-HEAD publish.


### Benign Tenant edits cannot mask true historical Yardi source swaps (2026-10-16)

Three related fast PostgreSQL cases complement the valid-profile Lease
regression. A previously accepted Lease already blocked by an exact
competing same-org Yardi Tenant staff-reviewed source must remain
blocked when the customer's first name, last name or password hash
changes. During the profile edit, changing WHICH old Yardi source ID
contests the same Tenant must invalidate the saved exact dry-run even
though all aggregate stale counters are unchanged, and restoring that
same contested source must restore the stored fingerprint. Only
restoring the original noncompeting provider source ID recovers the
Lease relationship. Test fixture customer values are restored and no
migration API, new Lease, ownership or financial posting is enabled.
This 3-case successor is detached until its parent exact hosted CI is
green and then requires its own complete six-job CI after publication.


### NULL-safe historic Lease Tenant source review under profile changes (2026-10-16)

The three benign-profile/real-source-swap cases above now execute with
both a known different historical Yardi Tenant source ID and a retained
NULL source ID. Six PostgreSQL combinations require a genuine same-org
staff-review collision to remain visible through changes to an eligible
Tenant's first/last name or password hash, and a different historical
source to expire the exact saved dry-run even when stale totals are equal.
Restoring the original NULL or known competing source restores the blocked
snapshot, and restoring the true same-source identity recovers legitimate
Lease readiness. This is a detached, test-only follow-up: no migration
customer writes, new Lease, provider API or accounting/owner allocation.
Prior cases are retained and expanded, pending exact six-job verification.


### Audit idempotency and credential redaction on exact Lease profile review (2026-10-16)

The three valid, six contested Tenant profile source-exact PostgreSQL cases
also verify that the initial reviewed dry run creates exactly one
append-only audit record and that later idempotent replay after a harmless
name/password-hash change adds no duplicate review audit entry. No
changed display name or rotated credential hash is disclosed in the
saved audit value. A true changed historic claim still expires the
fingerprint and remains blocked while restored source state recovers it.
This is test-only; production/customer migrations, Lease occupancy,
owner allocations, GL/AR/AP posting and undocumented APIs remain blocked.
The final descendant requires exact prior and own hosted all-six CI.


### Original disputed source restoration does not duplicate Yardi review audit (2026-10-16)

The NULL-safe historical Tenant source-swap regression also replays the
saved dry-run after exact restoration of its original already-contested
provider source identity, and verifies that this idempotent recovery does
not emit another `yardi_review_dry_run` audit row. Changed competing
historical source identity must still expire the saved snapshot before
restoration. No Yardi product or customer mutation, no migration
Lease/occupancy or financial posting. Detached and provisional until
verified hosted CI at the exact predecessor and successor commits.


### Unlinked Owner/Vendor eligibility must not expire a Yardi Lease review (2026-10-16)

Two additional PostgreSQL cases check that an unreferenced same-organization
Owner becoming inactive or Vendor being archived cannot expire an accepted
Lease's source-exact reviewed Property/Unit/Tenant snapshot, page preview,
or idempotent review/acceptance replay. Original customer fixture states
are restored and unrelated password/company names remain intact, while
no new Lease, migration binding, or duplicate dry-run audit is created.
This is source-dependency isolation only; no migration endpoints write
customer business records or enable unsupported Yardi API, Lease/occupancy
creation, owner allocation or financial posting. Detached until hosted
six-job verification on the parent and final published descendant.


### Consolidated review/audit source-exact isolation follow-up (2026-10-16)

Eight new fast-gated parameterized regressions after the published
three-case accepted Lease customer Tenant profile milestone protect:
six historically contested provider source claims (including NULL)
across valid Tenant first-name, last-name and credential-hash edits,
and two out-of-scope Owner/Vendor status changes on unrelated same-org
customers. Exact saved dry runs expire only for actual source-claim
changes, recover with exact restoration, replay without extra audit rows
and do not expose changed Tenant name or password hashes in audit values.
Tenant/Owner/Vendor test fixture data is restored; source rows, customer
Leases and durable mappings are unchanged by migration routes.
The associated unpublished intermediate Git commits are integrated
as ONE final descendant of published 27db379b, not separately
published/verified. Await ALL SIX jobs SUCCESS in CI 38996279387,
live sole-branch exact-parent check, then non-force expected-HEAD
publication. Require own all-six hosted exact-SHA CI.
No unofficial Yardi API, Lease/occupancy creation, ownership allocations,
financial posting or unavailable §§133–135 introduced.


### Native PostgreSQL NULL-safe historical Tenant review regression (2026-10-16)

A separate PostgreSQL-backed test, not just an isolated SQLite fixture,
checks the Yardi accepted Lease source review against a retained historical
same-org YARDI Tenant staff claim whose source_id is SQL NULL. PostgreSQL
`IS DISTINCT FROM` must recognize that claim, block reacceptance with 409,
show a paginated review-collision blocker and expire the saved dry-run;
restoring the exact original source ID must recover readiness. The test
uses an explicitly configured TEST_DATABASE_URL and external transaction
plus SAVEPOINTs to roll back fixture data. Local SQLite-only environments
skip this PG-specific test. No production customer write or undocumented
API/Lease creation/accounting feature is enabled. Requires exact hosted
six-job CI and test confirmation, provisional until verified.
