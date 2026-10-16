# AI_HANDOFF.md | Phase 4.15 Yardi | 2026-10-15

Repository: `yasirskhan/property-platform`.
ONLY branch: `chatgpt/checkpoint-005-safety`.
Do not touch `main`, create branches, force push, overwrite another session or modify unrelated systems.
Read this ENTIRE handoff and verify the live HEAD and GitHub CI before each write.

## Hosted CI VERIFIED product checkpoint — Sections 57–60

Product commit `94e2ebc7c30f271c5ac9d1d5044d68173df79b16`, GitHub Actions
run `38839237751`: SUCCESS, all six jobs (backend/PostgreSQL,
frontend, security, platform-admin, authenticated E2E, staging-config).
The previous Section 57-only CI `38838330535` was cancelled when the later
superset milestone was published; no independent green claim is made for it.
Sections 57–60 are therefore verified together on the exact superset SHA.

## Last confirmed VERIFIED checkpoint before this milestone

Previous verified Section 56: `24b702c6d517561d174f003c7f0f4844450397bd`,
run `38836676853`, all six jobs passed. Section 57 was included in the
successful Sections 57–60 superset milestone above.

## Combined Sections 58–60: VERIFIED in Sections 57–60 superset CI

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

**Exact-SHA milestone VERIFIED:** See successful run `38839237751` above. The
subsequent Sections 61–66 still need their independent hosted verification.

## Consolidated follow-up Sections 61–66: PREPARED, NOT VERIFIED

This follow-up is a cohesive metadata-only inventory milestone on top of the
published Section 58–60 source `94e2ebc7c30f271c5ac9d1d5044d68173df79b16`:

1. Batch live scoped Property, Unit, Owner, Tenant and Vendor target checks.
2. Batch exact durable Property parent identity and source-fingerprint lookups.
3. Fetch retained reviewed target claims only for current inventory page IDs.
4. Preserve cross-run different/unknown source collisions and fail-closed
   ambiguous legacy mappings on the page.
5. Strengthen PostgreSQL query-count, empty-page and second-target collision
   tests without deleting/skipping tests or changing customer data.

This product batch is PROVISIONAL until its own exact-SHA all-six-job CI.
Always check the live branch HEAD to distinguish prepared source from published
code. Recheck hosted CI for `94e2ebc7`, use expected-HEAD ref updates only,
and fix reds rather than marking any provisional product VERIFIED.
No unofficial Yardi API, accounting posting, Lease/occupancy creation or
customer overwrite is permitted. Original roadmap is retained.

## Immediate next steps

1. Verify live HEAD and the newest exact-SHA CI before any write. Sections
   57–60 are VERIFIED at `94e2ebc7`, run `38839237751`.
2. Verify consolidated Sections 61–66 through a fresh all-six-job hosted CI
   on the newly published exact SHA; repair any genuine failures without
   weakening existing tests.
3. Continue subsequent coherent three-to-five-task batches while CI runs;
   prepare detached code where the branch has an unverified pending milestone,
   then advance only after its exact-SHA success. Never modify `main`.

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

## Prepared Sections 64-66

Restrict historical Yardi review-claim reads to the current inventory page. Maintain unknown-source and competing cross-run claim classifications. Strengthen the existing Vendor regression for empty pages, page-specific collisions, and preservation of business records. Detached only, pending earlier milestone verification. No established requirements removed.
