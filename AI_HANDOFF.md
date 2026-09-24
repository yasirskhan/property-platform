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

Verified foundation through this checkpoint:
- Phase 3.4.S engineering safety foundation.
- Phase 3.4.3 identity boundary + immutable audit.
- Phase 3.4.4 Hybrid Capability Gating + jobs runtime + Sentry foundation.
- Phase 3.4.5 locked accounting periods + core organization settings + GDPR schema foundation.
- Phase 3.4.6 end-to-end verification.
- Phase 3.4.7 billing foundation.
- Phase 3.4.8 self-serve signup/payment.
- Phase 3.4.9 fraud/abuse foundation.
- Phase 3.4.10 separate internal admin app.
- Phase 3.4.11 customer release-gate consumption + Settings → Features.
- Phase 3.4.12 unit/plan-limit enforcement.
- Phase 3.4.13 Receipts compatibility retrofit.
- Phase 3.4.14 Bills compatibility retrofit is COMPLETE and VERIFIED.
- Phase 3.4.14 implementation commit: a7da11d20b7a88e00df4055fb486e22aa12ce727.
- GitHub CI run 35992544919: SUCCESS.
- Backend/PostgreSQL: 176 passed, 3 deselected, 1266 warnings in 35.15s.
- E2E: 3 passed in 12.01s.
- Customer frontend, platform-admin, security, parity/registry, backup/restore, and staging smoke: SUCCESS.
- Alembic head remains 8c4e2a7d1f90.

Current batch:
- Phase 3.4.15 Bank Deposits compatibility retrofit implementation is prepared in the current checkpoint and awaiting hosted CI verification.
- Existing deposit accounting contract remains unchanged: deposits group already-posted receipts and do not create new GL postings.
- Deposit list/new surfaces consume display context and shared date/money formatting.
- New Deposit warns when selected receipt dates differ from the deposit date.
- Planned print/edit/NSF/escrow-refund actions are release-gated compatibility slots and remain invisible while HIDDEN.
- Bank-specific deposit numbering is represented by a non-visual structural compatibility seam; the verified current global numbering behavior is unchanged.
- Deposit backend routes enforce ACCOUNTING.DEPOSITS permission in addition to organization scoping.
- Regression coverage includes permission-guard tests and authenticated E2E page proof.

Next action:
1. Verify the current Phase 3.4.15 checkpoint through hosted CI.
2. Fix any CI red autonomously.
3. When green, mark compliance.deposits.full_surface built, record exact verification results, and continue directly into the next compatibility retrofit from FEATURE_REGISTRY / parity order without waiting for the user.

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
