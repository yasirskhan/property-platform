# AI_HANDOFF.md | 2026-10-15 Phase 4.15 Yardi

Repository: `yasirskhan/property-platform`
ONLY authorized branch: `chatgpt/checkpoint-005-safety`
Never touch `main`, create a branch, force-push, or overwrite another agent's changes.
Use the connected GitHub integration directly in normal ChatGPT, not Work mode.
Verify LIVE HEAD and latest GitHub Actions before any subsequent write.

## Last fully VERIFIED product checkpoint

Commit: `1923bb64fd12a737536dc37c6d204e725eca523d`
Exact-SHA CI run: `38779933369` SUCCESS, all six jobs:
backend/PostgreSQL PASS; frontend PASS; platform-admin PASS;
security PASS; authenticated E2E PASS; staging-config PASS.

This verified commit includes the Unit MATCH_EXISTING replay protections
and fast Yardi CI gate coverage. Owner/Tenant/Vendor later competing review
claim checks were previously verified at
`a3b4ae52e97054ff692f854ca7f9400f5aec2c34` (run `38778001779`,
all six PASS; backend/PostgreSQL 1296 passed, 21 deselected).

Preceding verified Property replay correction:
`48d36e2c104cf23156de8a2b1ed7c262caac817d`, run `38696745662`,
attempt 2 SUCCESS, all six jobs. E2E attempt 1 had a transient
Short-term Rentals browser login navigation timeout; the rerun passed.

Verified product scope: Property staff MATCH_EXISTING replay revalidates
later durable target/source conflicts; Owner, Tenant and Vendor staff
MATCH_EXISTING replays recheck competing historical review claims rather
than returning stale idempotent success. See `docs/YARDI_MIGRATION_PLAN.md`
sections 40 and 41. Regression:
`backend/tests/test_yardi_property_match_review.py` and
`backend/tests/test_yardi_review_replay_claims.py`.
No customer business mutation or financial posting.

## Current newly committed product batch: PROVISIONAL until its exact-SHA CI

Yardi Owner, Tenant and Vendor MATCH_EXISTING replay:
- A same-run durable binding must still carry the exact original staged
  source fingerprint, even when target entity and target ID are unchanged.
- Reject stale replay with HTTP 409 while preserving audit/review evidence
  and customer identity data.
- Parameterized regression:
  `backend/tests/test_yardi_review_replay_claims.py::
  test_review_replay_rejects_changed_durable_source_fingerprint`
  exercises all three resources, drift rejection and recovery.
- The reviewed change originated in detached commit
  `627ce2db2c63983c55742ced14f9174bbeb1e08d`, but was transplanted
  onto the verified Unit-replay branch rather than publishing its obsolete
  detached parent. See migration plan section 43.

Do not label this batch VERIFIED until exact-SHA six-job CI passes. Repair
any red job and verify the replacement SHA before advancing the branch.

## Immediately actionable next bounded batch

After this source batch is verified, inspect current Yardi staff-review,
binding, reconciliation and invalidation paths for the next independently
demonstrable mismatch, especially historical replay and durable binding
consistency for Property/Unit/Owner/Tenant/Vendor. Do not repeat verified
fixes or enable unsafe customer/financial posting.

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
