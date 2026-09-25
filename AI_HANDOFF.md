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
- Phase 3.6 Chart of Accounts, Journal Entries, Receipts, Charges, Bills lifecycle, Recurring Bills/Credits, Post Codes, Manually Post Bills, Vendor Credits, Write Checks / Checks, Bank Deposits polish, Bank Reconciliation, QIF Import, and Check Setup are COMPLETE/VERIFIED.
- Check Setup implementation commit: 35cb5754884f4b2db797bd234f0898e823f49543.
- Check Setup CI run 36091014657: SUCCESS.
- Backend: 287 passed, 3 deselected, 2039 warnings in 27.32s.
- E2E: 3 passed in 11.75s.
- Frontend, platform-admin, security, and staging: SUCCESS.
- Current migration head: f2a4c6e8b0d5; expected model-table count: 89.
- Parity inventory: 238 built, 0 in progress, 390 scheduled, 628 total.

Current phase:
- Phase 3.6 — Accounting Polish.
- Active subsection: Bank Accounts.
- ACH File Generation is COMPLETE/VERIFIED in CI run 36091648909.
- Backend: 290 passed, 3 deselected, 2039 warnings in 51.71s.
- E2E: 3 passed in 11.18s; frontend, platform-admin, security, and staging all succeeded.
- Active subsection: Bank Adjustments.
- Remaining Bank Accounts order after Bank Adjustments: Bank Feed import.
- Preserve verified bank account CRUD, reconciliation/QIF, Check Setup, and all accounting isolation/immutability contracts.

Next exact action:
1. Implement Bank Adjustments as one coherent batch under release.accounting.bank_adjustments and ACCOUNTING.BANK_ACCOUNTS.
2. Use the central GL posting service for any financial posting, preserve immutable/reversal accounting contracts, and keep organization scope authoritative.
3. Add the customer-visible adjustment sub-tab/workflow and regression coverage.
4. Verify in hosted CI, fix reds autonomously, update planning/parity/catalog/checkpoint state, then continue directly to Bank Feed import.

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
