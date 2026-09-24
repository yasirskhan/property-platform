─────────────────────────────────────────────────────────
AI_HANDOFF.md LOCATION RULE (READ FIRST)
─────────────────────────────────────────────────────────
This file lives at the REPO ROOT.

Not in docs/.
Not in backend/.
Not in frontend/.

Every future ChatGPT session that works on this repo MUST keep
this file at the repo root and MUST overwrite it (not append)
after every BATCH DONE.

Why: this file is the single resume point between sessions.
If it moves, the next session will not find it.

The source-of-truth planning files live under docs/. Update them
when roadmap/capability state actually changes and keep registry /
parity consistency checks green.
─────────────────────────────────────────────────────────

# Current Resume State

Branch: chatgpt/checkpoint-005-safety
Current HEAD hash: resolve from this branch; this file is committed as part of HEAD, so it does not embed its own hash.

Completed and verified before this batch:
- Phase 3.4.S engineering safety foundation.
- Phase 3.4.3 identity boundary + immutable audit.
- Phase 3.4.4 Hybrid Capability Gating runtime + durable Arq/Redis jobs + Sentry foundation.
- Phase 3.4.5 locked accounting periods + core organization settings + GDPR schema foundation.
- Phase 3.4.6 end-to-end verification of the existing core product.
- Phase 3.4.7 basic billing foundation.
- Phase 3.4.8 self-serve signup/payment flow.
- Phase 3.4.8 implementation commit: 939358c5a517b67a5978dbb2f2832b6c5f26196f.
- Phase 3.4.8 closeout commit: 7e43a316d8a572f1b912383e335fd6ea30498b5d.
- GitHub CI run 35957428019: SUCCESS.
- Backend: 149 passed, 2 deselected, 1042 warnings in 31.05s.
- E2E: 2 passed in 6.61s.
- Frontend, security, staging: SUCCESS.
- Alembic head before 3.4.9: 2d4f8a6c9b10.

Last completed batch:
- Phase 3.4.9 fraud/abuse foundation is COMPLETE and VERIFIED.
- Implementation commit: 27fdf78524ddb4665bf3cc416b59c8289e4e8d51.
- GitHub CI run 35960071377: SUCCESS.
- Backend/PostgreSQL: 154 passed, 2 deselected, 1096 warnings in 35.89s.
- E2E: 2 passed in 6.63s.
- Frontend lint/TypeScript/build, security, backup/restore, and live staging smoke: SUCCESS.
- Durable fraud_cases + fraud_signals review storage is active.
- Stripe Radar early-fraud-warning/review events and fraud-related disputes feed the idempotent review queue without raw card data.
- Checkout velocity escalates HIGH -> CRITICAL; unresolved CRITICAL cases block new Checkout requests.
- Platform-only fraud review APIs audit decisions.
- Existing Arq/Redis runtime schedules hourly fraud-refresh jobs.
- Alembic head: 6f1a9c4d2e7b.
- Model table count: 75.
- Parity closeout updates 3.4.7/3.4.8 billing items to their verified state and shifts the remaining foundation numbering to match the actual revised sequence.

Phase 3.4.9 closeout checkpoint:
- Closeout commit: e33f421f3c8944e475f30369ed9cf3b7c247fce7.
- GitHub CI run 35960596442: SUCCESS.
- Backend/PostgreSQL: 154 passed, 2 deselected, 1096 warnings in 20.62s.
- E2E: 2 passed in 6.42s.
- Frontend, security, parity/registry, backup/restore, and live staging smoke: SUCCESS.

Current batch:
- Phase 3.4.10 Batch 1 platform-control APIs are VERIFIED.
- Batch 1 commit: 764f6816b8334490c93d095a47a721b8ccbf380d.
- GitHub CI run 35961065567: SUCCESS.
- Phase 3.4.10 Batch 2 separate internal Next.js admin application is VERIFIED.
- Batch 2 commit: 02ddfa7a622d9b155ca1c71899316c6b163755a2.
- GitHub CI run 35980762441: SUCCESS.
- Backend/PostgreSQL: 160 passed, 2 deselected, 1132 warnings in 40.37s.
- Platform-admin lint/TypeScript/build and npm-audit: SUCCESS.
- Customer frontend, security, existing E2E, backup/restore, and staging: SUCCESS.
- Phase 3.4.10 Batch 3 deterministic platform-admin browser proof is VERIFIED.
- Rename/fix commit: e195a2b98e0a1d5686580f89842ccd56726b0f0c.
- GitHub CI run 35981504331: SUCCESS.
- Backend/PostgreSQL: 160 passed, 3 deselected, 1132 warnings in 39.14s.
- E2E: 3 passed in 9.49s.
- Customer frontend, platform-admin frontend, security, backup/restore, and staging smoke: SUCCESS.
- Phase 3.4.10 is COMPLETE and VERIFIED.
- The internal app lives in platform-admin/, uses only platform-audience authentication/API routes, stores a separate platform_access_token, and does not reuse customer frontend auth state.
- Internal surfaces cover organizations, plan catalog, release gates, fraud review, and platform staff audit with backend role authorization remaining authoritative.
- Backend CORS permits the local internal app on port 3001.
- CI now has a dedicated platform-admin lint/TypeScript/production-build job and npm-audit gate.
- No migration in Batch 2; Alembic head remains 6f1a9c4d2e7b.

Current batch:
- Phase 3.4.11 customer release-gate consumption + Settings → Features is COMPLETE and VERIFIED.
- Capability API/storage commit: d32682c153b6ebbe83c262dc755e4104b0774710.
- Customer UI commit: bb43ad66e4aeb8608a0ec42e82f8c8a1b6e4bbf1.
- Toggle UX/E2E fix commit: d49368a07e6df74e78ed6d03f71e8afc3b3029aa.
- GitHub CI run 35985275368: SUCCESS.
- Backend/PostgreSQL: 165 passed, 3 deselected, 1187 warnings in 43.02s.
- E2E: 3 passed in 9.05s.
- Customer frontend, platform-admin, security, backup/restore, and staging smoke: SUCCESS.
- Alembic head: 3b8d1f5c7a20; model table count: 76.
- Customer runtime now exposes released capability decisions without leaking hidden stages and keeps release, entitlement, org configuration, authorization, and personal presentation concerns independent.
- Settings → Features, FeatureProvider, useFlag(), and <Flag> are verified.

Current batch:
- Phase 3.4.12 unit/plan-limit enforcement implementation is committed in the current checkpoint and awaiting hosted CI verification.
- Subscription rows now persist the purchased pricing tier; migration 8c4e2a7d1f90 backfills from completed checkout history when available.
- Active-unit capacity is enforced authoritatively on unit create and soft-delete restore. Legacy/enterprise subscriptions without a pricing tier remain uncapped.
- Add Unit shows an explanatory plan-options prompt when the backend returns the unit-limit conflict.
- Regression coverage covers limit resolution, create/restore blocking, Stripe tier reconciliation, and migration-head guards.

Next action:
1. Verify the current Phase 3.4.12 checkpoint through hosted CI.
2. Fix any CI red autonomously.
3. When green, record the verified 3.4.12 closeout and continue directly into 3.4.13 Receipts compatibility retrofit.

Open blockers:
- NONE

Rules:
- Work only on branch chatgpt/checkpoint-005-safety. Never touch main or create/switch branches.
- Read this file completely before every batch.
- Inspect real source before changing it.
- Existing VERIFIED behavior is a contract.
- Backend authorization is authoritative; UI hiding is never security.
- Keep release control, plan entitlement, org configuration, role permission, and user preference independent.
- Fix CI reds autonomously.
- Keep AI_HANDOFF.md current after every meaningful batch.
- Keep one coherent batch per commit and safe checkpoints.
