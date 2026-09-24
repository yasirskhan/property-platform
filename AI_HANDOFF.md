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

Current batch:
- Phase 3.4.9 fraud/abuse foundation is IMPLEMENTED; hosted CI verification is pending.
- Durable fraud_cases + fraud_signals review storage.
- Signed Stripe Radar early-fraud-warning/review events and fraud-related disputes enter an idempotent review queue without card data.
- Internal checkout-attempt velocity signals escalate HIGH -> CRITICAL.
- New checkout is blocked only while an unresolved CRITICAL fraud case exists.
- Platform-only fraud queue list/detail/review APIs with immutable audit of review decisions.
- Existing Arq/Redis runtime schedules one durable fraud-refresh job each UTC hour.
- New Alembic head: 6f1a9c4d2e7b.
- Expected model table count: 75.
- Regression coverage added for Stripe signal idempotency/linking, non-fraud dispute filtering, velocity escalation, critical checkout blocking, and platform review authorization.

Next action:
1. Verify this 3.4.9 implementation in hosted CI.
2. Fix CI failures autonomously.
3. When green, update PROJECT_MASTER/parity state and this handoff with exact verification evidence.
4. Continue directly into the next revised foundation phase: separate internal admin app for organizations, release gates, plans, fraud, and audit. Do not stop at the phase boundary.

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
