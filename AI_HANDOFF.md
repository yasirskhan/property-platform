# AI_HANDOFF.md | Phase 4.15 Yardi | 2026-10-15

Repository: `yasirskhan/property-platform`
ONLY branch `chatgpt/checkpoint-005-safety`.
Never touch main or another branch, never force-push.
Verify live HEAD and latest CI before every write.

## Last VERIFIED product checkpoint

Section 52, SHA `4727e8803a028abbfc753db7b067f1e3fb89be0a`,
GitHub Actions `38826234779`: SUCCESS on all six jobs
(backend/PostgreSQL, frontend, platform-admin, security, authenticated
E2E, staging-config). Historical NULL Yardi source IDs now fail closed
across five existing-target binders, durable inventory, Lease preview,
reconciliation and accepted/replayed Lease source reviews. Focused
Property/Unit/Owner/Vendor/Tenant/Lease/inventory regressions included.
Previous section 51: `5fc4bfca1f94912ea5a42c9c6ba6b3f182004759`,
run `38823731721` SUCCESS all six. No customer business mutation.

## Current COMMITTED product batch: PROVISIONAL pending exact-SHA CI

Section 53. Read-only lease source reconciliation now includes private
per-Lease-row readiness in the review fingerprint, preventing equal-total
source-target swaps from preserving an obsolete reviewed dry-run digest.
A two-tenant, two-source-row regression proves the fingerprint changes
without modifying customer Lease or financial records. Verify exact-SHA
six-job GitHub Actions CI before marking VERIFIED.

## Prepared DETACHED next tasks, NOT branch published

Section 54: `d691b3fadd58f701b7ae45ef3e7f106452c61abd`
(original parent `4db21a7995ae56d2838e6f246a4e091f0eeab1fd`):
reuse organization-scoped reviewed target claims in read-only Lease
aggregate and paginated preview, preserving NULL-source fail-closed
semantics; test customer nonmutation and stable SQL lookup counts.

Section 55: `dc0d10482be3eb28386314d3a2d529c77a121f36`
(original parent `d691b3fadd58f701b7ae45ef3e7f106452c61abd`):
project durable identity inventory's competing staff claims once
rather than SELECT per binding; test same-source identity, historical
NULL claim, cross-organization isolation, and stable query counts.

These are unpublished Git objects, NOT successful hosted CI. After
section 53 passes exact-SHA CI, repackage section 54 on the new verified
parent, then section 55 on its newly verified parent. Never publish a
detached commit whose original parent differs from live branch HEAD.

## Mandatory next step

Verify section 53 exact-SHA six-job CI, fix reds and document exact
results in handoff/roadmap. Then immediately repackage section 54, verify exact-SHA CI,
and continue with section 55 only after section 54 passes. Inspect further
Phase 4.15 gaps afterward. External Yardi source contracts still gate accounting,
Lease/occupancy mutation and any official API adapter.

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
