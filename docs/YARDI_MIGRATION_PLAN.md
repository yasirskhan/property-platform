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
nor assume undocumented Yardi API behavior. PROVISIONAL pending all six hosted
CI jobs on the exact product SHA.
