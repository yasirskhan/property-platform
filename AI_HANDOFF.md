# AI_HANDOFF.md | Phase 4.15 Yardi | 2026-10-15

Repository: `yasirskhan/property-platform`
ONLY branch `chatgpt/checkpoint-005-safety`.
Never touch main or another branch, never force-push.
Verify live HEAD and latest CI before every write.

## Last VERIFIED product checkpoint

Section 51, SHA `5fc4bfca1f94912ea5a42c9c6ba6b3f182004759`,
GitHub Actions `38823731721`: SUCCESS on all six required jobs
(backend/PostgreSQL, frontend, platform-admin, security, authenticated
E2E and staging-config). Run-level reconciliation now projects reviewed
target claims once and fails closed on historical NULL-source claims.
Owner/Tenant/Vendor test regressions cover fingerprint drift without
customer mutation. Prior section 50: `047da93677abaa1d088a770f942e27f4bf464971`,
CI `38817670120`, all six jobs SUCCESS.

## Current COMMITTED product batch: PROVISIONAL pending exact-SHA CI

Section 52. Five identity binders, read-only durable binding inventory,
Lease identity preview/reconciliation and accepted/replayed Lease source
relationships use NULL-safe reviewed source comparisons. This prevents
historical unknown-source MATCH_EXISTING evidence from bypassing competing
customer target safeguards. Focused regressions protect Property, Unit,
Owner, Tenant, Vendor, Lease and inventory paths. Metadata and diagnostics
only; no customer or financial record mutation. Verify new exact-SHA
hosted six-job CI before marking product changes VERIFIED.

## Prepared DETACHED next task, not verified or branch published

Section 53: `c33fad46b4368b8e908aaab2d0ef25abbfdb276f`
(original parent `75cff2008ed41e288cd690bf95fa4322ff44a545`):
per-Lease-source readiness fingerprint plus equal-count Tenant target
swap test. Repackage onto newly verified section 52 parent using
expected-SHA branch updates; never publish the detached commit directly.

## Mandatory next step

Verify section 52 exact-SHA hosted six-job CI; fix failures, update root
handoff and roadmap after success; immediately repackage and publish
section 53, verify CI and continue safe Phase 4.15 work. Never stop after
one green CI or handoff. Preserve prior evidence and customer data.

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
