# Phase 4.17 | DoorLoop migration contract and delivery plan

## Source-independent backend foundation (VERIFIED at 8323b120, CI 39152511094)

Platform staff can create organization-scoped DoorLoop DRAFT migration runs,
retrieve a run, list active-organization runs, and check provider and per-run
source readiness. Admin, Tech and Dev may create runs and inspect sources;
Support may only view, and Sales/Billing cannot access these actions.

Staff can inspect an explicitly supplied CSV or XLSX export within the shared
file parser's limits (10 MB, 10,000 rows, 100 columns, bounded spreadsheets).
Inspection returns header inventory, format, row count and SHA-256 of the
source file. Inspection does not persist or echo source rows, propose provider
field mappings, stage a file or mutate customer data. Credential-like source
headers, ambiguous duplicate headers and macro-enabled/legacy spreadsheets
are rejected. Responses are not cacheable.

DoorLoop run list, get and create routes use a bounded output schema that permits
only the same explicit nonsecret metadata fields as other platform migrations.

The hosted backend test includes a PostgreSQL-specific integration test,
using an independent database session to verify DRAFT run persistence and its
atomic redacted audit event. It skips when no PostgreSQL test database is
configured.

The run model's `provider` is `VARCHAR(32)` without an enum or CHECK
constraint in `d46f8a0c2e91`; `DOORLOOP` therefore requires no new DB
migration. Provider and active-organization filters are mandatory at reads.

A second optional read-only step accepts staff-proposed generic column mapping
and an **exact SHA-256 fingerprint required from inspection**. It reports
aggregate missing-field and duplicate nonempty source-identifier counts only.
Unknown/duplicate mapping fields, credential labels and changed files fail
closed. The preview does not certify a DoorLoop source-to-target relationship
or persist source bytes, rows or mappings.

## What is NOT enabled

- No DoorLoop API token handling, API polling or undocumented scraping
- No assumption about source record identifiers or resource relationships
- No staged customer data or auto-applied mapping
- No lease, property, owner, tenant, vendor or finance posting
- No customer record overwrite, replay, or controlled commit

## Required evidence before staged imports

1. Customer authorization and permitted DoorLoop export or documented API.
2. Authentic export examples for each supported resource, with source version,
   resource record grain, stable IDs and parent/relationship fields verified.
3. Financial/accounting signs, balances, currency and cutoff contracts before
   any GL, AR/AP, payment or deposit migrations.
4. Explicit staff mapping, validation/reconciliation, source-file fingerprint
   retention and preview before any customer mutation.
5. Controlled idempotent import, durable identity claims, audit and precise
   replay tests only after a verified source-to-target contract exists.

## Next milestone

The independent DoorLoop backend foundation passed all six hosted checks at
commit `8323b120` (run `39152511094`). Verify hosted CI for the operator UI
repair at `3e06394e` and for subsequent operator run lookup/readiness work.
Once verified, full vendor migration still requires authorized export evidence,
stable vendor IDs, relationships and accounting semantics; do not invent these.

## Platform staff workflow (new, provisional pending exact-SHA CI)

The Platform Admin dashboard now links a dedicated DoorLoop migration console
for Admin, Tech, Support and Dev. It presents the provider readiness contract,
active-organization run discovery and run metadata, with DRAFT creation for
Admin/Tech/Dev only. Authorized writers can inspect a local CSV/XLSX export,
review its exact SHA-256, choose explicit generic quality labels/columns and
an optional identity, and request a fingerprint-bound nonpersistent quality
preview. Changing the selected run, file or sheet clears stale review state.
Support has metadata-only access and no file controls; unauthorized roles
cannot access the protected backend endpoints. No vendor-specific mappings,
source persistence, staging, customer mutation, or controlled commit were added.

The prepared follow-up operator page supports opening a specific authenticated,
provider-scoped run ID when it falls outside the latest 100 in the dropdown,
and shows per-run contract blockers without retaining source content. This
follow-up remains provisional until committed and checked at its exact SHA.

## Official source acquisition and access evidence (2026-10-18)

DoorLoop's own [Reports and Report Filters guide](https://support.doorloop.com/en/articles/8272427-introduction-to-doorloop-reports-and-report-filters)
states that reports can be exported as PDF, CSV or Excel. Only customer-approved
CSV/XLSX exports are accepted by our current bounded in-memory inspector; PDF
is not an import source. Reports may be filtered and column-customized. Record
report identity, export timestamp, selected columns, filters and cutoff before
mapping, but do not infer stable IDs from display names, lease relationships
from shared labels, or debit/credit meaning from generic financial columns.

DoorLoop's [official API help article](https://support.doorloop.com/en/articles/7902913-api-documentation-and-where-to-find-help)
links to https://api.doorloop.com/. The provider [integration program](https://www.doorloop.com/partner)
notes that API access requires DoorLoop approval. Published existence of an API
is **not** evidence that this installation has credentials, authorized tenant
access, or a verified specific resource payload/accounting contract. Do not
implement undocumented endpoints or scrape internal web network calls.

The operator console now includes an explicit export-acquisition guide and
prevents file, sheet and run switching during in-flight inspection/review.
Both are independently deliverable staff usability/safety work, not a claim
that customer-data migration is implemented. The guide and the UI controls
require an exact-SHA hosted CI pass before marking this batch VERIFIED.
