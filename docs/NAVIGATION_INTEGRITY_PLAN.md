# NAVIGATION INTEGRITY PLAN

Status: **ACTIVE — authorized after Phase 4.10.**

This document is the permanent customer-navigation safety contract. Future
sessions read the repo-root `AI_HANDOFF.md` first and use this plan only when
the handoff says navigation work is active.

## Principles

1. Canonical menu keys may exist before their customer pages, but unfinished
   destinations must fail closed and must never render as clickable 404s.
2. Route readiness is presentation safety, not authorization. Entitlements,
   organization feature settings, role/user permissions and personal hiding
   remain separate and authoritative in their own layers.
3. Parents with children are expand/collapse containers. They do not require a
   landing page merely because `menuConfig.ts` stores an href.
4. A leaf menu item is navigable only when its configured route has a real,
   verified customer page.
5. Empty future containers must disappear rather than degrade into a broken
   leaf link.
6. Detail/action pages do not need sidebar entries. Valid entry paths include a
   parent workflow, report catalog, Settings, portal or contextual action.
7. Reporting catalog links are intentional navigation and must resolve.
8. Do not create placeholder pages merely to satisfy route tests.

## Mechanical vs structural findings

Mechanical fixes include obvious href corrections, an existing implemented
page missing its direct route, fail-closing an unfinished item, and regression
coverage.

Structural/product decisions include moving modules, changing canonical
taxonomy, deleting roadmap-backed menu items, renaming established keys or
changing entitlement/permission/org-configuration semantics.

If more than 10 non-mechanical findings require product decisions, or if 20+
broken links indicate one deeper architecture conflict, stop and report before
redesigning.

## Current readiness mechanism

`backend/app/constants/menu_keys.py::MENU_ROUTE_BLOCKED_UNTIL` is the
code-level fail-closed list. A phase removes its item only in the same verified
batch that ships the real customer route.

`backend/check_navigation.py` verifies:

- backend/frontend menu-key parity;
- exposed leaf menu destinations have page source;
- missing leaf routes are explicitly fail-closed;
- a blocked leaf with a newly created page is reviewed instead of remaining
  accidentally hidden forever;
- every available report-catalog href has page source.

The authenticated browser test snapshots links from the actually resolved
rendered sidebar and visits each one, failing on 404/not-found responses.

## Canonical placement

- Leasing: Listings, Applications, CRM, Lease Templates.
- Properties: Properties, Add Property, Units, Property Groups and contextual
  property workflows such as the verified Student Housing property tab.
- People: Team, Tenants, Owners, Vendors, Contacts.
- Accounting: receipts, charges, bills, banking, GL, diagnostics, deposits,
  management fees and owner statements.
- Maintenance: Work Orders, Recurring, Inspections, Unit Turns, Projects,
  Purchase Orders, Inventory, Fixed Assets, Smart Maintenance.
- Reporting: report catalog plus Custom Reports. Individual reports normally
  remain catalog destinations.
- Communication: Inbox, Messages, Templates, Surveys.
- Settings: settings families and compatibility/preference routes.
- HOA: existing HOA functionality stays under HOA/contextual HOA surfaces and
  is not scattered into unrelated modules.

## HOA and Student Housing boundaries

Navigation work may place existing HOA pages correctly, but it must not invent
new HOA business functionality. Backend-only HOA capabilities remain
PARTIAL/MISSING until their own product roadmap ships a customer page.

Phase 4.10 Student Housing is already verified as a gated property tab. Do not
create a new Student Housing sidebar module unless a later authoritative
navigation decision explicitly requires it.

## Unhide rule

Never unhide a key merely because its nominal phase number has passed. Unhide
only when:

1. the real customer page exists;
2. applicable product behavior is verified;
3. static navigation integrity is clean;
4. authenticated navigation E2E is green;
5. `AI_HANDOFF.md` updates the hidden-menu roadmap.

The handoff's **HIDDEN MENU / UNHIDE ROADMAP** is the operator-readable mirror
of the code readiness map.
