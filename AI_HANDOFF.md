# AI_HANDOFF.md | Phase 4.15 Yardi | 2026-10-15

Repository: `yasirskhan/property-platform`
ONLY branch `chatgpt/checkpoint-005-safety`.
Never touch main or another branch, never force-push.
Verify live HEAD and latest CI before every write.

## Last VERIFIED product checkpoint

Section 53, SHA `3fba1305ce001ac7e83a1bcc2d54c8759a6d92c3`,
GitHub Actions `38827781535`: SUCCESS on all six jobs
(backend/PostgreSQL, frontend, platform-admin, security, authenticated
E2E, staging-config). Private per-Lease-row readiness is incorporated in
the Yardi reconciliation fingerprint. A two-Tenant swap regression validates
that equal aggregate totals cannot silently retain obsolete dry-run evidence.
No customer business mutation.
Previous section 52: `4727e8803a028abbfc753db7b067f1e3fb89be0a`,
run `38826234779` SUCCESS on all six jobs.

## Current COMMITTED product batch: PROVISIONAL pending exact-SHA CI

Section 54. Organization-scoped reviewed target claims are projected once
for read-only Lease reconciliation and paginated identity preview instead of
running per-Lease review-claim SELECTs. Retained NULL provider source IDs
still contest claimed targets. Regression checks warning/current review,
constant SQL count and customer data preservation. Exact-SHA all-six-job CI
is required before verification.

## Prepared DETACHED next task, NOT branch published

Section 55: `dc0d10482be3eb28386314d3a2d529c77a121f36`
(original parent `d691b3fadd58f701b7ae45ef3e7f106452c61abd`):
project durable identity inventory's competing staff claims once
rather than SELECT per binding; test same-source identity, historical
NULL claim, cross-organization isolation, and stable query counts.
This detached Git object is NOT successful hosted CI. Repackage onto
newly verified section 54 parent; never publish it with an outdated parent.

## Mandatory next step

Verify section 54 exact-SHA six-job CI; fix any failures and update the
handoff and roadmap. Immediately repackage section 55 on the verified
section 54 branch HEAD; test, commit, obtain six-job exact-SHA hosted CI,
and continue the next independent Yardi Phase 4.15 safety batch.

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
