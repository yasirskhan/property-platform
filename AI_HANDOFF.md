# AI_HANDOFF.md | 2026-10-15 Phase 4.15 Yardi

Repository: `yasirskhan/property-platform`
ONLY authorized branch: `chatgpt/checkpoint-005-safety`
Never touch `main`, create a branch, force-push, or overwrite another agent's changes.
Use the connected GitHub integration directly in normal ChatGPT, not Work mode.
Verify LIVE HEAD and latest GitHub Actions before any subsequent write.

## Last fully VERIFIED product checkpoint

Commit: `79c531d8071bd088a4fbee256ba9e083f8da5f07`
Exact-SHA GitHub Actions run: `38803856489` SUCCESS, all six required jobs:
backend/PostgreSQL PASS; frontend PASS; platform-admin PASS;
security PASS; authenticated E2E PASS; staging-config PASS.

Verified product: section 43 exact durable source fingerprint revalidation
when replaying historically reviewed Owner, Tenant and Vendor identities.
Parameterized regression: `backend/tests/test_yardi_review_replay_claims.py::
test_review_replay_rejects_changed_durable_source_fingerprint`.
The previous verified Unit review replay checkpoint is
`1923bb64fd12a737536dc37c6d204e725eca523d`, CI `38779933369`
(all six PASS). The preceding Owner/Tenant/Vendor competing staff claim
replay guard was verified at `a3b4ae52e97054ff692f854ca7f9400f5aec2c34`,
CI `38778001779` (all six PASS). Property review replay source/target
claim guards were verified at `48d36e2c104cf23156de8a2b1ed7c262caac817d`,
CI `38696745662` attempt 2 (all six PASS).
No customer business mutation or financial posting.

## Current newly committed product batch: PROVISIONAL until its exact-SHA CI

All five reviewed existing-target identity binders (Property, Unit, Owner,
Tenant and Vendor) now reject initial binding or idempotent replay when
another Yardi source's retained staff review claims the same live customer
target. Keep source/run
identity scoping, exact fingerprints, target activity checks and immutable
business data intact. Parameterized regression:
`backend/tests/test_yardi_review_replay_claims.py::
test_reviewed_binding_rejects_later_staff_target_claim_on_first_bind_and_replay`.
Property and Unit regressions:
`backend/tests/test_yardi_reviewed_property_binding.py::
test_property_binding_rechecks_later_staff_claim_on_initial_bind_and_replay`
and
`backend/tests/test_yardi_unit_ingestion.py::
test_unit_binding_rechecks_later_staff_claim_on_initial_bind_and_replay`.
Both are added to the fast Yardi CI gate.
The reviewed work combines previously detached commits
`8757d3a2afa7189e91aa52c6d21960c07bb6e8ca` and
`69eab0fce2126204e9fac383b8a2e90ed19842bd` into one bounded
five-resource binding-claim safety batch rebased onto the latest verified
parent with this handoff. See plan sections 45 and 46.
Do not mark VERIFIED until this replacement commit's exact-SHA six-job CI passes.

## Immediately actionable next bounded batch

After this batch passes exact-SHA six-job CI, reconcile the prepared
run-level reviewed and durable identity coverage from detached commit
`49415b4516eef8a524eec50545adf78bdbed96de` (plan section 47).
Do not publish the old detached SHA directly after repackaging its parent.
Repackage with the new verified parent and the updated handoff.

Additional dependent prepared work, **not** branch-committed or verified:
- `8e15fdea7a192fd4cf580c94b90c5d9fa763cb9b`: read-only Lease
  target-claim acceptance/preview/summary/staff UI revalidation.
- `6d166d53d756391dd92a3bd3c982d06d164e40c1`: durable identity
  inventory staff warning for competing reviewed target.
They are detached, dependent historical commits and **must not be directly
pushed** after repackaging their parent. Repack each on the newly
verified live parent using expected-SHA branch protection and exact CI.

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
