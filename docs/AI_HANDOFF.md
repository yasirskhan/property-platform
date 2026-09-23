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
- Alembic head: `a6e4c8f2b1d0`
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
**3.4.3 Identity boundary + immutable audit — COMPLETE.**

Next: **3.4.4 Release-gate storage/resolver + jobs runtime foundation.**

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
- staging Compose rendering + backend/frontend image builds + live stack startup with backend /health and frontend /login (CI run 35916148970).

## Defects found and fixed by the safety work
- `check_parity.py` and `generate_file_catalog.py` had hard-coded Windows project paths; made portable.
- `requirements.txt` was UTF-16 and omitted runtime imports; normalized/pinned.
- fresh DB migration history could not create the pre-Alembic schema; guarded fresh bootstrap + legacy upgrade fixture now cover both paths.
- `init_db.py` omitted newer models; model-registry test now guards all 50 tables.
- GL reversal used two financial commits; reversal + original state now commit atomically with failure regression coverage.
- E2E seed used reserved `.test` domain rejected by Pydantic; fixed.
- Playwright used unreliable `networkidle`; now waits for DOM/UI readiness.

## Safety foundation closeout
Phase 3.4.S is COMPLETE.
- Staging live-start smoke: VERIFIED in CI run 35916148970.
- Portable security gate: Bandit + pip-audit + npm audit + committed-secret scan + Dependabot, VERIFIED in CI run 35917804417.
- CodeQL workflow is retained as optional/manual because private-repo SARIF upload requires GitHub Code Security.

## 3.4.3 evidence
- Separate `platform_users` identity domain, guarded first-admin seed, and strict customer/platform JWT audience separation: VERIFIED in CI run 35922527217.
- Immutable `audit_log`: ORM mutation guards, PostgreSQL direct-SQL trigger protection, canonical append-only service, and migration/bootstrap coverage: VERIFIED in CI run 35924373985.

## Current parity state
- 146 built
- 0 in progress
- 482 scheduled
- 628 total
- 0 unplanned / 0 phase-less expected

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

## Next phase
**3.4.4 — release-gate storage/resolver + jobs runtime foundation.**

The parity checklist places Redis/Arq queue, scheduler, retry/dead-letter patterns, and Redis standup in 3.4.4. Do not pull billing, fraud, expansion products, or broad page retrofits ahead of that dependency order.

## Rule for future assistants
Do not replace, redesign, or rebuild anything marked VERIFIED unless:
1. a regression test fails;
2. the current milestone requires a compatible refactor; or
3. Yasir explicitly requests the change.

When changing verified behavior, add/update regression coverage first or in the same batch.
