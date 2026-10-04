# AI_HANDOFF.md — 2026-10-04 PHASE 4.14 BUILDIUM PROPERTY MATCH REVIEW VERIFIED

## Current verified checkpoint

- Phase 4.13 — AppFolio CSV/XLSX migration: **COMPLETE | VERIFIED for the authorized file-based path**.
- Phase 4.14 — Buildium direct/API-assisted migration: **IN PROGRESS**.
- Verified PRODUCT SHA: `ccb433f41484543f595de0d95a1083198e22c824`.
- GitHub Actions run: `37192597336` — **SUCCESS**.
- All six required CI jobs passed:
  - frontend: PASS
  - backend: PASS
  - security: PASS
  - platform-admin: PASS
  - staging-config: PASS
  - authenticated E2E: PASS
- Backend/PostgreSQL: **994 passed, 21 deselected, 25840 warnings in 459.83s**.
- Authenticated E2E: **21 passed, 278 warnings in 114.42s**.
- Alembic head remains `1b8d3f6a9c20`.
- Expected model tables remain **202**.
- No migration was added in this batch.
- Navigation integrity and the complete HIDDEN MENU / UNHIDE ROADMAP remain unchanged.
- `docs/UX_STANDARDS.md` remains AUTHORIZED BUT NOT ACTIVE.

## Verified Buildium Property match-review behavior

The first Buildium Property foundation remains intact and now supports an
explicit reviewed decision for a source Property that may already exist in the
target organization.

Verified behavior:

1. Possible existing target matches are never auto-selected or overwritten.
2. The review contract supports only explicit `MATCH_EXISTING`, `CREATE_NEW`
   or `SKIP` decisions tied to an exact positive Buildium source `Id`.
3. A MATCH_EXISTING target is revalidated as active, undeleted and in the same
   target organization at dry-run and controlled-commit time.
4. Resolution state is included in the exact Buildium dry-run fingerprint, so a
   changed source row, changed resolution, changed target, or changed
   include-inactive choice cannot reuse a stale reviewed preview.
5. CREATE_NEW remains explicit and does not silently overwrite an existing
   customer Property.
6. SKIP excludes the reviewed source row from controlled commit without
   manufacturing a mapping.
7. Durable replay/idempotency continues to use the existing
   `platform_migration_items` provider-labelled mapping table.
8. Cross-organization targets, deleted/inactive targets, stale resolution
   payloads and inconsistent replay mappings fail closed.
9. No Buildium API credentials, outbound network calls, raw provider response
   persistence, accounting mutation, or Phase 4.13 behavior was added.
10. Focused Buildium regression coverage is included in the verified backend
    total above.

## Exact NEXT Phase 4.14 batch

Proceed to **Buildium Units foundation** using the same verified provider-labelled
migration architecture and the official Buildium v1 Rental Units source contract.

Required boundaries:

- use stable Buildium Unit `Id` as source identity;
- require the source `PropertyId` and resolve it only through an existing
  durable Buildium Property mapping from this same migration run;
- map Buildium `UnitNumber` and structured `Address` conservatively;
- preserve explicit review instead of guessing when a possible target Unit
  already exists under the mapped Property;
- never infer occupancy from `IsUnitOccupied`;
- do not create Lease/Tenant/Charge/GL history in the Unit batch;
- bind Property mapping state and any Unit match resolution into exact
  dry-run/commit fingerprints so stale mappings cannot be reused;
- preserve organization isolation, replay/idempotency, audit and no-overwrite
  rules;
- add focused cross-org/property, stale mapping, duplicate source ID,
  replay and no-unintended-mutation regressions;
- no Buildium credential storage or outbound API transport yet.

Do not reopen Phase 4.13, start general UX/navigation work, touch main, create a
new branch, or add the optional AppFolio API adapter.

---

# AI_HANDOFF.md — 2026-10-04 PHASE 4.14 BUILDIUM PROPERTY FOUNDATION VERIFIED

## Current verified checkpoint

- Phase 4.13 — AppFolio CSV/XLSX migration: **COMPLETE | VERIFIED for the authorized file-based path**.
- Phase 4.14 — Buildium direct/API-assisted migration: **IN PROGRESS**.
- Verified PRODUCT SHA: `be83e29e1792638c617f26fac277f2b20e439698`.
- GitHub Actions run: `37191001666` — **SUCCESS**.
- All six required CI jobs passed:
  - frontend: PASS
  - backend: PASS
  - security: PASS
  - platform-admin: PASS
  - staging-config: PASS
  - authenticated E2E: PASS
- Backend/PostgreSQL: **989 passed, 21 deselected, 25752 warnings in 468.57s**.
- Authenticated E2E: **21 passed, 278 warnings in 90.81s**.
- Alembic head remains `1b8d3f6a9c20`.
- Expected model tables remain **202**.
- No migration was added in this batch.
- Navigation integrity and the complete HIDDEN MENU / UNHIDE ROADMAP remain unchanged.
- `docs/UX_STANDARDS.md` remains AUTHORIZED BUT NOT ACTIVE.

## Verified Phase 4.14 first batch

The first Buildium migration batch reuses the existing provider-labelled
`PlatformMigrationRun` and `PlatformMigrationItem` architecture rather
than creating a parallel migration subsystem.

Verified bounded behavior:

1. Platform migration runs may now use provider `BUILDIUM` with the same
   organization scope, platform-role authorization, no-store reads and
   append-only audit expectations used by the verified migration foundation.
2. The first supported source contract is the official Buildium v1 Rental
   Property record shape supplied to the service after retrieval:
   - stable positive `Id`;
   - `Name`;
   - boolean `IsActive`;
   - structured `Address` with AddressLine1/2/3, City, State, PostalCode,
     Country;
   - optional `YearBuilt`;
   - `RentalSubType`.
3. The service does **not** make Buildium network calls in this batch and does
   **not** accept, persist or audit Buildium API credentials or raw provider
   response bodies.
4. Exact dry-run fingerprints bind provider, target organization,
   source-account reference, inactive-record choice and the exact supplied
   source records. A changed payload cannot reuse an older reviewed
   fingerprint.
5. Durable source-to-target mappings use the existing
   `platform_migration_items` table with provider `BUILDIUM` and resource
   `PROPERTIES`. Replays are idempotent and do not create duplicate
   Properties or mappings.
6. Inactive Buildium properties are excluded by default. When explicitly
   included, their target Property remains inactive rather than being silently
   activated.
7. Buildium property subtype mapping is intentionally conservative:
   - SingleFamily -> single-family;
   - MultiFamily -> multi-family;
   - documented commercial subtypes -> commercial;
   - CondoTownhome -> OTHER with a review warning rather than guessing condo
     versus townhouse;
   - absent/unknown subtype -> OTHER with a warning.
8. A populated Buildium AddressLine3 is a blocking validation error because
   the current target Property contract has no third address line. No address
   content is silently discarded.
9. A possible existing target Property match is surfaced during dry run and
   controlled commit is blocked. The system never auto-overwrites or silently
   duplicates the customer record.
10. Focused regressions cover platform role/provider isolation, target-org
    scope, no-store reads, exact fingerprint staleness, inactive preservation,
    source-ID duplication, AddressLine3 loss prevention, subtype warnings,
    replay/idempotency, durable mapping visibility, secret/raw-address audit
    exclusion and possible-match commit blocking.

## Current Phase 4.14 transport boundary

Official Buildium Open API v1 supports server-to-server API-key access and a
sandbox, but the verified product source above deliberately stops before
credential storage or outbound API transport. A later transport adapter must
feed the same provider-labelled migration/review/fingerprint/mapping pipeline.
It must never place Buildium client secrets in migration records, audit logs,
browser code or customer-visible responses.

## Exact NEXT Phase 4.14 batch

Before adding Buildium Units, close the first property safety gap:

**Buildium Property explicit existing-match review/resolution.**

Required behavior:

- reuse the existing provider-labelled migration run/mapping architecture;
- add an explicit reviewed decision for a possible target Property match;
- support only deliberate `MATCH_EXISTING`, `CREATE_NEW` or `SKIP`
  semantics for the reviewed Buildium source row;
- revalidate target organization, active/deleted state and exact source
  identity at commit time;
- bind the resolution state into the exact reviewed dry-run/commit contract so
  stale previews or changed source rows cannot inherit an old decision;
- preserve durable replay/idempotency;
- never automatically overwrite an existing customer Property;
- add focused cross-organization, stale-resolution, replay, deleted-target and
  no-unintended-mutation regressions;
- no Buildium API credentials/network transport yet;
- no Units batch until this property-match review gap is verified.

Do not reopen Phase 4.13, start general UX/navigation work, touch main, create a
new branch, or add the optional AppFolio API adapter.

---

# AI_HANDOFF.md — 2026-10-04 PHASE 4.13 CSV/XLSX FILE PATH COMPLETE | VERIFIED

## Final Phase 4.13 file-based migration checkpoint

- Phase 4.11 — Senior Housing: **COMPLETE | VERIFIED**.
- Phase 4.12 — Short-term Rentals: **COMPLETE | VERIFIED**.
- Phase 4.13 — AppFolio CSV/XLSX migration: **COMPLETE | VERIFIED for the authorized file-based path**.
- Final VERIFIED PRODUCT SHA: `b4ef4ac8313068a6cd1d1466b197fdf3cbf28bb7`.
- Product CI: `37172152530` — SUCCESS.
- File-path closeout source SHA: `e60d83f3c34704f79ea52bbf7aac99656301825b`.
- Closeout CI: `37172973833` — SUCCESS.
- All six required CI jobs passed on both final product and closeout verification checkpoints:
  - frontend: PASS
  - backend: PASS
  - security: PASS
  - platform-admin: PASS
  - staging-config: PASS
  - authenticated E2E: PASS
- Backend/PostgreSQL: **985 passed, 21 deselected, 25690 warnings in 463.28s** on closeout CI.
- Authenticated E2E: **21 passed, 278 warnings in 111.38s** on closeout CI.
- Alembic head remains `1b8d3f6a9c20`.
- Expected model tables remain **202**.
- Navigation integrity and the `HIDDEN MENU / UNHIDE ROADMAP` remain unchanged.
- `docs/UX_STANDARDS.md` remains AUTHORIZED BUT NOT ACTIVE.

## What Phase 4.13 now safely supports

The authorized AppFolio file path is:

`CSV/XLSX -> upload -> detect -> map -> stage -> validate -> review -> reconcile -> dry run -> controlled commit where the verified source/target contract is sufficient`.

Verified shared controls include bounded CSV/XLSX parsing, resource detection,
explicit column mapping, durable source identity, staged validation/review,
correction rules, source-to-target durable mappings, exact fingerprints,
stale-preview protection, run-level coverage/review summaries, review snapshot
fingerprinting, replay/idempotency, recovery/mapping visibility, organization
isolation and audit.

Verified resource coverage:

- Properties — controlled commit supported.
- Units — controlled commit supported.
- Owners — controlled existing-record mapping supported.
- Vendors — controlled commit supported.
- Tenants — controlled mapping supported.
- Lease/occupancy — staging + relationship reconciliation verified; controlled commit blocked on insufficient verified lease/occupancy semantics.
- GL Accounts — controlled mapping to existing same-organization GL Accounts supported.
- General Ledger/history — staging, relationship reconciliation, dry run, balanced transaction-group readiness, overall and per-account reconciliation verified; historical controlled posting remains blocked on independently verified target accounting semantics.
- Bills/payables — staging, relationship reconciliation, dry run and source identity/count/TotalAmount reconciliation verified; controlled commit blocked on line-item GL allocation and deterministic posting/business-date semantics.
- Charges/receivables — staging, relationship reconciliation, dry run and source identity/count/AmountDue reconciliation verified; controlled commit blocked on Occupancy/tenant identity plus original-charge/payment semantics.
- Work Orders — staging, relationship reconciliation and dry run verified; controlled commit blocked where the source contract cannot safely establish required target identity/assignment semantics.
- Security Deposits — automatic ingestion/reconciliation remains BLOCKED on authoritative source-schema evidence.
- Attachments/Documents — automatic ingestion remains BLOCKED on authoritative source-schema/entity-relationship evidence.

Section 11 reconciliation is complete wherever the verified current source contracts support it: record identity/count, GL debit/credit/per-account totals, Bills/payables TotalAmount and Charges/receivables AmountDue. Beginning/ending balances, Security Deposit totals and other external control totals remain explicitly unverified where no authoritative supplied source contract exists. No balancing entries or synthetic history may be fabricated.

## Preserved exclusions

- Do not implement the AppFolio API adapter yet. Section 12 remains optional later transport/testing and must feed this same verified staging pipeline.
- Do not add general UX work unless the owner explicitly says `start UX work`.
- Do not change navigation integrity or the hidden-menu roadmap unless a future verified feature actually qualifies under the existing unhide rules.
- Do not automatically overwrite existing customer records or invent missing source data.
- Do not reinterpret the resource-specific blockers above as authorization to synthesize accounting, occupancy, maintenance or document history.

## STOP / NEXT REFERENCE

Phase 4.13 file-based AppFolio migration work is complete at this checkpoint.

**Do not start Phase 4.14 in this closeout batch.**

The next roadmap phase may be taken up only in a subsequent explicit continuation instruction. The optional AppFolio API adapter also remains deferred and is not a prerequisite for this completed CSV/XLSX path.

---

# AI_HANDOFF.md — 2026-10-04 PHASE 4.13 CHARGES / RECEIVABLES RECONCILIATION VERIFIED

## Current verified product checkpoint

- Phase 4.11 — Senior Housing: **COMPLETE | VERIFIED**.
- Phase 4.12 — Short-term Rentals: **COMPLETE | VERIFIED**.
- Phase 4.13 — AppFolio CSV/XLSX migration: **IN PROGRESS**.
- Verified PRODUCT SHA: `b4ef4ac8313068a6cd1d1466b197fdf3cbf28bb7`.
- GitHub Actions run: `37172152530` — SUCCESS.
- All six required CI jobs passed:
  - frontend: PASS
  - backend: PASS
  - security: PASS
  - platform-admin: PASS
  - staging-config: PASS
  - authenticated E2E: PASS
- Backend/PostgreSQL: **985 passed, 21 deselected, 25690 warnings in 453.55s**.
- Authenticated E2E: **21 passed, 278 warnings in 113.44s**.
- Alembic head remains `1b8d3f6a9c20`.
- Expected model tables remain **202**.
- Navigation integrity and the `HIDDEN MENU / UNHIDE ROADMAP` remain unchanged.
- `docs/UX_STANDARDS.md` remains AUTHORIZED BUT NOT ACTIVE.

## Verified Charges / Receivables reconciliation control

1. A read-only Section 11 control compares retained staged Charge identity/count and supplied `AmountDue` against the exact current Charges dry-run preview.
2. Only rows already explicitly accepted through the verified Charges relationship review path are reconciled; SKIP rows remain excluded and unresolved/INVALID rows remain blockers through the existing dry-run helper.
3. Current durable GL Account relationships are revalidated through the existing Charges dry-run helper and the exact current dry-run fingerprint remains authoritative.
4. The result is explicitly review-only with `accounting_complete=false`; original billed amount, amount paid, paid/unpaid state, Occupancy/tenant identity, payment application, GL posting and historical AR balances remain unverified.
5. No Charge, RentInvoice, Receipt, Payment, GLTransaction, GLEntry, Bill, Check or customer balance is created or changed.
6. Platform read authorization, run/organization/upload/provider isolation and no-store behavior remain intact.
7. Focused tests cover deterministic count/identity/AmountDue reconciliation, stale-preview rejection, route exposure, SALES denial and zero accounting mutation.
8. AppFolio API transport, general UX, navigation and hidden-menu work remain out of scope.

Implementation commits in this bounded batch:
- `e126ba300bb009887d9de5a31f1479b3f67102b1` — Charges reconciliation response contract.
- `b6f48cc86aa8a9602036ab200f820e31b44d1a75` — read-only Charges/Receivables reconciliation control.
- `b4ef4ac8313068a6cd1d1466b197fdf3cbf28bb7` — focused reconciliation/stale-preview/authorization regressions; final VERIFIED PRODUCT SHA.

## Exact next Phase 4.13 batch

Perform a **file-based Phase 4.13 closeout audit** against `docs/APPFOLIO_MIGRATION_IMPORT_PLAN.md` and the verified live source.

Required boundaries:

1. Confirm every currently supportable CSV/XLSX resource in the plan has a verified upload/detect/map/stage/validate/review/dry-run/commit-or-explicit-blocker contract.
2. Confirm Section 11 controls now cover supported record counts, GL debit/credit/account totals, payable totals and receivable totals.
3. Preserve explicit blockers instead of inventing source data:
   - Security Deposit automatic ingestion/reconciliation remains blocked on authoritative source-schema evidence.
   - beginning/ending accounting balances remain unverified where no authoritative supplied control export exists.
   - controlled commits for Lease/occupancy, General Ledger history, Bills, Charges and Work Orders remain blocked where verified target/source semantics are insufficient.
   - Attachments/Documents automatic ingestion remains blocked on authoritative source-schema/relationship evidence.
4. Do not add AppFolio API transport; Section 12 remains an optional later adapter.
5. Do not add general UX, navigation or hidden-menu changes.
6. If no independently safe file-path product gap remains after reconciliation, update the plan/handoff to mark the Phase 4.13 CSV/XLSX path complete with the resource-specific blockers explicitly preserved. Do not start Phase 4.14 in the same batch.

---

# AI_HANDOFF.md — 2026-10-04 PHASE 4.13 BILLS / PAYABLES RECONCILIATION VERIFIED

## Current verified product checkpoint

- Phase 4.11 — Senior Housing: **COMPLETE | VERIFIED**.
- Phase 4.12 — Short-term Rentals: **COMPLETE | VERIFIED**.
- Phase 4.13 — AppFolio CSV/XLSX migration: **IN PROGRESS**.
- Verified PRODUCT SHA: `20cdbbff7db2c5e77fee1569fc105614c8091138`.
- GitHub Actions run: `37167167312` — SUCCESS.
- All six required CI jobs passed:
  - frontend: PASS
  - backend: PASS
  - security: PASS
  - platform-admin: PASS
  - staging-config: PASS
  - authenticated E2E: PASS
- Backend/PostgreSQL: **983 passed, 21 deselected, 25654 warnings in 340.37s**.
- Authenticated E2E: **21 passed, 278 warnings in 115.68s**.
- Alembic head remains `1b8d3f6a9c20`.
- Expected model tables remain **202**.
- Navigation integrity and the `HIDDEN MENU / UNHIDE ROADMAP` remain unchanged.
- `docs/UX_STANDARDS.md` remains AUTHORIZED BUT NOT ACTIVE.

## Verified Bills / Payables reconciliation control

1. A read-only Section 11 control compares retained staged Bill identity/count and supplied `TotalAmount` against the exact current Bills dry-run preview.
2. Only rows already explicitly accepted through the verified Bills relationship review path are reconciled; SKIP rows remain excluded and unresolved/INVALID rows remain blockers.
3. Current durable Property/Vendor mappings are revalidated through the existing Bills dry-run helper and the exact current dry-run fingerprint remains authoritative.
4. The result is explicitly review-only with `accounting_complete=false`; BillLine allocations, AP posting, paid/unpaid state, check/payment application, business/posting-date semantics and historical AP balances remain unverified.
5. No Bill, BillLine, Check, VendorCredit, GLTransaction, GLEntry, Charge, Receipt, Payment or customer balance is created or changed.
6. Platform read authorization, run/organization/upload/provider isolation and no-store behavior remain intact.
7. Focused tests cover deterministic count/identity/TotalAmount reconciliation, stale-preview rejection, authorization and zero accounting mutation.
8. AppFolio API transport, general UX, navigation and hidden-menu work remain out of scope.

## Exact next Phase 4.13 product batch

Add the matching read-only **Charges / Receivables staged reconciliation control** over the already-verified CHARGES dry-run contract.

Required boundaries:

1. Operate only on already-staged `CHARGES` rows and the exact current Charges dry-run fingerprint.
2. Reconcile only retained rows already explicitly accepted by the verified Charges relationship review/dry-run path; SKIP rows remain excluded and unresolved/INVALID rows remain blockers.
3. Compare stable source Charge identity/count plus supplied source `AmountDue` against the exact current preview `AmountDue` for the same retained source IDs.
4. Revalidate current durable GL Account relationships through the existing Charges dry-run helper; stale mappings or changed staged evidence must fail closed through exact-fingerprint protection.
5. Keep the result review-only with `accounting_complete=false`. It must not claim original billed amount, amount paid, paid/unpaid state, tenant/Occupancy identity, payment application, GL posting or historical AR reconciliation.
6. Do not infer tenant liability, rent-vs-charge classification, original charge amount, payment history, target Occupancy identity or GL posting semantics.
7. Do not create/update Charge, RentInvoice, Receipt, Payment, GLTransaction, GLEntry, Bill, Check or customer balances.
8. Preserve platform read authorization, run/org/upload/provider isolation and `Cache-Control: no-store`.
9. Add focused tests for deterministic source-vs-preview count/AmountDue reconciliation, stale-preview protection, authorization and zero mutation.
10. Keep AppFolio API transport, general UX, navigation and hidden-menu work out of scope.

---

# AI_HANDOFF.md — 2026-10-04 PHASE 4.13 GENERAL LEDGER PER-ACCOUNT RECONCILIATION VERIFIED

## Current verified product checkpoint

- Phase 4.11 — Senior Housing: **COMPLETE | VERIFIED**.
- Phase 4.12 — Short-term Rentals: **COMPLETE | VERIFIED**.
- Phase 4.13 — AppFolio CSV/XLSX migration: **IN PROGRESS**.
- Verified PRODUCT SHA: `1035185c978993dcfc5c0949e985cc0b62cadf1f`.
- GitHub Actions run: `37166335534` — SUCCESS.
- All six required CI jobs passed:
  - frontend: PASS
  - backend: PASS
  - security: PASS
  - platform-admin: PASS
  - staging-config: PASS
  - authenticated E2E: PASS
- Backend/PostgreSQL: **981 passed, 21 deselected, 25621 warnings in 344.46s**.
- Authenticated E2E: **21 passed, 278 warnings in 114.03s**.
- Alembic head remains `1b8d3f6a9c20`.
- Expected model tables remain **202**.
- Navigation integrity and the `HIDDEN MENU / UNHIDE ROADMAP` remain unchanged.
- `docs/UX_STANDARDS.md` remains AUTHORIZED BUT NOT ACTIVE.

## Verified per-GL-account reconciliation controls

1. The existing read-only General Ledger reconciliation now also produces deterministic control totals per durable source GL Account identity and resolved same-organization target GL Account ID.
2. Each account control compares source-vs-preview line count, debit total and credit total and exposes an explicit reconciled flag.
3. Account controls are canonically sorted by source GL Account ID and target ID; identical replay is deterministic.
4. The exact current staged dry-run/readiness fingerprint remains authoritative. A changed durable GL Account mapping source fingerprint or changed staged source evidence makes the prior dry run stale and reconciliation fails closed.
5. Overall reconciliation now requires line identity/count, total debit/credit, balanced supplied TransactionId groups and all per-account controls to match.
6. `accounting_complete` remains false. Beginning/ending balances, AR, AP, security deposits and independent external control totals remain explicitly unverified.
7. No balancing journal, GL transaction, Charge, Bill, Receipt, Payment or other customer/accounting record is created or changed.
8. Focused tests prove account-level totals for both debit and credit accounts, deterministic ordering, stale mapping protection, stale staged evidence protection and zero accounting mutation.
9. AppFolio API transport, general UX, navigation and hidden-menu work remain out of scope.

Implementation commits in this bounded batch:
- `a5deafb7a80468f48bd73462002638425c3ce875` — account reconciliation response contract.
- `54c0a95a2602da19e47ce3932e48c76713d2e149` — per-GL-account reconciliation aggregation.
- `1035185c978993dcfc5c0949e985cc0b62cadf1f` — focused per-account/stale-mapping tests; final VERIFIED PRODUCT SHA.

## Exact next Phase 4.13 product batch

Add a read-only **Bills / Payables staged reconciliation control** over the already-verified BILLS dry-run contract.

Required boundaries:

1. Operate only on already-staged `BILLS` rows and the exact current Bills dry-run fingerprint.
2. Reconcile only retained rows already explicitly accepted by the verified Bills relationship review/dry-run path; SKIP rows remain excluded and unresolved/INVALID rows remain blockers.
3. Compare stable source Bill identity/count plus source `TotalAmount` against the exact current preview `TotalAmount` for the same retained source IDs.
4. Revalidate current durable Property/Vendor relationships through the existing Bills dry-run helper; stale mappings or changed staged evidence must fail closed through exact-fingerprint protection.
5. Keep the result review-only with `accounting_complete=false`. It must not claim AP, payment, posting-date, line-item allocation, GL distribution or historical balance reconciliation.
6. Do not infer Bill line allocations, payment/application history, vendor liability beyond supplied source evidence, or target GL posting.
7. Do not create/update Bill, BillLine, Check, VendorCredit, GLTransaction, GLEntry, Charge, Receipt, Payment or customer balances.
8. Preserve platform read authorization, run/org/upload/provider isolation and `Cache-Control: no-store`.
9. Add focused tests for deterministic source-vs-preview count/TotalAmount reconciliation, stale-preview protection, authorization and zero mutation.
10. Keep AppFolio API transport, general UX, navigation and hidden-menu work out of scope.

---

# AI_HANDOFF.md — 2026-10-04 PHASE 4.13 GENERAL LEDGER RECONCILIATION CONTROL VERIFIED

## Current verified product checkpoint

- Phase 4.11 — Senior Housing: **COMPLETE | VERIFIED**.
- Phase 4.12 — Short-term Rentals: **COMPLETE | VERIFIED**.
- Phase 4.13 — AppFolio CSV/XLSX migration: **IN PROGRESS**.
- Verified PRODUCT SHA: `70108b1b7091f93a0bd6cb4158442559689da65e`.
- GitHub Actions run: `37165527762` — SUCCESS.
- All six required CI jobs passed:
  - frontend: PASS
  - backend: PASS
  - security: PASS
  - platform-admin: PASS
  - staging-config: PASS
  - authenticated E2E: PASS
- Backend/PostgreSQL: **981 passed, 21 deselected, 25621 warnings in 448.66s**.
- Authenticated E2E: **21 passed, 278 warnings in 112.11s**.
- Alembic head remains `1b8d3f6a9c20`.
- Expected model tables remain **202**.
- Navigation integrity and the `HIDDEN MENU / UNHIDE ROADMAP` remain unchanged.
- `docs/UX_STANDARDS.md` remains AUTHORIZED BUT NOT ACTIVE.

## Verified General Ledger reconciliation control

1. A read-only no-store Section 11 reconciliation endpoint now compares accepted staged AppFolio General Ledger source evidence against the exact current staged dry-run/readiness state.
2. The control verifies accepted line count, exact line identity, total debits, total credits, and supplied `TransactionId` group balance.
3. The reconciliation requires the exact latest staged dry-run fingerprint; normalized staged changes invalidate the prior preview and fail closed until a new dry run/readiness pass is completed.
4. The response keeps `accounting_complete=false` and explicitly lists unverified controls including beginning balance, ending balance, receivables, payables, security deposits and independent external control totals.
5. No balancing journal entry is created. No GL transaction/account, Charge or other customer/accounting record is mutated by reconciliation.
6. Platform read authorization, organization/run/upload/provider isolation and no-store behavior remain authoritative; platform SALES is denied.
7. Focused tests cover deterministic matching totals, stale-preview rejection, authorization, route exposure and zero accounting mutation.
8. CI on the initial test-fix SHA exposed an unrelated Short-term Rentals authenticated-navigation race after backend success. Test-only commit `70108b1b7091f93a0bd6cb4158442559689da65e` waits for authenticated dashboard/property readiness before clicking the gated tab; product behavior is unchanged.
9. AppFolio API transport, general UX, navigation and hidden-menu work remain out of scope.

Implementation commits in this bounded batch:
- `2f8fb88f9331697756c82ed93f0ab9f10579330b` — reconciliation response contract.
- `d1887d32cee195f17e24ae7b97791c2b7cb2ce2e` — read-only General Ledger reconciliation control.
- `8834ff3a6182cd26ab1545ae02492f37c62c3b2b` — reconciliation/stale-preview regressions.
- `0e95525fc12bdbcc379cd3ae37d454df374ac739` and `11f44f32e9b59f978adc956650d87f7e1a3b41f8` — authorization/test corrections.
- `70108b1b7091f93a0bd6cb4158442559689da65e` — scoped E2E stabilization; final VERIFIED PRODUCT SHA.

## Exact next Phase 4.13 product batch

Extend the same read-only Section 11 General Ledger reconciliation boundary with deterministic **per-GL-account source-vs-preview control totals**.

Required boundaries:

1. Operate only on already accepted/staged `GENERAL_LEDGER` rows and the exact current dry-run/readiness state.
2. Compare debit/credit totals per durable source GL Account identity and its currently resolved same-organization target GL Account ID.
3. Require every accepted line to have the exact durable GL Account mapping already used by the verified dry run; stale or changed mappings must fail closed.
4. Canonicalize/sort account controls deterministically; identical replay must be stable.
5. Expose source and preview debit/credit totals plus explicit per-account match status. Do not infer external balances not present in the source export.
6. Keep `accounting_complete=false`; this still does not verify beginning/ending balances, AR, AP, security deposits or independent external control totals.
7. Do not create balancing journals, GL transactions, Charges, Bills, Receipts, Payments or any customer/accounting mutation.
8. Preserve platform read authorization, organization/run/upload/provider isolation, no-store behavior and exact-fingerprint stale-preview protection.
9. Add focused tests for matching per-account totals, stale mapping/source evidence, deterministic ordering and zero mutation.
10. Keep AppFolio API transport, general UX, navigation and hidden-menu work out of scope.

---

# AI_HANDOFF.md — 2026-10-04 PHASE 4.13 RUN-LEVEL REVIEW SNAPSHOT FINGERPRINT VERIFIED

## Current verified product checkpoint

- Phase 4.11 — Senior Housing: **COMPLETE | VERIFIED**.
- Phase 4.12 — Short-term Rentals: **COMPLETE | VERIFIED**.
- Phase 4.13 — AppFolio CSV/XLSX migration: **IN PROGRESS**.
- Verified PRODUCT SHA: `af95086c25a5f8cc4c42ea91375f6d2611dee037`.
- GitHub Actions run: `37163325927` — SUCCESS.
- All six required CI jobs passed:
  - frontend: PASS
  - backend: PASS
  - security: PASS
  - platform-admin: PASS
  - staging-config: PASS
  - authenticated E2E: PASS
- Backend/PostgreSQL: **980 passed, 21 deselected, 25612 warnings in 398.63s**.
- Authenticated E2E: **21 passed, 278 warnings in 88.21s**.
- Alembic head remains `1b8d3f6a9c20`.
- Expected model tables remain **202**.
- Navigation integrity and the `HIDDEN MENU / UNHIDE ROADMAP` remain unchanged.
- `docs/UX_STANDARDS.md` remains AUTHORIZED BUT NOT ACTIVE.

## Verified run-level review snapshot fingerprint

1. The shared read-only AppFolio run review summary now exposes one deterministic SHA-256 review fingerprint over durable migration evidence already stored in the run.
2. The canonical fingerprint includes run identity, upload IDs/resources/normalized fingerprints, each upload's staged-review fingerprint, run-scoped correction rules, and durable source mappings including resource/source identity/target identity/source fingerprint.
3. The existing staged-review fingerprint already binds normalized staged values, row source fingerprints, correction evidence, dispositions and explicit review resolutions; those changes therefore invalidate the run-level review fingerprint.
4. Upload, correction-rule, staged review/resolution, staged source-fingerprint, durable mapping fingerprint or mapping target changes produce a different run review fingerprint; identical replay remains deterministic.
5. The run-level fingerprint is review/readiness metadata only. It does not authorize a global commit, mutate run status, or claim accounting completeness.
6. Platform read authorization, organization/run/provider isolation and `Cache-Control: no-store` remain authoritative.
7. Focused tests prove deterministic replay, all required fingerprint-change cases and zero mutation of uploads, staged rows, correction rules, source mappings, customer records or accounting records.
8. Exact-SHA CI first exposed an unrelated Student Housing authenticated-navigation race after all backend migration tests passed. Scoped test-only commit `af95086c25a5f8cc4c42ea91375f6d2611dee037` waits for authenticated dashboard/property readiness before clicking the gated tab; product behavior is unchanged.
9. AppFolio API transport, general UX, navigation and hidden-menu work remain out of scope.

Implementation commits in this batch include the review-summary schema/aggregation/fingerprint tests through `65768f2c25cf86913c11241f3cdd62d435030946`, plus the scoped E2E stabilization `af95086c25a5f8cc4c42ea91375f6d2611dee037` (final VERIFIED PRODUCT SHA).

## Exact next Phase 4.13 product batch

Reconcile the remaining authoritative `docs/APPFOLIO_MIGRATION_IMPORT_PLAN.md` requirements against live source and implement the next smallest independently safe gap. Preserve the shared migration-run/upload/staging architecture, exact-fingerprint dry-run/commit boundaries, durable source mappings, replay/idempotency, recovery visibility and accounting fail-closed rules. Do not add AppFolio API transport, general UX, navigation or hidden-menu changes.

---

# AI_HANDOFF.md — 2026-10-03 PHASE 4.13 RUN-LEVEL REVIEW SUMMARY VERIFIED

## Current verified product checkpoint

- Phase 4.11 — Senior Housing: **COMPLETE | VERIFIED**.
- Phase 4.12 — Short-term Rentals: **COMPLETE | VERIFIED**.
- Phase 4.13 — AppFolio CSV/XLSX migration: **IN PROGRESS**.
- Verified PRODUCT SHA: `f8a640bddd088d759113ded793b258b96964315c`.
- GitHub Actions run: `37160770621` — SUCCESS.
- All six required CI jobs passed:
  - frontend: PASS
  - backend: PASS
  - security: PASS
  - platform-admin: PASS
  - staging-config: PASS
  - authenticated E2E: PASS
- Backend/PostgreSQL: **979 passed, 21 deselected, 25601 warnings in 244.95s**.
- Authenticated E2E: **21 passed, 278 warnings in 74.84s**.
- Alembic head remains `1b8d3f6a9c20`.
- Expected model tables remain **202**.
- Navigation integrity and the `HIDDEN MENU / UNHIDE ROADMAP` remain unchanged.
- `docs/UX_STANDARDS.md` remains AUTHORIZED BUT NOT ACTIVE.

## Verified shared run-level migration review summary

1. A no-store platform-read endpoint aggregates durable migration run/upload/staged-row/source-mapping state across the whole AppFolio run.
2. The summary reports overall and per-resource counts for NEW, unresolved POSSIBLE_MATCH, explicit MATCH_EXISTING, explicit CREATE_NEW, relationship-only ACCEPT_RELATIONSHIP, ALREADY_MAPPED, SKIP, INVALID, unresolved REVIEW, warnings and conservative blockers.
3. ACCEPT_RELATIONSHIP is reported separately and is never mislabeled as an imported/matched customer target.
4. Durable source mappings are counted independently from staged review decisions.
5. The summary exposes the current run dry-run fingerprint/resource when present and reports `NONE_OR_STALE` whenever durable migration evidence exists without a current fingerprint; it does not trust the mutable run status alone.
6. Unknown staged dispositions fail conservatively into unresolved/blocking review rather than being treated as importable.
7. Run/organization/provider filters remain fail-closed and platform SALES cannot read migration review state.
8. Focused tests prove mixed-resource counts, run/org isolation, no-store behavior, role enforcement and zero mutation of uploads, staged rows, source mappings, customer records or accounting records.
9. The batch creates no AppFolio API transport, general UX, navigation or hidden-menu work.

Implementation commits:
- `e441355524b91efa02edd27632abcaf9052cf5ec` — review-summary response contract.
- `5c08655675d46b7355c68f0ea4e53f113782255f` — read-only run-level review aggregation.
- `9b033d918840a21182f0c3f75edbd4adad99cd15` — focused mixed-resource/non-mutation/authorization regressions.
- `f8a640bddd088d759113ded793b258b96964315c` — durable-evidence dry-run-state correction; final VERIFIED PRODUCT SHA.

## Exact next Phase 4.13 product batch

Extend the shared Section 10 review boundary with a deterministic **run-level review snapshot fingerprint**.

Required boundaries:

1. Fingerprint only durable AppFolio migration evidence already inside the shared run: upload normalized fingerprints, current staged-review fingerprints (including correction rules/evidence and explicit resolutions), and durable source-mapping identity/fingerprints.
2. Sort/canonicalize every component deterministically; identical replay must produce the same fingerprint.
3. Any upload, normalized staged correction, reusable correction-rule change, explicit resolution, staged row source fingerprint, or durable source-mapping fingerprint/target change must change the run review fingerprint.
4. Keep this fingerprint review/readiness metadata only. It must not authorize a global commit or imply accounting completeness.
5. Expose it through the read-only run-level review summary; mutate no run status, upload, staged row, rule, mapping, customer record or accounting record.
6. Preserve platform read authorization, organization/provider isolation and no-store behavior.
7. Add focused tests for deterministic replay and fingerprint changes across staged review, correction-rule and durable mapping changes while proving zero target/accounting mutation.
8. Keep AppFolio API transport, general UX, navigation and hidden-menu work out of scope.

---

# AI_HANDOFF.md — 2026-10-03 PHASE 4.13 REUSABLE CORRECTION RULES VERIFIED

## Current verified product checkpoint

- Phase 4.11 — Senior Housing: **COMPLETE | VERIFIED**.
- Phase 4.12 — Short-term Rentals: **COMPLETE | VERIFIED**.
- Phase 4.13 — AppFolio CSV/XLSX migration: **IN PROGRESS**.
- Verified PRODUCT SHA: `d9c9df635664d990170d7c84291f8a29d65193c8`.
- GitHub Actions run: `37158399721` — SUCCESS.
- All six required CI jobs passed:
  - frontend: PASS
  - backend: PASS
  - security: PASS
  - platform-admin: PASS
  - staging-config: PASS
  - authenticated E2E: PASS
- Backend/PostgreSQL: **976 passed, 21 deselected, 25563 warnings in 475.51s**.
- Authenticated E2E: **21 passed, 278 warnings in 75.33s**.
- Alembic head: `1b8d3f6a9c20`.
- Expected model tables: **202**.
- Navigation integrity and the `HIDDEN MENU / UNHIDE ROADMAP` remain unchanged.
- `docs/UX_STANDARDS.md` remains AUTHORIZED BUT NOT ACTIVE.

## Verified run-scoped reusable correction-rule scope

1. Reusable value-correction rules are persisted only inside one migration run and organization; they are never global cross-customer rules.
2. A rule binds the exact AppFolio provider + resource + safe descriptive field + normalized source value to one corrected value.
3. The same descriptive-field allowlist used by the verified row-correction layer remains authoritative; identities, relationship IDs, amounts, dates, statuses and accounting semantics are not generically corrected.
4. Original source evidence, upload fingerprints and row source fingerprints remain unchanged. Rule application affects only staged normalized overlays plus explicit correction evidence.
5. Rule creation/update is explicit, platform-write scoped and audited with actor/time.
6. Exact rule replay is idempotent. Conflicting rule updates are explicit, audited and invalidate the prior dry-run state.
7. Re-upload/replay in the same run applies the current exact matching rules deterministically; no fuzzy matching is used.
8. Active correction rules and staged correction evidence participate in the shared staged-review fingerprint, so changed rules make prior dry-run/commit readiness stale.
9. INVALID/unsafe rows are not made commit-safe by reusable rules.
10. The correction-rule lifecycle creates or updates zero existing customer Property/Unit/User/Vendor/Lease/Charge/Bill/WorkOrder/GL records and rewrites no source file.
11. The latest regression also supports the verified upload-object shape used by the shared review fingerprint without opening an AppFolio API transport path.
12. No general UX, navigation, hidden-menu or AppFolio API connector work was added.

Implementation commits after the prior correction-layer checkpoint:
- `8d88051689153529cc67c1becb8c41450e170132` through `84cc5ba85145ff95dc75b00c0c1cf803cf74f2e8` — correction-rule model, migration, schemas, API and initial tests.
- `4436af1b4db3134004a6a02c322a028c9ec9a7a7` through `661529276c9ee187524187a6f560995fb4168055` — run binding, explicit update lifecycle, deterministic application and lifecycle regressions.
- `041ae4b3a493d103704df1d78c439863041cf38e` — relationship mapping correction.
- `d9c9df635664d990170d7c84291f8a29d65193c8` — shared review-fingerprint upload-object compatibility; final VERIFIED PRODUCT SHA.

## Exact next Phase 4.13 product batch

Implement the shared **run-level migration review/readiness summary** required by section 10 of `docs/APPFOLIO_MIGRATION_IMPORT_PLAN.md`.

Required boundaries:

1. Aggregate only durable migration-run/upload/staged-row/mapping state already stored in the shared migration architecture.
2. Report run-level counts for new, possible matches, matched, already imported, skipped, invalid, review/unresolved rows, warnings and blocking errors, with resource-level breakdown.
3. Distinguish an explicit `MATCH_EXISTING` from relationship-only `ACCEPT_RELATIONSHIP`; do not claim accepted relationships are target records already matched/imported.
4. Surface the run's latest dry-run resource/fingerprint state and whether current staged-review fingerprints have made that state stale; do not manufacture a combined financial commit-ready claim.
5. Read-only analysis only: mutate no upload, staged row, correction rule, source mapping, customer record, accounting record or run status.
6. Preserve platform read authorization, organization/run scope and no-store behavior.
7. Add focused tests for mixed-resource counts, unresolved blockers, mapping/replay state, authorization and zero mutation.
8. Keep AppFolio API transport, general UX, navigation and hidden-menu work out of scope.

---

# AI_HANDOFF.md — 2026-10-03 PHASE 4.13 STAGED CORRECTION LAYER VERIFIED

## Current verified product checkpoint

- Phase 4.11 — Senior Housing: **COMPLETE | VERIFIED**.
- Phase 4.12 — Short-term Rentals: **COMPLETE | VERIFIED**.
- Phase 4.13 — AppFolio CSV/XLSX migration: **IN PROGRESS**.
- Verified PRODUCT SHA: `11eb9d0e9cff3ff5b16ca4884b9aa09ce7bf295c`.
- GitHub Actions run: `37151296381` — SUCCESS.
- All six required CI jobs passed:
  - frontend: PASS
  - backend: PASS
  - security: PASS
  - platform-admin: PASS
  - staging-config: PASS
  - authenticated E2E: PASS
- Backend/PostgreSQL: **972 passed, 21 deselected, 25482 warnings in 449.52s**.
- Authenticated E2E: **21 passed, 278 warnings in 112.76s**.
- Alembic head remains `0a7c4e9f2b61`.
- Expected model tables remain **201**.
- Navigation integrity and the `HIDDEN MENU / UNHIDE ROADMAP` remain unchanged.
- `docs/UX_STANDARDS.md` remains AUTHORIZED BUT NOT ACTIVE.

## Verified shared staged correction layer

1. A platform-write-scoped staged-row correction endpoint reuses the existing migration run/upload/staged-row architecture; no parallel migration system was added.
2. Generic corrections are intentionally restricted to allowlisted descriptive normalized staging fields per resource.
3. Stable source IDs, relationship IDs, amounts, dates, statuses, accounting classifications, payment/occupancy semantics and other resource-specific safety fields cannot be changed through the generic correction path.
4. INVALID/error rows cannot be made commit-safe through a generic correction.
5. The original upload `normalized_fingerprint`, staged-row `row_fingerprint` and durable source identity remain unchanged; correction modifies only the effective staged `normalized_data` overlay.
6. Every actual correction appends immutable audit history with prior/new value, platform actor/time and explicit no-source-file/no-customer/no-accounting-mutation flags.
7. Exact replay of the same correction is idempotent and does not duplicate audit history.
8. Any changed corrected normalized value clears the run's prior dry-run state and the shared staged-review fingerprint now binds `normalized_data`, so prior dry-run/commit-readiness state becomes stale automatically.
9. Corrections do not rewrite uploaded files or existing customer Property/Unit/User/Vendor/Lease/Charge/Bill/WorkOrder/GL records.
10. Focused regressions verify source preservation, fingerprint invalidation, replay/idempotency, role enforcement, identity-field rejection, INVALID-row rejection and zero customer/accounting mutation.
11. No AppFolio API transport, general UX, navigation or hidden-menu changes were added.

Implementation commits:
- `a7100e784f3733ea09ac623e9e8cb095f782af6a` — correction request contract.
- `6b11c774d9b73393e413a3572ee3140d5c307905` — staged correction endpoint and corrected-data fingerprint binding.
- `889129c7ef927ce8f8f8bca36d93dd5ae4b70c03` — focused correction safety regressions.
- `11eb9d0e9cff3ff5b16ca4884b9aa09ce7bf295c` — test-only audit JSON assertion correction; final VERIFIED PRODUCT SHA.

## Exact next Phase 4.13 product batch

Extend section 8 of `docs/APPFOLIO_MIGRATION_IMPORT_PLAN.md` with **run-scoped reusable value-correction rules** so an explicitly reviewed correction can be applied consistently to later staging/replay without editing source files row-by-row.

Required boundaries:

1. Reuse the same provider/run/upload/staged-row architecture and the existing safe descriptive-field allowlist.
2. Persist corrections as run-scoped provider/resource/field/source-value -> corrected-value rules with explicit actor/time; never global cross-customer rules.
3. Apply a reusable rule only to the exact same resource + field + normalized source value; never fuzzy-match or reinterpret identities, amounts, dates, statuses, relationship IDs or accounting semantics.
4. Preserve original source evidence and raw upload fingerprints. Rule application may affect only staged normalized overlays.
5. Conflicting rule changes must be explicit/audited, invalidate prior dry-run state and change the staged-review fingerprint.
6. Re-upload/replay must apply the current exact rule deterministically and remain idempotent.
7. Never mutate existing customer records or automatically make INVALID/unsafe rows commit-ready.
8. Add focused tests for run/org isolation, deterministic replay, conflicting-rule updates, fingerprint invalidation, authorization and zero target/accounting mutation.
9. Keep AppFolio API transport, general UX, navigation and hidden-menu work out of scope.

---

# AI_HANDOFF.md — 2026-10-03 PHASE 4.13 MIGRATION SOURCE COVERAGE CHECKLIST VERIFIED

## Current verified product checkpoint

- Phase 4.11 — Senior Housing: **COMPLETE | VERIFIED**.
- Phase 4.12 — Short-term Rentals: **COMPLETE | VERIFIED**.
- Phase 4.13 — AppFolio CSV/XLSX migration: **IN PROGRESS**.
- Verified PRODUCT SHA: `95649486557ab36531cc82b81085e8272c19adc0`.
- GitHub Actions run: `37136410778` — SUCCESS.
- All six required CI jobs passed:
  - frontend: PASS
  - backend: PASS
  - security: PASS
  - platform-admin: PASS
  - staging-config: PASS
  - authenticated E2E: PASS
- Backend/PostgreSQL: **970 passed, 21 deselected, 25458 warnings in 444.39s**.
- Authenticated E2E: **21 passed, 278 warnings in 112.72s**.
- Alembic head remains `0a7c4e9f2b61`.
- Expected model tables remain **201**.
- Navigation integrity and the `HIDDEN MENU / UNHIDE ROADMAP` remain unchanged.
- `docs/UX_STANDARDS.md` remains AUTHORIZED BUT NOT ACTIVE.

## Verified migration source coverage / completeness checklist

1. A read-only run-scoped coverage endpoint now reports the supported source families from durable AppFolio migration upload/mapping evidence only.
2. Coverage states distinguish `SUPPLIED`, `PARTIAL`, `MISSING` and `BLOCKED`; customer production records are never used to infer missing imports.
3. The checklist includes Properties, Units, Owners, Vendors, Tenants, Lease/occupancy, GL Accounts, General Ledger, Bills/payables, Charges/receivables, Security Deposits, Work Orders and Attachments/Documents.
4. Existing blockers are surfaced explicitly for Lease/occupancy controlled commit, historical GL controlled commit, Bills controlled commit, Charges controlled commit, Work Orders controlled commit, Security Deposit source-schema evidence and Attachments/Documents source-schema evidence.
5. `accounting_complete` fails closed unless every required accounting source family is under a supplied/verified commit-safe contract; partial operational coverage does not claim accounting completeness.
6. Coverage analysis is no-store/read-only and mutates no uploads, staged rows, mappings, customer records, balances or GL.
7. Platform organization/run scope and read-role authorization remain authoritative.
8. Focused tests cover partial coverage, blocked/missing states, accounting completeness fail-closed behavior, read-only replay and authorization.
9. No AppFolio API transport, general UX, navigation or hidden-menu changes were added.

## Exact next Phase 4.13 product batch

Implement the shared **migration-stage correction layer** from section 8 of `docs/APPFOLIO_MIGRATION_IMPORT_PLAN.md`.

Required boundaries:

1. Reuse the existing migration run/upload/staged-row architecture; do not build a parallel migration system.
2. A correction may change only an explicitly supported normalized staging field/value while preserving the original source value/evidence.
3. Record the correction decision, actor and timestamp durably and append-only/audited.
4. Corrections apply only to migration staging/review logic; never rewrite source files or existing production customer records.
5. A correction that changes normalized staged input must invalidate prior dry-run/commit-readiness state and participate in the exact staged-review fingerprint.
6. Replaying the identical correction must be idempotent; conflicting correction changes require a new fingerprint/dry run.
7. INVALID source identity or unsupported source/target semantics must not be made commit-safe by arbitrary correction.
8. Keep organization/run scope and platform-role authorization fail-closed.
9. Add focused tests for correction persistence, source preservation, fingerprint invalidation, replay/idempotency, authorization and zero customer/accounting mutation.
10. Do not add general UX, AppFolio API transport or hidden-menu/navigation changes.

---

# AI_HANDOFF.md — 2026-10-03 PHASE 4.13 WORK ORDERS STAGED DRY RUN VERIFIED

## Current verified product checkpoint

- Phase 4.11 — Senior Housing: **COMPLETE | VERIFIED**.
- Phase 4.12 — Short-term Rentals: **COMPLETE | VERIFIED**.
- Phase 4.13 — AppFolio CSV/XLSX migration: **IN PROGRESS**.
- Verified PRODUCT SHA: `978a8cdc07c9e33a416ba7b3472d3dd1437bc174`.
- GitHub Actions run: `37135155264` — SUCCESS.
- All six required CI jobs passed:
  - frontend: PASS
  - backend: PASS
  - security: PASS
  - platform-admin: PASS
  - staging-config: PASS
  - authenticated E2E: PASS
- Backend/PostgreSQL: **967 passed, 21 deselected, 25410 warnings in 436.53s**.
- Authenticated E2E: **21 passed, 278 warnings in 118.41s**.
- Alembic head remains `0a7c4e9f2b61`.
- Expected model tables remain **201**.
- Navigation integrity and the `HIDDEN MENU / UNHIDE ROADMAP` remain unchanged.
- `docs/UX_STANDARDS.md` remains AUTHORIZED BUT NOT ACTIVE.

## Verified Work Orders staged dry run

1. Dry run operates only on already-staged `WORK_ORDERS` rows.
2. Retained rows require stable Work Order source identity and explicit `ACCEPT_RELATIONSHIP`; `SKIP` rows are excluded and unresolved/INVALID rows block readiness.
3. Current durable Property plus any supplied Unit/Vendor mappings are revalidated to active same-organization targets and must still match the staged resolution snapshots.
4. Unit -> Property consistency is revalidated.
5. Dry-run fingerprint binds the shared staged-review fingerprint plus current mapping source fingerprints/target IDs for every accepted relation.
6. Source Id, PropertyId, UnitId, VendorId, AssignedUsers, Status, JobDescription, CanceledOn, CompletedOn, PermissionToEnter, Priority, ScheduledStart, ScheduledEnd and VendorTrade remain source evidence only.
7. No requester/tenant/occupancy identity, staff-assignment semantics, vendor contract, workflow-state translation, completion/cancellation meaning or accounting effects are inferred.
8. Empty accepted sets fail closed; exact replay is idempotent and audited once.
9. The batch creates or updates zero WorkOrder, Bill, Charge, GLTransaction, GLEntry, inventory, purchase-order, vendor-payment or staff-assignment records.
10. No AppFolio API transport, customer navigation change, hidden-menu change or general UX work was added.

Implementation commits:
- `1636bae3397782c4884b83118a67cf4520715075` — Work Order dry-run response contract.
- `93e8e95efea8320afe92bbddc93fb6c342a7bc74` — staged Work Order dry-run and mapping revalidation.
- `978a8cdc07c9e33a416ba7b3472d3dd1437bc174` — focused replay/staleness/blocking/non-mutation regressions; final VERIFIED PRODUCT SHA.
- `9bbe39caa617af52e4600afa399b9463a71b457e` — migration-plan documentation.

## Work Orders controlled-commit blocker

Controlled commit is intentionally blocked.

Target `WorkOrder` requires non-null `unit_id` and `tenant_id`. The verified AppFolio Work Orders source may omit UnitId and does not provide a verified tenant/requester identity contract. `AssignedUsers` cannot safely stand in for tenant/requester identity. Source Status/Priority values also remain source evidence and are not translated into target workflow enums.

Do not fabricate a tenant/requester, use a staff/platform user as a synthetic submitter, invent a Unit for property-only work, or guess workflow-state translations.

## Attachments/Documents source-schema check

Current public AppFolio material confirms document-management capabilities, but this review did not find an authoritative public AppFolio Stack CSV/XLSX or API field contract suitable for automatic Attachments/Documents migration mapping.

Therefore **Attachments/Documents automatic ingestion remains BLOCKED on source-schema evidence**. Do not invent attachment/document export columns, entity relationships, sharing state, folder semantics or file identity.

This resource-specific blocker does not block shared Phase 4.13 migration infrastructure.

## Exact next Phase 4.13 product batch

Implement the **migration source coverage/completeness checklist** required by section 6 of `docs/APPFOLIO_MIGRATION_IMPORT_PLAN.md`, using the existing migration run/upload records only.

Required boundaries:

1. Report which verified source families have been supplied to the run and which remain missing.
2. Distinguish supplied/partial/blocked states without claiming an accounting migration is complete merely because some operational resources exist.
3. Derive coverage only from durable migration uploads/mappings and verified resource contracts; never infer missing reports from customer production records.
4. Expose blockers already recorded for Security Deposits, Charges controlled commit, Bills controlled commit, Work Orders controlled commit and Attachments/Documents source schema without fabricating completion.
5. Read-only coverage analysis only: no customer record, staged row, mapping, GL, balance or source file mutation.
6. Organization/run scope and platform-role authorization must remain authoritative.
7. Add focused tests for partial coverage, replay/read-only behavior and accounting-completeness fail-closed semantics.
8. Do not add general UX, AppFolio API transport or hidden-menu/navigation changes in this batch.

---

# AI_HANDOFF.md — 2026-10-03 PHASE 4.13 WORK ORDERS RELATIONSHIP RECONCILIATION VERIFIED

## Current verified product checkpoint

- Phase 4.11 — Senior Housing: **COMPLETE | VERIFIED**.
- Phase 4.12 — Short-term Rentals: **COMPLETE | VERIFIED**.
- Phase 4.13 — AppFolio CSV/XLSX migration: **IN PROGRESS**.
- Verified PRODUCT SHA: `357653e915d2da4eb7813c14f0de80304e1993ab`.
- GitHub Actions run: `37110817034` — SUCCESS.
- All six required CI jobs passed:
  - frontend: PASS
  - backend: PASS
  - security: PASS
  - platform-admin: PASS
  - staging-config: PASS
  - authenticated E2E: PASS
- Backend/PostgreSQL: **964 passed, 21 deselected, 25336 warnings in 407.92s**.
- Authenticated E2E: **21 passed, 278 warnings in 100.19s**.
- Alembic head remains `0a7c4e9f2b61`.
- Expected model tables remain **201**.
- Navigation integrity and the `HIDDEN MENU / UNHIDE ROADMAP` remain unchanged.
- `docs/UX_STANDARDS.md` remains AUTHORIZED BUT NOT ACTIVE.

## Verified Work Orders staged relationship reconciliation

1. Reconciliation operates only on already-staged `WORK_ORDERS` rows.
2. Rows without stable supplied Work Order identity may only be `SKIP`ped; INVALID rows cannot be resolved.
3. `ACCEPT_RELATIONSHIP` revalidates every supplied PropertyId/UnitId/VendorId through current durable migration mappings to active same-organization targets.
4. Unit -> Property consistency is revalidated at review time.
5. Accepted review state snapshots only verified target Property/Unit/Vendor IDs on the staged row.
6. AssignedUsers, workflow status, priority, schedule/completion/cancellation, permission-to-enter and VendorTrade remain source evidence only.
7. Resolution changes invalidate prior dry-run state, participate in the shared staged-review fingerprint and are append-only audited.
8. Exact replay of the same resolution is idempotent.
9. The batch creates or updates zero WorkOrder, Bill, Charge, GLTransaction, GLEntry, inventory, purchase-order or vendor-payment records.
10. No AppFolio API transport, customer navigation change, hidden-menu change or general UX work was added.

## Exact next Phase 4.13 product batch

Add **Work Orders staged dry run only** using the existing exact-fingerprint staged-review architecture.

Required boundaries:

1. Operate only on already-staged `WORK_ORDERS` rows.
2. Include only explicit `ACCEPT_RELATIONSHIP` rows with stable Work Order source ID; `SKIP` rows remain excluded and unresolved/INVALID rows block readiness.
3. Revalidate current durable Property mapping plus optional Unit/Vendor mappings and require snapped target IDs to still match active same-organization targets.
4. Revalidate Unit -> Property consistency.
5. Preserve Id, PropertyId, UnitId, VendorId, AssignedUsers, Status, JobDescription, CanceledOn, CompletedOn, PermissionToEnter, Priority, ScheduledStart, ScheduledEnd and VendorTrade as source evidence only.
6. Bind the dry-run fingerprint to the shared staged-review fingerprint plus current mapping source fingerprints/target IDs for every accepted relation.
7. Do not create or update WorkOrder, Bill, Charge, GL, inventory, purchase-order, vendor-payment or staff-assignment records.
8. Do not infer requester/tenant/occupancy identity, assignment semantics, vendor contract, workflow-state translation, completion/cancellation meaning or accounting effects.
9. A dry run containing no accepted Work Order rows is not commit-ready.
10. Exact replay must be idempotent and audited once.
11. Work Orders controlled commit remains a separate later verified dependency; AppFolio API transport and general UX remain out of scope.

---

# AI_HANDOFF.md — 2026-10-03 PHASE 4.13 WORK ORDERS STAGING VERIFIED

## Current verified product checkpoint

- Phase 4.11 — Senior Housing: **COMPLETE | VERIFIED**.
- Phase 4.12 — Short-term Rentals: **COMPLETE | VERIFIED**.
- Phase 4.13 — AppFolio CSV/XLSX migration: **IN PROGRESS**.
- Verified PRODUCT SHA: `e9d6aba390d3756cb2481a937b6b0ff4a41d3d14`.
- GitHub Actions run: `37109939688` — SUCCESS.
- All six required CI jobs passed:
  - frontend: PASS
  - backend: PASS
  - security: PASS
  - platform-admin: PASS
  - staging-config: PASS
  - authenticated E2E: PASS
- Backend/PostgreSQL: **961 passed, 21 deselected, 25267 warnings in 389.12s**.
- Authenticated E2E: **21 passed, 278 warnings in 115.60s**.
- Alembic head remains `0a7c4e9f2b61`.
- Expected model tables remain **201**.
- Navigation integrity and the `HIDDEN MENU / UNHIDE ROADMAP` remain unchanged.
- `docs/UX_STANDARDS.md` remains AUTHORIZED BUT NOT ACTIVE.

## Verified Work Orders CSV/XLSX ingestion + staging

1. Shared ingestion now supports `WORK_ORDERS` using only the verified public AppFolio Stack Work Orders field inventory.
2. Automatic detection requires stable source Work Order `Id` plus `PropertyId`, `Status` and `JobDescription`.
3. Explicit-resource files missing source Work Order ID may stage for REVIEW/SKIP only; no identity is synthesized.
4. Duplicate supplied Work Order IDs fail closed.
5. PropertyId, UnitId and VendorId relationships are checked only through existing durable migration mappings and active same-organization targets.
6. Mapped Unit -> Property consistency is enforced.
7. AssignedUsers, status, priority, scheduled/completed/canceled timestamps, permission-to-enter and VendorTrade remain source evidence only.
8. Valid rows remain REVIEW-only; no target maintenance workflow translation occurs.
9. CSV/XLSX replay remains normalized-fingerprint idempotent and raw file bytes are not persisted.
10. The batch creates/updates zero WorkOrder, Bill, Charge, GLTransaction, GLEntry, inventory, purchase-order, vendor-payment or accounting-balance records.
11. No AppFolio API transport, customer navigation change, hidden-menu change or general UX work was added.
12. First exact-SHA CI run `37109486472` found one focused test-only count mismatch; `e9d6aba390d3756cb2481a937b6b0ff4a41d3d14` corrected the assertion without changing product behavior.

Implementation commits:
- `1f24d57f8dcfb30ca0aa7334ee50044d179766a8` — shared Work Orders staging contract.
- `f9c27843899a0594c241c0569228d3b2458a1784` — focused CSV/XLSX/replay/safety regressions.
- `e9d6aba390d3756cb2481a937b6b0ff4a41d3d14` — focused test expectation correction; final VERIFIED PRODUCT SHA.
- `b5c27e47d4f3a288158e69c1a78b60b83a68a77c` — migration-plan documentation.

## Exact next Phase 4.13 product batch

Add **staged Work Orders relationship reconciliation only** using the existing staged-row resolution/fingerprint/audit architecture.

Required boundaries:

1. Reconcile only already-staged `WORK_ORDERS` rows; never accept arbitrary Work Order payloads.
2. Rows without stable source Work Order `Id` may only be `SKIP`ped.
3. Add explicit `ACCEPT_RELATIONSHIP` only when every supplied PropertyId/UnitId/VendorId relation is revalidated through current durable mappings to active same-organization targets.
4. Revalidate Unit -> Property consistency.
5. Snapshot only verified target Property/Unit/Vendor IDs on the staged row; do not create WorkOrder or staff-assignment records.
6. AssignedUsers, workflow status, priority, schedule/completion/cancellation, permission-to-enter and VendorTrade remain source evidence only.
7. Resolution changes must invalidate prior dry-run state, participate in the shared staged-review fingerprint and be append-only audited.
8. Exact replay must be idempotent.
9. INVALID rows remain non-resolvable; safe REVIEW rows may be explicitly SKIPped.
10. Create/update zero WorkOrder, Bill, Charge, GL, inventory, purchase-order or vendor-payment records.
11. Do not implement Work Orders dry-run/controlled commit, AppFolio API transport or general UX work in this batch.

---

# AI_HANDOFF.md — 2026-10-03 PHASE 4.13 CHARGES STAGED DRY RUN VERIFIED

## Current verified product checkpoint

- Phase 4.11 — Senior Housing: **COMPLETE | VERIFIED**.
- Phase 4.12 — Short-term Rentals: **COMPLETE | VERIFIED**.
- Phase 4.13 — AppFolio CSV/XLSX migration: **IN PROGRESS**.
- Verified PRODUCT SHA: `ce41780f9250d9347367bb118f8ab197d80a0dd2`.
- GitHub Actions run: `37099508230` — SUCCESS.
- All six required CI jobs passed:
  - frontend: PASS
  - backend: PASS
  - security: PASS
  - platform-admin: PASS
  - staging-config: PASS
  - authenticated E2E: PASS
- Backend/PostgreSQL: **958 passed, 21 deselected, 25204 warnings in 409.27s**.
- Authenticated E2E: **21 passed, 278 warnings in 115.26s**.
- Alembic head remains `0a7c4e9f2b61`.
- Expected model tables remain **201**.
- Navigation integrity and the `HIDDEN MENU / UNHIDE ROADMAP` remain unchanged.
- `docs/UX_STANDARDS.md` remains AUTHORIZED BUT NOT ACTIVE.

## Verified Charges / Receivables staged dry run

1. Dry run operates only on already-staged `CHARGES` rows.
2. Retained rows require stable supplied Charge ID plus explicit `ACCEPT_RELATIONSHIP`; `SKIP` rows are excluded and unresolved/INVALID rows block the dry run.
3. The accepted `GlAccountId` relationship is revalidated against the current durable `GL_ACCOUNTS -> GL_ACCOUNT` mapping and active same-organization target.
4. Dry-run fingerprint binds the shared staged-review fingerprint plus current GL Account mapping source fingerprint and target ID, so either staged review changes or durable mapping changes produce a new fingerprint.
5. Preview preserves only supplied source evidence: `AmountDue`, `ChargedOn`, `Description`, `GlAccountId`, `OccupancyId`.
6. Resolved target output contains only the verified GL Account target. `OccupancyId` remains source evidence only and is not converted into Tenant/Lease/Unit/Property identity.
7. Empty accepted sets are not dry-run ready.
8. Exact replay is idempotent and does not duplicate dry-run audit activity.
9. The batch creates or updates zero Charge, RentInvoice, Receipt, Payment, GLTransaction, GLEntry or customer balance records.
10. No original charge amount, amount paid, paid/unpaid state, rent-vs-charge classification, payment application, tenant liability, target Occupancy identity, GL posting or historical reconciliation is inferred.
11. No AppFolio API transport, customer navigation change, hidden-menu change or general UX work was added.

Implementation commits:
- `5374e0e7f58692341b67a245a89fd182c807f765` — Charges dry-run response contract.
- `d7ee0fc561d44dd989137fcea68f7334e2aa17f7` — staged Charges dry-run and exact-fingerprint state.
- `83dee2a6b483ef176da891e60f9a6c3db2aeb2fb` — replay/mapping-staleness/blocking regressions.
- `ce41780f9250d9347367bb118f8ab197d80a0dd2` — documented dry-run and controlled-commit blocker; final VERIFIED PRODUCT SHA.

## Charges controlled-commit blocker

Controlled commit remains intentionally blocked.

Target `Charge` requires a real tenant identity and original billed amount. The verified AppFolio Charges source contract provides only `OccupancyId` plus current `AmountDue`. There is no separately verified durable Occupancy-to-target identity contract, and `AmountDue` cannot establish original amount or `amount_paid`. Creating a target Charge from those fields would fabricate tenant liability/payment history.

Do not synthesize tenant identity, property/unit association, original charge amount, amount paid, paid state or GL posting semantics.

## Security Deposit source-schema check

A public-source check was performed before adding any Security Deposit ingestion aliases.

- AppFolio's current public Stack API lists Charges, Tenant Ledgers, Rental Applications and other resources, but no standalone Security Deposit / Security Deposit Funds Detail API resource with a published field contract.
- Tenant Ledgers expose only a nested `Ledger` plus `OccupancyId` at the public contract level.
- Rental Application `Deposit` is an application/listing deposit field and is not proof of security-deposit funds held, ledger liability, receipt/payment history or refund state.
- Public material acknowledges security-deposit workflows, but no authoritative CSV/XLSX column contract for the Security Deposit Funds Detail report was found.

Therefore **Security Deposit CSV/XLSX automatic detection/staging is BLOCKED on source-schema evidence**. Do not invent report columns or map generic deposit amounts into held-funds/accounting history.

This blocker does not block Phase 4.13 overall.

## Exact next Phase 4.13 product batch

Proceed to the next independently safe resource with an authoritative public source contract: **Work Orders CSV/XLSX source-schema verification and shared staging support**.

Use the existing shared migration upload/detect/map/stage/validate/review architecture. The current public AppFolio source contract exposes Work Order fields including `Id`, `PropertyId`, `UnitId`, `Status`, `JobDescription`, `AssignedUsers`, `CanceledOn`, `CompletedOn`, `PermissionToEnter`, `Priority`, `ScheduledStart`, `ScheduledEnd`, `VendorId` and `VendorTrade`.

Required boundaries for the next batch:

1. Verify exact source aliases against authoritative public AppFolio evidence before coding.
2. Require a stable supplied Work Order ID for automatic identity; explicit-resource missing-ID rows may be REVIEW/SKIP only, never assigned synthetic IDs.
3. Preserve PropertyId, UnitId, VendorId and AssignedUsers as source relationship evidence unless an already durable migration mapping safely resolves that specific relation.
4. Do not infer Occupancy, tenant, requester, maintenance assignment, vendor contract, completion/cancellation semantics beyond supplied fields.
5. Stage only; do not create/update target WorkOrder records in this batch.
6. Preserve status/priority/schedule/completion/cancellation/permission-to-enter exactly as source evidence; do not translate workflow state until separately verified.
7. Duplicate supplied Work Order IDs must fail closed.
8. No Bill, Charge, GL, inventory, purchase-order, vendor-payment or accounting mutation.
9. Keep raw file content out of durable storage; preserve normalized fingerprints/replay/idempotency/audit behavior.
10. AppFolio API transport and general UX remain out of scope.

---

# AI_HANDOFF.md — 2026-10-03 PHASE 4.13 CHARGES RELATIONSHIP RECONCILIATION VERIFIED

## Current verified product checkpoint

- Phase 4.11 — Senior Housing: **COMPLETE | VERIFIED**.
- Phase 4.12 — Short-term Rentals: **COMPLETE | VERIFIED**.
- Phase 4.13 — AppFolio CSV/XLSX migration: **IN PROGRESS**.
- Verified PRODUCT SHA: `0bfb6794b4388a7cbf944fe10aed778a6222cae7`.
- GitHub Actions run: `37098864919` — SUCCESS.
- All six required CI jobs passed:
  - frontend: PASS
  - backend: PASS
  - security: PASS
  - platform-admin: PASS
  - staging-config: PASS
  - authenticated E2E: PASS
- Backend/PostgreSQL: **955 passed, 21 deselected, 25131 warnings in 231.73s**.
- Authenticated E2E: **21 passed, 278 warnings in 117.72s**.
- Alembic head remains `0a7c4e9f2b61`.
- Expected model tables remain **201**.
- Navigation integrity and the `HIDDEN MENU / UNHIDE ROADMAP` remain unchanged.
- `docs/UX_STANDARDS.md` remains AUTHORIZED BUT NOT ACTIVE.

## Verified Charges / Receivables staged reconciliation

1. Reconciliation operates only on already-staged `CHARGES` rows.
2. Allowed actions are `ACCEPT_RELATIONSHIP` or `SKIP`; rows without stable supplied Charge identity may only be skipped and INVALID rows cannot be resolved.
3. `ACCEPT_RELATIONSHIP` revalidates the supplied `GlAccountId` through the existing durable `GL_ACCOUNTS -> GL_ACCOUNT` mapping and requires the target GL Account to remain active in the same organization.
4. The accepted staged state snapshots only the typed target GL Account ID. Occupancy remains source evidence only; no Tenant, Lease, Unit, Property or payer/liability relationship is inferred.
5. Resolution changes invalidate prior dry-run state, participate in the shared staged-review fingerprint and are append-only audited.
6. Repeating an identical accepted resolution is idempotent and does not duplicate audit activity.
7. The batch creates or updates zero Charge, RentInvoice, Receipt, Payment, GLTransaction, GLEntry or customer balance records.
8. No paid/unpaid state, original amount, amount paid, rent-vs-charge classification, payment application, tenant liability, GL posting or historical reconciliation is inferred.
9. No AppFolio API transport, navigation change or general UX work was added.
10. Initial CI run `37098492141` exposed one focused test-only defect: AuditLog.new_value is stored as JSON text. Commit `0bfb6794b4388a7cbf944fe10aed778a6222cae7` corrected the assertion by parsing the immutable JSON text; product reconciliation behavior was unchanged.

Implementation commits:
- `80baa351489f6d6dcfa418af022269a381260efb` — Charges relationship-resolution schema.
- `4cd2c418fd15c3bbea92678fc15e02422d818946` — scoped Charges staged relationship resolver.
- `ef7f5dd7b83d3eb9b551cb6bddfc96f6f6b8de45` — reconciliation/idempotency/scope regressions.
- `8324be2dbf841af7f2de82a46392b28f5b2bf680` — migration-plan reconciliation contract.
- `0bfb6794b4388a7cbf944fe10aed778a6222cae7` — test-only audit assertion correction; final VERIFIED PRODUCT SHA.

## Exact next Phase 4.13 product batch

Add **Charges staged dry-run only** using the existing exact-fingerprint staged-review architecture.

Required boundaries:

1. Operate only on already-staged `CHARGES` rows.
2. Include only explicit `ACCEPT_RELATIONSHIP` rows with stable Charge source ID; SKIP rows remain excluded and unresolved/INVALID rows block readiness.
3. Revalidate current durable GL Account mapping and require the snapped typed target GL Account ID to still match.
4. Preserve `AmountDue`, `ChargedOn`, `Description`, `GlAccountId` and `OccupancyId` as source evidence only.
5. Bind the dry-run fingerprint to the shared staged-review fingerprint plus current GL Account mapping source fingerprint/target ID.
6. Do not create or update Charge, RentInvoice, Receipt, Payment, GLTransaction, GLEntry or customer balances.
7. Do not infer original amount, amount paid, paid/unpaid state, rent-vs-charge classification, payment application, tenant liability, Occupancy target identity, GL posting or historical reconciliation.
8. A dry run containing no accepted Charge rows is not commit-ready.
9. Repeating an identical dry run must be idempotent and audited once.
10. Charges controlled commit remains a separate later verified dependency; AppFolio API transport and general UX remain out of scope.

---

# AI_HANDOFF.md — 2026-10-03 PHASE 4.13 BILLS STAGED DRY RUN VERIFIED

## Current verified product checkpoint

- Phase 4.11 — Senior Housing: **COMPLETE | VERIFIED**.
- Phase 4.12 — Short-term Rentals: **COMPLETE | VERIFIED**.
- Phase 4.13 — AppFolio CSV/XLSX migration: **IN PROGRESS**.
- Verified PRODUCT SHA: `ab8a1b46c5211c4ca87df6a0be088e78b6ae1564`.
- GitHub Actions run: `37095170716` — SUCCESS.
- All six required CI jobs passed:
  - frontend: PASS
  - backend: PASS
  - security: PASS
  - platform-admin: PASS
  - staging-config: PASS
  - authenticated E2E: PASS
- Backend/PostgreSQL: **949 passed, 21 deselected, 25017 warnings in 431.74s**.
- Authenticated E2E: **21 passed, 278 warnings in 115.22s**.
- Alembic head remains `0a7c4e9f2b61`.
- Expected model tables remain **201**.
- Navigation integrity and the `HIDDEN MENU / UNHIDE ROADMAP` remain unchanged.
- `docs/UX_STANDARDS.md` remains AUTHORIZED BUT NOT ACTIVE.

## Verified Bills staged dry run

1. Dry run operates only on already-staged `BILLS` rows.
2. Only explicit `ACCEPT_RELATIONSHIP` rows with stable Bill source ID participate; SKIP rows are excluded and unresolved/INVALID rows block readiness.
3. Current durable Vendor and optional Property mappings are revalidated to active same-organization targets and must still match the snapped typed target IDs.
4. Dry-run fingerprint binds the shared staged-review fingerprint plus current Vendor/Property mapping source fingerprints and target IDs.
5. Due/invoice/posting dates, reference, remarks, TotalAmount, ApprovalStatus, CheckMemo, AccountNumber, ManagementCompanyAsPayee, WorkOrderId and LastUpdatedAt remain source evidence only.
6. No approval, paid/unpaid state, check/payment linkage, GL allocation, Work Order linkage or posting semantics are inferred.
7. Identical dry-run replay is idempotent and audited once; mapping-fingerprint changes produce a new dry-run fingerprint and stale/invalid relationships fail closed.
8. The batch creates or updates zero Bill, BillLine, Check, Vendor, WorkOrder, GLTransaction, GLEntry, Charge or accounting-balance records.
9. No AppFolio API transport, navigation change or general UX work was added.

Implementation commits:
- `2258047b98e5ba4e8863f12aefebc11cad6723b0` — Bills dry-run response schema.
- `4456a51c98360183ae15f613dc9345903e90f84c` — exact Bills staged/mapping revalidation and dry-run route.
- `ab8a1b46c5211c4ca87df6a0be088e78b6ae1564` — idempotency/staleness/non-mutation regressions; final VERIFIED PRODUCT SHA.

## Bills controlled-commit dependency

A target Bill cannot yet be safely created from this verified top-level source contract:

- target `Bill` creation requires at least one explicit `BillLine` with a verified GL Account allocation;
- the verified top-level Bills source contract intentionally does not flatten or infer structured line items;
- target posting requires a deterministic Bill business date and central GL posting semantics; DueDate/InvoiceDate/PostingDate are preserved source evidence and are not interchangeable by assumption;
- target `post_bill()` creates an accrual GL transaction immediately, so creating a Bill without verified source line allocations/date semantics would fabricate accounting history.

Therefore **Bills controlled commit remains blocked on a separately verified source line-item/accounting contract**. Do not synthesize BillLine rows, GL accounts, payable/cash accounts, bill dates, payment status, or balancing entries.

## Exact next Phase 4.13 product batch

Proceed to the next independently safe accounting resource: **Charges / Receivables CSV/XLSX source-schema verification and staging support**, using the same shared migration architecture.

Required boundaries:

1. Verify an authoritative AppFolio source/export contract before adding automatic aliases.
2. Reuse existing upload, detection, mapping, staging, validation, fingerprint, replay/idempotency, audit and recovery architecture.
3. Preserve supplied stable source Charge/Receivable identity only; never synthesize identity from tenant/name/property/amount/date.
4. Preserve source amount/date/description/status/reference and relationship IDs as evidence only unless the verified source contract proves their exact meaning.
5. Relationship resolution may only use existing durable source mappings to active same-organization targets.
6. First Charges/Receivables batch is staging only: create/update zero Charge, RentInvoice, Receipt, Payment, GLTransaction, GLEntry or customer balances.
7. Do not infer paid/unpaid balance, rent-vs-charge classification, payer liability, GL posting, payment application or historical reconciliation.
8. If no reliable source schema is available, record that resource-specific blocker and move to the next independently safe resource rather than inventing fields.
9. AppFolio API transport and general UX remain out of scope.

---

# AI_HANDOFF.md — 2026-10-03 PHASE 4.13 BILLS RELATIONSHIP RECONCILIATION VERIFIED

## Current verified product checkpoint

- Phase 4.11 — Senior Housing: **COMPLETE | VERIFIED**.
- Phase 4.12 — Short-term Rentals: **COMPLETE | VERIFIED**.
- Phase 4.13 — AppFolio CSV/XLSX migration: **IN PROGRESS**.
- Verified PRODUCT SHA: `d8a87958dfd363e73343401fb89a8efb183be834`.
- GitHub Actions run: `37093216499` — SUCCESS.
- All six required CI jobs passed:
  - frontend: PASS
  - backend: PASS
  - security: PASS
  - platform-admin: PASS
  - staging-config: PASS
  - authenticated E2E: PASS
- Backend/PostgreSQL: **946 passed, 21 deselected, 24954 warnings in 420.68s**.
- Authenticated E2E: **21 passed, 278 warnings in 110.28s**.
- Alembic head remains `0a7c4e9f2b61`.
- Expected model tables remain **201**.
- Navigation integrity and the `HIDDEN MENU / UNHIDE ROADMAP` remain unchanged.
- `docs/UX_STANDARDS.md` remains AUTHORIZED BUT NOT ACTIVE.

## Verified staged Bills relationship reconciliation

1. Resolution operates only on already-staged `BILLS` rows.
2. `ACCEPT_RELATIONSHIP` requires a supplied stable Bill source ID; rows without Bill ID may only be explicitly SKIPped.
3. Source Vendor identity is revalidated only through the durable `VENDORS -> VENDOR` mapping and an active same-organization Vendor.
4. A supplied PropertyId is revalidated only through the durable `PROPERTIES -> PROPERTY` mapping and an active same-organization Property.
5. Accepted review state snapshots only the already-verified typed target Vendor and optional Property IDs on the staged row.
6. INVALID rows remain non-resolvable; unresolved REVIEW rows may be explicitly SKIPped.
7. Resolution changes participate in the shared staged-review fingerprint and invalidate prior dry-run state.
8. Repeating the identical accepted resolution is idempotent and does not duplicate audit activity.
9. The batch creates or updates zero Bill, BillLine, Check, Vendor, WorkOrder, GLTransaction, GLEntry, Charge or accounting-balance records.
10. No AppFolio API transport, navigation change or general UX work was added.

Implementation commits:
- `c84e62c00bf4902c6a53b07a8486f0a4510a8125` — Bills relationship-resolution schema.
- `e408446b222fb59f4df9a3536a8beae9620e3c44` — staged Bills relationship resolver.
- `d8a87958dfd363e73343401fb89a8efb183be834` — focused reconciliation/idempotency/scope regressions; final VERIFIED PRODUCT SHA.

## Exact next Phase 4.13 product batch

Add **Bills staged dry-run only** using the existing exact-fingerprint staged-review architecture.

Required boundaries:

1. Operate only on already-staged `BILLS` rows.
2. Include only explicit `ACCEPT_RELATIONSHIP` rows with stable Bill source ID; SKIP rows remain excluded and unresolved/INVALID rows block readiness.
3. Revalidate current durable Vendor and optional Property mappings and require the snapped typed target IDs to still match.
4. Preserve due/invoice/posting dates, reference, remarks, TotalAmount, ApprovalStatus, CheckMemo, AccountNumber, ManagementCompanyAsPayee, WorkOrderId and LastUpdatedAt as source evidence only.
5. Do not create or update Bill, BillLine, Check, Vendor, WorkOrder, GLTransaction, GLEntry, Charge, AP balance or payment state.
6. Do not infer approval, paid/unpaid status, check/payment linkage, GL account/line-item allocation, Work Order linkage or posting semantics.
7. Dry-run output must bind the shared staged-review fingerprint plus current durable relationship mapping fingerprints/target IDs.
8. A dry run containing no accepted Bill rows is not commit-ready.
9. Repeating an identical dry run must be idempotent and audited once.
10. Bills controlled commit remains a separate later verified batch; AppFolio API transport and general UX remain out of scope.

---

# AI_HANDOFF.md — 2026-10-03 PHASE 4.13 BILLS CSV/XLSX STAGING VERIFIED

## Current verified product checkpoint

- Phase 4.11 — Senior Housing: **COMPLETE | VERIFIED**.
- Phase 4.12 — Short-term Rentals: **COMPLETE | VERIFIED**.
- Phase 4.13 — AppFolio CSV/XLSX migration: **IN PROGRESS**.
- Bills staging product/test SHA: `9158009acdb5dfdba9c409a034e61890841ac1a0`.
- Exact green checkpoint SHA: `86b7c2cf38219a67edc67b60230acb591fa2b903`.
- GitHub Actions run: `37092441697` — SUCCESS.
- All six required CI jobs passed:
  - frontend: PASS
  - backend: PASS
  - security: PASS
  - platform-admin: PASS
  - staging-config: PASS
  - authenticated E2E: PASS
- Backend/PostgreSQL: **943 passed, 21 deselected, 24903 warnings in 262.49s**.
- Authenticated E2E: **21 passed, 278 warnings in 112.78s**.
- Alembic head remains `0a7c4e9f2b61`.
- Expected model tables remain **201**.
- Navigation integrity and the `HIDDEN MENU / UNHIDE ROADMAP` remain unchanged.
- `docs/UX_STANDARDS.md` remains AUTHORIZED BUT NOT ACTIVE.

## Verified Bills / Payables CSV/XLSX staging

1. Shared AppFolio CSV/XLSX ingestion now supports explicit/auto-detected `BILLS` top-level source records.
2. Automatic detection requires a stable supplied Bill ID plus VendorId, DueDate and TotalAmount. Explicit BILLS staging may preserve a missing Bill ID for REVIEW/SKIP but never synthesizes identity.
3. Top-level source fields are preserved as source evidence only: Bill ID, VendorId, PropertyId, due/invoice/posting dates, reference, remarks, TotalAmount, ApprovalStatus, CheckMemo, AccountNumber, ManagementCompanyAsPayee, WorkOrderId and LastUpdatedAt when supplied.
4. Vendor relationship is considered resolved only through the existing durable `VENDORS -> VENDOR` source mapping and an active same-organization Vendor.
5. Optional Property relationship is considered resolved only through the durable `PROPERTIES -> PROPERTY` mapping and an active same-organization Property.
6. Duplicate supplied Bill IDs within one staged upload fail closed.
7. TotalAmount must be numeric/nonnegative source evidence; no paid/unpaid, approval, check/payment, AP, GL posting or accounting state is inferred.
8. WorkOrderId remains source evidence only; no Work Order relationship is inferred without a durable migration mapping.
9. Upload/parser staging creates or updates zero Bill, BillLine, Check, Vendor, WorkOrder, GLTransaction, GLEntry, Charge or accounting-balance records.
10. CSV/XLSX replay remains normalized-fingerprint idempotent and XLSX source cell representation is preserved rather than silently retyped.
11. Initial CI run `37065183863` exposed two focused test expectation defects; scoped correction `9158009acdb5dfdba9c409a034e61890841ac1a0` aligned assertions with the verified staging contract.
12. During verification, GitHub published high-severity `GHSA-vfj7-8cjw-p6xm` for the dev-only `braces` package with no patched npm release. Checkpoint `86b7c2cf38219a67edc67b60230acb591fa2b903` preserves high/critical npm auditing and allows only that exact advisory when every affected package node is dev-only; all other high/critical findings still fail CI.

## Exact next Phase 4.13 product batch

Add **staged Bills relationship reconciliation only** using the existing staged-row review/fingerprint/audit architecture.

Required boundaries:

1. Reconcile only already-staged `BILLS` rows; never accept arbitrary Bill payloads.
2. `ACCEPT_RELATIONSHIP` requires a supplied stable Bill source ID. Rows without Bill ID may only remain REVIEW or be explicitly `SKIP`ped.
3. Revalidate the current durable Vendor source mapping to an active same-organization Vendor before acceptance.
4. If PropertyId is supplied, revalidate its durable mapping to an active same-organization Property before acceptance.
5. Snapshot only the already-verified typed target Vendor/Property IDs on the staged row; do not create Bill/accounting records.
6. INVALID rows remain non-resolvable; unresolved REVIEW rows may be explicitly SKIPped.
7. Resolution changes must be audited, participate in the shared staged-review fingerprint and invalidate prior dry-run state.
8. Repeating an identical accepted resolution must be idempotent.
9. Create/update zero Bill, BillLine, Check, Vendor, WorkOrder, GLTransaction, GLEntry, Charge or accounting-balance records.
10. Bills dry-run/controlled commit remain separate later verified batches. AppFolio API transport and general UX remain out of scope.

---

# AI_HANDOFF.md — 2026-10-02 PHASE 4.13 GENERAL LEDGER COMMIT-READINESS VERIFIED

## Current verified product checkpoint

- Phase 4.11 — Senior Housing: **COMPLETE | VERIFIED**.
- Phase 4.12 — Short-term Rentals: **COMPLETE | VERIFIED**.
- Phase 4.13 — AppFolio CSV/XLSX migration: **IN PROGRESS**.
- Verified PRODUCT SHA: `391ade053318218e20e088eb6b8752ed09986c09`.
- GitHub Actions run: `37063743424` — SUCCESS.
- All six required CI jobs passed:
  - frontend: PASS
  - backend: PASS
  - security: PASS
  - platform-admin: PASS
  - staging-config: PASS
  - authenticated E2E: PASS
- Backend/PostgreSQL: **940 passed, 21 deselected, 24856 warnings in 225.33s**.
- Authenticated E2E: **21 passed, 278 warnings in 92.22s**.
- Alembic head remains `0a7c4e9f2b61`.
- Expected model tables remain **201**.
- Navigation integrity and the `HIDDEN MENU / UNHIDE ROADMAP` remain unchanged.
- `docs/UX_STANDARDS.md` remains AUTHORIZED BUT NOT ACTIVE.

## Verified General Ledger accounting-history commit-readiness

1. Readiness analysis consumes only the exact accepted staged rows behind the latest successful General Ledger dry-run fingerprint.
2. Source rows are grouped only by supplied stable `TransactionId`; missing transaction IDs fail closed.
3. Every retained transaction group must balance exactly from supplied source debit/credit evidence; unbalanced groups fail closed.
4. Already-verified active same-organization GL Account and any supplied Property/Unit relationships remain required through the dry-run revalidation path.
5. The readiness fingerprint binds the exact dry-run fingerprint plus deterministic transaction-group composition and source evidence.
6. Identical readiness replay is idempotent and audited once.
7. The batch does not fabricate balancing entries, opening balances, target transaction types, payer/payee identity, references or posting semantics.
8. The batch creates or updates zero GLTransaction, GLEntry, journal entry, Receipt, Bill, Charge, GLAccount, AccountingKeyAccount or balance records.

Implementation commits:
- `2c510beaa59ff9a2ddeb5506c9d30d227cff4fbd` — commit-readiness response schema.
- `814eb34b102457eb0075eb0355b3285d8a2862a6` — balanced source-transaction readiness analysis.
- `391ade053318218e20e088eb6b8752ed09986c09` — focused grouping/idempotency/fail-closed regressions; final VERIFIED PRODUCT SHA.

## Exact next Phase 4.13 product dependency

Before any controlled General Ledger accounting-history commit, reconcile the verified readiness contract against the target `GLTransaction` / `GLEntry` posting model and existing journal/posting invariants.

Proceed with a controlled accounting-history commit only if the live source proves a deterministic mapping that does not invent:
- target transaction type/status semantics;
- target business/posting date semantics beyond supplied source date;
- description/reference ownership;
- property/unit allocation rules;
- payer/payee identity;
- balancing lines;
- opening balances;
- reversal linkage.

If those semantics are not already defined by the existing target accounting model, treat that as a real source/contract blocker and continue to the next independently safe migration resource rather than inventing accounting history.

AppFolio API transport and general UX remain out of scope.

---

# AI_HANDOFF.md — 2026-10-02 PHASE 4.13 GENERAL LEDGER STAGED DRY RUN VERIFIED

## Current verified product checkpoint

- Phase 4.11 — Senior Housing: **COMPLETE | VERIFIED**.
- Phase 4.12 — Short-term Rentals: **COMPLETE | VERIFIED**.
- Phase 4.13 — AppFolio CSV/XLSX migration: **IN PROGRESS**.
- Verified PRODUCT SHA: `da0b23fdba8f95fb2eeb818d3ff95e40df3f6f97`.
- GitHub Actions run: `37062246604` — SUCCESS.
- All six required CI jobs passed:
  - frontend: PASS
  - backend: PASS
  - security: PASS
  - platform-admin: PASS
  - staging-config: PASS
  - authenticated E2E: PASS
- Backend/PostgreSQL: **938 passed, 21 deselected, 24789 warnings in 394.24s**.
- Authenticated E2E: **21 passed, 278 warnings in 72.04s**.
- Alembic head remains `0a7c4e9f2b61`.
- Expected model tables remain **201**.
- Navigation integrity and the `HIDDEN MENU / UNHIDE ROADMAP` remain unchanged.
- `docs/UX_STANDARDS.md` remains AUTHORIZED BUT NOT ACTIVE.

## Verified General Ledger staged accounting-history dry run

1. Dry run operates only on already-staged `GENERAL_LEDGER` rows from the verified CSV/XLSX pipeline.
2. Only explicit `ACCEPT_RELATIONSHIP` rows with stable source `LineItemId` participate; SKIP rows are excluded and unresolved/INVALID rows block readiness.
3. Current durable GL Account/Property/Unit source mappings and the accepted typed target IDs are revalidated before preview.
4. The dry-run fingerprint binds the shared staged-review fingerprint plus current durable relationship mapping fingerprints/target IDs, so changed mapping context fails stale.
5. Source transaction ID/date/debit/credit/description/reference/remarks/transaction type remain review evidence only.
6. Dry run returns resolved GLAccount/Property/Unit IDs without creating customer accounting records.
7. No balancing, netting, accounting-basis inference, opening-balance inference, payer/payee inference, target transaction grouping or posting semantics are performed.
8. Empty accepted-row sets are not dry-run ready.
9. Identical dry-run replay is idempotent and does not duplicate audit activity.
10. The batch creates or updates zero GLTransaction, GLEntry, journal entry, Receipt, Bill, Charge, GLAccount, AccountingKeyAccount or customer balance records.

Implementation commits:
- `4ba9e28f0eac8268c6700daf7aa4df2a4b042230` — General Ledger dry-run response schema.
- `5e3fbb2bb2bdf5c0265e9ae19c46fba9cf56a6ab` — exact staged/mapping revalidation and fingerprint state.
- `6da9efbd6b3a402d3d920593f7221c00104d19e2` — platform dry-run route and audit.
- `da0b23fdba8f95fb2eeb818d3ff95e40df3f6f97` — focused idempotency/staleness/non-mutation regressions; final VERIFIED PRODUCT SHA.

## Exact next Phase 4.13 product batch

Add **General Ledger accounting-history commit-readiness reconciliation only** before any customer accounting mutation.

Required boundaries:

1. Continue from the exact accepted staged rows and latest verified dry-run fingerprint; no arbitrary accounting payloads.
2. Group source rows only by supplied stable `TransactionId`; rows missing `TransactionId` cannot be commit-ready and may only remain review/skip.
3. Validate each candidate transaction group is internally balanced from source debit/credit evidence before any later commit can be permitted.
4. Require every retained line to have the already-verified active same-organization GL Account relationship and any supplied Property/Unit relationship.
5. Do not fabricate balancing lines, opening balances, target transaction type, payer/payee, reference semantics or posting date beyond supplied source evidence.
6. Record only review/readiness metadata or a deterministic readiness fingerprint in this batch; create/update zero GLTransaction/GLEntry/journal entry/Receipt/Bill/Charge/balance records.
7. A changed staged review, durable mapping, source line fingerprint or group composition must invalidate readiness.
8. Repeating identical readiness analysis must be idempotent/audited once.
9. Controlled accounting-history commit remains a separate later verified batch and must consume this exact readiness state.
10. AppFolio API transport and general UX work remain out of scope.

---

# AI_HANDOFF.md — 2026-10-02 PHASE 4.13 GENERAL LEDGER RELATIONSHIP RECONCILIATION VERIFIED

## Current verified product checkpoint

- Phase 4.11 — Senior Housing: **COMPLETE | VERIFIED**.
- Phase 4.12 — Short-term Rentals: **COMPLETE | VERIFIED**.
- Phase 4.13 — AppFolio CSV/XLSX migration: **IN PROGRESS**.
- Verified PRODUCT SHA: `40368c4a3e6fbcbb42b0c3bab08c3455864b6db2`.
- GitHub Actions run: `37059481037` — SUCCESS.
- All six required CI jobs passed:
  - frontend: PASS
  - backend: PASS
  - security: PASS
  - platform-admin: PASS
  - staging-config: PASS
  - authenticated E2E: PASS
- Backend/PostgreSQL: **936 passed, 21 deselected, 24741 warnings in 231.04s**.
- Authenticated E2E: **21 passed, 278 warnings in 75.98s**.
- Alembic head remains `0a7c4e9f2b61`.
- Expected model tables remain **201**.
- Navigation integrity and the `HIDDEN MENU / UNHIDE ROADMAP` remain unchanged.
- `docs/UX_STANDARDS.md` remains AUTHORIZED BUT NOT ACTIVE.

## Verified staged General Ledger relationship reconciliation

1. Resolution operates only on already-staged `GENERAL_LEDGER` rows.
2. `ACCEPT_RELATIONSHIP` requires durable source `LineItemId` identity; missing identity may only be explicitly SKIPped.
3. Source GL Account identity is revalidated only through the durable `GL_ACCOUNTS -> GL_ACCOUNT` mapping and an active, nondeleted, same-organization target GLAccount.
4. Supplied PropertyId/UnitId relationships are revalidated only through durable source mappings; Unit->Property consistency fails closed.
5. Accepted review state snapshots only already-verified typed target GLAccount/Property/Unit IDs on the staged row.
6. INVALID rows remain non-resolvable; unresolved REVIEW rows may be SKIPped.
7. Resolution changes participate in the shared staged-review fingerprint and invalidate prior run dry-run state.
8. Repeating the identical accepted resolution is idempotent and does not duplicate audit activity.
9. The batch creates or updates zero GLTransaction, GLEntry, journal entry, Receipt, Bill, Charge, GLAccount, AccountingKeyAccount or accounting-balance records.
10. No AppFolio API transport, navigation change or general UX work was added.

Implementation commits:
- `1ebb7b5f0395c91490f64805f636b2715482ecbf` — General Ledger reconciliation schema.
- `7d0b3c61e24ba6473d01338c80046e929919ba63` — staged relationship resolver.
- `40368c4a3e6fbcbb42b0c3bab08c3455864b6db2` — focused regressions; final VERIFIED PRODUCT SHA.

## Exact next Phase 4.13 product batch

Add **General Ledger staged accounting-history dry-run only** using the existing exact-fingerprint staged-review architecture.

Required boundaries:

1. Operate only on already-staged `GENERAL_LEDGER` rows from the verified upload pipeline.
2. Include only explicit `ACCEPT_RELATIONSHIP` rows with stable source `LineItemId`; SKIP rows remain excluded and unresolved/INVALID rows block readiness.
3. Revalidate current durable GL Account/Property/Unit mappings and the snapped typed target IDs before dry-run.
4. Preserve source date, debit, credit, description, reference, remarks, transaction type and transaction ID as review evidence only.
5. Do not create, update, balance, net or post GLTransaction, GLEntry, journal entry, Receipt, Bill, Charge, GLAccount, AccountingKeyAccount or customer balances.
6. Do not infer accounting basis, balancing entries, opening balances, payer/payee identity, reconciliation completion, transaction grouping or target posting semantics.
7. Dry-run output must bind the exact shared staged-review fingerprint and current source fingerprints; changed source/review state makes later use stale.
8. A dry-run containing no accepted ledger rows is not commit-ready.
9. Add focused safety/idempotency/staleness tests.
10. Accounting-history controlled commit remains a separate later batch; AppFolio API transport and general UX remain out of scope.

---

# AI_HANDOFF.md — 2026-10-02 PHASE 4.13 GENERAL LEDGER STAGING VERIFIED

## Current verified product checkpoint

- Phase 4.11 — Senior Housing: **COMPLETE | VERIFIED**.
- Phase 4.12 — Short-term Rentals: **COMPLETE | VERIFIED**.
- Phase 4.13 — AppFolio CSV/XLSX migration: **IN PROGRESS**.
- Verified PRODUCT SHA: `cd556c6c959457dfde93f6a3c93359557e3ef3ed`.
- GitHub Actions run: `37057756577` — SUCCESS.
- All six required CI jobs passed:
  - frontend: PASS
  - backend: PASS
  - security: PASS
  - platform-admin: PASS
  - staging-config: PASS
  - authenticated E2E: PASS
- Backend/PostgreSQL: **933 passed, 21 deselected, 24679 warnings in 392.18s**.
- Authenticated E2E: **21 passed, 278 warnings in 113.36s**.
- Alembic head remains `0a7c4e9f2b61`.
- Expected model tables remain **201**.
- Navigation integrity and the `HIDDEN MENU / UNHIDE ROADMAP` remain unchanged.
- `docs/UX_STANDARDS.md` remains AUTHORIZED BUT NOT ACTIVE.

## Verified General Ledger CSV/XLSX ingestion + staging

1. Shared ingestion now supports `GENERAL_LEDGER` using the verified AppFolio General Ledger Details source attributes only.
2. Automatic detection requires `GlAccountId`, `Date`, `Debit` and `Credit`; source fields remain source evidence rather than target accounting semantics.
3. Supplied `LineItemId` is preserved as stable row identity and duplicate supplied line IDs fail closed.
4. Missing `LineItemId` remains REVIEW; no identity is synthesized from transaction ID, dates, descriptions, references, row fingerprints or amounts.
5. Source GL Account relationships are checked only through durable `GL_ACCOUNTS -> GL_ACCOUNT` mappings and active same-organization targets.
6. Supplied Property/Unit IDs are checked only through existing durable source mappings; display names are not used as relationship keys.
7. Debit/credit source values must be numeric but are not posted, balanced, netted or translated into target entries.
8. Every valid ledger row remains REVIEW-only; accounting-history reconciliation and commit remain separate future batches.
9. CSV/XLSX replay is normalized-fingerprint idempotent.
10. The batch creates or updates zero GLTransaction, GLEntry, journal entry, Receipt, Bill, Charge, GLAccount, AccountingKeyAccount or accounting-balance records.

Implementation commits:
- `e7bc64e769f94f6393b5c6fcc627b79e319cb67c` — General Ledger staging contract in shared ingestion.
- `db95a09a0e437689d5319fe90d8d87418e4d14c7` — focused CSV/XLSX/replay/safety regressions.
- `890524ad3235f7e1fb7eea688efc844111aad21b` — plan/source-contract documentation.
- `cd556c6c959457dfde93f6a3c93359557e3ef3ed` — regression expectation correction; final VERIFIED PRODUCT SHA.

## Exact next Phase 4.13 product batch

Add **staged General Ledger relationship reconciliation only** using the shared staged-row resolution/fingerprint/audit architecture.

Required boundaries:

1. Reconcile only already-staged `GENERAL_LEDGER` rows; never accept arbitrary ledger payloads.
2. Require a stable source `LineItemId` before any row can be accepted for later accounting-history commit; rows without it may only be SKIPped.
3. Add/allow an explicit `ACCEPT_RELATIONSHIP` review action only when the current durable `GL_ACCOUNTS` mapping resolves to an active same-organization GLAccount.
4. If PropertyId/UnitId are supplied, revalidate their durable mappings and Unit->Property consistency; unresolved supplied relationships cannot be accepted.
5. Snapshot only typed target relationship IDs already available on the staged row; do not create GL/accounting records.
6. Resolution changes must be audited, participate in the shared staged-review fingerprint and invalidate prior run dry-run state.
7. Repeating the identical accepted relationship must be idempotent.
8. INVALID rows remain non-resolvable; REVIEW rows that cannot be safely accepted may be explicitly SKIPped.
9. Create/update zero GLTransaction, GLEntry, journal entry, Receipt, Bill, Charge, GLAccount, AccountingKeyAccount or balance records.
10. Do not implement accounting-history dry-run/controlled commit, AppFolio API transport or general UX work in this batch.

---

# AI_HANDOFF.md — 2026-10-02 PHASE 4.13 GL ACCOUNT CONTROLLED MAPPING COMMIT VERIFIED

## Current verified product checkpoint

- Phase 4.11 — Senior Housing: **COMPLETE | VERIFIED**.
- Phase 4.12 — Short-term Rentals: **COMPLETE | VERIFIED**.
- Phase 4.13 — AppFolio CSV/XLSX migration: **IN PROGRESS**.
- Verified PRODUCT SHA: `3b02f5d88c11100e7ff70fcada281ebdb8c9eee5`.
- GitHub Actions run: `37052444887` — SUCCESS.
- All six required CI jobs passed: frontend, backend, security, platform-admin, staging-config, authenticated E2E.
- Backend/PostgreSQL: **931 passed, 21 deselected, 24646 warnings in 294.15s**.
- Authenticated E2E: **21 passed, 278 warnings in 115.32s**.
- Alembic head remains `0a7c4e9f2b61`.
- Expected model tables remain **201**.
- Navigation integrity and the `HIDDEN MENU / UNHIDE ROADMAP` remain unchanged.
- `docs/UX_STANDARDS.md` remains AUTHORIZED BUT NOT ACTIVE.

## Verified GL Account controlled mapping commit

1. Staged `GL_ACCOUNTS` review state feeds an exact-fingerprint dry run.
2. Only explicit `MATCH_EXISTING` rows can persist new durable `GL_ACCOUNTS -> GL_ACCOUNT` mappings.
3. Existing durable mappings replay idempotently only while the target remains active, nondeleted and same-organization.
4. Changed staged resolution/source review state makes prior dry-run fingerprints stale.
5. SKIP rows are excluded; a skip-only upload cannot be committed as accounting migration progress.
6. Controlled commit creates or updates zero GLAccount, AccountingKeyAccount, journal-entry, GL-transaction, balance or accounting-history records.
7. Target GL account number/name/type and posting semantics remain untouched.

Implementation commits:
- `1fe69d4ab678d161160d182732e6851661dcc5ec` — dry-run/commit schemas.
- `83efe5f13122d4e9bee0be1858c198e5a9f1b9ca` — mapping dry-run/commit service.
- `6a958f64d5c74bd4400673e432871f23d3bca72d` — staged routes.
- `0b774e7e0517576260a285bbf923672c6a4e5013` — focused regressions.
- `3b02f5d88c11100e7ff70fcada281ebdb8c9eee5` — source-contract documentation; final VERIFIED PRODUCT SHA.

## Exact next Phase 4.13 product batch

Add **General Ledger/history CSV/XLSX ingestion + staging only** through the shared migration architecture.

Required boundaries:

1. Use only source fields verified for AppFolio General Ledger Details; do not invent source columns.
2. Preserve stable source line/transaction/GL-account/property/unit IDs when supplied; never synthesize identity from descriptions, dates or amounts.
3. Require durable GL Account source mapping before a row can be considered relationship-ready; unresolved references remain REVIEW/INVALID.
4. Preserve debit, credit, date, description, reference, remarks and transaction type as source evidence only.
5. Do not create/update GLTransaction, GLEntry, journal entry, balance, Receipt, Bill, Charge or other customer accounting record.
6. Do not infer target accounting basis, balancing entries, opening balances, payer/payee identity or reconciliation completion.
7. Reuse upload detection/mapping/fingerprint/replay/audit/recovery architecture; no parallel migration system.
8. Do not implement AppFolio API transport or general UX work.
9. Reconciliation/dry-run/controlled accounting-history commit requires separate verified batches.

---

# AI_HANDOFF.md — 2026-10-02 PHASE 4.13 GL ACCOUNT RECONCILIATION VERIFIED

## Current verified product checkpoint

- Phase 4.11 — Senior Housing: **COMPLETE | VERIFIED**.
- Phase 4.12 — Short-term Rentals: **COMPLETE | VERIFIED**.
- Phase 4.13 — AppFolio CSV/XLSX migration: **IN PROGRESS**.
- Verified PRODUCT SHA: `9b2523db5e0a2e561f61b47d7aebd7d76212ca89`.
- GitHub Actions run: `37050387343` — SUCCESS.
- All six required CI jobs passed:
  - frontend: PASS
  - backend: PASS
  - security: PASS
  - platform-admin: PASS
  - staging-config: PASS
  - authenticated E2E: PASS
- Backend/PostgreSQL: **928 passed, 21 deselected, 24585 warnings in 420.98s**.
- Authenticated E2E: **21 passed, 278 warnings in 116.94s**.
- Alembic head: `0a7c4e9f2b61`.
- Expected model tables remain **201**.
- Navigation integrity and the `HIDDEN MENU / UNHIDE ROADMAP` remain unchanged.
- `docs/UX_STANDARDS.md` remains AUTHORIZED BUT NOT ACTIVE.

## Verified staged GL Account reconciliation

1. Reconciliation operates only on already-staged `GL_ACCOUNTS` rows.
2. A dedicated typed `resolution_target_gl_account_id` foreign key now records explicit GL Account matches; Property/Unit/User/Vendor resolution fields are not reused.
3. `MATCH_EXISTING` requires a stable source GL Account ID and an active, nondeleted same-organization target GLAccount.
4. Rows without a stable source GL Account ID may only be explicitly SKIPped; account number/name never become synthesized source identity.
5. INVALID rows and already-mapped rows cannot be manually re-resolved.
6. AppFolio Type/FundAccount source values are not translated into target `account_type`, key-account roles or posting behavior.
7. Resolution changes participate in the shared staged-review fingerprint and invalidate prior run dry-run state.
8. Repeating the identical resolution is idempotent and does not duplicate audit activity.
9. Resolution changes are audited with explicit no-overwrite/no-classification/no-accounting-mutation metadata.
10. The batch creates or updates zero GLAccount, AccountingKeyAccount, journal entry, GL transaction or accounting-balance records.

Implementation commits:
- `ae6a0d84b37dcc4e4497162f9e29cd44cfb34e80` — typed GLAccount staged resolution target.
- `48a0dbf48940e9e436da7d8aa6c68ad614e0bcb9` — migration `0a7c4e9f2b61`.
- `6ff40f11c19da34a2a8c015ccf37d142b73e0500` — reconciliation schema.
- `6a2ecd76943a9379ad6683aeb550b839f1cd56e3` — resolver, scope checks, audit and fingerprint binding.
- `9b2523db5e0a2e561f61b47d7aebd7d76212ca89` — focused regressions; final VERIFIED PRODUCT SHA.

## Exact next Phase 4.13 product batch

Add **GL Account staged dry-run + controlled durable mapping commit** using the existing exact-fingerprint migration architecture.

Required boundaries:

1. Operate only on already-staged `GL_ACCOUNTS` rows.
2. Only explicit `MATCH_EXISTING` rows may become new durable mappings in this batch; SKIP remains excluded.
3. Do not create or update GLAccount records. Existing target account number/name/type remain untouched.
4. Revalidate every matched target as active, nondeleted and same-organization at dry-run/commit time.
5. Existing durable `GL_ACCOUNTS -> GL_ACCOUNT` mappings may replay only when the target is still valid.
6. Bind staged review state to the exact dry-run fingerprint; any changed resolution or source fingerprint makes commit stale.
7. Commit persists only `PlatformMigrationItem` source-to-target mappings and must be replay/idempotency safe.
8. Do not mutate AccountingKeyAccount, journal entries, GL transactions, balances or accounting history.
9. Do not begin General Ledger/history source ingestion until this mapping commit is independently verified.

---

# AI_HANDOFF.md — 2026-10-02 PHASE 4.13 GL ACCOUNT STAGING VERIFIED

## Current verified product checkpoint

- Phase 4.11 — Senior Housing: **COMPLETE | VERIFIED**.
- Phase 4.12 — Short-term Rentals: **COMPLETE | VERIFIED**.
- Phase 4.13 — AppFolio CSV/XLSX migration: **IN PROGRESS**.
- Verified PRODUCT SHA: `d7e54d816c7ba4e58d0f1eee297819f363eb0a9d`.
- GitHub Actions run: `37035944867` — SUCCESS.
- All six required CI jobs passed:
  - frontend: PASS
  - backend: PASS
  - security: PASS
  - platform-admin: PASS
  - staging-config: PASS
  - authenticated E2E: PASS
- Backend/PostgreSQL: **925 passed, 21 deselected, 24536 warnings in 418.99s**.
- Authenticated E2E: **21 passed, 278 warnings in 100.27s**.
- Alembic head remains `f58a2c4d6e91`.
- Expected model tables remain **201**.
- Navigation integrity and the `HIDDEN MENU / UNHIDE ROADMAP` remain unchanged.
- `docs/UX_STANDARDS.md` remains AUTHORIZED BUT NOT ACTIVE.

## Verified GL Accounts CSV/XLSX staging

1. Shared ingestion detects `GL_ACCOUNTS` only when Number, Name and Type are present.
2. CSV and XLSX staging preserve supplied stable GL Account ID plus account number/code, name, AppFolio type and verified source-only Fund/corporate/parent/offset/property/update fields.
3. Missing stable GL Account ID remains REVIEW; account number/name/type are not promoted to source identity.
4. Duplicate supplied GL Account IDs and duplicate number/name/type source rows fail closed.
5. AppFolio Type/FundAccount and related source fields are preserved as evidence only and are not translated into target GL classification, key-account roles or posting behavior.
6. Upload replay remains normalized-fingerprint idempotent.
7. The batch creates or updates zero GLAccount, AccountingKeyAccount, journal entry, GL transaction or accounting-balance records.
8. No AppFolio API transport, navigation change or general UX work was added.

Implementation commits:
- `44a5d9221be468799d6485f1766e1f5c52006032` — shared GL Account staging support.
- `705c65708898c27bd7de7302abf2cfb5fc70300c` — focused CSV/XLSX staging regressions.
- `d7e54d816c7ba4e58d0f1eee297819f363eb0a9d` — verified source-contract documentation; final VERIFIED PRODUCT SHA.

## Exact next Phase 4.13 product batch

Add **staged GL Account reconciliation only** using the existing shared review architecture.

Required boundaries:

1. Add a typed GL Account resolution target; do not reuse Property/Unit/User resolution fields.
2. Reconcile only already-staged `GL_ACCOUNTS` rows.
3. Permit explicit `MATCH_EXISTING` only to an active same-organization GLAccount, or explicit `SKIP`.
4. Rows without a stable source GL Account ID may only be skipped; never synthesize identity from account number or name.
5. Do not translate AppFolio account Type/FundAccount into target account_type or key-account semantics during reconciliation.
6. Resolution changes must be audited, invalidate prior dry-run state and participate in the shared staged-review fingerprint.
7. Repeated identical resolution must be idempotent.
8. Create/update zero GLAccount, AccountingKeyAccount, journal entry, GL transaction or balance records.
9. Do not start accounting-history migration or GL controlled commit until reconciliation is independently verified.

---

# AI_HANDOFF.md — 2026-10-02 PHASE 4.13 LEASE/OCCUPANCY RECONCILIATION VERIFIED

## Current verified product checkpoint

- Phase 4.11 — Senior Housing: **COMPLETE | VERIFIED**.
- Phase 4.12 — Short-term Rentals: **COMPLETE | VERIFIED**.
- Phase 4.13 — AppFolio CSV/XLSX migration: **IN PROGRESS**.
- Verified PRODUCT SHA: `adc689c2a89a26d79f19889e5ae5f609e55c7174`.
- GitHub Actions run: `37029331351` — SUCCESS after authenticated E2E retry.
- All six required CI jobs passed:
  - frontend: PASS
  - backend: PASS
  - security: PASS
  - platform-admin: PASS
  - staging-config: PASS
  - authenticated E2E: PASS
- Backend/PostgreSQL: **922 passed, 21 deselected, 24499 warnings in 411.26s**.
- Authenticated E2E retry: **21 passed, 278 warnings in 117.06s**.
- Alembic head remains `f58a2c4d6e91`.
- Expected model tables remain **201**.
- Navigation integrity and the `HIDDEN MENU / UNHIDE ROADMAP` remain unchanged.
- `docs/UX_STANDARDS.md` remains AUTHORIZED BUT NOT ACTIVE.
- The first E2E attempt failed on an unrelated existing Short-term Rentals tab click timeout; rerunning the failed job passed without source changes.

## Verified staged Lease / occupancy reconciliation

1. Reconciliation operates only on already-staged `LEASE_OCCUPANCY` rows; callers cannot submit arbitrary Lease records or target IDs.
2. `ACCEPT_RELATIONSHIP` revalidates durable TENANTS, PROPERTIES and UNITS mappings and requires active same-organization target entities of the expected types.
3. Accepted relationships snapshot the verified target Property, Unit and Tenant user IDs into the existing typed staged-row resolution fields.
4. The accepted review state participates in the shared staged-review fingerprint; changing reconciliation state changes the fingerprint.
5. Missing or unresolved durable relationship identity cannot be accepted; such REVIEW rows may be explicitly SKIPped.
6. INVALID/contradictory rows remain non-resolvable and cannot become commit-ready.
7. Unit/Property consistency is revalidated at reconciliation time; stale or type-changed source mappings fail closed.
8. Resolution changes invalidate the run's prior dry-run fingerprint/summary and are audited.
9. Repeating the identical accepted resolution is idempotent and does not duplicate audit activity.
10. The batch creates or updates **zero** Lease, RentInvoice, Payment, Charge, Receipt or GL records.
11. No AppFolio API transport, navigation change or general UX work was added.

Implementation commit:
- `adc689c2a89a26d79f19889e5ae5f609e55c7174` — Lease/occupancy reconciliation schema/route, durable dependency validation, fingerprint binding, plan update and focused regressions; final VERIFIED PRODUCT SHA.

## Exact next Phase 4.13 product batch

Proceed to **GL Accounts CSV/XLSX source-schema verification and staging support** using the existing shared migration architecture.

Reason for dependency transition:

- the verified Lease/occupancy source contract does not guarantee a stable AppFolio Lease/occupancy source ID;
- creating a durable Lease mapping key from names, dates, labels, row fingerprints or another synthesized value would invent source identity and violate the migration plan;
- therefore Lease target creation remains intentionally deferred until a reliable source identity/commit contract is independently verified;
- the documented dependency order permits continuing to GL Accounts after Lease/occupancy staging/reconciliation is safely preserved.

Required boundaries:

1. Verify a reliable AppFolio Chart of Accounts / GL Accounts export contract before adding automatic aliases.
2. Reuse shared CSV/XLSX upload, detection, mapping, staging, validation, fingerprint, replay/idempotency, audit and recovery architecture.
3. Preserve stable source account IDs/codes where the verified export supplies them; do not infer account identity from display name alone.
4. First GL Accounts batch is staging/reconciliation only: do not create/update GLAccount, key-account configuration, journal entries, transactions, balances or accounting history.
5. Preserve source account number/code, name, type/classification and any verified active/hidden/source-only fields without translating them into unsupported target semantics.
6. Missing or contradictory source identity/classification remains REVIEW/INVALID; never fabricate account codes or financial classifications.
7. Preserve organization scope, navigation integrity, hidden-menu roadmap and inactive UX standards.
8. Do not begin accounting-history/balance migration until GL Account staging and reconciliation are independently verified.

---

# AI_HANDOFF.md — 2026-10-02 PHASE 4.13 LEASE/OCCUPANCY STAGING VERIFIED

## Current verified product checkpoint

- Phase 4.11 — Senior Housing: **COMPLETE | VERIFIED**.
- Phase 4.12 — Short-term Rentals: **COMPLETE | VERIFIED**.
- Phase 4.13 — AppFolio CSV/XLSX migration: **IN PROGRESS**.
- Verified PRODUCT SHA: `92367ffd08b0f789bac4dff835ef8efee4e3262b`.
- GitHub Actions run: `36983384744` — SUCCESS.
- All six required CI jobs passed:
  - frontend: PASS
  - backend: PASS
  - security: PASS
  - platform-admin: PASS
  - staging-config: PASS
  - authenticated E2E: PASS
- Backend/PostgreSQL: **919 passed, 21 deselected, 24442 warnings in 400.52s**.
- Authenticated E2E: **21 passed, 278 warnings in 115.07s**.
- Alembic head remains `f58a2c4d6e91`.
- Expected model tables remain **201**.
- Navigation integrity and the `HIDDEN MENU / UNHIDE ROADMAP` remain unchanged.
- `docs/UX_STANDARDS.md` remains AUTHORIZED BUT NOT ACTIVE.

## Verified Lease / occupancy source staging

1. Shared CSV/XLSX ingestion supports explicit `LEASE_OCCUPANCY` staging without creating a parallel migration system.
2. `LEASE_OCCUPANCY` is intentionally explicit-only; Tenant Directory auto-detection remains unchanged.
3. The verified staging contract preserves stable Tenant, Property and Unit source IDs plus source-only tenant name, status, rent, deposit, move-in/out and lease-from/to evidence.
4. Relationship readiness resolves only through durable `TENANTS`, `PROPERTIES` and `UNITS` source mappings. Display names, labels, addresses and dates never substitute for source identity.
5. Missing relationship IDs or missing durable mappings remain REVIEW; contradictory Unit/Property target relationships become INVALID.
6. Duplicate relationship rows in one upload are rejected conservatively.
7. Rent, deposit, status and date values remain source evidence only and do not establish occupancy, rent liability, security-deposit receipt or accounting balances.
8. The batch creates or updates **zero** Lease, RentInvoice, Payment, Charge, Receipt or GL records.
9. CSV replay remains idempotent and preserves the existing upload/fingerprint/audit/recovery architecture.
10. No AppFolio API transport, navigation change or general UX work was added.

Implementation commit:
- `92367ffd08b0f789bac4dff835ef8efee4e3262b` — Lease/occupancy explicit staging contract, source evidence, relationship guards, plan documentation and focused regressions; final VERIFIED PRODUCT SHA.

## Exact next Phase 4.13 product batch

Add **staged Lease/occupancy reconciliation only** using the existing staged-row review architecture.

Required boundaries:

1. Reconcile only already-staged `LEASE_OCCUPANCY` rows; never accept arbitrary caller-supplied lease records.
2. Reuse durable Tenant, Unit and Property source mappings as the only relationship authority.
3. Allow only explicit review actions needed to mark a relationship as accepted-for-later-commit or SKIP; do not create a Lease in this batch.
4. Do not infer missing Tenant/Unit/Property identity, occupancy, lease status, rent liability, deposit receipt, credentials or accounting history.
5. REVIEW rows with missing/unresolved durable identities may only remain unresolved or be explicitly skipped; contradictory/INVALID rows must not become commit-ready.
6. Any reconciliation change must be audited, invalidate prior migration dry-run fingerprints/summaries, and bind into the shared staged-review fingerprint.
7. Preserve organization scope, replay/idempotency, recovery visibility, navigation integrity, hidden-menu roadmap and inactive UX standards.
8. Do not begin Lease controlled commit or accounting-history migration until this reconciliation dependency is independently verified.

---

# AI_HANDOFF.md — 2026-10-02 PHASE 4.13 TENANT DRY-RUN + CONTROLLED MAPPING COMMIT VERIFIED

## Current verified product checkpoint

- Phase 4.11 — Senior Housing: **COMPLETE | VERIFIED**.
- Phase 4.12 — Short-term Rentals: **COMPLETE | VERIFIED**.
- Phase 4.13 — AppFolio CSV/XLSX migration: **IN PROGRESS**.
- Verified PRODUCT SHA: `5b18d175a758707ff26ca31df872add06c0413a5`.
- GitHub Actions run: `36981372838` — SUCCESS.
- All six required CI jobs passed:
  - frontend: PASS
  - backend: PASS
  - security: PASS
  - platform-admin: PASS
  - staging-config: PASS
  - authenticated E2E: PASS
- Backend/PostgreSQL: **916 passed, 21 deselected, 24374 warnings in 392.46s**.
- Authenticated E2E: **21 passed, 278 warnings in 112.00s**.
- Alembic head remains `f58a2c4d6e91`.
- Expected model tables remain **201**.
- Navigation integrity and the `HIDDEN MENU / UNHIDE ROADMAP` remain unchanged.
- `docs/UX_STANDARDS.md` remains AUTHORIZED BUT NOT ACTIVE.

## Verified staged Tenant dry-run + controlled mapping commit

1. Reviewed staged TENANTS rows now feed a dedicated dry-run endpoint; callers cannot submit arbitrary Tenant records.
2. Tenant dry run/commit reuses the existing migration-run exact-fingerprint architecture and durable `PlatformMigrationItem` source mappings.
3. Existing durable TENANTS mappings replay safely only when the target remains an active same-organization `UserRole.TENANT`.
4. Explicit MATCH_EXISTING resolutions map only to an active same-organization TENANT user and never overwrite that user.
5. Tenant `CREATE_NEW` is intentionally unsupported for controlled commit because the verified Tenant Directory lacks safe first/last identity and credential semantics for a login-backed account.
6. SKIP rows are excluded; unresolved NEW/POSSIBLE_MATCH/REVIEW/INVALID rows block dry run unless safely resolved/skipped.
7. The exact fingerprint binds staged review state plus the referenced durable Property and Unit mapping IDs/source fingerprints. A changed relationship mapping makes the prior commit preview stale.
8. Controlled commit persists only a durable `TENANTS -> TENANT_USER` source mapping. It creates or updates **zero** customer User records.
9. Move-in/out and Lease From/To remain source evidence only. No Lease, occupancy event, Charge, Receipt or GL record is created.
10. Commit replay is idempotent and does not duplicate Tenant mappings.
11. Migration audit records explicitly disclose no target overwrite, no Tenant-user creation/update, no Lease/occupancy mutation and no accounting mutation.
12. No AppFolio API transport, navigation change or general UX work was added.

Implementation commit:
- `5b18d175a758707ff26ca31df872add06c0413a5` — Tenant staged dry run, relationship-bound fingerprint, controlled existing-user mapping commit and focused regressions; final VERIFIED PRODUCT SHA.

## Exact next Phase 4.13 product batch

Proceed in the documented dependency order to **Lease / occupancy source-schema verification and staging support**.

Required boundaries:

1. Reuse the shared CSV/XLSX upload, detection, column-mapping, staging, validation, fingerprint, replay/idempotency, audit and recovery architecture.
2. Do not create a parallel migration system and do not implement AppFolio API transport.
3. First verify a reliable AppFolio Rent Roll / lease-occupancy export contract before adding automatic field aliases; do not invent source columns from our target Lease model.
4. Preserve stable Tenant, Unit and Property source IDs where the verified export supplies them; relationships must resolve through durable source mappings, never display-name-only matching.
5. This first Lease/occupancy batch is **staging/reconciliation only**. Do not create or update Lease, RentInvoice, Payment, Charge, Receipt or GL records.
6. Treat contract dates, move-in/out, rent/deposit and occupancy fields as source evidence only until a later controlled commit contract is independently verified.
7. Missing/contradictory Tenant/Unit/Property source identities remain REVIEW/INVALID rather than fabricated.
8. Preserve organization isolation, audit/idempotency, recovery visibility, navigation integrity, the hidden-menu roadmap and inactive UX standards.
9. Do not begin accounting-history migration until Lease/occupancy staging and its dependency/reconciliation rules are verified.

---

# AI_HANDOFF.md — 2026-10-02 PHASE 4.13 TENANT STAGED RECONCILIATION VERIFIED

## Current verified product checkpoint

- Phase 4.11 — Senior Housing: **COMPLETE | VERIFIED**.
- Phase 4.12 — Short-term Rentals: **COMPLETE | VERIFIED**.
- Phase 4.13 — AppFolio CSV/XLSX migration: **IN PROGRESS**.
- Verified PRODUCT SHA: `ba82fc275495c41465383ea8d609dfccc15a4ece`.
- GitHub Actions run: `36977308748` — SUCCESS after authenticated E2E retry.
- All six required CI jobs passed:
  - frontend: PASS
  - backend: PASS
  - security: PASS
  - platform-admin: PASS
  - staging-config: PASS
  - authenticated E2E: PASS
- Backend/PostgreSQL: **913 passed, 21 deselected, 24323 warnings in 387.98s**.
- Authenticated E2E retry: **21 passed, 278 warnings in 117.00s**.
- Alembic head: `f58a2c4d6e91`.
- Expected model tables remain **201**.
- Navigation integrity and the `HIDDEN MENU / UNHIDE ROADMAP` remain unchanged.
- `docs/UX_STANDARDS.md` remains AUTHORIZED BUT NOT ACTIVE.
- The first E2E attempt failed on an unrelated existing Student Housing tab click timeout; rerunning that failed job passed without source changes.

## Verified staged Tenant reconciliation scope

1. Staged TENANTS rows now have a correctly typed `resolution_target_tenant_user_id` foreign key to customer users.
2. Tenant resolution does not reuse Property, Unit, Owner or Vendor resolution columns.
3. Stable-source-ID Tenant rows may be explicitly MATCH_EXISTING to an active same-organization `UserRole.TENANT`, CREATE_NEW only from a reviewed POSSIBLE_MATCH, or SKIP.
4. REVIEW rows with missing/unresolved durable Tenant/Unit/Property identity may only be skipped.
5. Cross-organization, inactive or wrong-role target probes fail closed.
6. Resolution never overwrites or mutates the matched customer Tenant user.
7. Resolution changes are audited, clear the prior run dry-run fingerprint/summary and participate in the shared staged-review fingerprint.
8. The reconciliation batch creates or updates **zero** customer Tenant users, leases, occupancy, charges, receipts or GL records.
9. Migration parity advanced to `f58a2c4d6e91`; model-table count remains 201.
10. No AppFolio API transport, navigation change or general UX work was added.

Implementation commits:
- `ce477249c75e932c812869b1a09ab51b39f38521` — typed Tenant reconciliation target, schema, route, migration and focused regressions.
- `ba82fc275495c41465383ea8d609dfccc15a4ece` — focused fixture-ID correction; final VERIFIED PRODUCT SHA.

## Exact next Phase 4.13 product batch

Add **staged Tenant dry-run + controlled mapping commit** using the existing exact-fingerprint architecture.

Required boundaries:

1. Derive input only from reviewed TENANTS staged rows; never accept arbitrary caller-supplied Tenant records.
2. Existing durable TENANTS mappings and explicit MATCH_EXISTING resolutions must replay safely and never overwrite the target Tenant user.
3. `CREATE_NEW` remains unsupported for controlled commit in this batch because the verified Tenant Directory provides a display name/contact data but not safe first/last identity and credential semantics for a login-backed Tenant account. Do not split names or invent credentials.
4. SKIP rows are excluded. Missing durable Tenant source ID, invalid/review/unresolved relationship rows block dry run unless explicitly skipped where permitted.
5. Dry run must be target-non-mutating and bind staged review state plus referenced durable Unit/Property mappings into the exact fingerprint.
6. Controlled commit may persist only durable TENANTS source mappings to verified existing TENANT users; it must not create or update customer User records.
7. Preserve Unit/Property relationship context for later occupancy migration, but do not create Lease/occupancy records or infer liability from move-in/out or lease dates.
8. Preserve organization scope, audit, idempotency, recovery visibility, navigation integrity and inactive UX standards.
9. Do not proceed to Lease/occupancy commit, accounting-history migration or AppFolio API transport until this Tenant mapping dependency is verified.

---

# AI_HANDOFF.md — 2026-10-02 PHASE 4.13 TENANT DIRECTORY INGESTION + STAGING VERIFIED

## Current verified product checkpoint

- Phase 4.11 — Senior Housing: **COMPLETE | VERIFIED**.
- Phase 4.12 — Short-term Rentals: **COMPLETE | VERIFIED**.
- Phase 4.13 — AppFolio CSV/XLSX migration: **IN PROGRESS**.
- Verified PRODUCT SHA: `bfa48605b37211547183ce6cdab02eaa9e96b0de`.
- GitHub Actions run: `36968555302` — SUCCESS.
- All six required CI jobs passed:
  - frontend: PASS
  - backend: PASS
  - security: PASS
  - platform-admin: PASS
  - staging-config: PASS
  - authenticated E2E: PASS
- Backend/PostgreSQL: **911 passed, 21 deselected, 24279 warnings in 299.42s**.
- Authenticated E2E: **21 passed, 278 warnings in 114.29s**.
- Alembic head remains `d46f1a7c9e20`.
- Expected model tables remain **201**.
- Navigation integrity and the `HIDDEN MENU / UNHIDE ROADMAP` remain unchanged.
- `docs/UX_STANDARDS.md` remains AUTHORIZED BUT NOT ACTIVE.

## Verified Tenant Directory ingestion/staging scope

1. Shared AppFolio CSV/XLSX ingestion now recognizes the verified Tenant Directory source contract.
2. Preserved source fields are limited to verified export columns: Tenant ID/name/contact/address, Property ID/name/address, Unit ID/name, move-in/out and Lease From/To.
3. Tenant Directory detection requires stable Tenant, Unit and Property source-ID columns for automatic report identification; explicit resource mapping remains available through the shared ingestion architecture.
4. Stable AppFolio Tenant ID, Unit ID and Property ID are preserved when supplied; none are synthesized from names, email or phone.
5. Unit/Property relationships are checked only through existing durable source-to-target mappings.
6. Consistent mapped Unit/Property references remain review context only; staging does not create occupancy or lease liability.
7. Missing Tenant/Unit/Property source identity or unresolved durable relationships remain REVIEW rather than fabricated.
8. Exact single-source email may surface a conservative same-organization active TENANT possible match; no automatic matching or overwrite occurs.
9. Existing durable TENANTS mapping is surfaced as ALREADY_MAPPED.
10. Duplicate Tenant source IDs fail the affected staged row.
11. Move-in/out and Lease From/To values remain source evidence only; no Lease, occupancy event, Charge, Receipt or GL record is created.
12. CSV/XLSX replay remains idempotent and creates no duplicate staged upload/rows.
13. This verified batch creates or updates **zero** customer Tenant users, leases, occupancy, charges, receipts or GL records.
14. No AppFolio API transport, navigation change or general UX work was added.

## Exact next Phase 4.13 product batch

Add **explicit staged Tenant reconciliation only** using the shared staged-row resolution/fingerprint/audit architecture.

Required boundaries:

1. Add a correctly typed Tenant-user resolution target; do not reuse Property/Unit/Owner/Vendor target columns.
2. Support explicit MATCH_EXISTING to an active same-organization `UserRole.TENANT`, CREATE_NEW only for a reviewed POSSIBLE_MATCH, and SKIP.
3. Rows without durable Tenant source identity, unresolved Unit/Property relationships or other REVIEW state may only be skipped; do not synthesize identity or occupancy.
4. Never overwrite or mutate a matched existing Tenant user.
5. Resolution changes must be durable, audited and invalidate the prior dry-run fingerprint.
6. Tenant resolution state/target identity must participate in the shared staged-review fingerprint.
7. This batch remains reconciliation-only: create/update **zero** Tenant users, leases, occupancy, charges, receipts or GL records.
8. Preserve organization isolation, durable Property/Unit relationship context, idempotency/recovery visibility, navigation integrity and inactive UX standards.
9. Do not implement Tenant dry-run/commit, Lease/occupancy commit, accounting-history migration or AppFolio API transport in this batch.

---

# AI_HANDOFF.md — 2026-10-02 PHASE 4.13 OWNER CONTROLLED MAPPING COMMIT VERIFIED

## Current verified product checkpoint

- Phase 4.11 — Senior Housing: **COMPLETE | VERIFIED**.
- Phase 4.12 — Short-term Rentals: **COMPLETE | VERIFIED**.
- Phase 4.13 — AppFolio CSV/XLSX migration: **IN PROGRESS**.
- Verified PRODUCT SHA: `62c87526e358baa56152afa32c781f2967323015`.
- GitHub Actions run: `36967232988` — SUCCESS.
- All six required CI jobs passed:
  - frontend: PASS
  - backend: PASS
  - security: PASS
  - platform-admin: PASS
  - staging-config: PASS
  - authenticated E2E: PASS
- Backend/PostgreSQL: **907 passed, 21 deselected, 24201 warnings in 400.80s**.
- Authenticated E2E: **21 passed, 278 warnings in 118.34s**.
- Alembic head remains `d46f1a7c9e20`.
- Expected model tables remain **201**.
- Navigation integrity and the `HIDDEN MENU / UNHIDE ROADMAP` remain unchanged.
- `docs/UX_STANDARDS.md` remains AUTHORIZED BUT NOT ACTIVE.

## Verified staged Owner dry-run + controlled mapping commit

1. Reviewed staged OWNERS rows now use the existing exact-fingerprint dry-run/controlled-commit architecture.
2. Commit input is derived only from staged Owner rows; arbitrary caller-supplied Owner records are not accepted.
3. Existing durable OWNERS mappings replay safely and must resolve to an active same-organization `UserRole.OWNER`.
4. Explicit MATCH_EXISTING creates only a durable AppFolio OWNERS -> existing `OWNER_USER` source mapping.
5. Existing target Owner profile fields are never overwritten or mutated.
6. Property ownership rows and `Property.owner_id` are not created or changed by this batch.
7. `CREATE_NEW` is intentionally blocked because the verified Owner Directory export does not provide safe first/last identity and credential semantics for a login-backed OWNER account.
8. SKIP remains supported; REVIEW/unresolved NEW/POSSIBLE_MATCH/invalid rows block dry run unless safely resolved or skipped.
9. Source display name, phone, email and property lists/IDs remain staging/review evidence and are explicitly disclosed as non-mutating.
10. Resolution/review state participates in the exact fingerprint; stale previews cannot commit.
11. Replay does not duplicate durable source mappings or customer Users.
12. No Tenant, Lease/occupancy, accounting-history, AppFolio API connector, navigation or general UX work was added.

Implementation commits in this verified batch:
- `0265c0d4c2989174f589fc99591d990dc29b9066` — Owner mapping commit engine.
- `c064ad40b4be49d78b90254103bd697b591e4a51` — Owner dry-run/commit schemas.
- `dcd4abfeaa800292267ed5d22ac24e4cbe043654` — staged Owner route wiring.
- `57ac3bea33960d83b6d414dcab56af2610f8f51a`, `62c87526e358baa56152afa32c781f2967323015` — focused Owner mapping regressions and test import correction; final VERIFIED PRODUCT SHA.

## Exact next Phase 4.13 product batch

Proceed to **Tenant Directory CSV/XLSX ingestion and staging only** using the existing shared migration staging architecture.

Required boundaries:

1. Verify the supported AppFolio Tenant Directory/export source columns before mapping them.
2. Reuse the current CSV/XLSX upload, detection, explicit/automatic mapping, staging, validation, replay/idempotency, audit and recovery architecture.
3. Preserve stable AppFolio Tenant ID and Unit/Property source references when supplied; do not synthesize source IDs from names, email or phone.
4. First Tenant batch is staging-only: create/update **zero** customer Tenant users, leases, occupancy, charges, receipts or GL records.
5. Resolve relationships only as review context through durable source IDs/mappings; do not infer occupancy or lease liability from display names.
6. Surface possible same-organization target matches conservatively and require later explicit reconciliation; never overwrite automatically.
7. Missing durable tenant identity or relationship references remain REVIEW/INVALID rather than fabricated.
8. Preserve exact source values not yet safe for target semantics as staging-only fields with disclosure.
9. Do not implement Lease/occupancy commit, accounting-history migration, AppFolio API transport or general UX work in this batch.
10. Keep navigation integrity, hidden-menu roadmap, organization isolation, audit/idempotency and recovery visibility unchanged.

---

# AI_HANDOFF.md — 2026-10-02 PHASE 4.13 VENDOR DRY-RUN + CONTROLLED COMMIT VERIFIED

## Current verified product checkpoint

- Phase 4.11 — Senior Housing: **COMPLETE | VERIFIED**.
- Phase 4.12 — Short-term Rentals: **COMPLETE | VERIFIED**.
- Phase 4.13 — AppFolio CSV/XLSX migration: **IN PROGRESS**.
- Verified PRODUCT SHA: `3dd5ee328eea0a03818254a3c7ca654848e7af11`.
- GitHub Actions run: `36956646373` — SUCCESS.
- All six required CI jobs passed:
  - frontend: PASS
  - backend: PASS
  - security: PASS
  - platform-admin: PASS
  - staging-config: PASS
  - authenticated E2E: PASS
- Backend/PostgreSQL: **905 passed, 21 deselected, 24157 warnings in 341.20s**.
- Authenticated E2E: **21 passed, 278 warnings in 115.46s**.
- Alembic head remains `d46f1a7c9e20`.
- Expected model tables remain **201**.
- Navigation integrity and the `HIDDEN MENU / UNHIDE ROADMAP` remain unchanged.
- `docs/UX_STANDARDS.md` remains AUTHORIZED BUT NOT ACTIVE.

## Verified staged Vendor dry-run + controlled commit

1. Reviewed staged VENDORS rows feed the existing exact-fingerprint migration architecture; callers cannot submit arbitrary Vendor payloads.
2. Durable VENDORS mappings replay safely and do not overwrite the mapped target.
3. Explicit MATCH_EXISTING resolutions map only to active same-organization Vendor targets and never mutate them.
4. Explicit CREATE_NEW may create only a new same-organization Vendor after the reviewed staged state is bound into the dry-run fingerprint.
5. Target creation maps only semantically supported Vendor Directory fields: company name and exact business email.
6. Address, plural phone values, Send 1099 and compliance-expiration values remain staging/source-only and are explicitly disclosed as omitted from target mutation.
7. SKIP rows are excluded; invalid/review/unresolved possible-match rows block dry run.
8. Controlled commit requires the exact latest dry-run fingerprint, persists durable VENDORS mappings and replays without duplicate Vendor creation.
9. Resolution/fingerprint changes invalidate stale commit attempts.
10. No Owner creation, Tenant, Lease/occupancy, accounting-history, AppFolio API connector, navigation or general UX work was added.

## Exact next Phase 4.13 product batch

Add **staged Owner dry-run + controlled mapping commit** using the same exact-fingerprint architecture.

Required boundaries:

1. Derive input only from reviewed OWNERS staged rows; never accept arbitrary caller-supplied Owner records.
2. Existing durable OWNERS mappings and explicit MATCH_EXISTING resolutions must replay safely and never overwrite the target OWNER user.
3. `CREATE_NEW` remains unsupported for commit because the verified Owner Directory supplies a display name but not safe first/last identity and credential semantics for a login-backed OWNER user. Do not split names or invent credentials.
4. SKIP rows are excluded. Missing durable source ID, invalid/review/unresolved possible-match rows block dry run unless explicitly skipped where already permitted.
5. Dry run must be target-non-mutating and bind staged review/resolution state into the exact fingerprint.
6. Controlled commit may persist only durable OWNERS source mappings to verified existing OWNER users; it must not create or update customer User records.
7. Preserve organization scope, audit, idempotency, recovery visibility, navigation integrity and inactive UX standards.
8. Do not proceed to Tenant Directory until this Owner commit dependency is verified.

---

# AI_HANDOFF.md — 2026-10-02 PHASE 4.13 OWNER/VENDOR RECONCILIATION VERIFIED

## Current verified product checkpoint

- Phase 4.11 — Senior Housing: **COMPLETE | VERIFIED**.
- Phase 4.12 — Short-term Rentals: **COMPLETE | VERIFIED**.
- Phase 4.13 — AppFolio CSV/XLSX migration: **IN PROGRESS**.
- Verified PRODUCT SHA: `e6c99f57a93b28fb71ea4951821793daff05b3d3`.
- GitHub Actions run: `36955400826` — SUCCESS.
- All six required CI jobs passed:
  - frontend: PASS
  - backend: PASS
  - security: PASS
  - platform-admin: PASS
  - staging-config: PASS
  - authenticated E2E: PASS
- Backend/PostgreSQL: **903 passed, 21 deselected, 24113 warnings in 389.34s**.
- Authenticated E2E: **21 passed, 278 warnings in 113.37s**.
- Alembic head: `d46f1a7c9e20`.
- Expected model tables remain **201**.
- Navigation integrity and the `HIDDEN MENU / UNHIDE ROADMAP` remain unchanged.
- `docs/UX_STANDARDS.md` remains AUTHORIZED BUT NOT ACTIVE.

## Verified AppFolio Vendor Directory ingestion/staging

- Product SHA `bfcd04fa887857250d0dd73646886fa0c007d0f2`.
- CI run `36949458698` SUCCESS; backend **900 passed, 21 deselected**; authenticated E2E **21 passed**.
- Shared CSV/XLSX staging recognizes the verified Vendor Directory source contract, preserves optional stable Vendor ID and source-only 1099/compliance-expiration values, supports conservative existing-target candidates, duplicate-source rejection, XLSX detection and replay/idempotency.
- Vendor staging creates or updates **zero** customer Vendor rows.

## Verified Owner/Vendor staged reconciliation foundation

1. Staged Owner and Vendor rows now have correctly typed reconciliation targets:
   - `resolution_target_owner_user_id` -> existing customer `users` OWNER row;
   - `resolution_target_vendor_id` -> existing customer `vendors` row.
2. The Property and Unit resolution foreign-key columns are not reused for Owner/Vendor IDs.
3. Stable-source-ID Owner/Vendor rows may be explicitly `MATCH_EXISTING`, `CREATE_NEW` (only from reviewed POSSIBLE_MATCH), or `SKIP`.
4. REVIEW rows with missing durable Owner/Vendor source identity may only be skipped; source identity is never synthesized from name/email.
5. Owner matches require active, undeleted same-organization `UserRole.OWNER`.
6. Vendor matches require active, undeleted same-organization Vendor.
7. Cross-organization or inactive target probes fail closed.
8. Resolution never overwrites or mutates the matched customer Owner/Vendor.
9. Resolution changes are audited, clear the prior run dry-run fingerprint/summary, and participate in the shared staged-review fingerprint.
10. Existing `ALREADY_MAPPED` rows remain controlled by their durable source mapping.
11. No Tenant, Lease/occupancy, accounting-history, AppFolio API connector, navigation, hidden-menu or general UX work was added.

Implementation commits in this verified batch:
- `f86aa2cfbb9be16b87431adc2b1a63c195e03aa5` — typed Owner/Vendor target columns.
- `20b746166b47cf75b7aa1d42edbce49d9860476f` — migration `d46f1a7c9e20`.
- `a86e0e318a9cc9302f16f92111dffe9784499a2b` — resolution schemas.
- `4660860bd9731213068a7279b447e547929cb55f` — scoped Owner/Vendor resolution endpoints and fingerprint binding.
- `e6c99f57a93b28fb71ea4951821793daff05b3d3` — focused reconciliation regressions; final VERIFIED PRODUCT SHA.

## Exact next Phase 4.13 product batch

Add **staged Vendor dry-run + controlled commit** using the existing exact-fingerprint migration architecture.

Required boundaries:

1. Derive commit input only from reviewed VENDORS staged rows; never accept arbitrary caller-supplied Vendor records.
2. Existing durable VENDORS mappings and explicit MATCH_EXISTING resolutions must replay safely and never overwrite the target Vendor.
3. CREATE_NEW may create only a new same-organization Vendor company after exact dry-run review.
4. Map only target fields that are semantically supported by the verified Vendor Directory source contract. Company name and exact business email are safe; do not reinterpret plural phone values, formatted address, Send 1099, insurance/license/EPA/contract expirations as target certification.
5. Source-only values remain preserved in staging; commit omission must be disclosed rather than silently invented or converted.
6. SKIP rows are excluded. INVALID/REVIEW/unresolved POSSIBLE_MATCH rows block dry run.
7. Dry run is target-non-mutating and binds staged review/resolution state into the exact fingerprint.
8. Controlled commit must require the exact latest fingerprint, persist durable VENDORS source mappings, and replay without duplicate Vendor creation.
9. Preserve organization scope, audit, idempotency, recovery visibility, navigation integrity and inactive UX standards.
10. Do not start Tenant Directory until the Owner/Vendor commit dependency is safe. Owner CREATE_NEW remains intentionally unresolved because the verified Owner Directory supplies a display Name while the current login-backed OWNER target requires separate first/last identity and credential semantics; do not invent those fields.

---

# AI_HANDOFF.md — 2026-10-02 PHASE 4.13 OWNER DIRECTORY STAGING VERIFIED

## Current verified product checkpoint

- Phase 4.11 — Senior Housing: **COMPLETE | VERIFIED**.
- Phase 4.12 — Short-term Rentals: **COMPLETE | VERIFIED**.
- Phase 4.13 — AppFolio CSV/XLSX migration: **IN PROGRESS**.
- Verified PRODUCT SHA: `5efbfcf0c517b04df9550474c232576cada53552`.
- GitHub Actions run: `36948279666` — SUCCESS.
- All six required CI jobs passed:
  - frontend: PASS
  - backend: PASS
  - security: PASS
  - platform-admin: PASS
  - staging-config: PASS
  - authenticated E2E: PASS
- Backend/PostgreSQL: **897 passed, 21 deselected, 24018 warnings in 388.04s**.
- Authenticated E2E: **21 passed, 278 warnings in 111.62s**.
- Alembic head remains `c35e9d2a7b14`.
- Expected model tables remain **201**.
- Navigation integrity and the `HIDDEN MENU / UNHIDE ROADMAP` remain unchanged.
- `docs/UX_STANDARDS.md` remains AUTHORIZED BUT NOT ACTIVE.

## Verified AppFolio Owner Directory ingestion/staging

1. Shared CSV/XLSX ingestion now recognizes a conservative verified Owner Directory export contract: Name, Phone Numbers, Email, Properties Owned and Properties Owned IDs, plus optional stable Owner ID when supplied.
2. Owner source fields remain staging/source data only. The batch does not split display names into target first/last names or invent target-only fields.
3. Missing stable Owner ID, missing email, or missing Properties Owned IDs remains explicit REVIEW rather than synthesizing identity or relationships.
4. Duplicate supplied Owner IDs in the same upload are INVALID.
5. Existing durable OWNERS source mappings replay as ALREADY_MAPPED.
6. Exact same-organization active target OWNER email is surfaced only as POSSIBLE_MATCH/review context; it is never automatically matched or overwritten.
7. CSV replay remains idempotent and multi-sheet XLSX can safely auto-select a unique Owner Directory sheet.
8. No customer User/Owner row is created or modified by staging.
9. No Vendor, Tenant, Lease/occupancy, accounting-history, AppFolio API connector, navigation change, or general UX work was added.

Implementation commit:
- `5efbfcf0c517b04df9550474c232576cada53552` — Owner Directory detect/map/normalize/stage support plus focused regressions; final VERIFIED PRODUCT SHA.

## Exact next Phase 4.13 product batch

Add **Vendor Directory CSV/XLSX ingestion and staging only** using the same shared staging architecture.

Required boundaries:

1. Map only fields supported by verified AppFolio Vendor Directory/export evidence; do not infer target-only fields.
2. Preserve optional stable Vendor ID when supplied; if durable source identity is absent, keep the row in REVIEW rather than synthesizing an ID.
3. Keep the first Vendor batch staging-only: no customer Vendor creation/update.
4. Surface same-organization possible target matches conservatively; never auto-overwrite.
5. Preserve export values such as company/name, address, phone, email, Send 1099 indicator and documented compliance-expiration fields as source data only; do not turn them into tax/compliance certification.
6. Reuse the existing upload/detection/mapping/staging/fingerprint/replay/audit/recovery architecture.
7. Do not proceed to Tenants until Owners/Vendors staging and reconciliation dependencies are verified.
8. Do not implement AppFolio API transport or general UX work.

---

# AI_HANDOFF.md — 2026-10-02 PHASE 4.13 UNIT RECONCILIATION VERIFIED

## Current verified product checkpoint

- Phase 4.11 — Senior Housing: **COMPLETE | VERIFIED**.
- Phase 4.12 — Short-term Rentals: **COMPLETE | VERIFIED**.
- Phase 4.13 — AppFolio CSV/XLSX migration: **IN PROGRESS**.
- Verified PRODUCT SHA: `25a90d9119f21767bff8f5b8c9cbda2c8c43e0ae`.
- GitHub Actions run: `36945450640` — SUCCESS.
- All six required CI jobs passed:
  - frontend: PASS
  - backend: PASS
  - security: PASS
  - platform-admin: PASS
  - staging-config: PASS
  - authenticated E2E: PASS
- Backend/PostgreSQL: **894 passed, 21 deselected, 23979 warnings in 269.53s**.
- Authenticated E2E: **21 passed, 278 warnings in 103.57s**.
- Alembic head: `c35e9d2a7b14`.
- Expected model tables remain **201**.
- Navigation integrity and the `HIDDEN MENU / UNHIDE ROADMAP` remain unchanged.
- `docs/UX_STANDARDS.md` remains AUTHORIZED BUT NOT ACTIVE.

## Verified staged Unit match/create/skip reconciliation

1. Staged Unit rows now carry a correctly typed `resolution_target_unit_id`; Unit IDs are not stored in the Property resolution foreign key.
2. Unresolved same-property Unit matches support explicit `MATCH_EXISTING`, `CREATE_NEW`, and `SKIP` decisions.
3. `MATCH_EXISTING` accepts only an active Unit under the already mapped same-organization Property and never overwrites the target Unit.
4. `CREATE_NEW` overrides only the exact reviewed same-property possible-match blocker; identity and Property-link validation remain fail-closed.
5. Exact same-property Unit create collisions fail closed unless the reviewed staged row explicitly carries `CREATE_NEW`.
6. `SKIP` is durable and removes the staged row from dry-run/commit input.
7. Resolution changes are audited and invalidate the prior run dry-run fingerprint.
8. Unit resolution state and typed target identity participate in the staged review/relationship fingerprint.
9. Controlled Unit commit still derives only from reviewed staged rows, preserves exact-fingerprint commit semantics, plan-limit checks and durable UNITS source mappings, and replays without duplicate Units.
10. Mixed matched/new/skipped resolution behavior is covered by focused regressions.
11. No Owners/Vendors, Tenants, Leases/occupancy, accounting history, AppFolio API connector, navigation change, or general UX work was added in this verified batch.

Implementation/source commits include:
- `9a1cc6deae69debb9124ead996dde16c07caab28` — typed Unit resolution target.
- `fbdc1e93db960e7e8858c13149bf053429e75e25` — Unit-resolution migration.
- `0de98cf12a9fb51f370a4be0a9904f5f03a7a72b`, `98177fb56096f65e1126d5f7a174ac5b1a96c292` — staged Unit resolution wiring and commit behavior.
- `1312d017b4e5ee41f2d224b6f26c0ef2ac94f757`, `f1a5b78c06f8d82fcb11047c095168bf0029d52b` — focused reconciliation regressions.
- `25a90d9119f21767bff8f5b8c9cbda2c8c43e0ae` — explicit CREATE_NEW disclosure; final VERIFIED PRODUCT SHA.

## Exact next Phase 4.13 product batch

Proceed in dependency order to **Owner Directory / Vendor Directory source-schema verification and staging support**.

Start with the smallest independently verifiable resource (Owner Directory or Vendor Directory) whose public/export schema can be verified. Required boundaries:

1. Reuse the existing shared CSV/XLSX upload, detection, column-mapping, staging, validation, fingerprint, replay/idempotency, audit and recovery architecture.
2. Do not create a parallel migration system.
3. Map only fields verified from an authoritative or otherwise reliable AppFolio export schema. Do not infer target-only fields.
4. Preserve stable source IDs whenever supplied.
5. The first Owner/Vendor batch is staging-only: no customer Owner/Vendor mutation yet.
6. Possible existing target matches must be surfaced for explicit review; never overwrite automatically.
7. Missing required identity/contact fields remain REVIEW/INVALID rather than fabricated.
8. Do not proceed to Tenants until Owners/Vendors staging/reconciliation dependency is verified.
9. Do not implement AppFolio API transport or general UX work.
10. Preserve navigation integrity, the hidden-menu roadmap, organization isolation, audit/idempotency and recovery visibility.

---

# AI_HANDOFF.md — 2026-10-01 PHASE 4.13 UNIT DRY-RUN + CONTROLLED COMMIT VERIFIED

## Current verified product checkpoint

- Phase 4.11 — Senior Housing: **COMPLETE | VERIFIED**.
- Phase 4.12 — Short-term Rentals: **COMPLETE | VERIFIED**.
- Phase 4.13 — AppFolio CSV/XLSX migration: **IN PROGRESS**.
- Verified PRODUCT SHA: `85ce6fec9eac9ce2ab1b4302b7b6ad27b01e298d`.
- GitHub Actions run: `36940824955` — SUCCESS.
- All six required CI jobs passed:
  - frontend: PASS
  - backend: PASS
  - security: PASS
  - platform-admin: PASS
  - staging-config: PASS
  - authenticated E2E: PASS
- Backend/PostgreSQL: **893 passed, 21 deselected, 23942 warnings in 357.98s**.
- Authenticated E2E: **21 passed, 278 warnings in 111.79s**.
- Alembic head remains `b24d8c1f4a62`.
- Expected model tables remain **201**.
- Navigation integrity and the `HIDDEN MENU / UNHIDE ROADMAP` remain unchanged.
- `docs/UX_STANDARDS.md` remains AUTHORIZED BUT NOT ACTIVE.

## Verified staged Unit dry-run + controlled commit

1. Reviewed staged UNITS uploads now have a dedicated dry-run endpoint using the existing run-level exact-fingerprint architecture.
2. Unit -> Property linkage is resolved only through durable AppFolio PROPERTIES source mappings; display-name-only linkage is not used.
3. The Unit source-context fingerprint binds the staged upload/review state plus each referenced durable Property mapping target/fingerprint, so changed relationship state makes the prior preview stale.
4. Unit dry run is target-non-mutating and creates no Unit rows.
5. The basic verified Unit Directory contract maps only the source Unit Name into target `unit_number`; missing bedrooms/bathrooms/monthly rent are explicitly disclosed as target defaults rather than claimed as AppFolio facts.
6. Existing durable UNITS mappings replay safely and must point to a Unit under the same mapped Property.
7. Same-property/same-unit-number target candidates are surfaced as possible matches and **block commit** until explicit Unit resolution is implemented; no automatic overwrite or merge occurs.
8. Controlled Unit commit accepts only the exact latest staged dry-run fingerprint; callers cannot submit arbitrary Unit records.
9. Unit creation is atomic, preflights the existing organization unit-plan limit for the full new-unit count, creates durable UNITS source-to-target mappings and replays without duplicates.
10. A changed Property mapping relationship fingerprint invalidates the old Unit commit preview.
11. No Property mutation, Owners/Vendors, Tenants, Leases/occupancy, accounting history, AppFolio API connector, navigation change, or general UX work was added.

Implementation commits:
- `79b1d8b2b4e02b9adda28462f24b45bc46c6d590` — Unit dry-run/commit engine.
- `e7ffe6d3d4284aa25105ff47f06d1d6e8b8cf110` — Unit migration schemas.
- `5ba54343c86797bb31edf099a5c1aac0cc02f044` — reviewed staged Unit route bridge.
- `85ce6fec9eac9ce2ab1b4302b7b6ad27b01e298d` — focused Unit dry-run/commit regressions; final VERIFIED PRODUCT SHA.

## Exact next Phase 4.13 product batch

Add explicit **staged Unit match/create/skip resolution** before moving to Owners/Vendors.

Required boundaries:

1. Reuse the existing staged-row resolution/fingerprint/audit pattern; do not create a parallel reconciliation system.
2. Because the existing `resolution_target_id` is Property-specific, add a correctly typed Unit-resolution target reference rather than storing Unit IDs in the Property FK column.
3. Support explicit operator decisions for unresolved Unit rows:
   - MATCH_EXISTING to an active Unit under the already mapped same-organization Property;
   - CREATE_NEW despite a reviewed same-property possible match;
   - SKIP.
4. Never overwrite the matched existing Unit.
5. CREATE_NEW may override only the exact reviewed same-property unit-match blocker and must not suppress identity/property-link validation errors.
6. Resolution changes must be durable, audited and invalidate the prior dry-run fingerprint.
7. Unit resolution state and target identity must participate in the staged relationship fingerprint so stale previews cannot commit.
8. Controlled commit must use reviewed staged rows only; mixed matched/new/skipped rows must replay without duplicate Units.
9. Keep organization scope, Property relationship validation, plan-limit enforcement, audit/recovery visibility and exact-fingerprint commit semantics intact.
10. Do not proceed to Owners/Vendors until Unit reconciliation/commit is verified.
11. Do not implement AppFolio API transport or general UX work.

---

# AI_HANDOFF.md — 2026-10-01 PHASE 4.13 UNIT DIRECTORY INGESTION + STAGING VERIFIED

## Current verified product checkpoint

- Phase 4.11 — Senior Housing: **COMPLETE | VERIFIED**.
- Phase 4.12 — Short-term Rentals: **COMPLETE | VERIFIED**.
- Phase 4.13 — AppFolio CSV/XLSX migration: **IN PROGRESS**.
- Verified PRODUCT SHA: `270dc810b3627b8fcc28b90482c946c22b10ea63`.
- GitHub Actions run: `36939396996` — SUCCESS.
- All six required CI jobs passed:
  - frontend: PASS
  - backend: PASS
  - security: PASS
  - platform-admin: PASS
  - staging-config: PASS
  - authenticated E2E: PASS
- Backend/PostgreSQL: **889 passed, 21 deselected, 23885 warnings in 355.35s**.
- Authenticated E2E: **21 passed, 278 warnings in 113.39s**.
- Alembic head remains `b24d8c1f4a62`.
- Expected model tables remain **201**.
- Navigation integrity and the `HIDDEN MENU / UNHIDE ROADMAP` remain unchanged.
- `docs/UX_STANDARDS.md` remains AUTHORIZED BUT NOT ACTIVE.

## Verified Unit Directory ingestion/staging scope

1. The shared AppFolio CSV/XLSX ingestion service now recognizes verified Unit Directory exports in addition to Properties.
2. Recognized Unit fields are intentionally limited to the verified export contract: Unit ID, Unit Name, Property ID, Property Name, Unit Address, Unit Street Address 1/2, Unit City, Unit State and Unit Zip. No target-model-only fields are inferred.
3. Unit Directory detection works for CSV and XLSX, including safe single-supported-sheet auto-selection inside multi-sheet workbooks.
4. Stable Unit ID and Property ID are preserved when supplied.
5. Unit rows use the existing durable Property source-to-target mapping for relationship validation. They are marked NEW only when the referenced source Property ID resolves to an active same-organization Property mapping.
6. Missing Unit ID, missing Property ID, or an unresolved source Property mapping stages the row as REVIEW rather than fabricating identity/linkage.
7. Duplicate Unit source IDs in the same upload fail the affected row as INVALID.
8. A corrupted/wrong-scope durable Property mapping fails closed.
9. Existing durable UNITS mapping is surfaced as ALREADY_MAPPED when present.
10. Equivalent re-upload/replay remains idempotent and creates no duplicate upload/staged rows.
11. This batch is staging-only. It creates **zero customer Unit rows** and does not mutate Properties.
12. No Owners/Vendors, Tenants, Leases/occupancy, accounting history, AppFolio API connector, navigation change, or general UX work was added.

Implementation commits:
- `9041313593db8a6dc8f7da6b803526f546d68b9e` — Unit Directory detect/map/normalize/stage support.
- `c1870088b84c1f48ede189e949bc4674f1a6447f` — cleanup.
- `270dc810b3627b8fcc28b90482c946c22b10ea63` — focused Unit staging regressions; final VERIFIED PRODUCT SHA.

Source-schema evidence used for this bounded batch:
- AppFolio Unit Directory export instructions documenting Unit Name, Property, Property Name, optional Property ID, Unit Address, Unit Street Address 1/2, Unit City, Unit State, Unit Zip and optional Unit ID.
- No unsupported bedrooms/rent/marketing fields were required or invented in this batch.

## Exact next Phase 4.13 product batch

Add a **Unit staged dry-run bridge + controlled commit** only after reconciling the existing target Unit contract against the verified source fields.

Required boundaries:

1. Reuse the existing run, upload, staged-row, durable mapping, exact-fingerprint dry-run/commit and recovery architecture; do not create a parallel migration system.
2. Unit -> Property must resolve through the durable source Property mapping; never link solely by display name.
3. Derive Unit creation only from fields actually present in the verified Unit Directory contract. If the target Unit contract requires information that the verified source does not provide and has no safe default, block the affected row rather than inventing data.
4. A Unit dry run must be target-non-mutating and bind the staged upload/mapping/relationship state into the exact preview fingerprint.
5. Existing durable UNITS mappings must replay safely without duplicate Unit creation.
6. Potential same-property existing Unit matches must be surfaced for explicit review; never overwrite automatically.
7. Controlled commit must require the exact latest reviewed fingerprint and derive its payload from staged rows, not arbitrary caller-supplied Unit records.
8. Any future match/create/skip Unit resolution must be explicit, audited and fingerprint-invalidating.
9. Do not proceed to Owners/Vendors until the Unit commit boundary is verified.
10. Do not implement AppFolio API transport or general UX work.
11. Preserve navigation integrity, hidden-menu roadmap, organization isolation, audit/idempotency and recovery visibility.

---

# AI_HANDOFF.md — 2026-10-01 PHASE 4.13 STAGED PROPERTY RESOLUTION + CONTROLLED COMMIT VERIFIED

## Current verified product checkpoint

- Phase 4.11 — Senior Housing: **COMPLETE | VERIFIED**.
- Phase 4.12 — Short-term Rentals: **COMPLETE | VERIFIED**.
- Phase 4.13 — AppFolio CSV/XLSX migration: **IN PROGRESS**.
- Verified PRODUCT SHA: `d7b80dd2fd165a6cd9961451a5fcf14e3881da0a`.
- GitHub Actions run: `36934014003` — SUCCESS.
- All six required CI jobs passed:
  - frontend: PASS
  - backend: PASS
  - security: PASS
  - platform-admin: PASS
  - staging-config: PASS
  - authenticated E2E: PASS
- Backend/PostgreSQL: **886 passed, 21 deselected, 23841 warnings in 384.54s**.
- Authenticated E2E: **21 passed, 278 warnings in 113.98s**.
- Alembic head: `b24d8c1f4a62`.
- Expected model tables: **201**.
- Navigation integrity and the `HIDDEN MENU / UNHIDE ROADMAP` remain unchanged.
- `docs/UX_STANDARDS.md` remains AUTHORIZED BUT NOT ACTIVE.

## Verified staged-property resolution + controlled commit

1. Reviewed staged Property rows now support explicit `MATCH_EXISTING`, `CREATE_NEW`, and `SKIP` decisions.
2. Match-to-existing validates the same organization and exact Property target before creating/preserving durable source-to-target mapping; it never overwrites the existing Property.
3. Create-new overrides only the reviewed possible-match disposition for that exact staged row; unrelated validation remains blocking.
4. Skip is explicit and durable for staging/review and excluded from target creation.
5. Resolution changes are audited and invalidate the prior run dry-run fingerprint.
6. The reviewed row-resolution state participates in the staged source-context fingerprint, so stale previews cannot commit.
7. Controlled staged commit derives its payload only from reviewed staged rows and requires the exact latest dry-run fingerprint; callers cannot resubmit arbitrary Property records through this endpoint.
8. Durable existing mappings remain replay-safe; mixed matched/new rows do not duplicate targets.
9. Migration `b24d8c1f4a62_appfolio_staged_property_resolution.py` adds reviewed-resolution metadata to staged rows. The follow-up compatibility fix uses Alembic batch mode so the legacy SQLite upgrade drill and PostgreSQL both preserve the intended foreign-key/index contract.
10. No existing customer Property is overwritten automatically and no missing source data is fabricated.
11. No Unit import, accounting-history import, AppFolio API connector, navigation change, or general UX work was added.

Implementation commits:
- `7954f2c630f2dd02ba24007b37e8d1d0ae42491f` — staged Property resolution + controlled commit.
- `d7b80dd2fd165a6cd9961451a5fcf14e3881da0a` — migration-compatibility fix and final verified PRODUCT SHA.

## Exact next Phase 4.13 product batch

Proceed in dependency order with **Unit Directory CSV/XLSX ingestion and staging only**.

Required boundaries:

1. Reuse the existing `PlatformMigrationRun`, `PlatformMigrationUpload`, `PlatformMigrationStagedRow`, column-mapping, fingerprint, replay/idempotency and audit architecture; do not create a parallel migration system.
2. Add Unit Directory detection/normalization only from verified AppFolio export columns. The current verified external export contract includes Unit Name, Property, Property Name, optional Property ID, Unit Address, Unit Street Address 1/2, Unit City, Unit State, Unit Zip and optional Unit ID. Do not infer extra source fields from the target Unit model.
3. Preserve stable source Unit ID and source Property ID when supplied. Unit -> Property linkage must use durable AppFolio source IDs/mappings where available; never link solely by display name when an ID relationship is expected.
4. The first Units batch is **staging-only**: detect, map, normalize, validate and persist reviewed staging state. Do not create customer Unit rows yet.
5. Missing/unresolved source Property linkage must mark the Unit row for REVIEW/INVALID and block unsafe later commit.
6. Existing committed Property source-to-target mappings may be used only to surface deterministic relationship status; do not mutate Properties.
7. Re-upload/replay must remain idempotent and a changed file/mapping must invalidate the prior dry-run fingerprint.
8. Do not automatically overwrite existing customer records or invent missing values.
9. Do not add Owners/Vendors, Tenants, Leases/occupancy, accounting history, maintenance or attachments in this batch.
10. Do not implement the AppFolio API connector.
11. Preserve navigation integrity, the hidden-menu roadmap, platform-role boundaries, organization isolation, audit/recovery visibility and inactive UX standards.

---

# AI_HANDOFF.md — 2026-10-01 PHASE 4.13 STAGED PROPERTY DRY-RUN BRIDGE VERIFIED

## Current verified product checkpoint

- Phase 4.11 — Senior Housing: **COMPLETE | VERIFIED**.
- Phase 4.12 — Short-term Rentals: **COMPLETE | VERIFIED**.
- Phase 4.13 — AppFolio CSV/XLSX migration: **IN PROGRESS**.
- Verified PRODUCT SHA: `f5e2c1fe524fa421f2b5da7153d2a19ca86951d7`.
- GitHub Actions run: `36931188442` — SUCCESS.
- All six required CI jobs passed:
  - frontend: PASS
  - backend: PASS
  - security: PASS
  - platform-admin: PASS
  - staging-config: PASS
  - authenticated E2E: PASS
- Backend/PostgreSQL: **882 passed, 21 deselected, 23761 warnings in 383.84s**.
- Authenticated E2E: **21 passed, 278 warnings in 109.24s**.
- Alembic head remains `f13c7a9e2b40`.
- Expected model tables remain **201**.
- Navigation integrity and the `HIDDEN MENU / UNHIDE ROADMAP` remain unchanged.
- `docs/UX_STANDARDS.md` remains AUTHORIZED BUT NOT ACTIVE.

## Verified staged Properties -> existing dry-run bridge

1. A staged `PROPERTIES` upload now has a dedicated dry-run endpoint that reuses the existing verified `dry_run_properties` engine.
2. Only rows without unresolved `INVALID`, `POSSIBLE_MATCH`, or `REVIEW` dispositions may progress.
3. Staged normalized rows are converted into the canonical existing property dry-run input; no second property preview engine exists.
4. The upload normalized fingerprint is included as the dry-run source-context fingerprint, so changed file/mapping state changes the exact dry-run identity.
5. The run-level `last_dry_run_fingerprint` / exact-preview contract remains authoritative.
6. The staged dry run is target-non-mutating and creates no customer Property rows.
7. Existing `ALREADY_MAPPED` rows remain replay-visible and organization/run scope fails closed.
8. Replaying the identical staged upload/dry run does not duplicate its audit event.
9. The staged dry-run endpoint is exposed through the existing platform AppFolio migration router.
10. No AppFolio API connector, accounting-history import, navigation change, or general UX work was added.

Implementation commits in this verified batch:
- `2110c07caefbe8dcbc128472b5015933b491f9d7` — staged Properties -> existing dry-run bridge and focused regressions.
- `f5e2c1fe524fa421f2b5da7153d2a19ca86951d7` — corrected replay warning assertion; final VERIFIED PRODUCT SHA.

## Exact next Phase 4.13 product batch

Add explicit **safe staged-property match resolution + controlled commit** before moving to Units.

Required boundaries:

1. Reuse the existing `PlatformMigrationRun`, staged upload/rows, `PlatformMigrationItem`, `dry_run_properties` and `commit_properties` architecture; do not create a parallel migration path.
2. Support explicit operator decisions for unresolved property rows: match to an existing same-organization Property, create new despite a reviewed possible match, or skip.
3. A match-to-existing decision must create/preserve the durable source-to-target mapping only after exact organization/resource/source validation; never overwrite the target Property.
4. A create-new decision may override only the reviewed possible-match blocker for that exact staged source row; it must not suppress unrelated validation or identity errors.
5. A skip decision must be explicit, durable for staging/review, and excluded from target creation.
6. Every resolution change must be audited and must invalidate the prior run dry-run fingerprint.
7. The reviewed resolution state must be included in the staged dry-run/commit source-context fingerprint so stale previews cannot commit.
8. Controlled staged commit must derive its payload from the reviewed staged rows and require the exact latest reviewed dry-run fingerprint; callers must not resubmit arbitrary property records.
9. Existing durable mappings remain replay-safe; mixed resolved/new rows must not duplicate targets.
10. Do not automatically overwrite existing customer records or invent missing source data.
11. Do not add Units, accounting history, or the optional AppFolio API connector in this batch.
12. Preserve navigation integrity, hidden-menu roadmap, organization isolation, audit, recovery visibility and inactive UX standards.

---

# AI_HANDOFF.md — 2026-10-01 PHASE 4.13 CSV/XLSX INGESTION + STAGING VERIFIED

## Current verified product checkpoint

- Phase 4.11 — Senior Housing: **COMPLETE | VERIFIED**.
- Phase 4.12 — Short-term Rentals: **COMPLETE | VERIFIED**.
- Phase 4.13 — AppFolio CSV/XLSX migration: **IN PROGRESS**.
- Verified PRODUCT SHA: `f7fea81f1952a716cb97e50f4b2f888e88c3a54e`.
- GitHub Actions run: `36928650807` — SUCCESS.
- All six required CI jobs passed:
  - frontend: PASS
  - backend: PASS
  - security: PASS
  - platform-admin: PASS
  - staging-config: PASS
  - authenticated E2E: PASS
- Backend/PostgreSQL: **878 passed, 21 deselected, 23708 warnings in 385.20s**.
- Authenticated E2E: **21 passed, 278 warnings in 100.62s**.
- Alembic head: `f13c7a9e2b40`.
- Expected model tables: **201**.
- Navigation integrity and the hidden-menu roadmap remain unchanged.
- `docs/UX_STANDARDS.md` remains AUTHORIZED BUT NOT ACTIVE.

## Verified shared ingestion/staging foundation

The first active batch of `docs/APPFOLIO_MIGRATION_IMPORT_PLAN.md` is verified:

1. CSV and XLSX source files are accepted through the existing platform AppFolio migration run.
2. File size, row count, column count, workbook sheet count, archive entry count and XLSX expanded-size limits fail closed.
3. XLSX is parsed as data only; formula cells and macro-enabled content are rejected and never evaluated/executed.
4. Raw uploaded file bytes are not retained in migration tables.
5. Credential/session-like source columns are rejected; API keys, Client Secrets, tokens, passwords and browser cookies are not stored.
6. Property-directory detection uses only the already verified AppFolio property schema/aliases. Other resource mappings are not invented.
7. Known high-confidence aliases auto-map; uncertain headers require explicit operator mapping.
8. Every upload is attached to the existing `PlatformMigrationRun`; no parallel migration system was created.
9. Staging persists normalized rows only in `PlatformMigrationUpload` / `PlatformMigrationStagedRow` with dispositions including NEW, POSSIBLE_MATCH, ALREADY_MAPPED, REVIEW and INVALID.
10. Validation summary exposes total, valid, warning, invalid, duplicate, possible-existing-match and missing/ambiguous-column counts.
11. Stable AppFolio property source IDs are preserved when supplied.
12. Normalized-source fingerprints bind organization/run, selected sheet, mapping and normalized source rows.
13. Equivalent re-upload/replay is idempotent and does not create duplicate upload/row/audit records.
14. A genuinely new staging or mapping state invalidates the prior run dry-run fingerprint.
15. Existing durable source-to-target mappings are surfaced as ALREADY_MAPPED; likely local matches are warnings/POSSIBLE_MATCH and are never overwritten automatically.
16. Upload/staging creates no Property or other customer business record.
17. Staging and row reads preserve platform role scope, target-organization scope, no-store responses and audit without raw source payloads.

Migration:
- `f13c7a9e2b40_appfolio_file_staging.py`
- adds `platform_migration_uploads` and `platform_migration_staged_rows`.

## Exact next Phase 4.13 product batch

Continue dependency order with **Properties** by connecting a reviewed staged
`PROPERTIES` upload to the existing verified AppFolio property dry-run
contract.

Required boundaries:

1. Reuse `dry_run_properties` and the existing run-level exact-fingerprint model; do not invent a second dry-run engine.
2. Convert only syntactically valid staged property rows into the canonical existing property dry-run input.
3. INVALID rows and unresolved POSSIBLE_MATCH/REVIEW conditions must block unsafe progression rather than be silently ignored.
4. ALREADY_MAPPED rows remain replay-safe and must not create new targets.
5. The staged normalized fingerprint/mapping must be bound into the dry-run identity so a changed file or mapping makes the prior preview stale.
6. The dry run remains target-non-mutating.
7. Do not add accounting-history import.
8. Do not implement the optional AppFolio API connector.
9. Preserve organization isolation, audit, source-to-target mapping, recovery visibility, navigation integrity and inactive UX standards.
10. After the staged-property dry-run bridge is verified, add explicit safe match-resolution / controlled-commit behavior as its own bounded batch before moving to Units.

---

# AI_HANDOFF.md — 2026-10-01 PHASE 4.13 CSV/XLSX MIGRATION DIRECTION AUTHORIZED

## Owner decision — authoritative Phase 4.13 direction

Phase 4.13 is **not blocked by AppFolio API access**.

The primary supported AppFolio migration path is now:

`AppFolio CSV/XLSX exports -> upload -> detect -> map -> stage -> validate ->
review -> reconcile -> dry run -> controlled commit`

Permanent implementation contract:
`docs/APPFOLIO_MIGRATION_IMPORT_PLAN.md`.

API research remains preserved at:
`docs/APPFOLIO_API_RESEARCH.md`.

The AppFolio API is an optional later transport/testing adapter only. It must
feed the same migration staging/dry-run/reconciliation/commit contracts and
must not use undocumented browser/session endpoints as production transport.

## Current verified base before the next product batch

- Phase 4.11 — Senior Housing: **COMPLETE | VERIFIED**.
- Phase 4.12 — Short-term Rentals: **COMPLETE | VERIFIED**.
- Phase 4.13 — AppFolio migration tooling: **IN PROGRESS**.
- Latest verified PRODUCT SHA remains
  `87614632efd2aa5ddb7d641d49d6846c4f74a7fc`.
- Latest verified product CI remains `36903338715` SUCCESS.
- Backend/PostgreSQL at that product checkpoint: **873 passed, 21 deselected**.
- Authenticated E2E: **21 passed**.
- Later handoff/docs checkpoint `d6d3e43b6d924407a465a95b9965ef4649349c40`
  also passed all six jobs in CI `36904752581`.
- API-research documentation checkpoint
  `d716d8c5afff78d08722f1b8ccdf4be357bbc1c2` passed all six jobs in
  CI `36923805971`.
- Alembic remains `e57c9b1d3f20`; expected tables remain **199**.
- Navigation integrity and the hidden-menu roadmap remain unchanged.
- UX remains **AUTHORIZED BUT NOT ACTIVE**.

## Exact next Phase 4.13 product batch

Build the **shared CSV/XLSX file-ingestion + staging foundation** by extending
the existing verified platform migration architecture.

First bounded product batch must focus on:

1. bounded CSV and XLSX ingestion;
2. data-only parsing; never execute spreadsheet formulas/macros;
3. report/file detection foundation;
4. header normalization and known aliases;
5. explicit column mapping when uncertain;
6. staging/preview only — upload itself must not mutate customer business data;
7. validation counts for valid/warning/invalid/duplicate/missing-column rows;
8. stable AppFolio source-ID preservation;
9. deterministic normalized-source fingerprint;
10. replay/re-upload idempotency;
11. organization isolation and audit;
12. safe file/row/workbook limits.

Do **not** begin accounting history import in this first batch.
Do **not** implement the optional AppFolio API connector in this first batch.
Do **not** create a parallel migration system.
Reuse the existing migration run, dry-run, exact-fingerprint commit,
source-to-target mapping and recovery architecture.

After the shared ingestion foundation is verified, continue resource mappings
in dependency order defined by `docs/APPFOLIO_MIGRATION_IMPORT_PLAN.md`.

## Non-negotiable migration rules

- Never automatically overwrite existing customer records.
- Never invent missing business data.
- Possible matches require explicit review/resolution.
- Missing required source data blocks the affected row/resource.
- Deterministic normalization is allowed; ambiguity goes to review.
- Stable provider/source IDs are preferred over name-only relationships.
- Any staging/mapping/correction change invalidates the prior dry-run fingerprint.
- Financial history cannot be called complete until required control totals
  reconcile.
- Never fabricate a balancing journal entry to force reconciliation.
- Preserve organization isolation, audit, accounting safeguards, idempotency
  and recovery visibility.

---

# AI_HANDOFF.md — 2026-10-01 APPFOLIO API RESEARCH PRESERVED

## AppFolio API reference for later testing

- New permanent reference: `docs/APPFOLIO_API_RESEARCH.md`.
- It preserves the official AppFolio Stack API resource/field inventory,
  AppFolio partner page, the mirrored Reports API v2 documentation, and
  third-party AppFolio API implementations for future interoperability testing.
- Source quality is explicitly labeled; mirrored/unofficial material is **not**
  treated as a production provider contract.
- The intended primary migration path may use customer CSV/XLSX exports.
- The optional API path remains available for later testing when a legitimate
  AppFolio test account/authenticated contract is available.
- Do not store API keys, Client Secrets, cookies, access tokens, or raw provider
  credentials in the repository or migration records.
- This documentation-only checkpoint does not change Phase 4.13 product
  behavior, navigation, hidden-menu rules, or inactive UX standards.

---

# AI_HANDOFF.md — 2026-10-01 PHASE 4.13 APPFOLIO MAPPING VISIBILITY VERIFIED

## Current verified product checkpoint

- Phase 4.11 — Senior Housing: **COMPLETE | VERIFIED**.
- Phase 4.12 — Short-term Rentals: **COMPLETE | VERIFIED**.
- Phase 4.13 — AppFolio migration tooling: **IN PROGRESS**.
- Verified PRODUCT SHA: `87614632efd2aa5ddb7d641d49d6846c4f74a7fc`.
- GitHub Actions run: `36903338715` — SUCCESS.
- All six required CI jobs passed on this exact product SHA:
  - frontend: PASS
  - backend: PASS
  - security: PASS
  - platform-admin: PASS
  - staging-config: PASS
  - authenticated E2E: PASS
- Backend/PostgreSQL: **873 passed, 21 deselected, 23646 warnings in 303.24s**.
- Authenticated E2E: **21 passed, 278 warnings in 111.35s**.
- Alembic head remains `e57c9b1d3f20`.
- Expected model tables remain **199**.
- Navigation integrity, planning parity and committed-secret checks passed.
- `docs/NAVIGATION_INTEGRITY_PLAN.md`, the `HIDDEN MENU / UNHIDE ROADMAP`, and inactive `docs/UX_STANDARDS.md` remain unchanged.

## Verified Phase 4.13 batch 3 — read-only source mapping / recovery visibility

1. Platform operators with authorized read roles can list durable AppFolio source-to-target migration mappings for a run without exposing raw provider payloads or credentials.
2. Reads are bounded, support optional resource filtering, and return `Cache-Control: no-store`.
3. Property mappings resolve only same-organization target Property records; missing target records are surfaced as `target_exists=false` rather than repaired or recreated.
4. Mapping reads are read-only and create no customer Property, accounting, audit-repair, or provider-side mutations.
5. PLATFORM_SUPPORT remains read-only; PLATFORM_SALES is denied.
6. Mapping organization/provider scope is validated against the migration run. Inconsistent durable mappings fail closed instead of silently returning an empty list or appearing to rebind to another organization.
7. The initial source commit `0f37fd8445f8f333bd3fe544a88eb41b1ce0b61d` failed hosted backend tests because the router omitted the `Property` import.
8. Scoped correction `272b732e9e840205c3dbfe60d2fe86edc27aa6a3` restored the target lookup, then CI exposed the intended fail-closed scope regression.
9. Final correction `87614632efd2aa5ddb7d641d49d6846c4f74a7fc` rejects migration-run/mapping organization or provider inconsistencies; this is the verified PRODUCT SHA.

## Exact next Phase 4.13 work

1. Live AppFolio transport remains **BLOCKED pending an authoritative authenticated provider contract**. Do not invent credentials, endpoints, resource fields, pagination, rate-limit semantics or source schemas.
2. Do not invent Unit, People, Lease or accounting mappings from target models.
3. If authoritative AppFolio authentication/resource documentation becomes available, reconcile it against the verified run/dry-run/commit/mapping contracts before implementing transport.
4. Preserve the dry-run-before-commit boundary, source-to-target mapping idempotency, organization isolation, audit integrity and customer accounting immutability.
5. Preserve navigation integrity, the hidden-menu roadmap and inactive UX standards.

---

# AI_HANDOFF.md — 2026-10-01 PHASE 4.13 APPFOLIO PROPERTY COMMIT VERIFIED

## Current verified product checkpoint

- Phase 4.11 — Senior Housing: **COMPLETE | VERIFIED**.
- Phase 4.12 — Short-term Rentals: **COMPLETE | VERIFIED**.
- Phase 4.13 — AppFolio migration tooling: **IN PROGRESS**.
- Verified PRODUCT SHA: `70c4c31d750a476ba7e20e7841e79d2eca40f4ad`.
- GitHub Actions run: `36892418691` — SUCCESS.
- All six required CI jobs passed on this exact product SHA:
  - frontend: PASS
  - backend: PASS
  - security: PASS
  - platform-admin: PASS
  - staging-config: PASS
  - authenticated E2E: PASS
- Backend/PostgreSQL: **871 passed, 21 deselected, 23617 warnings in 337.92s**.
- Authenticated E2E: **21 passed, 278 warnings in 118.18s**.
- Alembic head: `e57c9b1d3f20`.
- Expected model tables: **199**.
- Navigation integrity, planning parity and committed-secret checks passed in hosted CI.
- `docs/NAVIGATION_INTEGRITY_PLAN.md`, the `HIDDEN MENU / UNHIDE ROADMAP`, and inactive `docs/UX_STANDARDS.md` were preserved.

## Verified Phase 4.13 batch 2 — replay-safe AppFolio property commit

1. Registered the existing platform AppFolio migration router in the running FastAPI application; the previously tested endpoints are now actually exposed.
2. Added durable `platform_migration_items` source-to-target mappings keyed by migration run, resource and AppFolio source ID.
3. Property commit requires the exact payload fingerprint from the latest dry run. Changed/stale payloads fail closed.
4. Commit is atomic for the importable property set and blocks any dry run that still contains invalid rows.
5. Possible existing-target property matches block commit rather than silently creating duplicates; no automatic merge decision is made.
6. A successful commit creates only the already-previewed target Property fields and records source ID -> target Property ID mappings.
7. Identical commit replay returns the existing target mappings and creates no duplicate Property or duplicate commit audit event.
8. Missing/inconsistent/partial prior mappings fail closed for manual review.
9. Commit audit metadata records counts, fingerprint and target IDs only; provider credentials and raw source payload are not stored.
10. Migration `e57c9b1d3f20` adds the mapping table and model/bootstrap parity is restored at 199 tables.
11. Focused regressions cover exact-fingerprint enforcement, commit/replay behavior, target-conflict blocking, route exposure, credential-field rejection and migration parity.
12. First CI `36891558535` exposed two focused test defects: replay conflict detection occurred before own-source mapping recognition, and the route assertion inspected a wrapper lacking `.path`. Scoped correction `70c4c31d750a476ba7e20e7841e79d2eca40f4ad` fixed both; final CI is green.
13. Live AppFolio transport remains explicitly **NOT IMPLEMENTED**. Public AppFolio material confirms API availability by product plan, but no authenticated customer-specific transport/resource contract has been supplied to this repository; do not invent credentials, endpoints or source fields.

## Exact next Phase 4.13 work

1. Continue to seek authoritative AppFolio authentication/resource contracts before implementing any live connector or new resource mapper.
2. Do **not** invent Unit/People/Lease/accounting source fields from target models.
3. Independently actionable while transport/resource schemas remain unavailable: add read-only source-mapping/recovery visibility for committed migration items so platform operators can verify exactly which provider source IDs map to which target records without raw source payloads.
4. Preserve platform-role boundaries, active target organization checks, no-store reads, audit integrity and organization isolation.
5. Keep the dry-run-before-commit boundary; do not broaden property commit into automatic merge or overwrite behavior.
6. Preserve navigation integrity, hidden-menu roadmap and inactive UX standards.

---

# AI_HANDOFF.md — 2026-10-01 PHASE 4.13 APPFOLIO MIGRATION FOUNDATION VERIFIED

## Current verified product checkpoint

- Phase 4.11 — Senior Housing: **COMPLETE | VERIFIED**.
- Phase 4.12 — Short-term Rentals: **COMPLETE | VERIFIED**.
- Phase 4.13 — AppFolio migration tooling: **IN PROGRESS**.
- Verified PRODUCT SHA: `d0177f767320867b2e3925043c7b3950eec3924d`.
- GitHub Actions run: `36885305855`, attempt 2 — SUCCESS.
- All six required CI jobs passed on this exact product SHA:
  - frontend: PASS
  - backend: PASS
  - security: PASS
  - platform-admin: PASS
  - staging-config: PASS
  - authenticated E2E: PASS
- Backend/PostgreSQL: **868 passed, 21 deselected, 23584 warnings in 336.53s**.
- Authenticated E2E: **21 passed, 278 warnings in 120.04s**.
- Alembic head: `d46f8a0c2e91`.
- Expected model tables: **198**.
- Navigation integrity and parity checks passed in hosted CI.
- Attempt 1 staging-config failed only because Docker frontend `npm ci` hit a transient `ECONNRESET`; the same staging job passed on retry without product-code changes.
- `docs/NAVIGATION_INTEGRITY_PLAN.md`, the `HIDDEN MENU / UNHIDE ROADMAP`, and inactive `docs/UX_STANDARDS.md` were preserved.

## Verified Phase 4.13 batch 1 — platform AppFolio migration foundation

1. Added provider-labelled platform migration-run metadata scoped to an active target customer organization.
2. Platform migration records store no provider password, API key, access token, refresh token or raw provider payload.
3. Platform ADMIN/TECH/DEV may create/write migration runs; SUPPORT is read-only; SALES is denied.
4. AppFolio property dry-run accepts bounded explicit source records, validates/maps them into the existing Property contract and creates **no target Property rows**.
5. Dry runs explicitly handle hidden AppFolio records, duplicate source IDs, required fields, bounded field lengths and property-type mapping warnings.
6. Existing likely target matches are surfaced as warnings rather than silently duplicated.
7. Dry-run fingerprints are deterministic and replay-safe; an identical replay does not add a second dry-run audit event.
8. Run creation and first dry-run execution are audit logged without raw payloads or credentials.
9. Added hand-written Alembic migration `d46f8a0c2e91` and restored model-registry/bootstrap parity at 198 tables.
10. Focused regressions verify platform-role boundaries, active-target-org scope, no-store reads, replay behavior, no target mutation, existing-target warnings and rejection of credential-like extra fields.
11. This batch does **not** claim live AppFolio API connectivity. No authenticated customer/provider transport contract or provider credential storage exists yet.

## Exact next Phase 4.13 work

Continue the platform-run **direct AppFolio migration** roadmap without conflating it with the separate customer CSV importer:

1. Verify the current authoritative AppFolio API authentication/transport and resource contracts before implementing any live connector. Do not invent provider endpoints, fields or credential semantics.
2. If an authenticated provider contract is not available, keep live transport explicitly blocked and continue only with independently verifiable mapping/dry-run work backed by authoritative source schemas.
3. Preserve the dry-run-before-commit boundary. Do not mutate customer Property/Unit/People/Lease/accounting records merely because a source record validates.
4. Any later commit step must define explicit conflict/idempotency behavior and preserve organization isolation, audit, accounting immutability and rollback safety.
5. Keep navigation integrity, hidden-menu roadmap and inactive UX standards unchanged unless a real verified customer route ships under the documented unhide rule.

---

# AI_HANDOFF.md — 2026-10-01 PHASE 4.12 COMPLETE | VERIFIED

## Final Phase 4.12 product checkpoint

- **PHASE 4.12 COMPLETE | VERIFIED**
- Phase 4.11 — Senior Housing remains **COMPLETE | VERIFIED**.
- Final VERIFIED PRODUCT SHA: `a418d713a9859a2c91ff6589c29ccb61ddd8637a`.
- GitHub Actions run: `36871808980` — SUCCESS.
- All six required CI jobs passed on this exact product SHA:
  - frontend: PASS
  - backend: PASS
  - security: PASS
  - platform-admin: PASS
  - staging-config: PASS
  - authenticated E2E: PASS
- Backend/PostgreSQL: **864 passed, 21 deselected, 23552 warnings in 332.37s**.
- Authenticated E2E: **21 passed, 278 warnings in 120.60s**.
- Alembic head: `c35e7a9b1d4f`.
- Expected model tables: **197**.
- Navigation integrity and planning parity passed in hosted CI.
- `docs/NAVIGATION_INTEGRITY_PLAN.md`, the `HIDDEN MENU / UNHIDE ROADMAP`, and inactive `docs/UX_STANDARDS.md` were preserved.

## Verified Phase 4.12 Short-term Rentals scope

1. Hidden release gate `release.properties.short_term_rentals` controls the property surface independently of menu-route readiness.
2. Staff-recorded Airbnb/Vrbo references preserve provider, staff label, external listing reference, public URL and notes only; no credentials or live provider connection is claimed.
3. Dated nightly pricing is explicit local operational metadata per property/unit/date with minimum-stay notes; no provider pricing synchronization or accounting posting is represented.
4. Turnover schedules are explicit property/unit time windows with operational status and optional references to already-existing same-unit work-order and inspection records.
5. Turnover records never create, advance, close or otherwise mutate referenced maintenance/inspection workflows.
6. ADMIN/OWNER may write; assigned MANAGER is read-only; cross-organization, unassigned-property and foreign-unit access fails closed.
7. Short-term-rental CRUD mutations are audit logged; reads are `no-store`; setup creates no booking, lease, Charge, invoice, receipt, payout or GL entry.
8. The customer property page exposes a gated **Short-term Rentals** tab covering:
   - Airbnb/Vrbo channel references;
   - local nightly pricing;
   - turnover scheduling.
9. Dedicated authenticated browser coverage verifies one complete customer flow through all three surfaces.
10. No hidden sidebar item was added or unhidden, and no navigation/UX contract changed.

Final customer UI/E2E commits:
- `4fd70baf982d9a1e62505d215866566f8de8a2aa` — Short-term Rentals property UI.
- `6f2f5220c7ce5f3ed6de67769156ab3030e3af19` — gated property-tab integration.
- `aa813a8ef5c00c76c2c0f951be07ae114d1145c9` — dedicated authenticated browser coverage.
- `a418d713a9859a2c91ff6589c29ccb61ddd8637a` — E2E import-safety correction; final VERIFIED PRODUCT SHA.

## Exact next phase

Proceed to **Phase 4.13 — AppFolio migration tooling** from `docs/PLAN_GAPS.md`.

Before implementation:
- reconcile any existing CSV/import/migration primitives;
- distinguish platform-run direct AppFolio migration from already-planned customer CSV import;
- do not claim live AppFolio API connectivity without an actual authenticated provider contract;
- begin with the smallest independently verifiable migration foundation.

---

# AI_HANDOFF.md — 2026-10-01 PHASE 4.12 TURNOVER SCHEDULING VERIFIED

## Current verified product checkpoint

- Phase 4.11 — Senior Housing: **COMPLETE | VERIFIED**.
- Phase 4.12 — Short-term Rentals: **IN PROGRESS**.
- Verified PRODUCT SHA: `ce2dca976170e415b0356456c9779144a355c1ea`.
- GitHub Actions run: `36869468385` — SUCCESS.
- All six required CI jobs passed on this exact product SHA:
  - frontend: PASS
  - backend: PASS
  - security: PASS
  - platform-admin: PASS
  - staging-config: PASS
  - authenticated E2E: PASS
- Backend/PostgreSQL: **864 passed, 20 deselected, 23552 warnings in 346.18s**.
- Authenticated E2E: **20 passed, 274 warnings in 111.11s**.
- Alembic head: `c35e7a9b1d4f`.
- Expected model tables: **197**.
- Navigation integrity and planning parity passed in hosted CI.
- `docs/NAVIGATION_INTEGRITY_PLAN.md`, the `HIDDEN MENU / UNHIDE ROADMAP`, and inactive `docs/UX_STANDARDS.md` were not changed.

## Verified Phase 4.12 batch 3 — turnover scheduling

- Added property/unit-scoped `ShortTermRentalTurnover` schedule records with explicit start/end timestamps and operational status.
- Turnovers may reference an already-existing cleaning work order and/or explicit unit-inspection record for the same property/unit.
- Turnover records never create, advance, close, or otherwise mutate work orders or inspection records.
- No reservation ID, booking ID, guest identity, provider calendar event or provider synchronization is represented.
- ADMIN/OWNER may write; assigned MANAGER is read-only; other roles fail closed.
- Cross-organization, unassigned-property, foreign-unit and mismatched work-order/inspection links fail closed.
- Duplicate unit/start schedules fail closed; invalid schedule windows/statuses are rejected.
- CRUD mutations are audit logged and reads are `no-store`.
- Turnover scheduling creates no Charge or GL transaction.
- Existing Phase 5 maintenance/navigation behavior remains untouched.

## Exact next Phase 4.12 work

1. Add the gated customer **Short-term Rentals** property surface covering:
   - staff-recorded Airbnb/Vrbo channel references;
   - dated nightly pricing;
   - turnover scheduling with optional existing work-order/inspection references.
2. Add dedicated authenticated browser coverage for the customer flow.
3. Verify all six jobs on the exact final product SHA.
4. Update this handoff to **PHASE 4.12 COMPLETE | VERIFIED** before Phase 4.13.

---

# AI_HANDOFF.md — 2026-10-01 PHASE 4.12 NIGHTLY PRICING VERIFIED

## Current verified product checkpoint

- Phase 4.11 — Senior Housing: **COMPLETE | VERIFIED**.
- Phase 4.12 — Short-term Rentals: **IN PROGRESS**.
- Verified PRODUCT SHA: `f946f69c122bfd0943a6530cc8c0dadc2a945926`.
- GitHub Actions run: `36827997620` — SUCCESS.
- All six required CI jobs passed on this exact product SHA:
  - frontend: PASS
  - backend: PASS
  - security: PASS
  - platform-admin: PASS
  - staging-config: PASS
  - authenticated E2E: PASS
- Backend/PostgreSQL: **862 passed, 20 deselected, 23488 warnings in 337.21s**.
- Authenticated E2E: **20 passed, 274 warnings in 110.68s**.
- Alembic head: `b24d6f8a0c3e`.
- Expected model tables: **196**.
- Navigation integrity and planning parity passed in hosted CI.
- `docs/NAVIGATION_INTEGRITY_PLAN.md`, the `HIDDEN MENU / UNHIDE ROADMAP`, and inactive `docs/UX_STANDARDS.md` were not changed.

## Verified Phase 4.12 batch 2 — staff-entered nightly pricing

- Added property/unit-scoped `ShortTermRentalNightlyPrice` records for explicit dated nightly rates.
- Nightly pricing is independent of Airbnb/Vrbo provider records and contains no provider credential or synchronization claim.
- Records support unit, night date, nightly rate, minimum stay and notes.
- ADMIN/OWNER may write; assigned MANAGER is read-only; other roles fail closed.
- Cross-organization, unassigned-property and foreign/inactive-unit access fails closed.
- Duplicate unit/date records fail closed.
- CRUD mutations are audit logged and reads are `no-store`.
- Pricing records create no booking, lease, Charge, invoice, receipt, payout or GL transaction.
- Focused regressions verify scope, feature revocation, validation, duplicate protection, audit logging and zero Charge/GL mutation.

## Exact next Phase 4.12 work

Continue the authoritative `docs/PLAN_GAPS.md` scope:

1. **Turnover scheduling** — reconcile the existing work-order/inspection primitives and add the smallest property/unit-scoped short-term-rental turnover contract without fabricating reservation/channel synchronization.
2. Add the gated customer Short-term Rentals surface and dedicated authenticated browser coverage after backend contracts are verified.
3. Final exact-SHA six-job verification, then mark **PHASE 4.12 COMPLETE | VERIFIED** before Phase 4.13.

---

# AI_HANDOFF.md — 2026-10-01 PHASE 4.12 SHORT-TERM RENTAL CHANNEL FOUNDATION VERIFIED

## Current verified product checkpoint

- Phase 4.11 — Senior Housing: **COMPLETE | VERIFIED**.
- Phase 4.12 — Short-term Rentals: **IN PROGRESS**.
- Verified PRODUCT SHA: `2f7238f1db61eb9550f1d2da8899cc42f672c99b`.
- GitHub Actions run: `36826674455` — SUCCESS.
- All six required CI jobs passed on this exact product SHA:
  - frontend: PASS
  - backend: PASS
  - security: PASS
  - platform-admin: PASS
  - staging-config: PASS
  - authenticated E2E: PASS
- Backend/PostgreSQL: **860 passed, 20 deselected, 23430 warnings in 284.73s**.
- Authenticated E2E: **20 passed, 274 warnings in 115.95s**.
- Alembic head: `a13c5e7f9b2d`.
- Expected model tables: **195**.
- Navigation integrity and planning parity passed in hosted CI.
- `docs/NAVIGATION_INTEGRITY_PLAN.md`, the `HIDDEN MENU / UNHIDE ROADMAP`, and inactive `docs/UX_STANDARDS.md` were not changed.

## Verified Phase 4.12 batch 1 — Airbnb / Vrbo channel-reference foundation

- Added hidden release gate `release.properties.short_term_rentals`.
- Added property/organization-scoped `ShortTermRentalChannel` records for explicit staff-entered Airbnb or Vrbo listing references.
- Records may contain provider, staff label, external listing identifier, public listing URL and notes.
- ADMIN/OWNER may write; assigned MANAGER is read-only; other roles fail closed.
- Cross-organization and unassigned-property access fails closed.
- CRUD mutations are audit logged and reads are `no-store`.
- Duplicate provider/label references fail closed.
- Channel references contain no access token, refresh token, API key, password, reservation/booking linkage, payout amount or nightly rate.
- This batch does **not** claim live Airbnb/Vrbo API connectivity, OAuth authorization, scraping, reservation/calendar synchronization, payouts or pricing synchronization.
- Focused regressions verify scope, feature revocation, duplicate handling, audit logging, schema boundaries and zero Charge/GL mutation.

## Exact next Phase 4.12 work

Continue the authoritative `docs/PLAN_GAPS.md` scope:

1. **Nightly pricing** — add explicit property/unit/channel-independent staff pricing rules or dated nightly-price records without claiming provider synchronization or creating accounting entries.
2. **Turnover scheduling** — follow as a separate verified batch; reconcile existing work-order/inspection primitives before implementation.
3. Add the gated customer Short-term Rentals surface and dedicated authenticated browser coverage after backend contracts are verified.
4. Final exact-SHA six-job verification, then mark **PHASE 4.12 COMPLETE | VERIFIED** before Phase 4.13.

---

# AI_HANDOFF.md — 2026-10-01 PHASE 4.11 COMPLETE | VERIFIED

## Final Phase 4.11 product checkpoint

- **PHASE 4.11 COMPLETE | VERIFIED**
- Final VERIFIED PRODUCT SHA: `d8211d003bcd8d58f4514e3c53b4e6932f8df1f8`
- GitHub Actions run: `36818243408` — SUCCESS
- All six required CI jobs passed on this exact product SHA:
  - frontend: PASS
  - backend: PASS
  - security: PASS
  - platform-admin: PASS
  - staging-config: PASS
  - authenticated E2E: PASS
- Backend/PostgreSQL: **857 passed, 20 deselected, 23375 warnings in 316.32s**
- Authenticated E2E: **20 passed, 274 warnings in 111.44s**
- Alembic head: `d19f3a5c7e2b`
- Expected model tables: **194**
- Navigation integrity and parity checks passed in hosted CI.
- `docs/NAVIGATION_INTEGRITY_PLAN.md`, the `HIDDEN MENU / UNHIDE ROADMAP`, and inactive `docs/UX_STANDARDS.md` were preserved.

## Verified Phase 4.11 Senior Housing scope

1. Staff-recorded, property/organization-scoped age-restriction references support 55+, 62+ and other recorded restriction types without inferring resident eligibility or certifying Fair Housing/HOPA compliance.
2. Care-coordination placeholders are a property-level resource/contact directory only and contain no resident linkage, diagnosis, medical notes, treatment plan, medical eligibility or legal-care determination.
3. HUD 202/811 records preserve explicit staff references and evidence-readiness states only. They do not certify HUD eligibility, funding, subsidy, occupancy, resident qualification or payment status.
4. ADMIN/OWNER may write; assigned MANAGER is read-only; cross-organization and unassigned-property access fails closed.
5. Senior Housing CRUD mutations are audit logged and create no Charge or GL transaction.
6. The customer property page exposes a gated **Senior Housing** tab behind `release.properties.senior_housing` covering:
   - age-restriction references;
   - care-resource directory entries;
   - HUD 202/811 readiness references.
7. Dedicated authenticated browser coverage verifies one complete customer flow through all three surfaces and their non-certifying disclosures.
8. The release gate remains separate from menu-route readiness; no hidden sidebar item or navigation contract was changed.

Final UI/E2E commit:
- `d8211d003bcd8d58f4514e3c53b4e6932f8df1f8` — final VERIFIED PRODUCT SHA.

## Exact next phase

Proceed to **Phase 4.12 — Short-term Rentals** from `docs/PLAN_GAPS.md`.

Authoritative planned scope:
- Airbnb / Vrbo integration;
- nightly pricing;
- turnover scheduling.

Before implementing, reconcile live source for any existing short-term-rental/channel/calendar/pricing/turnover primitives and begin with the smallest independently verifiable foundation. Do not fabricate external channel connectivity or booking synchronization without an actual provider contract.

---

# AI_HANDOFF.md — 2026-10-01 PHASE 4.11 SENIOR HOUSING HUD 202/811 BACKEND VERIFIED

## Current verified product checkpoint

- Phase 4.11 — Senior Housing: **IN PROGRESS**
- Verified PRODUCT SHA: `902cb23a8bb30dc725a06fc0818cee88fd2f3a8b`
- GitHub Actions run: `36817150514` — SUCCESS
- All six required CI jobs passed on this exact product SHA:
  - frontend: PASS
  - backend: PASS
  - security: PASS
  - platform-admin: PASS
  - staging-config: PASS
  - authenticated E2E: PASS
- Backend/PostgreSQL: **857 passed, 19 deselected, 23374 warnings in 339.11s**
- Authenticated E2E: **19 passed, 271 warnings in 109.57s**
- Alembic head: `d19f3a5c7e2b`
- Expected model tables: **194**
- Navigation integrity and parity checks passed in hosted CI.
- `docs/NAVIGATION_INTEGRITY_PLAN.md`, the `HIDDEN MENU / UNHIDE ROADMAP`, and inactive `docs/UX_STANDARDS.md` were not changed.

## Verified Phase 4.11 batch 3 — HUD 202/811 recorded readiness facts

- Added property/organization-scoped `SeniorHUDProgram` records for explicit HUD 202 or HUD 811 staff references.
- Records support staff label, recorded authority/reference identifier, readiness status, evidence reference/date, effective dates and notes.
- Readiness states are limited to `REFERENCE_ONLY`, `EVIDENCE_PENDING`, and `EVIDENCE_RECORDED`; evidence-recorded state requires an explicit evidence reference.
- ADMIN/OWNER may write; assigned MANAGER is read-only; other roles fail closed.
- Cross-organization and unassigned-property access fails closed.
- CRUD mutations are audit logged.
- Records do **not** certify HUD eligibility, funding, subsidy, occupancy, resident qualification or payment status and contain no resident/tenant linkage or funding/subsidy amount fields.
- Focused regressions verify scope, validation, duplicate protection, feature revocation, audit logging, no-store reads and zero Charge/GL mutation.

## Exact next Phase 4.11 work

1. Add the gated customer **Senior Housing** property surface covering the three verified backend contracts:
   - age-restriction records;
   - care-resource directory placeholders;
   - HUD 202/811 readiness references.
2. Add dedicated authenticated browser coverage.
3. Verify all six jobs on the exact final product SHA.
4. Update this handoff to **PHASE 4.11 COMPLETE | VERIFIED** before moving to Phase 4.12.

---

# AI_HANDOFF.md — 2026-10-01 PHASE 4.11 SENIOR HOUSING CARE-RESOURCE FOUNDATION VERIFIED

## Current verified product checkpoint

- Phase 4.11 — Senior Housing: **IN PROGRESS**
- Verified PRODUCT SHA: `bcdb6b920d448d9bcf26a3d8e9aba2601f8bbcc7`
- GitHub Actions run: `36815663334` — SUCCESS
- All six required CI jobs passed on this exact product SHA:
  - frontend: PASS
  - backend: PASS
  - security: PASS
  - platform-admin: PASS
  - staging-config: PASS
  - authenticated E2E: PASS
- Backend/PostgreSQL: **855 passed, 19 deselected, 23322 warnings in 195.49s**
- Authenticated E2E: **19 passed, 271 warnings in 107.56s**
- Alembic head: `c08e2f4a6d1b`
- Expected model tables: **193**
- Navigation integrity and parity checks passed in hosted CI.
- `docs/NAVIGATION_INTEGRITY_PLAN.md`, the `HIDDEN MENU / UNHIDE ROADMAP`, and inactive `docs/UX_STANDARDS.md` were not changed.

## Verified Phase 4.11 batch 2 — care coordination placeholders

- Added property/organization-scoped `SeniorCareResource` records as a staff-maintained service/contact directory only.
- Supported recorded resource types: care coordination, transportation, meals, social services, and other.
- Records may contain provider/contact name, phone, email, reference URL and availability notes.
- ADMIN/OWNER may write; assigned MANAGER is read-only; other roles fail closed.
- Cross-organization and unassigned-property access fails closed.
- CRUD mutations are audit logged.
- Care-resource records are intentionally not resident-specific and contain no resident/tenant linkage, diagnosis, medical notes, treatment plan, eligibility field, or legal-care determination.
- Focused regressions verify scope, duplicate protection, feature revocation, audit logging, no-store reads and zero Charge/GL mutation.

## Exact next Phase 4.11 work

Continue the authoritative Phase 4.11 roadmap from `docs/PLAN_GAPS.md`:

1. **HUD 202/811** — explicit staff-recorded program/reference facts and readiness evidence only; do not certify HUD eligibility, funding, occupancy or subsidy status without authoritative evidence.
2. Customer Senior Housing surface + authenticated browser coverage after the backend contracts are verified.
3. Final exact-SHA six-job verification, then mark **PHASE 4.11 COMPLETE | VERIFIED** before moving to Phase 4.12.

---

# AI_HANDOFF.md — 2026-10-01 PHASE 4.11 SENIOR HOUSING AGE-RESTRICTION FOUNDATION VERIFIED

## Current verified product checkpoint

- Phase 4.11 — Senior Housing: **IN PROGRESS**
- Verified PRODUCT SHA: `436b503551a6b45965a5487930f68989ef464d83`
- GitHub Actions run: `36814348487` — SUCCESS
- All six required CI jobs passed on this exact product SHA:
  - frontend: PASS
  - backend: PASS
  - security: PASS
  - platform-admin: PASS
  - staging-config: PASS
  - authenticated E2E: PASS
- Backend/PostgreSQL: **853 passed, 19 deselected, 23270 warnings in 256.10s**
- Authenticated E2E: **19 passed, 271 warnings in 104.89s**
- Alembic head: `bf7d1e3a5c9f`
- Expected model tables: **192**
- Navigation integrity and parity checks passed in hosted CI.
- `docs/NAVIGATION_INTEGRITY_PLAN.md`, the `HIDDEN MENU / UNHIDE ROADMAP`, and inactive `docs/UX_STANDARDS.md` were not changed.

## Verified Phase 4.11 batch 1 — age-restriction foundation

- Added hidden release gate `release.properties.senior_housing`.
- Added property/organization-scoped `SeniorAgeRestriction` records for explicit staff-entered:
  - restriction type (`AGE_55_PLUS`, `AGE_62_PLUS`, or `OTHER_RECORDED`);
  - recorded minimum age;
  - staff label;
  - recorded authority/reference identifier;
  - effective dates and notes.
- ADMIN/OWNER may write; assigned MANAGER is read-only; other roles fail closed.
- Cross-organization and unassigned-property access fails closed.
- CRUD mutations are audit logged.
- Records are operational references only. They do **not** infer resident eligibility, certify HOPA/Fair Housing compliance, establish HUD status, create Charges, or create GL postings.
- Focused regressions verify scope, validation, duplicate protection, feature revocation, audit logging, no-store reads, and zero Charge/GL mutation.

## Exact next Phase 4.11 work

Continue the authoritative Phase 4.11 roadmap from `docs/PLAN_GAPS.md`:

1. **Care coordination placeholders** — property-scoped operational resource/workflow placeholders only; do not store or infer resident diagnoses, medical eligibility, treatment plans, or legal care obligations.
2. **HUD 202/811** — explicit staff-recorded program/reference facts and readiness evidence only; do not certify HUD eligibility, funding, occupancy, or subsidy status without authoritative evidence.
3. Customer Senior Housing surface + authenticated browser coverage after the backend contracts are verified.
4. Final exact-SHA six-job verification, then mark **PHASE 4.11 COMPLETE | VERIFIED** before moving to Phase 4.12.

---

# AI_HANDOFF.md — 2026-10-01 NAVIGATION / UX / HIDDEN-MENU CHECKPOINT VERIFIED

## Final verified checkpoint

- Navigation/UX/handoff checkpoint: **VERIFIED**.
- Verified source SHA: `de45d2c1b5d0d0309312e35708820ad490c84932`.
- GitHub Actions run: `36810461972` — SUCCESS.
- All six required CI jobs passed:
  - frontend: PASS
  - backend: PASS
  - security: PASS
  - platform-admin: PASS
  - staging-config: PASS
  - authenticated E2E: PASS
- Backend/PostgreSQL: **851 passed, 19 deselected, 23218 warnings in 223.35s**.
- Authenticated E2E: **19 passed, 271 warnings in 83.30s**.
- `backend/check_navigation.py`: PASS.
- The complete `HIDDEN MENU / UNHIDE ROADMAP` remains directly below the current navigation/UX checkpoint.
- The roadmap contains every key currently present in `backend/app/constants/menu_keys.py::MENU_ROUTE_BLOCKED_UNTIL`; no missing or extra roadmap keys were found.
- The first attempt of CI run `36807227573` exposed an existing authenticated HOA E2E navigation race. A retry failed at the same transition in a different HOA test, confirming the shared test synchronization defect.
- Scoped fix `de45d2c1b5d0d0309312e35708820ad490c84932` makes the 13 affected HOA browser flows wait for the authenticated dashboard identity to render before navigating to a property. No product behavior, menu readiness rule, navigation contract, or UX implementation changed.

## STOP POINT

- Phase **4.10 COMPLETE | VERIFIED** remains the last completed product phase.
- **Do not start Phase 4.11 / Senior Housing.**
- `docs/UX_STANDARDS.md` is owner-authorized but **NOT ACTIVE**. Do not implement UX work until the owner explicitly says `start UX work`.
- `docs/NAVIGATION_INTEGRITY_PLAN.md` remains the permanent navigation safety contract; do not recreate or repeat verified navigation work.
- Future menu items may be unhidden only under the mandatory rule in the `HIDDEN MENU / UNHIDE ROADMAP`.
- Development stops at this checkpoint until the owner gives the next instruction.

---

# AI_HANDOFF.md — 2026-10-01 NAVIGATION + UX PRESERVATION COMPLETE

## Current navigation/UX checkpoint

- Phase **4.10 COMPLETE | VERIFIED** remains the last completed product phase.
- Navigation integrity foundation source: `a5ee8bc6edb9c494903a000e472fcd55cddc6e6f`.
- Navigation CI: `36805027238` SUCCESS, all six jobs green.
- Final UX/documentation source before this handoff update: `9b5cfbf0d5272a7305036e3d04d251cc7d4dde37`.
- Final UX/documentation CI: `36806165154` SUCCESS, all six jobs green.
- Permanent navigation contract: `docs/NAVIGATION_INTEGRITY_PLAN.md`.
- Permanent UX contract: `docs/UX_STANDARDS.md`.
- UX product implementation is **AUTHORIZED BUT NOT ACTIVE**. Start only when the owner explicitly says `start UX work`.
- **Do not start Phase 4.11 until the owner explicitly resumes the product roadmap.**

# HIDDEN MENU / UNHIDE ROADMAP

This is the operator-readable roadmap for every menu key currently hidden by
the navigation-readiness layer in
`backend/app/constants/menu_keys.py::MENU_ROUTE_BLOCKED_UNTIL`.

These are platform/readiness hides only. A user's role, plan entitlement,
organization settings, permissions, or personal sidebar preferences can hide
additional items and are separate from this roadmap.

| Menu key | Customer label / area | Unlock phase or condition |
|---|---|---|
| `CALENDAR` | Calendar | Phase 5 — first real calendar/on-call customer surface |
| `WHATS_NEW` | What's New | UX — only after owner says `start UX work` |
| `LEASING.LISTINGS` | Listings | Phase 7 |
| `PROPERTIES.UNITS` | Units | TBD — Unit CRUD exists; dedicated list route is not yet verified |
| `PROPERTIES.GROUPS` | Property Groups | Phase 3.5 carry-forward; unhide only when the real route/workflow is verified |
| `PEOPLE.TENANTS` | Tenants | TBD — tenant capability exists; dedicated list route is not yet verified |
| `PEOPLE.OWNERS` | Owners | TBD — owner capability exists; dedicated list route is not yet verified |
| `ACCOUNTING.BANK_TRANSFERS` | Bank Transfers | TBD — canonical item; customer route is not yet scheduled |
| `ACCOUNTING.ONLINE_PAYMENTS` | Online Payments | Phase 8 |
| `MAINTENANCE` | Maintenance module container | Phase 5 |
| `MAINTENANCE.WORK_ORDERS` | Work Orders | Phase 5 |
| `MAINTENANCE.RECURRING` | Recurring Work Orders | Phase 5 |
| `MAINTENANCE.INSPECTIONS` | Inspections | Phase 5 |
| `MAINTENANCE.UNIT_TURNS` | Unit Turns | Phase 5 |
| `MAINTENANCE.PROJECTS` | Projects | Phase 5 |
| `MAINTENANCE.PURCHASE_ORDERS` | Purchase Orders | Phase 5 |
| `MAINTENANCE.INVENTORY` | Inventory | Phase 5 |
| `MAINTENANCE.FIXED_ASSETS` | Fixed Assets | Phase 5 |
| `MAINTENANCE.SMART` | Smart Maintenance | Phase 5 |
| `COMMUNICATION` | Communication module container | Phase 6 |
| `COMMUNICATION.INBOX` | Inbox | Phase 6 |
| `COMMUNICATION.MESSAGES` | Messages | Phase 6 |
| `COMMUNICATION.TEMPLATES` | Templates | Phase 6 |
| `COMMUNICATION.SURVEYS` | Surveys | Phase 6 |

## Unhide rule — mandatory

A future phase must not unhide an item merely because its nominal phase number
has passed. The same verified batch that removes an item from
`MENU_ROUTE_BLOCKED_UNTIL` must:

1. ship the real customer route/placement;
2. preserve backend authorization and organization/property isolation;
3. pass `backend/check_navigation.py`;
4. pass applicable backend/frontend tests;
5. pass the authenticated rendered-sidebar navigation E2E;
6. update this table and `docs/NAVIGATION_INTEGRITY_PLAN.md` if the contract changed.

If the roadmap still says `TBD`, do not invent a phase. Keep the item hidden
until an authoritative roadmap decision schedules it.

## Future-session startup

1. Read the entire repo-root `AI_HANDOFF.md`.
2. Verify live HEAD and CI.
3. Read `docs/NAVIGATION_INTEGRITY_PLAN.md` only when navigation work is active.
4. Read `docs/UX_STANDARDS.md` before UX work, but do not implement it unless the owner has explicitly said `start UX work`.
5. Never repeat verified navigation/UX foundation work.
6. Do not start Phase 4.11 unless the owner explicitly resumes the normal roadmap.

---

# AI_HANDOFF.md — 2026-10-01 PHASE 4.10 COMPLETE | VERIFIED

## Final Phase 4.10 product checkpoint

- **PHASE 4.10 COMPLETE | VERIFIED**
- Final VERIFIED PRODUCT SHA: `e4707a1e3ac695737dadc914d133667a929fca44`
- GitHub Actions run: `36798336118`
- Final run conclusion: SUCCESS
- All six required CI jobs passed on this exact product SHA:
  - frontend: PASS
  - backend: PASS
  - security: PASS
  - platform-admin: PASS
  - staging-config: PASS
  - authenticated E2E: PASS
- Backend/PostgreSQL: **849 passed, 18 deselected, 23214 warnings in 225.13s**
- Authenticated E2E: **18 passed, 271 warnings in 106.57s**
- Alembic head: `ae6c8d0f2b4c`
- Expected model tables: **191**
- No local test result is being substituted for hosted CI.

## Verified Phase 4.10 Student Housing scope

1. Property-scoped academic-year cycles are implemented behind `release.properties.student_housing`.
2. Active-unit bed inventory is explicit and organization/property scoped.
3. Central `Lease` supports optional Student Housing bed and academic-cycle references; no parallel rent/accounting system was created.
4. Distinct beds in one unit can have independent standard lease signature, activation, invoice and payment lifecycles.
5. Whole-unit and same-bed DRAFT/PENDING/ACTIVE occupancy conflicts fail closed.
6. Bed leases require an active same-property bed, active same-property academic cycle, active same-organization tenant, and dates contained within the selected academic cycle.
7. Open bed leases protect their bed and academic-cycle source records from deactivation.
8. Guarantor workflow supports explicit DRAFT -> REQUESTED -> DOCUMENT_RECEIVED or CANCELLED operational states. These states do not establish legal guaranty validity, signature, collectability or financial responsibility.
9. Student Housing setup and guarantor workflow create no Charge or GL transaction.
10. The customer property page now exposes a gated **Student Housing** tab with:
    - academic-cycle creation/listing;
    - bed inventory creation/listing;
    - draft by-the-bed lease creation/listing;
    - guarantor workflow creation and status transitions.
11. ADMIN/OWNER writes and assigned MANAGER read-only behavior remain enforced through the verified property/feature scope.
12. Dedicated authenticated browser coverage verifies the customer flow from academic cycle -> bed -> draft bed lease -> guarantor requested -> guarantor document received.

Final UI/E2E commits:
- `b3c63c83b0695c92ee7ef308c42fe63d508966c3` — Student Housing property UI.
- `635194771c43da5d4ca16e15300931c123a43ffc` — gated property-tab integration.
- `79606280a3a1244328c085fce15c9761ef85c87e` — authenticated Student Housing browser coverage.
- `e4707a1e3ac695737dadc914d133667a929fca44` — scoped E2E locator; final VERIFIED PRODUCT SHA.

## STOP POINT

Development is intentionally stopped after Phase 4.10.

**Do not begin Phase 4.11 or make further product-code changes until the user explicitly tells a future session to resume.**

For reference only, the next roadmap phase is **Phase 4.11 — Senior Housing**, described in `docs/PLAN_GAPS.md` as age-restricted compliance, care-coordination placeholders, and HUD 202/811 work. This is not started.

---

# AI_HANDOFF.md — 2026-09-30 VERIFIED PHASE 4.10 BED LEASING + GUARANTOR BACKEND

## Current verified product checkpoint

- Verified PRODUCT SHA: `45ca34c274c41a58a3ff38cc0abf38cefd2d74b3`
- GitHub Actions run: `36790368127`
- Final run conclusion: SUCCESS
- All six required CI jobs passed on this exact product SHA:
  - frontend: PASS
  - backend: PASS
  - security: PASS
  - platform-admin: PASS
  - staging-config: PASS
  - authenticated E2E: PASS
- Backend/PostgreSQL: **849 passed, 17 deselected, 23214 warnings in 255.43s**
- Authenticated E2E: **17 passed, 265 warnings in 99.13s**
- Alembic head: `ae6c8d0f2b4c`
- Expected model tables: **191**

## Verified Phase 4.10 backend scope

- central `Lease` now carries optional Student Housing bed and academic-cycle references;
- distinct beds in one unit can use independent standard lease signature/activation/invoice lifecycles;
- whole-unit leases and same-bed leases fail closed against conflicting DRAFT/PENDING/ACTIVE occupancy;
- bed leases require exact active same-property bed, academic cycle, active same-organization tenant, and dates inside the selected cycle;
- guarantor workflow records explicit DRAFT -> REQUESTED -> DOCUMENT_RECEIVED or CANCELLED staff states;
- guarantor workflow does not send messages, create signatures, establish legal guaranty validity, create Charges, or create GL transactions;
- open bed leases protect their bed and academic-cycle source records from deactivation;
- focused regressions prove two-bed coexistence, central RentInvoice generation after standard lease activation, scope controls and zero Charge/GL mutation from Student Housing setup/guarantor actions.

## Exact next Phase 4.10 work

Add the gated customer Student Housing property tab and dedicated authenticated browser coverage for academic cycles, bed inventory, draft by-the-bed lease creation and guarantor status tracking. Verify all six jobs on the exact final product SHA, update this handoff to **PHASE 4.10 COMPLETE | VERIFIED**, identify Phase 4.11 for reference only, then STOP.

---

# AI_HANDOFF.md — 2026-09-30 VERIFIED PHASE 4.10 STUDENT HOUSING FOUNDATION

## Current verified product checkpoint

- Verified PRODUCT SHA: `fcb86c2b643119d3c726adeaafe319246dbbd205`
- GitHub Actions run: `36789087201`
- Final run conclusion: SUCCESS
- All six required CI jobs passed on this exact product SHA:
  - frontend: PASS
  - backend: PASS
  - security: PASS
  - platform-admin: PASS
  - staging-config: PASS
  - authenticated E2E: PASS
- Backend/PostgreSQL: **847 passed, 17 deselected, 23070 warnings in 264.56s**
- Authenticated E2E: **17 passed, 265 warnings in 80.51s**
- Alembic head: `9d5f7b1c3e8a`
- Expected model tables: **190**
- No local test result is being substituted for hosted CI.

## Verified Phase 4.10 foundation

- explicit organization/property-scoped academic-cycle records;
- explicit active-unit bed inventory;
- Student Housing release gating through `release.properties.student_housing`;
- ADMIN/OWNER writes, assigned MANAGER read-only, cross-organization/property access fails closed;
- academic cycles and beds are operational metadata only and do not infer student status, occupancy eligibility, rent liability, guarantor liability, Charge, RentInvoice or GL posting.

## Exact next Phase 4.10 work

Complete the remaining Phase 4.10 plan from `docs/PLAN_GAPS.md`:

1. by-the-bed leases, implemented through the existing central `Lease` lifecycle rather than a parallel finance system;
2. guarantor workflow with explicit staff-tracked states and no fabricated legal acceptance;
3. customer Student Housing UI and focused authenticated browser coverage;
4. exact-SHA six-job verification, then mark **PHASE 4.10 COMPLETE | VERIFIED** and STOP before Phase 4.11.

---

# AI_HANDOFF.md — 2026-09-30 VERIFIED PHASE 4.9 RUBs ALLOCATION DETAIL REPORT

## Current verified product checkpoint

- Verified PRODUCT SHA: `bb8916af896053503bd5050c4a68b8e8c5016a02`
- GitHub Actions run: `36783872990`
- Final run conclusion: SUCCESS
- All six required CI jobs passed on this exact product SHA:
  - frontend: PASS
  - backend: PASS
  - security: PASS
  - platform-admin: PASS
  - staging-config: PASS
  - authenticated E2E: PASS
- Backend/PostgreSQL: **845 passed, 17 deselected, 23030 warnings in 318.69s**
- Authenticated E2E: **17 passed, 265 warnings in 100.93s**
- Alembic head remains `8c4e6a0b2d7f`
- Expected model tables remain **188**
- No local test result is being substituted for hosted CI.

## Phase 4.9 completed in this verified batch

Implemented the roadmap's **allocation detail per bill period** reporting surface over already-reviewed RUBs allocation snapshots:

- customer RUBs UI can select a reviewed bill-period snapshot and display the preserved bill period, bill ID, rule revision, allocation basis, source bill total, reviewed allocated total, per-unit weight/share/amount, deterministic remainder rule and review timestamp;
- unit labels are resolved only from the already scoped property allocation context; historical snapshot data itself remains the durable source of allocation amounts;
- the report is review-only and creates no tenant charge, owner charge, invoice, receipt, bank movement or GL entry;
- the report reuses the already verified organization/property/active SHARED utility authorization and reviewed-snapshot API rather than adding a parallel unscoped reporting path;
- authenticated browser coverage now verifies the allocation-detail report is visible after a reviewed snapshot is saved and shows both included units and the reviewed total;
- no database migration or backend finance behavior changed in this batch.

Implementation commits in this verified batch:

- `d18ef98cf541c93dae66621c5f04d92405b728dd` — customer allocation detail report
- `bb8916af896053503bd5050c4a68b8e8c5016a02` — authenticated E2E coverage; this is the verified PRODUCT SHA

## Exact next Phase 4.9 work

Continue Phase 4.9 with the remaining roadmap item **RUBs reports**. The planning source lists this separately from allocation detail per bill period, but does not define a tenant-billing or accounting posting contract for it.

Required boundaries for the next bounded batch:

1. Build reports only from already verified RUBs source records and reviewed allocation snapshots.
2. Keep the report informational/review-only. Do not infer tenant/owner legal chargeability, occupancy, fixture counts, lease liability or payer identity.
3. Preserve organization/property/active SHARED utility scope, manager assignment, RUBs release gating and current permission checks.
4. Do not create tenant/owner charges, invoices, receipts, bank movement or GL entries from report generation.
5. Prefer a reviewed-history summary across periods/units rather than inventing unsupported billing statements or provider data.
6. Add focused authenticated browser coverage and any backend coverage needed for new report logic.
7. Verify all six CI jobs on the exact product SHA, repair CI reds autonomously, then refresh this root handoff.

Planning alignment after this checkpoint:

- Meter reading (manual + import): verified.
- Ratio allocation methods: verified.
- Allocation detail per bill period: **verified in this batch**.
- Year-end true-up preview: verified and finance-neutral.
- RUBs reports: **next**.
- Utility provider integrations/manual bill entry and tenant/owner charges remain distinct roadmap capabilities; do not silently claim them complete from reporting work.

---

# AI_HANDOFF.md — 2026-09-30 PHASE 4.9 COMPLETE | VERIFIED

## Final Phase 4.9 product checkpoint

- **PHASE 4.9 COMPLETE | VERIFIED**
- Final VERIFIED PRODUCT SHA: `bb8916af896053503bd5050c4a68b8e8c5016a02`
- GitHub Actions run: `36783872990`
- All six required CI jobs passed on this exact product SHA:
  - frontend: PASS
  - backend: PASS
  - security: PASS
  - platform-admin: PASS
  - staging-config: PASS
  - authenticated E2E: PASS
- Backend/PostgreSQL: **845 passed, 17 deselected, 23030 warnings in 318.69s**
- Authenticated E2E: **17 passed, 265 warnings in 100.93s**
- Alembic head remains `8c4e6a0b2d7f`
- Expected model tables remain **188**
- No local test result is being substituted for hosted CI.

## Verified Phase 4.9 RUBs scope

1. Manual and bounded CSV meter readings are verified for active same-property SHARED utilities, with explicit source data and no inferred billing obligation.
2. Versioned allocation-rule revisions support SQUARE_FEET plus explicit OCCUPANCY, FIXTURES and MANUAL_WEIGHT inputs, with separate authorization and deterministic finance-neutral preview.
3. Reviewed allocation snapshots preserve the exact authorized rule revision, bill period, source amount, included units, weights, shares, rounded amounts and deterministic remainder behavior used at review time.
4. Snapshot replay is idempotent for identical requests and fails closed for conflicting data; reviewed history blocks destructive utility deletion.
5. Year-end true-up is implemented as a review-only preview over explicitly selected reviewed snapshots and explicit actual/adjustment weights. It creates no Charge, invoice, receipt, bank movement or GL posting.
6. The customer RUBs UI supports draft/authorize/preview, reviewed snapshot history, year-end true-up preview and a dedicated **allocation detail per bill period** report surface backed only by preserved reviewed snapshots.
7. The report shows bill period, bill/rule reference, basis, bill and reviewed totals, unit weights, shares, allocated amounts and the stored deterministic remainder rule. It does not reconstruct missing tenant/legal eligibility or create finance.
8. Focused backend and authenticated browser coverage verify scope, idempotency, deterministic calculations, reviewed history, report rendering and zero finance mutation.

Planning items now covered:
- `product.rubs.meter_reading`
- `product.rubs.allocation_methods`
- `product.rubs.true_up`
- `compliance.rubs.reports` — allocation detail per bill period

## Exact next phase

Proceed to **Phase 4.10 — Student Housing**.

Planned Phase 4.10 scope from `docs/PLAN_GAPS.md` and the parity checklist:
- by-the-bed leases;
- guarantor workflow;
- academic-year cycles.

Start with a bounded foundation batch that models explicit academic cycles and bed inventory/scope without changing existing whole-unit lease accounting. Do not infer guarantor liability, student status, occupancy eligibility or financial responsibility. Preserve existing organization/property/unit/lease isolation and central accounting behavior. Add focused backend and authenticated browser coverage, verify all six CI jobs on the exact product SHA, then refresh this handoff.

---

# AI_HANDOFF.md — 2026-09-30 VERIFIED PHASE 4.9 RUBs REVIEWED ALLOCATION HISTORY + TRUE-UP PREVIEW

## Current verified product checkpoint

- Verified PRODUCT SHA: `4d5a374962427b64cd93c1b75eabce04478bf1d8`
- GitHub Actions run: `36780722209`
- Final run conclusion: SUCCESS
- All six required CI jobs passed on this exact product SHA:
  - frontend: PASS
  - backend: PASS
  - security: PASS
  - platform-admin: PASS
  - staging-config: PASS
  - authenticated E2E: PASS
- Backend/PostgreSQL: **845 passed, 17 deselected, 23030 warnings in 324.56s**
- Authenticated E2E: **17 passed, 265 warnings in 64.67s**
- Alembic head: `8c4e6a0b2d7f`
- Expected model tables: **188**
- No local test result is being substituted for hosted CI.
- First E2E attempt on this SHA had one unrelated HOA reserve browser navigation failure; the RUBs browser flow passed. Re-running the failed jobs without product changes produced the final all-green run above.

## Phase 4.9 completed in this verified batch

Implemented durable reviewed RUBs allocation history and finance-neutral year-end true-up preview:

- a completed non-posting allocation preview can be explicitly saved as a reviewed historical allocation snapshot;
- snapshots preserve the exact authorized rule revision, bill period, bill amount, included unit IDs, weights, shares, rounded unit amounts and deterministic cent remainder behavior used at review time;
- snapshot save is explicit and retry-safe: exact replay is idempotent while conflicting data under the same request key fails closed;
- reviewed history remains scoped to the exact organization/property/active SHARED utility and does not infer legal tenant eligibility, occupancy, fixtures, lease dates or chargeability;
- year-end true-up preview operates only over explicitly selected reviewed allocation snapshots plus explicit adjustment/actual inputs;
- true-up output shows the selected period/source snapshots, prior allocated total, explicit actual/adjusted total and deterministic per-unit differences;
- this batch remains finance-neutral: it creates no tenant charge, owner charge, invoice, receipt, bank movement, GL transaction or accounting posting;
- customer RUBs UI supports saving reviewed allocation history and previewing the year-end true-up;
- deleting a utility that has reviewed RUBs allocation history is blocked so historical source records cannot be silently destroyed; staff must retain/deactivate the utility instead;
- focused backend and authenticated browser coverage verify reviewed snapshot idempotency, true-up calculation, scope controls and zero finance mutation.

## Exact next Phase 4.9 work

Continue Phase 4.9 with the remaining **RUBs reporting/review surface** that is separately scheduled in the roadmap. Before coding, reconcile the exact report requirements against the existing planning/checklist so this does not invent tenant billing, legal eligibility or accounting behavior.

Required boundaries:

1. Reports must read from the already verified RUBs source records and reviewed allocation snapshots; do not reconstruct or infer missing legal/tenant eligibility data.
2. Keep report output informational/review-only unless a later explicitly authorized roadmap item adds posting.
3. Preserve organization/property/active SHARED utility scope, manager assignment, RUBs release gating and existing permission checks.
4. Do not create tenant/owner charges, invoices, receipts, bank movement or GL entries from report generation.
5. Add focused backend and authenticated browser coverage for whatever report scope is actually present in the roadmap.
6. Use one bounded product batch, verify all six CI jobs on the exact product SHA, repair CI reds autonomously, then refresh this root handoff.

---

# AI_HANDOFF.md — 2026-09-30 VERIFIED PHASE 4.9 RUBs ALLOCATION RULES + PREVIEW

## Current verified product checkpoint

- Verified PRODUCT SHA: `53aba244af09fdaaf269fe0856fe7f4a2091404d`
- GitHub Actions run: `36769880286`
- Run attempt: 1
- All six required CI jobs passed on that exact SHA:
  - frontend: PASS
  - backend: PASS
  - security: PASS
  - platform-admin: PASS
  - staging-config: PASS
  - authenticated E2E: PASS
- Backend/PostgreSQL: **845 passed, 17 deselected, 23026 warnings in 315.23s**
- Authenticated E2E: **17 passed, 265 warnings in 101.41s**
- Alembic head: `7b3d9f1a5c2e`
- Expected model tables: **187**
- No local test result is being substituted for hosted CI.

## Phase 4.9 completed in this batch

Implemented versioned RUBs allocation-rule configuration and a finance-neutral allocation preview:

- added immutable versioned allocation-rule content per active same-property SHARED utility;
- rule revisions have effective dates, explicit DRAFT/AUTHORIZED status and separate authorization action;
- a new revision never inherits authorization automatically;
- SQUARE_FEET snapshots current positive square footage for explicitly selected active units;
- OCCUPANCY, FIXTURES and MANUAL_WEIGHT require explicit positive staff-entered weights;
- active units must be selected explicitly; tenant/lease/address/meter data is not used to infer legal eligibility;
- allocation context exposes only the source data needed for staff review;
- preview accepts one authorized rule revision and one complete valid source utility bill;
- preview fails closed for missing/reversed periods and overlapping recorded bill periods;
- deterministic cent handling: floor raw unit shares to cents, then distribute remaining cents in ascending unit-ID order;
- preview creates no tenant charge, owner charge, invoice, receipt, GL transaction or accounting posting;
- customer RUBs UI now supports creating draft revisions, explicit authorization and allocation preview;
- focused backend regressions cover authorization, revisioning, cross-property unit rejection, explicit-weight requirements, deterministic rounding and zero finance mutation;
- authenticated browser coverage exercises draft -> authorize -> preview and verifies finance counts remain unchanged.

Implementation commits in this verified batch:

- `8cf094224955372aa58fa092c9e84c35cd16bb5f` — versioned RUBs allocation preview
- `53aba244af09fdaaf269fe0856fe7f4a2091404d` — fail-safe migration correction; this is the verified PRODUCT SHA

## Exact next Phase 4.9 batch

Continue Phase 4.9 with the planned **RUBs year-end true-up** capability, but keep it finance-neutral until its source history is explicit and reviewable.

Required boundaries for the next batch:

1. Add durable, organization/property/shared-utility scoped reviewed allocation snapshots so a completed allocation preview can be preserved as historical source data without creating charges or GL.
2. Snapshot the exact rule revision, bill period, bill amount, included unit IDs, weights, shares, rounded amounts and deterministic remainder rule used.
3. Require an explicit staff review/save action. Replaying the same request must be idempotent; different data under the same request key must fail closed.
4. Do not infer tenant legal eligibility, tenancy dates, occupant counts, fixture counts or chargeability.
5. Build year-end true-up as a **preview/review calculation first** over explicitly selected reviewed allocation snapshots and explicit adjustment inputs. Do not post tenant/owner charges, invoices or GL in this batch.
6. Define and display the true-up period, source snapshots, prior allocated total, explicit adjustment/actual total, per-unit differences and deterministic cent handling.
7. Preserve exact org/property/active SHARED utility scope, existing RUBs gate/menu permission and manager-assignment behavior.
8. Add migration/model/schema/router/customer UI plus focused backend and authenticated browser coverage.
9. Prove no Charge/GL mutation in tests.
10. Use one bounded provisional product batch, verify all six CI jobs on the exact product SHA, repair CI reds autonomously, then refresh this handoff.

Planning source alignment:

- `product.rubs.meter_reading` — Phase 4.9, now implemented.
- `product.rubs.allocation_methods` — Phase 4.9, now implemented through versioned authorized rule configuration and non-posting preview.
- `product.rubs.true_up` — Phase 4.9, next planned item.
- RUBs reports remain separately scheduled; do not expand this batch into general reporting.

---

# AI_HANDOFF.md — 2026-09-30 VERIFIED PHASE 4.9 RUBs METER READINGS

**AUTHORITATIVE CURRENT CHECKPOINT. Phase 4.9 is IN PROGRESS. Earlier NEXT labels below are historical where superseded.**

- Last VERIFIED PRODUCT source: `8c749f1c05a913a92fc1fc03d33075cb23f9ecdf`.
- GitHub Actions **36763331835 attempt 1 SUCCESS, all SIX required jobs on this exact SHA**: frontend PASS; backend PASS; security PASS; platform-admin PASS; staging-config PASS; authenticated E2E PASS.
- Backend: **843 passed, 16 deselected, 22971 warnings in 316.47s**.
- Authenticated E2E: **16 passed, 256 warnings in 95.95s**.
- **TESTS NOT RUN locally.**
- Alembic head: **`e6f8a0c2d4b7`**. Expected SQLAlchemy model tables: **186**.
- Initial provisional source `a5f8ea4c3bcd62c87535460b1ea65524d423a8fa` had **841 passed, 16 deselected** with only two stale bootstrap/migration table-count snapshots failing after the new table. Corrective `8c749f1c...` changed only those two expected head/table constants and is the verified source.

## Verified Phase 4.9 meter-reading scope

1. Active authorized property staff can record raw meter readings only for an active same-property **SHARED** utility behind the existing `release.properties.rubs` gate and `PROPERTIES.ALL` scope.
2. Manual readings support property meters or an optional active same-property unit/submeter reference, date, nonnegative value, unit of measure, note and retry-safe request key.
3. CSV import accepts bounded rows with required meter/date/value/unit-of-measure fields and optional property-unit ID/note, validates the complete batch before insert, rejects cross-property unit references, and supports exact replay without duplicate rows.
4. Raw readings retain MANUAL/IMPORT source metadata and import batch reference. They are source inputs only.
5. This batch creates **no allocation formula, tenant charge, owner charge, RentInvoice, utility-provider integration, bank movement or GL posting**. Existing Phase 4.5 bill-period diagnostics remain intact.
6. Customer RUBs UI can select a shared utility, enter a manual reading, import CSV readings and review recorded raw readings while explicitly stating that allocation and billing remain disabled.

## EXACT NEXT Phase 4.9 batch

Implement **versioned property/shared-utility allocation-rule configuration and finance-neutral allocation preview**.

- Supported rule bases should cover the roadmap categories without inventing data: **SQUARE_FEET** may use current active-unit square feet only when every included unit has an explicit positive value; **OCCUPANCY** and **FIXTURES** require explicit staff-entered per-unit counts/weights because current source does not reliably contain legal occupant counts or fixture counts; allow an explicit **MANUAL_WEIGHT** basis rather than inferring missing inputs.
- Scope rules to exact organization/property/active SHARED utility; preserve the RUBs release/menu/manager-assignment checks.
- Store immutable/versioned rule revisions with effective dates/status and an explicit reviewed/authorized flag. A new revision must not silently authorize itself.
- Preview one complete utility-bill period only after the bill period is valid and non-overlapping for the selected source bill. Compute deterministic per-unit shares and rounded allocation detail with a documented remainder rule. Preview remains **non-posting**.
- Do **not** infer legal eligibility from property address, lease existence, tenant identity, raw meter readings or a utility bill. Do not create tenant/owner charges, GL, true-up, provider integration or reports in this batch.
- Add migration/schema/router/customer UI plus focused backend and authenticated browser coverage. One bounded provisional product commit on the existing branch, exact-SHA six-job CI, autonomous repair, then refresh this root handoff and continue Phase 4.9.

---

# AI_HANDOFF.md — 2026-09-30 PHASE 4.8 COMPLETE | VERIFIED

**AUTHORITATIVE FINAL PHASE 4.8 CHECKPOINT. STOP ALL DEVELOPMENT AFTER THIS HANDOFF UNTIL EXPLICIT USER INSTRUCTION.**

- **PHASE 4.8 COMPLETE | VERIFIED**
- Final VERIFIED PRODUCT SHA: `cd79ae8c953367935d5f78abd71452fa473cff12`.
- GitHub Actions **36755427547 attempt 1 SUCCESS, all SIX required jobs on this exact product SHA**: frontend PASS; backend PASS; security PASS; platform-admin PASS; staging-config PASS; authenticated E2E PASS.
- Backend: **841 passed, 16 deselected, 22895 warnings in 223.58s**.
- Authenticated E2E: **16 passed, 256 warnings in 98.25s**.
- **TESTS NOT RUN locally.**
- Final Alembic head: **`d5f7a9c1e3b6`**. Final expected SQLAlchemy model tables: **185**.

## Verified Phase 4.8 Commercial scope

1. Commercial lease references and scoped read-only reporting are verified.
2. Private same-scope Commercial lease source evidence is linked and protected without claiming execution or legal validity.
3. Versioned source-linked lease terms are verified for base-rent reference, escalations, lease options, co-tenancy summary, CAM/tax/insurance estimates and shares, percentage-rent rate/breakpoint and TI allowance; a new revision resets internal billing authorization.
4. Operational CAM and NNN tenant charges post through existing central `Charge` + balanced GL with scoped accounts, current source/authorization checks, idempotency, closed-period protection and unpaid reversal.
5. Annual CAM reconciliation uses private actual-CAM evidence, current authorized CAM share and posted estimate components; positive, negative and zero true-ups are supported with appropriate central GL/reversal behavior.
6. Percentage rent uses private tenant-sales evidence plus the current billing-authorized annual breakpoint/rate. Only sales above the breakpoint generate percentage rent; positive amounts create a tenant Charge + balanced central GL, zero creates no finance, and unpaid postings reverse through central GL.
7. TI allowance utilization uses private scoped evidence and the current authorized allowance, caps aggregate ACTIVE utilization at the source-backed allowance, retains immutable/void history, and creates **no inferred reimbursement, bank movement, Charge, RentInvoice or GL entry**.
8. Private Commercial source, CAM, percentage-rent and TI evidence remains protected from unsafe sharing/removal when referenced. Commercial operation panels only render when the current authorized terms contain the corresponding clause.

## STOP condition

**Do not make any further product-code changes. Do not start Phase 4.9, Phase 5 or any later phase until the user explicitly instructs a resume.**

Next phase/task for reference only, **NOT STARTED**:
- **Phase 4.9 — RUBs**
- First recorded task: **Meter reading (manual + import)**, followed by the remaining RUBs allocation/operational work from the existing roadmap/checklist.

Historical checkpoints below remain for audit only; their NEXT labels are superseded by this final stop instruction.

---

# AI_HANDOFF.md — 2026-09-30 VERIFIED COMMERCIAL CAM RECONCILIATION

**AUTHORITATIVE CURRENT CHECKPOINT. Phase 4.8 ONLY.** Do not start Phase 4.9+.

- Last VERIFIED PRODUCT source: `074f4c0dc8a9852935dc7bcb32825df4b95cde08`. GitHub Actions **36748569619 attempt 2 SUCCESS, all SIX jobs on this exact SHA**. Backend **836 passed, 16 deselected, 22756 warnings in 293.45s**; authenticated E2E **16 passed, 254 warnings in 94.17s**; frontend, platform-admin, security and staging-config PASS. **TESTS NOT RUN locally**. Attempt 1 failed one unrelated HOA reserve browser login/navigation check; the failed E2E job was rerun without product changes and passed.
- Verified annual Commercial CAM reconciliation: private same-scope evidence + current authorized CAM share are compared against CAM components of active posted Commercial operating charges for the selected year. Positive true-up creates a tenant Charge and balanced central GL posting; negative true-up posts the opposite balanced central GL entry without fabricating a cash refund; zero creates no finance. Unpaid positive true-ups and GL-only negative true-ups reverse through immutable central reversals. Evidence remains private and protected.
- Alembic head **`c4e6f8a0b2d5`**, **183 model tables**.
- **FINAL REMAINING Phase 4.8 batch:** percentage rent from private tenant-sales evidence using current billing-authorized rate/breakpoint, with positive/zero posting and unpaid reversal; plus TI allowance utilization tracking against current authorized allowance and private evidence, capped across active utilization with void history and no inferred payout/bank/GL movement. After exact-SHA six-job green, mark **PHASE 4.8 COMPLETE | VERIFIED**, update handoff with final SHA/counts, identify Phase 4.9 for reference only, and STOP all development until explicit user instruction.

---

# AI_HANDOFF.md — 2026-09-30 VERIFIED COMMERCIAL CAM / NNN POSTING

**AUTHORITATIVE CURRENT CHECKPOINT. Phase 4.8 ONLY.** Do not start Phase 4.9+.

- Last VERIFIED PRODUCT source: `c93f2af644d1971afb06ddd2a99f409669e833e5`. GitHub Actions **36736262765 SUCCESS, all SIX jobs on this exact SHA**. Backend **832 passed, 16 deselected, 22605 warnings in 275.17s**; authenticated E2E **16 passed, 253 warnings in 90.10s**; frontend, platform-admin, security and staging-config PASS. **TESTS NOT RUN locally**.
- Verified operational Commercial CAM/NNN: current active billing-authorized source-linked lease terms may post CAM-only or NNN (CAM + property-tax + insurance estimates) to the exact active Commercial tenant as an existing `Charge` plus balanced central GL receivable/income journal. Explicit period/posting/due dates, scoped ASSET receivable + INCOME accounts, request-key idempotency, current terms/source validation and closed-period protection are enforced. Unpaid postings reverse through a distinct central GL REVERSAL and soft-inactivate the tenant charge; reversal history remains immutable. No RentInvoice mutation.
- Alembic head **`b3d5f7a9c1e4`**, **182 model tables**.
- Initial product source `aaab9d223554527fe4f6e5871ba978ac5cc311c3` passed backend and five jobs but the browser test retained the old no-finance assertion. Test-only corrective `c93f2af644d1971afb06ddd2a99f409669e833e5` changed only that stale assertion; no product behavior changed.
- **NEXT Phase 4.8:** annual CAM reconciliation against source-backed actual CAM, current authorized CAM share and CAM components of active posted estimate charges, with positive/negative/zero true-up and reversal. Then percentage rent and TI allowance. After all Phase 4.8 requirements are exact-SHA six-job green, write final `PHASE 4.8 COMPLETE | VERIFIED` handoff and STOP. Do not implement Phase 4.9.

---

# AI_HANDOFF.md — 2026-09-30 VERIFIED COMMERCIAL SOURCE-LINKED TERMS

**AUTHORITATIVE CURRENT CHECKPOINT. Phase 4.8 ONLY.** Earlier NEXT labels below are historical. Do not start Phase 4.9+.

- Last VERIFIED PRODUCT source: `15ab3fcadd7d2a31b700c3c49ebd81913c232d2d`. GitHub Actions **36726538552 SUCCESS, all SIX jobs on this exact SHA**. Backend **829 passed, 16 deselected, 22495 warnings in 299.45s**; authenticated E2E **16 passed, 249 warnings in 89.95s**; frontend, platform-admin, security and staging-config PASS. **TESTS NOT RUN locally**.
- Verified Phase 4.8 Commercial terms: source-linked, immutable revision history for staff-abstracted base rent, escalations, lease options, co-tenancy summary, CAM/tax/insurance estimates and share, percentage-rent rate/breakpoint and TI allowance. Each revision is `STAFF_ABSTRACTED_UNVERIFIED`, requires a current private exact-lease source, and a separate explicit internal billing authorization. A later revision resets authorization. No charge, invoice or GL posting occurs from abstraction/authorization alone.
- Alembic head **`a2c4e6f8b0d1`**, **181 model tables**.
- **NEXT Phase 4.8 batch:** operational CAM/NNN periodic charge posting and reversal using ONLY the current active billing-authorized terms revision, exact commercial lease/property/tenant scope, explicit posting date, approved receivable + income GL inputs, central `post_transaction()`, closed-period protection, idempotency and immutable reversal history. CAM-only and NNN (CAM + tax + insurance) must be distinguishable. Do not infer amounts from old revisions or bypass current source/authorization. Then complete annual CAM reconciliation, percentage rent and TI allowance tracking. STOP after final Phase 4.8 verified checkpoint; do not begin Phase 4.9.

---

# AI_HANDOFF.md — 2026-09-30 VERIFIED COMMERCIAL PRIVATE LEASE SOURCE EVIDENCE

**AUTHORITATIVE CURRENT CHECKPOINT.** Phase 4.8 only. Earlier NEXT labels below are historical. Do not touch main, create a branch, force-push, merge or start Phase 4.9+.

- Last VERIFIED PRODUCT source: `e7bb66da129a840c49e88db896a39bb4abe14670`. GitHub Actions **36724237778 attempt 2 SUCCESS, all SIX jobs on this exact SHA**. Backend **827 passed, 16 deselected, 22394 warnings in 308.56s**; authenticated E2E **16 passed, 249 warnings in 89.76s**; frontend lint/typecheck/build, platform-admin, security and staging-config PASS. **TESTS NOT RUN locally**. Attempt 1 had one unrelated HOA reserve browser navigation failure; all Commercial source assertions passed. The failed E2E job was rerun without product edits and passed.
- Verified Phase 4.8 Commercial source evidence: authorized Commercial staff can link exactly one active PRIVATE same-org lease attachment to the active commercial lease abstract, list eligible private lease-source files, show filename/status and download through the existing scoped attachment endpoint. Sharing/deletion is blocked while referenced. The record remains STAFF_LINKED_UNVERIFIED and does not certify execution, parse terms, create rent/CAM/NNN/%-rent/TI obligations, invoice, Charge, RentInvoice or GL activity.
- Alembic head **`f5a7c9e1b3d8`**, **178 model tables**; migration adds only the source attachment FK to the existing Commercial abstract.
- **EXACT NEXT Phase 4.8 batch:** versioned source-linked Commercial lease terms for base rent reference, rent escalations, options, co-tenancy, CAM/tax/insurance estimates and shares, percentage-rent rate/breakpoint and TI allowance. A terms revision remains STAFF_ABSTRACTED_UNVERIFIED and creates no money. Add a separate explicit internal billing authorization per current revision; a new revision resets that authorization. Then continue Phase 4.8 CAM/NNN posting, annual reconciliation, percentage rent and TI tracking through existing central accounting. Stop only when all Phase 4.8 items are complete and verified; do not start Phase 4.9.

---

# AI_HANDOFF.md — 2026-09-30 COMMERCIAL RESUME RECONCILED

**AUTHORITATIVE CORRECTION TO THE NEXT TASK.** The Phase 4.7 completion checkpoint immediately below remains valid. Its Commercial "report next" sentence is superseded because live source/history shows that report was already completed and verified before HOA work resumed.

- Existing VERIFIED Phase 4.8 Commercial lease-reference report source: corrective commit `305eff4d5ff92425f781990c45274cf478f37c83` over implementation `2a41f051abb881b26a57072acde1b36cfc7cade0`. GitHub Actions **36456112573 SUCCESS all SIX jobs** on the corrective source: backend **721 passed, 4 deselected, 15849 warnings in 140.23s**; authenticated E2E **4 passed, 4 warnings in 13.60s**; frontend, platform-admin, security and staging-config PASS. It already provides scoped preview/CSV/email delivery for STAFF_RECORDED_UNVERIFIED commercial lease commencement references. Do not repeat it.
- Live Commercial abstract still contains only Lease/Unit scope plus optional staff-recorded rent-commencement metadata; it has no scoped private source-document reference. CAM/NNN, reconciliations, percentage rent, escalations/options/co-tenancy and TI remain unsafe to make operative without lease-source evidence and authenticated terms.
- **EXACT NEXT Phase 4.8 bounded batch: private Commercial lease-source document reference.** Reuse existing `EntityAttachment` bytes for the exact same-org commercial Lease/property and documents release. Allow authorized Commercial staff to link one active PRIVATE lease attachment to an existing active Commercial lease abstract; recheck property + LEASING + attachments gates, exact lease/entity linkage, active/unshared file and tenant/org scope on every read/update. Show source filename/status and allow scoped download through existing attachment API, but label it STAFF_LINKED_UNVERIFIED and do not claim execution, authenticity, legal effect or parsed terms. Prevent generic attachment archival/deletion while an active Commercial abstract depends on it, or otherwise fail closed without orphaning the reference. No CAM/NNN calculation, invoice, Charge, RentInvoice, GL posting, due date, notice or financial mutation. Add migration/schema/router/UI/backend + authenticated browser coverage. One provisional product commit on the existing branch, six-job exact-SHA CI, repair reds, then update handoff and continue.

---

# AI_HANDOFF.md — 2026-09-30 VERIFIED BOARD ATTENDANCE VISIBILITY / PHASE 4.7 OPERATIONAL COMPLETE

**AUTHORITATIVE CURRENT CHECKPOINT.** Earlier NEXT / PROVISIONAL headings below are historical. Verify live HEAD and CI before editing. Only branch `chatgpt/checkpoint-005-safety`; no main, new branch, force-push, PR merge or frozen docs edits.

- Last VERIFIED PRODUCT: `6054ceb170f9986e8407312bb55cd54c9cb7d699`. GitHub Actions **36671841727 attempt 2 SUCCESS, all SIX jobs on this exact SHA**. Backend **826 passed, 15 deselected, 22345 warnings in 231.02s**; authenticated E2E **15 passed, 236 warnings in 55.88s**; frontend lint/typecheck/build, platform-admin, security and staging-config PASS. **TESTS NOT RUN locally**. Attempt 1 failed only an unrelated ARC browser login/navigation transient with 14 browser tests passing; rerunning the failed E2E job succeeded without product edits.
- Verified final Phase 4.7 gap: a current verified paid-HOA delegated board seat can read ONLY the existing active staff-reported attendance for its exact live association/property/meeting. The portal exposes participant display name and PRESENT/ABSENT/UNCONFIRMED only, omits contact directory/email identifiers, labels the roster STAFF_REPORTED_UNVERIFIED / not certified quorum, and fails closed on seat/contact/property revocation. No new attendance store, self-certification, finance, legal or quorum effect. No migration; Alembic remains **`e4f6a8c0b2d5`**, **178 model tables**.
- **Phase 4.7 original independently actionable HOA scope is operationally covered and verified:** recurring/special member assessments with real central-GL posting, receipts/reversals/statements; violation notice/service/cure/hearing/fine/payment/appeal/outcome notification; authenticated board meetings/votes/rule adoption/motion outcomes/minutes/attendance visibility; operative ARC APPROVED/DENIED plus protected fee/notification/reversal and inspection completion; booked reserve accounting with protected execution/reversal; governing document private storage, delivery, board read and version lineage; annual budgets, actuals and approved assessment increases. Preserve all seven areas, the $79/month paid HOA entitlement, private scope boundaries, immutable audit, idempotency, accounting locks/balance and reversals.
- Remaining HOA production add-on provider checkout/price activation depends on external billing/provider configuration and is not an independently safe generic HOA implementation batch. Do not invent a Stripe/provider price or silently grant paid access. This does not reopen the seven operational HOA workflows.
- **RESUME Phase 4.8 Commercial from the preserved verified checkpoint.** Historical verified Commercial source `bfa68575cdd027141be22abeb70affb379fff17e` introduced scoped commercial lease abstracts. Exact next bounded Commercial batch: read-only same-scope lease-abstract summary/reporting using only current recorded commercial lease abstract references and live Lease/Unit/tenant scope. Do NOT infer CAM/NNN, percentage rent, escalations, options, TI obligations, billing dates or legal contract terms. Add focused backend + customer UI/browser coverage, one bounded provisional commit, six-job exact-SHA CI, repair reds, refresh handoff, continue.

---

# AI_HANDOFF.md — 2026-09-30 VERIFIED DELEGATED BOARD VIOLATION HEARING / FINE FLOW

**AUTHORITATIVE CURRENT CHECKPOINT.** Earlier NEXT / PROVISIONAL sections below are historical. Verify live HEAD and CI before editing. Only branch `chatgpt/checkpoint-005-safety`; no main, new branch, force-push, PR merge, or frozen docs edits.

- Last VERIFIED PRODUCT: `ac69ac62c95983ff8f6310bd553c50d208cce73a`. GitHub Actions **36670875386 attempt 1 SUCCESS, all SIX jobs on this exact SHA**. Backend **826 passed, 15 deselected, 22342 warnings in 300.51s**; authenticated E2E **15 passed, 236 warnings in 87.98s**; frontend lint/typecheck/build, platform-admin, security and staging-config PASS. **TESTS NOT RUN locally**.
- Verified delegated-board violation flow: an active verified paid-HOA board login with a current association/property authorized seat can see only scoped active FINE_PROPOSED cases, the served member/procedure/hearing state and current private case evidence, download only that live private evidence, record the existing standalone hearing outcome, and execute the existing final fine-decision endpoint from the board dashboard. Revocation/cross-scope isolation remains enforced. Hearing/fine decisions remain finance-neutral until the separate accountant posting action. Synthetic browser coverage exercises evidence download, hearing record, final decision, then returns to the staff accounting/appeal path with zero finance mutation.
- Initial provisional `682b66a8e0f3ced4586aa9daf8e7d720002704b1` failed one stale regression fixture because test board actors were not marked verified while **825 passed, 15 deselected**. Corrective `fc767736a174ad62e52d43d30a6a0748a70f5894` made only the fixture verification correction; backend became **826 passed**, but E2E exposed a navigation-state issue after returning from the board portal (14 passed, 1 failed). `ac69ac62c95983ff8f6310bd553c50d208cce73a` reopens the staff case panel after navigation and is the only source marked VERIFIED for this batch.
- Alembic remains **`e4f6a8c0b2d5`**, **178 model tables**. No migration in this delegated-board batch.
- **EXACT NEXT independently incomplete Phase 4.7 batch: board-portal visibility of existing meeting attendance.** Staff already records scoped attendance in `hoa_meeting_participation`, but the delegated board portal exposes meetings, motions, votes, minutes and outcomes without the attendance roster. Add a read-only live-seat board endpoint and UI that reuses ONLY active staff-reported attendance for that exact association/property/meeting, exposes participant display name + PRESENT/ABSENT/UNCONFIRMED status without email/contact-directory access, clearly labels it STAFF_REPORTED_UNVERIFIED / not certified quorum, and fails closed on seat/contact/property revocation. No new attendance store, no self-certification, no finance, no legal/quorum inference. Add backend and authenticated browser regression. No migration expected.
- Continue remaining original Phase 4.7 HOA gaps after that checkpoint. Preserve $79 paid-HOA entitlement, org/property/member/board boundaries, private attachments, immutable audit, idempotency, central GL locks/balance and reversals. GitHub connector workflow only: one bounded source+tests commit on the existing branch, exact-SHA six-job CI, autonomous repair, handoff refresh, then continue. Phase 4.8 remains paused.

---

# AI_HANDOFF.md — 2026-09-30 VERIFIED STANDALONE VIOLATION HEARING RECORD

**AUTHORITATIVE CURRENT CHECKPOINT.** Earlier NEXT / PROVISIONAL sections below are historical. Verify live HEAD and CI before editing. Only branch `chatgpt/checkpoint-005-safety`; no main, new branch, force-push, PR merge, or frozen docs edits.

- Last VERIFIED PRODUCT: `96a9c361504993091726c81a1c54aa9c178bcf16`. GitHub Actions **36667572480 attempt 1 SUCCESS, all SIX jobs on this exact SHA**. Backend **825 passed, 15 deselected, 22261 warnings in 294.95s**; authenticated E2E **15 passed, 236 warnings in 85.43s**; frontend lint/typecheck/build, platform-admin, security and staging-config PASS. **TESTS NOT RUN locally**.
- Verified Phase 4.7 standalone violation hearing outcome: after actual service and the configured cure/hearing process, an authorized scoped board actor records exactly one immutable `HEARING_HELD` (actual held date + live private case evidence) or `NO_REQUEST_RECORDED` (only after the configured request window). The record snapshots service, procedure revision, verified member and board seat; request keys are idempotent and audited. A final fine decision now reuses/rechecks that hearing record and rejects contradictory hearing snapshots. Recording the hearing creates no fine, charge, receipt, refund, GL entry or legal-service certification.
- Migration head **`e4f6a8c0b2d5`**, **178 model tables**. New `hoa_violation_hearing_records` table is one-per-case; `hoa_violation_fines.hearing_record_id` links the immutable prerequisite. Initial provisional `887de3b7` failed only one regression-test fixture NameError while **824 passed, 15 deselected**; corrective commit `96a9c361504993091726c81a1c54aa9c178bcf16` changed only that stale test reference and is the verified source.
- **EXACT NEXT independently incomplete Phase 4.7 batch: delegated board portal access to operational violation hearing/fine actions.** The backend hearing/fine endpoints enforce live board scope, but the delegated board dashboard currently exposes meetings, appeals and governing documents, not active FINE_PROPOSED violation cases. A board-only login therefore lacks a safe portal path to review the served member/procedure/hearing state and explicitly record the standalone hearing outcome and final fine decision. Add a bounded board portal list/action flow for ONLY the caller's active association/property board seats and FINE_PROPOSED cases; reuse the VERIFIED hearing/fine APIs and existing private case evidence, do not create a parallel decision engine. Expose only case-scoped evidence needed for a held hearing, preserve revocation/cross-org isolation, require the existing board authority and paid HOA gates, and keep hearing/fine actions finance-neutral until the separate existing accountant posting action. Add backend + authenticated board-browser coverage. No real notices or money in CI.
- Then continue any remaining original Phase 4.7 HOA gaps before Phase 4.8. Preserve $79 HOA entitlement, org/property/member/board boundaries, private files, idempotency, immutable audit, central GL locks/balance and reversals. Use connector blobs/tree/commit on the existing branch, verify the exact product SHA in all six jobs, repair reds autonomously, refresh this handoff, and continue.

---

# AI_HANDOFF.md — 2026-09-29 VERIFIED OPERATIONAL ARC INSPECTION COMPLETION

**AUTHORITATIVE CURRENT CHECKPOINT.** Earlier NEXT / PROVISIONAL sections below are historical. Verify live HEAD and CI before edits. Only branch `chatgpt/checkpoint-005-safety`; no main, new branch, force-push, PR merge, or frozen docs edits.

- Last VERIFIED PRODUCT: `2da803080365d1bb30588950d342d13584886a7d`. GitHub Actions **36663363650 attempt 1 SUCCESS, all SIX jobs on this exact SHA**. Backend **825 passed, 15 deselected, 22231 warnings in 304.98s**; authenticated E2E **15 passed, 236 warnings in 85.75s**; frontend lint/typecheck/build, platform-admin, security and staging-config PASS. **TESTS NOT RUN locally**.
- Verified Phase 4.7 ARC inspection completion: an existing APPROVED ARC decision may have an `INSPECTION` follow-up. Authorized scoped staff can explicitly mark that follow-up COMPLETED with a real completion date, substantive note and optional live private property evidence. Completion is idempotent by organization/request key, audited, rejects shared/cross-scope evidence, and preserves the original final board decision. It does not re-run applicant notification, fee posting/reversal, work-order creation, tenant charges, GL, or any legal-certification effect.
- Migration head **`d9f1b3c5e7a2`**, still **177 model tables**; migration adds completion metadata/constraints to `hoa_arc_follow_ups` only. Staff UI and the existing authenticated ARC browser scenario record an inspection request and completion with zero finance mutation.
- **EXACT NEXT independently incomplete Phase 4.7 batch: standalone operational violation HEARING record.** Current violation cases can plan a hearing and final fine decisions snapshot `HEARING_HELD` or `NO_REQUEST_RECORDED`, but there is no immutable hearing event recorded independently before the final fine decision. Add one scoped, idempotent hearing record tied to the served case/member and current procedure, with actual held date + private case evidence for held hearings or explicit no-request-after-window status. Final fine decision must reuse/recheck that hearing record instead of accepting a second contradictory hearing story. Preserve board authority, notice service/cure gates, private evidence, appeal/accounting workflows and no-money hearing semantics. Include staff/board UI as appropriate plus backend and authenticated browser regression. Do not invent statutory rules; use configured procedure and recorded service dates only.
- Then continue any remaining original Phase 4.7 operational gaps before Phase 4.8. Method unchanged: connector workflow, one bounded source+tests batch, exact-SHA six-job CI, autonomous repair, handoff refresh and immediate continuation. Preserve $79 HOA gates, org/property/member/board boundaries, idempotency, immutable audit, central GL locks/balance and reversals; synthetic CI must not send real customer notices or move real money.

---

# AI_HANDOFF.md — 2026-09-29 VERIFIED GOVERNING DOCUMENT VERSION LINEAGE

**AUTHORITATIVE CURRENT CHECKPOINT.** Earlier NEXT / PROVISIONAL sections below are historical. Verify live HEAD and CI before editing. Only branch `chatgpt/checkpoint-005-safety`; no main, new branch, force-push, PR merge, or frozen docs edits.

- Last VERIFIED PRODUCT: `75ab668a804d51d34e6809222b89c5f54185309f`. GitHub Actions **36662183776 attempt 1 SUCCESS, all SIX jobs on this exact SHA**. Backend **824 passed, 15 deselected, 22160 warnings in 287.02s**; authenticated E2E **15 passed, 236 warnings in 83.96s**; frontend lint/typecheck/build, platform-admin, security and staging-config PASS. **TESTS NOT RUN locally**.
- Verified Phase 4.7 governing-document version lineage: staff can replace an active private association/property governing-document reference with another private property attachment; prior references are archived, retained in scoped metadata history, and linked through immutable `supersedes_id` / monotonically increasing revision. Replacement request keys are idempotent, concurrency protected and audited. Historical attachment bytes/deliveries are not deleted or rewritten; current board view remains current-only. No adoption/legal-validity claim, delivery event, money, charge, ledger or GL effect is inferred.
- Migration head is **`c2e4a6b8d0f3`**, still **177 model tables** because this migration adds version-lineage columns/constraints only. Initial provisional product `9ad38ed3` failed only two stale bootstrap Alembic-head assertions; correction commits `c4a04324` and `75ab668a` changed only those two expected-head constants from `b1d3f5a7c9e2` to `c2e4a6b8d0f3`. Table-count expectation remained 177.
- **EXACT NEXT independently incomplete Phase 4.7 batch: operational ARC INSPECTION completion.** Existing approved ARC decisions can create `HOAARCFollowUp(kind="INSPECTION")`, but it remains an OPEN request with no completion date, staff completion note, private completion evidence pointer, idempotent completion request, or completion audit. Add a bounded staff-authorized completion workflow that rechecks paid HOA/property/association scope, preserves the final board decision, optionally links only private active property evidence, records completion idempotently, exposes status in ARC detail/UI, and has no fee/notification/GL/work-order re-execution. Add migration/schema/router/UI/backend + authenticated browser regressions. Do not treat inspection completion as a new ARC approval/denial or legal certification.
- After that, continue remaining independently actionable original HOA requirements. A likely later gap is an independent violation-hearing record: current cases plan hearings and final fine decisions snapshot hearing data, but there is no standalone immutable hearing event record. Do not advance Phase 4.8 while Phase 4.7 operational gaps remain.
- Method unchanged: GitHub connector, bounded source+tests, existing branch only, non-force ref update, all six CI jobs on exact product SHA, repair genuine reds, then refresh this root handoff with actual counts and continue. Preserve $79 HOA gates, org/property/member/board boundaries, private files, idempotency, audit, balanced central GL, accounting locks and reversals. Synthetic CI must not create real obligations, send customer notices or move real money.

---

# AI_HANDOFF.md — 2026-09-29 VERIFIED PRIVATE BOARD GOVERNING DOCUMENTS

**AUTHORITATIVE CURRENT CHECKPOINT.** Earlier NEXT and PROVISIONAL headings below are historical. Verify live branch, commits and CI. ONLY branch `chatgpt/checkpoint-005-safety`, no main, new branch, force-push, PR merge or frozen docs edits.

- Last VERIFIED PRODUCT `c72369f9c21124d00006b301603ec9bd9acea584`, GitHub Actions **36652630596 attempt 1 SUCCESS all SIX jobs on exact SHA**. Backend **823 passed, 15 deselected, 22111 warnings in 300.62s**; authenticated E2E **15 passed, 236 warnings in 80.54s**. Frontend lint/typecheck/build, platform-admin, security and staging-config all PASS. **TESTS NOT RUN locally**. Alembic still `b1d3f5a7c9e2`, **177 model tables**, no migration this batch.
- Verified authorized paid-HOA board-only read: scoped active PRIVATE staff-linked governing docs visible in board UI and downloadable through `/api/hoa/board/my-governing-documents` and `/governing-documents/{reference_id}`; live verified board login/association/property, contact link, document entitlement/release and private unshared source are rechecked. No general staff document permission or generic attachment API, write access, board adoption, statutory service, delivery, charge, ledger or GL effects. E2E synthetic file download/archive and finalized fine appeal private-evidence download both pass.
- **EXACT NEXT independently incomplete Phase 4.7 batch: staff-supplied governing document VERSION LINEAGE and explicit private document replacement.** Existing `HOAGoverningEvidence` only tracks active/archived source pointers; no revision chain. Add immutable prior-reference lineage, serialized replacement with idempotent request key and audit, private replacement file validation, scoped staff-only history, historical delivery preservation, current-only board view, staff UI and focused regression + authenticated browser tests. Do not claim new version means adoption/legal validity. No real outgoing delivery, money or new separate attachment bytes. Update migration head assertions and actual model count. Other HOA operational areas remain Phase 4.7.
- **PREPARED NOT COMMITTED/TESTED** candidate blobs against source `c72369f9c21124d00006b301603ec9bd9acea584`: model `backend/app/models/hoa_governing_evidence.py` SHA `0bfad0dc69b1cb942289b9ed8d91de99a47541a2`; schema `backend/app/schemas/hoa_governing_evidence.py` SHA `cb1379aa9a88b94ef5a1cbb6f39af7e39e452c1c`; migration `backend/alembic/versions/c2e4a6b8d0f3_hoa_document_versions.py` SHA `20849d6bc3ac0400ae19ae218b82125bd92a2271`; router `backend/app/routers/hoa_governing_evidence.py` SHA `42b9f167bd632dc4649610179a308438bd1af86d`; migration-test `backend/tests/test_migrations.py` SHA `40c7c8cf2ceb012eadbbd39b344ba120e8547e1c`; backend regression `backend/tests/test_hoa_governing_evidence.py` SHA `665321e54bfc199ae60df21752d7ef5facc1f6c3`; staff UI `frontend/src/components/property/HoaGoverningEvidencePanel.tsx` SHA `164e562efc291a90ef9fa6a51bb5eed1022cda52`; browser extension `backend/tests/e2e/test_hoa_evidence_e2e.py` SHA `70511c520e0f34291eee3ac2dee79aa1bcf96205`. REVIEW THESE BLOBS against live HEAD. They are merely prepared, not yet committed nor run in CI; fix any defects before provisional commit. If source advanced use live source. Never mark them verified without six-job CI.
- Method: GitHub connector; one bounded blob/tree/commit on feature branch, update_ref non-force, let GitHub Actions test ACTUAL committed SHA, inspect job logs, correct failures, only mark verified after all six jobs green; then prepend short root handoff with exact SHAs/counts/migration/table count and next independent task and continue. Preserve paid $79/month HOA gates, current association/property/member identity, live board authority, accounting locks, balanced GL, immutable audit, idempotency, protected reversal history. No real customer emails/money in synthetic CI.

---

# AI_HANDOFF.md — 2026-09-29 VERIFIED FINAL APPEAL EVIDENCE

**AUTHORITATIVE CURRENT CHECKPOINT.** Earlier NEXT / provisional labels below are historical. Verify live branch and CI. Only work on \`chatgpt/checkpoint-005-safety\`; no main, new branch, force push, PR merge or frozen docs edits.

- Last VERIFIED PRODUCT commit \`310eb1d114ba0e624add0bb604a14c89757185fa\`; GitHub Actions **36651852242 attempt 1 SUCCESS** on this exact SHA. All SIX jobs passed. Backend **822 passed, 15 deselected, 22033 warnings in 229.48s**; authenticated browser **15 passed, 234 warnings in 79.38s**; frontend lint/typecheck/build, platform-admin, security and staging-config PASS. **TESTS NOT RUN locally**. Previous provisional \`b4edf62d\` failed one incorrect test expectation (privacy guard returns HTTP 409, not 404), corrected by \`310eb1d1\`. Do not claim failed run 36651081910 verified.
- New VERIFIED behavior: an authorized, active, paid-HOA-gated association board seat may review/download only existing live, private, case-linked supporting evidence when fine appeal is OPEN or FINAL UPHELD/VACATED. Final board listing flags evidence availability without exposing an attachment ID. Checks enforce org/property/case/fine, live board delegation, private/unshared attachment, storage, attachment feature and revocation. No new ledger entry, refund, decision, email or legal-service assertion. Alembic remains \`b1d3f5a7c9e2\`; **177 model tables**, no migration this batch.
- EXACT NEXT independent Phase 4.7 batch: **Board portal read-only access to association-scoped private governing document evidence.** The current staff evidence index already stores unverified PDF/Word pointers but the delegated board portal cannot list/download them without generic staff document permissions. Expose only active current board association/property references and their private file bytes with live paid HOA and documents release, revocation, unsharing and archive checks, no generic attachment IDs or write permissions. Include authenticated board UI and regression/browser coverage. Reuse existing HOAGoverningEvidence and EntityAttachment; do not create a second attachment store, alter finance, claim document legal validity or dispatch notices.
- Prepared, UNCOMMITTED candidate blobs for the next batch: backend/app/routers/hoa_board_portal.py \`c672401afc508820b84b6dff66e6c133a44e42b6\`; backend/tests/test_hoa_procedure_cases.py \`30621e4df3871d4ef2501a88807503e6410d286b\`; backend/tests/e2e/test_hoa_evidence_e2e.py \`8675afbca4721e4e3d51ad97b23ee406ead31e6b\`; frontend/src/components/property/HoaBoardGoverningDocumentsPanel.tsx \`4bd6516616bfd2e2ddc38a29f895ff8f39f04c6c\`; frontend/src/app/dashboard/hoa/board/page.tsx \`2e75e35e41e10d352544d787740aa1cdd6c01ed7\`. Review/assemble them against LIVE HEAD, commit provisionally to ONLY the feature branch and fix CI failures. These blobs have NEVER been tested or committed and are NOT completion.
- Working procedure: one bounded source+tests commit using GitHub connector blobs/tree/commit, non-force ref update, let Actions test exact committed SHA in six jobs, repair failures, only then mark VERIFIED, prepend new root handoff with real test counts/migration/table status and exact next independent HOA feature. Continue Phase 4.7, do not advance 4.8 while actionable HOA requirements remain. No terminal clone is needed. Preserve authoritative HOA board decisions, live verified recipients, $79 HOA entitlement, accounting locks/GL/idempotency/reversals, private files, audit, no synthetic real customer effects.

---

# AI_HANDOFF.md — 2026-09-29 VERIFIED DELEGATED FINAL APPEAL PORTAL

**AUTHORITATIVE CURRENT CHECKPOINT.** Later historical sections are preserved below and their NEXT labels are superseded. Check live HEAD and CI before edits.

- Only working branch: `chatgpt/checkpoint-005-safety`. Last VERIFIED PRODUCT commit `2b72eaf080efe3cb3147b6d02c6a586bc7f6d632`; GitHub Actions run **36647708184 attempt 1 SUCCESS**, all SIX jobs: backend **822 passed, 15 deselected, 22032 warnings in 202.05s**; authenticated browser **15 passed, 234 warnings in 67.74s**; frontend, platform-admin, security and staging-config PASS. **TESTS NOT RUN locally**.
- This product batch includes provisional implementation `ef879582954553d464258a5fa60964295a9ae60a` and corrective association-scoped template/retry commit `2b72eaf080efe3cb3147b6d02c6a586bc7f6d632`. The two earlier workflow runs were CANCELLED; neither is verification. No migration in these two commits: latest verified Alembic **b1d3f5a7c9e2**, **177 model tables**.
- Authenticated paid-HOA delegated board members can view scoped FINAL UPHELD/VACATED appeal histories and notification states, explicitly send/retry using the existing shared notification outbox and association-scoped HOA appeal templates. Retain the previous OPEN-appeal private evidence portal. Do not infer email delivery or legal service from SMTP acceptance. No ledger or refund side effects; synthetic CI only.
- NEXT: inspect live source against original Phase 4.7 HOA roadmap and select an independently incomplete OPERATIONAL HOA capability, without repeating verified final-appeal notifications, board history, private evidence, posted dues/fines, ARC, governance, reserve accounting, documents or budget subsets. Preserve $79 paid-HOA gate, org/property/member scope, live board authority, accounting locks, audit, idempotency and reversals. Keep exact next scoped batch in handoff when identified. Phase 4.8 remains out of scope.
- Workflow: GitHub connector fetch/inspect, bounded blob/tree/commit only on existing branch, non-force ref update, GitHub Actions six jobs on exact commit, autonomously repair failures, update root handoff with real test counts, continue independently. Never touch main, create a branch, force-push, merge PRs or modify frozen docs/. PROVISIONAL means committed but not six-job green; PREPARED means uncommitted; BLOCKED needs an exact dependency.

---

# AI_HANDOFF.md — 2026-09-29 VERIFIED HOA FINE-APPEAL OUTCOME EMAIL

**AUTHORITATIVE CURRENT CHECKPOINT.** This entire leading section supersedes
historical NEXT, PROVISIONAL and CI-running labels below. Always verify live
GitHub HEAD and Actions before editing. Read the entire root handoff; history
is preserved below, but the live source and this leading section are current.

## Repository and test evidence
- Repository: `yasirskhan/property-platform`; ONLY branch:
  `chatgpt/checkpoint-005-safety`. Never modify main, create another branch,
  force-push, merge PRs without approval, or change frozen `docs/`.
- Last **VERIFIED PRODUCT** commit:
  `8e2173330aa3363538c12a04f392aaef644a6826`.
  GitHub Actions run **36646057349 attempt 1 SUCCESS** on this exact SHA:
  all SIX jobs PASS (backend, frontend lint/typecheck/build,
  platform-admin, security, staging-config, authenticated E2E).
  Backend **821 passed, 15 deselected, 21941 warnings in 273.63s**;
  authenticated browser **15 passed, 234 warnings in 76.56s**.
  **TESTS NOT RUN locally**; the committed source was tested in GitHub Actions.
- Database: Alembic head **`b1d3f5a7c9e2`**, **177 model tables**.
  Migration and ORM registry match. Migration test snapshots were updated.
- Product implementation started at `24f5e1fbbf074069438e3ba629cf42576a36c4e0`
  (PROVISIONAL). First CI run `36645590159` FAILED four outdated
  migration-head/table-count assertions (817 passed, 4 failed,
  15 deselected). Corrective product commit `8e217333` updates
  migration expectations and a browser status-text selector;
  the successful six-job run above verifies the corrected source.
  Do not misattribute the earlier failed run as verified.

## Phase 4.7 batch COMPLETED and VERIFIED
- An explicitly authorized HOA board member with requisite staff property/
  contact access can notify the responsible verified member of an existing
  FINAL `UPHELD` or `VACATED` fine appeal through the property staff UI.
  A decision is NOT generated by delivery. The existing appeal's final
  disposition and original responsible member are immutable source records.
- Reuses organization-authored `CUSTOM` letter templates titled
  `HOA Appeal: ...` from Reporting Letters. Only safe organization/property
  merge tags are supported; recorded final result, decision date and
  non-service/non-refund disclaimer are appended. Exact reviewed message,
  outcome, user, association, property and request key are snapshotted.
- New private `hoa_fine_appeal_notifications` outbox: explicit send,
  at-most-one outbox per appeal, idempotent request key, `PENDING`,
  `SENDING`, `TEST_ONLY`, `FAILED`, `SMTP_ACCEPTED`; bounded
  operator retry with stale-claim recovery, durable attempt/audit history,
  live sender board-delegation and recipient rechecks, private generic
  note/attachment denial. SMTP acceptance is NOT inbox-delivery proof,
  legally completed notice or service. Actual delivery is UNKNOWN absent
  external proof. Console CI sends no real emails.
- No new `Charge`, receipt, fine, ledger posting, refund or reversal arises
  from notification. Existing fine-appeal decision, service and accounting
  correction workflows are preserved. Backend security/idempotency/finance
  regressions and existing authenticated HOA browser flow exercise the
  synthetic transport without customer-facing side effects.
- Do not repeat verified private supporting-evidence delegation (product
  `1942b66a`, run `36643404274`) or this notification batch.

## EXACT NEXT independent Phase 4.7 batch
**Delegated board portal access to finalized appeal outcomes and safe
notification actions.** The board portal currently lists OPEN appeals only:
they disappear immediately after the final board decision. The new
notification panel and generic staff routes still require property/contact
staff permissions in addition to live board authorization, so a verified
association board member with ONLY delegated board scope cannot review
its final outcome history or send/retry that recipient notification.

Inspect live source first. Build one bounded batch that exposes ONLY that
board member's current association/property/case/fine FINAL UPHELD/VACATED
outcome references and scoped notification status, without leaking another
association's records or broad staff contacts. Reuse the VERIFIED outbox
and templates, not a second transport. Let an independently authorized
board-only login explicitly send/retry the same verified-recipient
notification, with association, property, case, fine, final appeal, paid HOA
add-on, active delegation and live recipient rechecks. No automatic email
on decision, no real CI emails or inferred legal service; no accounting.
Extend backend and authenticated browser regressions for delegation,
revocation, cross-org/property isolation, duplicate delivery and no money.
Preserve the existing protected pending-evidence board portal and staff
routes. If source has already advanced, pick the actual next independent
operational HOA gap instead.

Then continue other original seven operational HOA requirements (recurring/
special dues and member receipts, violations/service/hearings/fines/appeals,
board governance, operative ARC, booked reserve accounting, document
storage/versioning/delivery, annual budgets/approved increases). Do not
mistake prepared drafts for posted operational features and do not enter
Phase 4.8 while actionable HOA work remains.

## Required continuation workflow
Use GitHub CONNECTOR, not a terminal clone: terminal DNS for github.com/npm
may be blocked while connector works. Read full root handoff; verify current
HEAD, commits, CI and affected files. One bounded source+test batch; create
Git blobs/tree/commit against live branch; update ONLY existing branch with
`force=false`. The commit is PROVISIONAL until GitHub Actions on its
EXACT SHA succeeds in all SIX jobs. Inspect logs, autonomously correct
failures, report actual positive test counts. After green, prepend another
short authoritative checkpoint to THIS root handoff and commit it; the
handoff-only commit does not establish product testing. Immediately
continue independent Phase 4.7 work without requesting another "continue".
Never claim local tests ran or that uncommitted blobs passed Actions.
Keep paid $79/month HOA gates, association/property/board/member identity
boundaries, private evidence, accounting-period locks, balanced central GL,
idempotency, immutable audit and protected reversal history. The board
decides; software records authorized operations, without a blanket legal
certification gate. Stop only for necessary user-visible input, security or
a blocker affecting all independent work.

---

# AI_HANDOFF.md — 2026-09-29 VERIFIED PRIVATE APPEAL EVIDENCE / NEXT SESSION

**AUTHORITATIVE CURRENT STATUS.** Read the ENTIRE repo-root file before
acting. This new section supersedes every older NEXT, PREPARED, BLOCKED,
CI-running, or provisional label preserved below as history. Verify
live branch HEAD and CI again, because later sessions may have advanced.

## Repository and verified checkpoint
- Repository: `yasirskhan/property-platform`.
- ONLY working branch: `chatgpt/checkpoint-005-safety`.
- Last VERIFIED PRODUCT commit:
  `1942b66a4ce36a02e25d62eed19d635f37c01c76`.
  Hosted GitHub Actions run **36643404274 SUCCESS, all SIX jobs**
  on this exact commit: backend **818 passed, 15 deselected, 21675
  warnings in 287.67s**; authenticated browser **15 passed,
  232 warnings in 61.25s**; frontend lint, TypeScript,
  production build, platform-admin, security, staging-config PASS.
  **TESTS NOT RUN locally**. This product verification does not
  apply to later untested source.
- Verified Alembic head `6f9e2a7d4c1b`; **176 model tables**.
  This latest source has NO new migration or table.
- Current source completed a delegated HOA BOARD fine-appeal
  PRIVATE supporting-evidence batch: a staff member selects
  previously linked active private case evidence while recording
  a fine appeal; the OPEN appeal listing discloses whether private
  proof is available, not a generic attachment URL. A currently
  authorized, verified, paid-HOA-gated association/property board
  member may download only that case-linked evidence through
  `GET /api/hoa/board/fine-appeals/{appeal_id}/supporting-evidence`.
  The endpoint rechecks live board seat, associated case/fine,
  private attachment linkage, document release and storage.
  The same file is not made accessible to unrelated users,
  other organizations, owners or tenants. Tests cover revoked
  access, shared/stale evidence, closed appeal, financial
  nonmutation and actual synthetic browser navigation/download.
  Product commit `1942b66a` and CI above verify this batch.
- The preceding delegated fine-appeal board portal is VERIFIED:
  source `543d2bbba7e8c6ab29b5ddb39993eaeb8a9cde53`,
  GitHub Actions `36639458401` **attempt 2 SUCCESS all six**
  (817 backend passed, 15 browser passed). Attempt 1 had a
  browser failure; do not misstate it as successful.
- Older verified source `c41ea3e8` includes association-board
  UPHELD/VACATED fine appeals, private records, and separate,
  protected accounting corrections. Never silently erase a
  posted assessment/fine or refund a receipt merely by recording
  VACATED. Preserve direct operative ARC APPROVED/DENIED
  with authorized member fees/notification retries and reversals.

## Exact next independent Phase 4.7 task
Inspect the current source to determine whether an authorized
fine-appeal final decision already has customer-configured,
scoped, retryable outcome notification to the verified recipient.
If not implemented, complete that BOUNDED operational batch:
re-use existing central template/communications/outbox infrastructure,
actual board disposition, verified contact/member, active HOA
subscription/permissions, association/property/case/fine scope,
idempotent sending, retry and audit. Clearly distinguish queued,
transport-accepted, failed and actually delivered statuses; do not
equate e-mail acceptance with statutory legal service. No new fine,
charge, GL posting, refund or invented legal deadline; no real
emails from CI. Add focused backend and dedicated authenticated
HOA browser coverage. If equivalent functionality is ALREADY
VERIFIED, do not repeat it: select the next independently
incomplete operational original Phase 4.7 capability, write its
exact scope into THIS handoff and implement one batch at a time.

Original required SEVEN areas: real recurring/special member dues
and receipt allocation; operational violations/service/cure/hearing/
fine/appeal; board portal/meetings/votes/minutes; operative ARC;
reserve accounting with protected GL book entries; governing
document storage/versioning/delivery; annual budget/adoption and
approved assessment increases. Treat implemented subsets as
subsets, not a declaration that all seven are finished.
Keep the $79/month paid HOA add-on and feature entitlements.
Do not advance Phase 4.8 while independent HOA work remains.

## Exact working method, used successfully in normal Chat
1. Use the CONNECTED GitHub tools first. Read the entire
   `AI_HANDOFF.md`, inspect live HEAD, commits and latest run.
   Historical handoff labels are NOT live source facts.
2. Inspect affected live files/contracts and existing verified
   tests. Scope one new backend/frontend/migration/browser batch.
   Preserve already verified features and unrelated code.
3. GitHub connector can fetch and create Git blobs, create a tree
   based on the exact live feature-branch HEAD, create one
   provisional product commit, and fast-forward UPDATE ONLY
   `chatgpt/checkpoint-005-safety` using `force=false`.
   Recheck HEAD before moving the ref. Never switch branches,
   force-push, merge PRs, touch `main` or frozen `docs/`.
4. GitHub Actions then tests the ACTUALLY COMMITTED source.
   Run all required six jobs: backend, frontend,
   platform-admin, security, staging-config, authenticated E2E.
   Follow current job logs; fix genuine product/test failures
   through corrective feature-branch commits. If a transient
   browser failure is suspected, diagnose and rerun failed
   jobs, recording which attempt passed. No silent skipping.
5. Report REAL positive backend and browser test counts and
   corresponding exact source SHA. If local tests were not
   run, say `TESTS NOT RUN locally`; never imply uncommitted
   Git blobs were tested by CI. Provisional is not VERIFIED.
6. Once SIX green jobs pass for the same product SHA,
   append/prepend a concise new authoritative checkpoint
   to this ROOT handoff with source SHA, exact CI run/attempt,
   actual counts, migration head and table count, completed
   behavior, limitations and exact next independent batch.
   Commit the handoff on the same feature branch; the
   documentation-only commit does not establish new product
   testing. Preserve history but explicitly supersede older
   provisional/NEXT labels.
7. Immediately begin another independently actionable Phase 4.7
   batch within the SAME active session. A green CI checkpoint
   is not a request for user approval. Stop only for actual
   missing user input, an unresolved security issue, or a
   genuine blocker to all remaining authorized work. No
   excessive narration, repetitive audits or idle CI polling.

**Environment:** The GitHub connector works directly even if a
separate terminal cannot resolve github.com or npm. An executable
local clone is NOT required for this authorized connector-to-Actions
workflow. Do not falsely claim local npm/test execution, or claim
GitHub integration is disconnected because terminal DNS failed.
This chat cannot promise asynchronous work after its active run.

**Safety and product boundaries:** Organizations configure their
association procedures and identify authorized decision makers;
the software records those decisions and executes permitted
workflows, without inserting a blanket platform legal
certification gate. Enforce the actual configured/required
procedure, exact member/payee identity, scoped permissions,
posting locks, balanced central GL, idempotency, immutable audit,
reversals and accurate communication status. Do not invent law,
treat a staff draft as a fine, use a tenant Charge as member
liability, conflate booked GL reserve movements with bank
transfers, or allow synthetic CI to send real notices, capture
real money or create customer obligations.

---
# AI_HANDOFF.md — 2026-09-29 BOARD APPEAL PRIVATE EVIDENCE PROVISIONAL

Read entire handoff; this section supersedes historical NEXT labels.
Branch `chatgpt/checkpoint-005-safety` only. No main, new branch,
force-push, frozen docs/ or Phase 4.8.

Last VERIFIED product is `543d2bbba7e8c6ab29b5ddb39993eaeb8a9cde53`:
run 36639458401 attempt 2 SUCCESS, all SIX jobs;
backend **817 passed, 15 deselected**; browser **15 passed**.
Alembic **6f9e2a7d4c1b**, **176 tables**.
The docs-only commit `86d5b0b2` recorded this verification.

NEW proposed batch (NOT VERIFIED until its own all-six-job CI):
a currently delegated and paid-HOA-gated board member may download
only an OPEN fine appeal's active, PRIVATE, case-linked supporting
evidence. Staff can select previously linked case evidence during
appeal intake; the board list reveals availability but not generic
attachment access. Download revalidates board association/property,
parent case, fine, private linkage, document release and storage.
Backend tests cover role/org scope, revoked board seat, shared/stale
proof, disabled documents, terminal appeal and no finance side
effects. Dedicated browser exercises staff proof association and
board download in disposable E2E. No migration/new general ledger,
member charge, delivery or statutory service. No real data should
be seeded by CI. Only an authorized board can decide, as verified.
NEXT: commit this proposed source provisionally on THIS branch;
inspect actual CI and repair red jobs, mark VERIFIED only after six
jobs pass. Then refresh handoff and continue the next independent
operational HOA batch, with existing verified ARC, dues/fines, board,
budget, reserve and governing delivery intact.

---

# AI_HANDOFF.md — 2026-09-29 DELEGATED BOARD APPEAL PORTAL VERIFIED

**Read entire handoff. This current entry supersedes all older NEXT,
PROVISIONAL and CI-in-progress entries preserved below.**
Repository `yasirskhan/property-platform`, ONLY branch
`chatgpt/checkpoint-005-safety`. Do not touch main, start another
branch, force push, merge, modify frozen docs/, or advance Phase 4.8.

- Last VERIFIED product source `543d2bbba7e8c6ab29b5ddb39993eaeb8a9cde53`.
  GitHub Actions run **36639458401 attempt 2 SUCCESS all SIX jobs**
  on that exact SHA. Backend **817 passed, 15 deselected,
  21595 warnings in 218.03s**; browser **15 passed,
  232 warnings in 75.31s**. Frontend lint/TypeScript/build,
  platform-admin, security, staging PASS. **TESTS NOT RUN locally**.
  Run attempt 1 FAILED one older board-proposals login/navigation
  browser test while 14 other browser tests passed. Failed-jobs rerun
  succeeded without product edits; do not count attempt 1 as green.
- Verified Alembic head `6f9e2a7d4c1b` and **176 model tables**.
  No migration in delegated fine-appeal board portal batch.
- Verified board portal GET `/api/hoa/board/my-fine-appeals`
  lists OPEN fine appeals only for currently verified active member
  logins tied to active authorized association/property board seats
  with live paid HOA gates and parent case/fine scope. Board UI
  submits direct UPHELD/VACATED via the already verified disposition
  API without granting organization-wide staff permissions. It does
  not post GL, refund, send notice or override the source board decision.
  Earlier appealed fine accounting guard/reversal workflow remains.
- NEXT scoped independent Phase 4.7 batch: make previously recorded
  PRIVATE case-linked appeal supporting evidence available for
  authenticated, authorized, currently scoped board decision-makers.
  Expose only case-linked, active, unshared private evidence and only
  for a live appeal/board seat; add an authorized board download and
  strict revocation/foreign-scope test, customer board portal control
  and dedicated browser coverage. Reuse existing attachment bytes,
  do not grant generic file access, do not publish to owners/tenants,
  and do not infer legal service or send real messages. No new model
  or migration expected. Provisional feature branch source must
  pass ALL SIX CI jobs before marking this further batch verified.
  If this batch changes direction, record exact reason and next task.
- Original SEVEN real HOA capabilities remain Phase 4.7 priority.
  Preserve effective ARC APPROVED/DENIED, existing dues/fine
  GL/receipts/appeals, board votes and budgets, reserve book posting,
  private governing delivery and $79/month paid HOA gate. Avoid
  blanket platform legal-certification gates, do not invent statutory
  procedure, and leave only truly unsupported individual actions pending.
  Synthetic CI must not dispatch real notices or create real obligations.

---

# AI_HANDOFF.md — 2026-09-29 DELEGATED HOA BOARD APPEAL PORTAL PROVISIONAL

**Read the entire file.** Latest entry supersedes historical NEXT
and PREPARED labels. ONLY repository `yasirskhan/property-platform`,
branch `chatgpt/checkpoint-005-safety`. No main, new branch,
force push, PR merge, frozen docs/, or Phase 4.8.

- Last VERIFIED product source `c41ea3e8fad879f0ca825682786433d7066a54ef`.
  GitHub Actions **36637242297 SUCCESS all SIX jobs**:
  backend **816 passed, 15 deselected, 21515 warnings in 293.32s**;
  authenticated browser **15 passed, 232 warnings in 73.08s**;
  frontend lint/typecheck/build, platform-admin, security, staging PASS.
  TESTS NOT RUN locally. Verified Alembic **6f9e2a7d4c1b** /
  **176 model tables**. Latest docs-only verified-handoff
  commit `a5e45e0c` does NOT establish new product test.
- Verified appeal case state, direct board UPHELD/VACATED outcome,
  private evidence, role isolation, audit, open/vacated holds
  on new fine receipt/GL issuance, and separate receipt then fine
  reversal with an explicit pending correction indication.
  Original protected accounting and ARC remains unchanged.
- NEXT BATCH is PROVISIONAL delegated BOARD PORTAL fine-appeal
  disposition: restricted GET `/api/hoa/board/my-fine-appeals`
  enumerates only OPEN appeal records for currently live,
  verified board seats with exact association/property/contact
  membership, paid HOA gates, live case/fine. Its dedicated
  board portal UI sends the existing board-authorized appeal
  decision (no independent legal gate or new posting).
  Focused backend regression and authenticated browser navigation
  exercise an appeal opened in property compliance, decided
  through the board portal, then accounting in the property panel.
  NO migration or new model; expected head remains
  6f9e2a7d4c1b, 176 tables. Existing six-job CI has NOT
  tested this provisional batch.
- NEXT: commit proposed changes on THIS branch, obtain actual
  GitHub Actions six-job CI, repair failures; mark verified ONLY
  after all six pass on the new product SHA. Update this root
  handoff with real test counts and exact next independent
  Phase 4.7 operational requirement. Continue another batch
  if possible without user approval.
- Preserve seven operational HOA capabilities and the existing
  $79/month entitlement. Do not conflate a book GL reversal
  with actual bank movement, SMTP acceptance with statutory
  service or staff uploads with independent law certification.

---

# AI_HANDOFF.md — 2026-09-29 HOA FINE APPEAL VERIFIED

**READ ENTIRE FILE.** This section supersedes historical PREPARED/NEXT
entries below. ONLY `yasirskhan/property-platform` branch
`chatgpt/checkpoint-005-safety`. No main, new branch, force-push,
frozen docs/, merge or Phase 4.8.

- Last VERIFIED PRODUCT source:
  `c41ea3e8fad879f0ca825682786433d7066a54ef`. Hosted GitHub Actions
  **36637242297 SUCCESS ALL SIX JOBS on this source**:
  backend **816 passed, 15 deselected, 21515 warnings in 293.32s**;
  authenticated browser **15 passed, 232 warnings in 73.08s**.
  Frontend lint/TypeScript/build, platform-admin, security and
  staging-config PASS. **TESTS NOT RUN locally.**
  Verified Alembic **6f9e2a7d4c1b** / **176 model tables**.
  Previous head c8e0a2f4b6d9 / 175.
- VERIFIED current Phase 4.7 violation batch: staff records
  an association fine appeal against the final board-approved fine;
  authorized board directly records UPHELD or VACATED with
  redacted immutable audit and private case-linked evidence.
  Idempotent request keys, at most one open appeal per fine,
  same-org/property/association security, and current board seat
  / paid entitlement checks protect write and read endpoints.
  OPEN or VACATED appeal prevents NEW fine GL issuance and member
  receipt allocation. Actual fine receipt/GL reversals remain
  independent protected accounting actions. A VACATED appeal
  never silently refunds money, erases original entries, sends
  correspondence or proves legal service. Customer case UI
  records outcome and separately displays pending accounting
  reversal. Dedicated browser covered first appeal UPHELD,
  a later VACATED appeal, receipt reversal, fine GL reversal,
  and zero unintended tenant Charge effects.
- Initial provisional product `89c50a2b` CI 36637162406 was
  superseded/cancelled. Browser refresh correction
  `c41ea3e8` is the exact tested and verified product
  SHA. Do NOT claim cancelled CI passed or staged blobs tested
  before commits.
- Exact NEXT independent Phase 4.7 batch: show pending fine
  appeals in the AUTHENTICATED HOA BOARD PORTAL so a delegated
  verified board member can decide without organization-wide
  staff property permissions. Reuse existing `_board_scope`,
  association/property contact linkage, paid gates and the
  VERIFIED fine-appeal POST endpoint; do not rebuild appeal
  storage or issue accounting mutations. Add scoped board
  listing, portal UI and focused backend + browser coverage.
  One provisional commit, fix CI and mark verified ONLY when
  six jobs pass. Then update this handoff and continue further
  independently actionable HOA functionality.
- Preserve seven original operational HOA capabilities,
  direct operative ARC APPROVED/DENIED with fees and retries,
  real member assessments/receipts/statements, fine receipts,
  governing delivery, meeting votes/minutes, budgets,
  reserve booked GL, and $79/month entitlement. No blanket
  legal-effect gate, no invented deadlines, no financial
  or legal delivery claims from synthetic CI.

---

# AI_HANDOFF.md — 2026-09-29 HOA FINE APPEAL PROVISIONAL

**READ ENTIRE FILE. This newest checkpoint supersedes older NEXT and
PROVISIONAL status labels below, preserved as history.**
Repository `yasirskhan/property-platform`; ONLY branch
`chatgpt/checkpoint-005-safety`. No main, new branch,
force-push, PR merge, frozen docs/, or Phase 4.8.

- Last VERIFIED product source:
  `99b7728cf57c8bef66b149cf04e89a5b35e30504`;
  GitHub Actions **36632320665 SUCCESS all SIX jobs** on exact
  SHA. Backend **814 passed, 15 deselected, 21336 warnings in
  280.51s**; authenticated E2E **15 passed, 232 warnings in
  70.77s**. Frontend lint/TS/build, platform-admin, security
  and staging-config PASS. **TESTS NOT RUN locally.**
  Verified Alembic **c8e0a2f4b6d9**, **175 model tables**.
  Previous handoff's fine-payment unverified label is historical:
  partial/full offline-recorded fine receipts, central Receipt and
  balanced GL, audit/replay guards, member scope, receipt reversal
  and paid-fine GL reversal protection are VERIFIED in 99b7728c.
  No real bank capture/real-world CI payments.
- Current NEW batch: HOA fine appeal intake and authorized association
  board UPHELD/VACATED disposition. Proposed migration
  `6f9e2a7d4c1b` (after c8e0a2f4b6d9),
  anticipated **176** tables, NOT VERIFIED until SIX green jobs.
  Record one open appeal per fine, request-key replay guards, private
  optional evidence, association/property scopes, direct
  board-authorized disposition, immutable audit/redacted private
  narrative and history. OPEN/VACATED holds newly created fine
  GL posts/receipts. VACATED does NOT automatically erase
  earlier fine, undo settled receipts, refund cash, email members
  or post GL; previously verified receipt-specific reversal must
  precede separately authorized fine reversal. The UI explicitly
  shows pending accounting correction after vacatur.
  Includes focused backend, migration, and dedicated HOA browser
  extension. No new generalized legal deadlines invented.
  **Provisional product CI has not yet been verified.**
- NEXT: inspect CI for this exact new product commit; repair
  failures autonomously on same feature branch. Mark verified only
  when six jobs pass; record exact product SHA, counts, migration
  and schema. Then immediately continue an independently actionable
  Phase 4.7 operational HOA batch; do not stop at green CI.
- Preserve existing operative ARC direct APPROVED/DENIED and fees,
  approved member dues and receipts, board meetings/decisions,
  reserve GL, governing delivery, budgets and paid $79/month HOA
  entitlement; no blanket platform certification gate. User requires
  all SEVEN HOA capabilities real and tested, and no Phase 4.8 until
  independently actionable HOA work completes.

---

# AI_HANDOFF.md — 2026-09-29 HOA FINE RECEIPT E2E CORRECTION

The Phase 4.7 fine-payment implementation remains PROVISIONAL.
First source `d95fda55` / Actions 36630385628 failed only
five Alembic/bootstrapping tests due to a duplicate revision ID.
Corrected source `76d6519e` / Actions 36631193524 passed
backend **814 passed, 15 deselected, 21336 warnings in 221.94s**,
frontend, platform-admin, security, staging. E2E **14 passed,
1 failed**. The sole browser failure was a non-specific locator
matching a receipt reversal text before the fine-GL reversal had
completed; the test asserted GL count too early. This new test-only
correction anchors the browser wait to the exact board fine
status line. The source business logic is unchanged.
**NOT VERIFIED** until all six jobs on the new corrected
product SHA pass. Verified product remains `f82561f9`,
Alembic f2b4d6e8a0c3 / 174 tables until that point.
Next: fetch new CI, address any genuine failure, then
record final implementation SHA, test counts, new revision
c8e0a2f4b6d9 / 175 tables in root handoff. Continue
board appeal/correction history independently afterward.

---

# AI_HANDOFF.md — 2026-09-29 HOA FINE RECEIPTS PROVISIONAL

**Read the ENTIRE file.** This newest record supersedes historical NEXT
and PROVISIONAL headings below. Repository
`yasirskhan/property-platform`, ONLY branch
`chatgpt/checkpoint-005-safety`. No main, new branches,
force pushes, PR merge, frozen docs/ changes or Phase 4.8.

- Last VERIFIED product source `f82561f9ecc42ebef26e273a0acd9e7dac97f255`.
  GitHub Actions **36620561609 SUCCESS ALL SIX jobs**:
  812 backend passed, 15 deselected; 15 authenticated browser tests.
  Verified Alembic `f2b4d6e8a0c3` / 174 model tables.
  The docs-only HEAD `31e0c68e` passed all six CI jobs
  in **36621779725**, without advancing the product source.
- Latest Phase 4.7 violation fine RECEIPTS batch is PROVISIONAL,
  NOT YET VERIFIED. Reuses the existing Receipt, ReceiptLine
  and balanced central GL for cash received offline and allocated
  to the exact POSTED board-approved fine. Adds idempotent
  partial/full payments, history and scoped reversal, separate
  cash/receivable accounts, verified member identity, active
  accounting/HOA permissions, locked period, deposited-receipt
  denial, audit, duplicate prevention and payment-aware fine
  reversal guard. Generic receipt reverse/NSF cannot bypass
  HOA_FINE allocation rollback. No bank/card collection or
  real-world obligation is initiated by synthetic tests.
- Proposed Alembic `c8e0a2f4b6d9` after f2b4d6e8a0c3,
  EXPECTED 175 tables. First provisional source d95fda55 CI 36630385628 FAILED five bootstrap/migration tests (809 passed, 5 failed, 15 deselected): the proposed revision a3c5e7f9b1d4 collided with pre-existing LIHTC revision. Corrected revision c8e0a2f4b6d9 has unique filename/revision. All non-migration tests passed at the first source. Do NOT advance verified migration/table
  count until all SIX GitHub Actions jobs PASS on the product
  commit. Backend/HOA browser regressions, frontend UI and
  migration guards are included. TESTS NOT RUN locally.
- Next action: inspect CI on the provisional commit, correct any
  failing tests or product code on this same branch, then mark
  VERIFIED only when backend, frontend, platform-admin,
  security, staging and authenticated E2E all pass. Record
  actual positive counts and source SHA in a new top-of-file
  handoff checkpoint. Continue the next independently actionable
  Phase 4.7 HOA violation appeal/correction workflow.
- Preserve operative ARC APPROVED/DENIED, other verified HOA
  assessment/receipt/statements, board minutes/voting,
  annual budgets, reserve GL, documents and $79/month
  paid HOA entitlement. Association decisionmakers authorize
  their actions, no blanket platform legal-effect gate;
  enforce exact procedural and payer safeguards.

---

# AI_HANDOFF.md — 2026-09-29 HOA OPERATIVE FINES VERIFIED

**Read this entire file.** This newest status supersedes older NEXT and
PROVISIONAL entries, which remain below as historical evidence.
Repository `yasirskhan/property-platform`, ONLY branch
`chatgpt/checkpoint-005-safety`. No main, new branches, force pushes,
PR merge, frozen docs/ edits or Phase 4.8.

- Last VERIFIED PRODUCT SOURCE
  `f82561f9ecc42ebef26e273a0acd9e7dac97f255`.
  GitHub Actions **36620561609 SUCCESS all six jobs on this SHA**:
  backend **812 passed, 15 deselected, 21095 warnings in 288.63s**;
  authenticated browser **15 passed, 230 warnings in 71.09s**;
  frontend lint/TypeScript/production build, platform-admin, security
  and staging-config all PASS. **TESTS NOT RUN locally**.
- Verified Alembic **f2b4d6e8a0c3**, expected **174 model tables**;
  prior e1a3c5f7b9d2/173. PostgreSQL, migration and staging checks
  passed on the exact verified source.
- VERIFIED Phase 4.7 violation fine work: the association's authorized
  board records APPROVED or DENIED on a case after its configured
  documented service, cure/hearing opportunity, live private evidence
  and verified member controls. Hearing-held outcomes record date and
  privately retained case proof. A distinct accounting-authorized
  action posts approved member receivable/income through the
  existing balanced central GL with locked-period and replay
  protections; an explicit reversal retains the immutable trail.
  No tenant Charge, legal validity certification or SMTP-based
  service presumption. Tests cover unauthorized/foreign access,
  mismatched member, service/policy revisions, fine cap, hearing
  proof, denial, duplicate decision and posting, GL reversal,
  closed-period safeguards and private evidence retention.
  Dedicated synthetic HOA browser covers decision -> posting ->
  reversal. This is not a production financial posting from CI.
- Initial provisional product commit `dd0e5c49` CI
  **36619966428 FAILED** only two test fixtures:
  810 passed, 2 failed, 15 deselected; frontend/security/admin
  green; E2E/staging skipped. Test-only correction
  `f82561f9` supplied required hearing date and explicit synthetic
  attachment feature in proof-retention test; subsequent full
  **36620561609 SUCCESS**. Never attribute passing tests to the
  failed initial SHA. Older provisional handoff below is historical.
- Original seven operational HOA areas remain Phase 4.7 priority;
  preserve direct operative ARC board decisions, member dues,
  existing receipt/statement flow, board votes, reserve GL,
  budgets, documents and $79/month paid entitlement.
- Exact NEXT independently actionable Phase 4.7 violation task:
  **offline-recorded fine-specific member receipts/partial/full
  allocation and reversal** against the posted fine, reusing central
  Receipt/ReceiptLine and GL, correctly confirmed member, scoped
  accountant, cash-like GL, deposits/locked periods, idempotency,
  no overpayment or reversal of an allocated receivable.
  Distinguish actual recorded offline funds from bank/processor
  collection; no tenant receipt or duplicate ledger. Add focused
  backend and dedicated HOA browser coverage. A paid fine's
  GL original cannot be reversed until its receipts are reversed.
  Follow with appeal/correction tracking; no guessed legal deadlines
  or a blanket platform legal certification gate. Continue
  remaining independent HOA work without repeating completed batches.

---

# AI_HANDOFF.md — 2026-09-29 HOA BOARD FINE PROVISIONAL

**Read this ENTIRE root handoff.** This entry supersedes earlier
NEXT/PREPARED headings. Work only `yasirskhan/property-platform`
branch `chatgpt/checkpoint-005-safety`. No main, new branch,
force-push, PR merge, frozen docs/ or Phase 4.8.

- Last VERIFIED PRODUCT source:
  `195a048194ad44a1fc4ddd5453d03484c407d97b`.
  GitHub Actions **36615815202 SUCCESS ALL SIX**:
  backend **808 passed, 15 deselected, 20770 warnings in 211.50s**;
  authenticated browser **15 passed, 226 warnings in 68.21s**;
  frontend lint/TypeScript/build, platform-admin, security and staging
  all PASS. No local tests.
  Verified Alembic **e1a3c5f7b9d2 / 173 model tables**.
- NEXT Phase 4.7 violation batch is assembled/provisional:
  direct association-board fine APPROVED/DENIED and separate
  accountant-authorized central member GL posting/reversal,
  with privately evidenced service, configured cure/hearing periods,
  verified matched liable member, actual hearing date/proof when
  held, configured cap, immutable board outcome, duplicate controls,
  GL period locks, provenance and audit. Real fines must be
  explicitly authorized; a staff proposal/SMTP_ACCEPTED event
  NEVER becomes liability automatically. General ledger uses
  existing `post_transaction`, not a second ledger or tenant Charge.
- One proposed migration `f2b4d6e8a0c3` after e1a3c5f7b9d2;
  EXPECTED **174 model tables**, but verified head/count remain
  **e1a3c5f7b9d2 / 173** until this batch passes all SIX CI jobs.
  Hosted GitHub Actions must run on an actual provisional feature
  branch commit. Tests are NOT RUN for the proposed fine batch
  until that run completes. No real notices or financial
  obligations may be triggered by disposable CI fixtures.
- Focused tests check board/role/foreign-property/member isolation,
  service and hearing prerequisite, duplicate request and status,
  approved GL, reversal, locked period, audit redaction, private
  hearing proof retention and zero tenant Charge. Existing dedicated
  synthetic HOA browser extends case to fine board decision, member
  receivable GL and reversal. Preserve operative ARC direct
  APPROVED/DENIED, assessments/payments, board meetings/votes,
  reserve GL, budgets, governing documents and paid $79 add-on.
- AFTER six CI jobs pass, update this handoff with exact source,
  backend/browser counts, migration and 174 tables. Next
  independently actionable Phase 4.7 batch: member fine receipt
  allocation, reversal protection and an integrated board-case
  appeal/correction history. Continue remaining seven operational
  HOA areas without restarting verified features. Block only
  individual transactions missing concrete prerequisites.

---

# AI_HANDOFF.md — 2026-09-29 HOA SERVICE PROOF VERIFIED

**Read the entire file.** This is the newest status; historical
PROVISIONAL and NEXT headings below are superseded. Only branch
`chatgpt/checkpoint-005-safety` in `yasirskhan/property-platform`.
Do not modify main/frozen docs, add branches, force-push, merge or
advance Phase 4.8.

- VERIFIED PRODUCT source `195a048194ad44a1fc4ddd5453d03484c407d97b`.
  GitHub Actions **36615815202 SUCCESS all six jobs**.
  Backend **808 passed, 15 deselected, 20770 warnings in 211.50s**;
  authenticated browser **15 passed, 226 warnings in 68.21s**;
  frontend lint/TypeScript/build, platform-admin, security and
  staging-config SUCCESS. **TESTS NOT RUN locally**.
- Verified Alembic head **e1a3c5f7b9d2**, expected **173 tables**,
  up from d0f2a4c6e8b1 / 172. Fresh/legacy/PostgreSQL/staging guards
  passed on the same product source.
- Newly VERIFIED: association-authorized recorded actual notice
  service with exact private correspondence/policy revision, matching
  verified recipient, dated method, case-linked retained PRIVATE
  service proof, audit and case/request idempotency. The board supplies
  its service record; the platform does not independently certify
  compliance. SMTP_ACCEPTED/TEST_ONLY are not by themselves proof
  of service. The case browser exercises this flow with synthetic
  data. NO fine, charge or central GL posting in this batch.
- Source correction history: initial d4f75f04 and several
  successive product/test corrections; final test-only fixture
  correction `195a048194ad44a1fc4ddd5453d03484c407d97b` passed all six. The previous
  `195a` handoff's PREPARED label below is historical and must
  not cause this feature to be repeated.
- NEXT independently actionable Phase 4.7 violation batch:
  actual association board-recorded fine decision and separately
  permissioned member-ledger GL posting/reversal; reuse existing
  case, service evidence, verified member, real receipt/assessment
  posting infrastructure. Scope by live association/property,
  board seat, correctly matched member and actual case policy.
  Check service/cure/hearing prerequisites, amount cap, board
  outcome, central GL lock, idempotency and reversal. Do not
  infer legal delivery from SMTP or invent liability. Unsupported
  individual operations stay pending, not the whole project.
- Seven original HOA operational capabilities remain required.
  Preserve ARC direct APPROVED/DENIED, current member payments,
  board decisions, reserve GL, budget, documents and $79/month
  catalog/entitlement. No production notices or real financial
  obligations merely from synthetic CI.

---

# AI_HANDOFF.md — 2026-09-29 HOA SERVICE PROOF PROVISIONAL

**Read the entire file.** This new entry supersedes older NEXT/PREPARED
sections; historical source and CI facts are preserved below.
Only `yasirskhan/property-platform` branch
`chatgpt/checkpoint-005-safety`. No main, new branch, force-push,
PR merge, frozen docs/ edits, or Phase 4.8.

- Last VERIFIED PRODUCT source `e9156f611c77031acb43f0b90530f00b4f25c3fe`,
  CI **36609991874 SUCCESS all six jobs**: backend 806 passed,
  15 deselected; authenticated browser 15 passed. Migration
  `d0f2a4c6e8b1`, **172 model tables**.
- Subsequent documentation-only HEAD `fdc5328a8205df2239ab531a18c24ef52dbbf1ad`
  CI **36611150653** initially failed one transient browser login
  navigation, 14 passed/1 failed; rerun attempt 2 passed
  **15 E2E**, all six jobs SUCCESS. This did NOT change or independently
  advance verified PRODUCT source.
- This session's NEXT independent Phase 4.7 violation batch is
  **association-reported actual notice-service evidence**, extending
  already verified exact correspondence, verified recipient,
  authorized board seat, procedure settings, private case evidence
  and paid HOA scopes. Implementation source is PROVISIONAL until
  GitHub Actions runs all six jobs on the exact product commit.
  One new append-only model `hoa_violation_service_records` and
  migration `e1a3c5f7b9d2` after d0f2a4c6e8b1;
  EXPECTED table count 173, but VERIFIED head/count remains d0/172
  until six CI green.
  Association-authorized verified board actor records specific
  served-on date/method, exact latest correspondence revision,
  same-scope verified recipient, current policy revision, and
  active PRIVATE CASE-LINKED proof. Retain immutable identity,
  policy, evidence and staff actor snapshot. Unique case/request
  key, duplicate/replay checks, age/rule constraints, audit redaction
  and zero finance. Dedicated HOA case browser extension uses synthetic
  evidence, no production notice.
  This event captures what the association reports and independently
  evidences; the platform does not certify legal service.
  SMTP_ACCEPTED/TEST_ONLY alone never qualifies as proof.
  Original case evidence proof cannot be archived while referenced.
- After verification, NEXT Phase 4.7 violations work: separately
  recorded authorized fine decision and properly gated central
  GL member-receivable posting/reversal. Require case-specific
  service/procedure/hearing prerequisites and correct verified payer.
  An SMTP transport event alone is never legal service; an association
  service record alone never automatically assesses a fine.
  Block only missing individual prerequisites; continue independent
  operational HOA batches. Preserve direct operative ARC board
  APPROVED/DENIED, member assessment and receipt postings,
  board outcomes, reserve GL, budgets, governing documents and
  $79/mo entitlement. **TESTS NOT RUN locally.**

---

# AI_HANDOFF.md — 2026-09-29 HOA CASE EMAIL VERIFIED

**Read the entire repository-root file.** This header supersedes all
earlier NEXT/PREPARED labels, preserved below as history. Work only
`yasirskhan/property-platform` branch
`chatgpt/checkpoint-005-safety`. Do not touch main, frozen docs/,
create a new branch, force push, merge or advance Phase 4.8.

- Latest VERIFIED PRODUCT source `e9156f611c77031acb43f0b90530f00b4f25c3fe`.
  GitHub Actions [36609991874](https://github.com/yasirskhan/property-platform/actions/runs/36609991874)
  **SUCCESS all SIX jobs**, exact source. Backend **806 passed,
  15 deselected, 20636 warnings in 229.58s**. Authenticated
  E2E **15 passed, 226 warnings in 68.09s**. Frontend lint,
  TypeScript/production build, platform-admin, security, staging PASS.
  **TESTS NOT RUN locally.**
- Verified migration **d0f2a4c6e8b1**, SQLAlchemy expected **172
  model tables**, preceding c9e1f3b5d7a0 / 171. Fresh/legacy/PostgreSQL
  and staging checks passed.
- Actual authenticated association BOARD and permitted staff member may
  explicitly request email transport of the current exact private
  HOA violation correspondence, after live org/property/paid HOA,
  verified matching recipient, stage, notice and cure policy revision,
  and board-seat authorization checks. A durable idempotent record
  captures attempts, TEST_ONLY console, FAILED, SMTP_ACCEPTED, and
  redacted audit; retries revalidate live constraints. Snapshot email,
  revision and board seat remain private. Browser exercises a synthetic
  console-only attempt with **ZERO finance**. No statutory service is
  certified merely because SMTP accepts email. No fine/charge, liability
  or GL posting. SMTP retry is at-least-once when prior acceptance is
  uncertain; do not claim exactly-once external email delivery.
- Initial provisional source `e9156f611c77031acb43f0b90530f00b4f25c3fe` passed all six jobs
  without corrective product commits. Previously approved motion
  outcomes `a2edafce` / CI 36604831597 remain preserved.
  Historical "CASE CORRESPONDENCE EMAIL PROVISIONAL" heading below
  describes the state before this verified commit, NOT pending work.
- Original SEVEN operational Phase 4.7 features remain the scope.
  Preserve member dues/receipts/statements, authenticated board
  outcomes, operative ARC direct APPROVED/DENIED, reserve-book GL,
  annual budget/increases, governing documents, $79/month HOA paid
  entitlement and verified case tasks. No blanket platform legal
  certification gate.
- **NEXT independently actionable Phase 4.7 violation batch:**
  association-authorized fine decision + accounting, extending the
  existing FINE_PROPOSED case, verified contact/member identity,
  configurable procedure and real central GL posting. Require a
  specific authorized board decision, applicable association-entered
  notice/hearing prerequisites, an explicitly confirmed responsible
  member, actual scoped receivable/income accounts, idempotency,
  locked-period protections, reversals and immutable audit. If an
  individual real-world fine lacks an applicable procedural record,
  keep THAT action pending; do not manufacture broad HOA blockers.
  Do not infer legally effective service from SMTP_ACCEPTED alone.
  Add focused security/backend and dedicated browser tests. Only
  synthetic CI posts, never real-world financial obligations.
  After six jobs pass, update this file and immediately continue
  another independent HOA batch. Phase 4.8 PAUSED.

---

# AI_HANDOFF.md — 2026-09-29 CASE CORRESPONDENCE EMAIL PROVISIONAL

**READ ENTIRE ROOT HANDOFF.** Latest independent VERIFIED product source
`a2edafce2aa224b4e5aa798888003526e85b3e0f`; CI
[36604831597](https://github.com/yasirskhan/property-platform/actions/runs/36604831597)
SUCCESS all six: **803 backend passed, 15 deselected, 20423 warnings**;
**15 browser passed, 224 warnings**. Alembic verified
`c9e1f3b5d7a0` / **171 model tables**.
Handoff-only `ac0a7a7` changed no product source.

**PROVISIONAL NEXT BATCH, NOT VERIFIED:** Phase 4.7 association board-
authorized actual email transmission of a current private case
correspondence revision, extending already verified observation, case,
procedure, matched verified recipient, correspondence, board-seat
delegation, paid HOA feature gates and existing email SMTP implementation.
No invented law, statutory service, case-level liability, member charge,
fine or GL effect. Exact case/policy/stage/recipient identity checks
before every attempt. A current verified authorized board AND existing
admin/staff contact permission must explicitly request. Durable
idempotent outbox, retry on failure, console-mode TEST_ONLY,
SMTP_ACCEPTED distinct from proof of inbox receipt, immutable redacted
audit and private history. Case/recipient/policy revision changes block
unattempted and retried sends; stale correspondence never silently
sent. Browser covers disposable console-only transmission with zero
finance. No production email is sent merely by CI.

Prepared proposal: new migration `d0f2a4c6e8b1` after verified
`c9e1f3b5d7a0`; expected model-table count **172** only if all six
CI jobs pass. GitHub Actions must run against the exact provisional
feature-branch product commit; local tests **TESTS NOT RUN**.
After full green record actual SHA/counts/migration and continue
another independently actionable original Phase 4.7 batch. If CI
fails, fix it autonomously without touching main/frozen docs/,
creating branch, force push, merging or advancing Phase 4.8.
Preserve direct operative ARC decisions, current board outcome
and prior verified member assessments/receipts, reserve GL,
budget approval and documents.

---

# AI_HANDOFF.md — 2026-09-29 BOARD MOTION OUTCOMES VERIFIED

**READ THIS ENTIRE ROOT FILE.** This newest checkpoint supersedes all historical
NEXT/PREPARED headings below, which remain preserved for audit. Only repository
`yasirskhan/property-platform`, branch `chatgpt/checkpoint-005-safety`.
Do not modify main, create branches, force push, edit frozen docs/, merge,
or advance Phase 4.8.

- Latest VERIFIED PRODUCT source `a2edafce2aa224b4e5aa798888003526e85b3e0f`.
  GitHub Actions [36604831597](https://github.com/yasirskhan/property-platform/actions/runs/36604831597):
  **SUCCESS all SIX jobs on exact source**. Backend **803 passed,
  15 deselected, 20423 warnings in 154.65s**; authenticated browser
  **15 passed, 224 warnings in 66.43s**. Frontend lint, TypeScript,
  build, platform-admin, security, staging-config SUCCESS.
  **TESTS NOT RUN locally.**
- Verified Alembic head `c9e1f3b5d7a0`, **171 model tables** (was
  `b8d0f2a4c6e9` / 170). Fresh/legacy/PostgreSQL and staging PASS.
- VERIFIED operational board motion final outcome: an authorized verified
  association board member explicitly finalizes the exact immutable
  current motion SHA-256 and recorded individual vote-register digest
  using CURRENT board-adopted quorum/approval revision. Recorded
  `PASSED` or `NOT_PASSED` and snapshots of FOR/AGAINST/ABSTAIN,
  thresholds, adoption revision and recorder are immutable with redacted
  audit; stale changes or lack of quorum fail closed, duplicate races are
  serialized, later voting is rejected. This is actual association
  decision recording, NOT the platform's independent legal
  certification or automatic GL/notice.
- The older "BOARD MOTION OUTCOME PROVISIONAL" section below is now
  HISTORICAL. Corrective source `a2edafce` completed all six jobs.
  Earlier source `b7181855` and `b86339c2` CI runs were cancelled,
  not counted as passing.
- Preserve existing authenticated board portal, quorum rule adoption,
  vote history, ARC direct APPROVED/DENIED and protected fees/reversals,
  member assessments/receipts/statements, approved annual budget and
  increase GL, reserve GL book, private governing documents/delivery,
  HOA violations/case follow-ups and paid $79/mo entitlement.
- **NEXT independently actionable original Phase 4.7 feature: actual
  violation notification delivery and decision/cure workflow**,
  extending EXISTING private case correspondence, verified contact,
  staff-configured procedure and existing email/outbox. Require an
  authenticated association-authorized decision, current recipient
  identity, current correspondence revision and configured notice/cure
  prerequisites before an explicit send. Distinguish SMTP transport
  acceptance from proof of statutory service; no invented legal
  deadline, fine, debtor or charge. Implement a bounded end-to-end
  workflow, focused backend/security/browser tests, provisional commit
  on only feature branch, six green CI jobs, then refresh this handoff.
  If a particular delivery method or rule requires external inputs,
  block only that action and continue independent HOA operations.
- User's original SEVEN Phase 4.7 capabilities remain scope. Do not
  substitute additional endless draft screens for working workflows.
  Do not reinstate blanket platform legal-authorization gate.
  No live customer messages or real-world financial obligations
  from disposable CI. Phase 4.8 PAUSED.

---

# AI_HANDOFF.md — 2026-09-29 BOARD MOTION OUTCOME PROVISIONAL

**Read this entire root file.** Latest verified checkpoint is below;
historical NEXT labels are superseded. Repository
`yasirskhan/property-platform`, ONLY existing
`chatgpt/checkpoint-005-safety`. No main, frozen docs/,
new branches, force push, merge or Phase 4.8.

- Last VERIFIED PRODUCT source `199e72b10dafdbe2546f4c1f1aad8f264d677487`.
  GitHub Actions **36602554783 SUCCESS ALL SIX JOBS**;
  backend **801 passed, 15 deselected, 20281 warnings**;
  authenticated browser **15 passed, 224 warnings**;
  frontend lint, TypeScript/build, platform admin, security,
  staging PASS. **TESTS NOT RUN locally**.
  Verified Alembic `b8d0f2a4c6e9`, **170 model tables**.
  Latest handoff-only commit `3823e0dc744eb5b767310aa9f34caa1f1c1f53e4`
  records that checkpoint; it did not add product behavior.
- NEXT Phase 4.7 board source batch: **PROVISIONAL ONLY** until
  its own six green CI jobs: board member explicitly finalizes an
  exact current motion SHA and immutable per-seat voting register
  against the association's adopted quorum/approval rule snapshot.
  Outcome PASSED or NOT_PASSED is recorded with immutable tally,
  adoption revision, identity and audit. Missing/stale/no quorum
  fails closed, concurrent changes serialized, additional votes
  on a finalized motion rejected. No GL, notice or platform law
  certification. Proposed migration `c9e1f3b5d7a0` after b8d0f2a4c6e9;
  expected **171 model tables** only if new CI passes.
  Focused backend plus authenticated HOA board-browser test extended.
- After full green CI, record verified exact product SHA, run, actual
  tests and migration here and continue next Phase 4.7 operational
  HOA batch. Preserve real member charges/receipts/statements,
  operative ARC direct decisions and protected fees/notifications,
  reserve GL book, approved budget/increases, governing documents,
  $79 HOA entitlement, case follow-ups. No invented member
  liability, external bank movement or statutory delivery.
  User requires SEVEN actual operational areas, not preparation
  screens. Do not restore blanket legal-certification gate.

---

# AI_HANDOFF.md — 2026-09-29 BOARD RULE ADOPTION VERIFIED

**READ THE ENTIRE ROOT HANDOFF.** This latest status supersedes old
PREPARED/NEXT labels. Only `yasirskhan/property-platform` on existing
`chatgpt/checkpoint-005-safety`. No main, frozen docs/, new branch,
force push, merge or Phase 4.8.

- Last VERIFIED PRODUCT source `199e72b10dafdbe2546f4c1f1aad8f264d677487`.
  GitHub Actions [36602554783](https://github.com/yasirskhan/property-platform/actions/runs/36602554783)
  **SUCCESS ALL SIX JOBS** on the exact source. Backend **801 passed,
  15 deselected, 20281 warnings in 259.35s**; authenticated browser
  **15 passed, 224 warnings in 66.58s**. Frontend lint, TypeScript,
  production build, platform-admin, security, staging-config PASS.
  **TESTS NOT RUN locally**.
- Verified Alembic `b8d0f2a4c6e9`, **170 model tables** (previous
  a7c9e1f3b5d8 / 169). PostgreSQL, fresh/legacy schema and staging
  guards passed in verified source CI.
- Last VERIFIED Phase 4.7 board batch: current authorized authenticated
  association board member adopts the organization's explicitly
  configured quorum/approval proposal revision. New immutable
  `hoa_board_rule_adoptions` snapshots the two numbers, exact
  configured revision digest, authorized board seat, actor and time.
  Missing/incomplete/stale/repeated proposal decisions fail closed
  or replay idempotently. Reconfiguring staff rules requires new
  explicit board adoption for the new revision; earlier history
  stays immutable. Scoped live HOA entitlement, active board seat,
  property and organization checks, audit, generic notes denylist
  and zero financial side effects are tested. Dedicated browser
  covers configuration and direct board adoption. No platform legal
  certification, default legal threshold, automatic motion outcome,
  external notice, fee, account movement or third-party approval.
- Historical PREPARED section below is the prior state of the now
  VERIFIED source, not unfinished product work.
- **EXACT NEXT Phase 4.7 board batch:** Explicit authorized motion
  outcome recording against the CURRENT adopted quorum/approval
  revision, exact immutable recorded member votes and motion SHA.
  A board member confirms a final tally on an active meeting; no
  unconfigured default thresholds, inaccurate quorum, duplicate
  decision, extra vote after finalization, cross-organization leakage,
  or altered motion. Preserve immutable source-vote evidence and
  record the actor, adoption revision, tally and result with audit.
  Do not automatically issue notices, authorize funds or certify
  jurisdiction-specific legal compliance. Add focused backend and
  dedicated authenticated browser tests. After six green CI jobs,
  update this root handoff and immediately continue the next
  independent uncompleted HOA feature.
- User requires SEVEN operational HOA capabilities, not endless
  draft screens: member dues/receipts/statements, violation
  notice/cure/fines/hearings, board, ARC, reserve GL, governing
  documents and annual budget/increases. Preserve completed
  operative ARC APPROVED/DENIED, real member receivables,
  verified reserve book, document delivery, internal case
  follow-ups and $79/month paid HOA entitlement. Specific missing
  procedural/payer/GL inputs block only that operation; do not
  invent law, liable member, delivered notice or bank transfer.
  Phase 4.8 remains PAUSED.

---

# AI_HANDOFF.md — 2026-09-29 BOARD VOTE REGISTER VERIFIED

**READ THE ENTIRE ROOT HANDOFF.** This is the latest verified
checkpoint. Previous PREPARED and NEXT labels are historical.
Repository `yasirskhan/property-platform`, ONLY branch
`chatgpt/checkpoint-005-safety`. Never touch main, frozen docs/,
create another branch, force push, merge or advance Phase 4.8.

- Verified PRODUCT source `3bd9f11c828c089dbf36dd0f50f1741b0d395d7f`.
  [GitHub Actions 36597915429](https://github.com/yasirskhan/property-platform/actions/runs/36597915429)
  **SUCCESS, all SIX jobs**. Backend **799 passed, 15 deselected,
  20163 warnings in 271.73s**; authenticated browser **15 passed,
  224 warnings in 65.36s**; frontend lint/TypeScript/build,
  platform-admin, security, staging-config PASS.
  **TESTS NOT RUN locally.**
- Alembic `a7c9e1f3b5d8`, **169 model tables**. No new migration.
- Authenticated active association board members now see the
  historical per-motion seat/vote register plus FOR/AGAINST/ABSTAIN
  totals, alongside their own exact-text immutable vote. All
  reads remain current-seat, current-entitlement, current-property
  scoped; no general account export. Existing user/case/GL/ARC
  source and any prior verified work remain untouched.
- Initial provisional source `9f51d393` failed frontend lint
  from an unclosed JSX conditional. Corrected source
  `3bd9f11c828c089dbf36dd0f50f1741b0d395d7f` passed ALL six jobs. No falsely claimed verification
  on earlier source. The historical vote register represents
  actual recorded choices, NOT an automatic quorum certificate
  or statutory association resolution.
- NEXT independently actionable Phase 4.7 board batch: record
  association-authorized activation of the organization's
  explicitly configured quorum and approval thresholds using
  current verified association board seat and exact staff
  proposal revision, preserving an immutable history. Do not
  invent legal thresholds, infer authority from unauthenticated
  seat proposals or make the platform certify applicable law.
  Follow with explicit board motion outcome execution using
  authorized votes and captured thresholds. Test real board
  interaction and revocation with zero financial effects.
  Continue other operational HOA work if this specific input
  is unavailable; Phase 4.8 remains PAUSED.
- Original SEVEN operational HOA capabilities remain the priority.
  Preserve actual member charges/receipts/statements, budget
  adoption/actuals, operative ARC APPROVED/DENIED with protected
  fees/notifications, reserve GL book, document delivery, private
  case tasks and $79/month entitlement. No automatic external
  money movement, statutory notice, fine or liability from this
  board-vote register. Do not restore a blanket ARC legal-effect gate.

---

# AI_HANDOFF.md — 2026-09-29 BOARD MEMBER VOTES VERIFIED / VOTE REGISTER NEXT

**READ THE ENTIRE ROOT FILE.** This entry supersedes old NEXT and
PREPARED labels below. Only `yasirskhan/property-platform` on existing
`chatgpt/checkpoint-005-safety`. No main, new branch, force push,
frozen docs/, PR merge or Phase 4.8 work.

- Last VERIFIED product source `e1783988f04a55c35f3b6e174c1c07a2b8240d14`;
  GitHub Actions **36594111679 SUCCESS ALL SIX JOBS**, backend
  **799 passed, 15 deselected, 20163 warnings in 213.11s**,
  authenticated browser **15 passed, 224 warnings in 65.77s**.
  Frontend lint/TypeScript/build, platform-admin, security and staging
  PASS. **TESTS NOT RUN locally.**
- Verified Alembic head `a7c9e1f3b5d8`; **169 model tables**.
  Prepared individual vote blobs from historical handoff were committed
  and tested through the corrected product commit above. Previous
  provisional `f7366cec` CI 36592695951 FAILED due to minutes editor
  initial-load race; corrected `e1783988` passed six jobs.
- Completed: currently authorized, verified board-member login votes
  once immutably FOR/AGAINST/ABSTAIN on the exact motion SHA-256 through
  private board portal, idempotent exact replay and conflict detection.
  Meeting and motion updates/archive are protected when voted.
  Organization-scoped entitlement, current seat and source record
  access are rechecked. Recorded votes are NOT quorum certification
  or automatically effective association resolutions.
- NEXT independently actionable Phase 4.7 board batch: show a
  scoped, read-only authenticated member-vote register and FOR/AGAINST/
  ABSTAIN counts for each motion, using existing immutable `HOABoardVote`.
  Add backend + authenticated browser tests; no new migration, legal
  certification, notices, accounting or separate vote storage.
  Provisional commit to ONLY existing branch and verify all six CI
  jobs before marking complete. Then continue the next unblocked
  operational HOA workflow.
- All seven original operational Phase 4.7 HOA areas remain goal.
  Preserve previously verified member assessments/receipts/statements,
  annual budget, ARC direct decisions without blanket legal-effect
  gate, reserve GL book, document delivery, private case tasks, and
  $79/month HOA entitlement. Only specific missing action input
  blocks an individual operation; no inferred law, payer or real
  notice/bank collection. Phase 4.8 PAUSED.

---

# AI_HANDOFF.md — 2026-09-29 BOARD PORTAL VERIFIED / BOARD VOTES PREPARED

**READ THE ENTIRE ROOT FILE.** This latest entry overrides earlier
NEXT/PREPARED status labels, but historical verified entries below stay
unchanged. Repo `yasirskhan/property-platform`, ONLY existing branch
`chatgpt/checkpoint-005-safety`; never touch main, frozen docs/, make
a branch, force-push, merge PR or advance Phase 4.8.

- Last VERIFIED product source:
  `659a499c9ad76afe8cd2751ab0b69767bcbe62c7`.
  GitHub Actions [36591325344](https://github.com/yasirskhan/property-platform/actions/runs/36591325344)
  SUCCESS ALL SIX JOBS on this SHA. Backend **797 passed,
  15 deselected, 20034 warnings in 198.29s**; authenticated browser
  **15 passed, 224 warnings in 64.16s**; frontend lint/TypeScript/build,
  platform-admin, security, staging PASS. TESTS NOT RUN locally.
  Earlier provisional portal `8e94c976` CI `36590469656` FAILED
  one backend regression (`HOAContactLinkOut` response incorrectly
  treated as mutable SQLAlchemy row). Commit `659a499c` fixes the
  test to change persisted `HOAContactLink`; only this corrected
  source is marked VERIFIED.
- Alembic verified head `f6b8d0e2a4c7`; **168 model tables**.
  Current verified portal batch adds NO migration.
- Authenticated board-only `/dashboard/hoa/board` now lists live
  scoped association/property meetings for currently authorized
  verified board logins, including board members without
  organization-wide PROPERTIES.ALL permission. It reads exact
  minutes revision and records the individual authorized member's
  existing immutable minutes approval. Live HOA paid gate, active
  org/contact/seat/membership, E2E navigation, role revocation,
  audit, and zero finance are tested. This is not an official
  quorum or certified full-board vote.
- NEXT batch **PREPARED AS 15 UNCOMMITTED Git blobs**, NOT TESTED,
  NOT VERIFIED: authenticated individual member motion voting
  distinct from old STAFF-REPORTED ballot notes. A board member
  with current live association seat records exactly one
  immutable FOR/AGAINST/ABSTAIN choice for an exact motion
  SHA-256 text, with request replay and collision guards.
  Authenticated board portal gets motion list/own vote and a
  vote button; meeting/motion edits or archive cannot erase a
  recorded vote. Meeting/motion row locks serialize with vote
  insertion to prevent concurrent archive/edit races. No derived quorum/resolution, financial posting,
  statutory notice, law assumption or external message.
  Proposed migration `a7c9e1f3b5d8` follows f6b8d0e2a4c7;
  expected model count **169** is NOT verified until CI passes.
  Complete static review, assemble on current branch using one
  provisional commit and run all six hosted CI jobs; fix reds
  autonomously, then update this handoff and continue independently.
- **Prepared Git blob pointers**:
  - `backend/app/models/hoa_board_vote.py` `727b9e2121c65e5c97517b0756fec63bcdc88b5b`
  - `backend/alembic/versions/a7c9e1f3b5d8_hoa_board_votes.py` `7b04ac029f0f5db44d958559523303df32a6ca40`
  - `backend/app/schemas/hoa_board_vote.py` `a70ed4200749f9485a334e4bd8ca0181b1ee16d2`
  - `backend/app/routers/hoa_board_votes.py` `71ba59d4765793eceb1a023898f63632947663c0`
  - `backend/app/main.py` `c53166963518a815afb71bdf16c565207ec4f763`
  - `backend/init_db.py` `c8bab8ceb560abe241aa0a2af77d031a464dad60`
  - `backend/app/services/entity_notes.py` `fb89cd7f75a3c4f123a0492dd19f6dcedee8a170`
  - `backend/app/routers/hoa_meeting_workspace.py` `b8ff66064b3b4622684b0e134ddd1b4fa45ecdb4`
  - `backend/app/routers/hoa_meeting_drafts.py` `934abe4b97917e7e08914c26157c273757a5c57d`
  - `frontend/src/app/dashboard/hoa/board/page.tsx` `4c3442d88917d98159496dfc081af08047c314c9`
  - `backend/tests/test_hoa_meeting_workspace.py` `ea24764dd49be3cba91ceaf7d247a49273b29b38`
  - `backend/tests/e2e/test_hoa_evidence_e2e.py` `f9d520f46aae3881c9c54b4ca329ce5c605da2f5`
  - `backend/tests/test_migrations.py` `65758a5a425025b760cc40f61ac37fade254ba89`
  - `backend/tests/test_postgres_smoke.py` `4c594604684eabb52cf5b0eface032b50ff5ab54`
  - `backend/tests/test_prepare_database.py` `902a83696a295c42516f7b8fe5639876d357b604`
- Original SEVEN operational HOA capabilities remain the Phase 4.7
  product goal. Preserve verified member accounting, annual budget,
  ARC direct APPROVED/DENIED with protected fees/notifications,
  reserve GL book, document delivery, case tasks and $79/month HOA
  entitlement. Do not invent statutory deadlines, legal service,
  member liability or bank transfer; isolate specific prerequisites
  to their own action and continue other operational work.
  Phase 4.8 PAUSED.

---

# AI_HANDOFF.md — 2026-09-29 AUTHENTICATED HOA BOARD PORTAL PROVISIONAL

**READ ENTIRE ROOT HANDOFF.** This is the most recent state; older
NEXT/PREPARED sections below are historical. Only repository
`yasirskhan/property-platform`, only branch
`chatgpt/checkpoint-005-safety`. Never modify main, create a branch,
force push, merge PR, edit frozen docs/ or advance Phase 4.8.

- Latest VERIFIED product source `1cc1d5596304f25bf1460f3d5e33d76564a6b4ce`.
  GitHub Actions 36588839813 SUCCESS ALL SIX jobs:
  **796 backend passed, 15 deselected, 19964 warnings**;
  authenticated browser **15 passed, 224 warnings**;
  frontend lint/TypeScript/build, platform-admin, security, staging PASS.
  Alembic **f6b8d0e2a4c7, 168 model tables**. Local tests NOT RUN.
  Root handoff-only commit `d52d37ed0b2b24068396e75e929dd078a602c53a`
  records this actual verified product.
- Latest NEXT provisional Phase 4.7 board-portal batch: isolated
  `GET /api/hoa/board/my-meetings` for active verified association
  board login, checking the existing paid HOA gates, active org,
  active association/property membership, verified matching contact
  and current authorized board seat. Supports a board member who
  has no broad PROPERTIES.ALL staff permission. The customer dashboard
  offers a board-meetings link only for an eligible user and a
  `/dashboard/hoa/board` view with live scoped meeting agenda,
  board-only exact-revision minutes preview, immutable approval
  through the already VERIFIED board approval API, confirmation,
  retry/error handling. Adds focused permission/revocation tests and
  synthetic authenticated E2E exercising actual board portal approval.
  Existing ARC, board minutes, member accounting, annual budget,
  reserve GL, private correspondence and governing docs unchanged.
  NO migration and no billing or external notice/bank effects.
- Source changes are PROVISIONAL until six green hosted CI jobs on
  the new product SHA; do not attribute earlier green CI to the
  new portal. If a CI job fails, inspect logs and correct it
  autonomously on the same feature branch; actual test counts and
  source SHA required for VERIFIED. After green CI update root
  handoff and proceed to next independent Phase 4.7 board vote/
  configured quorum or scoped operational violations batch.
- Seven original HOA operational capabilities remain in progress.
  No blanket platform legal certification; enforce concrete
  association permission, decision record, applicable procedure,
  correctly identified payer, central GL, delivery and audit.
  Do not issue statutory notices or real customer finance in
  synthetic CI. Preserve paid $79/month HOA add-on.
  Phase 4.8 remains PAUSED.

---

# AI_HANDOFF.md — 2026-09-29 HOA BOARD MINUTES VERIFIED / AUTHENTICATED BOARD PORTAL NEXT

**READ ENTIRE REPOSITORY-ROOT FILE.** This newest verified checkpoint supersedes
all older NEXT/PREPARED entries below, preserved as history.

- Only repository `yasirskhan/property-platform`; only working branch
  `chatgpt/checkpoint-005-safety`. Do not touch main, create branches,
  force-push, merge PR, edit frozen docs/, repeat completed work or
  advance Phase 4.8.
- Last VERIFIED product source `1cc1d5596304f25bf1460f3d5e33d76564a6b4ce`.
  Hosted GitHub Actions [36588839813](https://github.com/yasirskhan/property-platform/actions/runs/36588839813)
  SUCCESS all SIX jobs on this exact source: backend **796 passed,
  15 deselected, 19964 warnings in 264.76s**; authenticated browser
  **15 passed, 224 warnings in 64.66s**; frontend lint/TypeScript/
  production build, platform-admin, security, staging-config PASS.
  **TESTS NOT RUN locally.** Initial staging/source remained in this
  exact bounded commit and passed; no earlier CI attributed to this code.
- Alembic verified head **f6b8d0e2a4c7**, previously
  e5a7c9d1f3b6; **168 model tables** (was 167). Fresh/legacy/
  PostgreSQL schema and staging guards passed.
- Completed Phase 4.7 C board-minutes batch: authenticated authorized
  association-specific board member may approve exact active staff
  meeting minutes revision (SHA-256 of body and optimistic version).
  Immutable approval records active seat and decision maker, dated
  event and redacted audit. Staff minutes edits/archive and parent
  meeting edits/archive cannot silently change approved history.
  Private board-preview, read and approval routes reuse existing
  paid HOA/active verified login and live seat/contact/member gates.
  Dedicated synthetic browser passed. Approval represents ONE
  authorized member's action, not statutory service, certified quorum,
  formal full-board vote or GL transaction. Parent history preserved.
- Prior budget-actuals source `444f3b61bd0cd5e944b67139c3d1d09691ac8b59`
  VERIFIED all six jobs on CI 36587564351: 794 backend passed,
  14 deselected, 14 browser passed; no new migration.
  Existing verified ARC operative APPROVED/DENIED with protected fees,
  notifications and reversals, HOA assessment/receipt posting, member
  statements, annual budget/increases, reserve GL book, document
  delivery and $79/month HOA entitlement remain unchanged.
- **Exact NEXT independently actionable Phase 4.7 C board portal
  batch:** authenticated board-member dashboard for their own
  currently authorized association/property meetings, real read-only
  minutes preview and direct exact-revision approval through the
  existing verified board approval route. Support board members who
  are TENANT/other non-organization-admin roles without granting
  broad PROPERTIES.ALL access. Test paid HOA entitlement, revoked/
  foreign/inactive seat and member scope, zero financial mutation,
  login and browser navigation. A new uncommitted candidate blob
  exists at `backend/app/routers/hoa_board_portal.py` SHA
  `0b8ee95f3ad8051abe087e61ecbdb7efa2865a3c`;
  this is NOT committed/tested/verified. Static source, UI,
  dashboard link and backend test candidate blobs are being
  assembled separately. No tree or commit exists for next batch.
  Use one provisional product commit only on designated branch,
  six GitHub CI jobs; autonomously correct failures, record real
  counts and new source in handoff, then continue next independent
  HOA capability such as authenticated votes/quorum or authorized
  violation notice operations.
- SEVEN operational HOA areas remain the user's completion scope:
  recurring/special dues, notices/cure/fines/hearings, board portal,
  ARC, reserve accounting, governing docs, annual budget/increases.
  Do not claim the whole phase complete on partial workflows.
  Board/association authority is recorded, not separately approved
  by platform; enforce exact applicable steps, identified payer,
  central GL, audit/reversal and delivery status. Never infer member
  liability from a contact or send real messages/post obligations in
  synthetic CI. Individual absent prerequisites block only that
  operation, not independent development. Phase 4.8 PAUSED.

---

# AI_HANDOFF.md — 2026-09-29 VERIFIED BUDGET ACTUALS / BOARD MINUTES PROVISIONAL

**READ THE ENTIRE ROOT HANDOFF.** This entry supersedes older NEXT/
PREPARED labels below. Only repository `yasirskhan/property-platform`
and branch `chatgpt/checkpoint-005-safety`. Never touch main, create
another branch, force-push, merge, edit frozen docs/ or start Phase 4.8.

- Latest VERIFIED product source `444f3b61bd0cd5e944b67139c3d1d09691ac8b59`.
  GitHub Actions [36587564351](https://github.com/yasirskhan/property-platform/actions/runs/36587564351)
  SUCCESS, all six jobs, on that exact SHA. Backend **794 passed,
  14 deselected, 19846 warnings in 250.10s**; authenticated browser
  **14 passed, 206 warnings in 60.23s**; frontend lint/TypeScript/build,
  platform-admin, security, staging-config PASS. Local tests: TESTS
  NOT RUN. The prior `ee105536` CI 36580024025 failed one outdated
  manager-authorization test; `b5b4468d` CI 36581054317 passed
  backend but failed two browser cases (login navigation timeout
  and incorrect currency-format assertion). Corrective
  `444f3b61` passed six jobs. Do not claim earlier red CI passed.
- Verified Alembic head **e5a7c9d1f3b6**, **167 SQLAlchemy model
  tables**; no migration was added by the budget-actuals batch.
  Approved HOA annual budget versus actual posted property-tagged
  existing central GL is now verified, with read-only budget/actual
  comparison, source limitations and reversal handling. It is not
  independently allocated HOA-only financial reporting. Earlier
  approved-budget recurring assessment increase source
  `430db13f` and all prior verified HOA functions remain intact.
- Exact current NEXT Phase 4.7 C board-portal batch: **authorized
  board-member approval of an exact existing staff minutes revision.**
  Provisional implementation adds one immutable association-scoped
  approval row linked to existing minutes and authorized board seat,
  SHA-256 content hash, revision and stale-edit protection, locks
  subsequent staff minutes updates/archive and parent meeting
  update/archive, redacted audit, restricted read/approval routes,
  a customer UI, focused backend security/regression and dedicated
  synthetic browser test. It represents this one authenticated
  member's adoption, NOT independently certified quorum, statutory
  notice or full-board vote; zero accounting effects.
- Provisional migration **f6b8d0e2a4c7** follows verified
  e5a7c9d1f3b6. Expected model count **168**, but verified count
  remains **167** until CI is green. Source changes are PROVISIONAL,
  not VERIFIED. The exact files are carried together in the next
  single provisional feature-branch commit and MUST pass all six
  GitHub Actions jobs. Correct failures autonomously. After green
  CI, record exact source SHA, run, positive test counts and actual
  migration/table count here, then continue an independently
  actionable original HOA operational batch, prioritizing
  authenticated board votes/configured quorum or authorized
  violation notices. Do not stop after green CI.
- Preserve direct operative ARC APPROVED/DENIED decisions, protected
  fees/notifications/reversals, member assessments and receipts,
  member statements, annual budgets/increases, reserve GL book,
  governing-document delivery, paid $79/month HOA add-on and
  entitlement. Seven original Phase 4.7 areas remain the goal.
  Do not introduce blanket platform legal certification, infer
  member debt from an unverified contact, bypass central GL, send
  real notices from synthetic CI, or advance Phase 4.8.

---

# AI_HANDOFF.md — 2026-09-29 HOA ANNUAL INCREASE VERIFIED / BOARD MINUTES NEXT

**READ THE ENTIRE FILE.** This newest verification supersedes the historical
PREPARED and NEXT labels below. Only `yasirskhan/property-platform`
branch `chatgpt/checkpoint-005-safety`. Never modify main,
frozen docs/, merge, force-push, create another branch or start Phase 4.8.

- Latest VERIFIED product SOURCE
  `430db13f81414e97c4bfe027313e6ad84283d9fc`.
  GitHub Actions [36578090888](https://github.com/yasirskhan/property-platform/actions/runs/36578090888)
  **SUCCESS all six jobs on that exact source**:
  backend **793 passed, 14 deselected, 19764 warnings in 212.41s**;
  authenticated browser **14 passed, 206 warnings in 51.69s**.
  Frontend lint, TypeScript, production build, platform-admin, security
  and staging passed. **TESTS NOT RUN locally.**
- Verified Alembic head **e5a7c9d1f3b6**, **167 model tables**
  (previous d4f6a8c0e2b5 / 166). PostgreSQL migrations,
  fresh/legacy and staging schema guards passed.
- The 16 provisional annual budget-linked increase files committed at
  `430db13f` are now TESTED/VERIFIED. New immutable provenance
  relates an already APPROVED association annual budget, an existing
  posted nonreversed recurring member charge and a newly drafted
  increased recurring assessment for the same currently verified
  responsible member. The amount must increase, the new effective
  date must be within the approved budget year, idempotency/locks
  prevent duplicate links. It atomically creates a new scoped
  HOAAssessmentProposal plus suggested payer reference, NOT a charge.
  The NEW board decision, explicit occurrence generation and actual
  accountant-controlled central GL issuance still take place through
  already verified, existing routes. In this source CI backend
  regression explicitly completed the new independent board
  APPROVED and POSTED $150 synthetic member receivable after the
  $125.50 previous charge. Existing private recipient history,
  ARC direct APPROVED/DENIED, receipt/reversal, governing documents,
  reserve GL book, paid $79/month HOA gates and earlier HOA features
  remained intact. Synthetic E2E sends no production messages or
  real-world charges.
- **Exact NEXT independently actionable original Phase 4.7 C Board portal
  batch:** authorized association board approval of existing staff
  meeting minutes, with immutable content hash/version, actual
  authenticated board-member decision, live association/property/
  meeting scope, no silent changes after approval, redacted audit,
  direct customer UI and dedicated browser test. Do not confuse
  one authorized member approving minutes with a certified quorum,
  formal full-board vote or statutory meeting notice. This is
  operationally meaningful board action, NOT completion of the
  seven-feature Phase 4.7 scope. Follow next with authenticated
  voting/quorum where technically appropriate.
- The original seven HOA capabilities remain operational goal.
  Individual action prerequisites (verified member, configured
  service procedure, payer/GL mapping and delivery settings) must
  be enforced, without blanket platform certification or manufactured
  broad blockers. No statutory notices/fines from staff drafts.
  Phase 4.7 IN PROGRESS; Phase 4.8 PAUSED. After each bounded batch,
  six green CI jobs and actual counts, refresh this root handoff
  and continue next independent batch.

---

# AI_HANDOFF.md — 2026-09-29 ANNUAL BUDGET INCREASE PROVISIONAL

**Authoritative most recent status. Read whole file; older NEXT/PREPARED
entries below are historical.** Repository `yasirskhan/property-platform`;
ONLY working branch `chatgpt/checkpoint-005-safety`. No main, new branch,
force-push, frozen docs/, PR merge, or Phase 4.8.

- Latest VERIFIED product source `cedb96d2c6c7301626330e78ef9f2546c50bca25`;
  CI **36574549498 SUCCESS all six jobs**, backend **791 passed,
  14 deselected**, browser **14 passed**. Migration
  `d4f6a8c0e2b5`, **166 tables**. No local tests.
- The immediately preceding root handoff commit
  `5d689fd6da6fc0bd87c369e5c2d002bb800dd05b`
  is documentation-only.
- Current proposed NEXT batch (NOT VERIFIED until six CI jobs pass):
  LINK approved association annual budget to a *new* recurring
  member assessment increase proposal, requiring an actual prior
  posted recurring HOA member receivable and independently verified
  same-scope responsible member. Idempotent source-charge/budget
  association, immutable previous and proposed amount snapshots,
  separate board decision and GL issuance, staff accountant
  permission and live HOA subscription/release gates, cross-property
  and cross-organization checks, audit redaction. The new proposed
  amount MUST exceed the previously issued amount; first assessment
  date must be in adopted budget year. The new proposal is atomically
  created with inherited currently live payer reference, but NO new
  board approval, notice or member charge/GL transaction results
  from creation. Existing separate authorized board decision,
  recurrence generation, GL posting, receipt, reversal remain
  mandatory and reusable.
- Proposed migration `e5a7c9d1f3b6` follows
  `d4f6a8c0e2b5`; EXPECTED **167 tables** only after verified.
  New table `hoa_annual_assessment_increases`. Proposed source
  includes route, component, backend regressions and annual budget
  browser extension. PROVISIONAL implementation commit and
  hosted GitHub Actions test result must be verified independently;
  do NOT attribute earlier green CI to this batch.
- After six green jobs, update handoff with real source SHA, run ID,
  backend/browser counts and schema. Continue the next unblocked
  Phase 4.7 operational batch, prioritizing authorized notice
  delivery for a specific approved member assessment or violation
  with exact configured procedure and recipient. No platform-wide
  legal approval gate; missing per-action jurisdictional fields,
  decision maker, verified payer or delivery channel block only
  that specific action.
- Preserve all previously verified HOA assessment posting, receipts,
  statements, annual budgets, direct ARC APPROVED/DENIED, reserve
  GL book transfers/reversal, private documents and $79/month
  add-on entitlements. The SEVEN original HOA capabilities must
  become operational and tested; Phase 4.7 IN PROGRESS.

---

# AI_HANDOFF.md — 2026-09-29 HOA ANNUAL BUDGET VERIFIED

**Latest verified product source** `cedb96d2c6c7301626330e78ef9f2546c50bca25`.
GitHub Actions **36574549498 SUCCESS ALL SIX JOBS** on that exact SHA.
Backend **791 passed, 14 deselected, 19603 warnings in 266.41s**;
authenticated browser **14 passed, 206 warnings in 53.92s**.
Frontend lint/typecheck/build, platform-admin, security and staging passed.
**TESTS NOT RUN locally**. Verified Alembic head `d4f6a8c0e2b5`,
expected **166 model tables**. Earlier annual-budget provisional
handoff below is HISTORICAL, not a pending task.

**Verified annual budget behavior:** scoped association/year budget
income/expense GL line snapshots, reserve allocation planning, draft
revision and authorized board APPROVED/DENIED decisions (including
authorized offline recording with private record). No separate property
budget relabeling, no charge or GL post simply for budget approval.
The previous HOA member statements and receipt posting are preserved.

**Exact NEXT Phase 4.7 operational batch:** annual-budget-linked
assessment increase workflow. Independently inspect existing approved
annual budget, assessment board decision, verified payer, central GL
and delivery contracts. Record association board authority for each
increase; never imply budget approval itself authorizes a member
charge. Extend operational issuance/notice only with scoped,
idempotent, tested posting and recipient protection. If a particular
notice/procedure requirement lacks configuration, leave that action
pending, continue other independent implementation.
Maintain the seven original operational HOA areas. No Phase 4.8,
new branch, main or frozen docs edits. After next source commit,
six CI jobs must pass before marking verified.

---

# AI_HANDOFF.md — 2026-09-29 ANNUAL HOA BUDGET PROVISIONAL

**READ THE ENTIRE FILE.** This newest entry supersedes historical
NEXT/PREPARED sections preserved further down. ONLY repository
`yasirskhan/property-platform` and existing branch
`chatgpt/checkpoint-005-safety`. Do NOT modify main or frozen docs/,
create another branch, force push, merge a PR, or advance Phase 4.8.

- Last VERIFIED product commit:
  `861191ab1a29b8b88371a5b4415b486a6ad9534e`.
  GitHub Actions [36563959170](https://github.com/yasirskhan/property-platform/actions/runs/36563959170)
  **SUCCESS all six jobs on this exact source**. Backend **789 passed,
  13 deselected, 19448 warnings in 260.28s**; authenticated browser
  **13 passed, 179 warnings in 59.80s**. Frontend lint/typecheck/build,
  platform-admin, security and staging PASS. **TESTS NOT RUN locally**.
  Initial member statement source `540d5e08` CI 36563300346 failed two
  direct-call tests because an optional FastAPI Query parameter had no
  plain Python default; `861191ab` corrected it, all six jobs green.
- Verified Alembic head `c3e5a7b9d1f4` with **165 model tables**.
  Existing HOA member receipts, board-approved member receivables and
  association-wide read-only posted member statements are VERIFIED.
  No new migration was needed for member statements.
- **IN-FLIGHT NEXT BATCH: HOA ANNUAL OPERATING BUDGET ADOPTION**.
  This is a NEW provisional backend/frontend/migration/tests batch
  pending its own GitHub Actions. Association-specific annual income/
  expense GL budget lines are entered by scoped staff, including a
  bounded planned reserve allocation. Existing authorized board login
  directly records immutable APPROVED/DENIED decision (also designated
  offline recorder/private meeting record), with revision history and
  soft archival on association unlink. The general property budget is
  not silently relabeled as HOA. Approval is operative as a board's
  budget decision, not a member assessment, restricted reserve
  declaration, automatic GL posting, or bank transfer. Separate member
  assessment approval, identified payer, GL posting and notices remain
  their own protected actions. A new migration
  `d4f6a8c0e2b5` follows verified `c3e5a7b9d1f4` and is EXPECTED to
  create **166 model tables**. Until six CI jobs pass, VERIFIED counts
  remain 165, not 166. Tests not yet run for this provisional batch.
- **Exact next action:** complete review of the prepared annual-budget
  implementation, commit provisionally through connected GitHub on
  this branch, run GitHub Actions on that commit, fix CI failures,
  mark VERIFIED only after six green jobs and report ACTUAL backend/
  browser test counts. Update this handoff and immediately continue
  the next actionable Phase 4.7 batch: annual budget-linked assessment
  increases with individually authorized member notice and posting,
  or another independently actionable remaining HOA requirement.
- The seven user-required HOA areas remain: real recurring/special
  dues, violations/notice/fines/hearings, board portal, operative ARC,
  reserve funds/GL, governing documents/delivery and annual budget/
  assessment increases. Preserve direct board APPROVED/DENIED ARC
  decisions, $79/month HOA add-on, customer feature/permission gates
  and shared central GL/idempotency/reversal protections. Do not invent
  member liability or jurisdiction-specific legal process; only block
  the particular operation missing a concrete prerequisite. No live
  financial obligations or real notices may be created by CI fixtures.
  Phase 4.7 IN PROGRESS; Phase 4.8 PAUSED.

---

# AI_HANDOFF.md — 2026-09-29 MEMBER PAYMENTS VERIFIED / MEMBER STATEMENTS PROVISIONAL

**Read the entire file; newest state supersedes the older NEXT labels below.**
Repository `yasirskhan/property-platform`; ONLY branch
`chatgpt/checkpoint-005-safety`. No main, new branch, force push,
frozen docs/ edits, PR merge or Phase 4.8 implementation.

- Last independently VERIFIED product source:
  `84371e9fb104b7fdb2aa95874a2d9552883abf7d`.
  GitHub Actions **36528948778 SUCCESS all SIX jobs** on this exact SHA:
  backend **787 passed, 13 deselected, 19291 warnings in 207.20s**;
  authenticated browser **13 passed, 179 warnings in 57.76s**.
  Frontend lint/typecheck/build, platform-admin, security,
  staging-config PASS. **TESTS NOT RUN locally**.
- Verified Alembic head `c3e5a7b9d1f4`; **165 model tables**
  after prior `b2d4f6a8c0e3` / 164. The earlier 16
  uncommitted member-payment blobs ARE now committed and verified
  in `84371e9f`, not pending. Real offline-recorded funds receive
  one existing Receipt/ReceiptLine and balanced central GL cash debit/
  receivable credit, with verified member, scoped permissions,
  partial/full allocations, idempotency and reversal. This is not
  bank collection, card capture or processor reconciliation.
  Existing generic receipt reverse/NSF paths cannot bypass
  HOA allocation rollback.
- NEXT independent Phase 4.7 A operational batch is **association-wide
  posted member account statements** across proposals. The new
  read-only accountant-scoped endpoint/component/test extension is
  PROVISIONAL until its own GitHub Actions runs all SIX jobs.
  It reflects actual posted receivables, receipts and reversals,
  explicitly rejects inconsistent amount_paid versus live allocations,
  and never books charges or sends messages. No migration is planned.
  Once all six jobs pass, update the verified-source SHA and actual
  counts here and immediately move to the next unblocked original
  HOA capability (operational violations, board portal or annual budget).
- User requires SEVEN functional HOA areas: recurring/special dues,
  violation notice/cure/fines/hearings, board portal, operative ARC,
  reserve funds/GL, governing document delivery and annual budget/
  assessment increases. Preserve verified operative ARC APPROVED/DENIED
  without restoring blanket legal-effect gate. The board is the
  authority; honor actual procedural requirements and correct member/
  account identification. Block only an action whose prerequisites
  are actually absent; continue independent development. Never
  issue real-world notices or payments from synthetic CI.
- Maintain existing paid $79/month HOA catalog, organization entitlement
  and permissions. Phase 4.8 remains PAUSED.

---

# AI_HANDOFF.md — 2026-09-29 CURRENT SESSION: MEMBER PAYMENT PROVISIONAL

**READ ENTIRE FILE.** This entry supersedes historical NEXT/PREPARED entries
below; earlier product verification remains correct and unchanged.

- Repository `yasirskhan/property-platform`; ONLY working branch
  `chatgpt/checkpoint-005-safety`. Never modify main/frozen docs,
  force push, merge or advance Phase 4.8.
- Last VERIFIED product SOURCE `951d144aa06283f14b8f4f65b8e951d5706a7ee4`.
  GitHub Actions **36527708582 SUCCESS ALL SIX JOBS** on that SHA:
  backend **785 passed, 13 deselected, 19090 warnings in 140.43s**,
  dedicated/authenticated browser **13 passed, 177 warnings in 51.99s**;
  frontend lint/TypeScript/build, platform admin, security, staging PASS.
  **TESTS NOT RUN locally.** Alembic **b2d4f6a8c0e3, 164 model tables**.
  Board-authorized reserve GL BOOK transfer/reversal is VERIFIED.
  No bank API transfer or certified statutory reserve restriction.
- Previously VERIFIED approved member assessments `cee88200`,
  CI 36527051274, 783 backend/12 browser, migration
  `a1c3e5f7b9d2`, 163 tables. Member payment allocation is the
  next real operational Phase 4.7 A dependency.
- Latest working batch is newly **PREPARED ONLY**, NOT COMMITTED,
  NOT TESTED, NOT VERIFIED: actual offline-recorded HOA member receipts
  linked to existing central Receipt + ReceiptLine and two-line balanced
  GL cash debit/member-receivable credit. Explicit verified member,
  scoped accountant permissions, live HOA entitlement, idempotency,
  partial/full allocations, overpayment and locked-period denial,
  receipt-specific reversals and immutable audit. No payment processor
  capture or bank transfer; staff must record only funds actually
  received. Generic receipt NSF/reverse route is blocked for HOA type
  so it cannot bypass the member allocation rollback. One migration
  `c3e5a7b9d1f4` follows verified b2 and is EXPECTED to make 165
  tables, but live VERIFIED head/table count stays b2/164 until
  its own six jobs pass.

**Prepared source blob pointers (uncommitted Git objects):**
- `backend/app/models/hoa_member_assessment_payment.py`: `d3aa7e08c116718631e69a840eb06c849fc01daf`
- `backend/alembic/versions/c3e5a7b9d1f4_hoa_member_assessment_payments.py`: `e0b08998920bc9a939e77a4bca467d5e8371cc56`
- `backend/app/schemas/hoa_member_payment.py`: `374d77b27f8ad7aba2ba949cab02b906057c31c9`
- `backend/app/routers/hoa_member_payments.py`: `270958677a7a996c2e10e292e244279b195a13dc`
- `backend/app/main.py`: `b7e440d0ecb4f0e5890511d4a38caeae51fe8ca6`
- `backend/init_db.py`: `4529297f0a1d02d52ebfaf94f33083627c2b43db`
- `backend/app/services/entity_notes.py`: `afc3b0f0bd2f9288a878d11f322512b0acb2e1e5`
- `backend/app/services/receipt_posting.py`: `0549a2a1c2f96b8d067b77c2d56333bd96099075`
- `backend/app/schemas/hoa_member_assessment.py`: `6c96a8125f77ff18e9bad25acc026d78576555a1`
- `frontend/src/components/property/HoaMemberPaymentsPanel.tsx`: `4c8bcde2c5b6e0eb457adc97648f3bd4900d44a6`
- `frontend/src/components/property/HoaMemberAssessmentsPanel.tsx`: `2e456d2b69057b5e724c64a9d18f7762459bda0e`
- `backend/tests/test_hoa_member_assessments.py`: `7bb76d41924ebc5cae5a8ca214a1d9c64bf939a5`
- `backend/tests/e2e/test_hoa_evidence_e2e.py`: `5a66acd34c019e8bed152a117a3e8041d2d263c7`
- `backend/tests/test_migrations.py`: `f20bb0a4d1fc6669b9b4bc4ce4147269b65e2cd3`
- `backend/tests/test_postgres_smoke.py`: `18eace749616af6e003b768c1e7f786bc3f331f0`
- `backend/tests/test_prepare_database.py`: `f73b912ebbfda2d7164565955d366a8cdbcdce54`

**Exact NEXT action:** Check branch HEAD and actual files, assemble these
16 product blobs with this root handoff in ONE provisional commit on
the designated branch. Run GitHub Actions against committed code and
fix CI failures autonomously. After six green jobs, record SHA, actual
backend/browser counts, migration head/table count, completed behavior
and remaining real HOA dependencies in this root handoff. Then start
next independent Phase 4.7 operational batch. Do not assume earlier CI
tested these uncommitted blobs. Preserve ARC direct board decisions
and the seven original operational HOA requirements.

---
# AI_HANDOFF.md — 2026-09-29 LATEST VERIFIED CHECKPOINT

**READ ENTIRE FILE FIRST.** This entry supersedes historical NEXT and
PREPARED sections further below. One feature-branch batch at a time.
- Repository `yasirskhan/property-platform`. ONLY branch
  `chatgpt/checkpoint-005-safety`. No main, new branch, force push,
  merge, frozen `docs/` changes or Phase 4.8.
- Last VERIFIED PRODUCT source: `951d144aa06283f14b8f4f65b8e951d5706a7ee4`.
  GitHub Actions [36527708582](https://github.com/yasirskhan/property-platform/actions/runs/36527708582)
  **SUCCESS ALL SIX JOBS on this exact SHA**. Backend **785 passed,
  13 deselected, 19090 warnings in 140.43s**; authenticated browser
  E2E **13 passed, 177 warnings in 51.99s**. Frontend lint,
  TypeScript, build, platform-admin, security, staging SUCCESS.
  TESTS NOT RUN locally.
- Alembic verified head **b2d4f6a8c0e3** after
  `a1c3e5f7b9d2`; **164 expected model tables** (was 163).
  Fresh/legacy/PostgreSQL migrations and staging passed.
- Verified bounded operational reserve BOOK posting: authorized
  authenticated association board approval/denial for existing
  scoped movement draft, optionally a designated offline board
  recorder with private meeting record; separate permitted accountant
  uses central balanced property-tagged GL TRANSFER on active,
  distinct same-org cash-like GL accounts and mapped reserve.
  Idempotent/locked issue, terminal decision, immutable audit and
  protected GL REVERSAL. Old draft cannot be cancelled once board
  decides. Customer reserve UI and dedicated synthetic browser cover
  approval, post and reverse. NO bank API transfer, actual bank
  disbursement, legal reserve restrictions certification or statutory
  ownership determination. Never confuse booked GL movement with
  physical bank movement.
- The 15 Git blobs and root handoff committed in `951d144aa06283f14b8f4f65b8e951d5706a7ee4`
  are now TESTED AND VERIFIED. Historical label "PREPARED" below
  describes their status BEFORE this verified commit; not a pending batch.
- Earlier verified member-assessment actual charge/GL/reversal:
  `cee88200f3780f3e1c42a300baf5afb44b4b229f`,
  CI 36527051274, 783 backend/12 browser, schema 163.
  Earlier verified governing-document e-mail copy delivery
  `bb9e9094`, internal violation case tasks `ef901b38`,
  direct ARC APPROVED/DENIED, paid HOA gate/catalog.
- Phase 4.7 operational HOA seven areas IN PROGRESS. User requires
  no blanket extra platform legal certification, and no guessing
  legal procedure or member liability. Only exact missing inputs block
  an individual operation. Phase 4.8 PAUSED.

**Exact next independent batch:** Operational HOA member-assessment
payment allocation and reversal, using the already VERIFIED scoped
`HOAMemberAssessmentCharge` with explicit verified member, existing
central GL and existing cash/receipt architecture. Verify actual
posting/receipt contract before implementation; ensure cash debit and
member RECEIVABLE credit, atomic account/payments state, posted-date
locks, duplicate idempotency, overpayment guard, paid-charge reversal
protection, correct audit, cross-org/property permissions and synthetic
browser. Do NOT treat a generic tenant receipt/Charge as HOA payment
or create a parallel general ledger. If a particular external bank or
processor collection integration is unavailable, explicitly separate
an offline manually recorded receipt from automated bank capture,
and continue independently authorized work. One scoped tested batch,
six green CI jobs, update handoff, continue the next HOA batch.

---
# AI_HANDOFF.md — 2026-09-29 CURRENT VERIFIED CHECKPOINT

**READ THIS ENTIRE FILE.** The entry below is the newest status. Older
"NEXT" entries retained later in the file are historical and superseded.

- ONLY repository `yasirskhan/property-platform`, ONLY working branch
  `chatgpt/checkpoint-005-safety`. No `main`, new branch, force-push,
  merge, frozen `docs/`, or Phase 4.8 work.
- VERIFIED PRODUCT SOURCE `cee88200f3780f3e1c42a300baf5afb44b4b229f`.
  GitHub Actions run **36527051274 SUCCESS ALL SIX JOBS** on that exact SHA:
  **783 backend passed, 12 deselected, 18963 warnings in 158.62s**;
  **12 authenticated browser E2E passed, 155 warnings in 53.22s**.
  Frontend lint, TypeScript, production build, platform-admin, security,
  and staging-config PASS. **TESTS NOT RUN locally**.
- Verified Alembic head `a1c3e5f7b9d2`, **163 model tables**.
  Previous head `f0b2d4e6a8c1`, 161 tables. PostgreSQL/fresh/legacy
  schema and staging checks passed on corrected source.
- Latest VERIFIED batch: ACTUAL association board-approved recurring/special
  assessment member receivables (not tenant-only Charge) with same-scope
  verified member, immutable approved proposal amount, explicit due date,
  idempotent occurrence issuance, balanced central GL, locks, reversal and
  private audit; member-ledger UI and dedicated browser. This is an
  operating subset, NOT completed payment allocation or collection.
  Initial commit `7de7ae71` CI 36526517909 FAILED two backend regressions:
  missing HOAMemberAssessmentCharge list import and incorrect ability to
  void a posted planned occurrence; 781 passed, 2 failed, 12 deselected.
  Corrected product `cee88200` adds import and row-locked posted-occurrence
  void guard, then six green jobs. No false green attribution to initial run.
- Earlier VERIFIED: private HOA governing-document email attachment delivery
  `bb9e9094` / 36525127269; internal violation case follow-ups
  `ef901b38` / 36521596577; effective ARC APPROVED/DENIED, protected fees,
  notifications/reversals, $79/mo HOA add-on catalog and entitlement.
- **Phase 4.7 IN PROGRESS:** seven operational HOA areas must be integrated
  and tested. No platform blanket `legal_decision_effective=false` gate.
  Apply actual configured procedure, authorized decision-maker, verified
  payer, permissions, GL lock/idempotency/reversal and delivery safeguards.
  Do not invent law, auto-charge a tenant or treat SMTP transport acceptance
  as legal service. Phase 4.8 remains PAUSED.
- This session's NEXT scoped batch is operational HOA reserve GL BOOK
  movement approval, posting and reversal, extending the existing VERIFIED
  reserve draft and account mapping. A GL book transfer is NOT an external
  bank transfer and cannot certify restricted reserve ownership. The
  15 source blobs listed below were prepared for one provisional feature
  commit on the existing branch. They have NOT run applicable CI yet.
  Commit source provisionally using GitHub connector, correct any CI red,
  mark VERIFIED only after six jobs pass, then refresh THIS handoff and
  proceed with the next independent original HOA workflow.

## PREPARED, UNCOMMITTED, NOT VERIFIED: RESERVE BOOK POSTING

This is NOT the last VERIFIED source until hosted CI passes.
- Model: `backend/app/models/hoa_reserve_movement_decision.py` `563142533d947a0d94bbbdeee8e97096f61ca6ee`
- Migration: `backend/alembic/versions/b2d4f6a8c0e3_hoa_reserve_movement_decisions.py` `3fff8521bcbc270e8ca14ec89f80d758717c3a03`
- Schema: `backend/app/schemas/hoa_reserve_execution.py` `8ce70df20d97be02b4a6cac45341e573ad3559ed`
- Router: `backend/app/routers/hoa_reserve_execution.py` `da7a4bf4a4fdb08e1a79fb23e4aa05497e7ac182`
- Registration: `backend/app/main.py` `ae740dc5129fe5d1915f47dcc8564dc7d9e95475`
- Model bootstrap: `backend/init_db.py` `01822f6bfc9ab25d8e2bfc134e1eed6febae43cd`
- Private notes denylist: `backend/app/services/entity_notes.py` `3008ec4ec75fcc665846c67a2f812d7412e60960`
- Prevent cancellation after board decision: `backend/app/routers/hoa_reserve_movements.py` `a200a1172627bde5a81512955d25b20a2a1cb8d0`
- Focused backend tests: `backend/tests/test_hoa_reserve_accounts.py` `a2a75a87eaf1faddb93595102d41fa9d78a982ce`
- Customer component: `frontend/src/components/property/HoaReserveExecutionPanel.tsx` `06a95bfb991c74b5ed4eee8cc694e41882262426`
- Parent UI: `frontend/src/components/property/HoaReserveMovementPlans.tsx` `671a485f6685ac75f2efcb6fe39708f063a1eaa7`
- Migration test: `backend/tests/test_migrations.py` `4c278f8bc4769f6de906089f55296baa6182d519`
- PostgreSQL test: `backend/tests/test_postgres_smoke.py` `e6e9ba766b0e0644b550642c3060fd7febc348e5`
- Staging test: `backend/tests/test_prepare_database.py` `9ca1e976af81a41debf70616ce2e709debba031e`
- Dedicated browser extension: `backend/tests/e2e/test_hoa_evidence_e2e.py` `78219bf63557efca4dea920c2ed1c0bdb076b92e`

New migration proposes `b2d4f6a8c0e3` after verified
`a1c3e5f7b9d2` and would increase models 163 to 164, but
the live verified schema is still 163 until complete CI passes.
Board decisions require authenticated same-association/property
authorized seat, with optional authenticated offline maker and private
record. Separate accounting-authorized actions post balanced property
GL TRANSFER and immutable REVERSAL with source/reference and redacted
audit. Idempotency and row locks prevent duplicates; a board-decided
draft cannot be cancelled; cancelled/unapproved/stale mappings cannot
post. The UI and synthetic dedicated browser test explicitly distinguish
real BOOK ledger entries from an actual bank transfer. No bank API action,
legal reserve certification or real-world transaction is claimed from CI.

---

# AI_HANDOFF.md — Property Platform, 2026-09-29

**READ THIS WHOLE FILE FIRST.** Latest instructions and verification
appear at the top; earlier sections are preserved as history. The
most recent user instruction prioritizes seven fully operational
Phase 4.7 HOA capabilities before Phase 4.8. Follow real source/CI,
not historical "NEXT" entries. No real-world messages, financial
obligations or production changes are authorized merely by CI.

- Repository: `yasirskhan/property-platform`; ONLY branch
  `chatgpt/checkpoint-005-safety`. No main, new branch, force-push,
  PR merge or frozen `docs/` edits.
- Last VERIFIED product source:
  `bb9e909491106dc4a9a55568ed8e46948e33b163`.
  GitHub Actions **36525127269 SUCCESS all SIX jobs** on this SHA:
  backend **780 passed, 11 deselected, 18776 warnings in 254.46s**;
  authenticated browser E2E **11 passed, 133 warnings in 46.83s**;
  frontend lint/TypeScript/production build, platform-admin,
  security and staging-config SUCCESS. Tests ran in GitHub Actions;
  **TESTS NOT RUN locally**. Prior run 36524867266 was superseded/
  cancelled after a narrow test-fixture correction, not green.
- Alembic verified head **f0b2d4e6a8c1** after
  `e9a1c3f5b7d0`; **161 expected SQLAlchemy model tables**
  (previous 160). Migration/PostgreSQL/staging checks passed.
- Phase 4.7 HOA **IN PROGRESS**; completed internal case tasks,
  directly operative ARC decisions, HOA add-on $79/month catalog
  and live paid entitlement gates remain preserved. Phase 4.8
  stays PAUSED.
- Latest VERIFIED batch: authenticated, association/property-scoped
  **governing-document email-copy delivery**, version fingerprint,
  durable idempotent request/outbox, redacted audit and explicitly
  retryable SMTP transmission. SMTP_ACCEPTED only means accepted by
  transport, **not actual inbox receipt or legally served**.
  Console-mode E2E emits TEST_ONLY; no real email or real-world
  obligations. No GL/Charge/RentInvoice mutations.
- User has authorized iterative development using connected GitHub
  Git objects, provisional commits and hosted GitHub Actions on
  this existing branch. Commit source provisionally, correct CI
  errors, mark VERIFIED only on six green jobs, update handoff,
  then continue to the next independently actionable feature.
  No terminal checkout/npm prerequisite to GitHub editing.
- Product scope comprises SEVEN original HOA areas:
  A actual recurring/special dues with verified payer, central GL,
  payments/adjustments/reversals; B violations, notices, fines,
  cure/hearings and correction history; C board access,
  meetings/motions/votes/minutes and offline decisions;
  D operative ARC application/decision and follow-ups;
  E reserve fund transfers/studies/accounting/reversals;
  F governing docs versioning/access/delivery; G annual
  budgets, approval and assessment changes.
  Do not conflate drafts with finished operational features.
- Association decision-maker/organization configures its rules,
  board authorization and approvals. There is NO blanket
  platform-operated extra certification or reinstated ARC
  `legal_decision_effective=false` gate. Specific required
  authority, payer identity, procedure, GL, locking, idempotency,
  audit and delivery prerequisites MUST still be enforced.
  An individual blocked action does not block independent
  generic HOA work. Never invent law or a liable member.

**NEXT independent batch:** Continue Phase 4.7 with genuinely
operational member-ledger assessment issuance/reversal in a narrowly
bounded increment, reusing the verified direct board-seat
authorization and central posting contract, current contact/user,
assessment and planning models. Establish a specific scoped
association decision record, identifiable verified member,
immutable approved amount/due date and real balanced posting;
no tenant-only Charge inference or blanket platform legal gate.
Run complete applicable CI. Alternatively continue a distinct
original HOA workflow when a specific dependency blocks this
increment. Do not repeat completed delivery or tasks.

## CURRENT SESSION UPDATE — 2026-09-29 HOA DOCUMENT EMAIL DELIVERY VERIFIED

Implementation `e7a4e8ab2c940dfe924e45624c016caeff29187c`
was provisionally committed; test-only correction
`bb9e909491106dc4a9a55568ed8e46948e33b163` changed the distinct conflicting contact-link
fixture. Latest product CI 36525127269 passed ALL SIX jobs:
backend 780 passed/11 deselected, browser 11 passed,
frontend, platform-admin, security, staging green.
Previous 36524867266 was cancelled by the correction.
No local tests. Migration `f0b2d4e6a8c1` adds
`hoa_document_deliveries` (161 models total). Frozen
`docs/` and Phase 4.8 untouched.

The new private evidence email workflow accepts only currently
scoped association/property links and active, private property
attachments; ADMIN/OWNER with HOA+attachments release and
PEOPLE.CONTACTS permission may explicitly select a live linked
Contact with a matching verified active organization User.
The API is
`/api/hoa/associations/{id}/governing-evidence/eligible-recipients`,
`/deliveries`, `/{evidence_id}/deliveries`,
`/deliveries/{delivery_id}/retry`. Every retry rechecks
identity, association/property, private source and SHA256
fingerprint before loading attachment bytes (5 MB bound).
Unique request-key history is durable; SMTP claim/attempt
and terminal status are recorded with redacted audit.
An already-accepted request cannot re-send through replay.
The existing org/platform SMTP transport is reused; failed
messages are retryable. TEST_ONLY console never transmits
attachment bytes and SMTP_ACCEPTED never asserts inbox
delivery or statutory legal service. UI has explicit
confirmation, verified recipient selector and scoped history.
Three new focused backend tests and one expanded dedicated
HOA browser interaction cover real mocked MIME attachment,
duplicate request, retry/revoked identity/digest mismatch,
console transport and zero Charge/GL effects. No statutory
notice, fine, dues or other financial action implemented here.

**Next:** As above, actual HOA assessment member issuance/reversal
using current approved board and central GL structures, not
another generalized readiness screen. Inspect current source
for proper payer/member-identity and board decision contracts.
A missing individual association-specific rule or payer
should pend only that action and never block independent
source development.

---

## CURRENT SESSION UPDATE — 2026-09-29 HOA INTERNAL CASE TASKS VERIFIED

The 15 prepared Git objects from the historical 2026-09-28 handoff
were recovered, reviewed against the actual feature-branch contracts
and assembled in one provisional product commit,
`ef901b38b53c13c493fa8130ec8df31ee1303d14`. Its GitHub Actions run **36521596577** completed
SUCCESS across all six jobs. Backend **777 passed, 11 deselected**;
browser **11 passed** including the existing dedicated HOA
case browser test extended to create, start and complete a task.
Frontend lint, TypeScript, production build, platform-admin, security
and staging-config PASS. Local tests: **TESTS NOT RUN**.
New migration `e9a1c3f5b7d0_hoa_case_tasks.py` follows
`d8f0a2c4e6b9`; schema expectations are **160 tables**.

The private `hoa_case_tasks` model and scoped routes provide internal
task assignment, target dates, idempotent request keys, a bounded
case task list and eligible verified staff selector. ADMIN/OWNER can
create/cancel; the currently assigned MANAGER can start and complete,
subject to live property permissions, verified identity, current
assignment and active association/observation/case. The task state
machine uses optimistic `expected_version` checks and row locks,
with terminal DONE/CANCELLED states. Completion requires a private
result note. Case closeout rejects outstanding OPEN/IN_PROGRESS tasks;
closed-case tasks are immutable. Tests cover duplicate key replay,
changed-payload conflicts, stale versions, unauthorized roles,
foreign-property/organization and feature revocation, non-staff or
unverified assignees, required completion notes, audit redaction,
generic-notes denylist and zero Charge/RentInvoice/Lease/GL mutation.
No new statutory notice, fine, assessed liability, official inspection
or work order is created.

The corrected `HoaCaseTasksPanel.tsx` source blob
`3c2c2507b2965d1851dee754368aaf02f9cbdbc4`
is included. Do not restore superseded UI blob
`b5738aff22705e1f3526f424dd596b9e90ccb8f1`.
All previously verified violation observations, case stages/history,
candidate-recipient references, correspondence and private evidence
remain intact. ARC final decisions are unchanged.

All work here was via the connected GitHub integration, not a
local clone. The GitHub Actions run tested the COMMITTED source
`ef901b38b53c13c493fa8130ec8df31ee1303d14`, not its prior uncommitted blobs.
The next dependency and governing-input blocker are described above.
Do not repeat this completed batch.

---

## NEXT SESSION START HERE — exact 2026-09-28 stopping point

The last action in this chat is this **documentation-only handoff
update**. Immediately before this edit, branch HEAD was
`ce2aae77a02a07f8b9c9fc48245b7f1b7aea7186`, itself
documentation-only, with run `36519516166` IN PROGRESS
at the time checked. Re-query the actual branch HEAD and its
latest run when the new chat starts; do not assume that docs CI
passed or that `ce2aae77` is still HEAD.

**Verified product baseline:** `4546b6abb597609690cc99fae25457892643a4e1`;
GitHub Actions `36510915584` SUCCESS on all six jobs:
775 backend passed, 11 deselected; 11 browser E2E passed;
frontend lint/TypeScript/build, platform-admin, security,
staging-config green. Alembic `d8f0a2c4e6b9`,
159 model tables. Later handoff-only commits do **NOT**
change the verified product baseline. No tests for the
proposed case-follow-up task batch have run.

**In-flight exact task:** Phase 4.7 HOA violation staff
case follow-ups. Fifteen Git blobs are prepared (complete
paths and SHAs immediately below). They cover the SQLAlchemy
task model, migration `e9a1c3f5b7d0`, API schemas/router,
closed-case outstanding-task guard, task and parent UI,
focused regression tests, HOA browser extension, bootstraps
and notes denylist. A later static review fixed a manager
UI authorization mismatch: use the **updated** task UI blob
`3c2c2507b2965d1851dee754368aaf02f9cbdbc4`,
not its superseded predecessor. **Prepared Git blob
objects are not a branch commit.** Never report these
changes as implemented or verified in the deployed branch.

**Do exactly this next:** check connected GitHub, read
this entire root handoff, inspect current HEAD and CI,
retrieve the listed 15 blobs if they still exist, and
assemble their proposed source atop the exact current
branch. Obtain an executable checkout of that current
source, run applicable focused backend + migration tests,
frontend lint and TypeScript, and dedicated HOA browser
tests *before* a product-code commit. Review role/assignee
authorization, request-key idempotency, stale optimistic
versions, closed/resolved case transitions, zero finance
side effects, no information leaks, and missing/foreign
property tests. If checkout/test access is still blocked,
state **TESTS NOT RUN** and stop before product-code
mutation; do not stage an unverified commit, alter
`main`, or make a new branch to work around the rule.
After precommit tests pass, create one bounded product
commit on `chatgpt/checkpoint-005-safety`, verify all
six CI jobs at the resulting SHA and record real positive
test counts. Fix failures autonomously. Update this
handoff after verification.

**Security/product boundary:** ARC final board approval
or denial is already operational; its board decision is
recorded directly as APPROVED or DENIED without a blanket
`legal_decision_effective=false` gate. Keep its atomic
member-fee posting, work order/inspection follow-up,
offline decision record, notification retries, and
reversal protections intact. Violation case staff stages,
potential-recipient references, private evidence,
versioned internal correspondence, and proposed fines
are a different workflow. The new tasks are internal
staff assignments only; they do not serve statutory
notices, assess fines, establish a liable member, or
post GL entries. Never misrepresent planning fields as
legally operative activity. HOA Phase 4.7 remains
IN PROGRESS; Phase 4.8 stays paused. Frozen `docs/`
and existing verified product code must not be altered
without a scoped, tested need.

## CURRENT SESSION UPDATE — 2026-09-28 CASE FOLLOW-UP PREPARED, UNCOMMITTED

**PREPARED ONLY — NOT TESTED — NOT COMMITTED — NOT VERIFIED.**
The requested next Phase 4.7 violation batch was designed using
the live GitHub branch at product source `4546b6ab` and
handoff-only HEAD `9823b11`. Drafted **15 Git blob objects**
in the connected repository, but did not update any product
files or create a product commit. The prepared implementation
has a new scoped `hoa_case_tasks` task model, migration
`e9a1c3f5b7d0` after `d8f0a2c4e6b9`, schemas, router,
case closeout guard, frontend task panel, updated bootstraps,
two focused backend regression tests and an extension of the
existing dedicated HOA browser test. It provides optional
staff-assigned internal inspections/remediation/review
follow-ups, idempotent request keys, versioned status
transitions, immutable existing audit-log events, completion
notes, property-assigned manager access, and no assumed
legal notice, member payer, Charge or GL posting.

**Blocker (actual):** Product-code commits require applicable
tests to run first. There is no current local checkout in the
session runtime. GitHub direct clone fails DNS with
`Could not resolve host: github.com`; the available
Library ZIP checkpoint-005 dates to **September 23** and
has no later HOA models. Actions cannot test uncommitted
changes on the existing branch. Therefore
**APPLICABLE TESTS NOT RUN**, **NO PRODUCT COMMIT**,
and **NO CI RUN** for this prepared batch. Do not
mark it VERIFIED or update Alembic head/model counts
in the live verified header. Do not put this change
on main or a new branch to bypass the user's test rule.

**Prepared Git blob pointers (not source commits):**
- Model `backend/app/models/hoa_case_task.py`: `123513d03e699a0c99da8cf4c255d220b63747f6`
- Migration `backend/alembic/versions/e9a1c3f5b7d0_hoa_case_tasks.py`: `9af675e0b72bcf6fb6bca85f243b5e5fd8028bda`
- Schema `backend/app/schemas/hoa_case_task.py`: `e9e4c99d69dedd9629fb5c0cdc48c9c14f2b7ccf`
- Router `backend/app/routers/hoa_case_tasks.py`: `f10f960c1e94c0c1acfc28b005db3a586ae66310`
- Case closeout guard `backend/app/routers/hoa_violation_cases.py`: `7a1cacddd0df375d38860d1c4e9371c9a7159cd9`
- UI component `frontend/src/components/property/HoaCaseTasksPanel.tsx`: `3c2c2507b2965d1851dee754368aaf02f9cbdbc4` (updated; prior blob `b5738aff22705e1f3526f424dd596b9e90ccb8f1`)
- UI parent `frontend/src/components/property/HoaCaseWorkflowPanel.tsx`: `3fc001e3c077b51526d1c9030bafd3e815c7ef11`
- Backend tests `backend/tests/test_hoa_procedure_cases.py`: `cf6f8daf37c1e47a6c0f240407e207ac453ea1f7`
- Browser tests `backend/tests/e2e/test_hoa_evidence_e2e.py`: `8e82f724c3d994a1c06b50c6de69e294e35aaeb1`
- Router registration `backend/app/main.py`: `883d2aa7fee20ac38800384d4108b63115ab7e66`
- Model registration `backend/init_db.py`: `30a2585a17f5f4844b7fb0508db7680de29fa0c9`
- Entity-notes denylist `backend/app/services/entity_notes.py`: `cfc54a30188d079be0eb5744370af4eefa2a8d1a`
- Migration expectation `backend/tests/test_migrations.py`: `9c6bcc42b0f0b6c06040be30c1047ec93e84b70b`
- PostgreSQL expectation `backend/tests/test_postgres_smoke.py`: `337bd7a5b2cc06df7ff3d6f55c40d52ac70e4c44`
- Staging expectation `backend/tests/test_prepare_database.py`: `d3176ffa5aad50fdd695007caf615ce3035b08ee`

**Static review follow-up (2026-09-28):** Reviewed all 15 staged blobs against current branch contracts and confirmed the prepared code remains uncommitted. Found and corrected a real interface authorization mismatch in a newly staged `HoaCaseTasksPanel.tsx` blob: ADMIN/OWNER may create and cancel; a logged-in assigned MANAGER now also sees start/complete actions matching the backend authorization, while non-assigned managers cannot transition and managers never see cancel controls. New staged blob SHA `3c2c2507b2965d1851dee754368aaf02f9cbdbc4`; previous SHA above was superseded. This is **source review only**, not a frontend lint/typecheck/browser test. Confirmed the Library's latest full repository ZIP is September 23 and contains none of the Phase 4.7 HOA additions; the connected GitHub tools have no remote uncommitted-code test execution facility. Neither the passing Actions run 36515302369 nor earlier CI tested the staged task batch.

**NEXT:** obtain a testable current HEAD checkout. Independently
review and run the applicable focused backend, migration,
frontend lint/typecheck and HOA browser tests against the
assembled proposed source before any product-code commit;
repair any failures before committing. A stale September 23
ZIP and blob existence are NOT a tested current checkout.
Keep ARC decisions direct and final without a blanket
legal-effect gate, keep Phase 4.8 paused. Unreferenced Git
blob objects may eventually expire, so treat this list as
temporary staging rather than a committed change.

## CURRENT SESSION UPDATE — 2026-09-28 HOA PRIVATE VIOLATION EVIDENCE VERIFIED

**Verified product source** `4546b6abb597609690cc99fae25457892643a4e1`.
Initial implementation commit `dd228cbcf2afbacc12f64e29378d71f35cc57f0e`,
CI `36510450263`: frontend lint FAILED on unescaped
apostrophe in new UI; backend **775 passed, 11 deselected**,
security and platform-admin passed, dependent E2E/staging
skipped. Corrective lint-only commit `4546b6ab`
succeeded in full **CI 36510915584 six/six jobs**:
backend **775 passed, 11 deselected, 18533 warnings
in 241.93s**; browser E2E **11 passed, 129 warnings in
28.64s**; frontend lint/TypeScript/build, security,
platform-admin and staging-config all SUCCESS.
Tests ran on hosted CI; **TESTS NOT RUN locally**.
Alembic head `d8f0a2c4e6b9`, **159 model tables**
(previous `c7e9f1a3b5d8` / 158). Fresh/legacy DB
bootstrap, PostgreSQL and staging schema pass. Existing
frozen `docs/` and parity files unchanged.

New `hoa_violation_evidence` indexes private existing
universal property attachments (photo PDF/DOC/DOCX/
JPG/JPEG/PNG/WEBP; no duplicate file copies) under a
live same-org/association/property active observation
and case. GET/POST/DELETE
`/api/hoa/associations/{association_id}/staff-cases/
{case_id}/evidence` uses live paid HOA/compliance
entitlement/release and document attachment gate.
ADMIN/OWNER create/archive; assigned MANAGER read
only; tenant, foreign org or unassigned property
fail closed. Links to already-shared, foreign, inactive
or wrong-property files are rejected. A case + attachment
pair has a DB unique constraint, so repeats reject 409
and archived links never silently resurrect. Closed
staff cases retain readable private history but cannot
alter evidence links. Source file archive hides links
without mutating prior audit. Each link/unlink writes
a redacted append-only audit; private file names never
enter the audit payload. General entity notes reject
the new restricted table.

**Cross-route security:** universal attachments'
download/list/share/archive gates additionally enforce
the active HOA association/property restriction for
linked case files. PATCH cannot change linked evidence
to `share_with_tenants` or `share_with_owners` true,
preventing bypass of a private HOA case through
ordinary property attachment sharing. The new case UI
lists private property photo/document candidates,
allows explicit category selection and scoped link,
shows existing links and guarded download, and
archives a link without deleting the source file.
Dedicated HOA browser links a synthetic private
case photo in disposable E2E and verifies no finance
mutation. Focused tests cover private versus shared/
foreign property/foreign org source, active manager
read, admin/owner write, duplicate and archive,
closed-case restrictions, feature revocation,
sharing denial, generic-notes denylist, audit and
zero Charge/RentInvoice/GL changes.

**No statutory violation notice, hearing adjudication,
fine assessment, debtor status or GL posting is
certified by case evidence.** Phase 4.7 remains
IN PROGRESS. Latest approved operative ARC workflow
remains directly effective on board decision without
any separate software legal-effect gate. Phase 4.8
continues PAUSED. This root handoff update is
documentation-only, not a new verified product source.

## CURRENT SESSION UPDATE — 2026-09-28 HOA PRIVATE CORRESPONDENCE VERIFIED

**Verified product source** `0895ea891abba98704bfa777dd0d3f4c75e818e9`.
Hosted GitHub Actions **36509060666 SUCCESS all SIX jobs on
the second attempt**. Backend **773 passed, 11 deselected,
18450 warnings in 227.29s**; authenticated browser E2E
**11 passed, 128 warnings in 43.93s**; frontend lint,
TypeScript and build, platform-admin, security, staging-config
SUCCESS. The first CI attempt had one unrelated intermittently
unsuccessful browser-login redirect in preexisting evidence
upload test (10 E2E passed, one failed) while five other jobs
succeeded; the same failed job was rerun and all six jobs
concluded SUCCESS, without modifying product code. A prior
handoff-only CI 36508308998 also had a different transient
login redirect in preexisting dues test; it is NOT a verified
new product source. **TESTS NOT RUN locally**. Alembic
head `c7e9f1a3b5d8`; **158 model tables**; prior
`f4b6d8a0c2e9` / 157. Fresh/legacy SQLite bootstrap,
PostgreSQL smoke, staging bootstrap passed. No frozen `docs/`
or unrelated parity changes.

New `hoa_violation_correspondence_drafts` table is
append-only, one immutable case-scoped revision at a time
(max 50), with unique (case_id,revision), subject/body
snapshots, policy id/revision, linked potential-recipient
reference ID plus matching verified member login, case stage,
tentative dates and preparer/time. The GET/POST
`/api/hoa/associations/{association_id}/staff-cases/
{case_id}/correspondence` API strictly reuses existing
paid HOA+compliance, active organization/association/
property/observation/case, PROPERTIES.ALL +
PEOPLE.CONTACTS and ADMIN/OWNER writes, assigned MANAGER
read-only. POST only in current correspondence stages
NOTICE_DRAFT, CURE_TRACKING, HEARING_PLANNED and
FINE_PROPOSED with nonempty current staff policy text,
a prepared staff case draft date, and a revalidated
live active potential recipient whose contact email
still matches the same-org verified User. No statute is
inferred from staff-configured policy text.

GET returns all old immutable private staff correspondence
versions with booleans naming CURRENT recipient reference,
CURRENT policy revision and CURRENT case stage. It catches
stale/missing authorization references without treating them
as current service identity; it never silently rewrites
historical text or invents an effective notice. Duplicate
exact same scope+snapshot+body+subject POST rejects 409;
revisions are assigned under a row lock and DB uniqueness
so concurrent duplicates cannot silently multiply. An
explicit changed policy can produce a new version.
Redacted append-only audit stores IDs and revision
without confidential body. Generic notes reject the
new table. Payload rejects unknown `send_notice` fields.
All output explicitly marks STAFF_DRAFT_NOT_SENT,
legally_served FALSE and fine_assessed FALSE.
No email, statutory notice, cure service, tenant
Charge, RentInvoice or GLTransaction is issued.
Customer case UI can open private correspondence,
display revisions/staleness, choose existing staff
policy example text and record a new internal draft.
Dedicated browser creates one private draft and
checks financial counters. Two new focused backend
tests validate missing/foreign/archived recipient,
scope, manager/tenant/foreign write denial, permission
revocation, missing staff policy, terminal case,
duplicate, changed policy revision, stage staleness,
audit isolation, forbidden generic notes, and zero
financial mutation.

**Next work:** Continue *violation* functionality, not
repeat these verified staff preparatory features.
Member-notice delivery and assessed fines remain blocked
until actual rules/service/liable-member authority is
established; do not inherit ARC's specifically removed
legal-decision gate for HOA ARC. Phase 4.7 remains
IN PROGRESS and Phase 4.8 remains paused.

## CURRENT SESSION UPDATE — 2026-09-28 HOA VIOLATION RECIPIENT VERIFIED

**Latest product source** `e6329464cdcaaae21235039ddbc6e4edc6a9fcdd`.
Implementation `f9983bf6bf00f24dbce79f46afa7197ff4a2a9f1`
introduced `hoa_violation_recipient_drafts`, a one-case/one-record
same-org/association/property verified-login staff recipient reference,
new customer UI and focused regression plus dedicated HOA browser
integration. Its first CI `36506977415` FAILED with **766 passed,
11 deselected, 5 failed**: five database-bootstrap tests detected
that the new migration accidentally reused older owner-ACH revision
`b6d8f0a2c4e7`. No backend domain test failed, browser/staging
were skipped. Corrective product commit `e6329464` moves ONLY
the new migration to unique ID `f4b6d8a0c2e9` and updates fresh,
legacy, PostgreSQL and staging expectations; it does not
rewrite the existing owner-ACH migration. Full CI
**36507547330 SUCCESS all six jobs**: backend **771 passed,
11 deselected, 18332 warnings in 245.51s**; E2E **11 passed,
128 warnings in 42.90s**. Frontend lint/TypeScript/build,
platform-admin, security and staging SUCCESS. All tests ran
in hosted CI; **TESTS NOT RUN locally**. Alembic HEAD
`f4b6d8a0c2e9`, **157 SQLAlchemy model tables** from 156.
No frozen `docs/` nor parity files modified.

New `GET/PUT/DELETE /api/hoa/associations/{association_id}/
staff-cases/{case_id}/recipient` uses existing paid HOA+compliance
release/entitlement, PROPERTIES.ALL, PEOPLE.CONTACTS, active
association/property and active observation/case scopes. ADMIN/
OWNER may explicitly select or clear an active same-association
Contact link; assigned MANAGER may read, not write; foreign
org/tenant/crew and missing permissions fail closed. A
recipient requires SAME-org verified active customer User
with case-insensitive matching Contact email. Retained
contact or user edits are revalidated live and a stale
identity does not surface as authorized. Duplicate unchanged
PUT rejects 409; an archived reference may be explicitly
rerecorded, never silently activated; closed cases cannot
change their candidate. The record is private with no-store
response, redacted scoped immutable audit, generic notes
denylist. A matched authenticated user is only a *potential
correspondence recipient*, **NOT certified member liability,
not proof of statutory notice service and not authority for
a fine or GL posting**. Every schema response flags delivery,
liability and certification FALSE. New case UI presents
a contact picker and explicit warning. Focused tests cover
verified versus unverified login, live identity changes,
duplicate, archive/re-record, all role/org/property/
permission/closed-state boundaries and ZERO Charge, Lease,
RentInvoice and GL effects. Existing dedicated violation
browser regression also binds a synthetic same-scope
verified login, checks "Notice delivery DISABLED" and
unchanged financial counters.

**ARC board decision batch immediately preceding this work
has independently green CI `36502395287`: 769 backend passed,
11 deselected; 11 browser passed, all six jobs.**
Source `88d598d` contains authenticated association
board-seat designation, designated-officer offline meeting
decisions with maker/date/private supporting record in
audit history, direct terminal APPROVED/DENIED (NO
`legal_decision_effective=false` flag, NO second
document-upload confirmation), atomic optional verified
member receivable and balanced central GL posting, appropriate
work-order or inspection follow-up, retryable scoped
notification outbox, unique decision and fee identifiers,
locked-period/paid-fee-safe GL reversals. Its latest UI and
browser contact-selector fixture are VERIFIED. Do not
reimplement or replace the removed blanket ARC gate.
Member receivables are not automatically tenant Charges
and no unidentified member is silently billed.

**Phase 4.7 remains IN PROGRESS.** Next meaningful
violation batch: individual proposed correspondence draft
and explicit member/delivery policy review using existing
case events and recipient, with controlled legal delivery
and fine/charge execution only when applicable rules,
verified payer and approval evidence can actually be
established. Never relabel mere staff dates as issued
statutory notices, or unassessed proposals as GL income.
The generic six-feature HOA completion condition remains
OPEN; Phase 4.8 Commercial remains paused. Root
handoff-only commit is documentation, NOT a new verified
product source.

## CURRENT SESSION UPDATE — 2026-09-28 HOA ARC BOARD DECISIONS VERIFIED

**Verified PRODUCT source** `69f0b9297fcdff2027be6af582d8efd9f62ba32b`,
following implementation `4093a2f0adf611c1c958deea31858f8efea6459d`.
First CI `36499467784` failed exactly ONE outdated staging
schema table-count expectation: backend **762 passed, 11 deselected,
1 failed**, E2E/staging skipped. The corrective commit `69f0b92`
updates `backend/tests/test_prepare_database.py` for the real
two-table migration. Full **CI 36499924708 SUCCESS six of six**:
backend **763 passed, 11 deselected, 17824 warnings in 233.19s**;
dedicated/authenticated browser **11 passed, 123 warnings in 34.52s**;
frontend lint, TypeScript, build, platform-admin, security,
staging-config PASS. **TESTS NOT RUN locally**. Alembic
**`f3a5c7e9b1d4`**, **153 model tables**. No frozen `docs/`
or parity changes.

User explicitly directed ARC board decisions recorded as operative
when the board decides, with NO software-added
`legal_decision_effective=false` flag. This user-directed
exception is specific to the ARC flow; it does NOT waive
organization isolation, financial permissions, authoritative
payer identification, existing central GL locks or statutory
violation/dues/reserve requirements. Current
`HOAARCApplicationOut` and ARC UI no longer expose the
`legal_decision_effective` or software governing-authority
flags. Staff intake/review/decision-preparation remains intact.
New POST
`/api/hoa/associations/{association_id}/arc-applications/
{application_id}/board-decision` records one final APPROVED
or DENIED board decision, history event and redacted immutable
audit. Existing paid `release.properties.hoa`, compliance,
association/property, active applicant/contact links and
ADMIN/OWNER live scope apply. It requires a verified logged-in
actor whose email matches the active same-org/association/
property eligible HOA board seat's contact email. A staff-only
preparation, generic Contact, inactive seat or unrelated
account cannot finalize the action. A unique decision/application
constraint and row lock block duplicate decisions and fees;
approved/denied status is terminal in the staff review
state machine.

Optional ARC approval fee, only with a verified same-org
applicant user matching the scoped applicant contact email,
creates a dedicated `hoa_arc_member_charges` record (NOT
tenant-only `Charge`) and a balanced central
`post_transaction(...,commit=False)` ASSET receivable /
INCOME GL journal entry in the same DB transaction. It
requires current CHARGES, RECEIVABLES and GL_ACCOUNTS
permissions, separate active same-org accounts and honors
locked periods and central GL restrictions. No fee is posted
on no-fee decisions or denials. This is a NEW member receivable
record with due date and GL source, not complete association
member payments, reconciliation or reversal collection.
Optional real WorkOrder is available only when applicant is
a verified TENANT with ACTIVE lease in the expressly supplied
same-property unit and maintenance permission; do not silently
fabricate a work order against a homeowner absent a tenant
work-order subject. No automatically scheduled inspection.
When a verified applicant login exists, notification emails
use the existing SMTP service AFTER durable decision, tracking
SENT vs FAILED; no email delivery implies no rollback of
the decision/fee. Unmatched unverified contacts yield
NO_VERIFIED_RECIPIENT; no email claimed. Email retry/outbox is
NOT YET IMPLEMENTED. Final ARC data and fee details are
property-scoped, accounting endpoint requires CHARGES;
generic notes/attachments deny new sensitive tables.
Tests cover board identity, finality, cross-org/property,
postings, locked-period rollback, recipient failure, duplicate
replay and dedicated browser final approval. Do not repeat.

**Phase 4.7 HOA remains IN PROGRESS, Phase 4.8 paused.**
Exact next authorized feature batch from latest user direction:
continue the EXISTING violation workflow without rebuilding
verified OPEN -> NOTICE_DRAFT -> CURE_TRACKING /
HEARING_PLANNED -> FINE_PROPOSED -> RESOLVED -> CLOSED
staff stages and configurable procedure policy. Add persistent
scope-checked action/correspondence history and safe recipient
identity prerequisite, browser regression, without inventing
jurisdictional legal notice/cure/fine authority. Actual
statutory notice delivery, assessed fines and member-GL
posting still require authenticated governing/procedure and
payer authority; org-supplied policy text is not proof.
Do not mark six-feature HOA complete or resume Commercial.
Root handoff-only commit following green CI does not create
a new verified product source.

## CURRENT SESSION UPDATE — 2026-09-28 HOA ISSUANCE READINESS VERIFIED

**Verified PRODUCT source** `1aa87bdf2ad55e4728c117e1552fc6b94be3a1a9`.
GitHub Actions **36494856673 SUCCESS all six jobs**: backend
**760 passed, 11 deselected, 17603 warnings in 192.10s**;
authenticated browser **11 passed, 116 warnings in 39.54s**;
frontend lint/typecheck/build, platform-admin, security and
staging-config all PASS. Hosted CI only, **TESTS NOT RUN locally**.
No schema/migration changes: Alembic `e2f4a6c8b0d3`, **151
SQLAlchemy tables**. Frozen `docs/` and parity files unchanged.
Previous handoff-only run `36494822406` was cancelled/superseded;
do not report that docs-only run as a separate green product.

The new GET `/api/hoa/associations/{id}/draft-assessments/
{proposal_id}/planned-occurrences/{occurrence_id}/issuance-readiness`
is deliberately READ-ONLY and fail-closed. It reuses the live
HOA paid entitlement/release, association/property/proposal/
planned-occurrence and contact scope, then requires ADMIN/OWNER
plus ACCOUNTING.CHARGES and ACCOUNTING.GL_ACCOUNTS permissions.
It checks the historical plan against the live payer reference,
an optional active same-org INCOME GL candidate, the current
organization accounting lock and VOIDED status. No identity
from a mere staff contact is treated as a legal debtor; the
candidate is NOT an approved HOA GL mapping. The response
names missing governing authority, assessment approval,
legal payer liability and approved GL mapping. Flags
`governing_authority_verified`,
`assessment_approval_verified`,
`legal_payer_liability_verified`,
`approved_gl_mapping_verified`, `posting_enabled` and
`reversal_enabled` are all explicitly FALSE regardless of a
valid candidate. This API does not accept attestation-by-query
or mutate Charge, RentInvoice, GLTransaction, GLEntry, bank,
posted history, a due date or a legal notice.

The existing unissued planning-history UI now allows admin/
owner to inspect precisely these blockers on each planning
row, without a dangerous "Issue charge" button. Two focused
new backend regressions cover active versus voided period,
locked date, candidate income GL versus approved mapping,
current payer archive, cross-property/manager/tenant/foreign
denial, accounting permission and feature revocation, no-store
and ZERO Charge/GL effects. The already dedicated HOA dues
browser test now also checks posting-readiness display and
zero finance; browser suite remains 11 tests. Earlier
reserve batch `9912398f` is independently verified by
`36493987607`, and earlier HOA/Commercial features remain
untouched.

**Original user completion condition remains OPEN.**
Recurring/special plans and history are NOT issued legal dues.
No official notices/fines, adopted board votes/minutes, final
ARC legal decisions or reserve GL transfer are enabled.
Private document evidence and the `$79/mo` hidden catalog
with separate paid HOA gating are verified; authorized
production add-on checkout/Stripe activation remains absent.
Operational legal activation requires actual applicable
authenticated HOA governing instruments, identifiable
authorized association actors/board members, approved
assessment payer, legal notice/fine/ARC rules, and authorized
reserve/GL policy. Org-entered text is not such evidence.
Preserve generic draft/case/review/document/meeting/GL-read
features and independent verified Phase 4.8 source, but do
NOT advance Phase 4.8 until requested six generic HOA
workflows are integrated and tested.

**Exact next safe original HOA task:** implement a reviewed,
non-self-certifying authority-evidence/decision-maker contract
that can ultimately authorize separate atomic issuance/
reversal and reserve posting through the existing central GL
once the genuine governing documents and payer mapping exist.
Do not invent authenticated HOA records, legal deadlines or
auto-bill a generic tenant from a Contact link. Also continue
independently safe board-member identity and subscription
purchase integration only with adequate authentication and
provider authorization; no self-issued legal authority.
This root handoff-only update is not a product test.

## CURRENT SESSION UPDATE — 2026-09-28 HOA RESERVE MOVEMENT DRAFTS VERIFIED

**Last verified PRODUCT HEAD**: `9912398fcb67d4a37ddb31c656c47f40c525c33a`.
Initial implementation `f781ee816f8810e1d715924eccc0660c70c7bf25`
introduced an unissued, idempotent reserve movement draft workflow,
migration `e2f4a6c8b0d3`, model table `hoa_reserve_movement_drafts`
and a new dedicated browser regression. Initial CI `36493083587`
FAILED browser: 9 passed, 2 failed; backend, frontend, security,
platform admin and staging PASS. First browser failure was the
intermittent login-navigation issue in an existing ballot test.
The second, real integration defect: the movement form reused
reserve-account options and could not select a counterparty after
reserve mapping. Corrective source `9912398f` added a distinct
scoped reserve-counterparty option endpoint, returning only
same-organization active cash-like ASSET GL display fields,
excluding all actively mapped reserve GLs, with admin/owner
access, no-store responses, and no routing/account secrets.
The movement UI now calls that endpoint; focused backend
regression checks the selector and manager denial. Full CI
**36493987607 SUCCESS ALL SIX JOBS**: backend **758 passed,
11 deselected, 17505 warnings in 232.87s**; browser **11 passed,
116 warnings in 37.21s** including the new reserve workflow.
Frontend lint/typecheck/build, platform admin, security and
staging PASS. **TESTS NOT RUN locally**. No frozen `docs/`
or parity checklist modified. Schema head `e2f4a6c8b0d3`,
**151 model tables**; PostgreSQL, bootstrap and legacy guards
green.

Bounded functionality: ADMIN/OWNER under existing paid HOA release,
property membership and accounting permissions can prepare
TO_RESERVE/FROM_RESERVE draft records referencing an active same-org
reserve mapping and a distinct cash-like GL, with a unique
org-scoped idempotency key, positive amount and planned date.
A replay cannot mutate a saved or cancelled request. Explicit
cancel and association/property unlink cancel planning with redacted
audit and no resurrected draft. Separate browser test proves
creation, cancellation and no Change to Charge/GL counters.
These are NOT posted movements, bank transfers, bank reconciliation,
legal reserve ownership or immutable GL reversal; response flags
posting/funds/verified reserve authority FALSE. Existing central GL
locks, ownership, original read-only reserve book remain untouched.

**Phase 4.7 HOA IN PROGRESS**. All generic infrastructure is not
legally effective. Outstanding: authenticated governing/assessment
payer evidence and approved GL mapping for actual recurring/special
dues, legally issued violation notices/fines, authenticated board
membership and legally effective votes/minutes, ARC legal approvals,
and reserve posted movements/reversals. Org-configured policies and
synthetic E2E sources are NOT legal proof. $79/mo HOA catalog +
hybrid entitlement are verified, but customer-authorized production
purchase/provider checkout are not yet implemented. Phase 4.8 stays
paused. **Exact next independently safe HOA batch**: separate,
permissioned read-only issuance/posting/reversal readiness contract
for current planned occurrences, checking current payer reference,
eligible income GL candidate, accounting lock, and missing legal
authorization without issuing tenant charges or posting GL. Do not
repeat verified reserve planning or skip legal prerequisites.
The next handoff-only commit is not a new product CI result.

## CURRENT SESSION UPDATE — 2026-09-28 HOA ADD-ON GATE VERIFIED

**Verified product source** `ea2f94e431fca28056c8bf54c619265d80cd9c80`.
Hosted **GitHub Actions 36491890725 SUCCESS all six jobs**:
backend **756 passed, 10 deselected, 17406 warnings in 125.36s**;
E2E **10 passed, 100 warnings in 28.18s**; frontend
lint/TypeScript/build, platform admin, security and staging all
PASS. No local tests run. E2E exercised existing dedicated
HOA flows using an explicitly disposable synthetic test
subscription; no new browser test was added in this batch.

This bounded HOA commercial-preparation batch adds migration
`d1e3f5a7b9c2` after `c0d2e4f6a8b1` with a paid
`Module(key="hoa", is_core=False)`,
`ModuleFeature(feature_key="hoa")`, a hidden
`release.properties.hoa` gate and an INACTIVE catalog
`AddOn(code="hoa_monthly", unit_price_cents=7900, currency="USD")`.
The $79/month price is a catalog record, **not a working checkout
offer**, automatic invoice, Stripe price or active customer
subscription. The existing `SubscriptionItem` entitlement
resolver checks paid HOA separately from the existing compliance
feature. HOA backend _access now demands BOTH the live
compliance capability and live dedicated HOA release/entitlement/
organization/permission decision. Customer property UI wraps
HOA with the same extra Flag, leaving unrelated affordable and
commercial property compliance presentation untouched. Existing
HOA tests' synthetic feature fixtures were extended for the
separate gate; focused new regression covers hidden/released,
no-subscription, per-organization paid grant, suspension, org
disable and restoration. Existing browser coverage provisionally
grants the test org a synthetic module subscription only within
disposable E2E context and tears it down afterward.

Existing DB Alembic migration seeds data; fresh bootstrap
seeds identical hidden catalog through idempotent
`seed_unreleased_hoa_catalog` because fresh bootstrap stamps
head and skips data-only migration. Both paths guarded in
schema tests, 150 model tables (unchanged), new Alembic head
**d1e3f5a7b9c2**. Frozen `docs/` and parity unchanged;
no Phase 4.8 work or new GL/Charge/RentInvoice mutation.

**Status distinction**: paid HOA entitlement/catalog and
release gating are now VERIFIED. Production add-on checkout,
provider price, signed subscription acquisition/cancellation,
and authorized customer purchase remain **NOT IMPLEMENTED**;
no consumer was billed or granted HOA access by this migration.
The earlier recurring planning history, violation staff stages,
private documents, meeting/ballot/minutes preparation, ARC
application/review, reserve read-only book remain verified.
Actual legally issued dues/reversals, operative violation
notices/fines, board voting/official minutes, ARC decisions,
reserve posted transfers and production add-on selling are
NOT COMPLETE. Real legal/financial activation requires
authenticated governing, payer and approved GL evidence.
Org-configured policies alone cannot certify this authority.
Continue generic Phase 4.7 only; DO NOT resume Phase 4.8.

**Exact next bounded authorized HOA work**: use existing
`hoa_planned_occurrences`, payer drafts, current GL and receipt
architecture to implement a separately gated, no-execution
posting/reversal validation contract and document what
authenticated actor, payer and GL mapping must provide.
Do not create any tenant charges or actual GL transactions
from unverified staff contacts. Alternatively implement the
next unblocked secure generic board/ARC/reserve integration
without enabling legally effective status; avoid repeating
verified drafts. Re-fetch HEAD and CI before further edits.
Root handoff-only commit is not a fresh product verification.

## CURRENT SESSION UPDATE — 2026-09-28 HOA PLANNING HISTORY VERIFIED

**Verified product source** `867cf2158bb98a962e1fd17c8ce3d342469c8187`.
Initial implementation `482dd87e17a0b07dea597acfa207f9437846dafb`;
the first CI run `36489493149` passed the backend, frontend,
platform-admin, security and staging jobs but failed ONE NEW browser
test at an unaccepted intentional JavaScript confirm dialog;
the previous nine E2E passed. Corrected test source `867cf21`
explicitly accepts that browser dialog. **GitHub Actions
36490457829 SUCCESS ALL SIX JOBS**: backend **755 passed,
10 deselected, 17376 warnings in 158.34s**; authenticated
browser **10 passed, 44 warnings in 21.48s**; frontend
lint/TypeScript/build, platform-admin, security and staging-config
PASS. Hosted CI only; **TESTS NOT RUN locally**.

One new `hoa_planned_occurrences` table and Alembic head
**`c0d2e4f6a8b1`** from `b9d1f3a5c7e2`;
**150 SQLAlchemy model tables**. Fresh/legacy migration,
PostgreSQL and staging guards passed. Frozen `docs/` and
planning parity unchanged. No new Phase 4.8 implementation.

This is a bounded Phase 4.7 C2 staff PLANNING batch: the existing
association/property-scoped assessment and suggested payer
contact are rechecked live under the verified compliance release,
PROPERTIES.ALL and PEOPLE.CONTACTS permission and assignment.
ADMIN/OWNER can explicitly generate bounded monthly/quarterly/
annual/one-time planning-period rows from the verified read-only
calendar and archive an individual row as VOIDED; assigned MANAGER
can read history. Stable unique (proposal, planned date) keys
make replay idempotent, including a previously voided period.
The suggested payer reference and proposal amount/revision are
snapshotted as planning history; updating a proposal never
rewrites prior records. Redacted audit, no-store reads,
cross-org/foreign/inactive-scope denials and generic notes/
attachment denylist apply. Existing UI now opens an unissued
planning-history panel with explicit record/void/replay controls.
Two focused backend tests and one NEW dedicated HOA browser
regression verify history, leap-day, idempotence, revocation,
non-resurrection and zero tenant Charge, Lease or GLTransaction
mutations. The void is a STAFF PLANNING ACTION, **not** a
financial reversal.

**NOT ISSUED, NOT CHARGED, NOT COMPLETE**: no approved/legal payer,
invoice/due-date liability, tenant-charge mutation, bank transfer
or central GL posting was implemented or enabled. Real
assessment issuance, posted accounting and posted reversals
remain gated on authenticated association/payer authority and
approved central-GL account mapping, including accounting
locks, idempotency and ownership safeguards. The other six-feature
gaps also remain: legally effective violation notice/fines,
authenticated board voters/adopted minutes, operative ARC
approval/denial, reserve posting and official reserve
reconciliation, plus the requested **$79/month HOA add-on
subscription/entitlement activation**. Existing generic staff
violation, documents, meeting/ballot/minutes, ARC and reserve
workflows remain verified and untouched. Org-entered procedures
are not legal authentication. HOA six-feature condition remains
IN PROGRESS; do NOT resume Phase 4.8.

**Exact next authorized batch**: implement and verify the generic
HOA commercial add-on entitlement/release-gating and proposed
$79/month billing catalog using existing plan/module/checkout
services WITHOUT activating or invoicing anyone absent a
customer-authorized subscription; separately continue
authorization-ready issuance/posting/reversal contracts only
when genuine governing, payer and GL prerequisites are
reviewed. Inspect current HEAD/CI before any new edits.
This update itself is handoff-only, NOT a product test.

## CURRENT SESSION UPDATE — 2026-09-28 HOA SUGGESTED PAYER VERIFIED

**Verified product source** `7ee92cfd067b2845eaca8b65bd532f9a37bcf615`.
Initial implementation `7757fd272f0ae0f52f4f8d160333eebc56e6d525`;
first GitHub Actions run `36484718678` FAILED **3 new
backend tests** because the response serializer passed a Contact
object rather than its display-name string; all other **750 backend
tests passed, 9 deselected**, while dependent E2E/staging jobs
skipped. Corrective source `7ee92cf` now passes full
**GitHub Actions 36485528517 SUCCESS, six of six jobs**:
backend **753 passed, 9 deselected, 17286 warnings in 206.89s**;
authenticated browser **9 passed, 36 warnings in 30.09s**;
frontend lint/TypeScript/build, platform-admin, security and
staging-config PASS. Hosted CI only; **TESTS NOT RUN locally**.
No additional dedicated payer browser test was added in this
batch; nine previously existing E2E passed.

One new scoped `hoa_payer_drafts` metadata table with Alembic
`b9d1f3a5c7e2` after `a8c0e2f4b6d1`: **149 model tables**.
User-facing assessment panel can suggest an existing active
same-organization, same-association/property HOA Contact link
for a draft assessment. Scoped GET/PUT/DELETE recheck live
compliance release and PROPERTIES.ALL+PEOPLE.CONTACTS permission,
current property assignment and active proposal/contact.
ADMIN/OWNER write; assigned MANAGER reads. A unique
proposal-reference constraint prevents duplicates; archived
references cannot be resurrected by reassociation. Archive of
linked contact, draft assessment or association/property
automatically archives the staff reference with redacted audit.
Generic notes/attachment target access is denied. Three focused
backend regressions cover CRUD/archive/replay, cross-org/cross-
property/manager/tenant permission and feature revocation,
contact relink, proposal cleanup and **zero Charge/GLTransaction
mutations**. Source excludes property-owner/tenant payment
liability, GL accounts, due dates, legal decisions and issuance.
Response: `STAFF_SUGGESTED_UNVERIFIED`,
`legal_payer_verified=false`, `issue_charge_enabled=false`.
This is NOT a legal payer or an actual HOA receivable.

**Phase 4.7 remains IN PROGRESS under user's six-feature
condition.** The past verified HOA dues calendar, violation
cases/procedure drafts, CC&R/rules/private minutes file index,
meeting/attendance/motion/ballot plus minutes draft, ARC
application/review, and reserve read-only book remain intact.
Next authorized bounded HOA batch: durable idempotent occurrence
generation and history tied to payer reference; separate
central-ledger posting/reversal remains disabled until
authenticated payer/assessment authority and approved GL
mapping are provided. Actual issued recurring and special HOA
charges, legally enforceable notices/fines, authenticated board
portal/certified votes/minutes, operative ARC decisions, reserve
posting and the $79/month HOA subscription/entitlement all
remain NOT COMPLETE. Do not advance Phase 4.8, do not invent
governing rules or issue a charge to generic tenant Charge
without verifying the legally liable entity. Frozen `docs/`
and parity files unchanged. This handoff itself is docs-only,
not fresh product testing; re-fetch current HEAD/CI next.

## CURRENT SESSION UPDATE — 2026-09-28 HOA MINUTES DRAFT VERIFIED

**Verified source** `548255b12229604df44b160c4356d8a3bed3ddf0`.
GitHub Actions **36483310027 SUCCESS all six jobs**: backend
**750 passed, 9 deselected, 17160 warnings in 221.28s**;
authenticated E2E **9 passed, 36 warnings in 29.20s**.
Frontend lint/TypeScript/production build, security,
platform-admin and staging configuration SUCCESS. Hosted CI only;
**TESTS NOT RUN locally**. No additional minutes-specific browser
test was added in this batch; the nine browser tests are the
existing suite at the current source.

Phase 4.7 HOA staff-meeting minutes now have one scoped staff
minutes-draft record per existing active meeting, with restricted
read/write/archive API, ADMIN/OWNER writes, assigned MANAGER reads,
organization/property/association/release/permission gates and
no-store reads. Existing workspace includes a customer minutes
panel. Updating preserves the record ID; archived minutes
cannot be resurrected through upsert. Parent meeting archive
soft-archives the related minutes and records a redacted audit;
private file minutes indexing remains available separately.
Input rejects claimed official approval/notice/GL fields,
status is STAFF_DRAFT_UNVERIFIED and all legal_effective/
quorum_certified/board_approval_certified indicators remain false.
Two new focused regressions cover CRUD, archive/replay blocking,
cross-scope/permission revocation, parent cleanup, and no
Charge or GLTransaction mutation. No official vote, minutes
adoption or notice issuance was enabled. Existing HOA staff
ballot records source `46f148b` and all earlier verified
HOA/commercial work remain preserved. No frozen `docs/` or
parity edits.

Migration `a8c0e2f4b6d1` follows `f7b9d1e3a5c2`; **148
model tables**. Fresh, legacy and PostgreSQL guards passed.

**Six-feature completion remains OPEN.** Dues payer assignment,
idempotent recurring/special charge history, authorization and
central posting/reversal; legally gated violation enforcement;
authenticated board-member portal, certified voting/minutes;
legally effective ARC decisions; reserve transfer/posting;
and the $79/month HOA add-on pricing and hybrid entitlement
remain unfinished. Existing violations, board ballot staff
recording, document storage, ARC application/review, reserve
read-only book, and dues planning preview must not be
reimplemented. Jurisdiction-specific legal actions remain
disabled pending verified governing rules; org-entered policy
does not establish legal authority. **Next bounded HOA batch**:
record explicitly scoped dues payer assignments and planned
charge generation/history without posting, then add a separate
authorization-backed posting/reversal path through the existing
accounting ledger. Do not resume Phase 4.8 before all six
generic HOA workflows are verified. Handoff commit is docs-only,
not a new product verification. Re-fetch branch HEAD and CI.

## CURRENT SESSION UPDATE — 2026-09-28 HOA BOARD BROWSER VERIFIED

**Product source** `da557728f400a7b3b03c27ff7f33f935660d805a`;
dedicated browser source `211585a3ebfdabcccacd428470b87f7e11550650`
corrected by `da557728` after one strict-mode selector failure
(the hidden SECRETARY select option matched the role text).
First CI `36474996561`: frontend, backend, security, platform
admin and staging PASS; browser **7 passed, 1 failed**. The only
failure was the new ambiguous test selector, not broken functionality.
Corrected GitHub Actions **36475977525 SUCCESS all six jobs**:
backend **745 passed, 8 deselected, 16926 warnings in 185.98s**;
E2E **8 passed, 28 warnings in 23.81s**; frontend lint/TypeScript/
build, security, platform admin and staging SUCCESS. Hosted CI only,
**TESTS NOT RUN locally**. One of eight is the new dedicated board
browser test: synthetic same-association contact and staff-role
proposal, proposed voting checkbox, configurable thresholds, proof
that the UI shows unverified/vote disabled, and zero Charge/GL
mutations. No real board identity, certified quorum or legal vote.
Schema remains `e6a8c0d2f4b1`, **146 model tables**. No frozen
`docs/` or parity edits. The previous verified product source
`9b7551da` remains the board backend/UI implementation; `da557728`
adds and verifies dedicated browser coverage.

**Phase 4.7 still IN PROGRESS** and the user explicitly prohibits
resuming Phase 4.8 until all six generic HOA features are built
and tested. Next bounded original HOA work: generic vote record
and meeting-minutes lifecycle integrated with the existing scoped
meeting, proposed seat and quorum records, while effective legal
voting stays disabled until verified board identities/authority.
Other incomplete items remain dues payer/charge history and central
idempotent posting/reversal, legally gated violations issuance,
reserve central GL movement, board identity and $79/month subscription/
entitlement. No fake governing rules or implicit authorization.
This handoff itself is docs-only.

## CURRENT SESSION UPDATE — 2026-09-28 HOA BOARD ROLE PROPOSALS VERIFIED

**Verified product source** `9b7551da061fe6bb032f799dc6fdf32f705c2069`.
GitHub Actions **36473978742 SUCCESS all six jobs**: backend
**745 passed, 7 deselected, 16926 warnings in 207.62s**;
authenticated browser **7 passed, 20 warnings in 24.15s**;
frontend lint/TypeScript/production build, platform-admin, security,
staging-config all passed. **No local tests run.** The seven browser
tests are the previously verified browser suite; dedicated board UI
automation is still outstanding.

Phase 4.7 bounded board infrastructure uses two new scoped model
tables `hoa_board_seats` and `hoa_board_rule_drafts`. Alembic
`e6a8c0d2f4b1` follows `d5f7a9b1c3e4`, **146 model tables**.
A proposed seat references the existing SAME-org, SAME-association,
SAME-property active HOA contact link, not a new identity system.
Staff can propose CHAIR, VICE_CHAIR, SECRETARY, TREASURER, DIRECTOR
or ALTERNATE and store a staff-proposed voting eligibility flag;
admins/owners can record/archive proposals, assigned managers read.
Configurable proposed quorum and approval threshold values are stored
separately without inventing jurisdiction-specific formulas.
Records and UI ALWAYS state `authority_verified=false`,
`quorum_certified=false`, `vote_enabled=false`. There is no
authenticated board member access, legal quorum, vote, adoption,
dues issuance or accounting effect. Generic notes/attachments deny
new table targets, no-store scoped reads and redacted immutable
audit apply. Contact unlink, association/property unlink or
association archive deactivates proposed seats/rules and never
silently resurrects archived records on relink.

Three focused backend regressions test staff CRUD and read scopes,
no duplicate resurrection, permission/release revocation,
cross-org/manager/tenant/foreign contact isolation, schema
rejection of claimed legal authority, unlink/archive cleanup
and zero Charge/GLTransaction mutation. The prior verified
ARC, case, procedures, meeting workspace, reserves and document
features remain unchanged. No frozen docs/ or parity files changed.

**Phase 4.7 remains IN PROGRESS** under the user's SIX-feature
completion condition; this is only an internal board-role/rule
foundation. Next bounded batch: authenticated board-member
access boundary and generic recorded ballot/minutes workflow,
with dedicated board browser regression. No real voting/right
or official minutes can become effective before association
identity, governing documents, eligibility and quorum policy
have been authenticated. Actual HOA dues payer assignment,
idempotent issuing/reversal plus central GL posting, reserve
transfers, and $79/month billing/entitlement also remain
incomplete. Phase 4.8 is paused without rolling back its
existing verified commits. All jurisdiction-specific legal
actions remain disabled; staff configuration alone is NOT
proof of authority.

This handoff is docs-only. Fetch current HEAD and CI at next
entry; do not falsely attribute this documentation-only commit
to new product verification.

## CURRENT SESSION UPDATE — 2026-09-28 HOA ARC APPLICATION WORKFLOW VERIFIED

**Verified product source** `01df09859e98e6575c8c16ae49c1dc23d1a94d67`.
Implementation began at `0fa7b80698b29dcfffb1415717665d4b49803e3c`;
compile import correction `16ab88d84744b21725b42139786870aa368c0415`;
archive duplicate fail-closed source `e7e49d1521e359d1d6fe76cb09782929fee3a3b4`;
final regression correction `01df09859e98e6575c8c16ae49c1dc23d1a94d67`.
GitHub Actions **36466695309 SUCCESS all six jobs**:
backend **742 passed, 7 deselected, 16805 warnings in 206.88s**;
authenticated/dedicated browser **7 passed, 20 warnings in 21.86s**;
frontend lint/TypeScript/build, platform-admin, security and staging passed.
No local tests run. Earlier source run `36465878722` failed compile from
one invalid import expression; `36466039178` then ran **741 passed,
1 failed, 7 deselected** because a test attempted to recreate an archived
application despite the schema's intentional unique/no-resurrection rule.
The final source fails closed with HTTP 409 and passed fully. Intermediate
run `36466679647` was superseded/cancelled.

Migration **d5f7a9b1c3e4** follows c4e6a8d0f2b1 and adds
`hoa_arc_applications`, `hoa_arc_application_attachments` and
`hoa_arc_review_events`: **144 model tables** from 141. Fresh SQLite,
PostgreSQL, staging preparation and legacy upgrade guards passed.

Generic ARC workflow now reuses one existing active same-scope staff ARC
intake plus an active same-association/property HOA Contact link as the
applicant reference; no parallel applicant identity store was created.
ADMIN/OWNER can record an application and review transitions; assigned
MANAGER can read through the existing compliance/property scope. Review
history supports SUBMITTED -> UNDER_REVIEW -> MORE_INFO_REQUESTED ->
INFO_RECEIVED -> READY_FOR_DECISION -> DECISION_PREPARED, including
prepared APPROVE/DENY recommendations. Every response states
`governing_authority_verified=false` and
`legal_decision_effective=false`; there is no operative approval,
denial, permit, deadline, fee, charge or notice.

ARC application files reuse existing PRIVATE property attachments and are
blocked from owner/tenant generic sharing while actively linked. Archive
of applicant contact, ARC intake, association or association/property
scope soft-archives dependent applications; relink does not silently
restore them. Generic notes/attachments cannot target ARC internal tables.
Audits record scoped IDs/status only. No Charge, RentInvoice, GLEntry,
GLTransaction or bank mutation. Dedicated browser coverage records ARC
intake, application, staff review and prepared approval, then asserts
"Effective legal decision: NO" and zero finance mutation.

**Phase 4.7 remains IN PROGRESS** under the user's six-feature completion
condition. ARC generic application/review/document/history infrastructure
is now implemented; legally effective approval/denial remains gated on
authenticated governing/decision authority. Existing private CC&R/rules/
minutes storage, violation case workflow, staff meeting participation/
motion prep and reserve read-only book remain verified. Still required:
explicit board member role/eligibility/approval configuration and formal
generic vote/minutes workflow without pretending authority; actual dues
payer assignment + idempotent charge history/reversal/posting contract
behind authority/accounting gates; reserve transfer/posting workflow
behind central GL locks; and the $79/month HOA add-on entitlement/pricing
activation. Do NOT resume Phase 4.8 until the six generic HOA workflows
meet the user's completion condition.

## CURRENT SESSION UPDATE — 2026-09-28 HOA MEETING WORKSPACE VERIFIED

**Product source** `61dcfdcef466eb2a20cc8adb8cf865d0e4eb6bb4`;
the following HEAD `28c3aa3cbda085d39112a6b781edfe528b0d07e2`
was documentation-only (separate prior reserve handoff), but retains
the exact product source. Hosted GitHub Actions **36463180281
SUCCESS, all six jobs**: backend **738 passed, 6 deselected,
16593 warnings in 209.74s**; dedicated/authenticated E2E
**6 passed, 12 warnings in 19.61s**; frontend lint, TypeScript and
production build, platform admin, security, staging SUCCESS.
**TESTS NOT RUN locally.** Migration `c4e6a8d0f2b1` follows
verified reserve `c3e5a7b9d1f2`; SQLAlchemy **141 model tables**
(previous 139). All PostgreSQL/fresh/legacy schema guards green.
Frozen `docs/` and parity checklist were not altered.

New strictly staff-only meeting workspace REUSES the previously
verified association/property membership, meeting-draft planning
and contact-link models and their live role, manager-assignment
and compliance gate, with extra PEOPLE.CONTACTS permission for
contact identity/attendance access. Separate `hoa_meeting_participation`
and `hoa_motion_drafts` tables hold staff-reported attendance and
proposal text. Read/list/create/correct/archive actions are scoped to
same-org active meeting and active association/contact link,
nondeleted contact, actor/permission and property. Browser UI lives
under the existing HOA meeting drafts, with direct links to proposal,
attendance and archive controls. It explicitly DOES NOT claim
board-member credentials, eligibility, quorum, official agenda
delivery, statutory meeting, official vote/resolution, approval or
legal authority. Response flags always state
`board_authority_verified=false`, `quorum_certified=false`,
`vote_enabled=false`. No automatic attendee voting or certification.

Association unlink/archive, meeting-draft archive and contact
unlink soft-disable affected historical workspace records and
do not silently resurrect them on relink. Audit records are redacted;
generic notes/attachments deny both internal tables. All operations
are zero `Charge`, `RentInvoice`, `GLEntry`,
`GLTransaction` and bank effects. Four focused backend tests
cover staff lifecycle, out-of-org/property/user access,
PROPERTIES.ALL / PEOPLE.CONTACTS/release revocation, archive/
relink, schema prohibition on invented board decisions, audit
and nonmutation. Two dedicated HOA browser tests now cover both
the earlier procedure/case workflow and new meeting motion UI,
in addition to prior private evidence workflow; browser total
is **6 passed** including three general smoke. The earlier
`e7a6ea44` case-test source CI `36461379481` was superseded/
cancelled; no false PASS attributed. The verified product commit
`61dcfdce` includes both browser tests and passed all jobs via
run `36463180281`.

**Phase 4.7 remains IN PROGRESS** per user's six-feature
completion requirement. Staff rule configuration, proposed
assessment preview, private source storage, internal violation
cases, unverified attendance/motions, ARC interest intake and
read-only reserve book are partial GENERIC components, not
issued owner-specific dues, formal enforcement, authenticated
board voting, issued ARC decisions or posted statutory reserve
activity. The $79/month HOA add-on is still a proposed catalog
price, NOT an active billed subscription or entitled new module.
No further Phase 4.8 Commercial development until HOA generic
features are implemented and verified. Next safely build a
separate applicant/review ARC lifecycle using existing ARC intake,
private evidence and live actor scopes, with no official
approval/denial until authenticated governing and decision
authority. Also remaining: board role/eligibility/approval
configuration, dues payer/charge history/idempotent issuance/
reversal contracts, reserve money workflow subject to central
GL locks. Jurisdiction-specific notice, fines, official votes,
ARC legal decisions and money postings require authenticated
declarations, rules and approved payer/GL policy; settings alone
are not authority.

## CURRENT SESSION UPDATE — 2026-09-28 HOA RESERVE BOOK VERIFIED

**Verified product source** `66aba90457c0d8b9c7d05370ccd10936a1b5a422`.
GitHub Actions `36462256248` SUCCESS all six jobs: backend
**734 passed, 5 deselected, 16375 warnings in 202.82s**,
browser E2E **5 passed, 8 warnings in 14.16s**;
frontend lint/typecheck/build, platform-admin, security and
staging-config passed. CI only; **no local tests run**.
Alembic **c3e5a7b9d1f2 / 139 model tables**, previously
b2d4f6a8c0e1 / 138; PostgreSQL/bootstrap/legacy guard green.
Frozen `docs/` and parity unchanged.

New `hoa_reserve_accounts` is a scoped STAFF-MAPPED/UNVERIFIED
reference from an authorized HOA-property membership to an existing
same-organization cash-like ASSET GL. Optional existing bank display
mapping must actually map to the selected same-org GL and cannot
expose full bank account/routing information. Org-wide GL may only
be assigned once through an org-unique mapping; changing a
historically selected GL is refused. Existing `GLAccount` service
remains responsible for creating actual GL accounts. The reserve
customer panel has a safe, redacted cash-GL/bank DISPLAY selector,
scoped association/property role/release and accounting permissions.
ADMIN/OWNER writes; MANAGER may read mapping only if granted all
required accounting permissions; the org-wide book is denied to
MANAGER even if assigned one property, to prevent other-property
balance disclosure. No tenant/crew/foreign/disabled actor access.
Active recorded mapping is archived when association/property
is unlinked or archived; relinking does not restore prior mapping
without explicit re-recording. Generic notes/attachments cannot
target this sensitive configuration; audits are redacted.

GET `/api/hoa/associations/{id}/reserve-book` uses the verified
central cash-flow `_account_totals` source: actual dated posted
same-org `GLTransaction`/`GLEntry`, including reversals,
with account-wide debit-minus-credit balance and separately
property-tagged book movements. Other/untagged book differences
and gross activity are flagged; a recorded property tag is NOT
legal allocation. This is read-only, never reconciled bank funds,
restricted statutory reserves, verified owner liabilities or
three-way reconciliation. NO `Charge`, `RentInvoice`,
`Lease`, `GLEntry`, `GLTransaction`, bank movement
or locked-period GL mutation was added. Focused regression tests
cover reconciliation caveats, historical date/reversal,
out-of-scope postings, mapping/role/permission/feature/archival
denials, no routing-number disclosure and finance nonmutation.
Existing browser E2E suite now reports 5 passed but is NOT a
dedicated reserve book interaction test.

Remaining requested HOA generic features: staff board-member
role/membership, meeting attendance, minutes and vote preparation;
ARC applicant/review lifecycle; explicit payer-specific dues
contracts, reliable idempotent recurring issuance and authorized
posted GL once governing/payer/accounting authority is verified;
the $79/month HOA add-on pricing and commercial entitlement.
Statutory notice, fine/legal decision and reserve transfer
activation remain genuinely BLOCKED on authentic HOA declarations,
bylaws, applicable jurisdiction, authorized decision makers,
notice/cure and approved dues payer/reserve policies.
User requires completing safe generic HOA workflows before
further Phase 4.8 Commercial batches. Next bounded safe
HOA batch: staff board meeting attendance/vote/prepared minutes
with verified role/meeting access but no legally binding vote.
Do not claim all six modules complete yet.

## CURRENT SESSION UPDATE — 2026-09-28 HOA PROCEDURES + CASES VERIFIED

**Product source** `cc1f4ea5d5040088252b82d16e3f48dd2a219c88`.
Full hosted GitHub Actions **36460477349 SUCCESS all six jobs**:
backend **731 passed, 4 deselected, 16221 warnings in 183.67s**;
browser E2E **4 passed, 4 warnings in 13.33s**;
frontend lint/typecheck/build, platform-admin, security and staging
all passed. **No local tests run.**
New migration `b2d4f6a8c0e1` following `a1c3e5f7b9d0`,
**138 model tables** from 136; PostgreSQL/bootstrap/legacy/schema
guards passed. Frozen `docs/` and parity checklist untouched.

Phase 4.7 HOA generic workflow priority is user-confirmed.
New `hoa_procedure_policies` stores versioned STAFF-CONFIGURED,
UNVERIFIED jurisdiction label/locality, draft notice text,
configurable notice/cure/hearing planning-day counts,
unassessed fine proposal cap and optional independently
UNVERIFIED same-scope PRIVATE HOA evidence reference.
No state-specific deadline, default penalty or legal language
hardcoded. Scoped GET/PUT at
`/api/hoa/associations/{id}/procedure-policy`; live organization,
association/property membership, actor status, ADMIN/OWNER write,
assigned MANAGER read, PROPERTIES.ALL and compliance hybrid release
gate are reused. Document link additionally checks live attachment
feature, same-org/property private active source. Updates increment
policy revision and redact text/amount/location from immutable audit.
Never claim configured rules are valid law or approved authority;
`issuance_enabled=false`. Procedure settings UI is in existing
property HOA Compliance panel. No charge, notice, fine or GL posting.

New `hoa_violation_cases` links ONE staff case to each verified
active same-scope HOA observation. Internal state machine:
OPEN -> NOTICE_DRAFT -> CURE_TRACKING / HEARING_PLANNED ->
FINE_PROPOSED -> RESOLVED -> CLOSED, with a permitted direct staff
resolution path. Server rejects illegal transitions, duplicate
observation linkage, unauthorized manager writes, foreign/inactive
references, missing staff notice language/cure configuration,
proposed fine above staff cap, unknown fields and unsafe status
escalation. Notice and hearing dates must be entered by staff,
and a cure *tentative planning date* is derived only from staff
notice-preparation date plus the configured period. Policy revision
is recorded with transition; audit stores IDs and stage only.
Case list and stage actions live under
`/api/hoa/associations/{id}/staff-cases` and the customer
property Compliance panel. Unlink/archive soft-disables settings
and cases; relink cannot resurrect them. Generic notes/attachments
explicitly deny both new tables.

These are operational STAFF DRAFTS ONLY, not an issued notice,
served notice, legally binding cure deadline, assessed fine,
hearing determination, official resolution, tenant/owner claim,
reserve accounting or booked receivable. No Charge, RentInvoice,
Lease or GL changes. New focused regressions cover positive
transitions, zero finance, scope/permission/release revocation,
source evidence privacy, audit redaction, invalid states,
schema validation and unlink/archive. Existing authenticated E2E
still only 3 general smoke + 1 dedicated HOA evidence browser
test, NOT dedicated procedure/case UI automation.

**Original requested six HOA features remain IN PROGRESS.**
Verified staff association/contact/draft assessment, read-only
recurrence preview, private documents incl. meeting-minutes,
observations, policy settings, internal violation case,
meeting plans and ARC intake do NOT constitute authorized
dues posting, formal enforcement, verified board voting,
official ARC decisions or reserve GL controls. Next bounded
Phase 4.7 tasks: staff board meeting attendance/minutes/vote
preparation, scoped ARC applicant/review tracking, read-only
reserve GL mapping/activity, and explicit HOA dues payer/
authoritative issuance/ledger contracts. Actual legal/finance
activation requires authenticated governing documents,
applicable jurisdiction and authorized actor, payer and GL
contracts. User specified HOA offered as **$79/month add-on**;
module commercial entitlement/pricing activation remains
unimplemented and must not be billed or claimed active.
Do NOT resume Phase 4.8 Commercial until remaining HOA
generic work is completed and tested per user instruction.

## CURRENT SESSION UPDATE — 2026-09-28 HOA DUES PREVIEW + MINUTES VERIFIED

**Source:** `ca663f872b76c8759f93ed5a9d888adb89eb45b7`,
based on the already-green independently implemented commercial
report source `305eff4d5ff92425f781990c45274cf478f37c83`.
**GitHub Actions 36458655420 SUCCESS all six jobs:**
backend **725 passed, 4 deselected, 15981 warnings in 192.16s**;
E2E **4 passed, 4 warnings in 14.50s**; frontend
lint/TypeScript/build, platform-admin, security and staging all
passed. Hosted CI only; **TESTS NOT RUN locally**.
No migration: Alembic **a1c3e5f7b9d0 / 136 model tables**.
Frozen `docs/` and parity checklist unchanged.

User explicitly reversed the prior deferral of generic Phase 4.7 HOA
work: complete generic HOA infrastructure before adding further Phase
4.8 commercial batches. Preserve all verified commercial source already
on this branch; do not repeat or revert it. HOA jurisdiction/legal inputs
remain unavailable, so user-entered settings alone cannot authenticate
governing authority or justify legally operative notices, fines, dues
or reserve postings. Continue safely with generic scopes, rule
configuration, state-machine preparations, document references,
review/audit and read-only GL reporting without inventing law/payers.

This bounded batch expands EXISTING verified HOA assessment planning
rather than rebuilding it. GET
`/api/hoa/associations/{id}/draft-assessments/{proposal_id}/preview`
requires `property_id`, `date_from`, `date_to`, reuses association/
property/actor live permission, manager assignment and compliance
release gate. Dates/amounts are DRAFT ONLY, no payer or legally due date,
with immutable read-only calculations of monthly, quarterly, annual
and one-time schedules. Month-end anchors stay month-end after
short months, including leap days; strictly bounded 5-year query and
finite occurrence cap; archive, cross-property, cross-org and feature/
permission revocation fail closed. No new Charge, RentInvoice,
Lease, GLEntry or GLTransaction writes. Existing customer HOA draft
panel now opens a read-only proposed-date preview.

Existing private HOA governing evidence categories now include
MEETING_MINUTES, alongside declaration/bylaws/rules/ARC/reserve
study, reusing EXISTING private universal property attachment
storage and live HOA access restrictions. They are still
STAFF_SUPPLIED_UNVERIFIED, not official adopted board minutes
or proof of a meeting/vote. No new document bytes/table.
Additional focused regression tests cover EOM/leap, date bounds,
month/year recurrence, actor/feature/archive scope, zero finance
and private meeting-minutes classification. Previous dedicated
HOA browser evidence test remains verified, and 4 E2E passed.

**Still unimplemented in Phase 4.7:** actual owner-specific recurring
dues receivables and immutable GL issuing, board-authenticated
meetings/voting, legally operative violation notices/fines/hearings,
official ARC approval/denial, reviewed reserve account activity
and any automatic legal deadlines. Existing staff-only records
must not be presented as official. NEXT bounded HOA batch:
versioned staff-entered jurisdiction/rule settings and scoped
operational case-state preparation, with tests, no legal issuance
or finance until authenticated authority and payer/GL contracts
are established. This is a genuine unfinished task, not proof
that the requested six modules are complete.

## CURRENT SESSION UPDATE — 2026-09-28 PHASE 4.8 COMMERCIAL REFERENCE VERIFIED

**Last verified product source**: `bfa68575cdd027141be22abeb70affb379fff17e`
(test/schema-guard correction on implementation `5226f9b66da62661d523ea3c30d7ce3c3f6a1969`).
GitHub Actions **36453893096 attempt 2 SUCCESS, all six jobs**:
backend **718 passed, 4 deselected, 15701 warnings in 192.41s**,
authenticated browser **4 passed, 4 warnings in 10.24s**; frontend
lint/TypeScript/production build, platform admin, security and staging
SUCCESS. The first product-source CI `36453309365` FAILED only two
old schema guards expecting 135 tables; its backend ran 716 passed,
2 failed, 4 deselected, frontend/security/platform admin passed,
E2E and staging skipped. Source correction `bfa68575` updated
`test_postgres_smoke.py` and `test_prepare_database.py` to
expected 136 tables/new head. The first corrected-source E2E attempt
timed out navigating from login; 3 other browser tests, backend and
all four other jobs passed. Its FAILED E2E job was re-run once,
passed 4/4, and GitHub marked all six jobs successful. No local
tests run; no unverified results claimed.

**Independent Phase 4.8 C3 first bounded batch**, now verified:
`commercial_lease_abstracts` holds one active staff reference per
existing same-org Lease on an active COMMERCIAL property and unit,
plus optional *separately staff-recorded* rent commencement date.
Schema migrates `f0b2c4d6e8a1` to **`a1c3e5f7b9d0`**;
**136 SQLAlchemy model tables**. The existing Lease.start_date,
Lease.end_date, Lease.status and Unit.unit_number are read in live
scope, never copied into immutable legal certifications. CRUD and
authorized lease selector live under
`/api/properties/{property_id}/commercial-lease-abstracts`;
property Compliance tab renders
`CommercialLeaseAbstractsPanel` only for commercial property type.
Reuses verified hybrid `release.properties.compliance` gate,
PROPERTIES.ALL and separate LEASING permission, live ADMIN/OWNER
write and currently assigned MANAGER read, active organization,
property, unit and same-org active TENANT linkage. Foreign and
unassigned lease/tenant/property probing denied, 250-row caps and
no-store reads. Redacted immutable audit; generic notes/attachments
denylisted. An archived reference never returns without an explicit
staff re-record. Three focused backend regression tests cover
dates versus actual Lease.start_date, CRUD/archive/re-record,
organization/manager/tenant and residential denials, live feature
and permission revocation, generic-target denial and zero
RentInvoice/Charge/GLTransaction mutations. No finance, HOA, lease
signature/activation, charge, CAM/NNN/percentage-rent calculation
or automatic due date behavior added. The staff rent-date entry
is **STAFF_RECORDED_UNVERIFIED**, not sourced/authenticated contract
terms. The four E2E tests remain the prior general smoke + dedicated
HOA evidence test; NO dedicated commercial browser automation yet.
No frozen `docs/` or planning parity changes.

**Precise original roadmap next:** Phase 4.8 C3 Commercial lease
abstract data/reporting only where verified source record exists.
Can extend a read-only, same-scope summary/report of currently
recorded staff references WITHOUT treating dates as operative
billing dates. Actual CAM/NNN formulas, annual reconciliations,
percentage rent, escalations, tenant improvement and lease options
must not become financial/legal actions until underlying executed
commercial leases, tenant cost-sharing/exclusion rules and approved
GL posting/notice workflow are authenticated. Do not infer contract
terms from current Lease.monthly_rent or generic expense fields.

**Original Phase 4.7 C2 HOA remains independently BLOCKED.**
Authenticated CC&Rs/declarations, bylaws/amendments, ARC requirements,
jurisdiction, legally authorized decision makers, assessment payer
and board rules, notice/cure/hearing rules, reserve policy and GL
mapping remain unavailable. No dues, fines, notices, official votes,
ARC decisions or reserve movement may be invented from staff
inventory. This commercial batch does not change verified HOA.
Current handoff-only update is NOT a fresh product test. Re-fetch
the branch HEAD and latest Actions before future edits.

## CURRENT SESSION UPDATE — 2026-09-28 HOA BROWSER REGRESSION VERIFIED

**Product/source HEAD** `8383c592b3ab606fb78147306fae4ec0c2f448de`.
Test introduction `a683725cd4053ff27875787f96fa6414e187ca8c`;
test import correction `60af071e1dba18f991a621f620eda51f62259d48`;
customer dropdown accessibility correction `8383c592b3ab606fb78147306fae4ec0c2f448de`.
**Hosted GitHub Actions 36448961679 SUCCESS, all six jobs**:
backend **715 passed, 4 deselected, 15562 warnings in 186.49s**;
authenticated browser **4 passed, 4 warnings in 8.57s**;
frontend lint/typecheck/build, platform-admin, security and staging
all passed. **No local tests run.** One browser test now specifically
covers the HOA evidence flow; the other three are general smoke.

New disposable-database E2E test records a synthetic association,
uploads a PRIVATE synthetic PDF labelled NOT a governing instrument,
links it as staff-supplied UNVERIFIED evidence, downloads and archives
the reference, and checks zero new Charge/GLTransaction postings.
Existing release gates are temporarily enabled only in the disposable
test and restored afterward. The customer Document and Category
selectors have explicit accessible names; no legal or financial HOA
features were added. No migration: `f0b2c4d6e8a1`, **135 model tables**.
Frozen `docs/` and parity files unchanged. Initial CI `36447994524`
had **one new E2E failure** from the missing accessible select label
(three other E2E passed, remaining five jobs passed); corrected
source CI `36448961679` fully passed. Intermediate run
`36447963624` was cancelled, not passed.

**AUTHENTIC HOA SOURCE BLOCKER REMAINS.** Available conversation/
Library file searches and repository project-document inspection
found planning material, not verified association declaration/CC&Rs,
amendments, bylaws, written rules/ARC terms, specific jurisdiction,
authorized decision makers, assessment/payer authority,
notice/cure/hearing rules, reserve policy or approved GL mapping.
The synthetic E2E PDF is NOT real governing evidence. Phase 4.7
C2 is IN PROGRESS. Do not invent official assessment/fine/notice,
ARC decision, board vote, reserve movement, or Charge/GL posting.
Next exact original dependency is obtaining and reviewing the
actual association/property governing instruments and current
jurisdiction-specific authority; only an independent permitted
original-roadmap task may proceed until that is satisfied.
No verified previous HOA capability was repeated or modified.
Re-fetch branch HEAD and Actions after this docs-only handoff commit;
the verified PRODUCT source/run are recorded above.

## CURRENT SESSION HANDOFF — 2026-09-28 (READ BEFORE HISTORICAL ENTRIES)

This is a **documentation-only handoff update**. No product code, test or
migration was changed in this handoff. Preserve the entire detailed
historical record below and use current GitHub HEAD/CI to supersede stale
"NEXT" subsections embedded in older completed-batch notes.

**Repository:** private `yasirskhan/property-platform`.
**Only branch:** `chatgpt/checkpoint-005-safety`.
**HEAD checked before this handoff:** `ecf8b797b05b2c86234dcb63b004e9c4299d481f`;
this is a handoff-only commit on top of the last verified product source.
After this document commit, HEAD will change: fetch it anew on entry.
**Latest complete GitHub Actions run on prior HEAD:** `36443917977`,
SUCCESS across all six jobs. Backend **715 passed, 3 deselected,
15562 warnings in 127.94s**. Generic authenticated browser E2E
**3 passed in 8.39s**. Frontend, platform-admin, security and
staging-config PASS. This is hosted CI on docs-only HEAD, **not new
product testing**. Last verified **product-source** commit remains
`97ac854cfb7653f95f4e23d173cfb0706362bf8a`, with its own
full green run `36442794100` (715 backend passed / 3 deselected;
3 E2E passed). No local tests run for this handoff.

**Schema:** Alembic head `f0b2c4d6e8a1`, **135 model tables**.
No new migration or parity-status/count update in this handoff.
**Current roadmap point:** Phase 4.7 C2 HOA; earlier phases' completed
batches are verified as detailed in the chronology, but the entirety
of Phase 4.7 C2 is NOT completed. Do not reinterpret past verified
staff-only records as official legal or financial HOA workflows.

**Precise stopping point:** staff-only HOA association/property registry,
contact references, draft assessments, observations, meeting planning,
architectural-interest intake, and a **private governing-document
evidence index + customer UI** are verified. The evidence index merely
points to staff-supplied property attachments and does NOT validate
authenticity, applicability or authority. It does not certify legal
rights or make a filing. There is no verified authentic HOA declaration,
bylaws/amendments, written rules, ARC guidelines or jurisdiction-specific
legal/notice/dues/reserve policy for an actual association in the last
handoff. No new product batch is awaiting CI, and no unverified
implementation should be carried forward from this session.

**Exact next original-roadmap dependency:** verify actual governing
documents and jurisdiction for the specific HOA/property, including
authorized legal actors, notice/cure/hearing requirements, dues payer,
approval and reserve policies. Reconcile any supplied records with
applicable current law *before* implementing official violations,
architecture decisions, board voting, dues/fines, notice delivery,
reserve movements or central-ledger postings. The required genuine
source evidence was not present/verified in the previous source handoff.
Do not infer any of this from unverified staff metadata. Phase 4.6
substantive HUD/LIHTC/HAP/AMI work likewise requires authentic
property/program rules and secure household policy. External Avalara/
IRS filing acceptance and Stripe live acceptance also are not
established by the internal preflight/sandbox work.

**Startup instructions for the next chat — no questions about prior
decisions:**

1. Read the complete repository-root `AI_HANDOFF.md`, confirm HEAD,
   last product commit, and GitHub Actions CI. Treat `ecf8b797` as
   last pre-handoff HEAD, not as a permanent current HEAD. Inspect
   `PROJECT_MASTER.md`, `FEATURE_REGISTRY.md`, `PLAN_GAPS.md`,
   `APPFOLIO_PARITY_CHECKLIST.json`, and `FILE_CATALOG.md`
   read-only as necessary.
2. Check for *actual new authoritative HOA source files* made
   available in the chat, repository, or accessible user-file sources;
   never treat the staff evidence-index entries as verified documents.
   If authentic documents and scope are present, analyze them and
   implement only the legally authorized next Phase 4.7 step with
   regression tests and the established backend authorization/GL
   contracts. If absent, mark the dependent official HOA workflows
   BLOCKED. Do not manufacture rules or repeatedly re-audit completed
   safe drafts. Without asking the user to repeat context, proceed
   only with a genuinely independent next task already authorized
   by the original dependency roadmap, if one exists; otherwise
   report the specific missing evidence as a genuine blocker.
3. Preserve all VERIFIED work; never rebuild it. Existing generic
   authenticated E2E is **not** a dedicated HOA interaction test.
   Read actual current source before edits. Do not touch `main`,
   create a branch, force-push, or change frozen `docs/` files without
   explicit authorization. Do not expose PII/tax secrets or guess
   accounting classifications. Do not use Work mode.
4. For bounded product-code batches include focused regression tests,
   commit to the existing branch, verify **all applicable GitHub
   Actions CI jobs**, fix failures and do not start a new feature while
   CI is red. Never mark an unverified batch COMPLETE. Report real
   test totals; docs-only edits: **TESTS NOT RUN locally**. Update
   the root handoff with new source SHA, CI run, counts, migrations,
   scope, limitations, and the next exact dependency.
5. Continue autonomously across *unblocked* original-roadmap batches
   without permission prompts or hollow progress polling. Stop on a
   genuine missing authoritative source, an unresolved security/legal
   decision, or context limit, after leaving a faithful root handoff.

---

## Verification chronology — don't reimplement

| Batch | Source commits | Last full SUCCESS CI | Evidence |
| --- | --- | --- | --- |
| Phase 4.7 HOA property/association registry + customer Compliance UI | d929d71c50b40849e0f5fa6849b294ca87a4780b, 38dee8344851cac33b1f792e16a529211db86782 | 36425025893 | 692 backend passed / 3 E2E; 129 tables; no HOA financial posting |
| Phase 4.7 HOA private property-document evidence index + UI | 20c982700e1de1efc98921b0ab0f6dfa06c1ba7d, 270e37b1b4e3e77089565fd07b0b411addb3b8c6, 97ac854cfb7653f95f4e23d173cfb0706362bf8a | 36442794100 | 715 backend passed / 3 E2E; 135 tables; staff-supplied unverified only; no legal/accounting action |
| Phase 4.7 HOA contact references + customer UI | 404e6dcccff779c63311018221544d8508d929ff, 8b25ab6240c7cd69c1708d28002f583b526af71c | 36426366891 | 694 backend passed / 3 E2E; 130 tables; no dues or payer designation |
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
| Vendor Directory (registered contact users) | 840a10ef8d4ecb791b24cb2ef09952f09b2c5cc7, 74fc8455d63d6dac52374ea74e3a8668aba58e71 | 36287404716 | 518 backend passed / 3 E2E |
| Vendor Ledger (linked bill register) | fe0f0d44e129cb5dd21e7b6a0ea7d0b434e8fbed | 36300269360 | 522 backend passed / 3 E2E |
| Work Order recorded summary | ecf5d652e0ec9ca2b0428934446e1073b8d6a629 | 36300632574 | 526 backend passed / 3 E2E |
| Accounting Account Totals | 63c9272670d7eb2b4b509fbec70da681bbfd9767 | 36300974942 | 529 backend passed / 3 E2E |
| Accounting Balance Sheet | 0d8f40db185126be26a67db32dbaa9126d02c782 | 36301335972 | 532 backend passed / 3 E2E |
| Bank Account Activity (posted cash-GL book activity) | d90102a7cd1baa0ae71ff0dace48d70f6357c1dc | 36301725230 attempt 2 | 535 backend passed / 3 E2E; first E2E login-navigation timeout retried successfully |
| Bank Account Association (bank-to-GL mapping, no private bank numbers) | 369f1e3f374397ca704219aa8995b5c5a0ffc159, 73873fddb7fcf7aee7115d6de0d145fbb8d55ad9 | 36323294362 | 538 backend passed / 3 E2E |
| Cash Flow (posted bank-mapped book movement, not GAAP-classified) | 0bce280bcd932b5ba1862689d14380ad620697fb, 5305d8d4cd6c80f7ecb5cf893dbbfe100c3f1b0f | 36323986765 | 541 backend passed / 3 E2E |
| Cash Flow 12-Month with year rollover and earliest-date boundary | c1f97d1823c14a268d7f42263b379cb1f801263c, d4b180fafd06f01b10b64c230184357f1a403881, 0718264d01661140e592ad9008117b2c87740d1b | 36324425667 | 545 backend passed / 3 E2E |
| Expense Distribution (posted accrual expense GL) | 67d8630f871e26226e8a280913742a4ae780d4c4 | 36324862669 | 548 backend passed / 3 E2E |
| Income Statement (posted accrual P&L) | c20ef1877bcde6b5c97da302e25e4767a7f07586 | 36326806250 | 551 backend passed / 3 E2E |
| Trust Account Balance (mapped posted cash GL snapshot) | 6c8ced27805a63e0ad715fac8eb46621c3c58c5a, 9bd8e948d68dad97dd409ca11a7e0f95d3bf0443 | 36327401270 | 554 backend passed / 3 E2E |
| Trust Account Detail (posted trust bank GL entries, validated tags) | 28a697be8317f2754262881f0a3ce6efa4693693 | 36327838434 | 557 backend passed / 3 E2E |
| Aged Payables (posted bill current due aging) | 2558a0b11ab73463071de83c83e6d80aa94ecba2, 895857091f918293761e39d6cb9fad12655fb5e0 | 36328376671 | 560 backend passed / 3 E2E; test-only bucket correction |
| Aged Receivables (current rent invoice due aging) | 7af730729cd126b61331caf0b170b7e290eee0c9, d1e2b0501602c33d61a9c901791286eef6a771cd, 545894bbe5f6acbef78a5b37ee58c707f55f5a81 | 36329631501 | 563 backend passed / 3 E2E; test-only second-property bucket correction |
| Bill Detail (posted bill header and verified lines) | bed121f5796aedd3c6985f5bda972e8dded32d45 | 36330083012 | 566 backend passed / 3 E2E |
| Charge Detail (standalone charges incl paid/credit) | cc0d81971de51bf6b7c0b3cb3d0963b085514e8b | 36330600066 | 569 backend passed / 3 E2E |
| Check Register (issue/void, bank-safe) | 1597120b55d45a37d17bc1baddf4c663abaec4b2 | 36331055801 | 572 backend passed / 3 E2E |
| Check Register Detail (recorded allocations) | 9a1dd5dc941bb4a1043b7c367c072f3d4a54d61e, 0494f6a14bc8ee835837d87c5832995609b52c8f | 36332054459 | 575 backend passed / 3 E2E; first registration CI red corrected |
| Deposit Register (recorded receipt grouping) | bdf317cc8e2912061b1544229303aef12a1d3d34 | 36332538763 | 578 backend passed / 3 E2E |
| Expense Register (posted expense GL detail) | fa8ab2e287aea400e6e684205cf5c9a6308ef85a, 7882a5921be2d38601f0a989d8d46552089debe1 | 36333373605 | Verified source; see subsequent section |
| Income Register (posted income GL detail) | 3875ef5af74097f93643d6925eb8b14dfd6ac147 | 36335844931 | 584 backend passed / 3 E2E |
| Journal Entry Register (manual/recurring JE and linked reversal line report) | 329a85e1683f4392568f8d746404bec689c9b788 | 36336312154 | 587 backend passed / 3 E2E |
| Phase 4.5 RUBs shared utility inventory + period completeness | ca07e0af4103b55425b26561641728f521b991ab | 36367397250 | 644 backend passed / 3 E2E; read-only |
| Phase 4.5 RUBs duplicate/overlap review diagnostics | 54ad71a8ab2d2bb8aaeeaad27f97614707b71369 | 36368986607 | 646 backend passed / 3 E2E; no charges or allocations |
| Phase 4.5 trust-interest manual policy readiness backend | ed9d2d97cce994909798c6f413e2ed4b4247c116 | 36369555961 | 649 backend passed / 3 E2E; no GL posting |
| Phase 4.5 bank trust-interest review UI | a2da32a884a16ff9a1fa8adedc3b199810d19e36 | 36370090346 | 650 backend passed / 3 E2E; no interest posting |
| Phase 4.5 positive-pay issue/void preflight | 82844c94fad5d4ef7fd33ac2e0366055953320e1 | 36370656288 | 653 backend passed / 3 E2E; not a bank upload file |
| Phase 4.5 positive-pay customer bank review UI | 6fe873dfa466a33b478dc638c0196bbddb64c9e5 | 36371943676 | 654 backend passed / 3 E2E; read-only, no bank file |
| Phase 4.6 property-level affordable program inventory | 8c20d48deab2ad5fdbe8c323d8409462bce77068 | 36372554518 | 657 backend passed / 3 E2E; no eligibility determination |
| Phase 4.6 staff-recorded CRM program interest register | 67d4d5f15d10b0830a02702b453c68a98e5e9d45 | 36373217097 | 660 backend passed / 3 E2E; no official ranked waitlist |
| Phase 4.6 scoped affordable evidence-readiness checklist | e492a46356bc19a57c55f63fe9ad85a5e0b7d5c8 | 36378052654 | 665 backend passed / 3 E2E; 123 tables |
| Phase 4.6 read-only recorded unit-inspection cross-reference | 87c2eaa9ba5a21f8cc461c92cf46aaf474cd8b46 | 36378605760 | 667 backend passed / 3 E2E; no migration |
| Phase 4.6 BIN syntax normalization and alias collisions | 6ae01cc927264273e5fc8d067da15bd6c45f3faa | 36379842520 | all six jobs success; 2/4-digit year + five-digit sequence; no new migration |
| Phase 4.6 per-building annual Form 8609-A staff reference tracking | 5b520d93aaa7a4307fb5e8533da552aea210cffd | 36383794588 | 681 backend passed / 3 E2E; 127 tables, no IRS filing |
| Phase 4.6 bounded encrypted compliance document rewrap | 40317c96f7b564abce3483b088727c25c53a6b2b | 36384377433 | All six CI jobs success; previous key support, no migration |
| Phase 4.6 scoped rotation readiness preview | 8c5e2a0973b40e414a68f2b8242621324f0e1419, a8adc7dc2f47a40085c1203b38dd2254d778a907 | 36412399420 | 685 backend passed / 3 E2E; read-only, 127 tables |
| Phase 4.6 administrator rotation-readiness UI | 82c8ede338b9030acfd993bbe6888eae7e07ddce | 36413219901 | 686 backend passed / 3 E2E; existing archive UI; no migration |
| Phase 4.6 staff public agency guidance provenance | 3f2d5d4b60f9eb29ced0aa68c182e41fe51df0e1, d5b63d0310b008489cb645e9d1cc74ab16ea4245 | 36414139582 | 688 backend passed / 3 E2E; 127 tables, no agency validation |
| Phase 4.6 restricted encrypted Form 8609 staff-scan archive | fb448c7b283d1e29950fe1290c5d9c70ca25d51f | 36383165892 | 678 backend passed / 3 E2E; dedicated key, 126 tables |
| Phase 4.6 per-building staff Form 8609 reference readiness | a28a4dd6b46757a226ce5e8ecd683341b1e9502b, 8a480d05e21a842b1376b1f4d5e595fe58d687de | 36382487436 | 674 backend passed / 3 E2E; 125 tables; test-only org-admin scope correction |
| Phase 4.6 staff-recorded LIHTC building BIN inventory | 952261b3448400dc5c4d1742e5b4b70538c1e2af | 36379299678 | 670 backend passed / 3 E2E; 124 tables |
| Phase 4 vendor company entity + scoped customer UI | 6e1d0eb730a71d913021b590667123ee047c4858 | 36336927654 | 590 backend passed / 3 E2E |
| Phase 4 vendor insurance lifecycle | 8d2cb6adffbde41282fc77e9e0365b2913410f66, 3de4c938e07fc695cf33eec3b1a7af7fd552e73b, 5dcdd6272bd1e18fe78a0ae2868ef6d110caf2c8 | 36337623891 | 593 backend passed / 3 E2E |
| Phase 4 vendor trade/insurance filters | b40d94b3861809d4cfd5bb563a21bd6a4e524476, 0d32310911be49c9133ba002d19fdfdb9fce7e9a, 87ed9dd1396686065c9596622173297628b2ace2 | 36338819609 | 596 backend passed / 3 E2E |
| Phase 4 explicit Bill Vendor FK and customer picker | 7a8d30733480a31fb476391a923759d92242c043, 5064b41a2f996d783fd25346a476c0a55c1b4a5a | 36339328334 | 599 backend passed / 3 E2E |
| Phase 4 WorkOrder explicit Vendor FK and staff selector | c14e3c7d0a8a08257e9177247c56a7d1093424fd, b90fd3deab170009e5b577f90f085ff98e034630 | 36339917953 | 601 backend passed / 3 E2E |
| Phase 4 independent Contacts directory and customer CRUD | b91ec3c38055272ae97a81a2e16630e87cd98ac7, be1d1f84cac32a136202e8e17651161a63316fd3, a607c8c370fa42f44e897a34a7667dd46c30ce69 | 36340860778 | 604 backend passed / 3 E2E; fixed existing async toggle E2E race |
| Universal Tags (org-scoped definitions and authorized entity links) | 73d4cceae74c44b1fd45afe18368cd7514706039 | 36341415211 | 607 backend passed / 3 E2E |
| Contacts CSV preview, bounded confirmed import and safe export | 0062cc22834129c1998c2320e5f78cad50b9d1c8 | 36347187712 | 612 backend passed / 3 E2E |
| Rental Applications safe applicant drafts, pending-payment submission and scoped staff queue | 864bf2e02a80e1b2a4af58a0bdaa279b5f4f14a9 | 36347804741 | 617 backend passed / 3 E2E |
| Encrypted applicant address and income questionnaire | cbcc52bf710791abd721b8a63dc4bceb10c9b806 | 36348392919 | 623 backend passed / 3 E2E |
| Read-only server-authorized unit application fee quote + applicant UI | 8e751bed878d158501754ae3858f1047e39888ef | 36359893698 | 626 backend passed, 3 deselected / 3 E2E |
| Applicant idempotent fee preparation with immutable unit fee snapshot (no charge) | af94f8afefd853a906c9bf19fc96819eab42c7fc | 36360330500 | 629 backend passed, 3 deselected / 3 E2E |
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
Migration c7e9a1b3d5f2 adds letter_templates; expected 104 tables.
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
No migration in this batch: Alembic c7e9a1b3d5f2, 104 tables.
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
Alembic c7e9a1b3d5f2 / 104 SQLAlchemy tables unchanged.

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
fixture correction. No schema migration; Alembic c7e9a1b3d5f2,
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
staging-config SUCCESS. No migration: Alembic c7e9a1b3d5f2,
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
staging-config passed. No migration, head c7e9a1b3d5f2,
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
staging-config passed. Alembic c7e9a1b3d5f2, 104 tables;
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
No migration; Alembic c7e9a1b3d5f2, 104 tables.
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
No migration; Alembic c7e9a1b3d5f2 / 104 tables.
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
No migration, Alembic c7e9a1b3d5f2 / 104 tables unchanged.
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


## Phase 3.7 Vendor Directory — VERIFIED 2026-09-27

Source 840a10ef8d4ecb791b24cb2ef09952f09b2c5cc7;
scope regression fix 74fc8455d63d6dac52374ea74e3a8668aba58e71.
CI 36287404716 SUCCESS six jobs: 518 passed backend,
3 deselected; authenticated E2E 3 passed in 10.64s.
No migration; head d2f4a6c8e0b1 / 108 tables. Frozen docs unchanged.

STANDARD vendor.directory at /dashboard/reporting/vendor-directory:
recorded active undeleted same-org User.role VENDOR contacts only;
UserRole.VENDOR_CREW, cross-org and free-text Bill payees excluded.
Only ADMIN and OWNER match existing /users contact visibility;
MANAGER is denied (existing manager users API is crew-only).
REPORTING.ALL and PEOPLE.VENDORS, export release gate checked.
Canonical preview no-store, ReportPayload formula-escaped CSV
and server email. No banking/taxpayer or invented mailing data.
Regression tests include foreign vendor-actor denial.

## Phase 3.7 Vendor Ledger — VERIFIED 2026-09-27

Source fe0f0d44e129cb5dd21e7b6a0ea7d0b434e8fbed.
CI 36300269360 SUCCESS six jobs: 522 backend passed,
3 deselected, 8188 warnings in 91.93s; E2E 3 passed
in 10.58s. Frontend lint/typecheck/build, security,
platform-admin, staging-config green. These E2E are generic
authenticated smoke, not vendor-ledger-specific interactions.
No migration: d2f4a6c8e0b1; 108 model tables.
Frozen docs and planning parity left unchanged.

ENHANCED vendor.ledger at
/dashboard/reporting/vendor-ledger, preview
GET /api/reporting/vendor-ledger/preview (no-store).
Only ADMIN current active undeleted same-org with REPORTING.ALL,
PEOPLE.VENDORS, ACCOUNTING.PAYABLES can access. Financial
ledger does not widen OWNER or MANAGER contact/report access.
User.role VENDOR recipient linkage must be an explicit
Bill.payee_user_id; no guessed vendor from Bill.payee_name
or unrelated VENDOR_CREW/tax data. Only active undeleted
registered vendor users and active, unreversed, non-VOID,
undeleted bills are included. Cross-org user links excluded;
foreign vendor_id probes fail closed. Optional vendor_id,
date_from, date_to validated. CSV formula escaping and
server CSV/email recheck report permission plus
release.reporting.export. Five focused assertions across
four focused tests validate role/menu/org scope, metadata
amounts, invalid values, CSV/email, no GL writes, revocation.

IMPORTANT SEMANTIC LIMIT: this is a read-only RECORDED LINKED
BILL AP REGISTER with Bill.amount and Bill.amount_paid metadata,
and their difference. It is NOT the full historical vendor
GL cash/payment ledger. Reversed/void/archived bills, unlinked
payees and detached vendor accounts are excluded. No inference
of tax reportability, accounting postings, cash balances or
historical paid events. Do not misstate these limitations.

NEXT ORIGINAL Section 38 Owner & Vendor item: Work Order.
Reuse REAL WorkOrder / Property / Unit / assignment records
and existing work-order user-visibility semantics. WorkOrder
has tenant_id, description and entry_notes that can be sensitive:
avoid printing entry notes, photographs, private history,
tax/banking or tenant PII. Current reporting should show
recorded work order id, location, title, category, priority,
status and timestamps, with clearly recorded costs only.
Role-scope active org ADMIN/OWNER/MANAGER; manager must
be live-assigned. Enforce REPORTING.ALL and
MAINTENANCE.WORK_ORDERS plus export release gate on
preview/CSV/email; no leak via foreign property_id probe.
No migration expected if only existing WorkOrder rows.

## Phase 3.7 Work Order Report — VERIFIED 2026-09-27

Product source ecf5d652e0ec9ca2b0428934446e1073b8d6a629.
CI 36300632574 SUCCESS six jobs: backend 526 passed,
3 deselected, 8317 warnings in 107.50s; browser E2E
3 passed in 8.74s; frontend lint/typecheck/production
build, platform-admin, security, staging-config all green.
Generic E2E smoke, not dedicated work-order interactions.
No migration: d2f4a6c8e0b1 / 108 tables;
frozen docs and planning parity unchanged.

STANDARD maintenance.work_order links
/dashboard/reporting/work-orders. No-store preview
GET /api/reporting/work-orders/preview and existing server
ReportPayload/CSV/email, release.reporting.export check,
formula-escaped CSV. Current ADMIN/OWNER/MANAGER only
with REPORTING.ALL and MAINTENANCE.WORK_ORDERS.
Managers have active undeleted property assignments,
all roles org scope plus active undeleted Property/Unit.
Foreign/unassigned property-id probes fail closed.
Allowed filters property_id, created date range, current
status. Report uses REAL WorkOrder title/category/priority/
status, property/unit references and recorded timestamp/
total_cost fields ONLY. Excludes tenant ID, description,
entry notes, photo URLs and activity history. Recorded cost
is NOT a posted GL expense or bank payout; no GL writes,
no invented inspection or project activities.
Four focused regression tests cover privacy, org/manager
scope, invalid filters, permission/export revocation,
CSV formula escaping, preview, server CSV/email and
no GL mutations. No unrelated work-order workflow change.

NEXT ORIGINAL Section 38 Accounting reports:
Account Totals, then Balance Sheet, Bank Account Activity,
Bank Account Association, Cash Flow, Cash Flow 12 Month,
then other listed reports. Existing Chart of Accounts,
Trial Balance and per-account General Ledger VERIFIED;
do not rebuild. Account Totals must reflect real posted
org-scoped GL balances/period totals, including reversal
entries, with explicit ACCRUAL vs CASH handling. Do not
infer cash activity or historical snapshots from current
editable fields. Review original document and
reporting_basis/read-only GL services first; add tests
and preserve posted accounting integrity.

## Phase 3.7 Account Totals — VERIFIED 2026-09-27

Source 63c9272670d7eb2b4b509fbec70da681bbfd9767.
All-six-job CI 36300974942 SUCCESS: 529 backend passed,
3 deselected, 8424 warnings in 87.57s; E2E 3 passed
in 9.29s; frontend lint/typecheck/build, platform-admin,
security and staging-config green. E2E is generic
authenticated smoke, not dedicated account-totals UI test.
No migration: d2f4a6c8e0b1 / 108 model tables.
Frozen docs and parity unchanged.

STANDARD accounting.account_totals links
/dashboard/reporting/account-totals; preview
GET /api/reporting/account-totals/preview no-store.
ADMIN only, active/not deleted, REPORTING.ALL plus
ACCOUNTING.GL_ACCOUNTS, export gate on preview/server
CSV/email. Existing ReportPayload and CSV formula escaping.
Accrual-only REAL posted, org-scoped GLTransaction/GLEntry
summed by GLAccount, including reversal entries and
recorded activity on archived GL accounts. Optional
as_of cumulative cutoff; no cutoff means all recorded
transaction dates. Explicit include_zero for no-activity
accounts. Columns: posted debit, posted credit, signed
debit-minus-credit (not a normalized balance sheet).
CASH accounting basis refuses instead of fabricating
cash-basis GL balances. No GL writes or inferred cash.
Three focused tests cover sums/reversal/inactive accounts,
org isolation, role/menu denial, CASH refusal, invalid
params, formula escaping, no GL changes, CSV/email,
release revocation and no-store preview.

NEXT original Section 38: Balance Sheet. Existing
Trial Balance and Account Totals already provide
immutable posted GL totals. Balance Sheet should use
posted journal entries with account types ASSET,
LIABILITY, EQUITY, INCOME, EXPENSE, and explicitly
separate net unclosed income/expenses from equity;
do not infer balance from property market value or
current bill/receipt snapshots. Only ADMIN should
access full-org balance sheet without widening
owner-specific financial visibility. Respect
ACCRUAL/CASH basis and original report gates.
Test that assets = liabilities + equity + unclosed
earnings for balanced postings, including reversals,
and refuse inconsistent books rather than claim
a verified balance. Do NOT silently relabel this
as a GAAP audited financial statement.

## Phase 3.7 Balance Sheet — VERIFIED 2026-09-27

Product source 0d8f40db185126be26a67db32dbaa9126d02c782.
Full CI 36301335972 SUCCESS all six jobs: backend
532 passed, 3 deselected, 8547 warnings in 115.51s;
authenticated browser E2E 3 passed in 10.33s;
frontend lint/typecheck/production build, platform-admin,
security and staging-config SUCCESS. Generic E2E smoke,
not dedicated Balance Sheet interactions.
No migration: Alembic d2f4a6c8e0b1, 108 model tables.
Frozen docs and planning parity unchanged.

ENHANCED accounting.balance_sheet now links
/dashboard/reporting/balance-sheet. No-store preview
GET /api/reporting/balance-sheet/preview.
Reuses VERIFIED build_account_totals for ADMIN,
same-org active actor, REPORTING.ALL,
ACCOUNTING.GL_ACCOUNTS, posted accrual GL and
historical archived GL account balances.
Requires as_of. Assets debit minus credit; liabilities
and equity credit minus debit; explicitly shows
unclosed posted earnings = income minus expense.
Refuses to display if actual posted equation does not
reconcile, unknown account type or CASH basis.
Recorded reversal entries included; no guessed assets,
historical positions, bank values, income closing entries
or new GL postings; marked UNAUDITED.
Shared ReportPayload CSV/email and release.reporting.export.
Three new focused tests cover dated posted equation,
reversal/archived income, cross-org and roles,
unbalanced-book fail closed, CASH denial, CSV formula
escaping, no GL edits, menu/export revocation and
no-store preview/email delivery.

NEXT original Section 38 Banking/Accounting reports:
Bank Account Activity, then Bank Account Association,
Cash Flow, Cash Flow 12-Month. Existing BankAccount
maps bank accounts to GL cash account via gl_account_id.
BankAccount currently stores routing_number and
account_number as plaintext columns (!). DO NOT include
those fields in ANY new report, CSV, email or preview.
Bank feed inbox is not GL; bank reconciliation statement
balances and GL book balances are distinct. Design Bank
Account Activity as explicitly posted GL activity on the
selected org-scoped bank account's mapped GL cash account;
read immutable GLEntry/GLTransaction, include reversal,
and do not infer cleared/settled bank transactions.
Strict ADMIN/ACCOUNTING.BANK_ACCOUNTS and
ACCOUNTING.GL_ACCOUNTS checks. A bank ID must always
be scoped to actor's organization; reject foreign IDs.
Document ACCRUAL-only vs CASH-basis handling explicitly.
No migration if existing GL and bank mapping suffice.

## Phase 3.7 Bank Account Activity — VERIFIED 2026-09-27

Product source d90102a7cd1baa0ae71ff0dace48d70f6357c1dc.
Full source CI 36301725230 attempt 2 SUCCESS all six jobs;
backend 535 passed, 3 deselected, 8687 warnings in 61.26s;
E2E 3 passed in 9.16s; frontend lint/typecheck/build, platform-admin,
security and staging-config green. First attempt failed ONLY transient
E2E login navigation waiting for /dashboard load (2 passed, 1 failed);
one targeted retry succeeded, no product-code edit to auth.
No migration: d2f4a6c8e0b1, 108 model tables. Frozen docs unchanged.

STANDARD accounting.bank_activity links
/dashboard/reporting/bank-activity. No-store preview
GET /api/reporting/bank-activity/preview; shared ReportPayload/
CSV/email/release.reporting.export gate. ADMIN only, same-org
active/not deleted, REPORTING.ALL + ACCOUNTING.BANK_ACCOUNTS +
ACCOUNTING.GL_ACCOUNTS. Requires active in-scope bank_id.
Shows actual dated GLEntry/GLTransaction posted GL movement
on associated org ASSET GL account, opening debit-minus-credit,
running posted cash-book balance, reversal entries, date range.
CASH presentation refused because report is posted ACCRUAL GL.
Never uses bank-feed inbox, clearing/statement balances,
routing_number/account_number, foreign GL accounts or bank
settlement claims. Three focused tests cover date/opening/reversal,
foreign and role/menu/privacy, CSV formula escaping,
no GL edits, preview/email and export gate.

## Phase 3.7 Bank Account Association — VERIFIED 2026-09-27

Product 369f1e3f374397ca704219aa8995b5c5a0ffc159;
focused test isolation correction
73873fddb7fcf7aee7115d6de0d145fbb8d55ad9.
Initial source CI 36323157932 backend 537 passed /
1 failed / 3 deselected: test accidentally left GL permission revoked
before expecting a foreign-bank not-found error. No product
defect: restored test permission state. Final CI 36323294362
SUCCESS all six jobs: 538 backend passed, 3 deselected,
8766 warnings in 115.20s; browser E2E 3 passed in 9.95s;
frontend lint/typecheck/build, security, platform-admin,
staging-config green. The E2E is generic authenticated smoke,
not a dedicated association UI interaction.
No migration: d2f4a6c8e0b1 / 108 model tables.
Frozen docs/ source-of-truth files and parity status unchanged.

STANDARD accounting.bank_association links
/dashboard/reporting/bank-association. No-store preview
GET /api/reporting/bank-association/preview and shared
CSV/email ReportActions; rechecks REPORTING.ALL,
ACCOUNTING.BANK_ACCOUNTS, ACCOUNTING.GL_ACCOUNTS,
release.reporting.export. ADMIN-only, active same-org
with inactive/deleted actor denial, opt bank_id and include_inactive.
BankAccount -> GLAccount recorded mapping ONLY, not
property-to-bank mapping (no such relation on current Property)
and not statement/clearing/balances. Includes recorded
bank display name, type, status, mapped GL account name/number,
GL status and mapping review flag; not routing/account numbers,
ACH info, bank notes, foreign GL metadata. Inconsistent foreign
or missing GL mapping appears UNRESOLVED with no GL details;
non-ASSET mappings flagged for review. Archived bank records
visible only when include_inactive=true, and archived GL status
explicit. CSV formula escaping, invalid-filter and org ID probes,
role/menu revocation, release gate, server preview/CSV/email,
no GL writes covered in 3 focused tests. CASH/ACCRUAL accounting
basis is not applicable to a configuration-only mapping inventory.

NEXT original Section 38 Accounting report: Cash Flow, followed by
Cash Flow 12-Month. Use only real immutable org-scoped
posted GLEntry/GLTransaction and verified BankAccount
-> GLAccount cash mappings; do NOT infer historical external
bank settlements from bank feed, owner/bill snapshots or
routing/account fields. Read GLAccount.include_on_cash_flow
and accounting-basis semantics. Carefully distinguish
bank-mapped GL book cash movement from full classified
GAAP Statement of Cash Flows (the data currently lacks
independent operating/investing/financing classifications).
Bank-to-bank transfers may inflate gross posted inflows
and outflows while net book cash movement cancels.
Preserve role/menu/export checks and explicit limitations;
do not silently claim CASH-basis P&L, audited balances or
bank reconciliation. No migration expected if source GL
is enough. Include opening/ending posted book cash,
reversals, date filters and tests; identify how any unmapped
cash accounts affect completeness.

## Phase 3.7 Cash Flow — VERIFIED 2026-09-27

Source 0bce280bcd932b5ba1862689d14380ad620697fb;
test order correction 5305d8d4cd6c80f7ecb5cf893dbbfe100c3f1b0f.
First source CI 36323735841 FAILED only one test's
bank-record creation-order assumption (540 passed, 1 failed,
3 deselected). Bank rows legitimately sort by display name.
Test-only correction selected rows by bank ID; report code
not changed to satisfy the test. Final CI 36323986765
SUCCESS all six jobs: backend 541 passed, 3 deselected,
8964 warnings in 106.58s; authenticated E2E 3 passed
in 9.24s; frontend lint/typecheck/build, platform-admin,
security, staging-config green. E2E generic smoke; not
dedicated Cash Flow UI interactions.
No migration: Alembic d2f4a6c8e0b1 / 108 model tables.
Frozen docs and planning parity unchanged.

ENHANCED accounting.cash_flow at
/dashboard/reporting/cash-flow, preview
GET /api/reporting/cash-flow/preview no-store;
server ReportPayload, CSV formula escaping, shared
CSV/email ReportActions, release.reporting.export.
Authenticated ADMIN active/not-deleted same-org with
REPORTING.ALL, ACCOUNTING.BANK_ACCOUNTS and
ACCOUNTING.GL_ACCOUNTS. date_from/date_to mandatory,
validated inclusive date range; refused malformed/extra
query keys. Reuses actual same-org BankAccount -> GLAccount
mappings, only ASSET GL accounts marked
include_on_cash_flow=true. Includes archived bank/GL
records when their historical posted activity exists.
Actual org-scoped GLEntry/GLTransaction posted debit
and credit sums, opening before range, period movement,
closing and TOTAL; reversal journal entries included.
Cash-to-cash transfers inflate gross inflows/outflows
but cancel in net. No bank-feed inbox, statement
clearing, transaction settlement, or private bank
account/routing fields in preview, CSV or email.
Unmapped/excluded GL cash accounts are omitted and
explicitly disclosed. Broken foreign/non-ASSET mapping
fails closed. This is posted bank-mapped book-cash
movement, NOT classified GAAP/audited Cash Flows.
Accounting CASH vs ACCRUAL toggle does not magically
translate the immutable posted GL; report label
explicitly states posted book movement in both modes.
No GL writes. Three focused tests cover opening,
net transfer/reversal, missing/excluded mappings,
org/role/menu scope, input validation, basis behavior,
formula escaping, exported/email data and revocation.

NEXT original Section 38: Cash Flow 12-Month.
Reuse VERIFIED build_cash_flow for 12 full calendar
months ending in specified YYYY-MM. Derive per-month
period posted debit/credit, net, opening/closing
and grand totals. Preserve legacy month-end / year
rollover behavior, bank-mapped GL caveat, transfer
double-count gross only, role/menu/export restrictions.
One source implementation edge case: build_cash_flow
currently uses start.fromordinal(start.toordinal()-1)
for opening, which raises for date.min 0001-01-01;
fix safely and add an edge regression test when touching
this service. Do not alter accounting posting.
No database migration expected.

## Phase 3.7 Cash Flow 12-Month — VERIFIED 2026-09-27

Product source c1f97d1823c14a268d7f42263b379cb1f801263c;
pre-CI calendar-index correction d4b180fafd06f01b10b64c230184357f1a403881;
pre-CI fixed-width ancient-year label correction
0718264d01661140e592ad9008117b2c87740d1b.
Original uncorrected source CI 36324381414 and intermediate
36324402432 were cancelled/superseded; no false test results.
Final CI 36324425667 SUCCESS all six jobs: backend
545 passed, 3 deselected, 9224 warnings in 100.89s;
browser E2E 3 passed in 10.97s, frontend lint/typecheck/build,
security, platform admin, staging config GREEN. The E2E tests
are generic authenticated smoke, not dedicated 12-month UI.
No migration: Alembic d2f4a6c8e0b1 /108 model tables.
Frozen docs and planning parity unchanged.

ENHANCED accounting.cash_flow_12_month links
/dashboard/reporting/cash-flow-12-month. No-store preview
GET /api/reporting/cash-flow-12-month/preview;
server canonical ReportPayload, CSV formula escaping, shared
ReportActions CSV/email, release.reporting.export checked;
current user ADMIN, same-org, active/not deleted,
REPORTING.ALL + ACCOUNTING.BANK_ACCOUNTS +
ACCOUNTING.GL_ACCOUNTS repeatedly checked.
Requires strict ending_month YYYY-MM and uses 12 full
calendar months, including year rollover. Delegates each
month to verified build_cash_flow; explicitly posted
bank-mapped GL cash only, archived historical banks and
GL included, source asset/include_on_cash_flow filtering.
Shows opening, posted debit/inflow, posted credit/outflow,
net, ending per month; ending 12-month TOTAL and continuity
guard. Internal cash transfers inflate gross and cancel
net; unmapped and excluded cash GL records omitted;
no private bank account/routing numbers, bank feeds,
cleared settlement, fake classified GAAP statements
or GL mutations. Same posted-book data irrespective
CASH/ACCRUAL presentation toggle.
Fixed build_cash_flow earliest date 0001-01-01 opening
underflow by using < start filter rather than previous
ordinal; focused regression covers date boundary.
Three new 12-month regression tests validate rollover,
old-year carry/transfer/reversal, earliest calendar
edge, org/menu/role isolation, invalid month,
export gate, no-store preview, email, CSV, no GL writes.
One additional underlying cash-flow earliest-date test.

NEXT original Accounting report: Expense Distribution.
Source: org-scoped posted GLEntry / GLTransaction and
actual GLAccount.account_type=EXPENSE. Do not infer bills
or cash payouts from editable summary fields. Clearly
label posted accrual expense by account, reversal
effects, income/cash basis distinction, and categories
limited to genuine GL account metadata. Scope ADMIN,
REPORTING.ALL, ACCOUNTING.GL_ACCOUNTS, export gate;
date range filters, no GL posting, no invented
property allocations. Examine existing Account Totals
and reporting_basis as verified reference.
No migration anticipated. Add focused tests.

## Phase 3.7 Expense Distribution — VERIFIED 2026-09-27

Product source 67d8630f871e26226e8a280913742a4ae780d4c4.
Full CI 36324862669 SUCCESS all six jobs: backend
548 passed, 3 deselected, 9364 warnings in 93.26s;
browser E2E 3 passed in 9.80s; frontend, platform-admin,
security, staging-config all green. Generic authenticated E2E,
not dedicated expense report interactions. No migration;
Alembic d2f4a6c8e0b1 / 108 model tables.
Frozen docs/ and parity unchanged.
STANDARD accounting.expense_distribution links
/dashboard/reporting/expense-distribution, no-store preview
GET /api/reporting/expense-distribution/preview;
server ReportPayload/CSV/email reuse, release.reporting.export
gate, org ADMIN/REPORTING.ALL/ACCOUNTING.GL_ACCOUNTS.
Dated posted GL income classification EXPENSE by chart account,
net signed debits less credits, reversal and archived account
activity, optional include_zero, income/cash-basis excluded.
Share (%) meaningful when net positive; negative share permitted.
CASH reporting basis refuses rather than invent cash-basis expense.
Three focused tests verify real posted sums, date bounds,
reversals, negative and zero, cross-org/role/menu, CSV escaping,
no GL mutation, live authorization and email/export gate.

## Phase 3.7 Income Statement — VERIFIED 2026-09-27

Product commit c20ef1877bcde6b5c97da302e25e4767a7f07586.
CI run 36326806250 SUCCESS all six jobs:
backend 551 passed, 3 deselected, 9553 warnings in 118.92s;
authenticated browser E2E 3 passed in 5.97s;
frontend lint/typecheck/build, platform-admin, security,
staging-config all successful. E2E is generic browser smoke,
not dedicated income statement interactions.
No migration, Alembic d2f4a6c8e0b1 / 108 tables.
No frozen docs/ or parity edits.

ENHANCED accounting.income_statement links
/dashboard/reporting/income-statement.
GET /api/reporting/income-statement/preview is no-store;
existing backend ReportPayload / CSV email and export gate.
Current org ADMIN active/not deleted with REPORTING.ALL
plus ACCOUNTING.GL_ACCOUNTS required in router and builder.
Read-only dated posted GLEntry/GLTransaction grouped by
organization-owned GLAccount types INCOME and EXPENSE,
including archived accounts, credit returns/reversals and
negative signed balances. Revenue = posted credits minus
debits, expense = posted debits minus credits; net = income
minus expense. No invented closing adjustments, property
allocations, bank deposits, bill snapshots, GAAP audit status
or CASH-basis P&L; CASH view refuses. Required inclusive
date_from/date_to, optional include_zero, fail closed on
unknown/invalid filters. Three targeted regression tests
verify date/cross-org scope, account and reversal signs,
negative and zero, access/role/menu and CASH denial,
CSV formula escaping, no GL writes, preview/email/export
release revocation. Output labeled UNAUDITED.

NEXT original Section 38: Trust Account Balance, then Trust
Account Detail. Reuse real org-scoped BankAccount -> GLAccount
cash mappings, Account Totals / Bank Account Activity and
existing trust owner subledger/diagnostics where applicable.
Do not expose plaintext routing/account numbers stored on
BankAccount. Do not conflate posted GL BOOK cash with bank
statement balance, cleared reconciliation balance, tenant
deposit liability or owner subledger. Existing code currently
does not automatically prove three-way reconciliation.
A meaningful trust balance should reflect as-of posted
cash book by configured trust bank accounts, preferably
explicit account type and reconcile STATUS limitations.
Detect invalid/foreign GL mappings and duplicate mapping
double counting; refuse rather than fabricate trust funds.
Admin-only + REPORTING.ALL/BANK_ACCOUNTS/GL_ACCOUNTS,
release.reporting.export, no-store preview, CSV/email.
Document as-of and archived historical postings, future
date and zero balance choices. Tests for org and bank
probes, permissions, historical reversal, no PII, no
GL writes; no migration if verified source data suffices.

## Phase 3.7 Trust Account Balance — VERIFIED 2026-09-27

Product source 6c8ced27805a63e0ad715fac8eb46621c3c58c5a;
test-only assertion correction 9bd8e948d68dad97dd409ca11a7e0f95d3bf0443.
Initial CI 36327229773 FAILED one test: it tried to create
two bank records mapping the same org GL, which the database
rightly rejects under the pre-existing UNIQUE constraint.
Initial backend 553 passed / 1 failed / 3 deselected;
no report-code defect or schema change. The test now
asserts that existing SQL uniqueness and rolls back
before testing foreign-org mapping. Final full
CI 36327401270 SUCCESS all six jobs: backend 554 passed,
3 deselected, 9718 warnings in 115.00s; browser E2E
3 passed in 9.57s; frontend lint/typecheck/production build,
security, platform-admin and staging-config all GREEN.
E2E generic smoke, not dedicated trust report browser interaction.
No migration: Alembic d2f4a6c8e0b1 /108 model tables.
Frozen docs/ and parity status/counts unchanged.

ENHANCED accounting.trust_account_balance links
/dashboard/reporting/trust-account-balance. No-store preview
GET /api/reporting/trust-account-balance/preview;
shared backend ReportPayload, CSV/email ReportActions,
release.reporting.export. Requires org-active ADMIN
REPORTING.ALL, ACCOUNTING.BANK_ACCOUNTS and
ACCOUNTING.GL_ACCOUNTS; backend scope rechecked.
as_of required, optional bank_id. All org bank mappings,
including archived historical records, must point
to unique same-org ASSET GL accounts. Unknown/foreign
bank ID, foreign/nonasset GL or duplicate mapping
fails closed. Reuses verified cash_flow._account_totals
for posted GLEntry/GLTransaction through as_of.
Rows show bank ID, display name/type, archive status,
GL number/status and posted debit-minus-credit
book balance plus total; negative balances possible.
No bank account/routing, ACH, bank feed, bank
statement, cleared reconciliation, owner/tenant
liability, property inferred allocation or GL writes.
Title explicitly says unaudited book balances,
NOT a three-way reconciliation. Three new focused tests
cover date/archived/reversal/zero, duplicate DB
constraint, mapping errors, foreign/roles/menu, no
PII, formula escaping, preview/email/CSV and export
gate revocation. No change to verified Bank Activity.

NEXT Section 38 Trust Account Detail. Implement
entry-level dated book activity for selected
bank-mapped same-org ASSET trust GL; include opening
and running balance, real posted transaction IDs
and recorded owner/property tags only after same-org
verification. Unverified foreign owner/property tags
must not disclose foreign IDs/names; mark unresolved.
Do not infer bank settlement, reconciled statement
balance or owner funds from a GL entry tag.
Reuse trust balance mapping/permissions and verified
cash-flow opening, no sensitive routing/account fields.
Strict as-of/period validation, admin/report/export
gate, no-store preview, existing CSV/email actions.
Regression tests for allocation, archived historical
activity, org isolation, date/reversal, no GL writes.
No migration anticipated.

## Phase 3.7 Trust Account Detail — VERIFIED 2026-09-27

Source 28a697be8317f2754262881f0a3ce6efa4693693;
CI 36327838434 SUCCESS six jobs: backend 557 passed,
3 deselected, 9870 warnings in 81.80s; authenticated
E2E 3 passed in 9.03s; frontend lint/typecheck/build,
platform-admin, security, staging-config all passed.
E2E generic smoke, not dedicated trust detail UI test.
No migration: Alembic d2f4a6c8e0b1 / 108 tables.
Frozen docs/ and parity status/counts unchanged.

ENHANCED accounting.trust_account_detail links
/dashboard/reporting/trust-account-detail, no-store preview
GET /api/reporting/trust-account-detail/preview, shared
ReportPayload/CSV/email and export gate. Requires current
org ADMIN REPORTING.ALL, ACCOUNTING.BANK_ACCOUNTS,
ACCOUNTING.GL_ACCOUNTS; verified trust-account-balance
builder reused for same-org bank-to-ASSET GL mapping,
duplicate mapping guard, archived history and scope.
bank_id, date_from, date_to required. Trust cash GL
entries are posted GLEntry/GLTransaction only, with
opening and running as-of book balance through dates,
real recorded references and reversal entries.
Property/owner tags displayed as IDs only when matched
to same-organization existing Property and OWNER User;
foreign/corrupt IDs withheld, flagged UNVERIFIED.
A recorded GL tag is NOT proof of ownership/allocation,
nor a cleared bank transaction, bank statement,
liability statement or reconciled three-way position.
No bank routing/account numbers or GL writes.
Three new focused regression tests check historical/
archive/foreign tags, period/opening/reversal, org
isolation and roles/menu, foreign GL/bank probes, no PII,
CSV formula escaping, email, preview/no-store, export gate.

NEXT Section 38 Transaction report Aged Payables, then
Aged Receivables. Existing Bill holds mutable
amount_paid and status, payable gl_transaction_id,
due_date (optional), bill_date, status/is_reversed.
No historical as-of unpaid balances can be reconstructed
from live Bill.amount_paid alone; do not label current
recorded outstanding as historic. Aged Payables should
show current recorded open bill liabilities by due date
relative to an explicit reference date and separate
missing/future dates, with real recorded amounts and
safeguards against void/reversed/deleted bills or
unposted drafts. Verify bill workflow/GL pointer and
permissions before coding; reuse existing vendor ledger
and canonical report delivery. Do not alter GL or
infer paid checks/payment dates from mutable summaries.
No migration anticipated. Include org/menu/role, age
boundaries, CSV escape and gating tests.

### Phase 3.7 Aged Payables — VERIFIED 2026-09-27

Source 2558a0b11ab73463071de83c83e6d80aa94ecba2;
test-only 31–60-day assertion correction
895857091f918293761e39d6cb9fad12655fb5e0.
Source CI 36328376671 SUCCESS all six jobs:
backend 560 passed, 3 deselected, 10156 warnings in 119.72s;
browser E2E 3 passed in 8.74s; frontend, security,
platform-admin and staging-config GREEN.
No migration, Alembic d2f4a6c8e0b1 / 108 tables.
Frozen docs and parity not touched. Standard report
transaction.aged_payables at /dashboard/reporting/aged-payables
with server /api/reporting/aged-payables/preview and existing
CSV/email renderer. Current recorded unpaid posted Bill metadata
only; due-date 1–30/31–60/61–90/91+ buckets plus future,
due-today and missing dates; no historical snapshot.
Excludes void/reversed/deleted/unposted bills and fails
on bad status/amounts/foreign payable GL, enforces ADMIN,
REPORTING.ALL, ACCOUNTING.PAYABLES, ACCRUAL and
release.reporting.export. No GL writes or private bank details.
Three focused tests cover arithmetic, org/role, probes,
CSV escaping, preview/email/revocation. Earlier superseded
CI runs 36328190941 and 36328319776 were CANCELLED, not
proof of a product regression.

## Phase 3.7 Aged Receivables — VERIFIED 2026-09-27

Source 7af730729cd126b61331caf0b170b7e290eee0c9;
pre-CI preview summary-count correction
d1e2b0501602c33d61a9c901791286eef6a771cd;
test-only 1–30-day second-property bucket correction
545894bbe5f6acbef78a5b37ee58c707f55f5a81.
Initial source CI 36329370057 FAILED only a focused
test expectation: it omitted a legitimate $250
second-property invoice from 1–30 bucket. Backend
562 passed / 1 failed / 3 deselected. Product
logic left unchanged; corrected expected $400.
Final CI 36329631501 SUCCESS all six jobs:
backend 563 passed, 3 deselected, 10449 warnings in 82.71s;
E2E 3 passed in 8.37s, frontend lint/typecheck/build,
platform-admin, security and staging-config GREEN.
Browser E2E is generic authenticated smoke, not dedicated
receivables UI interaction. No migration; Alembic
d2f4a6c8e0b1 / 108 model tables. Frozen docs/parity unchanged.

STANDARD transaction.aged_receivables links
/dashboard/reporting/aged-receivables. Server
GET /api/reporting/aged-receivables/preview returns
no-store; shared ReportPayload and CSV/email gated by
release.reporting.export. Builder requires current active
org ADMIN or assigned MANAGER, REPORTING.ALL and LEASING.
Only active same-org tenant/units/properties, valid manager
property assignments; tenant_id/property_id probes fail
closed. Invoice status VOID excluded, fully paid excluded;
bad paid/rent/late-fee metadata refuses. Uses actual
RentInvoice due_date and current mutable amount_paid,
with separate 1–30/31–60/61–90/91+ age, future and
due-today sums. No historic "as-of" inference. No posted
GL AR assertion and no standalone Charge balances;
those might overlap invoice late fees and are kept
in separately verified Unpaid Charges reporting. No
GL/payment writes. Focused regressions cover boundaries,
partial/paid, org/assignment/role, invalid parameter and
corrupt metadata, CSV formula escaping, preview/email,
release and permission revocation.

NEXT original Transaction report: Bill Detail, followed
by Charge Detail. Inspect pre-existing verified Bill
detail modal, BillLine, GL posting and vendor ledger.
Implement scoped posted Bill header + recorded line
breakdown (do not pretend payment history or infer
foreign-account/property data). Reuse canonical report
catalog, server ReportPayload/CSV/email, strict access
and no-store preview, focused tests and full six-job CI.
Do NOT write GL or reconstruct historic payment snapshots.

## Phase 3.7 Bill Detail — VERIFIED 2026-09-27

Source bed121f5796aedd3c6985f5bda972e8dded32d45.
CI 36330083012 SUCCESS all six jobs: backend 566 passed,
3 deselected, 10632 warnings in 121.02s; browser
E2E 3 passed in 9.06s; frontend lint/typecheck/build,
platform-admin, security and staging-config green.
Browser E2E is the existing authenticated smoke, not
Bill Detail screen-specific automation. No migration:
Alembic d2f4a6c8e0b1 /108 model tables.
Frozen docs/ and planning parity unchanged.

STANDARD transaction.bill_detail links
/dashboard/reporting/bill-detail, no-store preview GET
/api/reporting/bill-detail/preview. Existing server
ReportPayload/CSV/email reuse + release.reporting.export
gate. ADMIN current active same-org user must have
REPORTING.ALL, ACCOUNTING.PAYABLES, ACCOUNTING.GL_ACCOUNTS.
Bill ID and inclusive bill_date filter optional; unknown,
foreign and non-posted bill IDs fail closed; at most 5000.
Source posted Bill linked to same-org original BILL
GLTransaction, excluding reversed GL/bill, void,
inactive and deleted. Same-org LIABILITY payable
GL and each BillLine same-org GL account checked,
line amounts positive and sum equals parent Bill.amount.
One BILL header displays current mutable status/amount/
paid/unpaid and separate LINE rows show recorded GL
account, line description/amount without repeating
bill total on every line. No owner/property identifiers,
private bank info or invented payment dates/checks,
no historic payable reconstruction and no GL writes.
3 focused regression tests: verified line split,
invalid GL/amount/foreign bill, roles/menu,
CSV formula escape, preview/email and export gate.
No further Bill Detail changes needed absent new evidence.

NEXT original Transaction report: Charge Detail,
then Check Register. Reuse verified Charge, tenant
unpaid charge and tenant ledger models/scoping.
Include PAID and outstanding standalone Charge records,
but never combine RentInvoice with Charge as its late fee
may already be in invoice. Charge.amount_paid and
is_paid are mutable current recorded metadata, not
GL-settled historic payments. In particular, Charge
has NO documented posted GLTransaction pointer, so
cannot claim GL-posted AR. Respect current access,
same-org tenant/properties, active assignment,
unallocated admin-only records and same-org GL code.
Use shared report delivery, no-store preview,
formula escape, regression tests and six-job CI;
do NOT rebuild existing Unpaid Charges report.

## Phase 3.7 Charge Detail — VERIFIED 2026-09-27

Source cc0d81971de51bf6b7c0b3cb3d0963b085514e8b.
CI 36330600066 SUCCESS all six jobs: backend 569 passed,
3 deselected, 10772 warnings in 97.78s; browser E2E
3 passed in 9.19s; frontend lint/typecheck/build,
platform-admin, security and staging-config green.
E2E only existing generic smoke, not dedicated Charge
Detail UI flow. Alembic d2f4a6c8e0b1/108 tables;
no migration, frozen docs/ and parity unchanged.
Previous Bill Detail handoff-only run 36330510399 may
have been superseded by this source push; do not claim
green without its own results.

STANDARD transaction.charge_detail at
/dashboard/reporting/charge-detail, authenticated no-store
GET /api/reporting/charge-detail/preview, shared server
ReportPayload/CSV/email with release.reporting.export gate.
Organization ADMIN or assigned MANAGER, active/current,
REPORTING.ALL, LEASING, ACCOUNTING.CHARGES,
ACCOUNTING.GL_ACCOUNTS. Filters charge_id, tenant_id,
property_id, charge_date inclusive range; max 5000
rows and foreign/unauthorized reference fail-closed.
Uses standalone Charge, User(TENANT), Property,
PropertyAssignment, Unit and same-org INCOME GLAccount.
Propertyless charges admin only; inactive/deleted and
foreign records excluded. Full paid, unpaid and recorded
overpay/credit included with warning when is_paid flag
disagrees with computed current balance; no made-up
credit settlement. RentInvoice intentionally excluded
as may double-count late fees. No GL posted AR assertion,
no historic balance or payment inference and no GL writes.
Three focused tests cover full/partial/credit arithmetic,
unallocated/assigned/foreign/invalid GL scoping, roles,
CSV escape, preview/email, revocation and export gating.

NEXT: original Transaction Check Register followed by
Check Register Detail. Reuse existing Check/
CheckBillAllocation, Check issue/void, BankAccount
and GLTransaction. Only same-org original CHECK GL
with correct void reversal state; do NOT expose
BankAccount.account_number or routing_number,
do not pretend issued checks have cleared bank,
and do not repeat check total on child allocations.
Preserve permissions and release gate; no writes.


## Phase 3.7 Check Register and Check Register Detail — VERIFIED 2026-09-27

Check Register source 1597120b55d45a37d17bc1baddf4c663abaec4b2,
CI 36331055801 SUCCESS all six jobs, backend 572 passed,
3 deselected, 10902 warnings in 122.35s; E2E 3 passed in 8.46s.
No migration, head d2f4a6c8e0b1 /108 model tables.

Check Register Detail source 9a1dd5dc941bb4a1043b7c367c072f3d4a54d61e,
authorization/catalog/delivery registration fix
0494f6a14bc8ee835837d87c5832995609b52c8f.
Initial run 36331816602 FAILED three new focused tests because
the initial tree omitted three modified existing registration files;
backend 572 passed, 3 failed, 3 deselected, 11004 warnings.
Corrective commit includes reporting router, catalog and dispatcher.
Final source CI 36332054459 SUCCESS six jobs; backend 575 passed,
3 deselected, 11004 warnings in 93.50s; E2E 3 passed in
10.62s, frontend/platform-admin/security/staging all green.
E2E remains the generic authenticated browser smoke, not
dedicated interaction coverage. No schema change, Alembic
d2f4a6c8e0b1/108 tables, frozen docs/parity unchanged.

STANDARD transaction.check_register is at
/dashboard/reporting/check-register; GET
/api/reporting/check-register/preview; existing server CSV/email
with export gate. Only active org ADMIN, REPORTING.ALL,
ACCOUNTING.BANK_ACCOUNTS + ACCOUNTING.PAYABLES. Validates
same-org BankAccount -> ASSET GL and original CHECK GLTransaction,
verified status and VOID reversal marker, capped filters, no-store;
exports bank display name only (never routing/account number).
An ISSUED check is NOT a cleared check; no bank settlement inference.

STANDARD transaction.check_register_detail is at
/dashboard/reporting/check-register-detail; GET
/api/reporting/check-register-detail/preview; existing
ReportPayload/CSV/email, release.reporting.export and no-store.
Reuses verified check-register filters/issue/void/authorization
and excludes foreign bills/invalid allocations. CHECK row has one
nominal total, ALLOCATION rows show bill ID/number and their
recorded amounts without repeating nominal total. Checks
allocation sum agrees with nominal check amount, refuses
negative/overprecision and cross-org bill ID. No GL writes,
bank secrets or historic bill payment reconstruction.
Three focused regression tests cover sums/invalid/foreign
allocation, role/filter protections, CSV formula escaping,
preview/email and live gate/permission revocation. No new
schema or parallel reporting implementation.

NEXT original Transaction report Deposit Register. Inspect
existing Deposit/DepositLine/Receipt/deposit_posting.
Deposits group existing posted receipts; deposits DO NOT post
new GL transactions or prove external bank settlement.
Deposit.bank_gl_account_id points to a GL account, not directly
to a BankAccount. Do not accidentally claim bank reconciliation,
double count posted receipts or expose routing/account numbers.
Validate same-org GL and included receipt/line org scope and
recorded totals; historical reversal/archived statuses must
be explicit. No mutation, report/admin/export gates, no-store
preview, CSV/email, focused tests. Only after six-job CI green,
continue Expense Register and Income Register in plan order.

## Phase 3.7 Deposit Register — VERIFIED 2026-09-27

Product commit bdf317cc8e2912061b1544229303aef12a1d3d34.
Full CI 36332538763 SUCCESS all six jobs: backend 578 passed,
3 deselected, 11124 warnings in 124.44s; authenticated browser E2E
3 passed in 8.76s; frontend lint/typecheck/build, security,
platform-admin and staging-config all passed.
No migration; Alembic d2f4a6c8e0b1 / 108 model tables.
Frozen docs/ and parity unchanged; generic E2E smoke only.

STANDARD transaction.deposit_register at
/dashboard/reporting/deposit-register with authenticated
GET /api/reporting/deposit-register/preview (no-store), shared
ReportPayload/CSV/email and release.reporting.export gate.
Requires active org ADMIN, REPORTING.ALL, ACCOUNTING.DEPOSITS,
ACCOUNTING.GL_ACCOUNTS. Optional deposit_id, bank_gl_account_id
(the cash GL, NOT physical bank ID), date range; 5000 row cap.
Verifies org ownership/ASSET cash GL, DepositLine organization,
unique same-org original posted Receipt and RECEIPT GLTransaction,
receipt reversals, positive amounts and sum against recorded
Deposit.total. Output only recorded deposit grouping, date,
number, cash GL display label, count, flagged reversed receipts
and nominal amount; never new GL cash, cleared banking,
reconciliation or routing/account numbers. No GL writes.
Three focused tests cover reversed receipt counts, org/amount/
GL/line probes, formula-escaped CSV, preview/email and gate/
role revocation. Existing deposit_posting and receipt_posting
untouched. Do not repeat.

NEXT Expense Register then Income Register in original Section 38.
Inspect posted accrual GLEntry/GLTransaction and GLAccount
EXPENSE/INCOME. PropertyExpense metadata is not a verified
posted GL source. Avoid presenting bills/bank cash as posted
expense accrual, double counting journal lines or inventing
cash-basis classifications. Reuse expense_distribution and
reporting_basis, admin org and GL permissions, no-store,
canonical ReportPayload/CSV/email, export gate and tests.

## Phase 3.7 Income Register — VERIFIED 2026-09-27

Source 3875ef5af74097f93643d6925eb8b14dfd6ac147.
Full GitHub CI 36335844931 SUCCESS all six jobs:
backend 584 passed, 3 deselected, 11380 warnings in 95.99s;
authenticated browser E2E 3 passed in 9.44s; frontend
lint/typecheck/build, platform admin, security and staging-config
all passed. Browser suite is generic authenticated smoke, not
dedicated Income Register page E2E. No migration; Alembic
d2f4a6c8e0b1 / 108 expected tables. Frozen docs and planning
parity unchanged.

STANDARD transaction.income_register links
/dashboard/reporting/income-register; authenticated no-store
GET /api/reporting/income-register/preview. Existing
ReportPayload, shared CSV/email ReportActions and
release.reporting.export gating reused. Only active same-org
ADMIN with REPORTING.ALL and ACCOUNTING.GL_ACCOUNTS.
ACCRUAL basis required; CASH basis refused rather than invent
cash-flow income. Actual dated posted GLTransaction/GLEntry
joined to same-org INCOME GLAccount, including archived
accounts, income credits, debit returns and reversal lines.
Signed net income = credits less debits. Strict date range,
optional account_id with org/type check; 5000 entry cap,
malformed/extra filters fail closed. Rows include real
transaction and entry IDs, recorded reference and description;
no receipt/bank clearing, invoice status or historic cash
claims; no GL writes. Three focused tests cover signed entries,
returns/archived history and org isolation, permission/release
revocation, CSV escaping, preview/email, invalid filters and
basis refusal.

NEXT original Section 38: Journal Entry Register. Inspect
existing /api/accounting/journal-entries and gl_posting,
GLTransaction.transaction_type JOURNAL_ENTRY and its
REVERSAL semantics. Original manual JE records may be
marked is_reversed=True while their reversal transaction
has type REVERSAL and reversal_of_id. Do not silently omit
historically posted originals or count reversals from
unrelated source types. Show recorded manual/recurring
journal metadata and true reversal markers, verify
balanced posted GLEntry lines, org-owned GL accounts,
date/role scope and no GL mutations. No new schema expected.
Preserve canonical report delivery, export gate, no-store
preview, formula escaping, focused tests and full six-job CI.

## Phase 3.7 Journal Entry Register — VERIFIED 2026-09-27

Source commit 329a85e1683f4392568f8d746404bec689c9b788.
GitHub Actions 36336312154 SUCCESS all six jobs:
backend 587 passed, 3 deselected, 11529 warnings in 126.65s;
authenticated browser E2E 3 passed in 10.07s; frontend
lint/typecheck/build, platform-admin, security and staging-config
passed. E2E generic smoke only, not dedicated Journal Register UI.
No migration; Alembic d2f4a6c8e0b1, 108 model tables.
Frozen docs and planning parity unchanged.

STANDARD transaction.journal_entry_register at
/dashboard/reporting/journal-entry-register, no-store preview
GET /api/reporting/journal-entry-register/preview; canonical
ReportPayload, shared CSV/email and release.reporting.export.
Active same-org ADMIN with REPORTING.ALL,
ACCOUNTING.JOURNAL_ENTRIES and ACCOUNTING.GL_ACCOUNTS.
Only GLTransaction type JOURNAL_ENTRY, plus REVERSAL whose
reversal_of_id points to same-org original JOURNAL_ENTRY.
Original journal marked is_reversed stays visible, and linked
REVERSAL lines show original ID and reversal status. Other GL
source types and unrelated reversals excluded. Validates
same-org GLEntry/GLAccount, positive single-sided debit/credit,
per-transaction balanced total. Date interval required;
optional transaction_id and include_reversals, 5000 txn/line
bounds, fail-closed on invalid/foreign references.
Posted debit/credit amounts unchanged by CASH/ACCRUAL
presentation setting, no bank clearing/GL mutation.
Three focused tests validate originals and linked reversals,
nonjournal exclusion, signed line arithmetic, archived GL,
org/role/menu, foreign account tampering, invalid filters,
CSV formula escaping, preview/email and live export gate.

Original Section 38 reports and customer-side prerequisites
are now verified except that actual external 1099 sandbox
acceptance, production filing, IRS receipt/corrections and
recipient copies remain provider/credential dependent.
Do not claim regulatory/operational 1099 filing complete;
vendor/report preparation features are not the same as
externally acknowledged 1099 forms.

NEXT original master Phase 4 starts with Full Vendor entity.
Current app has UserRole.VENDOR contact records but Bill.payee_name
remains free text; no durable Vendor model. Preserve verified
vendor directory/ledger and tax profiles; do not treat vendor
contact users as a fully implemented vendor company.
Inspect User, Bill, WorkOrder, access architecture and manual
Alembic migration patterns. Start bounded org-scoped Vendor
entity (company, contacts/address/trade, operational state)
with focused isolation, access and migration tests, then
continue insurance expiry and the planned real Vendor picker.
Do not auto-link historical free-text Bill payees by name or
migrate plaintext tax IDs. User only authorized narrow 1099
frozen-doc amendments; all other docs/ remain frozen.

## Phase 4 Vendor companies — VERIFIED 2026-09-27

Source 6e1d0eb730a71d913021b590667123ee047c4858.
GitHub CI 36336927654 SUCCESS six jobs: backend
590 passed, 3 deselected, 11598 warnings in 114.79s;
authenticated E2E 3 passed in 9.67s; frontend
lint/typecheck/build, security, platform-admin and staging
passed. Generic E2E only, no dedicated Vendor page browser E2E.
Manual Alembic e3f5a7b9c1d2 adds vendors table;
109 expected model tables; PostgreSQL/bootstrap/legacy
schema tests passed. Frozen docs/ and parity unchanged.

New app/models/vendor.py is a real organization-owned
vendor COMPANY distinct from UserRole.VENDOR portal/contact.
Optional contact_user_id must point to active same-org
role VENDOR user. Company name, trade, business email,
phone and address stored; NO tax ID fields.
Backend GET/POST/PATCH/DELETE/restore
/api/vendors, org role/menu PEOPLE.VENDORS.
Active same-org ADMIN may create/change/deactivate/
restore, OWNER may read/list, other customer roles
denied. Inactive/deleted actor denied, foreign IDs
404, live vendor-contact link validated fail closed.
Soft deactivation, list search/inactive filter, append-only
change audit, no-store reads, 1000-row bound. Frontend
/dashboard/vendors is already linked by verified sidebar
PEOPLE.VENDORS menu config; create/edit/contact link,
search/list/soft deactivate/restore.
No automatic Bill.payee_name mapping, no WorkOrder
assignment changes, no tax profile/1099 mapping;
verified vendor directory and ledger unchanged.
Three focused tests prove same-org CRUD, audit,
role/menu/contact/probe checks, archived lifecycle
and validation, no bill mutation. No other product
feature was represented as completed.

NEXT original Phase 4: Vendor insurance with recorded
coverage, policy number, carrier and expiration.
Inspect existing PropertyInsurance (different scope):
do NOT create expenses or GL entries from vendor
insurance premium metadata. Use org-owned Vendor model,
admin PEOPLE.VENDORS, verified record isolation and
authenticated document handling. Then vendor list
insurance-expiry filters, planned bill/work-order real
Vendor pickers, owner Vendor 1099 payer flag in dependency
order. Do not reuse general attachments for W-9s or
claim tax profile automatically linked to vendor
company; existing tax profiles still target UserRole.VENDOR.

## Phase 4 Vendor directory filters — VERIFIED 2026-09-27

Backend/service/tests commit b40d94b3861809d4cfd5bb563a21bd6a4e524476;
customer vendors page UI commit 0d32310911be49c9133ba002d19fdfdb9fce7e9a;
date.max overflow fix in existing vendor_insurance._status
87ed9dd1396686065c9596622173297628b2ace2.
Final six-job GitHub Actions run 36338819609 SUCCESS:
backend 596 passed, 3 deselected, 11742 warnings in 71.83s;
authenticated E2E 3 passed in 8.91s; frontend lint/typecheck/
build, security, platform-admin, staging-config all green.
E2E remains generic authenticated smoke, not dedicated vendor filter
browser interactions. Earlier superseded runs were CANCELLED, not
passed. No migration in the FILTER batch; existing vendor-insurance migration
head a9b1c3d5e7f0 / 110 tables unchanged.
Frozen docs/ and parity not edited.

Org-owned Vendor company list GET /api/vendors now supports exact
case-insensitive trade, insurance_status and optional as_of date,
composable with existing company search/include_inactive. Status
uses ACTIVE policies only and reuses verified vendor_insurance._status
(expired, within 30 days inclusive, upcoming, current, missing).
When multiple active policies exist, precedence EXPIRED >
EXPIRING_30_DAYS > UPCOMING > CURRENT; this is a review/alert
priority, not verification of coverage. No active policy is MISSING.
No historic snapshots are persisted, as_of is only a date-relative
interpretation of CURRENT recorded policy metadata. Archived
insurance excluded from status. SQL EXISTS predicates are correlated
to same-org Vendor and only after org ADMIN/OWNER + PEOPLE.VENDORS
authorization. Insurance metadata loaded in one scoped query
for at most 1000 vendors, guard 10000 active policies; no policy
numbers, carrier secrets, W-9s, bank data, GL writes or bills modified.
VendorOut directory summary includes status and nearest relevant
expiration, single-vendor detail otherwise unchanged.
Customer /dashboard/vendors adds trade, status and reference date
controls plus at-a-glance status/expiration per company.
Three regression tests validate status boundary, mixed policies,
foreign org, role/menu revocation, no-store, no GL posting and
invalid oversized trade filter.

NEXT original Phase 4: real Vendor link on Bills, then WorkOrder
vendor assignment/picker. Bill currently retains original free-text
payee_name and optional payee_user_id. Do NOT auto-match historic
payees by text, conflate Vendor company with UserRole.VENDOR, or
change GL amounts/history. Introduce nullable vendor_id FK, validate
active same-org Vendor on new bills, persist in same atomic posting,
retain original immutable payee_name snapshot, render choice in bill
creation UI, inspect existing listing and recurring/reversal behavior.
Do not silently mutate old rows; include migration guards, scoped
tests and full six-job CI. Then work order vendor link independently
from assigned_to_id crew user; preserve existing crew assignment
lifecycle and property access authorization.

## Phase 4 Bill company picker and link — VERIFIED 2026-09-27

Source/migration/regression tests:
7a8d30733480a31fb476391a923759d92242c043.
Customer New Bill picker:
5064b41a2f996d783fd25346a476c0a55c1b4a5a.
CI 36339328334 SUCCESS six jobs, 599 backend passed,
3 deselected, 11821 warnings in 131.97s; authenticated
browser E2E 3 passed in 9.70s; frontend/platform admin/
security/staging green. Existing browser E2E generic smoke,
not new-Bill vendor selector-specific test.
Superseded source-only run 36339303676 was cancelled;
no invented test result.
Manual Alembic migration b0c2d4e6f8a1 adds nullable Bills
vendor_id -> vendors.id ON DELETE SET NULL with index.
Model tables remain 110. PostgreSQL/bootstrap/legacy path
and migration head guards succeeded. No data backfill,
old Bills.vendor_id remains NULL. No frozen docs/ or
planning parity mutations.

BillCreateIn.vendor_id optional positive integer and
BillOut.vendor_id optional. New /dashboard/accounting/bills/new
picker lists only authorized active vendor companies via
GET /api/vendors. If user lacks PEOPLE.VENDORS or list
is unavailable, existing manual-payee entry continues.
Choosing a company sets/stops edits of payee_name
snapshot, and sends explicit vendor_id. Backend
post_bill validates active/not-deleted, same-org
Vendor and active/not-deleted ADMIN/OWNER user
with PEOPLE.VENDORS permission BEFORE original GL
posting; payee_name must match current selected
vendor company to avoid silently linking an unrelated
payee. Foreign/inactive/name-mismatch or permission
revocation fails before GL writes. No inference
from Bill.payee_name, no auto-link on old entries,
no UserRole.VENDOR contact substitution.
Bill vendor_id is recorded in same original bill
write; original paid expense/AP and amount posting
are untouched. Original payee_name remains a
historical snapshot if Vendor company is later
renamed/deactivated. Reversal mirror inherits vendor_id
without revalidating deactivated historic company.
Three focused tests cover original and reversal,
cross-org/inactive/name/permission fail closed before
GL, manual payee compatibility and no implicit matching.
No tax-profile links, bank info or special vendor
payment calculation introduced.

NEXT Phase 4: a real WorkOrder vendor company link/picker,
separate from assigned_to_id crew user and existing
work-order status/crew assignment. Inspect current
WorkOrder/WorkOrderUpdate schemas, router authorization,
UI route availability and company list permission.
Do not introduce vendors as UserRole.CREW or alter
existing crew assignment history. Restrict assignment
to authorized same-org staff with PEOPLE.VENDORS;
validate active same-org Vendor, preserve property/org
scope. Existing app may lack a customer WorkOrder
management screen; do not call a backend-only link a
completed user-facing picker. Include relevant safe
customer selection interface, focused regression
tests and migration guards. No accounting/GL writes.
Then return to original Phase 4 Contacts/Tags and
other tasks in dependency order.

## Phase 4 WorkOrder vendor company association — VERIFIED 2026-09-27

Backend model, scoped staff GET/POST, migration and regression tests:
c14e3c7d0a8a08257e9177247c56a7d1093424fd.
Authenticated staff vendor picker and link from vendor directory:
b90fd3deab170009e5b577f90f085ff98e034630.
Final GitHub Actions run 36339917953 SUCCESS all six jobs;
backend 601 passed, 3 deselected, 11898 warnings in 72.39s;
browser E2E 3 passed in 8.96s; frontend lint/typecheck/
production build, platform admin, security, staging all passed.
Browser E2E is existing authenticated smoke, not a
dedicated vendor-selector click test. Earlier superseded CI
run 36339883696 was not represented as the final green run.
Migration c1d3e5f7a9b0 adds nullable work_orders.vendor_id
-> vendors.id ON DELETE SET NULL, index; 110 model tables
unchanged. No historical auto-link, financial posting,
crew assignment or status mutation. No frozen docs or
parity mutations.

Existing /work-orders routes and crew assigned_to_id
lifecycle preserved exactly. Separate admin/owner-only
GET /work-orders/vendor-assignments and
POST /work-orders/{id}/vendor require active same-org
actor, PEOPLE.VENDORS plus MAINTENANCE.WORK_ORDERS
menu permission. Only active, nondeleted, same-org
company may be linked; cross-org WorkOrder/vendor IDs
fail closed. Finished CLOSED/CANCELLED WorkOrders
cannot change link. All writes log WorkOrderUpdate
and an immutable audit event in same transaction;
idempotent repeat selection does not duplicate audit.
Response deliberately excludes tenant name, entry
instructions, photographs and vendor private details.
Customer /dashboard/work-orders/vendor-assignments
lists scoped work orders and the authorized active
company selector, with explicit unlink; also linked
from /dashboard/vendors. The picker does NOT dispatch
a vendor, grant portal access, generate contracts,
or alter crew assignments, costs or GL.
Two regression tests prove link/unlink, audit,
tenant/manager denial, foreign company/workorder
denial, archived/finished/permission revocation,
inactive actor and GL non-mutation.

NEXT original plan Phase 4 People — Contacts / Tags:
- Contacts (non-vendor, non-tenant), then Universal
  Tags, then People import/export.
- Current repo has User accounts with role TENANT,
  OWNER, VENDOR, etc., and distinct Vendor COMPANY.
  Contacts must be an org-owned non-login directory,
  not fake User accounts or a second Vendor company
  collection. Inspect real existing roles and universal
  notes/attachments/permissions before implementation.
- Tags must be scoped universally to authorized
  entities, not raw cross-org table references or
  user-controlled arbitrary SQL; import/export later.
- Keep hybrid capability gating and immutable audit,
  active actor, org scope and exclusion of W-9/tax
  data from general exports. Include tests and
  verify full six-job CI. No extra docs/ changes.


## Phase 4 Contacts directory — VERIFIED 2026-09-27

Backend/model/migration/regressions b91ec3c38055272ae97a81a2e16630e87cd98ac7;
customer UI be1d1f84cac32a136202e8e17651161a63316fd3;
existing browser E2E test-only race correction
a607c8c370fa42f44e897a34a7667dd46c30ce69.
Full source CI 36340860778 SUCCESS all six jobs:
backend 604 passed, 3 deselected, 11960 warnings in 133.93s;
authenticated E2E 3 passed in 10.77s; frontend
lint/typecheck/build, platform-admin, security, staging-config green.
Initial CI 36340447416 backend 604 passed, but browser E2E
failed existing Features "Map view" toggle reload test because
it reloaded before the optimistic PUT response; test-only correction
awaits the actual successful PUT before reload. No Features
implementation changed. Earlier superseded runs cancelled.
E2E generic smoke, not dedicated Contacts UI interaction coverage.

Alembic d2e4f6a8b0c1 creates one contacts table,
111 expected model tables; bootstrap/legacy/PostgreSQL guards green.
Independent organization-owned non-login Contact PERSON/BUSINESS
with recorded name, company, email, phone, job title, mailing address.
No automatic User, Vendor, Bill, tax-profile or W-9 links.
Authenticated GET/POST/PATCH/DELETE/restore /api/contacts,
admin writes, ADMIN/OWNER/MANAGER permitted read with PEOPLE.CONTACTS;
nonstaff denied, inactive/deleted actors denied, cross-org IDs 404.
Bounded case-insensitive search, soft deactivation/restore,
no-store reads, append-only audit without contact PII.
Frontend /dashboard/contacts is preexisting PEOPLE.CONTACTS
menu destination. Form/directory supports add/edit/search/archive/
restore; unauthorized writes blocked by backend. Three focused
tests cover isolation, roles, revocation, audit, input validation
and no user/vendor mutations. Frozen docs/ and planning parity unchanged.

NEXT original Phase 4: Universal Tags, then People import/export.
Reuse verified generic entity_notes.resolve_note_target for
organization/permission/property scope and explicit safelist
of supported target entities; do not allow arbitrary table names,
tax data or cross-org targets. Tag definitions and scoped link
rows must be durable, audited and duplicate-safe. Keep staff
target permissions and user-visible picker on actual entities.
Existing Contacts non-login records should use PEOPLE.CONTACTS
when resolving generic notes/tags for assigned managers.
No GL/posting mutation, no tax identifiers or unencrypted W-9s.
Do not invent generalized bulk imports before tags verified.


## Phase 4 Universal Tags and Contacts CSV transfer — VERIFIED 2026-09-27

Universal Tags source 73d4cceae74c44b1fd45afe18368cd7514706039.
CI 36341415211 SUCCESS all six jobs: backend 607 passed,
3 deselected, 12069 warnings in 102.64s; E2E 3 passed
in 8.78s; frontend, platform admin, security, staging green.
Added tag definition/association models, migration and tests;
retained explicit target allowlist, org/member property scoping,
no tax/secret entities, audited idempotent links, and reusable
Contact/Vendor TagPicker. Do not rebuild tags.

Contacts CSV source 0062cc22834129c1998c2320e5f78cad50b9d1c8.
CI 36347187712 SUCCESS all six jobs: backend 612 passed,
3 deselected, 12151 warnings in 137.77s; authenticated
browser E2E 3 passed in 8.76s; frontend lint/typecheck/build,
platform admin, security, staging config all green.
Generic E2E smoke only, not a dedicated file-upload browser flow.

Files: backend/app/services/contact_transfer.py,
backend/app/routers/contacts.py, backend/tests/test_contact_transfer.py,
frontend/src/components/contacts/ContactTransferPanel.tsx,
frontend/src/app/dashboard/contacts/page.tsx.
Exports only active org Contacts via the canonical server
ReportPayload/CSV formula-escaping renderer. Requires live
PEOPLE.CONTACTS plus release.reporting.export, 1000-row ceiling,
no-store/nosniff/download headers; excludes inactive/foreign
contacts, Users, Vendors and any tax or W-9 data.

Admin import is TWO-STAGE: server CSV preview, then explicit
confirmed commit using the matching org-bound CSV SHA-256 digest.
Limit 128 KiB/200 rows, explicit 12-field contact allowlist,
Pydantic validation; rejects unexpected sensitive/identity
columns, invalid emails/types, malformed rows, in-file and
org-existing email/name conflicts (including archived contacts).
Revalidates live admin/menu/org access and all duplicates before
atomic insert, and serializes org imports through FOR UPDATE on
PostgreSQL. Never edits/merges existing records or creates User/
Vendor accounts. Audit records count only, never contact PII.
Five focused backend tests cover no-write preview, atomic creation,
conflicts/format/digest, org scope, role/menu/export revocation,
CSV formula escaping and unaffected Users/Vendors. No migration:
Alembic d2e4f6a8b0c1 / 111 tables unchanged. Frozen docs/ and
parity unchanged. This is bounded independent Contacts transfer,
NOT general user, vendor, tax or bank-data import.

Original next feature after Contacts/Tags/import-export section:
Phase 4 Leasing Applications expansion (read original Section 18
and Phase 4 checklist). Current LeaseApplication model already
contains optional applicant_ssn as PLAINTEXT String and screening
results as Text, even though no application router currently exists.
Do NOT expose, serialize, log, duplicate, or write plaintext SSNs
via any new intake. The approved encrypted W-9 tax profile storage
is for tax forms, not a default applicant screening store. Scope
Phase 4 application onboarding to safe non-SSN fields and
verified org/property/applicant access first; sensitive income/
screening, payment integration, consent, secure deletion and
reporting require separate controls/provider workflows. Do not
declare a full online paid/screened application workflow until
implemented and verified. Preserve existing Lease/GL/accounting
semantics. No frozen docs/ edits without separate authorization.


## Phase 4 Rental Applications initial safe intake — VERIFIED 2026-09-27

Source 864bf2e02a80e1b2a4af58a0bdaa279b5f4f14a9.
Full CI 36347804741 SUCCESS all six jobs:
617 backend passed, 3 deselected, 12289 warnings in 99.42s;
authenticated E2E 3 passed in 9.03s; frontend
lint/typecheck/production build, security,
platform-admin and staging-config all green.
Five focused backend tests; generic E2E smoke not
dedicated applicant UI payment or screening tests.
No migration: head d2e4f6a8b0c1 and 111 tables.
Frozen docs/ / parity unchanged.

Added /api/leasing/applications and the existing
LEASING.APPLICATIONS menu destination
/dashboard/leasing/applications; applicant role
gets a direct link from dashboard home.
Applicants with active organization accounts can
create self-owned DRAFT applications for active
same-org property and optional matching active
unit, edit only own draft, and explicitly submit
to PENDING_PAYMENT. Submission DOES NOT charge
a fee; ApplicationPayment count remains unchanged.
No staff approval, screening, status PAID or lease
activation route was added. Scoped staff ADMIN/
OWNER/MANAGER can read only current org/property
applications with live LEASING.APPLICATIONS menu
permission; managers need active assignment.
Other applicants, tenants, inactive users and
foreign property/unit probes fail closed.
No-store read APIs, 200-row queue ceiling,
append-only status-only audit, no GL writes.

Safe serializer and schema never accept, return,
or write existing plaintext applicant_ssn, DOB,
screening_result, fee_amount or payment tokens.
Existing LeaseApplication still has an old
applicant_ssn String column in schema: no new
intake may populate it. Form only collects
applicant name/email/phone, optional preferences,
bounded occupant names and pet description.
This does NOT implement original complete online
rental application; missing current/previous
addresses, personal/financial data, fee payment,
signed consent, screening and review workflows.
Do not call it FULL Applications until verified.
No public listings integration yet: applicant
supplies a property/unit ID from property office.
Do not infer applicant consent or eligibility.

NEXT bounded original Phase 4 Applications work:
complete secure applicant details and application
fee flow with verified amounts, consent, user/org
scope, payment webhook integrity; no plaintext SSN.
Review existing Property/Unit application_fee,
ApplicationPayment and Stripe checkout/webhook
infrastructure. Keep payment status server-trusted
and do not silently treat pending as paid. The
next phase after Applications in original Section
18 is Lease Templates, then CRM/Prospects and
Guest Cards. Avoid starting new unrelated Phase 3.7
reports or rewriting previously verified contacts.

## Phase 4 encrypted application questionnaire and fee quote — VERIFIED 2026-09-27

Encrypted private questionnaire source
cbcc52bf710791abd721b8a63dc4bceb10c9b806;
CI 36348392919 SUCCESS all six jobs (623 backend passed,
3 deselected, 12484 warnings in 143.90s; E2E 3 passed;
frontend, platform-admin, security and staging green).
Migration f1e3a5c7d9b0 adds one organization-owned
application_private_details ciphertext table (114 expected tables).
Separate APPLICATION_ENCRYPTION_KEY; never fallback to ordinary
SMTP or tax keys. Applicant-only own DRAFT edits, applicant and
authorized scoped staff read, no-store responses; encrypted
address/employment/income, no plaintext SSN, date of birth, bank
information or screening. Generic notes/attachments cannot target
private details. No fee or GL change from this batch.
Real provider-backed screening is Phase 8, NOT included.

Fee quote source 8e751bed878d158501754ae3858f1047e39888ef;
CI 36359893698 SUCCESS six jobs: backend 626 passed,
3 deselected, 12590 warnings in 103.00s; E2E 3 passed
in 10.16s; frontend, platform-admin, security and staging green.
No migration: still f1e3a5c7d9b0 / 114 tables.
backend/app/routers/rental_applications.py
  GET /api/leasing/applications/{application_id}/fee-quote
frontend/src/components/leasing/ApplicationFeeQuote.tsx
frontend/src/app/dashboard/leasing/applications/page.tsx
backend/tests/test_rental_applications.py
Three new focused tests verify applicant/foreign-organization/staff
access, disabled/foreign unit and property safety, optional unit/fee
unconfigured behavior, negative fee rejection, zero-dollar quote,
read-only repeat and absence of any ApplicationPayment/GL/status
mutation. Quote displays only server-configured active unit fee
in USD and never assumes a property-only fee or an unconfigured
zero fee. No checkout URL or payment action. E2E is generic
authenticated browser smoke, not a dedicated payment-browser test.

The next original Phase 4 Applications batch must implement an
explicitly configured provider-backed payment attempt and safe
webhook/accounting lifecycle; use actual Unit.application_fee,
never browser-supplied amounts or fake PAID status. Existing
app/services/stripe_billing.py is for subscription billing
and its webhook must not be reused as an application-fee
event handler without separate event identity/verification.
Use one-time Stripe Checkout/payment mode, unique idempotent
attempts scoped to application/organization/applicant, signed
webhook and exact amount/currency/intent/session validation;
accounting must use the verified GL/receipt posting with no
duplicate receipt on replay. Deferred payments, refunds,
overpayment, zero fee, session expiry, provider unavailable
and legacy paid statuses need explicit treatment. Do not
turn on payment until provider credentials, webhook secret,
GL cash/income mapping and reconciliation work end-to-end.
Existing ApplicationPayment is legacy and has no org FK or
unique provider guarantee; inspect before migration. Never
claim a Stripe session alone means money received. Consider
explicit applicant consent/terms before charging. Existing
POST /api/billing/checkout-session is SUBSCRIPTION mode, not
the application fee route. No frozen docs/parity edited.
No IRS/Avalara external filing progress is claimed by this batch.

## Phase 4 fee preparation contract — VERIFIED 2026-09-27

Source af94f8afefd853a906c9bf19fc96819eab42c7fc.
Full CI 36360330500 SUCCESS all six jobs: backend
629 passed, 3 deselected, 12662 warnings in 133.73s;
authenticated E2E 3 passed in 10.10s; frontend,
platform-admin, security and staging green.
Migration f2e4a6c8d0b1 (after f1e3a5c7d9b0)
creates one application_fee_attempts table; 115 model tables.
Read-only Unit fee quote from prior batch still verified.

POST /api/leasing/applications/{id}/fee-preparation
is applicant-owned, pending_payment only, requires
a currently active org/property/unit and configured
positive server fee; rejects missing/unitless, zero,
negative, changed fee and foreign/staff access.
Request has only an idempotency key (extra fields
forbidden); DB unique application ID and PostgreSQL
row lock enforce one pending preparation per app.
Duplicate same key+amount returns same prepared record;
different key or changed fee returns 409. Receipt/Stripe
payment rows, GL, app PAID status and existing signed
webhook/subscription billing remain UNCHANGED.
Status PREPARED and checkout_available=false are
not payment authorization or money received.
App payment provider step still needs verified
merchant-of-record/funds destination: existing
Stripe billing session is SaaS SUBSCRIPTION mode,
not an authorized application fee merchant account.
No live fee checkout should reuse platform
subscription funds by default. Existing 1099 provider
credentials are unrelated. Added three focused
tests for idempotency, money nonmutation,
foreign/staff/disabled-unit scope, fee precision
and generic-attachment denial. No frozen docs
or parity changes.

Next safe fee-workflow batch: explicitly link a
staff-received APPLICATION_FEE Receipt already
posted through verified GL, with exact same-org
property/unit and amount, source reference
and non-reversed GL, admin + receipts and
applications permissions, duplicate prevention,
audit and reversal reconciliation. Do NOT
post a second GL entry, fabricate payment
or use frontend success as a receipt.
This is *offline receipt accounting only*;
online Stripe checkout still needs distinct
org merchant/provider configuration, webhook,
event idempotency and provider-confirmed funds.
Respect original Section 18 Applications;
external Stripe payments remain Phase 8
integration dependency until configured.


## Phase 4 offline application fee settlement — VERIFIED 2026-09-27

Source f364877dabe43757ea949d8d28e1d2682e3bebaa;
migration/reversal fix 4781ddc4e4dccbb8e6be99f032704aaa56a685d3;
isolated receipt fixture repair b149717b76a45be85a02584d26176bbb90048dd4.
CI 36361333281 SUCCESS all six jobs: backend 633 passed,
3 deselected, 12872 warnings in 144.57s; authenticated browser
E2E 3 passed in 9.85s; frontend, platform-admin, security, staging green.
Prior run 36361018433 FAILED; fix and new CI green; intermediate
36360963206 CANCELLED. These counts apply to verified source only.
Alembic f3e5a7c9d1b2 adds nullable unique
application_payments.receipt_id FK; 115 SQLAlchemy tables unchanged.

POST /api/leasing/applications/{id}/record-fee-receipt is admin-only,
requires live LEASING.APPLICATIONS + ACCOUNTING.RECEIVABLES
permissions and release.accounting.receipts.application_fee;
links an EXISTING, active, non-reversed, exact-fee, verified
APPLICATION_FEE Receipt already posted through immutable central GL.
Original Receipt must match current organization, property, unit,
applicant name, APP-{application_id} reference, income GL 4420
and active original GL transaction. Prepared attempt amount/ID
and applicant ownership are verified. Unique receipt FK prevents
reuse; one paid payment per application. Link changes applicant
status to PAID without duplicating GL or charging Stripe.

Existing reversal and NSF receipt posting now reconcile linked
application fee: payment status reversed, application back to
PENDING_PAYMENT, fee_amount reset and attempt REVERSED, all
transactional with the original accounting reversal. An
unsuccessful locked-period GL reversal leaves paid application
untouched. Focused tests verify scope, permission/gate revocation,
idempotence/reuse, exact amounts/receipt references and reversal.
No browser-supplied fee amounts, no card checkout, and no automatic
provider fee deposit. The online Stripe/provider integration still
requires authorized org-specific merchant of record, signed
webhook, reliable event reconciliation and provider-confirmed funds.

NEXT original plan Phase 4 Lease Templates: 3-level Template +
Addenda + Attachments; database-wide (same organization) or
per-property. Reuse entity attachments with lease-template target
permission and property assignment checks; exclude tax/SSN
content, draft versioning/immutable published copies where required,
no automated e-signature or tenant disclosure without approval.
Before coding inspect existing Lease/Property and template-related
models, menu permissions, Frontend navigation and docs Section 18.
Use bounded product code plus applicable tests and hosted CI.


## Phase 4 Lease Templates and CRM — VERIFIED 2026-09-27

Lease Templates backend 6faba5d9e34fdc6be255006c0a50739a6bf6a4ae,
customer UI 3e37cc8ae9238a278cf4c7fc35586c98797e865a;
CI 36364069609 SUCCESS all six jobs: backend 636 passed,
3 deselected, 12972 warnings in 109.56s; E2E 3 passed in 8.73s.
Migration f4e6a8c0d2e3 adds lease_templates and lease_template_addenda,
117 model tables. Three-level draft template/addenda/ordinary universal
attachment UI, organization-wide or property scope, manager property
assignment restrictions, admin writes, audit, bounded text validator.
No signature, tenant delivery, active lease or GL mutation. Existing
attachment service reused; no parallel store.

CRM backend 0fcc72f063a13d0aeb7c420d88aa9531e314a8cc;
customer UI 1e2713aa5c549af6c6fc00bfc8b6b879e4ae8647.
CI 36365456607 SUCCESS all six jobs: backend 638 passed,
3 deselected, 13033 warnings in 107.99s; E2E 3 passed in 10.74s.
Migration f5e7a9c1d3e4 adds leasing_prospects (118 tables), linked
to existing org Contact and active Property. Stages NEW, CONTACTED,
TOUR_SCHEDULED, APPLIED, CLOSED; marketing source, follow-up date,
org/assignment scope, admin/manager staff writes, scoped owner read,
archive, permission recheck, redacted audit and duplicate rejection.
Source marketing label is captured; a full attribution analytics engine
is NOT implemented. Frontend /dashboard/leasing/crm uses existing
LEASING.CRM navigation and Contact/Property pickers. No login
identity, Application, Lease, payment or GL mutations.
Backend CRM regression tests: 2; existing tests: 636 prior to CRM,
638 now. Browser E2E is generic smoke, NOT dedicated CRM flow.
Frozen docs/ not edited; parity planning statuses not advanced.

NEXT original Phase 4 task: Guest Cards. Inspect existing
Contact, Prospect, Property/Unit scoping before coding. Use a
scoped prospective-tour/guest record linked to an existing prospect,
not a public unauthenticated intake or automatic applicant account.
No SSN, payment, screening, signatures or automated outbound
messages. Include regression tests, hosted CI and handoff update.


## Phase 4 Guest Cards — VERIFIED 2026-09-27

Source model/API/migration/regression/customer UI
b5dc99a60559d0ddb5fcb9b8aecca6813e320098;
follow-up scoped serializer/query refactor
70a5f00ae506f74567060d208e9aa8a92733663d.
Full CI 36365992264 SUCCESS all six jobs: backend
640 passed, 3 deselected, 13110 warnings in 117.87s;
authenticated E2E 3 passed in 9.55s; frontend lint/typecheck/build,
platform-admin, security and staging all green.
Initial CI 36365973815 was superseded/cancelled, not verified;
only final source 70a5 has verified complete CI. Generic browser
smoke, not dedicated Guest Card browser interaction tests.
Migration f6e8a0c2d4e5 adds leasing_guest_cards; 119 model tables.

GET/POST/PATCH/DELETE /api/leasing/guest-cards and customer page
/dashboard/leasing/guest-cards linked from CRM.
Each staff-recorded card refers to an existing active same-org
Prospect/Contact/Property, optional active same-property Unit;
records visit date, attendance and bounded next-step enum.
Admin and assigned Manager may write; Owner may read within org,
nonstaff denied; live LEASING.CRM permission and active user
rechecked. Manager only sees assigned properties. A same-prospect/
day database unique constraint rejects duplicate records;
soft archive and append-only redacted action audit.
Does not create or submit a rental application, lease, payment,
login identity, tenant signature, external messages or SSN.
Two new focused backend tests for scope, unit/role/permission,
duplicate handling, archive and zero application/lease mutations.
No changes to frozen docs or plan parity status.

NEXT original Section 18 CRM subrequirement: marketing effectiveness.
The verified CRM captures marketing source and staff-maintained stage
but has no source effectiveness summary. Implement an explicitly
read-only per-source stage/count breakdown over authorized active
prospects, with clear warning that staff-marked stages are NOT
verified paid conversions, ad spend or real applications. Do not
infer marketing ROI without cost data or change GL/applications.
Then consult original Phase 4 checklist for next unverified work.


## Phase 4 CRM recorded marketing-source summary — VERIFIED 2026-09-27

Source 423d78f52e1f3628701099ff8eba7dbff972903b.
CI 36366800985 SUCCESS all six jobs: 642 backend passed,
3 deselected, 13172 warnings in 152.71s; 3 authenticated E2E passed
in 7.64s; frontend, platform-admin, security, staging-config green.
No migration: Alembic f6e8a0c2d4e5, 119 model tables.
GET /api/leasing/prospects/source-summary uses live LEASING.CRM,
org isolation, manager assigned-property visibility, active
property/contact/lead filters and bounded per-source/per-stage
aggregation. Staff-marked stage APPLIED is not verified submitted
Application; no ad-spend ROI, verified conversions or GL effects.
Frontend marketing-source table within the verified CRM page updates
after staff changes. Two focused backend tests cover scope,
archived/disabled targets, role/menu permission and nonmutation.
Existing E2E is generic smoke, not dedicated CRM analytics UI test.
No frozen docs/ or planning parity changes.

NEXT original roadmap after Section 18 leasing: Phase 4.5 compliance
umbrella (HOA, Affordable, Commercial, RUBs, Escrow) and separate
4.6-4.17 product-line subphases described in docs/PLAN_GAPS.md.
Start with bounded property RUBs tab / allocation readiness,
not a full tenant charge engine: existing PropertyUtility and
UtilityBill describe current utility setup/owner-paid bills, but
no verified RUBs allocation formula, meter readings or legal rate
rules yet. Require org/property role/assignment scope; do not
create charges, GL postings or pretend a utility bill is
allocable without explicit reviewed rules and period data.
Check frozen docs/PROJECT_MASTER.md Section 38/Compliance checklist
and docs/PLAN_GAPS.md C1-C4 READ-ONLY; never amend without approval.
Then proceed in original dependency order after hosted CI.

## Phase 4.5 RUBs inventory and bill-period diagnostics — VERIFIED 2026-09-27

Read-only readiness source ca07e0af4103b55425b26561641728f521b991ab;
CI 36367397250 SUCCESS six jobs (644 backend passed, 3 deselected,
13237 warnings in 152.05s; 3 E2E passed in 10.99s).
Period diagnostics source 54ad71a8ab2d2bb8aaeeaad27f97614707b71369;
CI 36368986607 SUCCESS six jobs (646 backend passed, 3 deselected,
13305 warnings in 151.20s; 3 E2E passed in 9.20s).
No migrations: f6e8a0c2d4e5; 119 model tables unchanged. Frontend lint,
typecheck, build; platform-admin, security, staging green. No frozen
docs or parity statuses edited.

Property > RUBs gated release.properties.rubs uses live PROPERTIES.ALL
permission, active org + property scope, manager current assignment,
no tenant/other-organization visibility. Shows active SHARED utilities
and counts recorded bills with complete, missing or reversed periods.
Second bounded batch counts exact duplicate intervals and overlapping
intervals (inclusive boundary dates), ignoring invalid/missing periods.
An overlap count flags each subsequent sorted interval intersecting a
previous interval; a duplicate count flags subsequent identical
start/end pairs. Such flags need manual bill review and are NOT an
allocation formula or assertion of billable expenses.
Two original + two extra focused backend regression tests verify scope,
gate/role denials, duplicate/overlap calculations, invalid periods,
sensitive account-number/bill-amount exclusion and no Charge/GL change.
The authenticated browser smoke is generic, not a dedicated RUBs
browser interaction test.

IMPORTANT: docs/PLAN_GAPS.md C4 schedules full ratio allocation,
meter reading, utility provider integration, reviewed tenant/owner
charges, true-ups and reports as NEW Phase 4.9, not completed Phase 4.5.
Do not mark full RUBs implemented from the readiness tab. Do not assume
any recorded bill is legally allocable without property jurisdiction,
lease disclosures and reviewed cost/meter/occupancy rules.

Original Phase 4.5 additional trust-account enhancements in
docs/PLAN_GAPS.md C7 trust interest, C8 bank positive pay, C9 provider
e-filing remain scheduled. Next bounded Phase 4.5 task can establish
explicit trust-interest policy/manual legal-review readiness scoped to
verified bank/GL mapping. Do not assume whether interest belongs to
tenant, state or housing fund from bank account type or geography.
No GL posts, bank movements, tenant interest payment or tax claims
without verified jurisdiction/lease rules and an approved posting path.
Then proceed in the original plan dependency order.

## Phase 4.5 trust-interest jurisdictional policy readiness — backend VERIFIED 2026-09-27

Source ed9d2d97cce994909798c6f413e2ed4b4247c116.
GitHub Actions run 36369555961 SUCCESS all six jobs:
649 backend passed / 3 deselected / 13393 warnings in 104.75s;
3 authenticated E2E passed in 9.90s. Frontend lint/typecheck/
build, platform-admin, security and staging passed.
Migration a7c9e1f3b5d0 after f6e8a0c2d4e5 adds
trust_interest_readiness; 120 SQLAlchemy tables. Existing
GL/bank posting, bank identities, checks and RUBs unchanged.
Three focused tests: same-organization and current active bank/GL
scope, user/menu/release gating, validation, audit redaction,
no account number exposure and no GLTransaction writes. Generic
browser E2E is NOT a dedicated interest settings interaction test.

GET/PUT /api/accounting/bank-accounts/{bank_id}/interest-readiness
reuse customer auth, ADMIN/OWNER and ACCOUNTING.BANK_ACCOUNTS
permission plus existing release.accounting.bank_accounts gate.
Valid active org-scoped bank and active org-mapped ASSET GL are
required. A unique bank/org readiness record stores staff-entered
jurisdiction, proposed interest recipient class (UNDETERMINED,
TENANT, STATE, HOUSING_FUND, OTHER) and bounded basis-reference
text. Proposed recipient other than UNDETERMINED requires BOTH
jurisdiction and reference; neither represents verified applicable
law or formal approval. API returns no routing/account numbers and
only a boolean noting a supporting reference was recorded. Audits
contain bank ID and manual-review flag, never reference contents.
All outputs truthfully require further legal review; both
interest_allocation_enabled and interest_posting_enabled are FALSE.
No interest rate, daily accrual, tenant distribution, escrow transfer,
payee tax assessment, or generated financial transaction.
This is a preparation contract, not a completed C7 trust-interest
accounting engine. Frozen docs/ and parity unchanged.

NEXT bounded UI: reuse Bank Accounts customer listing; expose
a restricted interest-policy review link/action for ADMIN/OWNER,
with a modal or embedded accessible component for each current
bank. Explain proposed handling requires independent jurisdiction/
lease verification and nothing is calculated or posted.
Use existing apiGet/apiPut; never show full bank numbers.
Then return to original Phase 4.5 PLAN_GAPS C7/C8 order:
interest accounting remains gated until jurisdiction rules and
posting contracts verified; bank positive-pay requires a bank-
specific verified issue/void file schema and user review.

## Phase 4.5 trust-interest customer bank review UI — VERIFIED 2026-09-27

UI/regression source a2da32a884a16ff9a1fa8adedc3b199810d19e36,
CI 36370090346 SUCCESS six jobs: 650 backend passed,
3 deselected, 13423 warnings in 115.57s; 3 authenticated E2E
passed in 9.15s. Frontend lint/TypeScript/build, security,
platform-admin, staging green. No migration: head a7c9e1f3b5d0,
120 SQLAlchemy model tables. Original bank account editing and
fund movements unchanged. Frozen docs and parity unchanged.

Bank Accounts customer page includes scoped ADMIN/OWNER-only
Interest review button behind existing bank_accounts feature.
frontend/src/components/accounting/TrustInterestReview.tsx uses the
verified GET/PUT interest-readiness API; shows recorded jurisdiction,
proposed beneficiary and supporting-reference existence.
Previously stored free-text reference is not exposed in responses,
and must be re-entered when changing a proposed recipient.
UI clearly says independent legal/jurisdiction/lease review is
required, and no interest calculation, payout or GL posting exists.
One additional focused backend test verifies Cache-Control no-store,
the active same-org mapped ASSET GL check and no GL activity.
Generic E2E smoke passes; it is NOT a dedicated interest dialog
interaction test. Existing C7 trust-interest accounting and statutory
disbursement remain pending until verified jurisdiction-specific
requirements. Do not imply a staff proposal determines legal ownership.

NEXT original PLAN_GAPS C8 positive-pay check-file requirements.
The app has verified issue/void check ledger and Check Register
but no verified bank-specific positive-pay file schema/format
or bank acceptance. Start with bounded per-bank issue/void
eligibility/preflight from verified Check/GL state, staff scoped,
no routing/account numbers in UI or unsupported bank-upload file.
Require a confirmed bank template and human review before a
bank-specific positive-pay file is labelled upload-ready.
Reusing an ACH or check-register CSV as a bank-approved positive-
pay file is NOT acceptable. No GL, check issue, void or bank
reconciliation mutation in a readiness preview.

## Phase 4.5 positive-pay bank preflight + customer UI — VERIFIED 2026-09-27

Preflight source 82844c94fad5d4ef7fd33ac2e0366055953320e1,
CI 36370656288 SUCCESS six jobs: backend 653 passed,
3 deselected, 13565 warnings in 123.50s; E2E 3 passed in 8.42s.
Customer bank review source 6fe873dfa466a33b478dc638c0196bbddb64c9e5,
CI 36371943676 SUCCESS six jobs: backend 654 passed,
3 deselected, 13612 warnings in 149.65s; authenticated E2E
3 passed in 9.31s. Frontend lint/typecheck/build, security,
platform-admin, staging passed. No migration: Alembic
a7c9e1f3b5d0 / 120 model tables. Tests added with both
batches. No frozen docs/ or parity changes.

Admin-only GET /api/accounting/bank-accounts/{bank_id}/positive-pay/preflight
requires active same-org bank mapped to active ASSET GL, bank
permission, release.accounting.check_printing and verified Check
Register permissions. Accepts optional check-date range, max 500
recorded checks, no-store response. Reuses the verified issue/void
GL provenance logic, flags missing recorded number/payee, returns
only check display attributes (never bank routing/account IDs).
Internal issue/void status is NOT bank clearing or acceptance.
No check, GL, bank reconciliation or other accounting mutation.
Customer Bank Accounts page now opens a gated ADMIN-only
Positive-pay review dialog with date filters, issued/void counts
and review flags, explicitly NOT_SUBMITTED and no export.
Check-date is ORIGINAL issue date, not necessarily void-action date;
this view is not an event-dated bank file or accepted bank template.
Generic E2E smoke passed; it is NOT a dedicated dialog browser test.

Original PLAN_GAPS C8 positive-pay file/export remains UNVERIFIED:
a bank-specific approved template/schema, event/effective-date
semantics, transmission method, reconciliation and human review
are required before any upload-ready file or bank integration.
Existing ACH CSV/NACHA/check-register exports MUST NOT be
presented as positive-pay bank files. No actual bank file, submission
or bank acceptance implemented; needs bank-supplied specifications.
This is an external dependency and does not block work on
independent original-plan Phase 4.6.

NEXT independent original phase: 4.6 Affordable Housing /
Section 8 / LIHTC per PLAN_GAPS C1 (read frozen docs only).
Start with bounded property-level program inventory linked to
current org/property, staff-scoped and release.properties.compliance
gated, explicitly descriptive, not HUD/LIHTC eligibility
certification. Do not infer eligibility, HAP amounts, AMI limits,
income, legal rates or applicant status. Add focused tests and UI,
CI verify, then update this root handoff.

## Phase 4.6 affordable-housing property program inventory — VERIFIED 2026-09-27

Source 8c20d48deab2ad5fdbe8c323d8409462bce77068.
Hosted CI 36372554518 SUCCESS all six jobs:
657 backend passed, 3 deselected, 13686 warnings in 142.67s;
3 authenticated browser E2E passed in 8.93s.
Frontend lint/TypeScript/build, security, platform-admin and
staging-config green. E2E is generic authenticated browser smoke,
NOT a dedicated Compliance tab interaction test.
Alembic b8c0d2e4f6a9 (from a7c9e1f3b5d0);
model table count 121 (previously 120).
New backend/app/models/affordable_program.py, schemas/affordable_program.py,
routers/affordable_programs.py and 3 focused backend regressions;
new frontend/src/components/property/AffordableProgramsTab.tsx and
enabled existing release.properties.compliance-gated Compliance tab.
Root init_db.py, app/main.py, and 3 migration guard tests updated.
Frozen docs/ and planning parity not changed.

GET/POST/PUT/DELETE /api/properties/{property_id}/affordable-programs:
scoped active organization/property, ADMIN/OWNER writes,
assigned MANAGER reads only, no TENANT/CREW access.
Live PROPERTIES.ALL and release.properties.compliance required.
Records bounded staff-entered program category (LIHTC,
Section 8 voucher/project-based, HUD other, other), label,
optional recorded agency and dates. Explicitly not a verified
HUD participation, LIHTC certification, eligibility, AMI/rent
limit, HAP payment, tenant admission or tax-credit assertion.
Distinct recorded labels per property, immutable action audit
(redacted to program type), soft archive, 101-result bounded read.
No protected household, income, SSN, application/lease,
Charge, GL or bank account changes. Tests verify org/manager scope,
live gates/permissions, uniqueness, date validation, lifecycle,
no-store, activity and accounting nonmutation.

NEXT Phase 4.6 dependency: intake for existing authorized CRM
prospects' recorded interest in a recorded property program.
Build a *staff-recorded interest register*, NOT an official
HUD/LIHTC ordered waiting list, eligibility determination,
program-specific preference/ranking/offer or public signup.
HUD's own occupancy guides require program/owner-specific
tenant selection policies; do not auto-rank or infer eligibility.
Reuse Prospect/Contact/property assignment and active program
scope; require both PROPERTIES.ALL / compliance feature and
LEASING.CRM permission before revealing contact names.
Do not add race/disability/household/income fields to generic
interest register or expose applicants across organizations.
Next full program-specific waitlist/selection workflows depend
on reviewed jurisdiction/agency tenant selection plans.
Reference: https://www.hud.gov/hud-partners/public-housing-occupancy-guidebook
and https://www.hud.gov/helping-americans/housing-choice-vouchers-guidebook .

## Phase 4.6 recorded program CRM interest — VERIFIED 2026-09-27

Implementation 67d4d5f15d10b0830a02702b453c68a98e5e9d45.
GitHub Actions 36373217097 SUCCESS all six jobs: backend
660 passed, 3 deselected, 13816 warnings in 139.87s;
authenticated E2E 3 passed in 11.28s; frontend,
platform-admin, security, staging-config all green.
Generic authenticated E2E, not dedicated Compliance-tab interaction.
Migration c9d1e3f5a7b0 adds affordable_program_interests:
122 model tables, previous b8c0d2e4f6a9/121.
No frozen docs/ or parity edit.

GET/POST/DELETE
/api/properties/{property_id}/affordable-programs/{program_id}/interest
and customer Compliance tab "Interest" panel link
current authorized CRM Prospect/Contact to existing active
same-org property program. ADMIN/OWNER may record/archive;
assigned MANAGER may read only. Each call enforces
PROPERTIES.ALL, release.properties.compliance, LEASING.CRM,
current active organization/property/program and Prospect/Contact.
No archived contact name is returned. Unique org/program/prospect
constraint, bounded list 200, no-store, append-only redacted audit,
soft archive, date recorded is NOT admission/priority. Three
focused tests validate lifecycle, cross-org/property scope,
assignment, CRM/compliance revocation and absence of
Lease/Charge/GL mutation. No income, SSN, household protected
fields, eligibility decisions, HUD waiting-list rank, electronic
submission, applicant status or automatic messages.
Existing generic notes/attachment resolver is dynamically
model-discovering; assess denying this new linked-contact entity
to prevent disclosure via a weaker access route. Follow with
focused regression and CI before adding further sensitive modules.

## Phase 4.6 property-program evidence-readiness index — VERIFIED 2026-09-28

Source e492a46356bc19a57c55f63fe9ad85a5e0b7d5c8.
Hosted CI 36378052654 SUCCESS all six jobs: 665 backend passed,
3 deselected, 13936 warnings in 165.90s; 3 authenticated E2E passed
in 9.62s. Frontend lint/typecheck/build, platform admin, security,
staging passed. Generic browser smoke, NOT dedicated evidence UI E2E.
New migration d0e2f4a6b8c1 following c9d1e3f5a7b0;
123 model tables (prior 122). No frozen docs/ or planning parity edits.

Scoped active org/property/program staff evidence-readiness API:
GET/PUT /api/properties/{property_id}/affordable-programs/{program_id}/evidence.
Reuse verified compliance _property/_item authorization (live gate,
PROPERTIES.ALL, staff roles, manager active property assignment).
Only ADMIN/OWNER may edit; assigned MANAGER may read. Fixed categories:
agency guidance, program agreement, property record index, inspection
coordination. Staff-controlled statuses NOT_RECORDED, FOLLOW_UP_NEEDED,
REFERENCE_IDENTIFIED and optional staff follow-up date. These are
only records of staff preparation, not verified document availability,
agency approval, HUD/HQS/LIHTC certification, income/rent eligibility,
legal deadlines or inspection results. No raw documents, household
information, protected applicant data, open-text notes, rent amounts
or GL/Charge/Lease mutation in the new table.
New frontend/src/components/property/AffordableEvidenceChecklist.tsx
under already verified customer Compliance tab; canEdit follows
existing ADMIN/OWNER UI contract. Generic notes/attachments resolver
explicitly excludes affordable_program_evidence because its access
boundary is narrower than ordinary entity notes. Three new regression
tests cover scoped lifecycle, manager cross-property/other-org denials,
feature/permission revocation, invalid certification-like statuses,
audit, generic-target denial and accounting nonmutation.

Next safe Phase 4.6 subtask: show a read-only scoped count/most recent
date for already explicitly staff-recorded unit inspections, reusing
backend/app/services/unit_inspections.py; require its own existing
REPORTING.ALL, PROPERTIES.ALL, PROPERTIES.UNITS and ADMIN/MANAGER
authorization as well as the compliance gate and property visibility.
Do not expose inspection findings/tenant information via compliance
summary or claim existing staff observations satisfy HQS, LIHTC or
other agency-specific inspection standards. Existing full
unit-inspections route/report remains unchanged. Add focused tests
for permission mismatch, scope, inactive units and nonmutation.
After that, program-specific agency/legal policies and secure
household document workflow must be verified before substantive
eligibility/certification or HAP posting. Original Phase 4.6 remains
IN PROGRESS, no official compliance workflows are complete.

## Phase 4.6 existing unit-inspection cross-reference — VERIFIED 2026-09-28

Source 87c2eaa9ba5a21f8cc461c92cf46aaf474cd8b46.
CI 36378605760 SUCCESS all six jobs; backend 667 passed,
3 deselected, 14005 warnings in 161.47s; browser E2E
3 passed in 11.00s; frontend, platform-admin, security and
staging green. No migration: d0e2f4a6b8c1, 123 tables.
Frozen docs/ and parity untouched. Generic browser E2E passed;
no dedicated inspection-cross-reference browser test.

GET /api/properties/{property_id}/affordable-programs/
{program_id}/inspection-summary reuses existing _property/_item
compliance scope and the INDEPENDENT verified
unit_inspections._scope permissions: ADMIN/MANAGER and
REPORTING.ALL, PROPERTIES.ALL, PROPERTIES.UNITS; managers require
active assigned property. OWNER/tenant/crew do not obtain
inspection access from compliance permission. Only total recorded
count and latest inspection date are returned, NOT unit IDs,
tenant information, private findings, conditions or report bodies.
Query excludes inactive/deleted units and other organizations.
Read-only; no UnitInspectionRecord, Lease, Charge, GL or other
mutation. Frontend evidence panel lets permitted staff cross
reference the existing unit inspection report. Clearly
property-wide and not attached to program or independently
verified: NOT an HQS/NSPIRE/LIHTC inspection or agency clearance.
Two targeted backend regression tests cover scope, owner denial,
permission revocation, excluded inactive units, program archive
and nonmutation.

Original roadmap Phase 4.6 C1 next covers LIHTC Form 8609 building
identification and eventually annual 8609-A. IRS confirms
building-specific agency-assigned BIN and distinct 8609 per
building (multiple allocations may involve multiple forms for
one BIN). https://www.irs.gov/instructions/i8609
Safe next bounded prerequisite: staff-recorded BIN registry per
existing LIHTC program/property, explicitly not a signed IRS
8609, agency allocation, eligible basis, credit certification or
tax return. Require scoped ADMIN/OWNER writes, assigned MANAGER
reads and regression/CI verification. Avoid storing TINs, credits
or sensitive Form 8609 documents in ordinary attachments.
Source must be reviewed again before any actual tax computation
or filing; 8609 is separate from the 1099 provider workflow.

HUD program inspection policy is date- and program-specific; HUD
notices include the revised HCV/PBV NSPIRE transition through
Jan 31, 2027, with Feb 1, 2027 as the revised compliance date.
This is NOT a universal program deadline and no hardcoded
inspection policy/automatic pass-fail has been added.
https://www.hud.gov/reac/nspire-notices

## Phase 4.6 LIHTC per-building agency BIN inventory — VERIFIED 2026-09-28

Product source 952261b3448400dc5c4d1742e5b4b70538c1e2af.
GitHub Actions 36379299678 SUCCESS all six jobs: backend 670 passed,
3 deselected, 14101 warnings in 156.13s; authenticated E2E
3 passed in 6.16s; frontend lint, typecheck, production build,
platform-admin, security, staging-config all green. Generic browser
smoke, not dedicated BIN form E2E. Alembic e1f3a5b7c9d2 (from
d0e2f4a6b8c1); 124 model tables (from 123). Frozen docs/ and
planning parity untouched.

Existing customer Compliance LIHTC program offers "Recorded LIHTC
buildings" panel. New affordable_lihtc_buildings model links org,
property and one LIHTC program to staff-entered building label
and agency BIN, with scoped unique constraint, archive/restore
and immutable redacted audit. Same approved ADMIN/OWNER write,
assigned MANAGER read and same-org active property/program plus
live PROPERTIES.ALL/release.properties.compliance gates. Non-LIHTC
programs cannot use endpoints; tenant/crew and cross-property/org
probes denied. Generic notes/attachments resolver excludes
affordable_lihtc_buildings. Three new focused backend tests cover
lifecycle, repeated BIN rejection, cross-scope probing, release/
permission revocation, invalid input and no Lease/Charge/GL change.

This is an inventory only. The app does NOT validate against housing
agency records, receive signed 8609s, establish qualified basis,
calculate a low-income housing credit, certify resident eligibility,
file IRS returns or submit anything to housing agencies.

IMPORTANT FOLLOW-UP: The current generic BIN input pattern is
deliberately conservative about TINs but overly permissive for some
syntactically invalid agency IDs. IRS Notice 88-91 and current
IRM 3.11.26 prescribe two-letter state prefix, 2-digit allocation
year (IRS also accepts 4-digit year representation) and 5-digit
agency sequence, with dashed examples CT-87-00023 or
CT-1987-00023. Correct validation without changing existing
tables and test malformed shapes; continue to label all BINs
STAFF-RECORDED, never agency verified.
https://www.irs.gov/irm/part3/irm_03-011-026r
https://www.irs.gov/instructions/i8609

## Phase 4.6 Form 8609 per-building reference readiness — VERIFIED 2026-09-28

LIHTC BIN format-source 6ae01cc927264273e5fc8d067da15bd6c45f3faa
already passed all six CI jobs (36379842520) when this session started;
the older handoff had not recorded its verified status. It normalizes
2-/4-digit-year agency BINs and prevents alias duplicates. No rebuild.

New readiness product a28a4dd6b46757a226ce5e8ecd683341b1e9502b;
test-only fix 8a480d05e21a842b1376b1f4d5e595fe58d687de.
First source CI 36382232239 backend 673 passed, 1 failed,
3 deselected: NEW regression mistakenly forbade org ADMIN reading
another same-org property; actual authorization was correct. Revised
test asserts ADMIN same-org access and still denies assigned MANAGER
outside their assigned property. Current CI 36382487436 SUCCESS:
all six jobs; backend 674 passed / 3 deselected /
14235 warnings in 162.82s; E2E 3 passed in 8.67s; frontend,
platform admin, security, staging green. E2E is generic browser
smoke, NOT dedicated Form 8609 panel interaction.
Alembic f2a4b6c8d0e3 from e1f3a5b7c9d2;
125 SQLAlchemy model tables from 124. Frozen docs and parity untouched.

New affordable_lihtc_8609_readiness table holds only one bounded
status per existing active LIHTC building (NOT_RECORDED,
FOLLOW_UP_NEEDED, REFERENCE_IDENTIFIED), org/property/program/building
FKs, timestamp and staff actor; UNIQUE(org,building). Backend
GET/PUT /api/properties/{property_id}/affordable-programs/
{program_id}/buildings/{building_id}/8609-readiness. It reuses
approved compliance authorization: active same-org property/program,
ADMIN/OWNER write, assigned MANAGER read only, release gate and live
PROPERTIES.ALL. No data on archived buildings, no Tenant/Crew,
no cross-org/property ID probes, no generic entity notes/attachments.
No-store GET, redacted append-only audit, regression tests for
lifecycle, authorization, revocation and Lease/Charge/GL nonmutation.
Existing Compliance LIHTC building panel adds a staff status selector.
Staff status is NOT an authentic agency-issued signed original,
allocation certification, owner election, IRS submission,
annual 8609-A, tax credit or verified claim. No document is uploaded.
Form 8609 may have MULTIPLE separate allocations per building;
the single readiness status is aggregate staff follow-up only, not
an inventory of separate authentic forms.
Current IRS guidance:
https://www.irs.gov/instructions/i8609
https://www.irs.gov/instructions/i8609a

Next safe bounded dependency: restricted agency-issued Form 8609
document *archive* under a new dedicated encryption key (no
fallback), scoped to active LIHTC program/building and restricted
ADMIN/OWNER access; staff provenance and immutable list/download
audit. Reuse proven encrypted tax-W9 streaming pattern, not generic
unencrypted attachments, but do NOT conflate IRS signed original or
one-time filing with staff-upload attestation. Allow multiple copies
per building for distinct allocations; avoid declaring eligibility
or calculating basis or credit. Require operator-configured key
before any PDF archive; do not commit key material. Test oversize,
invalid PDF, tamper, scope, role and nonmutation. Signed document
handling needs malware scanning before broad external sharing and
reviewed retention; never expose the raw PDF in generic reports.
After that, any annual 8609-A tracker must explicitly distinguish
acquisition/building vs rehabilitation allocations and tax years;
do not infer applicable fraction or credit from staff metadata.

## Phase 4.6 restricted encrypted Form 8609 staff-scan archive — VERIFIED 2026-09-28

Product source fb448c7b283d1e29950fe1290c5d9c70ca25d51f;
CI 36383165892 SUCCESS all six jobs: backend 678 passed,
3 deselected, 14379 warnings in 159.99s; authenticated
browser E2E 3 passed in 9.96s; frontend, platform-admin,
security, staging green. E2E is existing browser smoke,
NOT dedicated document upload/preview E2E. New migration
c8e0a2f4b6d9 from f2a4b6c8d0e3, 126 model tables from 125.
Frozen docs/ and planning parity untouched.

New encrypted table affordable_lihtc_8609_documents linked to active,
same-org property/LIHTC program and recorded building. Distinct
rows can record multiple separate scans/allocations for one BIN.
PDF ciphertext is stored in a dedicated database LargeBinary field,
encrypted by operator-supplied COMPLIANCE_DOCUMENT_ENCRYPTION_KEY.
No key is committed; settings validates the key is a separate
valid Fernet key and runtime fails closed with 503 if absent.
Never reuse app, application-income or tax-W9 encryption keys.
No user uploads are stored as plaintext multipart temp files.
POST streams bounded 5MB raw application/pdf body, validates
PDF framing, requires staff scan-review attestation and received date;
that attestation is NOT independent agency signature/authenticity
verification or Form 8609 issue/IRS filing confirmation. No
automatic PDF malware scanner: do NOT distribute scans to tenants,
generic notes/attachments, general report downloads or public URLs.
Backend GET list/POST upload/GET download under the existing
/api/properties/{property_id}/affordable-programs/{program_id}/
buildings/{building_id}/8609-documents path. ADMIN/OWNER only,
live PROPERTIES.ALL / release.properties.compliance plus
organization/property/program/building active checks and 404
cross-org/cross-property denials. MANAGER cannot download PDFs even
if allowed to read non-sensitive BIN readiness. All list/download/
archive actions create redacted immutable audit records; returns
use Cache-Control no-store, sanitized Content-Disposition and
no-sniff/sandbox download headers. Generic entity notes/attachments
expressly exclude this document table. Existing customer LIHTC
building panel opens a restricted archive subpanel for staff.
Regression tests cover multiple scans, ciphertext redaction,
PDF/tamper/key failure, role and tenant isolation, gate revocation,
immutable audits and no GL/Charge/Lease mutation.
This is staff-held evidence ONLY, not signed 8609 agency verification,
IRS submission, allowable tax credit, annual 8609-A or eligibility.

NEXT 4.6 safe original-plan C1 subtask: Annual 8609-A
reference-readiness index by existing LIHTC building + explicit
tax year and separate base/acquisition vs rehabilitation
record type (IRS 8609-A instructions distinguish the two).
Explicitly not credit calculation, filing, proof of a 15-year
compliance period, 8609 original verification or agency approval.
https://www.irs.gov/instructions/i8609a

## Phase 4.6 annual Form 8609-A staff reference tracker — VERIFIED 2026-09-28

Source 5b520d93aaa7a4307fb5e8533da552aea210cffd.
CI 36383794588 SUCCESS all six jobs: backend 681 passed,
3 deselected, 14488 warnings in 126.64s; authenticated
E2E 3 passed in 9.49s, frontend, security, platform-admin
and staging green. E2E is generic browser smoke, NOT
dedicated 8609-A interaction. New migration b4d6f8a0c2e5
after c8e0a2f4b6d9, 127 SQLAlchemy tables from 126.
Frozen docs/ and planning parity untouched.

New affordable_lihtc_8609_annual table is only one bounded
record for (organization, LIHTC building, staff-entered tax
year, allocation category); categories BUILDING_OR_ACQUISITION
and REHABILITATION, fixed statuses NOT_RECORDED,
FOLLOW_UP_NEEDED, REFERENCE_IDENTIFIED. Year 1987–2100
is a syntactic bound, not an IRS eligibility determination.
GET/PUT under existing LIHTC property/program/building
scope, manager assigned read only, ADMIN/OWNER write, live
permissions/gates, no-store read, redacted immutable audit.
UI links from existing Compliance LIHTC building index;
there are NO income, eligible basis, applicable fraction,
credit, filing, signed original or sensitive household fields.
Annual category values are staff follow-up metadata, not
a prepared or submitted Form 8609-A. Generic notes and
unencrypted attachments denylist includes annual table.
Three focused tests cover year/category isolation, audit,
cross-organization/property/role/revocation, bounds,
generic target denial and GL/Charge/Lease nonmutation.

IMPORTANT ORIGINAL C1 DEPENDENCIES: agency-issued forms and
staff scans are not authentic issuer verification. IRS 8609
and annual 8609-A require actual eligible basis, owner election,
applicable fraction, compliance history and potentially
separate rehabilitations; do not derive credit from this
tracker. Housing-specific HUD/LIHTC income certifications,
tenant selection plans, utility allowance data, rent
and jurisdiction requirements need reviewed agency policy.
No HUD/LIHTC eligibility, HAP, tax calculation or IRS
transmission has been delivered.

## Phase 4.6 compliance key rewrap + read-only status — VERIFIED 2026-09-28

Existing product commit 40317c96f7b564abce3483b088727c25c53a6b2b
already implements admin-only scoped Form 8609 historical ciphertext
key rotation. CI 36384377433 SUCCESS all six jobs. Do not repeat.

This session added read-only, bounded, audited rotation readiness:
source 8c5e2a0973b40e414a68f2b8242621324f0e1419 and test-only
direct-route invocation correction
a8adc7dc2f47a40085c1203b38dd2254d778a907.
CI 36412399420 SUCCESS all six jobs: backend 685 passed,
3 deselected, 14644 warnings in 167.94s; authenticated
E2E 3 passed in 9.57s. Frontend, security, platform-admin,
staging passed. Existing general browser smoke, NOT dedicated
rotation UI E2E. No migration, Alembic b4d6f8a0c2e5; 127 tables.

GET /api/properties/{property_id}/affordable-programs/{program_id}/
buildings/{building_id}/8609-documents/rotation-readiness
is ADMIN-only, rechecks the existing property/program/building gate,
live org/role/permission boundary, and reads at most 25 scanned
records per page. It validates ciphertext against the current and
configured historical keys; counts only current-key vs needing
rewrap, no decrypted PDF or key material leaves server/audit.
Fails closed on missing historical key, malformed/invalid scan,
scope probing or revoked permissions. Redacted immutable audit
event records status access. No documents, leases, charges, GL
or financial data are mutated. HTTP response has no-store.
This proves ONLY per-page/per-building readiness; old shared keys
must NOT be retired until all relevant buildings/organizations
and encrypted stores are audited. No generic raw document access.

NEXT UI BATCH: show the read-only paginated administrator status
inside existing restricted Form 8609 archive with explicit
cross-building/organization warning. Avoid exposing to OWNER
or MANAGER, who may have archive/readiness access but cannot rotate
keys. Existing backend authorization remains authoritative.

## Phase 4.6 administrator Form 8609 rotation UI — VERIFIED 2026-09-28

Source 82c8ede338b9030acfd993bbe6888eae7e07ddce.
Full CI 36413219901 SUCCESS all six jobs:
686 backend tests passed, 3 deselected, 14678 warnings in
146.61s; browser E2E 3 passed in 8.78s; frontend lint,
typecheck, production build, platform-admin, security and
staging-config SUCCESS. No migration: b4d6f8a0c2e5, 127
SQLAlchemy tables; frozen docs/ and parity unchanged.
Browser E2E is general smoke, NOT a dedicated rotation UI test.

Existing frontend/src/components/property/Affordable8609Archive.tsx
now exposes an administrator-only, manually requested, paginated,
read-only inspection of the VERIFIED backend rotation-readiness
endpoint. Admin role resolved from existing /auth/me; OWNER and
MANAGER do not see the control and backend remains authoritative.
Shows only per-building counts of scanned/current-key/pending;
does not transmit PDF contents or keys, does not initiate rotation,
and tells the user explicitly that each building/organization
must be checked before global historical key retirement.
After archive upload, status resets to avoid stale indication.
Added focused backend regression for empty archive pagination,
live permission revocation, no-store status and absence of
GL/Lease mutations.

NEXT Phase 4.6 original C1 safe prerequisite: extend existing
staff affordable_program_evidence AGENCY_GUIDANCE category with
bounded provenance of independently reviewed public agency guidance,
if this can be added without leaking sensitive household data,
turning staff links into legal certification, or duplicating
evidence/document stores. Consider scheme/host validation,
staff-check date, live org/program scope, permission revocation,
and no accounting mutation. Jurisdiction/agency-specific actual
eligibility and HUD/HAP rules still require verified authoritative
source specifications before enforcement. Do not claim the
provenance field proves a policy is effective or authoritative.

## Phase 4.6 staff public agency-guidance provenance — VERIFIED 2026-09-28

Source 3f2d5d4b60f9eb29ced0aa68c182e41fe51df0e1;
URL authority/backslash hardening d5b63d0310b008489cb645e9d1cc74ab16ea4245.
CI 36414139582 SUCCESS six jobs: backend 688 passed,
3 deselected, 14709 warnings in 181.86s, authenticated E2E
3 passed in 10.21s. Frontend lint, typecheck and production build,
platform-admin, security and staging success. Generic E2E,
NOT a dedicated public-guidance UI browser test.

Migration c5e7a9b1d3f6 from b4d6f8a0c2e5 adds nullable
source_url and source_checked_on to the EXISTING table
affordable_program_evidence. 127 model tables unchanged.
All frozen docs/ and planning parity unchanged.

Existing property compliance Program Evidence panel, not new
parallel evidence/document storage, now allows ADMIN/OWNER to
record an optional PUBLIC HTTPS agency-guidance URL and
staff-checked date ONLY in AGENCY_GUIDANCE category when a
staff reference is recorded. Assigned MANAGER may see its
property-scoped staff index but cannot write. Existing live
release/PROPERTIES.ALL/property/program/assignment scope reused.
Link is not fetched/parsed for authoritative legal compliance,
not an official effective policy, not an agency signature,
not a household record, not HUD eligibility, not an AMI or
tax-credit calculator. It may be inaccurate, outdated or fake;
the UI visibly labels it STAFF-SUPPLIED/UNVERIFIED.
Only HTTPS public host links accepted; reject private/intranet
hostnames, raw IPs, embedded credentials, nonstandard ports,
whitespace, backslash authority ambiguities, too-long URLs
and checked dates in the future. Do not log full link URL in
immutable audit: only boolean public_reference_present metadata.
No GL, Lease, Charge or protected household mutation.
Focused tests cover validation, role/org/property scope,
null-on-unrecorded, audit redaction and nonmutation.
No public policy legal verification has been performed.

NEXT: remaining Phase 4.6 C1 substantive program-dependent tasks
require real authoritative agency/jurisdiction eligibility,
income-certification/privacy, HAP and AMI source requirements.
These are NOT represented as completed or safe to automate
without those sources/contractual permissions. The independent
original roadmap Phase 4.7 C2 HOA foundation (association and
property scope, no dues/penalties/board governance yet) is
available to continue without fabricating HUD/LIHTC rules.
Reuse existing property/release/org authorization and audit.
Never post HOA fees or violate accounting locks from a
staff-inventory entry.

## Phase 4.7 C2 HOA scoped registry and property UI — VERIFIED 2026-09-28

Backend source d929d71c50b40849e0f5fa6849b294ca87a4780b;
UI + fourth regression source 38dee8344851cac33b1f792e16a529211db86782.
Full CI 36424060872 success for backend source: 691 passed,
3 deselected, 14790 warnings in 171.54s; 3 browser E2E
passed in 9.65s. Final UI/source CI 36425025893 success
all six jobs: backend 692 passed, 3 deselected,
14820 warnings in 172.29s; browser E2E 3 passed
in 10.15s; frontend lint/typecheck/build, platform admin,
security, staging all green. Browser E2E remains generic
smoke, not a dedicated HOA interaction test.
Alembic d6f8a0b2c4e7 after c5e7a9b1d3f6, 129 model
tables from 127. Frozen docs/ and planning parity unchanged.

Staff association and many-to-many property inventory in
hoa_associations + hoa_property_memberships. CRUD at
/api/hoa/associations (GET list/one, POST, PUT, DELETE).
Reuse existing hybrid release.properties.compliance and live
PROPERTIES.ALL permission, organization-isolation and active
property checks. ADMIN/OWNER write; MANAGER read only their
assigned active properties, with no empty association-name
leak. TENANT/CREW and deactivated users denied. Cross-org
association/property probes fail closed. Case-folded
org-unique names, soft archive, redacted append-only audit,
no-store reads; generic notes/attachments denylist excludes
the two new registry tables. Four focused tests cover scoped
CRUD, many-to-many membership, name/ID validation,
revocation, no GL/Charge/Lease mutations.

Customer property detail > Compliance now includes
HoaAssociationsPanel, within the existing compliance gate.
Owners/admins can record multiple property links, attach
current property to existing association, unlink, archive;
managers read assigned memberships only. Explicit UI notices
that the recorded association is NOT legal verification,
member consent, assessment authorization, dues, penalties,
board governance or a booked liability. It posts no finance.

Original Phase 4.7 C2 is STILL IN PROGRESS. Exact next
dependent subtask: an explicitly recorded HOA property
contact/member responsibility roster (reuse the verified
independent org-scoped Contacts directory, do not infer from
Property.owner_id or tenant identities) and draft recurring/
special dues assessment configuration subject to legal,
payer identity and central GL controls. No automatic charge,
GL posting, reserve transfer, violation, board vote or
IRS/regulatory certification from staff inventory metadata.

## Phase 4.7 scoped HOA Contact references and UI — VERIFIED 2026-09-28

Source 404e6dcccff779c63311018221544d8508d929ff;
TSX parser fix 8b25ab6240c7cd69c1708d28002f583b526af71c.
First CI 36426173436 exposed a new frontend parsing failure;
corrected source CI 36426366891 SUCCESS all six jobs:
backend 694 passed, 3 deselected, 14893 warnings in 175.75s;
E2E 3 passed in 9.63s; frontend lint/typecheck/build,
platform-admin, security, staging passed. E2E is generic smoke,
not dedicated HOA UI. Migration e7a9b1c3d5f8 after
d6f8a0b2c4e7, 130 model tables (was 129).
Frozen docs/ and parity untouched.

New hoa_contact_links is an explicit scoped reference to the
existing independently managed organization Contacts directory.
It is NOT proof of legal HOA membership, ownership, voting rights,
registered agent identity or dues responsibility. POST/GET/DELETE
/api/hoa/associations/{id}/contacts route, requiring live
association/property membership, org/active Contact,
PROPERTIES.ALL + PEOPLE.CONTACTS + compliance hybrid gate,
admin/owner writes, assigned manager reads only. Cross-org,
inactive and unassigned scopes fail closed. Per-property unlink
and association archive soft-disable contact references, so
relinked property cannot silently regain old contacts; explicit
staff action is necessary. Immutable redacted audit, no-store
read, generic notes/attachments denylist, no GL/Charge/Lease
changes. Two focused regression tests cover these contracts.
Existing property Compliance HOA panel now opens nested
HoaContactsPanel, with explicit no-liability message.
No tax identifiers, owner/tenant liabilities or payment
instructions inferred from simple contact references.

NEXT: user-entered DRAFT HOA recurring/special proposal
configuration, association/property scoped and read-only to
assigned manager. No true assessment, due date enforcement,
automatic charge, GL booking, reserve accounting or fine
without verified governing authority, recipient ownership/
payer obligation, board approval, accounting policies.

# Exact next work: obtain and review real HOA legal source

1. Read complete root AI_HANDOFF.md; verify HEAD and latest CI.
   Last VERIFIED product 97ac854cfb7653f95f4e23d173cfb0706362bf8a;
   run 36442794100 SUCCESS (715 backend passed / 3 deselected;
   3 browser E2E passed); migration f0b2c4d6e8a1 / 135 tables.
2. Governing-evidence backend/UI is VERIFIED; do not repeat it.
   This indexes *private existing property attachments* per HOA and
   property and labels them STAFF-SUPPLIED/UNVERIFIED. It does NOT
   establish document authenticity or applicable law. Source documents
   must be provided before any substantive legal compliance work.
3. Obtain and review actual association declaration/CC&Rs, bylaws
   and amendments, applicable written rules/ARC guidelines, and
   property jurisdiction (state/county/local ordinances), together
   with legally authorized actor/notice/cure/hearing and approved
   assessment/reserve policy. Reconcile documents with current law,
   dated scope, identity, payer and board authority before issuance
   or finance. Never extrapolate source rules from staff inventory.
4. Do not invent official HOA violation issuance, ARC approvals,
   board voting eligibility, dues payer, reserve or locked-period
   postings. No lease/charge/GL mutation from evidence index.
   Phase 4.6 HUD/LIHTC substantive controls similarly require real
   authoritative property/program/agency terms. Preserve originals.
5. If authentic source documents/jurisdiction are unavailable, stop
   as a genuine legal/data blocker and identify the required inputs,
   not a false completed task or another duplicate draft registry.
   When sources exist, proceed narrowly with authorized Phase 4.7 C2
   actions in original dependency order, test in CI, update handoff.
   Only the existing branch; don't touch main or frozen docs.

## Session start for successor

Continue ONLY yasirskhan/property-platform branch
chatgpt/checkpoint-005-safety. Read entire root AI_HANDOFF.md,
verify HEAD and GitHub CI. Last VERIFIED source
97ac854cfb7653f95f4e23d173cfb0706362bf8a;
CI 36442794100 SUCCESS all six jobs: 715 backend passed,
3 deselected; 3 browser E2E passed. Alembic f0b2c4d6e8a1,
135 tables. HOA association registry, contacts, staff-only
assessment drafts, observations, meeting planning, ARC interest
intake and private governing-document evidence backend/UI are
VERIFIED. Do not reimplement. Actual governing docs and
jurisdiction/authority are not supplied/validated: THIS IS
THE NEXT LEGAL/DATA BLOCKER. Do not infer liability, deadlines,
official approvals/fines, reserve postings or board rules.
No unrelated frozen docs changes; no main/new branch; source
CI verification required; do not request Work mode.

## Phase 4.7 C2 HOA assessment draft source — VERIFIED 2026-09-28

Backend source d993b1afa2905e626f8ba6af233c05f236d5313c;
test-fixture correction b78f8fd8569a3b0a3c95699d3461123cbdcd9c4a.
Initial CI 36427514427 FAILED four new-test fixture setup errors:
monkeypatch targeted the assessment router rather than the existing
HOA authorization helper. Corrected CI 36428959926 SUCCESS all six
jobs, 698 backend passed, 3 deselected, 14988 warnings in 151.75s,
3 browser E2E passed in 6.24s; frontend, platform-admin, security,
staging green. This is source verification, not dedicated assessment
browser interaction E2E. New migration f8b0c2d4e6a9, 131 tables.
Backend staff DRAFT recurring/special proposal API is available:
GET/POST/PUT/DELETE /api/hoa/associations/{id}/draft-assessments.
No APPROVED status, payer, payable/receivable, Charge, GL, notice,
assessment issuance, automatic billing, fines or reserve movement.
Organization and association property link, active staff assignment,
compliance gate and PROPERTIES.ALL permission rechecked live;
ADMIN/OWNER write, assigned MANAGER read, TENANT/CREW denied;
archived/unlinked records fail closed. Generic unencrypted notes and
attachments cannot target proposals. Audit metadata redacted.
No changes to frozen docs/ or planning parity.

## Phase 4.7 C2 HOA assessment customer UI — VERIFIED 2026-09-28

Source ead950a0b7dc0aa0bae18c44513db5ccbbbe28e2 added
HoaDraftAssessmentsPanel.tsx to existing property Compliance HOA panel
and one additional API contract test. CI 36429898691 SUCCESS all six
jobs: 699 backend passed, 3 deselected, 15017 warnings in
176.77s; 3 authenticated E2E passed in 9.19s; frontend,
platform-admin, security and staging passed. Existing generic
browser smoke, NOT a dedicated HOA draft UI interaction test.
The panel offers read-only manager viewing, ADMIN/OWNER create/edit/
archive of staff DRAFT amounts/frequency/dates, and explains clearly
that no legal assessment, payer, approved charge or GL is created.
No migration. Source head f8b0c2d4e6a9 and 131 tables remain verified.


## Phase 4.7 C2 HOA draft scope integrity — VERIFIED 2026-09-28

Source fe1449420ab89723973e4e3730ce48d917f58f36;
CI 36431000854 SUCCESS all six jobs, backend 700 passed,
3 deselected, 15059 warnings in 136.91s; 3 browser E2E
passed in 9.35s. No migration: f8b0c2d4e6a9 / 131 tables.
On association/property unlink or association archive, active
staff assessment draft assumptions are softly archived with
redacted immutable audit; a later relink cannot resurrect
obsolete amounts. Regression tests cover relink, archive,
per-org isolation, zero Charge/GL/Lease effects.

## Phase 4.7 C2 staff observation prerequisite — VERIFIED BACKEND + UI

This new source batch adds only organization/property/association-
scoped staff observations for possible HOA issues. It is NOT
an adjudicated violation, an issued notice, a cure deadline, a
fine, a legal obligation, a hearing or a GL/tenant charge.
ADMIN/OWNER write; assigned MANAGER read. Backend checks live
association membership, compliance release gate, org and
property scope, and PROPERTIES.ALL permission. Generic notes/
unencrypted attachments denylisted; audit metadata excludes
free-text details. Association unlink and archive soft-disable
old staff records so relink cannot silently reactivate them.
Migration c7e9a1b3d5f2 adds hoa_observations (132 model tables).
Focused tests assert no legal/finance fields and no GL/Charge/
Lease mutation. Backend source fixed duplicate migration-revision
ID at commit 60671d5869191c261f06e28149995e477c1fda12;
CI 36432576387 SUCCESS all six jobs, backend 704 passed,
3 deselected, 15165 warnings in 178.27s, E2E 3 passed in
9.02s. Customer UI source d061925d5e29dee69833d13dcb8f6aaf785c7479;
CI 36436896287 SUCCESS all six jobs, backend 705 passed,
3 deselected, 15194 warnings in 156.31s, E2E 3 passed in
8.14s. Generic browser smoke, not dedicated observation UI E2E.
Frontend lint/typecheck/build, security, platform-admin and staging
green. New HoaObservationsPanel in existing property HOA
Compliance section: ADMIN/OWNER create/edit/archive, assigned
MANAGER read-only. Explicit non-legal/no-fines/no-GL labeling,
no tenant notifications or charges. Focused additional regression
checks manager payload visibility and no unauthorized archive or
finance posting. Frozen docs/ and parity unchanged.
No frozen docs/ or planning parity changes in this batch.


## Phase 4.7 C2 HOA staff meeting planning — VERIFIED 2026-09-28

Source 0073e49ccf84d5e8b6bfe48c459c7b4a0bb8b025.
CI 36438320448 SUCCESS all six jobs; backend 708 passed,
3 deselected, 15297 warnings in 180.28s; generic authenticated
E2E 3 passed in 8.21s; frontend lint/typecheck/production build,
platform-admin, security and staging green.
Migration d8f0a2b4c6e9 from c7e9a1b3d5f2 adds
hoa_meeting_drafts (133 SQLAlchemy tables). Planning parity and
frozen docs/ untouched.
Association/property/org-scoped staff draft CRUD at
/api/hoa/associations/{id}/meeting-drafts; existing live
PROPERTIES.ALL and compliance release gate, staff role and
manager assignment authorization rechecked. ADMIN/OWNER writes,
assigned MANAGER reads, TENANT/CREW denied. One hundred percent
staff planning: title, proposed date and tentative agenda; no
official meeting notice, minutes, votes, board quorum,
board membership certification, fines, dues or GL effects.
Generic notes/attachments denylist applies. Unlink/archive
soft-disable staff drafts, no hidden resurrection on relink.
Redacted append-only audit, no-store reads, bounded records.
Customer property HOA panel includes HoaMeetingDraftsPanel.
Three focused tests cover CRUD, org/role/assignment/revocation,
forbidden governance fields, no GL/Charge/Lease changes and
unlink/archive. E2E is generic browser smoke, NOT dedicated
meeting UI E2E. Formal board portal is NOT VERIFIED.

## Phase 4.7 C2 ARC staff intake — VERIFIED 2026-09-28

Verified source 711800ce4d02aa5c1e52f5703b8817740832c24e;
full CI 36439808118 SUCCESS all six jobs: backend 711 passed,
3 deselected, 15400 warnings in 182.75s; browser E2E 3 passed
in 9.57s; frontend lint/typecheck/build, platform-admin, security,
staging all green. General browser smoke, NOT dedicated ARC UI E2E.
Migration e9a1b3c5d7f0 from d8f0a2b4c6e9 / 134 model tables.
Property/association/org scoped staff architectural-interest
intake GET/POST/PUT/DELETE under /api/hoa/associations/{id}/arc-intakes,
existing live PROPERTIES.ALL + compliance gate; ADMIN/OWNER write,
assigned MANAGER read, TENANT/CREW denied. No applicant identity,
issued application, decision/denial, permit, statutory review period,
fee, charge, GL or legal notice. Customer HoaARCIntakePanel in
existing property HOA Compliance section; staff-only captions.
Association unlink/archive soft-deactivates prior intake; relinking
does not resurrect. Redacted append-only audit, no-store reads,
generic notes/attachments denylist. Three focused tests cover
CRUD, cross-org/assignment/permission, input extra-field rejection,
audit and zero GL/Charge/Lease effects, and unlink/archive.
Frozen docs/ and planning parity unchanged.


## Phase 4.7 C2 dependency boundary after ARC intake — 2026-09-28

Three consecutive meaningful source batches in this session are VERIFIED:
- Staff observations backend source 60671d5869191c261f06e28149995e477c1fda12
  CI 36432576387 SUCCESS, 704 backend passed / 3 E2E.
- Staff observation customer UI source d061925d5e29dee69833d13dcb8f6aaf785c7479
  CI 36436896287 SUCCESS, 705 backend passed / 3 E2E.
- Staff meeting planning backend/UI source 0073e49ccf84d5e8b6bfe48c459c7b4a0bb8b025
  CI 36438320448 SUCCESS, 708 backend passed / 3 E2E.
- Staff ARC intake source 711800ce4d02aa5c1e52f5703b8817740832c24e
  CI 36439808118 SUCCESS, 711 backend passed / 3 E2E.

The original Phase 4.7 C2 still requires real HOA assessments,
violations, statutory notice/cure, fines, hearings, board portal
governance/meeting/vote records, ARC applicant/decision workflow,
reserve studies/fund accounting and governing document delivery.
These are NOT complete. Property manager's staff-only records do not
create association authority, property/owner payer liability,
tenant charges, voting eligibility, legal decisions or accounting
permission. Do not convert proposal/intake fields into legal action
until authoritative governing documents and jurisdiction-specific
rules are provided and approved, and finance is centrally posted
through the verified GL with lock/idempotency/owner isolation.
Project docs/ source-of-truth and parity remain unchanged. Last CI
only verifies general browser smoke; specialized HOA interaction
E2E is still needed before release.

Exact next responsibly actionable work: obtain/review the actual
HOA governing documents, HOA jurisdiction, service/notice rules,
authorized decision maker, who pays dues and legal approval/
reserve policies. If these are unavailable, record a genuine
legal/data blocker, do not fabricate policy or relabel safe drafts
as completed full workflows. Independent later phases should
follow the original dependency order; no unapproved roadmap edits.

## Phase 4.7 C2 governing-document private evidence — VERIFIED 2026-09-28

Backend source: 20c982700e1de1efc98921b0ab0f6dfa06c1ba7d.
Customer property HOA Compliance panel and fixture fix:
270e37b1b4e3e77089565fd07b0b411addb3b8c6.
Nested-form correction: 97ac854cfb7653f95f4e23d173cfb0706362bf8a.
Final full CI 36442794100 SUCCESS all six jobs:
backend 715 passed, 3 deselected, 15562 warnings in 188.05s;
generic authenticated E2E 3 passed in 9.30s; frontend
lint/typecheck/production build, platform-admin, security,
staging-config SUCCESS. This is generic browser smoke, NOT
dedicated HOA evidence upload/link/download interaction E2E.
Previous runs 36442523063 and 36442730744 were superseded/
cancelled after newer source commits, not verified source runs.
Migration f0b2c4d6e8a1 after e9a1b3c5d7f0 adds one
hoa_governing_evidence metadata table: 135 SQLAlchemy tables.
Project docs/ and planning parity unchanged. No local tests run.

New source index does NOT duplicate file bytes: references existing
private EntityAttachment on the same org/property under an active
HOA association membership, accepted only PDF/DOC/DOCX extensions,
staff-supplied category, never verification/approval/certification.
Routes GET/POST/DELETE under
/api/hoa/associations/{association_id}/governing-evidence.
Existing live release.properties.compliance / PROPERTIES.ALL and
release.documents.attachments, active actor, org/property/association
membership and assignment scope rechecked on every call.
ADMIN/OWNER create/archive, assigned MANAGER read-only;
TENANT/CREW denied. No external signature, governing-law review,
recipient delivery, association authentication, official copy
certification or reserve policy decision is represented.
Existing universal attachment downloads/lists enforce live HOA
scope for *actively indexed* document links, preventing a crew
member from reading a newly linked document via generic route.
Active indexed files cannot be shared via generic tenant/owner
attachment sharing. Unlink/archive of association/property
soft-archives evidence metadata to prevent relink resurrection.
A deleted/private-share-changed source is hidden on evidence list.
No legal deadline, fines, board action, Charge, Lease or GL posting.
Staff document references are not legal proof of applicable rule.

Existing property HOA customer panel opens governing-evidence
section, lists/downloads live scoped private source references,
and lets admin/owner link/archive source file pointers. Reuses
verified EntityAttachments property uploader without nesting
forms. UI states STAFF-SUPPLIED/UNVERIFIED throughout.
Four focused backend tests cover scope, private/share controls,
archive/relink, role/feature revocation, audit and nonmutation.
No real HOA governing documents were supplied for legal review;
no authentic jurisdiction-specific authority has been validated.
Follow exact-next-work requirements above before any official action.
