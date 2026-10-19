# Phase 5: maintenance work-order attribution contract (design gate)

**Status: DESIGN ONLY, not implemented or CI verified.**

## Current source observations (2026-10-19)

- WorkOrder.tenant_id is a required FK to users.id.
- POST /work-orders assigns tenant_id=current_user.id even for staff submissions. WorkOrderUpdate.user_id identifies the actual submitting actor.
- Tenant read access currently uses WorkOrder.tenant_id == user.id. Manager/crew use scoped current property assignments; staff and owner access also checks actual Unit -> Property organization.
- WorkOrderOut requires tenant_id as an integer, so simply making it nullable would break existing response expectations.

## Correct model for the next implementation

- Distinguish immutable request origin: TENANT, STAFF, AUTOMATION, and UNKNOWN_LEGACY.
- Store the real authenticated requester separately (requested_by_user_id, nullable for automation). Do not invent human identities for automated generation.
- Store tenant_id only when a verified real tenant is associated with the request. System-generated preventive orders and staff-originated orders may have no tenant.
- Preserve historical original values and audit trails, including ambiguous staff-originated legacy tenant_id rows. Do not silently reinterpret or bulk overwrite them.
- Perform expand / reconcile / contract schema migration with explicit API compatibility, rather than dropping NOT NULL before updating every reader and writer.

## Mandatory authorization and audit safeguards

- Tenant visibility must be based on verified tenant association, authorized lease/unit and organization, not on arbitrary submitter IDs.
- Every generated order must validate active property, schedule permissions and organization isolation at execution time.
- Schedule occurrence uniqueness must be database-enforced per organization / schedule / occurrence key, including concurrent workers and retry recovery.
- Generated order and initial activity/audit records must commit atomically, with explicit schedule and system provenance. No silent deletion or automatic finance posting.
- Automatic work orders do not confer permission to enter tenant units or authorization to charge a tenant.
- Schedule policy, effective dates, pause/resume, edits and actor audit history are required before UI release.

## Required implementation and test order

1. Inventory tenant_id consumers in endpoints, response schemas, reports, finance and imports.
2. Add new origin/requester fields via additive migration, with nonbreaking manual-write behavior and regressions.
3. Migrate manual writers/readers and tenant-visibility checks. Reconcile legacy rows explicitly.
4. Safely make tenant_id optional once downstream consumers support absent tenants.
5. Add persistent schedules, transactional idempotent occurrences, audit, authorization and denial tests.
6. Verify six-job hosted CI and authenticated E2E before exposing feature gates.

**No recurrence engine, migration or scheduled background worker is implemented by this document.**
