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

Verified foundation:
- Phase 3.4.S and Phases 3.4.3 through 3.4.26 are COMPLETE/VERIFIED.
- Phase 3.5.5 compatibility pass is COMPLETE.
- Phase 3.6 Chart of Accounts polish is COMPLETE/VERIFIED.
- Phase 3.6 Journal Entries polish is COMPLETE/VERIFIED.
- Phase 3.6 Receipts polish is COMPLETE/VERIFIED.

Latest Receipts evidence:
- Implementation commit: 1859e35bf914b2d0d612500f497c844a8e312005.
- Type-contract repair commit: 65929757ae5cd32911c219c769f9565d6538f31f.
- Hosted CI run 36078119785: SUCCESS.
- Backend/PostgreSQL: 272 passed, 3 deselected, 1574 warnings in 28.64s.
- E2E: 3 passed in 11.33s.
- Customer frontend, platform-admin, security, parity/registry, backup/restore, and staging smoke: SUCCESS.
- Dedicated Application Fee receipts, Process NSF, printable receipt, repeat receipt, deposited-receipt integrity visibility, and Automatic cash account behavior are implemented.
- Posted receipt immutability and existing reversal/deposit accounting contracts are preserved.
- No migration in the Receipts batch; Alembic head remains 6a1d9e3f4b72 and expected model-table count remains 79.

Current phase:
- Phase 3.6 — Accounting Polish.
- Active subsection: Bills.
- Charges subsection is already built in current source/parity: standalone entry/list plus paid-floor/no-paid-delete backend edit rules.

Current Bills lifecycle batch:
- Partial-payment reversal stages reversal of all unreversed bill-payment GL transactions plus the original accrual and commits the full unwind atomically.
- Fully paid bills remain protected from reversal.
- DELETE is accounting-safe and unpaid-only: it reverses the accrual, preserves the immutable GL trail, and soft-hides the bill/reversal records.
- Bills carry an optional default cash account; entering the bill remains accrual-only and later payments may use or override that default.
- Customer New Bill exposes the default cash account and the bill detail payment flow preselects it.
- Migration 9c2e4f6a8b10 adds bills.cash_gl_account_id; expected model-table count remains 79.
- Regression coverage is added in backend/tests/test_bill_polish.py.

Next exact action:
1. Verify this Bills lifecycle batch in hosted CI and fix reds autonomously.
2. On green, checkpoint its evidence and continue the Bills subsection with recurring bills/Post Codes, Enter Credit, Write Checks, and Manually Post Bills.

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
- Do not stop at phase boundaries; continue until a true blocker or context handoff is required.
