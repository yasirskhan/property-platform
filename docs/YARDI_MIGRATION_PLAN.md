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
| Units | PARTIAL | Explicit mapped staging, required source Property ID and parent-mapping warning. No reviewed target Unit binding or customer Unit creation. Next independently actionable batch: read-only Unit target review and relationship validation without mutation. |
| Owners / ownership | PARTIAL | Owner identity staging only; no ownership relationship or login creation. Source ownership relationship contract not verified. |
| Vendors | PARTIAL | Vendor identity staging only; no customer vendor or payment/GL account creation. |
| Residents / tenants | PARTIAL | Resident identity staging only; no login, lease, or occupancy creation. |
| Leases / occupancy | PARTIAL | Stable source identity and Property/Unit/Tenant source references staged with missing-parent warnings. No lease, liability, rent, deposit or occupancy mutation. |
| GL accounts | BLOCKED BY SOURCE CONTRACT | Verified Yardi account schema and target accounting mapping absent. |
| Open receivables / lease charges | BLOCKED BY SOURCE CONTRACT | Authoritative charge grain, direction, periods, balances and reconciliation absent. |
| Open payables / bills | BLOCKED BY SOURCE CONTRACT | Authoritative payable, settlement and target posting contract absent. |
| Bank accounts | BLOCKED BY SOURCE CONTRACT | Account identity and reconciliation contract absent. |
| Current-year budgets | BLOCKED BY SOURCE CONTRACT | Period, account, amount semantics and target reconciliation absent. |
| Outstanding checks | BLOCKED BY SOURCE CONTRACT | Cleared state, bank movement and settlement semantics absent. |
| Trial balance / historical GL | BLOCKED BY SOURCE CONTRACT | Debit/credit direction, opening balances and period semantics absent. |
| Official Yardi API adapter | BLOCKED BY SOURCE CONTRACT | No verified customer/partner interface, credentials or endpoint schema. Export/ETL remains the supported transport. |

**Next product batch:** Unit source-to-existing-target review/reconciliation, using the same provider-labelled metadata and explicit-review controls. First inspect actual Unit model ownership and existing AppFolio/Buildium patterns; do not create Unit records, auto-link occupancy, or enable controlled customer mutation. Property replay micro-regressions are not the default next workstream.

**Completion interpretation:** Staging-only support is not equivalent to a completed resource import. Phase 4.15 remains IN PROGRESS until independently supportable resources are reconciled and verified, with source-contract blockers recorded explicitly.
