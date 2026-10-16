# AI_HANDOFF.md | Phase 4.15 Yardi | 2026-10-15

Repository: `yasirskhan/property-platform`
ONLY branch `chatgpt/checkpoint-005-safety`.
Never touch main or another branch, never force-push.
Verify live HEAD and latest CI before every write.

## Last VERIFIED product checkpoint

Section 54, SHA `6cd613c2c5288e471315fb29416014179ae9e129`,
GitHub Actions `38831150479`: SUCCESS on all six jobs
(backend/PostgreSQL 1,312 passed, 21 deselected; frontend, platform-admin,
security, authenticated E2E and staging-config). The Yardi read-only
Lease aggregate and paginated preview reuse organization-scoped reviewed
target claims without per-Lease reviewed-claim SELECTs. Unknown historical
source IDs still contest customer target claims; customer data unchanged.
Previous section 53: `3fba1305ce001ac7e83a1bcc2d54c8759a6d92c3`,
run `38827781535` SUCCESS on all six jobs.

## Current COMMITTED product batch: PROVISIONAL pending exact-SHA CI

Section 55. Read-only durable Yardi Property/Unit/Owner/Vendor/Tenant
binding inventory reuses one organization-scoped retained review-claim
projection per page. Historical NULL-source target claims remain fail-closed.
A bounded SQL count regression ensures a second Vendor binding does not add
another reviewed-claim SELECT and customer data is preserved. Verify this
branch commit through all six hosted CI jobs before marking VERIFIED.

## Prepared DETACHED next batches, NOT branch published

Section 56: `961ac0f54307777fc4e386d0e98ebf0afcf598fe`
(original parent `c6b3b37785a9c2ff54cfa6da5c5405b6008fe005`):
read exact historical Unit source-parent evidence once per paginated
inventory page, preserving all contradictory reviews and NULL-source
semantics. SQL count regression across one and two Units.

Section 57: `464b54111234b574d85db06a3d6e1f6a2e66b798`
(original parent `961ac0f54307777fc4e386d0e98ebf0afcf598fe`):
fail closed on ambiguous mapped Property source versions when reporting
Unit source-parent readiness; regression checks explicit duplicate SKIP
recovery and preservation of original customer Property/Unit.

Section 58: `dce8d6db3736ad3a18aeb9f1fe14a47652e42b65`
(original parent `464b54111234b574d85db06a3d6e1f6a2e66b798`):
add diagnostic for ambiguous mapped Property source-parent claims to
read-only inventory and platform-admin Yardi staff console; regression
checks current/ambiguous/recovered classifications.

These Git objects are NOT published or verified. Repackage each against
the newly verified parent in order. Never publish original detached commits
with outdated parent SHAs or skip exact-SHA CI.

## Mandatory next step

Verify section 55 all-six-job CI at exact branch SHA, fix reds, update
handoff/roadmap, and immediately repackage and publish section 56. Then
continue the verified cycle through sections 57, 58 and further independent
Phase 4.15 work while the active session permits. External Yardi source
contracts still gate accounting, Lease/occupancy mutation and official API.

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
