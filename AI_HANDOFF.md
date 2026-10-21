# Property Platform - current recovery checkpoint

Observed: 2026-10-21T05:21:16.924Z (UTC).
Repository: `yasirskhan/property-platform`.
ONLY branch: `chatgpt/checkpoint-005-safety`. Read root AGENTS.md first.

## Exact source and CI before this documentation cleanup
- Published source HEAD: `8b8f9a36d039117ddb8fcf22b71c186a9254b85a`.
- [Actions 39546681328](https://github.com/yasirskhan/property-platform/actions/runs/39546681328): FAILED. backend failed; frontend, platform-admin and security passed; e2e and staging-config SKIPPED.
- Last independently checked all-six-green source: `7c9cece747d829f4ca8ac0b59aceff81cba216d7`, [run 39536297032](https://github.com/yasirskhan/property-platform/actions/runs/39536297032).
- This recovery cleanup changes documentation/guidance only and DOES NOT repair or verify the failed source. Its own CI must also be checked. Do not publish a new feature or claim the phase verified over these failures.

## Immediate next executable action: repair all five backend failures
Read failing backend job 119046313388 in run 39546681328. Summary: 5 failed, 1599 passed, 35 deselected.
1. tests/test_affordable_evidence.py::test_program_inspection_summary_reuses_inspection_scope_not_hqs: expected HTTPException was not raised. Inspect the actual inspection/program permission path and fixture; repair the cause while preserving the intended independent authorization boundary. Do not remove the denial assertion to obtain green.
2. tests/test_migrations.py::test_fresh_database_bootstrap_creates_current_schema_and_stamps_head.
3. tests/test_migrations.py::test_legacy_schema_snapshot_upgrades_to_head.
The last two compare new head `e6b4d2a7c910` against old expected `b8f2a91c4d65`; reconcile the additive inspection-review migration and bootstrap upgrade with the actual migration graph.
4. tests/test_postgres_smoke.py::test_postgres_fresh_bootstrap_when_ci_database_is_available.
5. tests/test_prepare_database.py::test_prepare_database_bootstraps_empty_then_upgrades_safely.
The last two still expect 213 tables; the new model schema has 214. Verify the exact new table, migration and bootstrap parity before updating expectations. Do not mask missing/extra schema.
Run focused regressions, publish the coherent repair with expected-SHA fast-forward, then verify ALL SIX hosted jobs at the repair SHA. Preparing independent code while CI runs does not authorize publishing another feature over red.

## Phase 5 implementation truth
Recent published source includes independent inspection-review backend/UI/migration, monthly on-call calendar and bounded attention-scan fairness repair. These additions remain UNVERIFIED while the current full workflow fails.
The authoritative acceptance matrix is docs/PHASE5_ACCEPTANCE_AND_ISSUES.md. OPEN requirements include:
- P5-AUTO-01 autonomous execution (the current worker only records in-app overdue attention).
- P5-DLV-02 real provider delivery/acknowledgement and vetted vendor controls.
- P5-ESC-03 actual timed backup routing, delivery, overrides and recovery.
- P5-INSP-04 complete inspection evidence/attachments/offline/review acceptance.
- P5-PM-05 complete preventive scheduling/occurrence/recovery acceptance.
- P5-PROC-06 purchasing, receiving, inventory/materials, allocation and reversals.
- P5-FIN-07 approved invoices/payables/tenant-charge safeguards and financial lifecycle.
- P5-ACC-08 complete role/tenant/audit/browser/release acceptance.
Phase 5 remains OPEN. Do not advance to Phase 6. Owner opt-in UI, a helper/service or a green subset is not complete Smart Dispatch. Global unattended dispatch and unverified provider/financial capabilities remain OFF.

## Required sources and continuation
Read docs/PHASE5_ACCEPTANCE_AND_ISSUES.md, docs/PHASE5_MAINTENANCE_QUEUE.md, docs/FEATURE_REGISTRY.md, docs/PLAN_GAPS.md, docs/PROJECT_MASTER.md, and relevant current source/tests.
After repairing CI, reconcile the first unfinished approved end-to-end workflow from that matrix; preserve inherited property policy, groups, business hours, urgency, scheduling, permissions and audit requirements. Do not reimplement verified earlier phases.
Root AI_HANDOFF.md is the active checkpoint; docs/AI_HANDOFF.md is older background. No local unsaved draft or new detached candidate is claimed by this cleanup.
Previous development conversation, observed with a completed response and available composer: https://chatgpt.com/c/6ad83dd3-ba70-83e9-a639-b2618da181f1 .
Use docs/SESSION_CONTROL.md for coordinated transfer and truthful periodic monitoring.

## History preservation
The ENTIRE pre-cleanup root handoff is preserved unchanged at:
`docs/AI_HANDOFF_ARCHIVE_2026-10-21_8b8f9a36.md`
It reuses original Git blob `1e8247f2b747bc01a2f07930097d6f61a12eb3ee`.
Older archives, all feature IDs, specifications, registers and frontend/AGENTS.md remain unchanged. Search archives only for a related unresolved detail.

## Closeout discipline
Record published versus saved candidates, exact successful source/run/jobs and remaining blockers. Keep this file concise by replacing stale current facts instead of appending history. Fix failures, update actual feature/issue registers and continue substantive approved work within active execution limits; never claim a nonexistent background process.
