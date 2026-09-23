# ENGINEERING SAFETY

**Phase:** 3.4.S  
**Status:** Active foundation  
**Last updated:** 2026-09-23

This file is the executable-quality companion to `PROJECT_MASTER.md` Section 84.
It defines what "done" means and which checks protect later AI-assisted batches.

## 1. Verification layers

A change is not VERIFIED merely because code exists or `check_parity.py` is CLEAN.
Use every layer that applies:

1. **Planning consistency** — parity JSON + Feature Registry remain structurally CLEAN.
2. **Backend behavior** — unit/service/API tests pass.
3. **Database behavior** — migration/bootstrap verification passes.
4. **PostgreSQL behavior** — CI integration run passes against PostgreSQL.
5. **Frontend behavior** — lint + TypeScript + production build pass.
6. **Critical workflow behavior** — Playwright smoke/E2E where applicable.
7. **Accounting behavior** — financial invariants pass for every money-moving change.
8. **Security behavior** — dependency/static scanning passes; deeper staging/pen-test gates apply before launch.

A non-applicable check passes by definition. A skipped applicable check does not.

## 2. Database paths

### Existing database

Existing installations MUST use:

    alembic upgrade head

Never run the fresh bootstrap against an existing database.

### Brand-new empty database

The historical Alembic chain began after the application already had tables, so revision
`660bc48a3454` is intentionally a historical checkpoint rather than a complete empty-DB
schema creator.

A fresh database therefore uses:

    python bootstrap_fresh_db.py

The bootstrap refuses to run if application tables already exist. It creates the current
SQLAlchemy model schema, verifies the created table set, then stamps the current Alembic
head. All future migrations apply normally after that point.

### Legacy migration regression fixture

`backend/tests/fixtures/pre_alembic_1d77_schema.sql` is schema-only. It was derived from
the historical 2026-09-19 database backup and contains no application rows or user data.
CI/tests use it to prove the real legacy upgrade chain still reaches current head.

## 3. Accounting invariants

For all current and future money-moving code:

- total debit must equal total credit;
- no transaction may persist partially after validation failure;
- every referenced GL account/property/unit must belong to the correct organization;
- reversals create a new opposite transaction and net the original effect to zero;
- posted GL history is never silently edited/deleted;
- once locked-period enforcement ships, unauthorized posting into a locked period must fail;
- retries or duplicate events must never create duplicate financial effects.

Tests are required when a change touches any of these rules.

## 4. Idempotency standard

Any operation that can be retried, redelivered, scheduled, or invoked more than once must
have a stable business idempotency identity.

Applies to, at minimum:

- Stripe/payment webhooks;
- recurring charges and receipts;
- late-fee runs;
- management-fee runs;
- owner-statement generation;
- ACH/check/payment exports;
- imports;
- scheduled/background jobs;
- any API endpoint whose duplicate execution would move money or create an external side effect.

Rules:

1. The idempotency key is based on the business event, not a random retry request.
2. The database owns duplicate prevention through a unique constraint or equivalent atomic guard.
3. "Check then insert" without a database uniqueness/locking guarantee is not sufficient.
4. A retry after timeout must return/reuse the first successful result where practical.
5. External side effects and internal posting must have a documented retry order.
6. Jobs must be safe to run again after worker crash/restart.
7. Every implementation gets a duplicate-execution regression test.

This section defines the standard. Individual workflows gain enforcement as they are built
or touched.

## 5. Definition of Done

### Documentation-only change

- source documents agree;
- `check_parity.py` passes when parity/registry content changed;
- no code behavior is claimed VERIFIED.

### Backend change

- relevant unit/integration tests added or updated;
- existing backend regression tests pass;
- parity/registry updated when product surface/status changed.

### Schema change

All backend requirements plus:

- hand-written Alembic migration;
- upgrade path tested from the relevant prior state;
- fresh bootstrap/current model compatibility checked;
- backup/forward-recovery plan for destructive changes.

### Frontend change

- lint passes;
- TypeScript no-emit passes;
- production build passes;
- critical changed workflow gets browser smoke/E2E coverage when Playwright applies.

### Accounting/payment change

All applicable checks above plus:

- debit/credit invariant coverage;
- org-boundary coverage;
- failure atomicity coverage;
- reversal/void behavior where applicable;
- duplicate/idempotency coverage where retries can occur.

### VERIFIED status

A capability may be called VERIFIED only after the checks applicable to that capability
pass. "Built" in the parity inventory means implemented product scope; VERIFIED is a
stronger engineering claim and belongs in the living ledger/handoff with evidence.

## 6. One-command local verification

From the project root on Windows:

    verify.bat

or:

    python verify_project.py

The verifier runs the project checks it can run locally and stops on failure. CI remains
the authoritative Python 3.12 + PostgreSQL environment.

## 7. Current known verification environment

- Target backend runtime: Python 3.12.
- CI database: PostgreSQL.
- SQLite remains useful for fast local unit tests and legacy-upgrade regression.
- Production/staging database target: PostgreSQL.
- `check_parity.py` is a consistency check, never a behavioral test.
## 8. Browser smoke / E2E foundation

`backend/tests/e2e/test_smoke.py` is a real-browser Playwright smoke test. It uses a disposable seeded account and verifies:

- login through the real FastAPI auth endpoint;
- authenticated Dashboard load;
- Properties list load;
- Receipts list load;
- Bills list load;
- protected pages do not fall back to `/login`.

`backend/seed_e2e.py` refuses to run unless `E2E_SEED_ALLOWED=true`. CI runs the smoke test against PostgreSQL 16 with real FastAPI and Next.js processes. The browser test is IN PROGRESS until a dependency-complete CI run succeeds.

## 9. Staging path and deploy safety

The basic staging path lives under `deploy/staging/` and is documented in `docs/STAGING_RUNBOOK.md`. It uses PostgreSQL 16, FastAPI and Next.js containers.

`backend/prepare_database.py` is the only automatic database-preparation path for staging:

- empty database -> guarded current-schema bootstrap + Alembic stamp;
- existing versioned database -> `alembic upgrade head`;
- nonempty database without `alembic_version` -> refuse and require manual/legacy migration handling.

Staging/production startup is fail-closed for the development JWT/encryption defaults. `ENVIRONMENT=staging|production` requires distinct strong secrets.

CI renders the staging Compose file and builds both staging images. Actual staging bring-up remains IN PROGRESS until those hosted checks and a real staging run succeed.

## 10. PostgreSQL backup/restore drill

The E2E CI job performs a `pg_dump` of the seeded PostgreSQL database, restores it into a separate database, then verifies the expected application table count and seeded user. This complements the locally passing SQLite restore proof. PostgreSQL restore remains IN PROGRESS until the hosted CI drill succeeds.
