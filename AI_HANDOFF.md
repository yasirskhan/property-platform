# AI_HANDOFF.md | Phase 4.15 Yardi | 2026-10-15

Repository: `yasirskhan/property-platform`
ONLY branch `chatgpt/checkpoint-005-safety`.
Check live HEAD and exact-SHA hosted CI before any write.
Do not touch main, create another branch or overwrite another session.

## Last VERIFIED product batch

Section 49 at `1d9bb956bcb9976916d5da9609f7d075c1b9d42e`:
GitHub Actions `38815725119` SUCCESS, all six jobs passed:
backend/PostgreSQL, frontend, platform-admin, security,
authenticated E2E and staging-config. Read-only Yardi durable binding
inventory now exposes independent target_review_collision warning for
different-source reviewed existing customer targets, even when target
remains active. It permits repeated review of the SAME source ID.
Vendor regression checks conflict/recovery, cross-org isolation and
customer nonmutation; platform staff can see the warning.

Earlier section 48 verified SHA `b73022f034852c07b79c50559ba8fbd424c20d9c`,
run `38812602409` SUCCESS all six. Section 47 verified
`81a3fdcef15d04407809552fb05644ca1ae7ea0a`, run
`38810003222` SUCCESS all six. Binder source-ID repair section 46a:
`45060cd57670417370e0c9b8ff430341e3c4de2d`,
run `38808091338` SUCCESS all six.

## Current COMMITTED product batch: provisional until exact-SHA CI

Section 50: private reconciliation review fingerprint now includes
per-staged-identity-row current/stale classification. Previously
different customer identities could become contested while aggregate
coverage stayed identical, allowing a stale dry-run fingerprint.
Vendor two-target swap regression:
`backend/tests/test_yardi_review_replay_claims.py::
test_reconciliation_fingerprint_changes_when_competing_target_swaps_but_totals_do_not`.
No customer/financial mutations. Check live HEAD and its six CI jobs,
fix reds before marking verified.

## Prepared DETACHED only: next bounded batches

51: `5f83ff5923ef2cb77733bffad81005ba8c852bfa`
(original parent `287e492e...`). Run-level read-only reviewed
claims projection and NULL-source historical claims fail closed.
52: `75cff2008ed41e288cd690bf95fa4322ff44a545`
(original parent `5f83ff59...`). Null-safe is_distinct_from source
comparison in five binders and Lease/inventory diagnostics, with
Owner/Tenant/Vendor/Property/Unit regression coverage plus Lease and
inventory checks. Supersedes detached `1503db48...`.
53: `c33fad46b4368b8e908aaab2d0ef25abbfdb276f`
(original parent `75cff200...`). Per-Lease-source readiness
fingerprinting and equal-count Tenant-target swap regression.
None are branch-published or VERIFIED. Repackage each onto newly
verified parents using expected-SHA protection; never directly
push historical detached objects after parent replacement.

## Mandatory next step

Verify section 50 at its exact HEAD and all six CI jobs, repair any
failures, update this handoff and roadmap after success, then publish
section 51 on that VERIFIED source and continue. Repeat for 52 and 53.
Do not stop at one verified product commit or one handoff update.

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
