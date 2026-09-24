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
- Phase 3.4.7 basic billing foundation is COMPLETE at the backend/foundation level.
- Maintenance after Phase 3.4.7 — CI backup/restore validation is schema-aware, schema-head/table-count guards are current, the authenticated property smoke opens the Units tab before asserting seeded unit data, and property/unit edit permission guards normalize role enum casing before client-side routing.
- Phase 3.4.8 Batch 1 — backend-only Stripe Checkout foundation: durable DB-first checkout attempts, Stripe/provider idempotency, hosted subscription Checkout creation, signed raw-body webhook verification, Stripe customer/subscription reconciliation, and subscription/invoice lifecycle event handling. No frontend/UI changes.
- Phase 3.4.8 Batch 2 — backend-only customer billing read APIs: authenticated ADMIN/OWNER catalog reads expose active plans with ordered pricing tiers, while org-scoped billing state exposes safe billing settings, current subscription status, and the latest checkout attempt without provider customer/subscription/session IDs or idempotency keys. No frontend/UI changes.
- Phase 3.4.8 Batch 3 — self-serve ADMIN/OWNER organizations start in PENDING_BILLING, billing state reports the organization lifecycle state, invited-user signup preserves existing org state, and verified Stripe checkout completion promotes the organization to ACTIVE. No frontend/UI changes.

Next batch to run:
- Phase 3.4.8 Batch 4 — build the first customer-visible self-serve signup/payment surface: plan selection from the billing catalog, account creation, authenticated Checkout launch, and success/cancel state handling. Keep Stripe-hosted payment collection; never collect or store card data in our frontend.

Open blockers:
- NONE

Exact prompt for a new ChatGPT session:
Read AI_HANDOFF.md at the repo root first. Continue only on branch `chatgpt/checkpoint-005-safety`. Do not switch branches, create branches, or touch `main`. Do not edit the frozen source-of-truth files under docs/: PROJECT_MASTER.md, FEATURE_REGISTRY.md, PLAN_GAPS.md, FILE_CATALOG.md, or APPFOLIO_PARITY_CHECKLIST.json. Follow the existing project plan and the user's one-batch/one-commit autonomous workflow. Phase 3.4.7 is complete and Phase 3.4.8 Batches 1-3 are implemented. Resume with Phase 3.4.8 Batch 4: build the customer-visible self-serve signup/payment surface using the verified billing catalog, signup lifecycle, Checkout endpoint, and billing-state endpoint. Stripe remains the hosted payment surface; never collect or store card data in our frontend. Stop only for a true blocker/security/failing unrelated test/context-limit condition or before starting the next phase. Keep AI_HANDOFF.md at repo root and overwrite it after every BATCH DONE while preserving the permanent location-rule header at the top.
