# Phase 4.17 | DoorLoop migration contract and delivery plan

## Current implementation (provisional, exact-SHA CI required)

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

DoorLoop run list, get and create routes use a bounded output schema that permits\nonly the same explicit nonsecret metadata fields as other platform migrations.\n\nThe hosted backend test includes a PostgreSQL-specific integration test,\nusing an independent database session to verify DRAFT run persistence and its\natomic redacted audit event. It skips when no PostgreSQL test database is\nconfigured.\n\nThe run model's `provider` is `VARCHAR(32)` without an enum or CHECK
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

Finish exact-SHA hosted CI for the source-inspection and durable-run regression
batch. If all six jobs pass, document the new verified baseline. Then pursue
contract-backed source discovery using actual authorized exports, or move to
another independent roadmap feature instead of inventing DoorLoop mappings.
