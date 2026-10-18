# Phase 5: Work-order queue foundation

## Scope and current status

This grouped candidate is **not VERIFIED** until the hosted CI for its final
exact SHA passes backend/PostgreSQL, frontend, platform-admin, security,
authenticated E2E and staging. Phase 5 as a whole is not completed.

The existing work-order lifecycle remains unchanged. This milestone adds an
accessible work-order queue with role-safe filters and pagination:

- API: `GET /work-orders` accepts optional `status`, `priority`,
  `category`, `property_id`, case-insensitive literal `search` (title
  or description, 2–80 characters), `limit` (1–200) and `offset`
  (0–100000). Old calls without `limit` continue returning all visible
  orders, preserving existing dashboards and integrations.
- Stable ordering by created timestamp descending, then ID descending.
  Wildcard characters `%` and `_` in searches are treated literally.
- Authorization is evaluated before filters. Admin/owner must remain in
  their own organization; managers must be actively assigned to a property
  **in their own organization**, preventing a stale cross-organization
  assignment from leaking orders. Tenants see their own requests, and
  crew see assigned work orders.
- UI: `/dashboard/maintenance/work-orders` supports the above filters, clear,
  page navigation, role-scoped results and empty/error states. Manager
  dashboard links to this page and counts only nonclosed, noncancelled
  work orders.

## Verification gates

Database-backed tests demonstrate exact-ID tie-break pagination, literal
wildcard search, attribute filters, role-scoped visibility and deliberately
malformed cross-organization manager assignment denial. Authenticated
Playwright smoke navigates the work-order page, applies search, and verifies
the empty state on the disposable seed.

## Not included in this milestone

No recurrence scheduling, auto-dispatch, vendor escalation, messaging,
purchase orders, work-order-to-bill conversion, field inspections or
customer accounting mutation. These are separate Phase 5 requirements
and must not be advertised as complete.

## Route readiness for the first implemented maintenance page

The canonical `MAINTENANCE.WORK_ORDERS` route and its parent `MAINTENANCE`
are no longer blocked by navigation readiness. This exposes the real
`/dashboard/maintenance/work-orders` page only through existing entitlement,
role/user and personal-visibility filters. All remaining Phase 5 maintenance
routes remain fail-closed until implemented, tested and independently unblocked.
`backend/tests/test_navigation_integrity.py` verifies the visible parent and
Work Orders leaf and that all other unfinished maintenance leaves remain hidden.
This change does **not** open a whole Phase 5 module or grant missing permissions.

## Work-order detail and activity (follow-up, provisional)

A dedicated role-scoped detail page at
`/dashboard/maintenance/work-orders/[id]` loads the existing backend work-order
detail, status history and comments. The queue title links to this page. An
authorized user can add an activity note; the existing backend checks work-order
access before persisting it. No new fields, payments, dispatch decisions,
notifications or automated status transitions are introduced. A disposable
Playwright smoke test authenticates, submits one work order, views its detail,
records a note and verifies it appears in history. This follow-up remains
PROVISIONAL until the full six-job CI succeeds for its final exact SHA.

## Role-aware lifecycle controls (follow-up, provisional)

The detail view surfaces only the next existing backend-validated transition:
admin/owner/manager may acknowledge SUBMITTED or approve-close COMPLETED;
an assigned CREW member may start ASSIGNED or mark IN_PROGRESS completed
with optional resolution notes. A note-only flow remains available to all
authorized work-order participants. Button visibility is merely usability;
backend role, assignment, organization and state checks remain authoritative.
The authenticated browser regression additionally verifies that an admin can
acknowledge the newly submitted work order and see the recorded result. This
change requires hosted E2E and backend verification at its eventual exact SHA.

## Audited generic edits (follow-up, provisional)

The legacy generic `PATCH /work-orders/{id}` workflow now rejects attempts
to change `status` directly with HTTP 409; status changes must use the
existing explicit acknowledgement, assignment, crew work, close/cancel routes.
Permitted edits write the work-order fields, activity entry and immutable
audit event containing before/after values in one database transaction,
rather than committing the fields and event separately. The database-backed
regression verifies before/after audit content and the status-bypass denial.
This changes the generic-PATCH status behavior intentionally for integrity;
client workflows should call dedicated lifecycle endpoints. This follow-up is
provisional until the exact hosted commit CI passes all six jobs.

## Manual crew assignment (follow-up, provisional)

After staff acknowledgement, authorized admin/owner/manager can choose an
active organization crew member from the existing role-scoped users endpoint.
The backend accepts assignment only from ACKNOWLEDGED or ASSIGNED, verifies
both parties' organization and the crew's active property assignment, rejects
unavailable/inactive users and terminal or in-progress orders, and returns a
no-op for replaying the exact same assignment. It records genuine assignment
changes in the existing work-order activity history. No automated dispatch,
notification, on-call routing or vendor contract is implied. Database-backed
and authenticated browser regressions accompany this candidate; verify it at
exact hosted SHA before treating it as delivered.

## Transaction-atomic work-order creation and acknowledgement (follow-up)

New work-order submission now inserts the work-order and the initial status
history in the **same transaction**, rather than committing the order before
its activity event. Staff acknowledgement similarly commits its changed status
and history in one transaction. Database tests assert one creation event and
one acknowledgement event on the same authorized order. Neither workflow
creates charges or financial postings. Hosted full-suite CI remains required
before this follow-up is considered VERIFIED.

## Status, assignment and comment audit coverage

A work-order status transition now produces both the existing activity-history
entry and an append-only organization-scoped audit event with actor and
before/after status. Crew assignment produces an additional before/after crew
ID record, while replaying an unchanged assignment is a no-op. Comments use
an audit event pointing at the activity row; comment text remains in the
work-order activity trail rather than being copied into the global audit
ledger. The API enforces the UI's 2,000-character comment limit. Changes are
transactional and regression-tested; full hosted six-job CI is required
before declaring the batch VERIFIED.

## Role-scoped operational queue counters (prepared, CI pending)

A read-only `GET /work-orders/summary` provides five counts of work orders
that the current actor is permitted to see: open (anything not closed or
cancelled), emergency open, acknowledged but not yet crew-assigned, in progress,
and completed awaiting close. The query uses the same organization/property,
manager-assignment, tenant and crew isolation as the ordinary list, with
DISTINCT work-order IDs so duplicate assignments cannot inflate totals.
Summary counters appear above filters; they reflect all authorized orders,
not just current list filters. On failed summary reads, the interface shows
"Summary unavailable" rather than reporting a misleading zero. Tests prove
foreign organizations and unauthorized properties remain excluded.

## Authorized new-request unit picker and intake form (prepared)

`GET /work-orders/request-units` lists only minimal same-organization active
property and unit labels. Tenants see units from their active leases; managers
see only actively assigned properties; admins/owners remain organization
scoped; crew and unrelated roles receive no unit choices. Case-insensitive
literal property/unit search and bounded limit/offset pagination avoid
unbounded disclosure. `POST /work-orders` now explicitly rejects any
cross-organization unit even when a malformed active lease would appear to
authorize it. The new customer route
`/dashboard/maintenance/work-orders/new` collects a unit, issue title,
description, category, urgency and optional entry permission, and submits
through the existing work-order API. Tenant and manager dashboards link to it.
Database regressions include cross-organization forged leases and staff
attempts; authenticated E2E checks the disposable org's authorized unit.
This is NOT all of the planned smart maintenance intake and is not VERIFIED
until the final exact-SHA hosted CI passes all jobs.

## Similar requests during intake (new, not CI verified)

The request form now has an optional check for existing open orders for the
selected unit. It searches the first 80 characters of the entered title and
shows up to five matches; closed and cancelled work orders are excluded.
Results use the existing server-side organization and role restrictions.
The feature does not block intake or decide whether an order is a duplicate.
Automated tests include different roles, cross-organization restrictions,
literal wildcard handling and an authenticated browser lookup.
