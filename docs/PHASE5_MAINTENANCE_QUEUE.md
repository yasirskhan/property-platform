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

## Inactive/deleted unit and property intake safeguards (VERIFIED)

New maintenance requests fail closed for units or their parent properties when
inactive or soft-deleted. The picker also excludes all four unavailable states.
Existing maintenance and inspection history is unchanged. Regression tests
exercise the picker and the server-side submit guard for each state.
Verified at `ac8f312847b1e59c5b2d24af2989b6f1a4bf7abd`, hosted run `39181939149` (all six jobs PASS).

## Limited staff inspection records (published; exact CI pending)

ADMIN/MANAGER staff can record dated unit-condition evidence and findings in a
small dedicated page linked from the Work Orders queue. The existing audited
inspection API enforces reporting/unit permissions, active property scope and
staff-only recording. Authenticated browser coverage waits for the signed-in
shell and verifies creation and visible findings. Back navigation goes to the
implemented Work Orders queue. Do not unhide the canonical full Inspections
menu or claim mobile/offline/photos/checklists are complete.

## Staff inspection route-readiness repair (provisional)

The limited staff evidence page uses `/dashboard/maintenance/staff-inspection-records`, an explicitly
noncanonical route linked by the Work Orders queue to ADMIN/MANAGER only.
The canonical `/dashboard/maintenance/inspections` is deliberately ABSENT from
page source, keeping the `MAINTENANCE.INSPECTIONS` sidebar readiness block
intact until the full module is ready. This avoids weakening the independent
navigation-integrity gate; exact-SHA hosted CI remains required.

## Archived inspection evidence review (provisional; CI required)

Staff-recorded inspections remain available through the existing scoped API and
report after their unit or property is deactivated or soft-deleted. New entries
still require both the unit and its property to be active and not deleted.
ADMIN and currently assigned MANAGER access continues to require the same
organization, active user, and reporting/property permissions; a revoked
manager assignment cannot read archived evidence. The original immutable
inspection rows and audit records are preserved without new financial writes.
Database regression covers both inventory retirement states, write denial,
foreign organization, tenant denial, and assignment revocation. This is a
limited historical-evidence repair, not the full Phase 5 inspection module.
Mark VERIFIED only after all six hosted jobs pass at its exact published SHA.

## Staff inspection unit search (prepared, not yet published)

The limited staff evidence screen will use the already server-scoped active-unit
picker with an optional property/unit-number search, showing at most 100 matches
per query rather than trapping a large organization at the first 100 units.
An explicit search button avoids searching on every keystroke, clears any
previous unit selection, and displays lookup errors separately from historical
inspection reads. The inspection POST retains the server-side role/property/
active-inventory authorization and append-only audit. Authenticated E2E covers
a successful searched-unit recording. This is not a full inspection module.

## Maintenance intake unit-picker manager revocation (prepared)

The shared unit picker used for both maintenance requests and staff unit search
must require an active, **non-soft-deleted** manager PropertyAssignment.
Regression covers a stale active flag with deleted_at set: the manager can no
longer enumerate the unit, while organization ADMIN access is unchanged.
This is a scoped access repair, not a change to inspection history authority.

## Staff inspection history paging (prepared, not yet published)

The staff inspection API supports optional bounded limit/offset parameters,
with the existing unpaged behavior retained for existing callers and the
separate authorized reporting/export route. The staff screen reads at most
100 entries per request, exposes a Load older inspections control when more
might exist, and handles a page failure without implying that prior saves or
already loaded history failed. Results retain inspection-date/ID ordering and
server-enforced organization/assignment/menu restrictions; automated tests
cover deterministic pages, authorized manager access and denials to foreign
organizations and tenants. No inspection records are overwritten.

## Property/work-order staff authorization repair (prepared, CI required)

A malformed cross-organization staff assignment must not grant property-detail
access, and soft-deleted assignments cannot authorize property/maintenance
visibility, manager submission, crew work, or crew assignment. Requiring
same-organization Property scope plus nondeleted active assignments preserves
ADMIN/OWNER organization rights but does not resolve the separately open
multi-owner OWNER policy review. Database regression checks rogue foreign
assignment and manager/crew revocation. Verify all six hosted CI jobs on the
published SHA before marking this security batch verified.

## Readable historical inspection location labels (prepared; CI required)

The scoped inspection API includes current property-name and unit-number
labels alongside existing stable IDs. Both freshly saved evidence and paged
history resolve labels from already authorized Property and Unit objects,
including archived inventory. The UI displays the location, retaining a safe
ID fallback for older responses. Labels are current inventory metadata,
not claimed to be immutable historical name snapshots. Regression and signed-in
browser coverage require exact-SHA hosted CI; no new access is granted.

## Work-order crew selector enum contract (prepared; CI required)

The work-order detail page must query `/users?role=CREW`, matching the
backend's uppercase UserRole enum. The former lowercase query returned HTTP
422 and made staff crew selection appear empty. Authenticated browser coverage
asserts that the page requests the uppercase crew filter and receives HTTP
200, without bypassing backend property assignment validation. This is a
UI/API compatibility repair, not automatic dispatch or a permission expansion.

## Property staff roster and assignment reactivation (prepared, CI required)

The property assignment roster excludes deleted assignment rows and inactive,
deleted or foreign-organization users even if historical records remain marked
active. Explicitly reassigning a previously soft-deleted manager/crew clears
deleted_at and realigns role; inactive/deleted users cannot be reassigned.
Database regressions check foreign-org roster access, revocation, deliberate
reactivation and inactive-user rejection. No broader role or OWNER entitlement.

## Property-scoped crew choice on work-order detail (prepared; CI required)

The work-order detail screen will use the existing authenticated per-property
assignment roster, not organization-wide crew accounts, when showing eligible
crew. The backend roster denies cross-org and deleted/inactive staff and returns
only current assignments. Client-side options filter role CREW; the assignment
POST continues enforcing actual property and status. Load failures are shown,
and old selections are cleared on property change. Authenticated E2E compares
visible select options against returned authorized crew IDs. This replaces the
intermediate uppercase `/users?role=CREW` workaround and prevents offering
staff who cannot actually be assigned. Needs its own exact-SHA six-job CI.

## Deleted crew guard on work-order assignment (prepared, CI required)

Assignment POST rejects a crew account whose deleted_at is set, even with a
stale is_active=True and live property assignment. The property-scoped UI
roster already filters deleted accounts; this guard prevents a forged request
from bypassing that safeguard. Regression verifies status remains acknowledged
and crew unset. No automatic dispatch, financial write or new permission.

## Durable work-order comment save without dependent GET (prepared, CI required)

After successful POST of a work-order comment, the detail UI appends the server-
returned activity entry instead of requiring a second GET before acknowledging
success. A temporary detail read failure no longer removes the work-order view
or incorrectly suggests the comment did not persist, preventing accidental
repeated submissions. Authenticated E2E deliberately returns 503 for the
post-save detail GET and verifies both success notice and appended comment.
Server authorization, audit, append-only history and immutable IDs are unchanged.

## Audited staff property assignments (next prepared; CI required)

Existing create/revoke/reactivate assignment routes now append a property_assignment
audit row in the SAME transaction as the change, with actor, organization,
property/user/role, and before/after active state. Idempotent repeated assign or
revoke does not create a spurious event; cross-organization denial creates no
audit or mutation. Regression checks this full lifecycle and append-only row
content on a disposable database. Audit logs are not silently deleted.

## Durable lifecycle status after read outage (prepared; CI required)

The work-order detail page now accepts the persisted status transition POST
response as authoritative. A follow-up GET refresh is optional; a read outage
does not clear the work-order detail or display a false failed transition. The
actual backend state machine and append-only audit remain authoritative. The
authenticated browser test simulates HTTP 503 on detail GET after acknowledge,
verifies the saved status and notice remain visible, and still submits a
comment during that same outage. No new lifecycle action is exposed.

## Durable crew assignment acknowledgement (prepared; CI required)

After a successful backend-validated work-order assignment POST, the detail
screen keeps the server-returned assigned crew and ASSIGNED state even when a
later detail GET fails. It clears stale crew selection and treats follow-up
activity refresh as best-effort only, reducing accidental assignment retries.
Backend staff/property validation and append-only assignment audit remain the
security boundary. This is a UI reliability improvement, not dispatch automation.

## Audited staff offboarding and restoration (prepared; CI required)

The existing user account deactivation route now adds an append-only audit
with actor, organization and before/after is_active status, in the same
transaction as the access change. Explicit admin/owner/manager user edit
re-activation/deactivation via is_active also writes the same audit; null
is_active is rejected, and repeated no-op changes emit no duplicate events.
Database regression checks deactivation, restoration, idempotence and
cross-org denial. These are staff access integrity safeguards; no owner
multi-property entitlement decision or new user roles are introduced.

## Inactive/deleted customer credential revocation (prepared, CI required)

The customer authentication boundary now rejects accounts with is_active=False
or deleted_at set at password verification, on EVERY protected request using an
existing customer JWT, and at two-factor challenge completion. This prevents
staff offboarding from being merely cosmetic while a valid token survives.
Database-backed regression checks active controls, deactivated and soft-deleted
logins, reused JWTs and pre-issued MFA challenges. No new token audience,
permission or user role is introduced; the platform-admin identity domain
remains separately governed. This security change must pass hosted CI.

## Invalid signed customer token subjects (prepared; CI required)

Both customer JWT and two-factor challenge boundaries now return HTTP 401 for a
signed but nonnumeric subject, rather than raising a ValueError/HTTP 500 while
casting the subject to a user ID. New regression generates audience-valid JWT
and 2FA challenge tokens with malformed subjects and checks the deny response.
This complements revoked-user checks without changing key material, audiences,
2FA policy or authorization entitlements.

## Soft-deleted user restoration is not profile editing (prepared; CI required)

A staff user marked deleted_at cannot be restored simply by PATCHing
is_active=True, which would create an inconsistent visible state while the
login and JWT access cutoff correctly continue to reject the account. The
profile edit returns HTTP 409 and leaves active state/audit untouched; actual
undelete, if ever supported, needs its own owner-approved audited workflow.

## Scoped work-order property and unit display labels (prepared; CI required)

The existing authorized GET work-order detail response now carries optional
current property name and unit number derived from the work order's actual
Unit-to-Property relationship only after _check_access succeeds. The detail
page displays those readable labels, retaining stable-ID fallbacks for old
responses. Names reflect current inventory, not immutable historical snapshots.
Database tests check labels and cross-org/tenant denial; the signed-in browser
regression expects the seeded property/unit names. No schema migration,
financial mutation or new access role.

## Explicit work-order cancellation review (prepared; CI required)

The manager/admin/owner work-order detail screen now exposes the existing
backend-validated cancel action only for nonterminal work orders. A two-step
in-page confirmation prevents accidental cancellation; declining confirmation
has no side effect. Successful POST updates current state from the server and
survives a later detail GET outage. Existing backend status/role validation
and append-only audit record are unchanged. Database tests check authorization,
terminal state and audit idempotence; the authenticated browser test exercises
both keep and confirm paths on a disposable work order. No new right is granted.

## Audited cancellation reason in work-order lifecycle (prepared; CI required)

The manager/admin/owner detail cancellation confirmation now requires an
explanation (5–1000 trimmed characters) before the destructive POST is enabled.
The existing cancellation API remains compatible with old no-body clients,
while an explicit reason is validated, stored in the append-only status audit
new_value and included in activity. Refused blank reasons cause no state or
audit writes. Regression verifies the reason and legacy terminal behavior;
authenticated E2E checks disabled action before a reason and cleared reason
when confirmation is declined. No silent deletion, billing or auto-dispatch.

## Scoped actor names on work-order history (prepared; CI required)

The authorized work-order GET detail response now resolves human-readable actor
names for status/activity entries from users in the same organization as the
actual Unit-to-Property relationship only. Foreign-org/missing actor IDs retain
plain numeric fallback without leaking another organization's profile. Existing
comment POST returns its saved actor name immediately for the durable no-refresh
UI path. A disposable regression inserts an intentionally malformed foreign
actor record and verifies that its name remains hidden. No PII is added to the
append-only audit table and historical actor IDs remain stable.

## Readable location labels in authorized work-order queue (prepared; CI required)

Existing GET /work-orders returns optional current property-name and
unit-number fields for the work orders already visible to the requester.
A small number of batch queries after role/org/assignment filtering avoids
n+1 lookups, and only names properties in the same organization and units
whose parent matches the work-order property. The queue UI displays labels
with stable ID fallback. Paging, filters, legacy output fields and summary
are unchanged; DB tests verify role scope and no cross-org label disclosure.
No tenant, owner, crew permissions are widened.

## Server-side activity note validation (prepared; CI required)

Work-order activity POST trims notes server-side and rejects whitespace-only
payloads with 422, even if a client bypasses its existing trimmed UI guard.
Rejected notes create no activity/audit event; accepted notes return the
saved canonical text and actor label. Regression verifies no mutation on deny,
one append-only audit on accept, and unchanged organization/role checks.

## Scoped property and unit text search in work-order queue (prepared; CI required)

The existing literal case-insensitive work-order search expands from title and
description to the property name and unit number through the SAME authorized
Unit/Property joins used for role scope. All search fields are evaluated only
after organization/assignment/tenant/crew visibility. No extra result rows,
permissions or business mutations. DB tests verify property and unit matches,
cross-org and manager scoping, and literal wildcard escaping. Queue UI label
now makes the additional supported search fields discoverable.

## Emergency maintenance triage (detached; hosted CI required)

New read-only `GET /work-orders/triage` returns up to 20 open EMERGENCY-priority
orders through the SAME tenant, crew, manager-assignment and org authorization
query as the work-order queue. Submitted/unacknowledged emergencies are shown
first, followed by oldest created timestamp and stable ID, with batched current
property/unit labels and no disclosures across organizations. The Work Orders
page links each authorized result to existing work-order detail, shows explicit
unavailable/empty states, and warns that triage is not automatic dispatch or
emergency response. Tests cover order, status, bounds and all scoped roles,
plus authenticated browser heading visibility. This is not full SLA monitoring,
on-call dispatch, notifications or automated escalation.

## Emergency triage follow-through to full queue (detached; CI required)

The limited top-20 triage panel includes a working action that applies the
existing emergency-priority queue filter and resets pagination, so staff can
review all accessible emergency work without mistaking the bounded quick list
for the entire set. The filter is still server-scoped; no new data access.
Signed-in browser test verifies apply and clear of that filter.

## Authenticated emergency triage end-to-end regression (detached; CI required)

A separate real-browser test logs in to the disposable organization, creates
an emergency work order via authenticated intake, finds its exact ID/title in
the bounded authorized emergency triage region, confirms the seeded property
and unit labels, and navigates into the existing scoped work-order detail.
This complements the database role and terminal-status tests without using
mock UI data or weakening other smoke coverage.
