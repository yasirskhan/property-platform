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
