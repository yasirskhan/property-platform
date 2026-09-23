# AI HANDOFF

**Purpose:** Current-project checkpoint for any future ChatGPT session.  
**Maintainer:** The assistant doing development. Yasir is not responsible for reconstructing technical context.  
**Last updated:** 2026-09-23

## Project
Property Management Platform (AppFolio-equivalent).

## Repository truth
- GitHub: `yasirskhan/property-platform` (private)
- Default branch: `main`
- Safety work branch: `chatgpt/checkpoint-005-safety`
- Draft PR: #2, "Safety Foundation: CI, Postgres, E2E, staging safeguards"
- `main` must remain untouched until Yasir explicitly approves a merge.
- Alembic head: `5949df11e460`
- Repository state and tests are authoritative. Chat history is not.

## Resume order
1. This file.
2. Relevant current section of `PROJECT_MASTER.md`.
3. `ENGINEERING_SAFETY.md`.
4. Relevant `FEATURE_REGISTRY.md` section.
5. `APPFOLIO_PARITY_CHECKLIST.json`.
6. Actual source/migrations/tests for the current task.
7. `PLAN_GAPS.md` / `FILE_CATALOG.md` only when needed.

## Current phase
**3.4.S Engineering Safety Foundation — final hosted closeout.**

Session 3.4.2 is COMPLETE:
- Feature Registry covers 24 current routes / 211 meaningful rows / 67 release gates.
- Strong parity checker validates registry structure, routes, and parity metadata.

## Hosted evidence already green
GitHub CI run 35897240195 proved:
- backend Python 3.12 suite against PostgreSQL 16;
- Python compile;
- parity/registry CLEAN;
- committed-secret scan;
- frontend npm install, lint, TypeScript, production build;
- fresh PostgreSQL bootstrap of all 50 model tables + Alembic stamp;
- deterministic E2E admin seed;
- PostgreSQL pg_dump + restore verification;
- authenticated Playwright login;
- Dashboard, Properties, Receipts, and Bills protected-page navigation;
- staging Compose rendering + backend/frontend image builds.

## Defects found and fixed by the safety work
- `check_parity.py` and `generate_file_catalog.py` had hard-coded Windows project paths; made portable.
- `requirements.txt` was UTF-16 and omitted runtime imports; normalized/pinned.
- fresh DB migration history could not create the pre-Alembic schema; guarded fresh bootstrap + legacy upgrade fixture now cover both paths.
- `init_db.py` omitted newer models; model-registry test now guards all 50 tables.
- GL reversal used two financial commits; reversal + original state now commit atomically with failure regression coverage.
- E2E seed used reserved `.test` domain rejected by Pydantic; fixed.
- Playwright used unreliable `networkidle`; now waits for DOM/UI readiness.

## Final 3.4.S checks in this branch sync
- CodeQL: add private-repo `actions: read` permission, keep `security-events: write`, upgrade action to v4, serialize language matrix.
- Staging: CI now starts the Docker Compose stack and checks backend `/health` and frontend `/login`.
- CI events: feature-branch push duplication removed; normal CI runs on main pushes, PRs, or manual dispatch.

## Parity state before final closeout
- 140 built
- 2 in progress
- 486 scheduled
- 628 total
- 0 unplanned / 0 phase-less expected

The two remaining in-progress safety records are staging live-start proof and CodeQL hosted proof. Flip them to built only after the new hosted run succeeds.

## Locked architecture decisions
- Hybrid Capability Gating with independent layers: release control, plan entitlement, org configuration, authorization/permission, user presentation.
- Non-applicable layers auto-pass.
- UI hiding is never security. Backend authorization/entitlement is authoritative.
- Do not gate routine fields/columns/filters merely because they are future-facing.
- No arbitrary target flag count.
- Safe refactoring is allowed with regression protection.
- `check_parity.py CLEAN` is planning consistency only.
- Core launch precedes specialized expansion products.
- Existing verified behavior is a contract.
- Financial posting uses `post_transaction()` and atomic transaction boundaries.
- Retryable/financial/external side effects require stable idempotency identity and DB-backed duplicate prevention.
- Fresh empty DB uses `bootstrap_fresh_db.py`; existing versioned DB uses `alembic upgrade head`; unknown nonempty unversioned DB must be refused.
- Do not require Alembic downgrade paths when unsafe; use forward recovery + tested backups.
- The assistant updates continuity files; Yasir never has to manage AI memory.

## Next phase after 3.4.S is green
**3.4.3 — identity boundary + immutable audit + jobs foundation.**

Do not skip ahead to billing, fraud, expansion products, or broad page retrofits unless the dependency plan is explicitly changed.

## Rule for future assistants
Do not replace, redesign, or rebuild anything marked VERIFIED unless:
1. a regression test fails;
2. the current milestone requires a compatible refactor; or
3. Yasir explicitly requests the change.

When changing verified behavior, add/update regression coverage first or in the same batch.
