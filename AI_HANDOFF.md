# AI_HANDOFF.md | Phase 4.15 Yardi | 2026-10-15

Repository: `yasirskhan/property-platform`
ONLY branch `chatgpt/checkpoint-005-safety`.
Never touch main or another branch, never force-push.
Verify live HEAD and latest CI before every write.

## Last VERIFIED product checkpoint

Section 50, SHA `047da93677abaa1d088a770f942e27f4bf464971`,
GitHub Actions `38817670120`: SUCCESS on all six required jobs:
backend/PostgreSQL, frontend, platform-admin, security, E2E and staging-config.
Run-level review fingerprint now includes per-row current/stale readiness,
so equal aggregate counts cannot conceal swaps of contested customer targets.
Regression `test_reconciliation_fingerprint_changes_when_competing_target_swaps_but_totals_do_not`.
Earlier verified: section 49 `1d9bb956bcb9976916d5da9609f7d075c1b9d42e`,
run `38815725119` SUCCESS; section 48 `b73022f034852c07b79c50559ba8fbd424c20d9c`,
run `38812602409` SUCCESS; section 47 `81a3fdcef15d04407809552fb05644ca1ae7ea0a`,
run `38810003222` SUCCESS. All six passed for each.

## Current COMMITTED product batch: PROVISIONAL pending exact-SHA CI

Section 51. Read-only run-level identity reconciliation now projects
same-organization staff-reviewed source target claims once, avoiding
one competitor SELECT per staged identity. NULL/unknown historical source
IDs on retained MATCH_EXISTING claims are treated as competing source
evidence instead of being silently ignored by SQL inequality. Reviewed
same source ID across runs is still not itself a collision.
Parameterized Owner/Tenant/Vendor regression covers missing source ID
and readiness fingerprint drift. No customer/financial mutation.
Check live branch HEAD and CI; do not mark verified until all six
jobs pass for the exact product SHA.

## Prepared DETACHED next tasks, not verified or branch published

Section 52: `75cff2008ed41e288cd690bf95fa4322ff44a545`
(original parent `5f83ff5923ef2cb77733bffad81005ba8c852bfa`):
NULL-safe is_distinct_from guard in five binders and Lease/inventory
diagnostics, with Owner/Tenant/Vendor/Property/Unit, Lease and inventory tests.
Section 53: `c33fad46b4368b8e908aaab2d0ef25abbfdb276f`
(original parent `75cff200...`):
per-Lease-source readiness fingerprint plus equal-count Tenant target swap test.
They must be repackaged onto newly verified parents and committed using
expected-SHA branch updates, never pushed directly after parent replacement.

## Mandatory next step

Verify new section 51 HEAD and exact-SHA hosted six-job CI; fix failures;
update the root handoff and roadmap after success; immediately repackage
and publish section 52, verify CI, then section 53. Do not stop after a
successful CI or handoff. Preserve historical evidence and customer data.

## Continuous workflow

Verify live HEAD and latest CI -> inspect handoff/plan/source/tests ->
implement bounded fix -> review/test -> commit on sole branch using expected
parent SHA -> hosted CI -> fix reds -> verify six jobs at exact SHA -> update
this handoff -> immediately start the next bounded Phase 4.15 task.
A green CI is not a stopping point. Never advance this branch while the
prior exact-SHA CI is still running; prepare detached work instead.
Never mark unverified source complete.

## External gates and preservation

Only existing CSV/XLSX Yardi upload, stage, validation, review, reconciliation,
read-only dry-run and controlled identity metadata binding are authorized.
No undocumented official Yardi API, historical GL, AR/AP, payments/deposits,
owner allocations, customer Lease/occupancy creation, or financial posting
without authoritative source contracts and explicit authorization. Never
overwrite/delete existing customer data, silently merge source IDs or rewrite
audit history. Historical handoff:
`docs/AI_HANDOFF_ARCHIVE_2026_10_15.md`. Roadmap:
`docs/YARDI_MIGRATION_PLAN.md`.
