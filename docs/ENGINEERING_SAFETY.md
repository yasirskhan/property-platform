# ENGINEERING SAFETY

**Phase:** 3.4.S  
**Status:** Final hosted closeout  
**Last updated:** 2026-09-23

This file defines what "done" means for later AI-assisted batches.

## Verification layers
Use every applicable layer:
1. parity/registry planning consistency;
2. backend unit/service/API behavior;
3. database migration/bootstrap behavior;
4. PostgreSQL integration behavior;
5. frontend lint + TypeScript + production build;
6. critical Playwright workflow smoke;
7. accounting invariants for money-moving changes;
8. security/dependency/static scanning.

A skipped applicable check does not count as verified.

## Database paths
- Existing versioned database: `alembic upgrade head`.
- Brand-new empty database: `python bootstrap_fresh_db.py`.
- Nonempty unversioned database: refuse automatic preparation and require deliberate legacy handling.
- `backend/tests/fixtures/pre_alembic_1d77_schema.sql` is schema-only and proves the historical upgrade chain through current head.

## Accounting invariants
- total debit equals total credit;
- validation failure leaves no partial financial state;
- referenced accounts/property/unit belong to the correct org;
- reversals create opposite entries and net to zero;
- posted history is never silently edited/deleted;
- protected-period enforcement gets explicit tests when implemented;
- retries must not duplicate financial effects.

## Idempotency standard
Retryable, redelivered, scheduled, money-moving, or external-side-effect operations need:
- stable business idempotency identity;
- database uniqueness/atomic guard;
- safe retry behavior after timeout/crash;
- documented ordering between external effects and internal persistence;
- duplicate-execution regression tests.

Applies to Stripe/webhooks, recurring charges/receipts, late fees, management fees, statements, payment exports, imports, and background jobs.

## Definition of Done
Documentation change: canonical docs agree and parity/registry checks pass where applicable.

Backend change: relevant tests added/updated and regression suite passes.

Schema change: hand-written Alembic migration, relevant upgrade proof, fresh-schema compatibility, and recovery plan for destructive changes.

Frontend change: lint + TypeScript + production build; critical changed workflow gets browser smoke where appropriate.

Accounting/payment change: all applicable checks plus balance, org boundary, failure atomicity, reversal/void, and duplicate/idempotency coverage.

**VERIFIED is stronger than built.** A feature is VERIFIED only when its applicable automated evidence passes.

## Current hosted evidence
GitHub CI has passed PostgreSQL backend tests, frontend lint/type/build, fresh DB bootstrap, deterministic seed, PostgreSQL dump/restore, authenticated Playwright smoke, staging image/config checks, and live Compose staging startup/health smoke. CI run 35916148970 verified the running backend `/health` and frontend `/login` endpoints.

CodeQL extraction/analysis runs for Python and TypeScript, but GitHub currently rejects SARIF/status upload because code scanning is disabled for this private repository. That repository setting must be enabled before the final hosted security gate can be marked verified.

## Security timing
Dependency scanning/static analysis start now. DAST grows with staging. Formal penetration testing remains a pre-launch gate.

## One-command local verification
From project root on Windows: `verify.bat` or `python verify_project.py`. Hosted GitHub CI remains the authoritative PostgreSQL/Python 3.12/browser environment.
