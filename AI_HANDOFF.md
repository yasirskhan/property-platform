# AI_HANDOFF.md | Phase 4.15 Yardi | 2026-10-15

Repository: `yasirskhan/property-platform`
ONLY branch `chatgpt/checkpoint-005-safety`.
Never touch main or another branch, never force-push.
Verify live HEAD and latest CI before every write.

## Last VERIFIED product checkpoint

Section 56, SHA `24b702c6d517561d174f003c7f0f4844450397bd`, GitHub Actions `38836676853`:
SUCCESS, all six jobs (backend/PostgreSQL, frontend, platform-admin,
security, authenticated E2E, staging-config). Paginated read-only Unit
inventory batches exact historical reviewed source-parent evidence and
retains contradictory/unknown-source safety checks. No customer mutation.
Previous section 55: `9d159a46b7b7365cbc38cc69b5a62acd760b72ea`,
run `38832851778` SUCCESS on all six jobs.

## Current COMMITTED product batch: PROVISIONAL pending exact-SHA CI

Section 57. An unresolved duplicate or changed Property source version
invalidates the read-only original Unit source-parent classification even when
the live Unit still belongs to the same active customer Property. Focused
regression checks mismatched Property staged versions, reason-coded duplicate
SKIP recovery and preservation of customer Property/Unit. Verify exact source
commit through all six hosted CI jobs before marking VERIFIED.

## Prepared DETACHED next batches, NOT branch published

Section 58: `dce8d6db3736ad3a18aeb9f1fe14a47652e42b65`
(original parent `464b54111234b574d85db06a3d6e1f6a2e66b798`):
add diagnostic for ambiguous mapped Property source-parent claims to
read-only inventory and platform-admin Yardi staff console; regression
checks current/ambiguous/recovered classifications.

Additional independent draft work (NOT branch published, not CI verified):
Section 59 detached tree `24637ee6c651bf8e989696a9aa00baca682c0a46`,
built on the prepared Section 58 tree: reject stale exact mapped Property
source fingerprints in read-only Unit parent readiness, with regression.
Section 60 detached tree `38145e93504a8240306a542997fc8707ac2ecad7`,
built on Section 59: show an explicit source-drift warning in staff console.
Review and rebase these trees against verified parents before publishing.

These Git objects are NOT published or verified. Repackage each against
the newly verified parent in order. Never publish original detached commits
with outdated parent SHAs or skip exact-SHA CI.

## Mandatory next step

Verify section 57 all-six-job CI at its exact branch SHA, repair reds
as necessary, update handoff/roadmap, then immediately publish Section 58
against the newly verified parent. Continue with reviewed independent draft
Sections 59/60 only after their prerequisite verified batches.
External Yardi source contracts still gate accounting, Lease/occupancy mutation
and official API.

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
