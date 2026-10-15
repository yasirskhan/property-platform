# AI_HANDOFF.md | Phase 4.15 Yardi | 2026-10-15

Repository: `yasirskhan/property-platform`. Only branch:
`chatgpt/checkpoint-005-safety`. Do not modify other branches.
Verify live HEAD and its exact-SHA six-job GitHub CI before every write.

## Last verified product checkpoint

Section 48, exact SHA `b73022f034852c07b79c50559ba8fbd424c20d9c`,
GitHub Actions `38812602409`, SUCCESS. All six jobs passed:
backend/PostgreSQL, frontend, platform-admin, security, authenticated E2E,
staging-config. Lease source metadata acceptance and previews now reject
different-source reviewed target claims for Property/Unit/Tenant, report
target-review collisions, preserve same-source-ID reviews, and do not
create customer Leases or financial entries.

Section 47 earlier verified at `81a3fdcef15d04407809552fb05644ca1ae7ea0a`
with run `38810003222` SUCCESS, all six jobs. Section 46a binder
repair verified at `45060cd57670417370e0c9b8ff430341e3c4de2d`,
run `38808091338` SUCCESS, all six jobs.

## Current newly committed batch: provisional until own CI

Section 49: read-only `/runs/{run_id}/bindings` returns
`target_review_collision` separately from `target_current` for
all five identity resources, with staff-visible warning. Vendor regression
covers conflict/recovery, same source-ID exception, cross-organization
isolation and nonmutation. Do not mark verified before exact-SHA six-job CI.

## Next prepared detached batches

Section 50: `58c24fe66f6ef09f9d25a6caa9b4507134dbd2d3`,
prepared parent `5aca144bf549e0e3b22ac9d235ec29106871b1d0`.
Fingerprint per-row readiness so swaps in contested targets invalidate
prior dry-run evidence even when aggregate counts are unchanged.
Section 51: `7dea138a4bb9c9ee822787ab0c4c345d8cc8b0ad`,
prepared parent `58c24fe...`. Scoped historical claim projection and
NULL-source conflict regression. Detached commits are not verified;
repackage each onto the most recent VERIFIED branch SHA, not the
historic detached parent.

## Mandatory immediate sequence

Check current section 49 hosted CI and exact SHA. Fix failures, verify all
six jobs, update this root handoff and the roadmap, then publish section 50
with expected-SHA fast-forward and continue the same cycle to section 51.
Never advance the branch while its prior exact-SHA CI is still running.

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
