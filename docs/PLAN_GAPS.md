## Phase 5 operational recovery and crew decisions (2026-10-20)

Preventive execution becomes transferable without rewriting immutable creator attribution. The per-schedule execution operator is scoped to the actual organization/property and validated on each daily sweep; staff have read-only execution health and an audited recovery action. Migration `c4b7e2f9a601` and browser/backend regressions await exact hosted CI verification.

Next dispatch foundation uses distinct pending/accepted/rejected crew assignment responses and row-lock serialization, requires rejection reason, and returns rejected orders to the authorized manager queue with full audit. Existing assigned work orders with NULL response remain startable to avoid forging acceptance. Prepared additive migration `e1b9c7d2a540` must be published and six-job CI verified before release.

**Still missing:** dispatch groups/urgency and business-hour policy, notifications, SLA clocks/escalation, on-call calendar, ranked preferred vendors and recovery; full inspections, materials, purchasing, invoice integration. An assignment response is not proof the full dispatch subsystem is complete.

# PLAN GAPS

> **Engineering order update — 2026-09-23:** Phase 3.4.S Engineering Safety Foundation now sits between registry completion (3.4.2) and implementation phase 3.4.3. Core launch work takes priority over specialized expansion products. Hybrid Capability Gating replaces per-field flagging. See PROJECT_MASTER Sections 70, 79, 80, 82, and 84 plus ENGINEERING_SAFETY.md.


**Supplement to PROJECT_MASTER.md**
**Last updated: 2026-09-22**

This file captures everything missing from PROJECT_MASTER.md that must
be planned before the product ships. It's the "nothing gets lost" file —
same reasoning as FEATURE_REGISTRY.md, same session.

Every gap has a category, a decision status, and a phase. Nothing here
is a wishlist — each item was discussed with Yasir and has a call.

---

## How to read this file

- **Decision** — the business or engineering call, already made
- **Phase** — when it ships
- **Cost** — rough session estimate
- **Depends on** — hard dependencies in the foundation order

---

# A. COMPLIANCE & LEGAL

## A1. Multi-region data residency

**Decision:** Model B — single logical system, `data_region` column on
`organizations` (and `properties`), routing through a single
`get_db_for_org(org)` layer. Start US-only. Add `eu-west-1` when the
first EU customer signs. Add `ap-southeast-1` when APAC scales.
Physical isolation (Model C) only for a seven-figure enterprise
customer, and never for general use.

**Sub-decision:** Option Y — US-only today. Add regions when a real
customer needs them. The routing layer makes it mechanical later.

**Phase:** `data_region` column + routing layer ship in **Foundation
Session 5**. First regional DB added when needed.

**Cost:** 1 session to build the routing layer now. 2–3 sessions per
region added later.

**Depends on:** Nothing. Ships alongside the identity boundary.

## A2. GDPR + CCPA compliance

**Decision:** Per-org and per-property. When an org's `data_region` is
`eu`, GDPR rules apply. When it's `us-ca`, CCPA rules apply. Rules
include:

- Machine-readable export endpoint (user asks for everything we hold)
- Right-to-be-forgotten flow (hard-delete after retention window)
- Schema change: `deleted_at` timestamp on every soft-deletable table
  (replaces the current `is_active = False` only)
- Data processing agreement (DPA) template per region
- Subprocessor list published
- Cookie consent banner (EU only)
- Privacy policy + ToS version acceptance tracked per user

**Phase:** Schema change (`deleted_at`) ships in **Foundation Session
5** alongside `data_region` (same migration family). Export and
forget-me endpoints ship in **Foundation Session 5 or 6**. Consent
banner + ToS versioning ship in **Phase 4**.

**Cost:** ~1 session for the schema + endpoints. ~1 session for the
consent banner + versioning.

## A3. SOC 2

**Decision:** Pursue within 24 months. Log everything from day one.

Requirements this imposes immediately:
- Immutable audit log (append-only, no UPDATE or DELETE allowed)
- Every admin action logged (who, when, what, from which IP)
- Every data access logged where sensitive
- Retention policy defined per data class (30 days / 1 year / 7 years
  / forever)
- Encryption at rest (RDS default) + in transit (TLS)

**Phase:** Audit logging **from Foundation Session 3 onward** (identity
boundary + flags). Retention policy defined in **Foundation Session
5**. Formal SOC 2 audit process is a **Phase 11+** business project
(not engineering).

**Cost:** No extra engineering if we do it right from the start.
Costly if we retrofit.

## A4. FCRA / screening compliance

**Decision:** Plan now, ship with Phase 8 screening.

Requirements:
- Adverse action notices (auto-generated letter when screening
  causes denial, with provider contact info + dispute rights)
- Dispute handling workflow
- Record retention (2 years minimum per FCRA)
- Provider agreement with TransUnion / Experian / Equifax
- User-facing disclosures

**Phase:** **Phase 8** alongside screening.

**Cost:** ~1 session.

## A5. PCI DSS

**Decision:** We never store, process, or transmit card numbers. Stripe
handles all card data via Stripe Elements / Checkout. We store only
Stripe's token IDs (`pm_xxx`, `cus_xxx`, `sub_xxx`).

This is documented as a hard rule. Any code that touches a card number
is rejected in review.

**Phase:** N/A — this is a permanent rule, enforced in code review.

---

# B. INFRASTRUCTURE

## B1. Background job system

**Decision:** **Arq** (async Redis-based job queue). Fits FastAPI's
async model. Has a built-in scheduler. Simpler than Celery. Used
widely in the FastAPI community.

**Phase:** **Foundation Session 4** (flag system + jobs stand up
together).

**Cost:** ~1 session to stand up + write the standard patterns
(define job, enqueue, retry, dead-letter, monitor).

## B2. Scheduler

**Decision:** **Arq's built-in cron**. Same process as jobs. One thing
to deploy, one thing to monitor.

Needed for:
- Monthly billing (Stripe invoices)
- Monthly management fees
- Monthly owner statements
- Daily delinquency aging
- Daily late fee application
- Nightly backup verification
- Hourly fraud signal refresh

**Phase:** **Foundation Session 4.**

**Cost:** Included in B1.

## B3. Redis

**Decision:** Stand up now. **Upstash** serverless for dev (free tier
covers dev). **AWS ElastiCache** for production.

**Phase:** **Foundation Session 4.**

**Cost:** ~$0 dev, ~$15–50/mo prod depending on tier.

## B4. Observability

**Decision:**
- **Sentry** — errors (frontend + backend)
- **Logtail** — log aggregation
- **Grafana Cloud** — metrics + dashboards + alerts

**Phase:** **Foundation Session 4** (Sentry + basic structured
logging). Logtail + Grafana in **Phase 11** when we have real traffic.

**Cost:** ~1 session for Sentry wiring. ~1 session for the full stack
in Phase 11.

---

# C. PRODUCT SCOPE (new sub-phases)

These were one-liners in the master doc. They are multi-month products.
Each gets its own sub-phase with its own section in the master doc.

## C1. Affordable Housing / Section 8 / LIHTC

**Decision:** Full sub-phase. Includes:
- HUD compliance (income certs, recerts, EIV, HQS inspections)
- LIHTC (applicable fraction, minimum set-aside, 8609s)
- Section 8 / HAP contracts (rent reasonableness, HAP requests)
- AMI rent limits per county/state
- Waiting lists
- Tenant income certification workflow
- Annual recertification workflow
- HUD reporting

**Phase:** **New Phase 4.6** (after Phase 4.5, before Phase 5).

**Cost:** 12–20 sessions.

## C2. HOA

**Decision:** Full sub-phase. Includes:
- HOA dues (recurring + special assessments)
- Violations workflow (notice, cure period, fines, hearings)
- Board portal (meetings, minutes, votes, documents)
- Architectural Review Committee (ARC) requests
- Reserve studies + reserve fund accounting
- Governing document storage + delivery
- Annual budget + assessment increase workflow

**Phase:** **New Phase 4.7.**

**Cost:** 10–15 sessions.

## C3. Commercial (CAM / NNN / percentage rent)

**Decision:** Full sub-phase. Includes:
- CAM charges (Common Area Maintenance)
- NNN (triple net: taxes, insurance, CAM)
- CAM reconciliation (annual true-up)
- Percentage rent (% of tenant sales over breakpoint)
- Lease abstracts (rent schedule, options, escalations, co-tenancy)
- Rent commencement vs. lease commencement
- TI allowances (tenant improvement)
- Options (renewal, expansion, ROFR, ROFO)
- Sales reporting (tenant portal upload)
- Commercial lease templates

**Phase:** **New Phase 4.8.**

**Cost:** 12–18 sessions.

## C4. RUBs (Ratio Utility Billing)

**Decision:** Full sub-phase. Includes:
- Meter reading (manual entry + import)
- Ratio allocation methods (sq ft, occupancy, # of fixtures, etc.)
- Utility provider integrations (or manual bill entry)
- Allocation detail per bill period
- Tenant charges + owner charges
- True-up at year end
- RUBs reports

**Phase:** **New Phase 4.9.**

**Cost:** 6–10 sessions.

## C5. Student / Senior / Short-term rentals

**Decision:** In the plan, deferred.

- **Student housing:** by-the-bed leases, guarantor workflow, academic
  year cycles. **Phase 4.10.**
- **Senior housing:** age-restricted compliance, care coordination
  placeholders, HUD 202/811. **Phase 4.11.**
- **Short-term rentals:** Airbnb / Vrbo integration, nightly pricing,
  turnover scheduling. **Phase 4.12.**

**Cost:** 4–6 sessions each.

## C6. Migration tooling

**Decision:** Two-sided, with export/import as the primary safe path.

**Org side (customer-run):**
- Generic CSV importer with column mapping, dry run, commit
- Standard templates for properties, units, tenants, owners, leases,
  charges, payments, GL history
- **Phase 4.**

**Provider migration side (platform-run):**
- AppFolio export migration — **Phase 4.13**:
  - CSV/XLSX upload is the primary supported migration transport;
  - report/file detection, column mapping, staging, validation and coverage;
  - stable source-ID linking across files;
  - possible-match review rather than automatic overwrite;
  - exact-fingerprint dry run before controlled commit;
  - accounting reconciliation before financial history is committed;
  - missing/ambiguous data is surfaced for review, never invented.
- AppFolio API transport is an **optional later adapter/testing path** feeding
  the same staging/dry-run/commit pipeline. It must not block Phase 4.13 and
  must not use undocumented browser/session endpoints as production transport.
- Direct/API-assisted Buildium migration — **Phase 4.14**
- Direct/API-assisted Yardi migration — **Phase 4.15**
- Direct/API-assisted RentManager migration — **Phase 4.16**
- Direct/API-assisted DoorLoop migration — **Phase 4.17**
  - **2026-10-18 VERIFIED source-independent foundation** (SHA `8323b120`, CI `39152511094`): secured DoorLoop
    DRAFT run creation/list/get and audit, nonpersistent bounded CSV/XLSX export
    inventory, exact-file-fingerprint read-only source-quality diagnostics,
    staff roles and provider/active-organization isolation. See
    `docs/DOORLOOP_MIGRATION_PLAN.md`. The new role-gated Platform Admin DoorLoop export-review
    UI is separately provisional pending exact-SHA CI. Actual customer imports stay
    blocked by authorized, versioned source exports and verified resource,
    relationship and accounting contracts.

Detailed Phase 4.13 contract:
`docs/APPFOLIO_MIGRATION_IMPORT_PLAN.md`.

**Cost:** Phase 4.13 continues in bounded verified batches; later provider
adapters remain separately estimated.

## C7. Trust account interest

**Decision:** In the plan. Some states require interest-bearing trust
accounts, and the interest either goes to the tenant, to the state,
or to a housing fund depending on jurisdiction.

**Phase:** **Phase 4.5** (with the other trust-account enhancements).

**Cost:** 2–3 sessions.

## C8. Positive pay

**Decision:** In the plan. Bank-level check fraud prevention. We
generate a positive pay file (issued checks) and upload to the bank;
the bank rejects any check not on the list.

**Phase:** **Phase 4.5.**

**Cost:** 1–2 sessions.

## C9. 1099 e-filing

**Decision (2026-09-26):** Use IRS IRIS (Taxpayer Portal / approved A2A) or
Track1099 or an equivalent supported provider. FIRE retires for the 2027 filing
season; do not generate legacy FIRE submissions for tax year 2026. Bring secure
payer/recipient tax profiles and W-9 intake ahead of Phase 3.7 filing; keep
actual transmission, recipient delivery, corrections and provider workflows
in the Phase 4.5 integration scope until verified. Follow the applicable tax-
year IRS instructions and do not infer reportable payments from raw GL totals.

- Vendor 1099-NEC (non-employee compensation)
- Owner 1099-MISC (rent paid directly to individual owners, when
  applicable)
- Secure W-9/tax-profile intake and tracking: prerequisite pulled into Phase 3.7;
  provider e-delivery/corrections/retention/expiration alerts remain Phase 4.5

**Phase:** **Phase 4.5.**

**Cost:** 2–3 sessions.

## C10. Year-end close / locked periods

**Decision:** Org-configurable. `locked_through_date` on the org.
Enforced in every posting (GL, receipts, bills, deposits, JEs). Once
locked, no posting dated before that date is allowed without an
override from ADMIN with a reason.

**Phase:** **Foundation Session 5** (schema) + **Phase 3.6**
(enforcement + UI).

**Cost:** ~1 session.

---

# D. OPERATIONAL

## D1. Enterprise (non-self-serve) onboarding

**Decision:** Enterprise customers do NOT sign up on the website. They
are provisioned by us via the internal admin (Foundation Session 9).
Their plan is negotiated. Their feature set is customized via per-org
overrides.

**Phase:** **Foundation Session 9** (internal admin org creation).

**Cost:** Included in the internal admin app.

## D2. Custom domains + white-label

**Decision:** In scope. Enterprise customers can:
- Point their own domain at their portal (`portal.acme.com`)
- Use their own logo, taglines, colors
- Brand invoices, bills, statements, letters with their logo

**Phase:**
- Per-org branding (logo, tagline, colors): **Phase 3.6**
- Custom domains (DNS + TLS automation): **Phase 11** (requires
  infrastructure work)
- Portal branding (Tenant / Owner / Vendor / Crew): **Phase 7**

**Cost:** 2–3 sessions for branding. 3–5 sessions for custom domains.

## D3. Status page + incident communication

**Decision:** Publicly hosted status page (`status.yourplatform.com`)
on a static provider (Statuspage.io, Instatus, or self-hosted).
Internal incident tracker lives in the internal admin.

**Phase:** **Phase 11.**

**Cost:** ~1 session.

## D4. Support SLAs by tier

**Decision:**
- Standard plan: 24h first response
- Enterprise plan: 4h first response
- Feature requests: triaged into backlog, no SLA
- Critical (system down): 1h, all plans

Ticket system with SLA clocks ships in **Phase 9**.

**Phase:** **Phase 9.**

**Cost:** 3–5 sessions for the ticket system.

---

# E. ENFORCEMENT

## E1. `check_parity.py` gets teeth

**Decision:** `check_parity.py` reads `FEATURE_REGISTRY.md`, extracts
the required slot list for each page, verifies the slot list is
present in the page source (via a marker comment block), and fails
the build if any page is missing slots.

Every page must have a top-of-file marker:

    // ═══════════════════════════════════════════════════
    // PAGE SURFACE — from FEATURE_REGISTRY.md
    // Slots: receipts.tabs, receipts.date, receipts.cash, ...
    // ═══════════════════════════════════════════════════

**Phase:** **Foundation Session 2** (right after the registry is
written).

**Cost:** ~1 session.

---

# F. FOUNDATION ORDER (the 12-session sequence)

| # | Session | Ships |
|---|---|---|
| 1 | **This session** | `PLAN_GAPS.md` + `FEATURE_REGISTRY.md` (structure + Receipts) + master doc updates + parity JSON updates |
| 2 | Next | Finish `FEATURE_REGISTRY.md` (all pages) + `check_parity.py` v2 |
| 3 | | Backend identity boundary (`platform_users`, separate JWT, seed script) |
| 4 | | Feature flags tables + resolver + audit + Arq + Redis + Scheduler + Sentry |
| 5 | | `data_region` column + `get_db_for_org()` routing layer + `deleted_at` schema + `locked_through_date` |
| 6 | | Billing foundation (Stripe products, plans, subscriptions, webhooks) |
| 7 | | Signup + payment flow (customer side) |
| 8 | | Fraud / abuse layer (Stripe Radar + our signals + review queue) |
| 9 | | Internal admin app (separate Next.js app) — orgs, flags, plans, fraud, audit |
| 10 | | `useFlag()` + `<Flag>` + Settings → Features (customer side) |
| 11 | | Unit enforcement + plan limits |
| 12 | | Retrofit Receipts page (proves the pattern) |
| 13+ | | Retrofit remaining pages, one per session |
| N | | **Back to features.** Journal Entries sub-tabs is the first feature built on the new foundation. |

Total foundation cost: **~12 sessions.** After that, every feature
ships by flipping a flag. No more loops.

---

# G. WHAT THIS REPLACES / UPDATES IN THE MASTER DOC

- **Phase 9** — was "Internal Team + Support." Becomes
  "Extended Internal Tools" (support tickets, SLA, status page,
  impersonation logs). The **basic internal admin moves earlier** into
  the foundation pass.
- **Phase 10** — was "Subscription & Billing." Most of it moves
  earlier into the foundation pass (Stripe, plans, subscriptions,
  signup, unit enforcement). Metering, discounts, quotes stay Phase 10.
- **Phase 3.5.5** — starts after Foundation Session 11 (flag system
  is live). Retrofit uses the flag system.
- **Phase 4.5** — becomes the umbrella for HOA, Affordable,
  Commercial, RUBs, trust interest, positive pay, 1099 e-filing.
- **New Phase 4.6 – 4.17** — the multi-month product lines.
- **Phase 11** — gains: data region provisioning, custom domain
  automation, status page, full observability.
- **Section 9 (5-layer menu gating)** — unchanged. The flag system
  is Layer 1 as designed.
- **Section 67** — the Complete-Page rule gains teeth (E1).
- **Section 79, 80** — unchanged. This file makes them real.

---

# END OF PLAN_GAPS.md
## Open Phase 5 maintenance attribution issue (2026-10-19)

**Priority: blocking recurring generation.** `WorkOrder.tenant_id` is NOT NULL and manual staff creation still writes the staff user ID there for backward compatibility. Additive `request_origin` and `requested_by_user_id` now exist, but a complete reader/API/finance/report consumer audit and safe nullable-tenant migration are not yet implemented. Explicit tenant-origin records must not disclose to a tenant unless requested_by_user_id matches that tenant; historical unknown provenance remains compatibility-scoped. Do not create automated orders with fabricated tenant IDs. Planned: complete model/schema migration, recurring schedule/occurrence unique keys, on-call dispatch policies, inspections/inventory and billing integration behind separate authorization and audit gates.

## Phase 5 inspection checklist gate (prepared 2026-10-19)

A bounded signed-in staff checklist form and storage/read/report workflow is prepared in detached code, not verified. Five checklist areas record per-item condition and optional notes, with immutable evidence and append-only audit. The existing staff-only permission and current property/unit scoping remain. Scope explicitly excludes mobile offline sync, photographs, external approvals and the full Inspections feature gate. Must verify additive migration, PostgreSQL regressions, frontend, browser E2E, security and staging at exact SHA before treating this portion delivered.

## Phase 5 staff inspection detail and parent integrity (2026-10-19; CI gated)

Record history/report reads validate stored inspection parent against actual Unit→Property; malformed rows do not leak or masquerade as another property's evidence. Append-only creation audit now contains findings. Read-only scoped GET /api/unit-inspections/{id} and staff detail page keep retired history available to authorized staff while respecting assignment revocations. Tests cover mismatched parent, recovery, forbidden cross-organization/tenant access and persisted browser navigation. This does not enable full inspections, photo/offline or approval features; exact six-job hosted CI required.

## Phase 5 inspection history filters (2026-10-19; detached)

Staff-recorded inspection history can be filtered by recorded condition and inclusive inspection-date range with server-side authorization, bounded pagination, and explicit invalid-range errors. No tenant access, cross-property visibility, automatic evidence, accounting changes or module-wide release. Exact six-job CI required.

## Phase 5 inspection actor identity visibility (2026-10-19; detached)

Authorized staff inspection records show same-organization recorder names in list/detail after access check. Missing/deleted/foreign recorder profiles receive stable-ID fallback, never foreign name disclosure. Bulk list label resolution avoids per-row lookup. Backend negative test covers deliberately corrupt cross-org recorder reference. Requires exact hosted CI; no expanded module authorization.

## Phase 5 inspection history filter and E2E strict locator (2026-10-19)

The entry and filter fields have overlapping accessible labels: browser test must select the entry condition by its exact accessible name, retaining assertions. Prepared authorized-unit history filtering extends condition/date filters with server-scoped unit ID; backend negative tests cover unassigned manager unit, foreign organization and tenant denial. Still pending six-job hosted verification at the exact branch head. Full inspections and recurring scheduling stay gated.

## Phase 5 inspection-to-maintenance follow-up (2026-10-19; detached)

An authorized staff inspection can serve as traceable source evidence for a manually created maintenance work order. New nullable source_inspection_id FK is additive and never backfills invented links. Source inspection ID must be readable by the current staff user and match the selected work-order unit and property, otherwise request is rejected. Tenants and unauthorized organization/property users cannot forge source evidence. The link persists to the existing status-change audit and can be opened from the authorized work-order detail. The UI drafts a request from inspection facts but still requires an explicit user submission; no automatic dispatch, financial posting or tenant charge occurs. Exact hosted CI and permission regressions required before release.

## Phase 5 non-fabricated maintenance tenant identity (2026-10-19; detached)

New staff-originated work orders currently inherit submitting staff ID in legacy tenant_id, which is not a real lease tenant. Prepared revision 5a9e3c7d1b2f makes tenant_id nullable without rewriting old rows and records NULL for new staff submissions. The true staff requester remains in requested_by_user_id and append-only creation audit; tenant submissions still validate active lease/actual tenant. API read types and scope must support absence. Existing WorkOrder migrations/imports are historical evidence-only. No synthetic system identity or tenant charge is allowed when recurrence is later built. Exact six-job CI must pass and downgrade must reject populated tenantless records.

## Phase 5 preventive schedules (2026-10-19; CI gated)

Initial explicit-due foundation: organization-scoped schedule records with property/unit association, interval days, next due, active state, and actor audit. Authorized staff may manually materialize one due occurrence into a tenantless, no-entry-consent, unbilled work order. Duplicate schedule/date prohibited by DB uniqueness; a row-level lock serializes PostgreSQL workers. No automatic scheduler, automatic catch-up, self-service feature release, dispatch, or financial posting. Exact six-job CI is required.

## Phase 5 preventive daily sweep and staff UI (2026-10-19; detached)

Prepared signed-in staff schedule page, per-schedule activity history, duplicate-safe due generation, pause/resume and daily Arq due sweep. The durable scheduled JobRun is per UTC date. Worker reuses the audited occurrence transaction; a per-schedule bounded catch-up of 12 periods prevents unlimited burst. Creator identity, role, organization, active property/unit and manager assignment are revalidated. Automatic work orders neither grant entry permission nor post tenant charges. UTC due policy and full operations/release gates need further refinement before marking complete.

## Phase 5 paused preventive schedule edits (2026-10-19; detached)

Schedules can be paused and their task title, description and repeat interval changed. Editing an active schedule returns 409. The due date and previously generated work orders remain unchanged; all effective changes are audited with before/after values and must pass live role/organization/property-assignment authorization. PostgreSQL row lock protects concurrency with generation; there is no silent financial or tenant effect. Hosted six-job CI remains required, and dispatch/inspections/inventory/purchasing are unfinished.

## Phase 5 bounded preventive schedule lifecycle (2026-10-19; detached)

Staff can pause a schedule, then edit its title, instructions, interval and optional end date. Active edits are rejected, and row locks serialize updates with generation. End dates stop due generation and daily catch-up after the last eligible occurrence without rewriting prior work orders; replay remains idempotent, no tenant rights or charges. Full six-job CI still required. Dispatch, inspection approvals, inventory and purchasing remain open.

## Phase 5 retired maintenance schedule evidence (2026-10-20; detached)

Historical schedules and occurrence work-order references remain readable by current organization-authorized staff even when property or unit is inactive; manager assignments must remain currently valid. Such inventory cannot be used for new recurrence, activation changes, or schedule settings edits. The feature requires six-job hosted CI; automatic dispatch, on-call policy, mobile inspection approval, purchasing and inventory are still unfinished.

## Phase 5 preventive occurrence history paging (2026-10-20; detached)

Staff can load older recurring work-order occurrences in bounded authorized pages, with deduplication and chronological ordering. The history API already enforced unit/property/org scope; backend tests cover pagination and tenant denial. Exact successor six-job CI remains mandatory. Purchase orders, inventory and full dispatch still remain open.

## Phase 5 preventive due preview (prepared; CI gate)

Staff may preview bounded due dates of a current active preventive schedule without creating work orders or financial entries. Pending preview never authorizes entry, vendor dispatch or tenant billing. Corrupted occurrence replay must not reveal other organization's work. All-six exact-SHA CI pending; inventory and purchasing still outstanding.

## Phase 5 preventive replay audit bindings (prepared)

Scheduled generation and replay must never return an unrelated work order as an occurrence even if a database association is corrupted within the same property and unit. The prepared change verifies append-only creation evidence ties exact schedule and due date. Bounded read-only due previews are planned for the same staff-scoped screen; no automatic dispatch, entry consent or billing is granted. Requires exact SHA CI success before delivery.
