# UX STANDARDS — AUTHORIZED, NOT YET ACTIVE

**Owner authorization:** approved  
**Implementation status:** NOT ACTIVE  
**Activation phrase:** `start UX work`

These standards are permanent product direction. They do not authorize an
agent to interrupt the active product roadmap or rebuild existing systems.

Before implementing any section, inspect the live repository and classify the
capability as **VERIFIED / PARTIAL / PLANNED / MISSING**. Reuse and extend
existing architecture. Never create a parallel replacement merely because this
document describes existing behavior in newer language.

Navigation integrity is governed separately by
`docs/NAVIGATION_INTEGRITY_PLAN.md`.

## 1. Modern product standard

The customer application should remain lightweight, responsive, fast, modern,
consistent, discoverable, permission-aware and mobile-friendly. Prefer shared
primitives and common data contracts over one-off page implementations.

## 2. Feature/Page Registry

Reuse `docs/FEATURE_REGISTRY.md`; do not create a second feature registry.

Meaningful primary features/pages should have intentional identity, route,
module/parent, release state, entitlement, organization configurability,
permission requirements and presentation/entry placement where applicable.

## 3. Intentional page placement

Every customer-facing page needs an intentional entry path. Valid placement
includes top-level navigation, submenu, module landing page, report catalog,
parent/contextual workflow, Settings, portal, platform/internal surface,
hidden/internal state or archive.

Not every page belongs in the sidebar. Detail, create, edit, print and action
routes are normally reached from their parent workflow.

## 4. Canonical product taxonomy

The platform owns feature/module hierarchy. Personal customization must not
arbitrarily re-parent product domains such as Accounting into Leasing.

## 5. Sidebar customization

Reuse the existing personal hide/show, drag-to-reorder and reset behavior.
Personal presentation preferences never grant authorization.

## 6. Platform release control

Reuse the existing release-gate system. Do not create another release-control
mechanism.

## 7. Organization feature control

Reuse customer `Settings → Features`. Organization administrators may control
only capabilities that are explicitly organization-configurable. Organization
settings cannot override platform release stage, commercial entitlement,
backend authorization or security.

## 8. Feature lifecycle and retirement

Where applicable, use a controlled lifecycle:

`ACTIVE → DEPRECATED → READ-ONLY (when needed) → ARCHIVED → REMOVED`

Before removal, consider live usage, saved links/configurations, historical
records, integrations and navigation. Do not casually delete production-used
features.

## 9. Address autocomplete

Reuse `frontend/src/components/AddressAutocomplete.tsx`; improve it rather
than rebuilding it.

Typing a partial address such as `2820 Brid...` should return useful address
suggestions. Selection should populate available structured fields such as
street, city, state, ZIP, county, coordinates and timezone where supported.
Manual correction remains possible.

## 10. State autocomplete

Reuse `frontend/src/components/StateAutocomplete.tsx`.

Examples:

- `O` may show Ohio, Oklahoma and Oregon.
- `Oh` should narrow toward Ohio.

Display a user-friendly state name and store the standardized state code
(e.g. `OH`) where required by the data contract.

## 11. Duplicate property-address detection

When the same organization attempts to add a property at an existing address,
warn before accidental duplication and offer a path to the existing property.

This lookup must never reveal another organization's property.

## 12. Universal Smart Lookup

Create one reusable internal-entity lookup architecture rather than unrelated
pickers for every form. Candidate entities include tenants, owners, properties,
units, vendors, contacts, staff/managers, HOA members, GL accounts and bank
accounts.

Results must always respect organization scope, permissions and
property/assignment scope where required.

## 13. Smart Lookup interaction standard

When implemented, Smart Lookup should support debounce, server-side search for
large organizations, keyboard navigation, Enter-to-select, loading and
no-results states, useful secondary identifiers and accessible semantics.

## 14. Global Search / Command Search

Extend the existing TopBar Search shell and the already-planned Universal
Powerful Search rather than adding a competing search system.

Authorized search scope may include permitted records, pages and commands.
Examples include a tenant name, `bank reconciliation`, `ARC`, or
`owner statements`. A command-palette shortcut such as `Ctrl+K` may be used
only after reconciling the existing shortcut plan.

## 15. Universal Add / Add Functionality

Convert the existing TopBar **Add Functionality** shell into a permission-aware
action menu. Examples include Property, Tenant, Owner, Vendor, Receipt, Bill,
Work Order, Application, HOA case and ARC request.

Only actions the current user can actually perform may be shown.

## 16. Contextual Help

Convert the existing Help & Training concept into reusable product help.
Use a small `?`/info affordance only for fields or workflows that reasonably
need explanation, such as GL mapping, reserve accounts, reconciliation,
assessments, permission configuration or accounting locks.

Do not put help icons beside every obvious field.

## 17. Help behavior

Simple help should use concise accessible tooltip/popover content. Complex help
may open a side panel containing: what this does, when to use it, an example,
important warning and learn-more path.

Keyboard and screen-reader use must work.

## 18. What's New

Turn the existing `WHATS_NEW` concept into actual release communication.

- Normal update: What's New feed + unread indicator.
- Important update: optional dismissible banner.
- Critical operational message: optional one-time login modal.

Ordinary releases must not become repeated login popups.

## 19. Announcement targeting

Where useful, release announcements may target all organizations, selected
organizations, modules/add-ons and/or roles. Store per-user read/dismiss state.

## 20. Notification Center

Reuse the existing notification architecture and Phase 6 communication plan.

A future central notification UI may include approvals, failed payments,
overdue tasks, lease/insurance expirations, reconciliation issues, maintenance,
HOA/ARC events and communication failures. Do not replace verified
domain-specific notification workflows.

## 21. Action Center

Notifications and work requiring action are separate concepts. A future Action
Center should answer **What requires my attention?**

Examples include bill approval, application review, bank reconciliation, ARC
review, appeal handling, inspections, failed payment resolution, insurance
renewal and overdue work orders. Role and assignment scope remain authoritative.

## 22. Module landing pages

Create landing/overview pages only when they provide real value.

Useful Accounting landing content might include common actions, alerts, recent
activity and shortcuts. HOA may expose Assessments, Violations, ARC, Board,
Documents, Reserves and Budgets. Reporting may expose categories, search,
favorites, recent reports and the builder.

Never create an empty landing page solely to satisfy a route test.

## 23. Reporting charts

Do not rebuild Reporting. Reuse the report catalog, report services, search and
saved report configurations.

Charts are summaries layered on authoritative report data.

## 24. Chart standard

Charts should be lightweight, responsive, fast and accessible. Prefer line,
bar, stacked bar, carefully used donut/pie, and KPI cards.

**Charts summarize; tables remain authoritative.**

## 25. Appropriate chart usage

Examples include:

- Income Statement: revenue, expenses, net income trend.
- Cash Flow: inflow, outflow, ending cash.
- Budget: actual vs budget and variance.
- Receivables: aging and delinquency trends.
- Property performance: income, expenses, NOI, occupancy.
- Maintenance: open/completed, overdue, completion time.
- HOA: billed/collected assessments, outstanding balances, violations,
  ARC turnaround, reserves and budget vs actual.

## 26. Chart performance

When implemented:

- avoid unnecessarily heavy libraries;
- lazy-load where practical;
- aggregate large datasets server-side;
- do not ship thousands of raw rows solely for a chart;
- reuse existing report data and filtering;
- keep animation minimal;
- support responsive/mobile layouts, loading/empty states and print/PDF;
- chart failure must never block the authoritative table.

## 27. Chart drilldown

Where valuable, chart interaction may filter/navigate to underlying records.
Examples include a delinquency bucket, overdue work orders, expense category or
outstanding HOA assessments.

Chart and table calculations must use the same business logic.

## 28. Custom Report Builder visualizations

Extend the existing Saved Custom Report Builder; do not replace it.

Potential visualization modes include Table, Bar, Line and appropriately used
Pie/Donut. Configuration may include grouping, date dimension, metric, filters
and preview. Saved configurations should retain visualization settings when
this work becomes active.

## 29. Favorites and Recent

Future productivity support may include favorite reports/pages and recently
viewed properties, tenants, owners, vendors and HOA cases. All results remain
permission-scoped.

## 30. Breadcrumbs

Deep workflows should support useful breadcrumbs, especially routes that are
intentionally absent from the sidebar.

Examples:

`Properties > 2820 Bridge Ave > Units > Unit 2 > Edit`

`HOA > Violations > Case #123 > Hearing`

## 31. Saved Views

Where useful, support personal and later shared views such as:

- My overdue work orders
- Cleveland properties
- tenants 30+ days delinquent
- HOA violations awaiting hearing
- open ARC applications

Permissions remain authoritative.

## 32. Role-aware dashboards

The current dashboard may evolve into role-aware summaries. Examples:

- Admin: portfolio health and alerts
- Owner: financial/property information
- Manager: tasks, delinquency, maintenance
- Crew/Vendor: assigned work
- Tenant: lease, payment, work orders
- HOA board: meetings, decisions, ARC

Do not rebuild verified portal-specific functionality.

## 33. Onboarding

Reuse the existing onboarding roadmap. Potential checklists include
organization, accounting, HOA and import/migration setup. Do not create a
parallel onboarding framework.

## 34. Better empty states

Where appropriate, replace bare `No records` messaging with a short
explanation, primary next action and optional help path. Keep empty states
lightweight.

## 35. Record activity timeline

Reuse immutable audit infrastructure. Important records may expose a readable
timeline such as Created, Updated, Approved, Notice sent, Payment posted,
Email failed/retried, Reversed and Archived.

Do not create a second audit datastore.

## 36. Responsive standard

New shared UI should be responsive from the start.

- Desktop: full navigation, detailed tables, optional side panels.
- Tablet: sensible stacking/reduced columns.
- Mobile: navigation drawer, accessible actions, mobile-safe forms,
  full-width charts and usable table alternatives.

This complements rather than replaces the existing native-mobile roadmap.

## 37. Accessibility

Shared primitives should support keyboard navigation, visible focus, proper
labels, accessible help, semantic controls, sufficient contrast and
screen-reader-friendly status messages. Prefer fixing accessibility in reusable
primitives instead of patching individual pages.

## 38. Environment identification

Staging, demo and test environments should clearly identify themselves where
useful so operators do not confuse them with Production.

## 39. Route/feature health

The navigation integrity foundation now protects exposed menu/report routes.
Longer-term platform visibility should also surface broken routes, orphaned
primary pages, frontend failures and failed API destinations so customers are
not the first monitoring mechanism.

## 40. Platform feature visibility

Extend the existing Platform Admin and Feature Registry instead of replacing
them. Future visibility may include feature/page route, release stage, plan,
organization availability, roles, help/announcement status, route health and
archive/deprecation state.

---

# Live reconciliation snapshot — 2026-10-01

This snapshot prevents future sessions from treating all 40 standards as new.

| # | Standard | Live classification | Existing source / future tracking |
|---|---|---|---|
| 1 | Modern product standard | NEW STANDARD | Governing standard; not a standalone feature |
| 2 | Feature/Page Registry | VERIFIED | `platform.feature_registry.full_surface` |
| 3 | Intentional page placement | VERIFIED foundation | `docs/NAVIGATION_INTEGRITY_PLAN.md` |
| 4 | Canonical taxonomy | PLANNED/established | PROJECT_MASTER navigation sections |
| 5 | Sidebar customization | VERIFIED | Menu Permissions + My Preferences |
| 6 | Platform release control | VERIFIED | `platform.feature_flags.system` |
| 7 | Organization feature control | VERIFIED | Settings → Features |
| 8 | Feature lifecycle | GENUINELY NEW | `ux.feature_lifecycle` |
| 9 | Address autocomplete | VERIFIED | Existing AddressAutocomplete component |
| 10 | State autocomplete | VERIFIED | Existing StateAutocomplete component |
| 11 | Duplicate property detection | GENUINELY NEW | `ux.duplicate_property_detection` |
| 12 | Universal Smart Lookup | GENUINELY NEW | `ux.smart_lookup` |
| 13 | Smart Lookup UX | NEW, bundled | `ux.smart_lookup` |
| 14 | Global Search | ALREADY PLANNED | `universal.powerful_search`, Phase 3.5 carry-forward |
| 15 | Universal Add | GENUINELY NEW | `ux.universal_add` |
| 16 | Contextual Help | GENUINELY NEW | `ux.contextual_help` |
| 17 | Help behavior | NEW, bundled | `ux.contextual_help` |
| 18 | What's New | GENUINELY NEW implementation | `ux.whats_new` |
| 19 | Announcement targeting | NEW, bundled | `ux.whats_new` |
| 20 | Notification Center | ALREADY PLANNED | Phase 6 / `communication.notifications_log` |
| 21 | Action Center | GENUINELY NEW | `ux.action_center` |
| 22 | Module landing pages | DESIGN STANDARD | Build only where useful |
| 23 | Reporting charts | GENUINELY NEW | `ux.reporting_visualizations` |
| 24 | Chart standard | NEW, bundled | `ux.reporting_visualizations` |
| 25 | Chart use cases | NEW, bundled | `ux.reporting_visualizations` |
| 26 | Chart performance | NEW, bundled | `ux.reporting_visualizations` |
| 27 | Chart drilldown | NEW, bundled | `ux.reporting_visualizations` |
| 28 | Report Builder visualizations | GENUINELY NEW extension | `ux.custom_report_visualizations` |
| 29 | Favorites/Recent | GENUINELY NEW | `ux.favorites_recent` |
| 30 | Breadcrumbs | GENUINELY NEW | `ux.breadcrumbs` |
| 31 | Saved Views | GENUINELY NEW | `ux.saved_views` |
| 32 | Role-aware dashboards | GENUINELY NEW | `ux.role_aware_dashboards` |
| 33 | Onboarding | ALREADY PLANNED | `migration.onboarding_checklist`, Phase 4 |
| 34 | Better empty states | GENUINELY NEW | `ux.empty_states` |
| 35 | Activity timeline | GENUINELY NEW presentation layer | `ux.activity_timeline`; reuse audit data |
| 36 | Responsive standard | ALREADY PLANNED | PROJECT_MASTER responsive pass + native mobile roadmap |
| 37 | Accessibility | GENUINELY NEW platform-wide standard | `ux.accessibility_primitives` |
| 38 | Environment identification | GENUINELY NEW | `ux.environment_identification` |
| 39 | Route/feature health | PARTIAL | navigation integrity is verified; broader `ux.route_feature_health` remains |
| 40 | Platform feature visibility | PARTIAL | existing Platform Admin/release gates; `ux.platform_feature_visibility` extends them |

## Activation and batching

All `ux.*` scheduled items remain **AUTHORIZED BUT NOT ACTIVE**. A later
session starts them only after the owner explicitly says `start UX work`.

At activation time, audit the live repository again. A requirement may have
been completed by an intervening roadmap phase; if so, mark/reuse it rather
than implementing it twice.

Implement one bounded, independently testable batch at a time, preserve
verified functionality, and update `AI_HANDOFF.md` after each verified batch.
