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
- Phase 3.6 Chart of Accounts, Journal Entries, Receipts, Charges, and Bills lifecycle polish are COMPLETE/VERIFIED.
- Bills lifecycle CI: run 36080191707, 275 passed, 3 deselected.
- Recurring Bills/Credits backend foundation: e1a7ee2037b3065261b8531b90bfa368379a4b46 + repair d068eb3cdab90647c5ea9249067bfcf1952d79a6.
- Recurring customer workflows: ea5367284813669fee383fc63438bde02df82f1e.
- Recurring Bills/Credits, Post Codes, Manually Post Bills, and positive-value Vendor Credits are COMPLETE/VERIFIED in CI run 36083621549.
- CI 36083621549: backend 280 passed, 3 deselected, 1807 warnings in 50.46s; E2E 3 passed in 13.00s; frontend/platform-admin/security/staging all SUCCESS.
- Current migration head: ad3e5f7b9c21; expected model-table count: 83.
- Parity inventory after this closeout: 226 built, 0 in progress, 402 scheduled, 628 total.

Current phase:
- Phase 3.6 — Accounting Polish.
- Active subsection: Write Checks / Checks.
- Verified Bills contracts remain fixed: two-step accrual, partial payment, partial-payment reversal, unpaid-only safe delete, default cash account, recurring posting idempotency, positive vendor credits, locked periods, organization isolation, and central post_transaction() accounting.

Next exact action:
1. Implement Write Checks flow in one coherent batch: Find Bills -> Confirm & Finalize -> Print.
2. Add durable Check + Check/Bill allocation storage, bank-account-backed cash posting, Check Memo, list/date filtering/drill-down, and accounting-safe Void Check.
3. Gate check writing independently with release.accounting.write_checks + check_writing entitlement/config + ACCOUNTING.PAYABLES backend permission.
4. Preserve bill amount_paid/status semantics and make issue/void financial state atomic.
5. Verify in hosted CI, fix reds autonomously, update PROJECT_MASTER / FEATURE_REGISTRY / APPFOLIO_PARITY_CHECKLIST / FILE_CATALOG / AI_HANDOFF, then continue directly to the next ordered Phase 3.6 subsection.
6. Do not stop at phase boundaries; continue unless truly blocked or context handoff is required.

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
