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
- Phase 3.6 Chart of Accounts, Journal Entries, Receipts, Charges, Bills lifecycle, Recurring Bills/Credits, Post Codes, Manually Post Bills, Vendor Credits, and Write Checks / Checks are COMPLETE/VERIFIED.
- Write Checks implementation commit: 5a13033641035aceffa0283d48c470c894e008dd.
- Write Checks CI run 36085905091: SUCCESS.
- Backend: 282 passed, 3 deselected, 1889 warnings in 48.45s.
- E2E: 3 passed in 12.39s.
- Frontend, platform-admin, security, and staging: SUCCESS.
- Current migration head: f4a6c8d0e2b1; expected model-table count: 85.
- Parity inventory: 230 built, 0 in progress, 398 scheduled, 628 total.

Current phase:
- Phase 3.6 — Accounting Polish.
- Active subsection: Bank Deposits implementation committed for hosted verification.
- Preserve verified deposit contract: receipts already post cash; deposits group receipts only through deposit_lines and do not create another GL transaction.
- Verified accounting contracts remain fixed: org isolation, locked periods, central post_transaction() for real GL writes, atomic financial workflows, and immutable/reversal accounting semantics.

Next exact action:
1. Verify the Bank Deposits polish batch in hosted CI and fix reds autonomously.
2. Batch includes durable per-bank deposit sequencing, existing date mismatch warnings, gated print slips, and safe post-creation edit of metadata/receipt membership without GL writes.
3. After green, update PROJECT_MASTER / FEATURE_REGISTRY / APPFOLIO_PARITY_CHECKLIST / FILE_CATALOG / AI_HANDOFF.
4. Continue directly to the next ordered Phase 3.6 subsection without waiting for user approval.

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
