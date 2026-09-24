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
- Phase 3.4.7 Batch 1 — billing catalog foundation: plans, modules, plan/module links, module features, and property-count pricing tiers.

Next batch to run:
- Phase 3.4.7 Batch 2 — customer subscription storage foundation and organization-to-plan subscription state, backend only.

Open blockers:
- NONE

Exact prompt for a new ChatGPT session:
Read AI_HANDOFF.md at the repo root first. Continue only on branch `chatgpt/checkpoint-005-safety`. Do not switch branches, create branches, or touch `main`. Do not edit the frozen source-of-truth files under docs/: PROJECT_MASTER.md, FEATURE_REGISTRY.md, PLAN_GAPS.md, FILE_CATALOG.md, or APPFOLIO_PARITY_CHECKLIST.json. Follow the existing project plan and the user's one-batch/one-commit autonomous workflow. Resume with Phase 3.4.7 Batch 2: customer subscription storage foundation and organization-to-plan subscription state. Keep AI_HANDOFF.md at repo root and overwrite it after every BATCH DONE while preserving the permanent location-rule header at the top.
