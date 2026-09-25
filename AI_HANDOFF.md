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
- Phase 3.6 Chart of Accounts, Journal Entries, and Receipts polish are COMPLETE/VERIFIED.
- Phase 3.6 Bills lifecycle batch is COMPLETE/VERIFIED at commits a5bf7a42d3a0bc3d859efbac3d7df1b9ea79c008 + d58dbff17137a6d9fa1cbfadbf2a845f22b6adc2; CI run 36080191707 was green with 275 passed, 3 deselected.

Current phase:
- Phase 3.6 — Accounting Polish.
- Active subsection: Bills.
- Current implementation batch: recurring Bill/Credit schedules + Post Codes + Manually Post Bills + real positive-value Vendor Credits backend foundation.
- This batch adds durable recurring-bill schedules, selected/manual due posting, a daily durable-job sweep, and vendor credits posted as DR Accounts Payable / CR line accounts rather than negative bills.
- Product commit for this batch is pending hosted CI verification.
- Migration head for this batch: ad3e5f7b9c21; expected model-table count: 83.

Next exact action:
1. Verify the current Bills workflow backend batch in hosted CI.
2. Fix any CI red autonomously without waiting.
3. When green, activate the customer UI for Recurring Bills, Manually Post Bills, and Enter Credit using the existing release gates and ACCOUNTING.PAYABLES authorization.
4. Update planning/registry/parity state and FILE_CATALOG as appropriate, checkpoint AI_HANDOFF.md, then continue directly into Write Checks / Checks list / Void Check / Check Memo.
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
