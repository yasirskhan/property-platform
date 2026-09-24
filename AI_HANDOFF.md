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
- Phase 3.4.14 Bills compatibility retrofit.
- Phase 3.4.15 Bank Deposits compatibility retrofit.
- Phase 3.4.16 GL Accounts compatibility retrofit.
- Phase 3.4.17 Journal Entries compatibility retrofit is COMPLETE and VERIFIED.
- Phase 3.4.17 implementation commit: 57754c2c684d64ba8355e6634cc4c860fe0a6cd6.
- GitHub CI run 35998021267: SUCCESS.
- Backend/PostgreSQL: 193 passed, 3 deselected, 1266 warnings in 40.66s.
- E2E: 3 passed in 8.44s.
- Customer frontend, platform-admin, security, parity/registry, backup/restore, and staging smoke: SUCCESS.
- Alembic head remains 8c4e2a7d1f90.

Current batch:
- Phase 3.4.18 Management Fees compatibility retrofit implementation is prepared in the current checkpoint and awaiting hosted CI verification.
- Existing fee calculation and two-step accounting spine remain unchanged: running a fee creates an unpaid Bill and posts DR Management Fee Expense / CR Accounts Payable; Bill payment remains the second step.
- List/new surfaces consume display context and list/detail periods use shared date formatting.
- Pay Owners, Overcollection Strategy, Management Fee Exclusions, and Post GPR are release-gated compatibility slots and remain invisible while HIDDEN.
- Backend routes enforce ACCOUNTING.MANAGEMENT_FEES permission; preview/run/reverse additionally enforce ADMIN/OWNER/MANAGER write roles, matching the customer UI.
- Regression coverage includes permission/write-role tests and authenticated E2E proof that unreleased capability buttons stay hidden.
- No migration is required; Alembic head remains 8c4e2a7d1f90.

Next action:
1. Verify the current Phase 3.4.18 checkpoint through hosted CI.
2. Fix any CI red autonomously.
3. When green, mark compliance.management_fees.full_surface built, record exact verification results, and continue directly into Owner Statements compatibility work without waiting for the user.

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
