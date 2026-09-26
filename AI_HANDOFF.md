─────────────────────────────────────────────────────────
AI_HANDOFF.md LOCATION RULE (READ FIRST)
─────────────────────────────────────────────────────────
This file lives at the REPO ROOT, not under docs/.
It is the single source of truth for resuming AI development.
The assistant must overwrite it after every meaningful batch, keeping
the next task, exact verification evidence, and Git/migration state current.
Do not ask Yasir to reconstruct context or maintain this file.
─────────────────────────────────────────────────────────

# RESUME HERE — 2026-09-26

Repository: yasirskhan/property-platform (private)
Only working branch: chatgpt/checkpoint-005-safety
Inspected source HEAD before this handoff-only commit:
fad5066aa2bc4498156179fad6bb5c8ad1cfcf65
Always fetch current branch HEAD again before work; this file's own
commit changes the hash. Never edit main, switch/create branches, or
force-push. Draft PR #2 targets main; do not merge without approval.

CURRENT PHASE: 3.7 — Reports + Universal Attachments, IN PROGRESS.
EXACT NEXT BATCH: Custom Report Builder (saved configurations).
The preceding report framework and Print / Email / CSV delivery work
are COMPLETE/VERIFIED. No implementation for the custom builder was
included in this handoff-only update. Do not restart Phases 3.4.x.
Phases 3.4.S and 3.4.3–3.4.26, compatibility pass 3.5.5, and
Accounting Polish 3.6 were previously completed/verified.

# LAST VERIFIED CI AND SCHEMA

Latest verified source commit:
fad5066aa2bc4498156179fad6bb5c8ad1cfcf65
Message: Docs: verify shared report delivery
Hosted GitHub Actions CI run: 36222494517 — SUCCESS, attempt 1.
Backend exact summary:
380 passed, 3 deselected, 3120 warnings in 58.96s
E2E exact summary: 3 passed in 9.17s
Frontend: SUCCESS (lint, TypeScript, production build)
Platform admin: SUCCESS
Security: SUCCESS
Staging-config: SUCCESS
Backend job includes PostgreSQL/bootstrap and parity/registry/secret checks;
E2E includes disposable DB seed and PostgreSQL backup/restore drill.
This handoff edit itself does not rerun tests: TESTS NOT RUN for docs-only edit.
Never reuse these counts to describe tests on any later source change.

Alembic head: a3d5f7b9c1e4
Expected model tables: 99
Parity checklist metadata (source HEAD): 628 total,
264 built, 364 scheduled, 0 in progress.
`check_parity.py CLEAN` is planning consistency, not proof of behavior.

# VERIFIED CONTRACTS TO PRESERVE

1. Hybrid Capability Gating keeps release control, plan entitlement,
   organization configuration, role/menu permission, and user preference
   separate. The backend is authoritative; hiding UI is not security.
   No per-field flags for routine columns, labels, filters, or controls.
2. Existing verified accounting posts through central immutable GL paths.
   Maintain org/owner/property isolation, locked-period constraints,
   atomic accounting, append-only audit, and idempotency where needed.
3. Customer and internal platform identities and JWT audiences remain
   separate. Do not mix platform staff with customer roles.
4. Universal Notes and Universal Attachments are verified shared
   organization-scoped services. Reuse them; do not build parallel stores.
5. Reporting basis is ACCRUAL by default or CASH at the report layer only;
   selecting it must not change GL postings.
6. Existing reporting catalog is the canonical standard/enhanced inventory.
   Catalog: GET /api/reporting/catalog, protected by REPORTING.ALL.
   Existing verified report delivery supports Chart of Accounts,
   Trial Balance, per-account General Ledger, and frozen Owner Statement.
   CSV/email re-render on server; underlying report permissions and
   release.reporting.export remain authoritative. CSV formula escaping,
   organization scope, and fail-closed unsupported keys are verified.
7. The existing customer reporting page uses catalog tier tabs, search,
   category grouping, and shared ReportActions. Preserve current
   standard BUTTON vs enhanced TAB presentation.

# PHASE 3.7 WORK COMPLETED

- Universal Attachments: commit 90e54eb834047038f01959c5a2a20c9e4155e999;
  CI 36219990832 SUCCESS.
- Report framework: commit 3afb0d3d2b41a222225e5ca20fb9c976fee77742;
  CI 36221727596 SUCCESS.
- Print / Email / CSV shared report actions:
  commit f5c8a5177db003c5d6d1b2eb2fbf8510791d31d6;
  CI 36222255513 SUCCESS.
- Report-delivery documentation closeout:
  fad5066aa2bc4498156179fad6bb5c8ad1cfcf65;
  CI 36222494517 SUCCESS.

Relevant existing implementation entry points:
- backend/app/routers/reporting.py
- backend/app/schemas/reporting.py
- backend/app/services/report_catalog.py
- backend/app/services/report_delivery.py
- backend/app/services/reporting_basis.py
- backend/tests/test_reporting_framework.py
- backend/tests/test_report_delivery.py
- frontend/src/app/dashboard/reporting/page.tsx
- frontend/src/components/reporting/ReportActions.tsx
- frontend/src/lib/reporting.ts
- backend/app/models/entity_attachment.py
- backend/app/routers/entity_attachments.py
Find actual wiring in backend/app/main.py and the repository file catalog;
inspect current source rather than assuming these signatures stay unchanged.

# NEXT WORK — DO THIS, NOT AN OLD ROADMAP ITEM

1. Read this entire handoff first, then inspect the actual source.
   Consult docs/PROJECT_MASTER.md Section 38 for ordered Phase 3.7
   deliverables and Section 82 for revised foundation ordering;
   use docs/FEATURE_REGISTRY.md, docs/PLAN_GAPS.md,
   docs/APPFOLIO_PARITY_CHECKLIST.json, and docs/FILE_CATALOG.md.
   WARNING: older PROJECT_MASTER Part A/B1 text contains historical
   status and may contradict this newer verified branch checkpoint.
   Do not regress to older 3.4/3.6 instructions.
2. Implement Custom Report Builder SAVED CONFIGURATIONS as the next
   meaningful batch, reusing the canonical report catalog and existing
   reporting auth/gating. Inspect current models/routes/frontend before
   designing storage or endpoints. Scope its edit/run/permission rules
   against source-of-truth docs and verified services; do not invent
   generic arbitrary SQL/report execution or expose unauthorized data.
3. Add focused regression tests for cross-org isolation, saved
   configuration validation, permission/gate enforcement, and existing
   catalog/delivery compatibility. Use a hand-written Alembic migration
   only if storage requires one. Update head/table-count test guards.
4. Run applicable local tests BEFORE product-code commits when an
   executable current-head working tree is available. The connected
   GitHub-only environment does not execute tests on uncommitted edits:
   if no local runner is available, do not pretend local tests ran.
   The user authorized commit-first, CI-verified TEST-ONLY fixes for
   stale assertions; that exception does NOT apply to product code.
   If product-code verification is impossible, treat it as a real
   blocker rather than silently weakening the rule.
5. Fix CI reds autonomously; when same assertion fails three times
   consecutively, stop and report. Record exact pass/fail counts,
   commit SHAs, CI run IDs, current Alembic head/table count, and
   parity changes. Update this repo-root handoff after EVERY batch,
   not just at phase boundaries.
6. After Custom Report Builder, follow Section 38 Phase 3.7 order:
   Create Labels Report; Generate 1099 Forms & Reports; Letters;
   Send Owner Packets; tenant/property/owner/accounting/transaction
   reports, checking exact roadmap order and existing verified work.
   Continue into subsequent phases without asking for a new "go".
   Stop only for a true blocker, repeated same assertion per rule,
   or context exhaustion with a complete handoff.

# DEVELOPMENT AND DOCUMENTATION RULES

- Meaningful batches, not repetitive one-file steps or narration-only
  audits. Inspect source before editing; do not duplicate verified work.
- Fix CI reds yourself. Do not poll excessively or claim tests passed
  unless you have the exact observed result.
- Update AI_HANDOFF.md at repo root after each batch, never under docs/.
- Keep roadmap, capability inventory, parity metadata, and file catalog
  accurate when changes warrant it; preserve their established contracts
  rather than casually rewriting them. Follow current user instructions
  if legacy documents conflict.
- Keep tested migration/model inventory synchronized with actual schema.
- Do not edit product code merely to improve the handoff.
- User is a non-coder; do not ask the user to perform code changes.
- No speculative success claims, no duplicate commit/batch, no forced
  branch updates, and no changes to main.

# NEXT-SESSION START PROMPT

Continue yasirskhan/property-platform on
chatgpt/checkpoint-005-safety. Read repo-root AI_HANDOFF.md completely.
Verify current HEAD and current CI, then execute the exact next task:
Phase 3.7 Custom Report Builder (saved configurations). Preserve all
VERIFIED contracts and the original roadmap. Keep AI_HANDOFF.md current
after every meaningful batch; fix CI reds yourself; do not stop at
phase boundaries, except for a true blocker or context handoff.
