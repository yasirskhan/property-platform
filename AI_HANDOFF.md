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
- Phase 3.4.18 Management Fees compatibility retrofit is COMPLETE and VERIFIED.
- Phase 3.4.18 repair/final implementation commit: 1ee39901d7ffd42f01c26db158ce692993f1deb1.
- GitHub CI run 36036233118: SUCCESS.
- Backend/PostgreSQL: 203 passed, 3 deselected, 1266 warnings in 39.57s.
- E2E: 3 passed in 11.89s.
- Customer frontend, platform-admin, security, parity/registry, backup/restore, and staging smoke: SUCCESS.
- Alembic head remains 8c4e2a7d1f90.

Current batch:
- Phase 3.4.19 Owner Statements compatibility retrofit implementation is prepared in this checkpoint and awaits hosted CI verification.
- Frozen statement snapshots and existing per-property transaction math remain unchanged.
- List/new/detail surfaces consume display context; statement periods and transaction dates use shared date formatting.
- Backend routes enforce ACCOUNTING.OWNER_STATEMENTS permission; preview/generate additionally enforce ADMIN/OWNER/MANAGER write roles.
- Required Reserves and Prepaid Rent are represented as structural compatibility slots with no fabricated balances because no verified accounting source/configuration exists yet.
- Property Cash Summary, Owner Packet, and Email Statement are release-gated compatibility slots and remain invisible while HIDDEN.
- Authenticated E2E coverage proves unreleased owner-reporting actions stay hidden.
- First hosted CI run 36042783934 stopped at parity consistency because parity metadata still declared 199 built / 428 scheduled after the status transition. The repair checkpoint updates metadata to the computed 200 built / 1 in progress / 427 scheduled counts; product code is unchanged from the implementation checkpoint.
- No migration is required; Alembic head remains 8c4e2a7d1f90.

Next action:
1. Verify the current Phase 3.4.19 checkpoint through hosted CI.
2. Fix any CI red autonomously.
3. When green, mark compliance.owner_statements.full_surface built, record exact verification results, and continue directly into Bank Accounts compatibility work without waiting for the user.

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
