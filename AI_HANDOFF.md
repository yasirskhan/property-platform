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

Current batch:
- Phase 3.4.10 separate internal admin app is NEXT and not yet implemented.

Next action:
1. Re-read this file and inspect the current platform auth, org, release-gate, plan, fraud, and audit sources.
2. Add platform-audience-only backend read/provisioning APIs required by the internal app, with role authorization and immutable audit for changes.
3. Build a separate Next.js internal application for organizations, release gates, plans, fraud, and audit; do not mix it into the customer frontend.
4. Add the internal app to CI lint/TypeScript/build gates.
5. Verify CI, fix reds autonomously, update handoff/roadmap, and continue directly into Phase 3.4.11 customer release-gate consumption + Settings Features.

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
