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

Verified latest batch:
- Phase 3.4.19 Owner Statements compatibility retrofit is COMPLETE and VERIFIED.
- Final repair commit: 2632f10e8d973a15fdcb7ee50f1b13d1ea91cd1f.
- GitHub CI run 36043279261: SUCCESS.
- Backend/PostgreSQL: 213 passed, 3 deselected, 1266 warnings in 28.28s.
- E2E: 3 passed in 11.57s.
- Customer frontend, platform-admin, security, parity/registry, backup/restore, and staging smoke: SUCCESS.
- Frozen statement snapshots and existing per-property transaction math remain unchanged.
- Display/date compatibility, ACCOUNTING.OWNER_STATEMENTS permission enforcement, ADMIN/OWNER/MANAGER write roles, structural reserve/prepaid slots, and hidden release-gated cash-summary/packet/email slots are verified.
- Alembic head remains 8c4e2a7d1f90.

Verified latest batch:
- Phase 3.4.20 Bank Accounts compatibility retrofit is COMPLETE and VERIFIED.
- Final repair commit: aa44bc1a53717188bc37a5adda04abc7505358fe.
- GitHub CI run 36046681933: SUCCESS.
- Backend/PostgreSQL: 223 passed, 3 deselected, 1266 warnings in 42.30s.
- E2E: 3 passed in 10.75s.
- Customer frontend, platform-admin, security, parity/registry, backup/restore, and staging smoke: SUCCESS.
- Existing physical bank-account CRUD and GL-account mapping remain unchanged.
- Shared display compatibility, ACCOUNTING.BANK_ACCOUNTS permission enforcement, ADMIN/OWNER/MANAGER write roles, and hidden release-gated reconciliation/QIF/check/ACH/feed/adjustment slots are verified.
- Alembic head remains 8c4e2a7d1f90.

Verified latest batch:
- Phase 3.4.21 Charges compatibility retrofit is COMPLETE and VERIFIED.
- Implementation commit: 7148b788315be7c6a245884da8d2dec5e0f02913.
- GitHub CI run 36051620935: SUCCESS.
- Backend/PostgreSQL: 233 passed, 3 deselected, 1266 warnings in 36.78s.
- E2E: 3 passed in 11.77s.
- Customer frontend, platform-admin, security, parity/registry, backup/restore, and staging smoke: SUCCESS.
- Existing charge paid-floor/delete rules remain unchanged; ACCOUNTING.CHARGES permission/write-role enforcement and display compatibility are verified.
- Bulk Tenant Charges Upload remains a hidden compatibility slot; the actual bulk workflow is still scheduled.
- Alembic head remains 8c4e2a7d1f90.

Current batch:
- Phase 3.4.22 Properties compatibility retrofit.

Next action:
1. Read AI_HANDOFF.md completely before the batch.
2. Inspect the existing Properties list/detail/edit/unit surfaces and preserve verified property/unit behavior.
3. Add missing shared display compatibility and authoritative PROPERTIES permission/write enforcement where needed.
4. Represent planned independent property capabilities as release-gated compatibility slots without implementing expansion workflows.
5. Add regression/E2E coverage, verify through hosted CI, fix reds autonomously, update ledgers/handoff, and continue directly to the next ordered batch.

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
