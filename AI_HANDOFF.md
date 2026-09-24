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

The docs/ folder is reserved for source-of-truth documents
that must NOT be edited by ChatGPT:

- docs/PROJECT_MASTER.md
- docs/FEATURE_REGISTRY.md
- docs/PLAN_GAPS.md
- docs/FILE_CATALOG.md
─────────────────────────────────────────────────────────

# Current Resume State

Branch: chatgpt/checkpoint-005-safety
Current HEAD hash: resolve from this branch with `git rev-parse HEAD`; this file is committed as part of HEAD, so the literal self-hash cannot be embedded without changing that hash.

Last completed batch:
- Phase 3.4.7 Batch 10 — transactional subscription lifecycle service with append-only events and provider-event idempotency.
- Phase 3.4.7 basic billing foundation is COMPLETE at the backend/foundation level: catalog, subscriptions/items/events, invoices/usage, billing settings/payment-method metadata, entitlements, menu gating, add-ons/discounts/quotes, and lifecycle transitions are now represented.
- Maintenance after Batch 10 — CI backup/restore validation now compares restored schema table count to the source schema instead of a stale hardcoded count.
- Maintenance after Batch 10 — authenticated E2E property smoke now opens the Units tab before asserting seeded unit data, matching the current property-detail UI.

Next batch to run:
- Phase 3.4.8 Batch 1 — backend-only Stripe Checkout session and webhook foundation for self-serve signup/payment. Do not build user-visible UI in this batch.

Open blockers:
- NONE

Exact prompt for a new ChatGPT session:
Read AI_HANDOFF.md at the repo root first. Continue only on branch `chatgpt/checkpoint-005-safety`. Do not switch branches, create branches, or touch `main`. Do not edit the frozen source-of-truth files under docs/: PROJECT_MASTER.md, FEATURE_REGISTRY.md, PLAN_GAPS.md, FILE_CATALOG.md, or APPFOLIO_PARITY_CHECKLIST.json. Follow the existing project plan and the user's one-batch/one-commit autonomous workflow. Phase 3.4.7 is complete. Resume with Phase 3.4.8 Batch 1: add backend-only Stripe Checkout session creation and webhook processing foundations for self-serve signup/payment, with no user-visible page yet. Stop for the user's "go" only immediately before the first user-visible page/tab/button/form/menu work in Phase 3.4.8, or for a true blocker/security/failing unrelated test/context-limit condition. Keep AI_HANDOFF.md at repo root and overwrite it after every BATCH DONE while preserving the permanent location-rule header at the top.
