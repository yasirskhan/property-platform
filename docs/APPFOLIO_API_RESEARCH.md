# APPFOLIO API RESEARCH — REFERENCE FOR FUTURE TESTING

Status: **REFERENCE ONLY — NOT A PRODUCTION CONNECTOR CONTRACT**

Last reviewed: 2026-10-01

Purpose: preserve public AppFolio API material and third-party research so the
project can revisit and test an optional AppFolio API migration path after the
core migration/import system is complete.

This file does **not** authorize live provider transport by itself. Do not
commit AppFolio credentials, session cookies, Client Secrets, access tokens, or
customer data to the repository.

## Source quality legend

- **OFFICIAL** — published by AppFolio.
- **MIRRORED / UNVERIFIED COPY** — appears to reproduce AppFolio documentation,
  but is not hosted by AppFolio. Useful for research and test planning only.
- **THIRD-PARTY IMPLEMENTATION** — independent open-source implementation.
  Useful for corroboration and interoperability research, not an authoritative
  contract.
- **UNOFFICIAL WEB-INTERNAL APPROACH** — relies on AppFolio web-session/internal
  behavior. Do not use as the production migration transport.

## 1. OFFICIAL — AppFolio Stack API resource/field inventory

Source:
https://www.appfolio.com/stack/partners/api

What it currently exposes publicly:

- resource names and descriptions;
- field inventories for many API resources;
- examples include Properties, Units, Tenants, Owners, Property Groups,
  General Ledger Accounts, General Ledger Details, Bills, Charges,
  Journal Entries, Tenant Ledgers, Bank Accounts, Work Orders and more.

Examples relevant to migration mapping:

### Properties

Public fields include identifiers and common property attributes such as:

- Id
- Address1 / Address2
- City
- State
- Zip
- Name
- PropertyType
- HiddenAt
- LastUpdatedAt
- PropertyGroupIds
- MaintenanceNotes

### Units

Public material includes unit identifiers, property relationships,
LeasingType, hidden/update filters and RentReady-related information.

### Tenants

Public material includes:

- Id
- OccupancyId
- UnitId
- PropertyId
- FirstName / LastName
- CompanyName
- Status
- PhoneNumber
- Email
- MoveInOn / MoveOutOn
- LeaseSignedDate
- LeaseStartDate / LeaseEndDate
- PrimaryTenant
- TenantType
- HiddenAt / LastUpdatedAt

### Owners

Public material includes:

- Id
- CompanyName
- FirstName / LastName
- Email / PhoneNumber
- address fields
- HiddenAt
- MaintenanceNotes

### Accounting

The official public inventory also describes General Ledger Accounts,
General Ledger Details, Bills, Charges, Journal Entries and Tenant Ledgers.

Use this page as the primary public field-name reference when reconciling
future source mappings.

## 2. OFFICIAL — AppFolio partner program

Source:
https://www.appfolio.com/stack/become-a-partner

AppFolio describes its partner program, API documentation, and integration
partner process here.

Treat partner-only or authenticated documentation obtained later as higher
authority than mirrored/public third-party material in this file.

## 3. MIRRORED / UNVERIFIED COPY — Reports API v2 documentation

Source:
https://gist.github.com/omnimaxxing/2b016c518b4063fd536549b12694b7b7

The gist identifies itself as:

- "AppFolio Reports API (2.0.0)"
- proprietary API documentation

It currently describes a likely Reports API v2 contract including:

- REST;
- HTTP Basic Auth;
- Client ID + Client Secret;
- JSON request/response format;
- customer database subdomain;
- POST requests shaped like:
  `https://{database}.appfolio.com/api/v2/reports/{report_name}.json`;
- Reports API credentials reportedly generated from AppFolio's
  General Settings -> Manage API Settings -> Reports API Credentials;
- report-specific filter bodies;
- pagination / next-page behavior;
- rate-limit guidance;
- HTTP error behavior.

IMPORTANT: because this copy is not hosted by AppFolio, do **not** treat its
transport/authentication details as authoritative production requirements
without validating them against current authenticated AppFolio documentation
or a legitimate AppFolio test account.

Keep it because it is valuable for:

- adapter interface design;
- mock contract fixtures;
- test-case planning;
- identifying questions to verify when credentials/documentation are obtained.

## 4. THIRD-PARTY IMPLEMENTATION — AppFolio MCP Server

Source:
https://github.com/NightSquawk/appfolio-mcp-server

Reviewed reference:
https://github.com/NightSquawk/appfolio-mcp-server/blob/v1.0.0/README.md

The project reports catalog coverage for:

- 137 Reports API v2 reports;
- 156 Database API v0 operations.

It exposes list/describe/call tooling over local catalogs. This is useful for
discovering likely report/endpoint names and comparing parameter/response
shapes.

Do not automatically import its catalogs into production code. If used later,
compare every field/endpoint needed by our migration against the current
AppFolio contract/test account first.

## 5. UNOFFICIAL WEB-INTERNAL APPROACH — Integuru AppFolio API

Source:
https://github.com/Integuru-AI/AppFolio-Unofficial-API

Example implementation:
https://github.com/Integuru-AI/AppFolio-Unofficial-API/blob/main/appfolio_integration.py

This implementation uses AppFolio web-session/cookie behavior and internal web
requests.

It may be useful for understanding what the AppFolio web application does, but
it is **not** the approved production transport for this project.

Do not build production migration around:

- scraped session cookies;
- browser-login tokens;
- undocumented internal web endpoints;
- UI-specific request behavior.

Those interfaces can change without notice and have different security/
authorization expectations from an official API.

## 6. Intended migration strategy

Primary migration path should remain export/import friendly:

1. customer exports AppFolio-owned data/reports to CSV/XLSX where available;
2. customer uploads those files to our platform;
3. detect source report/type;
4. validate and map by stable source IDs;
5. dry-run;
6. surface duplicates/errors/reconciliation totals;
7. commit through the existing replay-safe migration contracts;
8. preserve source-to-target mappings and recovery visibility.

Optional future path:

- AppFolio Reports API for customers who legitimately have API access;
- Database API only after legitimate access and current contract verification.

CSV/XLSX migration must not depend on the optional API connector.

## 7. Future API test checklist

When the platform is otherwise ready and a legitimate AppFolio sandbox/test
account or authenticated contract is available, verify all of the following
before enabling live transport:

### Authentication

- current auth mechanism;
- credential creation/revocation;
- credential scope;
- read-only vs write access;
- customer/database identifier semantics;
- secret rotation;
- failure behavior for revoked/invalid credentials.

### Base URLs and transport

- sandbox base URL;
- production base URL;
- database/subdomain formatting;
- TLS requirements;
- request methods;
- content types.

### Reports API

- exact report slugs/names;
- required vs optional filters;
- response columns/types;
- hidden/inactive record behavior;
- pagination contract;
- maximum page size;
- stable source IDs;
- date/time/timezone semantics.

### Database API

- exact endpoint version;
- read/write operation availability;
- resource filters;
- pagination;
- last-updated filters;
- attachment behavior;
- write idempotency if ever used.

### Error/retry behavior

- 400 validation errors;
- 401/403 authentication/authorization;
- 404 resource/report behavior;
- 406/content negotiation if applicable;
- 429 rate limiting;
- retry-after headers;
- 5xx retry safety;
- timeout behavior.

### Rate limits

- exact request window;
- per-customer vs per-partner scope;
- whether Reports API and Database API have separate limits;
- burst behavior;
- pagination impact.

### Migration reconciliation

For a controlled test account, compare API results against AppFolio
CSV/XLSX exports for the same data set:

- property count + IDs;
- unit count + property relationships;
- tenant/occupancy relationships;
- owner relationships;
- GL account count;
- GL detail totals;
- hidden/inactive records;
- dates and monetary values.

Do not call the connector production-ready until these comparisons reconcile
and existing migration dry-run/commit/idempotency tests stay green.

## 8. Security rules

- Never commit secrets.
- Never persist raw provider credentials in migration records.
- Never log Client Secrets/session cookies/tokens.
- Keep organization isolation fail-closed.
- Keep dry-run-before-commit.
- Preserve exact-fingerprint commit and source-to-target idempotency.
- Do not let provider transport directly mutate accounting outside established
  migration/GL contracts.
- Do not weaken audit or recovery visibility.

## 9. Handoff rule

Future agents working on Phase 4.13 must read this file before claiming the
AppFolio API path is blocked or complete.

Public/mirrored material may support research, mocks, import-schema comparison,
and test planning. Live production transport still requires verification
against a legitimate current AppFolio contract/test account.
