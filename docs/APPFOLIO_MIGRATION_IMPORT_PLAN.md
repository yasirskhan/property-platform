# APPFOLIO MIGRATION IMPORT PLAN

Status: **AUTHORIZED — PHASE 4.13 ACTIVE DIRECTION**

Owner decision: **CSV/XLSX exports are the primary AppFolio migration path.**
A live AppFolio API adapter is optional future transport/testing and must not
block the supported export/import migration workflow.

This plan extends the verified Phase 4.13 migration-run, dry-run, exact-
fingerprint commit, source-to-target mapping, replay/idempotency and recovery
architecture. Do not build a parallel migration system.

Related reference:
- `docs/APPFOLIO_API_RESEARCH.md` — API research for later testing only.
- `docs/PLAN_GAPS.md` — Phase 4.13 roadmap.
- `AI_HANDOFF.md` — current verified checkpoint and exact next batch.

## 1. Product objective

A customer leaving AppFolio should be able to export supported reports/data to
CSV or XLSX, upload them to this platform, review what can and cannot be safely
mapped, correct staging decisions, dry-run the migration, reconcile critical
totals, and only then commit approved records.

Primary flow:

`AppFolio CSV/XLSX -> upload -> detect -> map -> stage -> validate -> review ->
reconcile -> dry run -> controlled commit -> durable source mapping`

The upload itself must never mutate customer business records.

## 2. Safety model

Every staged row/resource should resolve to an explicit migration disposition:

- `NEW`
- `POSSIBLE_MATCH`
- `ALREADY_MAPPED`
- `INVALID`
- `SKIP`
- `REVIEW`

Never overwrite an existing Property, Unit, Owner, Tenant, Vendor, Lease,
GL Account, transaction, balance, Work Order, attachment or other customer
record merely because imported data looks similar.

Possible matches require an explicit safe resolution before commit.

Missing business data must not be invented. If required information is absent,
mark the row/file blocked or incomplete and explain what is missing.

Optional fields may remain blank.

Only deterministic normalization is automatic. Examples:
- `Ohio -> OH`
- known column aliases such as `Zip`, `ZipCode`, `PostalCode`

Ambiguous interpretation goes to review.

## 3. Shared file-ingestion foundation — first active batch

Build the reusable Phase 4.13 ingestion/staging foundation before adding more
business-resource committers.

Required capabilities:

1. CSV upload.
2. XLSX upload.
3. Bounded file size, row count and workbook/sheet count.
4. File/report type detection.
5. Header normalization.
6. Known-column aliases.
7. Explicit column mapping when automatic mapping is uncertain.
8. Staging only; upload/parser execution creates no customer business records.
9. Validation summary:
   - valid
   - warnings
   - invalid
   - duplicates
   - possible existing matches
   - missing required columns
10. Preserve stable AppFolio source IDs when supplied.
11. Deterministic normalized-source fingerprint.
12. Replay/re-upload idempotency.
13. Organization isolation fails closed.
14. Audit meaningful migration actions without storing secrets.
15. Spreadsheet formulas/macros or unsupported active content must never execute.
16. Do not store API keys, AppFolio Client Secrets, tokens or browser cookies.

Prefer parsing XLSX as data only. Do not evaluate formulas or macros. Treat
formula cells conservatively unless a verified, explicit value-only policy is
implemented.

## 4. Report/file coverage

The migration framework should eventually recognize authoritative AppFolio
exports such as:

- Property Directory
- Unit Directory
- Tenant Directory
- Owner Directory
- Vendor Directory
- Rent Roll / occupancy data
- Chart of Accounts / GL Accounts
- General Ledger
- Bills / Payables
- Charges / Receivables
- Security Deposit reports
- Work Orders
- supported document/attachment exports where source structure is verified

Do not implement every resource in one batch.

Preferred dependency order:

`Properties -> Units -> Owners/Vendors -> Tenants -> Leases/Occupancy ->
GL Accounts -> Accounting history/balances -> Maintenance ->
Attachments/Documents`

Resource mappings must be based on verified source schemas, not invented from
our target models.

## 4.13 Lease / occupancy staging contract

The first Lease/occupancy batch uses an explicit `LEASE_OCCUPANCY` resource
selection. It is intentionally **not auto-detected as Rent Roll**.

Reason:

- the verified Tenant Directory contract supplies stable Tenant, Unit and
  Property source IDs plus Move-in, Move-out, Lease From and Lease To;
- AppFolio Rent Roll references commonly include Unit, Tenant, Status, Rent,
  Deposit, Lease Start and Lease End, but stable relationship IDs are not
  guaranteed by the public report descriptions;
- names, addresses, unit labels and dates therefore must never substitute for
  durable source IDs.

Rent, Deposit and Status may be preserved as supplementary source evidence when
present or explicitly mapped. They are not proof of rent liability, deposit
receipt, occupancy, receivable balances or GL history.

This first Lease/occupancy batch is staging/reconciliation only. It creates no
Lease, RentInvoice, Payment, Charge, Receipt or GL record. A later controlled
commit requires its own independently verified source and reconciliation
contract.

### Lease / occupancy staged reconciliation

A staged `LEASE_OCCUPANCY` row may be explicitly marked
`ACCEPT_RELATIONSHIP` only after the current durable TENANTS, PROPERTIES and
UNITS source mappings are revalidated to active same-organization targets and
the mapped Unit still belongs to the mapped Property. The accepted review state
snapshots those three target IDs into the existing typed staged-row resolution
fields so the shared staged-review fingerprint binds the reviewed relationship.

Rows with missing or unresolved durable relationship identity cannot be
accepted; they may remain unresolved or be explicitly `SKIP`ped. INVALID rows
remain non-resolvable. Acceptance is review metadata for a later independently
verified controlled-commit contract only: it does not create or update Lease,
RentInvoice, Payment, Charge, Receipt, GL, occupancy or security-deposit records.

## 4.13 GL Accounts staging contract

The first GL Accounts batch uses the shared `GL_ACCOUNTS` resource and the
existing CSV/XLSX ingestion/staging architecture.

Source-schema verification is intentionally narrower than the target
`GLAccount` model. Current AppFolio Stack documentation for General Ledger
Accounts publishes these source fields:

- `Number`
- `Name`
- `Type`
- `FundAccount`
- `IsCorporateAccount`
- `OffsetAccountId`
- `ParentGlAccountId`
- `PropertyIds`
- `LastUpdatedAt`

A Chart of Accounts export may also expose a stable GL Account ID. Preserve a
supplied GL Account ID, but never synthesize one from account name, account
number, row order or a row fingerprint.

Safety boundaries for this first GL Accounts batch:

1. Automatic report detection requires source Number, Name and Type.
2. Account Number/code, Name and AppFolio Type are preserved exactly as source
   evidence after deterministic cell cleanup.
3. Fund/corporate/parent/offset/property fields remain source-only metadata.
4. AppFolio Type/FundAccount values are **not** translated into target
   `GLAccount.account_type`, key-account roles or posting behavior.
5. Missing stable GL Account ID remains REVIEW; account number/code is preserved
   but is not silently promoted into durable source identity.
6. Duplicate supplied GL Account IDs are invalid.
7. Upload/replay remains fingerprint-idempotent.
8. This batch creates or updates **zero** `GLAccount`,
   `AccountingKeyAccount`, journal entry, GL transaction or accounting-balance
   records.
9. GL Account reconciliation and controlled commit require a separate verified
   batch before any accounting-history migration may begin.

## 4.13 GL Account reconciliation + controlled existing-account mapping

After GL Account staging is verified, operators may explicitly reconcile a
stable AppFolio GL Account ID to an existing active same-organization target
GLAccount.

This reconciliation/commit contract is intentionally mapping-only:

1. `MATCH_EXISTING` requires a supplied stable source GL Account ID and a
   reviewed existing target GLAccount; source account number/name are never
   promoted into durable identity.
2. `SKIP` excludes the staged row. Missing-source-ID rows may only be skipped.
3. Target GLAccount number, name, account_type, hierarchy, offsets and posting
   flags remain untouched.
4. AppFolio Type/FundAccount/corporate/parent/offset/property fields remain
   source evidence and are not translated into target accounting semantics.
5. Dry run revalidates active same-organization targets and binds the shared
   staged-review fingerprint.
6. Controlled commit persists only a replay-safe
   `PlatformMigrationItem(resource="GL_ACCOUNTS", target_entity="GL_ACCOUNT")`
   source-to-target mapping.
7. Repeating the identical commit does not duplicate mappings or mutate the
   target account.
8. Any changed review resolution invalidates the prior dry-run fingerprint.
9. This step creates or updates zero GLAccount, AccountingKeyAccount, journal
   entry, GL transaction, balance or accounting-history records.

Only after this mapping contract is independently verified may Phase 4.13 begin
General Ledger/history source ingestion and accounting reconciliation.

## 4.13 General Ledger/history ingestion + staging

The first accounting-history batch uses the shared `GENERAL_LEDGER` resource
and existing CSV/XLSX upload/detection/mapping/staging architecture.

The source contract is limited to the currently published AppFolio General
Ledger Details attributes:

- `Credit`
- `Date`
- `Debit`
- `Description`
- `GlAccountId`
- `LineItemId`
- `PropertyId`
- `Reference`
- `Remarks`
- `TransactionId`
- `TransactionType`
- `UnitId`

Safety boundaries for this staging batch:

1. `GlAccountId`, `Date`, `Debit` and `Credit` are required source fields
   for automatic General Ledger detection.
2. `LineItemId` is preserved as durable row identity when supplied. It is never
   synthesized from transaction ID, date, description, reference, amounts or row
   fingerprint.
3. Duplicate supplied `LineItemId` values in one staged upload are invalid.
4. A source GL Account relationship is considered resolved only through the
   existing durable `GL_ACCOUNTS -> GL_ACCOUNT` mapping and an active,
   nondeleted same-organization target account.
5. Supplied Property/Unit source IDs are checked only through existing durable
   source mappings; unresolved optional relationships remain review context and
   are never linked by display name.
6. Debit, credit, date, description, reference, remarks and transaction type
   remain source evidence only. This stage does not choose accounting basis,
   calculate balances, infer payee/payer identity or fabricate balancing entries.
7. Every valid row remains REVIEW-only until a separate accounting-history
   reconciliation/dry-run/controlled-commit contract is independently verified.
8. This batch creates or updates zero `GLTransaction`, `GLEntry`, journal
   entry, Receipt, Bill, Charge, GLAccount, AccountingKeyAccount or accounting
   balance records.
9. CSV/XLSX replay remains normalized-fingerprint idempotent; raw source bytes
   are not persisted.
10. No AppFolio API transport or general UX work is added.

## 4.13 Charges / Receivables ingestion + staging

The first Charges/Receivables batch uses the shared `CHARGES` resource and
existing CSV/XLSX upload/detection/mapping/staging architecture.

The source contract is intentionally limited to the current public AppFolio
Stack Charges field inventory:

- `Id`
- `AmountDue`
- `ChargedOn`
- `Description`
- `GlAccountId`
- `OccupancyId`

These fields remain source evidence until later reconciliation proves a safe
target contract.

Safety boundaries:

1. Automatic detection requires a supplied stable Charge `Id` plus
   `AmountDue`, `ChargedOn`, `GlAccountId` and `OccupancyId`.
2. Explicit CHARGES staging may preserve a missing Charge ID for REVIEW/SKIP,
   but never synthesizes identity from occupancy, account, date, description,
   row order, fingerprint or amount.
3. `AmountDue` is the source current outstanding amount. It is not treated as
   original target `Charge.amount`, amount paid, paid/unpaid status, rent,
   reconciled receivable balance or tenant liability.
4. `GlAccountId` is considered resolved only through an existing durable
   `GL_ACCOUNTS -> GL_ACCOUNT` source mapping to an active
   same-organization target.
5. `OccupancyId` is preserved only as source evidence in this batch. The
   current migration architecture has no independently verified durable
   occupancy source-to-target mapping, so no tenant, Lease, Unit or Property is
   inferred from it.
6. `ChargedOn` and `Description` remain source evidence and are not promoted
   into customer records.
7. Duplicate supplied Charge IDs fail closed. Source `AmountDue` must be
   numeric, but its sign is not reinterpreted into unsupported payment/credit
   semantics.
8. Every valid row remains REVIEW-only. GL mapping availability does not make
   the charge commit-ready while Occupancy identity and original-amount/payment
   semantics remain unresolved.
9. This batch creates or updates zero `Charge`, `RentInvoice`, `Receipt`,
   `Payment`, `GLTransaction`, `GLEntry` or customer balance records.
10. Charges reconciliation/dry-run/controlled commit require separate verified
    batches. Do not infer payer liability, payment application, rent-vs-charge
    classification, GL posting or historical reconciliation.

## 4.13 Charges / Receivables staged reconciliation

After CHARGES ingestion/staging is verified, review may explicitly accept only
the relationship that has an independently durable target contract today:
the source `GlAccountId` to an existing active same-organization
`GLAccount`.

Safety boundaries:

1. Reconcile only already-staged `CHARGES` rows from the shared migration
   upload architecture.
2. The only allowed actions are `ACCEPT_RELATIONSHIP` and `SKIP`.
3. A row without a stable supplied Charge `Id` may only be skipped.
4. `ACCEPT_RELATIONSHIP` requires the staged `GlAccountId` to have an
   existing durable `GL_ACCOUNTS -> GL_ACCOUNT` migration mapping and the
   mapped target must still be active in the same organization.
5. `OccupancyId` remains source evidence only. Reconciliation must not infer
   Tenant, Lease, Unit, Property, payer identity or liability from it.
6. The accepted review state snapshots only the verified target GL Account ID
   on the staged row; no Charge target or customer balance record is created.
7. INVALID rows remain non-resolvable. Unresolved REVIEW rows may be explicitly
   skipped.
8. Resolution changes participate in the shared staged-review fingerprint,
   invalidate prior dry-run state and are audited. Repeating the identical
   resolution is idempotent.
9. The batch creates or updates zero `Charge`, `RentInvoice`, `Receipt`,
   `Payment`, `GLTransaction`, `GLEntry` or customer balance records.
10. No paid/unpaid state, original amount, amount paid, rent-vs-charge
    classification, payment application, tenant liability, GL posting or
    historical reconciliation is inferred.

Next dependency after this reconciliation is independently verified:
**CHARGES staged dry run only**. That dry run must bind the exact staged-review
fingerprint plus the currently valid durable GL Account mapping. It remains
review-only and must not create customer receivables or accounting history.

## 5. File/report detection and column mapping

The same AppFolio concept may arrive under different header spellings or export
variants.

The importer may automatically map only high-confidence known aliases.

Example:

| Source column | Target staging field |
|---|---|
| Property Id / Id | source property ID |
| Property Name / Name | property name |
| Street / Address1 / Address 1 | address line 1 |
| Zip / ZipCode / PostalCode | ZIP/postal code |

When uncertain, require an operator mapping decision.

Save explicit mapping decisions with the migration run so later files/replays
use consistent interpretation where appropriate.

Do not silently reinterpret a source field after a dry run.

## 6. Missing-column and missing-file handling

Required source information:
- cannot be synthesized;
- blocks the affected row/resource;
- must identify the missing field/report where known.

Optional source information:
- may remain null/blank;
- must not be replaced with fabricated data.

Derived/normalized information:
- allowed only when deterministic and auditable.

The migration must expose a coverage checklist showing which source families
have been supplied and which are missing.

Example:

- Properties: supplied
- Units: supplied
- Tenants: supplied
- Owners: not supplied
- Vendors: not supplied
- Lease/occupancy: partial
- GL Accounts: not supplied
- General Ledger: not supplied
- Work Orders: not supplied
- Documents: not supplied

A safe partial operational migration may be allowed.

An accounting migration must not be represented as complete until the required
accounting sources reconcile.

## 7. Cross-file relationships

Use stable AppFolio IDs wherever available.

Examples:
- Unit -> Property by AppFolio Property ID
- Tenant/occupancy -> Unit by AppFolio Unit ID
- Owner relationship -> Property by source IDs
- accounting rows -> source GL/property/unit IDs where available

Do not link relationships solely by display name.

If a referenced source ID is missing, contradictory or unresolved, mark the
dependent row for review and block unsafe commit.

Durable source-to-target mappings must remain authoritative after a manual
match is resolved.

## 8. Correction layer

Customers should not need to edit the original source file for every mapping
issue.

Provide migration-stage corrections/mappings such as:

`Apt Bldg -> Apartment`

Rules:
- preserve the original source value where appropriate;
- record the chosen normalized/mapped value;
- record who/when resolved the ambiguity;
- apply the correction to staging/migration logic only;
- never silently rewrite unrelated existing production records.

A correction that changes normalized staged input invalidates the prior dry-run
fingerprint and requires a new dry run.

## 9. Existing-record conflict resolution

Default behavior is **never automatic overwrite**.

Potential resolution choices may include:
- Match to existing
- Create new
- Skip
- Review later

The choice must be explicit and auditable.

Financial/accounting records require stricter identity rules than simple
name/address similarity.

Once resolved, persist the source-to-target mapping so future files and replay
use the same target deterministically.

## 10. Dry-run and commit boundary

The existing verified exact-fingerprint model remains mandatory.

Dry run should eventually summarize:
- new
- possible matches
- matched
- already imported
- skipped
- invalid
- warnings
- blocking errors

Commit must require the exact reviewed normalized/staged fingerprint.

If:
- the source file changes;
- column mapping changes;
- correction mapping changes;
- match resolution changes; or
- dependent source relationships change,

then the previous dry-run fingerprint is stale and commit must fail until a new
dry run is completed.

Replay must not duplicate already committed target records.

## 11. Accounting reconciliation

Historical accounting migration requires explicit reconciliation before commit.

Where source exports support it, compare:
- record counts
- debits
- credits
- GL totals
- beginning/ending balances
- receivable/payable totals
- security-deposit totals
- other authoritative control totals

If source and migration-preview totals do not reconcile, financial commit must
fail closed or enter a specifically designed exception-review workflow.

Never manufacture a balancing journal entry merely to make imported totals
agree.

Never bypass locked-period, audit, reversal, organization-scope or central GL
rules.

## 12. API path — optional later adapter

The API path is no longer a blocker for Phase 4.13.

Later, after the file-based migration system is mature, a legitimate AppFolio
Reports API or Database API adapter may feed the same staging contracts.

Requirements:
- read `docs/APPFOLIO_API_RESEARCH.md`;
- verify transport/authentication against current legitimate AppFolio
  documentation/test access;
- do not use undocumented browser/session endpoints as production transport;
- API records must enter the same mapping/staging/dry-run/reconciliation/commit
  pipeline as file imports;
- API transport must not get a privileged bypass around migration safeguards.

## 13. Verification

Each bounded batch must use applicable focused tests plus hosted CI.

Do not mark a product batch VERIFIED until:
- exact product SHA is known;
- all six required hosted CI jobs pass;
- real backend/E2E test counts are recorded;
- migration/parity/security checks are clean;
- `AI_HANDOFF.md` records the verified state and exact next task.

## 14. Preserved architecture

Do not disturb:
- Phase 4.11 Senior Housing verified work
- Phase 4.12 Short-term Rentals verified work
- current Phase 4.13 migration run model
- dry-run-before-commit
- exact fingerprinting
- source-to-target durable mappings
- replay/idempotency protection
- mapping/recovery visibility
- organization isolation
- audit integrity
- customer accounting safeguards
- navigation integrity
- hidden-menu roadmap
- `docs/NAVIGATION_INTEGRITY_PLAN.md`
- inactive `docs/UX_STANDARDS.md`
