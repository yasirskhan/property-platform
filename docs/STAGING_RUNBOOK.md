# STAGING RUNBOOK

**Purpose:** Repeatable production-like verification before public deployment.  
**Database:** PostgreSQL 16.  
**Rule:** Staging is disposable; production is not.

## First setup
Copy `deploy/staging/.env.example` to `deploy/staging/.env`, replace every placeholder secret, never commit the resulting `.env`, then run:

    docker compose --env-file .env up -d --build

The backend runs `prepare_database.py` before FastAPI:
- empty DB -> guarded current-schema bootstrap + Alembic head stamp;
- versioned DB -> `alembic upgrade head`;
- nonempty unversioned DB -> deployment refuses to guess.

## Required release-candidate checks
- backend `GET /health` returns 200;
- frontend `/login` loads;
- authenticated Playwright smoke passes;
- PostgreSQL integration suite passes;
- parity/registry is CLEAN;
- frontend lint, TypeScript, and production build pass;
- backup + restore drill passes;
- destructive migrations have an explicit forward-recovery/restore plan.

CI starts the same Compose topology with CI-only secrets and proves backend/frontend reachability.

## Rollback / recovery
Application rollback and database recovery are separate decisions.

If schema remains compatible, redeploy the previous known-good application commit/image.

For migration failure or incompatible schema, stop writes, preserve logs, and use the release's documented forward-recovery migration or restore the pre-deploy backup into a controlled recovery instance. Do not improvise unsafe downgrades.

## Data safety
Never seed staging with real customer/tenant data unless intentionally sanitized. E2E seeding requires `E2E_SEED_ALLOWED=true` and is disposable-test-only. Production credentials never belong in staging. Stripe/email remain disabled or sandboxed until explicitly tested.

Phase 11 still owns final AWS/TLS/DNS/WAF/production observability, production backup schedules, deployment automation, and formal disaster-recovery drills.
