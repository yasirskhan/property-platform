# STAGING RUNBOOK

**Purpose:** Repeatable production-like verification before public deployment.  
**Database:** PostgreSQL 16.  
**Rule:** Staging is disposable; production is not.

## 1. First setup

1. Copy `deploy/staging/.env.example` to `deploy/staging/.env`.
2. Replace every placeholder secret. Never commit `.env`.
3. From `deploy/staging/`, run:

       docker compose --env-file .env up -d --build

The backend runs `prepare_database.py` before FastAPI starts:

- empty database -> current schema is bootstrapped and Alembic head stamped;
- versioned existing database -> `alembic upgrade head`;
- nonempty unversioned database -> deployment stops instead of guessing.

## 2. Required staging checks

Before a release candidate can move toward production:

- `GET /health` returns 200;
- frontend `/login` loads;
- authenticated Playwright smoke passes;
- PostgreSQL integration suite passes;
- parity/registry is CLEAN;
- frontend lint, TypeScript and production build pass;
- backup + restore drill passes for the release candidate;
- no pending destructive migration lacks a forward-recovery plan.

## 3. Deploying a new candidate

1. Verify the current Git commit is a known-good checkpoint.
2. Create a database backup before any schema-changing deployment.
3. Build/start the candidate:

       docker compose --env-file .env up -d --build

4. Inspect service state:

       docker compose ps

5. Run the smoke suite against staging.
6. Only then mark the candidate staging-verified.

## 4. Rollback / recovery policy

Application rollback and database rollback are separate decisions.

### Application failure with compatible schema

Redeploy the previous known-good Git commit/image. Do not reverse the database merely
because application code is rolled back if the schema remains backward-compatible.

### Migration failure or incompatible schema

Do not improvise a downgrade. Stop writes, preserve logs, and use the release's documented
forward-recovery migration or restore the pre-deploy backup into a controlled recovery
instance. Destructive migrations require an explicit backup/recovery plan before deployment.

## 5. Data safety

- Never seed staging with real tenant/customer data unless it has been intentionally sanitized.
- E2E seed scripts require `E2E_SEED_ALLOWED=true` and are for disposable test databases only.
- Production credentials must never be copied into staging.
- Staging Stripe/email integrations remain disabled or sandboxed until explicitly tested.

## 6. What this does not replace

This is the basic staging path for Phase 3.4.S. Phase 11 still owns production AWS design,
TLS/DNS, WAF, production backup schedules, observability at scale, deployment automation,
and formal disaster-recovery drills.