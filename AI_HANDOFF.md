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
- Phase 3.6 Chart of Accounts, Journal Entries, Receipts, and the first Bills lifecycle batch are COMPLETE/VERIFIED.
- Bills lifecycle verification: CI run 36080191707, 275 passed, 3 deselected.
- Recurring Bills / Vendor Credits backend foundation is COMPLETE/VERIFIED at commits e1a7ee2037b3065261b8531b90bfa368379a4b46 + d068eb3cdab90647c5ea9249067bfcf1952d79a6.
- Backend foundation verification: CI run 36083078977 SUCCESS; 279 passed, 3 deselected, 1807 warnings in 45.37s; E2E 3 passed in 12.14s; frontend/platform-admin/security/staging green.
- Current migration head: ad3e5f7b9c21; expected model-table count: 83.

Current phase:
- Phase 3.6 — Accounting Polish.
- Active subsection: Bills.
- Current implementation batch: customer UI for Recurring Bills/Credits, Post Codes, selected Manually Post Bills, and Enter Vendor Credit.
- Existing release gates remain independent and backend ACCOUNTING.PAYABLES authorization is authoritative.
- Static workflow routes use unambiguous paths so GET /{bill_id} cannot shadow recurring/credit reads.
- Product commit for this UI batch is pending hosted CI verification.

Next exact action:
1. Verify the current Bills workflow UI batch in hosted CI and fix any red autonomously.
2. When green, update PROJECT_MASTER / FEATURE_REGISTRY / APPFOLIO_PARITY_CHECKLIST / FILE_CATALOG for the verified recurring bills, post codes, manual posting, and vendor credits capability.
3. Continue immediately into Write Checks: Find Bills -> Confirm & Finalize -> Print, then Checks list, Void Check, and Check Memo.
4. Preserve central post_transaction(), locked periods, organization isolation, payment/reversal contracts, and independent access layers.
5. Do not stop at the phase boundary; continue ordered Phase 3.6 work unless truly blocked.

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
