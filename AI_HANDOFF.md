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
- Phase 3.6 Chart of Accounts, Journal Entries, Receipts, Charges, Bills lifecycle, Recurring Bills/Credits, Post Codes, Manually Post Bills, Vendor Credits, Write Checks / Checks, Bank Deposits polish, Bank Reconciliation, and QIF Import are COMPLETE/VERIFIED.
- Bank Reconciliation + QIF implementation commit: a6f69edfe2659ae8aacf5f44c3ab773a7992af0d.
- Bank Reconciliation + QIF CI run 36087388737: SUCCESS.
- Backend: 286 passed, 3 deselected, 1977 warnings in 49.89s.
- E2E: 3 passed in 11.56s.
- Frontend, platform-admin, security, and staging: SUCCESS.
- Current migration head: f2a4c6e8b0d5; expected model-table count: 89.
- Parity inventory: 236 built, 0 in progress, 392 scheduled, 628 total.

Current phase:
- Phase 3.6 — Accounting Polish.
- Active subsection: Bank Accounts.
- Active subsection: Check Setup implementation committed for hosted verification.
- Remaining Bank Accounts order after this batch: ACH file generation, Bank Adjustments, Bank Feed import.
- Preserve verified bank account CRUD, reconciliation/QIF, and all accounting isolation/immutability contracts.

Next exact action:
1. Verify the Check Setup batch in hosted CI and fix reds autonomously.
2. The batch adds per-bank automatic check numbering, optional prefix, check stock position, memo/signature print preferences, and a gated customer setup page; Write Checks consumes configured numbering when the check number is blank.
3. After green, update planning/parity/catalog/checkpoint state.
4. Continue directly to ACH file generation, Bank Adjustments, and Bank Feed without waiting for user approval.

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
