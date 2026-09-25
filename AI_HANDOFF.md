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
- Phase 3.6 Chart of Accounts, Journal Entries, Receipts, Charges, Bills lifecycle, Recurring Bills/Credits, Post Codes, Manually Post Bills, Vendor Credits, Write Checks / Checks, and Bank Deposits polish are COMPLETE/VERIFIED.
- Bank Deposits implementation commit: 2911ddb2ab857db6dc65e78cbba42db05a923523.
- Bank Deposits CI run 36086704375: SUCCESS.
- Backend: 284 passed, 3 deselected, 1942 warnings in 44.30s.
- E2E: 3 passed in 10.98s.
- Frontend, platform-admin, security, and staging: SUCCESS.
- Current migration head: c7d9e1f3a5b2; expected model-table count: 85.
- Parity inventory: 234 built, 0 in progress, 394 scheduled, 628 total.

Current phase:
- Phase 3.6 — Accounting Polish.
- Next ordered subsection: Bank Accounts.
- Bank Accounts order: Bank Reconciliation (Section 37), QIF Import, Check Setup, ACH file generation, Bank Adjustments, Bank Feed import.
- Preserve verified bank account CRUD and all accounting isolation/immutability contracts.

Next exact action:
1. Read current Bank Account source and Section 37 before implementation.
2. Build the Bank Reconciliation foundation/workflow as the next coherent batch: statement date/ending balance, clearable deposits + checks/payments, reconcile calculator, balanced finish, and QIF import support where it naturally belongs to the reconciliation workflow.
3. Keep ACCOUNTING.BANK_ACCOUNTS backend permission authoritative and gate reconciliation/QIF through their existing independent release + entitlement/config layers.
4. Verify in hosted CI and fix reds autonomously.
5. Update PROJECT_MASTER / FEATURE_REGISTRY / APPFOLIO_PARITY_CHECKLIST / FILE_CATALOG / AI_HANDOFF after green.
6. Continue directly through Check Setup, ACH generation, Bank Adjustments, and Bank Feed without waiting for user approval.

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
