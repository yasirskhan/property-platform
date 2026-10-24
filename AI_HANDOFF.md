# Property Platform — Phase 5 OPEN | worker original-evidence integrity gate
Observation: 2026-10-24 UTC. ONLY `yasirskhan/property-platform` branch `chatgpt/checkpoint-005-safety`. One authorized writer; normal Chat; no Work/main/new branches/force push/Zargul/production activation.

## Startup and safety
Verify live branch SHA and six individual Actions jobs; read `AGENTS.md`, entire current `AI_HANDOFF.md`, `docs/SESSION_CONTROL.md`, `docs/PROJECT_MASTER.md`, `docs/PHASE5_ACCEPTANCE_AND_ISSUES.md`, `docs/PHASE5_MAINTENANCE_QUEUE.md`, `docs/FEATURE_REGISTRY.md`, `docs/PLAN_GAPS.md`, and actual source/tests. Previous handoff archived unmodified at `docs/AI_HANDOFF_ARCHIVE_2026-10-24_before_worker_integrity_gate.md`, other archives retained.

## Exact already-verified commits
- `8970d68e9350f69eccaa34620e111705d1a64d54` / run `40058174471`: six SUCCESS, reviewed PM backlog recovery.
- `02fdd0b171daae45320a5a1dafb7c8d67baa6369` / run `40060920637`: six SUCCESS, PostgreSQL recovery racing/audit rollback/partial retry.
- Original repair failure `150af7a92903142ce1de17e838207ae82c213ac8` / run `40062693766`: E2E RED `Please use browser.new_context()`.
- First repair `330d615db3e8219666e66cca954c18dd2b2917d4` / run `40070095207`: E2E RED (login redirect).
- `8d00c6623c09eb3674953faacd56cdef9433218c` / run `40071893735`: all SIX SUCCESS, explicit shared browser context and login transition repair. The recovery receipts, foreign/orphan original integrity, same-device cross-tab private draft preflight, and formerly detached successors are ANCESTORS, already published; never republish them.

## Current repair | exact six-job CI REQUIRED
The substantive P5-PM-05 history-integrity gate was published at `25ac92088ee143b0743b1c7d96971d1fb889b436`. GitHub run `40087600243`: backend **1652 passed, 38 deselected**, frontend, security, platform-admin and staging-config SUCCESS; authenticated E2E **37 passed, 1 failed**. Actual failure `test_corrupt_earlier_preventive_original_blocks_execution_in_staff_browser`: Playwright global `get_by_role("alert")` collides with the page-local evidence warning and Next.js route announcer; NOT a failed backend provenance check. A targeted descendant now asserts only the page-level server error `main > p[role='alert']`, preserving every test and authorization. This repair needs its OWN all-six CI before GREEN.

P5-PM-05 source still enforces complete bounded original occurrence/audit integrity before normal worker OR manual generation, reports `ORIGINAL_EVIDENCE_INTEGRITY_FAILURE` in staff single/batch health, and tests earlier cross-org originals/orphan audit, tenantless/uncharged outcomes and role/org denial. Histories beyond the 500-row review bound require a scalable operator restore solution; Phase 5 acceptance remains OPEN.

## Next executable work
On CI red: inspect actual failing logs, repair before next feature, publish only exact expected-SHA fast-forward (`force:false`). On all green: update exact SHA and run in this handoff and registers, then move to next independent approved dependency-safe executable requirement, particularly P5-INSP-04 mobile/offline recovery, P5-AUTO-01 release-gated execution and P5-ESC-03 backup routing, P5-PROC-06 supplier workflow, P5-FIN-07 financial authorization, P5-ACC-08 security/restore acceptance. Keep source of truth live code, not historical detached labels.

## OPEN acceptance / blocked external
P5-PM-05 daily worker restore, full operator validation, large history/restore drills remain OPEN; P5-INSP-04 offline/mobile/device-loss/virus-scanning/operator acceptance OPEN; P5-AUTO-01 autonomous dispatch executor OFF; P5-ESC-03 real timed vetted backups OPEN; P5-DLV-02 provider credential/consent/contract/delivery receipts BLOCKED EXTERNAL; P5-PROC-06 supplier acknowledgment, physical valuation, security/operator acceptance OPEN; P5-FIN-07 authorized ledger payments/settlement/reversal BLOCKED EXTERNAL; P5-ACC-08 end-to-end/operator/restore gates OPEN. No fabricated approvals, tenant charges or provider sends. Phase 6 Messaging only after actual Phase 5 exit.
