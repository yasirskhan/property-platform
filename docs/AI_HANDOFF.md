# AI HANDOFF

**Purpose:** Current-project checkpoint for any future ChatGPT session.  
**Maintainer:** The assistant doing the development. Yasir is not responsible for reconstructing prior technical context.  
**Last updated:** 2026-09-23 — Phase 3.4.S Engineering Safety Foundation in progress

## Project

Property Management Platform (AppFolio-equivalent)

## Resume order

Read only what is needed, in this order:

1. `docs/AI_HANDOFF.md` (this file)
2. `docs/PROJECT_MASTER.md` current state + current phase
3. `docs/ENGINEERING_SAFETY.md` for quality/DoD rules
4. `docs/FEATURE_REGISTRY.md` relevant page/capability section
5. `docs/APPFOLIO_PARITY_CHECKLIST.json`
6. `docs/PLAN_GAPS.md`
7. `docs/FILE_CATALOG.md` when locating code
8. Actual source/migrations/tests for the current task

**Repository state is authoritative. Chat history is not.**

## Current phase

**IN PROGRESS: Phase `3.4.S` — Engineering Safety Foundation.**

Foundation Session `3.4.2` is COMPLETE.

## Current inventory

Latest `backend/check_parity.py` result:

    628 total parity items
    135 built
    7 in progress
    486 scheduled
    0 unplanned
    0 phase-less
    Feature Registry: 24 routes / 211 rows / 67 release gates
    CLEAN

`CLEAN` is planning/registry consistency only, never behavioral proof.

## Current migration state

Alembic head: `5949df11e460`

### Fresh database rule

The historical Alembic chain began after the application already had a database schema. Therefore revision `660bc48a3454` is a historical checkpoint, not a complete empty-database creator.

For a **brand-new empty DB**, use:

    backend/bootstrap_fresh_db.py

It refuses nonempty databases, creates the full current SQLAlchemy model schema, verifies the table set, and stamps Alembic head.

For an **existing DB**, use:

    alembic upgrade head

Never bootstrap over an existing database.

### Legacy upgrade evidence

`backend/tests/fixtures/pre_alembic_1d77_schema.sql` is a sanitized schema-only fixture derived from the 2026-09-19 backup. It contains no application rows/user data and represents revision `1d77e94a0fb5`.

The regression test upgrades that schema successfully through current head `5949df11e460`.

## Engineering Safety work completed / locally proven

### Backend verification framework

Created:

- `backend/pytest.ini`
- `backend/tests/conftest.py`
- `backend/tests/test_parity.py`
- `backend/tests/test_gl_posting.py`
- `backend/tests/test_migrations.py`
- `backend/tests/test_model_registry.py`
- `backend/tests/test_backup_restore.py`
- `backend/tests/test_postgres_smoke.py`
- `backend/tests/test_prepare_database.py`
- `backend/tests/test_config_safety.py`
- `backend/tests/e2e/test_smoke.py` (real-browser CI smoke; hosted run pending)
- `backend/tests/test_health.py` (requires dependency-complete environment)

Locally runnable core/safety suite result in this Chat runtime:

    16 passed
    1 skipped (PostgreSQL-only test; no PostgreSQL service in this runtime)

The additional locally proven checks cover safe database preparation and staging/production secret validation.

The full `test_health.py` could not be collected here because this runtime is missing project packages such as `python-jose`; outbound package installation is unavailable. This is an environment limitation, not a claimed application pass. CI installs the pinned requirements before running the complete suite.

### Accounting invariants currently covered

- balanced posting produces equal debit/credit totals;
- unbalanced posting is rejected without persisted GL transaction/entries;
- cross-org GL account reference is rejected;
- reversal links to the original and nets each account to zero;
- reversal posting + the original `is_reversed` state change are atomic; a
  simulated commit failure proves neither half persists.

Locked-period and idempotency tests are added when those enforcement features ship.

### Accounting atomicity fix

`reverse_transaction()` previously committed the reversal GL transaction and then
marked the original reversed in a second commit. A failure between those commits
could leave a reversal durable while the original remained reversible.

It now uses the non-committing internal mode of `post_transaction()` and commits
the reversal + original-state flip as one transaction. Audit logging happens only
after the financial commit. A regression test simulates commit failure and proves
no partial reversal survives.

### Model registry guard

`backend/init_db.py` now imports all 50 model tables, including the six newer Settings/permission/Charge/Currency models that were previously missing.

`test_model_registry.py` scans every declared `__tablename__` and fails if `Base.metadata` does not contain exactly that set.

### Backup/restore

`backend/backup_restore_check.py` verifies SQLite backup and restore using SQLite's backup API, `PRAGMA integrity_check`, schema/table lists, and per-table row counts.

The automated local SQLite test passes. CI now contains a PostgreSQL `pg_dump`/`pg_restore` drill into a separate restore database, with table/user verification. The hosted PostgreSQL restore run is still pending.

### Dependency/config reproducibility

- `backend/requirements.txt` normalized from UTF-16 to UTF-8.
- Missing runtime packages used by existing code are now explicitly pinned (`boto3`, `cryptography`, `requests`, `stripe`).
- `backend/requirements-dev.txt` contains pytest/coverage/httpx/PostgreSQL driver/Playwright dependencies.
- `backend/alembic/env.py` accepts `DATABASE_URL`, enabling CI/staging PostgreSQL.

### CI/security definitions present

Created:

- `.github/workflows/ci.yml` — Python 3.12, PostgreSQL 16, parity, backend tests/coverage, frontend lint/type/build, authenticated Playwright smoke, PostgreSQL restore drill, and staging image/config validation.
- `.github/workflows/codeql.yml`
- `.github/dependabot.yml`

These are **IN PROGRESS, not VERIFIED**, because the uploaded ZIP has no `.git` history/remote and this Chat runtime cannot run GitHub-hosted Actions.

### Frontend verification wiring present

`frontend/package.json` includes:

- `npm run typecheck`
- `npm run check` (lint + typecheck + build)

The CI frontend job runs `npm ci`, lint, typecheck, and production build.

This Chat runtime cannot install the frontend dependency tree because external npm access/cache is incomplete. Do not mark frontend checks VERIFIED until run in a dependency-complete environment.

### Browser/staging safety wiring present

- `backend/seed_e2e.py` seeds only when `E2E_SEED_ALLOWED=true`.
- `backend/tests/e2e/test_smoke.py` performs real login + Dashboard/Properties/Receipts/Bills browser checks.
- `backend/prepare_database.py` safely chooses fresh bootstrap vs versioned upgrade and refuses unknown nonempty schemas.
- `backend/Dockerfile`, `frontend/Dockerfile`, and `deploy/staging/compose.yml` define the basic staging stack.
- `docs/STAGING_RUNBOOK.md` defines deploy, backup, smoke, rollback, and recovery rules.
- Staging/production refuse the repository's development JWT/encryption defaults.

These are built but remain **IN PROGRESS, not VERIFIED**, until dependency-complete CI/staging execution succeeds.

### Definition of Done / idempotency

`docs/ENGINEERING_SAFETY.md` is canonical for:

- verification layers;
- fresh DB vs existing DB migration paths;
- accounting invariants;
- idempotency rules for retryable/financial/external side effects;
- change-type-specific Definition of Done;
- VERIFIED status rules.

`verify_project.py` and `verify.bat` provide Yasir a one-command local quality gate once dependencies are installed.

## Safety parity status

Built:

- backend test framework;
- migration verification framework (fresh guarded bootstrap + legacy upgrade fixture);
- idempotency standard;
- core accounting invariant tests;
- Definition of Done / one-command verifier.

In progress pending hosted/environment evidence:

- CI pipeline;
- PostgreSQL integration environment;
- frontend lint/type/build verification;
- backup/restore (SQLite proven, PostgreSQL staging proof pending);
- dependency/static security scanning first hosted run.

Now in progress pending hosted/environment evidence:

- Playwright smoke/E2E foundation (implemented, hosted browser run pending);
- basic staging path (implemented, actual bring-up/image-build run pending).

## Known warnings / non-blocking tech debt

Current locally runnable tests emit deprecation warnings for:

- Pydantic v2 class-based `Config` usage in several schemas/settings;
- `datetime.utcnow()` usage in SQLAlchemy defaults / GL posting.

These are not current failures but should be cleaned before their upstream removals become blockers.

## Locked architecture decisions

### Correctness before feature count

Implemented is not VERIFIED. Tests determine behavioral confidence.

### Hybrid Capability Gating

Five concerns remain separate:

1. release control;
2. commercial entitlement;
3. organization configuration;
4. authorization/permission;
5. user presentation preference.

A non-applicable layer passes automatically.

Backend authorization/entitlement enforcement is authoritative. Frontend hiding is never security.

### Gate granularity

Gate pages/capabilities only when reasonably independently releasable, disable-able, beta-testable, saleable, or grantable.

Routine fields, columns, filters, labels, sort controls, and ordinary form controls get no independent release gate.

### Refactoring

Do not rewrite working behavior merely for style. Refactoring is allowed when public behavior/API contracts are preserved and regression tests prove compatibility.

### Scope

Core Launch precedes expansion products. Affordable Housing, HOA, Commercial, RUBs, Student, Senior, Short-term rentals, and competitor migrations remain post-launch unless explicitly reprioritized.

## NEXT ACTION

Continue Phase `3.4.S` without overclaiming environment-dependent checks.

Priority order:

1. Run/repair the first dependency-complete GitHub CI cycle.
2. Confirm frontend `npm ci` + lint + TypeScript + production build.
3. Confirm PostgreSQL 16 integration, authenticated Playwright smoke, and PostgreSQL dump/restore jobs.
4. Bring up `deploy/staging/compose.yml` with non-default staging secrets and run the smoke suite.
5. Only after those external gates are green, close 3.4.S and continue to 3.4.3 identity/audit/jobs.

This Chat runtime attempted `npm ci`, but external package resolution stalled and was stopped cleanly; no partial `node_modules` remains. Do not interpret that environment limitation as a frontend failure or pass.

## Uploaded-repository constraints

The supplied ZIP has no `.git` directory/history, so no Git HEAD can be recorded from this working copy.

The original ZIP contained `backend/property_platform.db.bak_20260919_224655`. It was used only to derive the sanitized schema-only migration fixture. New ChatGPT checkpoint ZIPs should exclude all database/backup files to avoid propagating local data.

## Continuity rule

After every meaningful verified batch, update this file before starting another broad batch. Before unusually large changes, create a checkpoint ZIP. Yasir should never have to reconstruct prior technical decisions or completion state from memory.