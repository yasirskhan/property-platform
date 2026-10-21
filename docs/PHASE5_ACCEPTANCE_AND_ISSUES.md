# Phase 5 acceptance and issue register

Updated 2026-10-21. Truthful current state; this is **not** a phase-complete signoff. Compare these rows with `docs/PHASE5_MAINTENANCE_QUEUE.md`, `docs/FEATURE_REGISTRY.md`, `docs/PLAN_GAPS.md` and the live GitHub CI run. Entries marked implemented are not an assertion that every later dependent workflow is finished.

| Approved scope | Observed implementation | Acceptance status / remaining requirement |
|---|---|---|
| Maintenance work orders, requester attribution, role scope, bounded queue, duplicate detection and activity | Backend and staff/tenant workflows with audit and browser coverage | Existing implementation, verify regression on final SHA |
| Crew dispatch, in-app pending/accept/reject/recall, arrival ETA, time evidence and independent correction | Server validations, staff and crew UI, append-only audit | Existing implementation, verify final SHA |
| Primary on-call calendar, property CREW assignment, cancellations | Authenticated scheduling UI and durable shifts | Existing implementation, verify final SHA |
| Preferred vendors by property/trade and coarse insurance state | Ranked configuration and review UI | Advisory only; vendor safety/contract/compliance authorization before real delivery remains open |
| Dispatch groups, inherited DEFAULT, Owner/Admin settings, business hours and urgency policies | Database/owner interface plus scoped resolver | Existing implementation, verify final SHA |
| Dispatch attention and audited manual follow-up cases | Manager inbox and human review/closure UI | Existing implementation, verify final SHA |
| Policy-guided first-target crew execution | Operator confirms a live, policy-configured in-app offer; transactional rechecks and audit; no external delivery | **Implementation candidate:** `maintenance_policy_offers`. Full six-job CI required |
| Autonomous dispatch (only with explicit owner opt-in), scheduled runner, exactly-once execution | Owner/Admin intent OFF by default; prepared durable five-minute system attention sweep with global release OFF, one notice per assignment and recoverable JobRun | **OPEN P5-AUTO-01:** independent full executor release, real assignment attempts/delivery states and recovery; worker only records in-app overdue attention |
| Provider channel delivery acknowledgements and vendor compliance | No verified external delivery, consent/contract gate, confirmation callbacks or reconciliation | **OPEN P5-DLV-02:** implement vetted adapters, scoped credentials, receipts and provider failure handling; never invent delivery |
| Timed SLA escalation and backups | Prepared release-gated durable timed *in-app attention* record, audit and staff UI; no notification or backup execution | **OPEN P5-ESC-03:** execute vetted backup routing, real delivery, manual overrides and retry reconciliation; automatic notice alone is insufficient |
| Inspection end-to-end including evidence attachments, reviews and offline needs | Staff inspection records/checklist/history plus independent immutable review API/UI and backend/browser regression candidate | **OPEN P5-INSP-04:** reviewer candidate still needs exact-SHA CI; attachments, offline capture/sync, complete approval acceptance remain unfinished |
| Preventive maintenance scheduling and due generation | Existing staff schedule UI, due generation, daily worker | **OPEN P5-PM-05:** reconcile all schedule/occurrence/recovery requirements with live code and acceptance |
| Purchase requests, purchase orders, inventory/materials and cost allocation | Work-order costing and vendor references do not prove purchasing/inventory approval workflow | **OPEN P5-PROC-06:** complete approval, receiving, reconciliation, reversals, stock and financial controls |
| Work-order invoices/payables/tenant-charge protections | No approved full settlement workflow verified | **OPEN P5-FIN-07:** original/adjusted amounts, review authority, protected ledger posting, reversals and receipts |
| Cross-cutting release gates, role/tenant isolation, audit and E2E acceptance | Multiple existing security and browser tests | **OPEN P5-ACC-08:** full scenario reconciliation plus all six CI jobs at exact final SHA |

All open items require backend, frontend, real authorization boundaries, isolated data, rollback-safe writes, and regression plus browser acceptance. Never mark Phase 5 complete or advance to Phase 6 while any of these remain. Publishing a commit or green CI verifies only the covered code, not this entire matrix.
