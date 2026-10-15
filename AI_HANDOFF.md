# AI_HANDOFF.md | 2026-10-15 Phase 4.15 Yardi

Repository: `yasirskhan/property-platform`
ONLY authorized branch: `chatgpt/checkpoint-005-safety`
Never touch `main`, create a branch, force-push, or overwrite another agent's changes.
Use the connected GitHub integration directly in normal ChatGPT, not Work mode.
Verify LIVE HEAD and latest GitHub Actions before any subsequent write.

## Last fully VERIFIED product checkpoint

Commit: `a3b4ae52e97054ff692f854ca7f9400f5aec2c34`
Exact-SHA CI run: `38778001779` SUCCESS, all six jobs:
backend/PostgreSQL PASS (1296 passed, 21 deselected); frontend PASS;
platform-admin PASS; security PASS; authenticated E2E PASS;
staging-config PASS.

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

Yardi Unit MATCH_EXISTING replay:
- Recheck any later competing staged staff review claim before returning success.
- Revalidate same-run durable source entity, target ID and exact row fingerprint;
  do not accept historical success after durable source evidence drifts.
- Keep customer Units untouched, preserve recorded reviewer evidence.
- Add focused regression `backend/tests/test_yardi_unit_review_replay_claims.py`.
- Add this test and Owner/Tenant/Vendor replay tests to the fast Yardi CI gate
  in `.github/workflows/ci.yml`.

This handoff was updated in the same source commit as the new Unit batch.
Do not call the Unit change VERIFIED until hosted CI for the exact new branch
SHA passes ALL SIX jobs. If red, inspect logs, fix, commit, verify replacement SHA.

## Immediately actionable next bounded batch

A separate detached historical work commit
`627ce2db2c63983c55742ced14f9174bbeb1e08d` implements
Owner/Tenant/Vendor staff replay revalidation of exact durable source
fingerprints with parameterized regressions (plan section 43). Its historical
parent was detached Unit commit `2a0c26b85d5e41ac0bcebba6ed48b2d354c281c8`.
Because the Unit batch was repackaged here with handoff and CI gate updates,
DO NOT push the old detached commits directly. Reconcile and transplant the
reviewed section 43 source, tests, and documentation onto the latest fully
verified branch HEAD with an expected-SHA Git ref update. Verify its own CI.

Then keep selecting independent safety, reconciliation, source validation,
audit, and staff review defects from the current Yardi plan and actual code.
Do not repeat verified work just because an older heading says provisional.

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
