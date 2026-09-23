# JOBS RUNTIME

**Phase:** 3.4.4  
**Runtime:** Arq + Redis + durable PostgreSQL job state

## Core rule

Redis is the dispatch mechanism. PostgreSQL is the durable source of truth for job identity, status, retries, and dead letters.

For any retryable, scheduled, financial, or external-side-effect job:

1. Build a stable business `idempotency_key`.
2. Reserve and commit the `job_runs` row first.
3. Enqueue the durable row ID to Arq with deterministic job ID `property-platform:job-run:{id}`.
4. Mark the row QUEUED only after Redis confirms enqueue.
5. Execute through the registered handler.
6. Record every attempt and terminal result in PostgreSQL.

The unique constraint on `(job_name, idempotency_key)` is the authoritative duplicate guard. Redis job IDs are an additional queue-level guard, not a replacement.

## Status lifecycle

`PENDING -> QUEUED -> RUNNING -> SUCCEEDED`

Transient failures use:

`RUNNING -> RETRYING -> QUEUED -> RUNNING`

Exhausted retries use:

`RUNNING -> DEAD_LETTER`

Dead-letter details are copied into `job_dead_letters` and remain queryable by the internal platform monitoring API.

## Retry behavior

The current retry delay is exponential:

- attempt 1: 5 seconds
- attempt 2: 10 seconds
- attempt 3: 20 seconds
- continues doubling
- capped at 300 seconds

Each `JobRun` has its own `max_attempts`. Business-specific jobs may choose a lower or higher limit deliberately.

## Scheduler / recovery

Arq cron runs `recover_pending_jobs` every minute.

The sweep recovers:

- PENDING rows whose scheduled time is due;
- RETRYING rows whose `next_retry_at` is due;
- durable DB-first jobs where Redis dispatch was interrupted after the database commit.

Deterministic Arq job IDs make repeated recovery sweeps safe.

## Handler registration

Use `app.jobs.registry.register_job_handler("stable.job.name")`.

Handlers receive the stored JSON payload and must be safe under the project's idempotency standard. Money-moving/external-side-effect handlers must use their own business uniqueness/atomicity rules in addition to the generic job-run guard.

## Monitoring

Platform-only endpoints:

- `GET /api/platform/jobs`
- `GET /api/platform/jobs?status=DEAD_LETTER`
- `GET /api/platform/jobs/dead-letters`
- `GET /api/platform/jobs/summary`

Admin, Dev, Tech, and Support platform roles may inspect job state. Customer identities cannot use the platform JWT audience.

## Redis environments

Configuration is provider-neutral through `REDIS_URL`.

- Local development: local Redis is allowed while `JOBS_ENABLED=false` by default.
- Staging/CI: Docker Redis with persistence and health check.
- Managed development environments: use an Upstash Redis URL.
- Production: use the deployment's managed Redis endpoint, planned as ElastiCache.

When `JOBS_ENABLED=true` in staging/production, localhost Redis URLs are rejected by configuration validation.

## Worker

Run:

`arq app.jobs.worker.WorkerSettings`

The worker uses the same database, Redis URL, queue name, and optional Sentry configuration as the backend.

## Observability

Worker handler exceptions are sent to Sentry when `SENTRY_DSN` is configured. Job lifecycle state remains durable in PostgreSQL even when Sentry is disabled or unavailable.

## Safety requirements for new jobs

Before a new business job is considered complete:

- stable business idempotency identity;
- DB-backed uniqueness or atomic guard;
- retry-safe business logic;
- explicit max attempts;
- tested failure behavior;
- dead-letter visibility;
- no duplicate financial/external side effect after timeout or redelivery.
