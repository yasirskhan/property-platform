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
- Post GPR checkpoint commit 538f04ac9d8e6f2bb60e71036765da045d4824ad is green in hosted CI run 36077315410.

Current Receipts batch:
- Implementation commit: 1859e35bf914b2d0d612500f497c844a8e312005.
- Initial CI run 36077939445: backend GREEN at 272 passed, 3 deselected, 1574 warnings in 43.59s; security + platform-admin GREEN; frontend TypeScript failed only because the typed ReceiptCreateIn contract still required numeric cash_gl_account_id while Automatic legitimately sends null and Receipt output had been made optional.
- Repair is type-contract only: Receipt output cash_gl_account_id stays required numeric; ReceiptCreateIn cash_gl_account_id becomes optional/null. Product behavior is unchanged.
- Hosted CI verification of the repair is the immediate next action.

Implemented Receipts capabilities:
- Dedicated APPLICATION_FEE receipt mode posts to standard 4420 and is server-gated by release.accounting.receipts.application_fee.
- Cash Account Automatic resolves the org's active OPERATING bank mapping, falling back to active 1150 Rental Trust when no bank mapping exists.
- Process NSF is a server-gated bounced-payment action that reuses the verified reversal spine and preserves original deposit history; any NSF fee remains a separate tenant Charge.
- Print one receipt has a server-gated print-data endpoint and dedicated printable customer page.
- Repeat prior receipt has a server-gated repeat-data endpoint that hydrates the existing New Receipt form instead of auto-posting a duplicate.
- Receipt responses expose deposit_id/is_deposited so deposited history is visible; posted receipts remain immutable and corrections stay reversal/NSF based.
- No migration is planned for this batch; Alembic head should remain 6a1d9e3f4b72 and expected model-table count 79.

Next exact action:
1. Commit the frontend type-contract repair and verify it in hosted CI; fix any remaining reds autonomously.
2. On green, update PROJECT_MASTER/FEATURE_REGISTRY/APPFOLIO_PARITY_CHECKLIST/FILE_CATALOG plus this handoff with exact evidence.
3. Continue directly to the next ordered Phase 3.6 accounting subsection without waiting.

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
