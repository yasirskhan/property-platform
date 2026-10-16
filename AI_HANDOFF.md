# AI_HANDOFF.md | Phase 4.15 Yardi | 2026-10-15

Repository: `yasirskhan/property-platform`.
ONLY branch: `chatgpt/checkpoint-005-safety`.
Do not touch `main`, create branches, force push, overwrite another session or modify unrelated systems.
Read this ENTIRE handoff and verify the live HEAD and GitHub CI before each write.

## Last confirmed VERIFIED checkpoint before this milestone

Section 56, product source `24b702c6d517561d174f003c7f0f4844450397bd`,
GitHub Actions run `38836676853` SUCCESS, all six required jobs.
The subsequent Section 57 source `6969249803a2ec992769a985aa097bc5753b9414`
was provisional and was undergoing exact-SHA CI run `38838330535`
when this combined Sections 58–60 batch was prepared. Recheck the actual
conclusion and all six jobs before treating Section 57 as VERIFIED.

## Combined Sections 58–60: COMMITTED PRODUCT MILESTONE, PROVISIONAL until CI

Read the actual branch HEAD to discover the published milestone commit SHA.
These three existing prepared drafts were reviewed and consolidated rather
than redundantly reimplementing older Section 40–56 work:

1. Section 58: distinguish unresolved mapped Property source-parent collisions
   from Unit source collisions and customer-target activity; show staff warning.
2. Section 59: reject stale exact mapped Property source fingerprints in the
   read-only Unit parent readiness calculation; page-batched version lookup.
3. Section 60: expose a specific Property fingerprint drift warning in the
   platform-admin Yardi staff console.

Regression extended `backend/tests/test_yardi_durable_binding_inventory.py`:
no collision, changed duplicate Property source, reason-coded SKIP, stale
single Property mapping fingerprint, restoration, customer preservation.
No existing tests deleted, weakened or skipped. No additional platform data
mutation or unsupported source adapter was introduced. Full source/roadmap
audit reviewed the exact three-file changes against
`docs/YARDI_MIGRATION_PLAN.md` §§57–60.

**Do not mark milestone VERIFIED without all-six-job successful hosted CI at
its precise product commit SHA.** Local targeted backend/TS commands could not
be executed using this GitHub-only connector environment; require hosted
verification and repair any regressions.

## Immediate next steps

1. Verify live HEAD, branch protection, and latest exact-SHA CI; do not assume
   any SHA here remains live. Confirm Section 57 CI `38838330535` concluded
   successfully, or repair relevant reds before treating as verified.
2. Verify combined Sections 58–60 at their exact product SHA through hosted
   backend/PostgreSQL, frontend, platform-admin, security, authenticated E2E
   and staging-config jobs. Fix any genuine failures; do not spend hours on
   unrelated 15-second Short-Term Rentals navigation flakes. Do not rerun the
   already verified Section 40 work.
3. After verification, update this handoff and roadmap with exact SHA and CI.
   Immediately continue 3–5 coherent bounded Yardi Phase 4.15 sub-features,
   targeted tests first where possible, one six-job CI milestone after the batch.
   While CI runs, prepare detached follow-up code; never advance the branch
   across unverified source or overwrite a concurrent session.

## Mandatory pre-CI completeness checklist

Before each milestone publish or CI, audit changed code line by line against
`docs/YARDI_MIGRATION_PLAN.md` and this handoff: explicitly enumerate all
subitems, confirm no tests removed/disabled/weakened and no roadmap dependency
silently omitted or stubbed. Prefer single focused batches and one hosted
six-job run per milestone rather than one CI loop per microtask. Never falsify
local test results or mark provisional work verified.

## External Yardi dependency gates

Only existing controlled CSV/XLSX upload, mapping, stage, validation, review,
reconciliation, read-only dry-run and safe durable identity metadata binding
are authorized. Official Yardi API, Lease/occupancy customer mutations,
historical GL, AR/AP, payments/deposits, ownership percentage and other
financial posting require authoritative source contracts and separate explicit
approval. Never overwrite, delete or auto-merge customer records, or erase
staff decision/audit history. See
`docs/AI_HANDOFF_ARCHIVE_2026_10_15.md` for historical handoff and
`docs/YARDI_MIGRATION_PLAN.md` for full roadmap.
