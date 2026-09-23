# PLAN GAPS

**Supplement to PROJECT_MASTER.md**
**Last updated: 2026-09-23**

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

**Decision:** Two-sided.

**Org side (customer-run):**
- CSV importer with column mapping, dry run, commit
- Standard templates for properties, units, tenants, owners, leases,
  charges, payments, GL history
- **Phase 4.**

**Our side (platform-run):**
- Direct API migration from AppFolio — **Phase 4.13**
- Direct API migration from Buildium — **Phase 4.14**
- Direct API migration from Yardi — **Phase 4.15**
- Direct API migration from RentManager — **Phase 4.16**
- Direct API migration from DoorLoop — **Phase 4.17**

**Cost:** 1–2 sessions per competitor.

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

**Decision:** Provider-based. **Track1099** or equivalent. Handles
IRS FIRE system, e-delivery, corrections.

- Vendor 1099-NEC (non-employee compensation)
- Owner 1099-MISC (rent paid directly to individual owners, when
  applicable)
- W-9 collection + tracking + expiration alerts

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

## D5. Engineering Safety Foundation

**Decision:** complete the registry first, then install the automated
quality foundation before large implementation batches.

Includes CI, PostgreSQL integration tests, backend unit/integration
tests, frontend lint/type/build checks, Playwright smoke/E2E, migration
verification, basic staging, backup/restore proof, idempotency
standards, accounting invariants, dependency/static scanning, and a
written Definition of Done.

**Phase:** **3.4.S**, immediately after 3.4.2 and before 3.4.3.

**Status 2026-09-23:** **IN PROGRESS.** Locally verified: backend test
framework, core accounting invariants, fresh database bootstrap, legacy
migration upgrade regression, model-registry guard, SQLite backup/restore,
idempotency standard, and Definition of Done. Built but awaiting hosted
evidence: GitHub CI/PostgreSQL integration, frontend lint/type/build, and
CodeQL/Dependabot. Still scheduled inside this phase: Playwright, staging,
and PostgreSQL staging restore proof.

---

# E. ENFORCEMENT

## E1. Parity consistency is one quality check, not proof of correctness

**Decision:** `check_parity.py` verifies the parity inventory remains
complete and phased. Session 3.4.2 expands registry coverage checks, but
a CLEAN parity result is never treated as proof that a workflow works.

After the Engineering Safety Foundation, the close gate also includes
applicable backend tests, PostgreSQL integration tests, migration
verification, frontend lint/type/build checks, browser smoke/E2E tests,
and accounting invariants.

**Phase:** Registry/parity coverage in **3.4.2** (**COMPLETE 2026-09-23**);
behavioral quality gates in **3.4.S**.

---

# F. FOUNDATION ORDER (revised)

| Order | Phase | Ships |
|---|---|---|
| 1 | 3.4.1 | PLAN_GAPS + FEATURE_REGISTRY v1 + planning decisions |
| 2 | 3.4.2 | Finish FEATURE_REGISTRY in Hybrid Capability Gating format + parity coverage tooling |
| 3 | **3.4.S** | Engineering Safety Foundation: CI, PostgreSQL tests, backend/frontend verification, Playwright, migrations, staging path, backup/restore, idempotency, accounting invariants, Definition of Done |
| 4 | 3.4.3 | Identity boundary + immutable audit + background jobs foundation |
| 5 | 3.4.4 | Release-gate tables/resolver (capabilities, not every field) |
| 6 | 3.4.5 | Locked accounting periods + core org settings; multi-region routing deferred until customer need |
| 7 | 3.4.6 | End-to-end verification of existing core product |
| 8 | 3.4.7 | Basic billing foundation |
| 9 | 3.4.8 | Self-serve signup/payment flow |
| 10+ | later foundation | Fraud, internal admin, unit enforcement, and broad retrofits in dependency order |
| then | compatibility | Retrofit Receipts first, then remaining pages with regression protection |
| then | core product | Resume Phase 3.6 and continue to core launch |
| post-launch | expansion | Affordable, HOA, Commercial, RUBs, Student, Senior, Short-term, competitor migrations unless reprioritized |

The safety foundation intentionally slows the first few steps so later
AI-assisted batches can be much larger without sacrificing correctness.

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
- **Sections 70, 79, 80** — revised to Hybrid Capability Gating with separate release, entitlement, org-setting, permission, and user-preference concerns.

---

# END OF PLAN_GAPS.md