# Repository development instructions

## Scope
- Repository: `yasirskhan/property-platform`.
- ONLY authorized branch: `chatgpt/checkpoint-005-safety`.
- Use normal Chat for the owner's development sessions. Do not start Work mode.
- Never modify main, create another branch, force push, or edit `yasirskhan/Zargul-Silver-Marquee`.
- A supervising session may coordinate both projects only under the owner's explicit authorization. A development worker remains restricted to this repository.

## Start and sources
- Read the ENTIRE concise root AI_HANDOFF.md, then the current specifications/registers it lists and relevant source/tests.
- Verify live branch HEAD, the latest branch-filtered GitHub Actions runs and every required job before writes.
- GitHub source and exact test results take precedence over stale handoff claims. Historical "prepared"/"detached" notes do not establish publication or verification.
- Read archived handoffs only for a related missing detail. Preserve archives and all approved requirements.
- Follow docs/SESSION_CONTROL.md for supervision and session recovery.

## Development and safe publication
- Maintain one active writer for this repository. Check current file blobs and branch HEAD; reconcile unexpected changes before retrying.
- Use expected_sha with force=false for branch publication. Preserve every concurrent change; never blind-overwrite or reset.
- Implement coherent backend + actual UI + authorization + durable audit + error/retry behavior and relevant tests.
- Fix failing CI and regression causes before proceeding to another feature. Preparing independent work while CI runs is allowed.
- Do not remove, skip or weaken tests, permissions, tenant/hall isolation, financial safeguards, immutable audit or release gates to obtain green CI.
- Run focused checks when available, then the complete required hosted workflow on the exact new SHA. Failed/skipped/pending jobs are NOT VERIFIED.
- A green run verifies its covered source, not an entire unfinished phase. Reconcile all approved requirements before phase completion.
- Keep production switches OFF until existing acceptance and operator-release requirements are met. Do not fabricate provider delivery, payments, source contracts, credentials or acceptance.

## Continuity and stopping
- Continue successive meaningful approved implementation batches within the active execution limits. A push, green run or documentation update alone is not the stopping condition.
- Keep root AI_HANDOFF.md current and concise; replace stale current state rather than append history. Preserve old text verbatim in an archive.
- Save actual code/drafts and identify their location before ending when possible. Distinguish published source, saved candidates, verified source and unknown unsaved work.
- Update existing roadmap, feature and issue registers honestly. Do not silently drop requirements, label foundations end-to-end complete, or invent local test execution.
- Report a genuine tool/usage/external blocker precisely. Never claim background development without a confirmed persistent mechanism.

## Property-specific acceptance
- Phase 5 scope: docs/PHASE5_ACCEPTANCE_AND_ISSUES.md, docs/PHASE5_MAINTENANCE_QUEUE.md, docs/FEATURE_REGISTRY.md and docs/PLAN_GAPS.md.
- All six jobs are required: backend, frontend, platform-admin, security, e2e, staging-config.
- Preserve database migration/bootstrap parity, organization/property/role scope, real requester identity, tenant-charge protections and immutable evidence.
- Finish every approved Phase 5 requirement before Phase 6. Automatic dispatch, provider delivery and finance release need their existing explicit gates and real verification.
- frontend/AGENTS.md remains applicable for frontend work.
