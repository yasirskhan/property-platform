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
- Phase 3.4.S and Phases 3.4.3 through 3.4.26 are COMPLETE/VERIFIED, including safety, identity/audit, hybrid capability gating/jobs, locked accounting periods/org settings, end-to-end verification, billing/signup/fraud/internal-admin/customer feature consumption/plan limits, and the planned compatibility retrofit surfaces.
- Phase 3.5.5 compatibility pass is COMPLETE.
- Phase 3.6 Chart of Accounts polish is COMPLETE/VERIFIED: GL Account Permissions, hide/deactivation semantics, offset account UI, must-clear UI, and Recalculate Balances.
- Phase 3.6 Journal Entries polish is COMPLETE/VERIFIED: manual posting and memo/line semantics preserved, real recurring schedules + durable daily due sweep, and real Post GPR workflow.

Latest verified Journal Entries evidence:
- Recurring-JE repair commit: 25dff5056ec4e3c82ec157de170dc707176c1edc.
- Recurring-JE CI run 36073956865: SUCCESS.
- Backend/PostgreSQL: 266 passed, 3 deselected, 1423 warnings in 44.41s.
- E2E: 3 passed in 7.76s.
- Post GPR implementation commit: 032f75cead0a367d7c12c16146ea7e3a03869244.
- Post GPR test-fixture repair commit: 45ca7d683ed8084a30f6bfcfe9f8f24035d57645.
- Post GPR CI run 36076785230: SUCCESS.
- Backend/PostgreSQL: 269 passed, 3 deselected, 1508 warnings in 25.84s.
- E2E: 3 passed in 11.85s.
- Customer frontend, platform-admin, security, parity/registry, backup/restore, and staging smoke: SUCCESS.
- Post GPR is gated by release.accounting.journal_entries.post_gpr + gpr_posting entitlement + org config + ACCOUNTING.JOURNAL_ENTRIES.
- GPR candidates use Unit.monthly_rent as market/potential rent and overlapping ACTIVE Lease.monthly_rent as scheduled rent; vacant units use scheduled rent 0.
- Posting is a zero-net monthly reclassification through post_transaction(): 4100 Rent, 4115 Gross Potential Rent, 4120 Loss/Gain.
- Duplicate unit/month postings and cross-org units are rejected.
- No migration in Post GPR; Alembic head remains 6a1d9e3f4b72. Expected model-table count remains 79.

Current parity inventory:
- 213 built
- 0 in progress
- 415 scheduled
- 628 total

Current phase:
- Phase 3.6 — Accounting Polish.
- Active subsection: Receipts.

Next exact ordered batch:
1. Read this file completely and inspect real current receipt/deposit/bank-account source.
2. Implement the Receipts polish batch:
   - Dedicated Application Fee workflow.
   - Process NSF.
   - Print one receipt.
   - Repeat prior receipt.
   - Deposited-receipt integrity visibility / lock semantics without weakening existing immutable receipt behavior.
   - Cash Account “Automatic” behavior using existing verified bank/GL configuration; do not invent a property-bank relationship that does not exist.
3. Preserve existing tenant/owner/other receipt posting, reversal, deposit grouping, org isolation, and central post_transaction() contracts.
4. Apply release/entitlement/org-config/permission gating server-side to independent capabilities where required.
5. Verify in hosted CI, fix reds autonomously, update this handoff and planning docs, then continue Phase 3.6 without stopping.

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
