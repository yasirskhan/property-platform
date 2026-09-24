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

Verified foundation through this checkpoint:
- Phase 3.4.S engineering safety foundation.
- Phase 3.4.3 identity boundary + immutable audit.
- Phase 3.4.4 Hybrid Capability Gating + jobs runtime + Sentry foundation.
- Phase 3.4.5 locked accounting periods + core organization settings + GDPR schema foundation.
- Phase 3.4.6 end-to-end verification.
- Phase 3.4.7 billing foundation.
- Phase 3.4.8 self-serve signup/payment.
- Phase 3.4.9 fraud/abuse foundation.
- Phase 3.4.10 separate internal admin app.
- Phase 3.4.11 customer release-gate consumption + Settings → Features.
- Phase 3.4.12 unit/plan-limit enforcement.
- Phase 3.4.13 Receipts compatibility retrofit.
- Phase 3.4.14 Bills compatibility retrofit.
- Phase 3.4.15 Bank Deposits compatibility retrofit.
- Phase 3.4.16 GL Accounts compatibility retrofit.
- Phase 3.4.17 Journal Entries compatibility retrofit is COMPLETE and VERIFIED.
- Phase 3.4.18 Management Fees compatibility retrofit is COMPLETE and VERIFIED.
- Phase 3.4.18 repair/final implementation commit: 1ee39901d7ffd42f01c26db158ce692993f1deb1.
- GitHub CI run 36036233118: SUCCESS.
- Backend/PostgreSQL: 203 passed, 3 deselected, 1266 warnings in 39.57s.
- E2E: 3 passed in 11.89s.
- Customer frontend, platform-admin, security, parity/registry, backup/restore, and staging smoke: SUCCESS.
- Alembic head remains 8c4e2a7d1f90.

Verified latest batch:
- Phase 3.4.19 Owner Statements compatibility retrofit is COMPLETE and VERIFIED.
- Final repair commit: 2632f10e8d973a15fdcb7ee50f1b13d1ea91cd1f.
- GitHub CI run 36043279261: SUCCESS.
- Backend/PostgreSQL: 213 passed, 3 deselected, 1266 warnings in 28.28s.
- E2E: 3 passed in 11.57s.
- Customer frontend, platform-admin, security, parity/registry, backup/restore, and staging smoke: SUCCESS.
- Frozen statement snapshots and existing per-property transaction math remain unchanged.
- Display/date compatibility, ACCOUNTING.OWNER_STATEMENTS permission enforcement, ADMIN/OWNER/MANAGER write roles, structural reserve/prepaid slots, and hidden release-gated cash-summary/packet/email slots are verified.
- Alembic head remains 8c4e2a7d1f90.

Verified latest batch:
- Phase 3.4.20 Bank Accounts compatibility retrofit is COMPLETE and VERIFIED.
- Final repair commit: aa44bc1a53717188bc37a5adda04abc7505358fe.
- GitHub CI run 36046681933: SUCCESS.
- Backend/PostgreSQL: 223 passed, 3 deselected, 1266 warnings in 42.30s.
- E2E: 3 passed in 10.75s.
- Customer frontend, platform-admin, security, parity/registry, backup/restore, and staging smoke: SUCCESS.
- Existing physical bank-account CRUD and GL-account mapping remain unchanged.
- Shared display compatibility, ACCOUNTING.BANK_ACCOUNTS permission enforcement, ADMIN/OWNER/MANAGER write roles, and hidden release-gated reconciliation/QIF/check/ACH/feed/adjustment slots are verified.
- Alembic head remains 8c4e2a7d1f90.

Verified latest batch:
- Phase 3.4.21 Charges compatibility retrofit is COMPLETE and VERIFIED.
- Implementation commit: 7148b788315be7c6a245884da8d2dec5e0f02913.
- GitHub CI run 36051620935: SUCCESS.
- Backend/PostgreSQL: 233 passed, 3 deselected, 1266 warnings in 36.78s.
- E2E: 3 passed in 11.77s.
- Customer frontend, platform-admin, security, parity/registry, backup/restore, and staging smoke: SUCCESS.
- Existing charge paid-floor/delete rules remain unchanged; ACCOUNTING.CHARGES permission/write-role enforcement and display compatibility are verified.
- Bulk Tenant Charges Upload remains a hidden compatibility slot; the actual bulk workflow is still scheduled.
- Alembic head remains 8c4e2a7d1f90.

Verified latest batch:
- Phase 3.4.22 Properties compatibility retrofit is COMPLETE and VERIFIED.
- Final repair commit: d26b2f4e8eee85e09643a29fcda68948d98c5192.
- GitHub CI run 36056943124: SUCCESS.
- Backend/PostgreSQL: 239 passed, 3 deselected, 1266 warnings in 36.66s.
- E2E: 3 passed in 10.40s.
- Customer frontend, platform-admin, security, parity/registry, backup/restore, and staging smoke: SUCCESS.
- Minimal org-isolation test schema includes menu_permissions + user_permissions required by authoritative property permission resolution; product authorization is unchanged.
- Existing org/assignment scope and unit plan-limit behavior are unchanged.
- Backend routes now layer PROPERTIES.ALL, PROPERTIES.ADD, and PROPERTIES.UNITS menu permissions over existing scope/role checks.
- Property list/detail/new/edit and unit new/edit surfaces consume shared display preferences and normalize role casing.
- Property edit UI now matches backend ADMIN/OWNER authorization while MANAGER keeps allowed unit/child-tab management.
- Planned Property Groups/Map and property-detail capabilities are hidden release-gated compatibility slots only; their workflows remain scheduled.
- No migration is required; Alembic head remains 8c4e2a7d1f90.

Verified latest batch:
- Phase 3.4.23 Currencies compatibility retrofit is COMPLETE and VERIFIED.
- Implementation commit: 9b9dad9eec699887035f6acd9fbb6bbb7b150729.
- GitHub CI run 36057866985: SUCCESS.
- Backend/PostgreSQL: 249 passed, 3 deselected, 1266 warnings in 42.14s.
- E2E: 3 passed in 13.23s.
- Customer frontend, platform-admin, security, parity/registry, backup/restore, and staging smoke: SUCCESS.
- Existing per-org currency CRUD, system-currency protections, and current-currency delete/deactivate protections are unchanged.
- Currency routes now enforce SETTINGS.CURRENCIES server-side in addition to existing ADMIN/OWNER write roles.
- Currencies UI consumes shared display layout/density metadata and hides mutation controls from non-writers.
- Display currency choices come from /api/settings/currencies; hardcoded alternate fallback currencies were removed, while the current org currency remains selectable if catalog loading fails.
- No migration is required; Alembic head remains 8c4e2a7d1f90.

Verified latest batch:
- Phase 3.4.24 Display compatibility retrofit is COMPLETE and VERIFIED.
- Implementation commit: 4a58e2513004b3ad235d495b964a5749e5780faf.
- GitHub CI run 36058923158: SUCCESS.
- Backend/PostgreSQL: 252 passed, 3 deselected, 1266 warnings in 41.71s.
- E2E: 3 passed in 11.93s.
- Customer frontend, platform-admin, security, parity/registry, backup/restore, and staging smoke: SUCCESS.
- Existing display preference storage/API and org-currency write semantics are unchanged.
- GET/PUT /api/settings/display now enforce SETTINGS.DISPLAY server-side.
- DisplayContext's theme, density, font size, accent, and reduce-motion attributes are consumed by shared CSS.
- The Display page consumes shared layout/density metadata; density, font size, accent color, and reduce-motion controls now drive already-existing persisted fields.
- Number format remains intentionally deferred because formatMoney() does not yet consume it.
- No migration is required; Alembic head remains 8c4e2a7d1f90.

Verified latest batch:
- Phase 3.4.25 Permissions compatibility retrofit is COMPLETE and VERIFIED.
- Implementation commit: 9a0680914e0f1f3ac96a93e2751d6db180a2eadf.
- GitHub CI run 36060022264: SUCCESS.
- Backend/PostgreSQL: 256 passed, 3 deselected, 1266 warnings in 41.97s.
- E2E: 3 passed in 10.77s.
- Customer frontend, platform-admin, security, parity/registry, backup/restore, and staging smoke: SUCCESS.
- Existing role matrix/editor hierarchy, immutable ADMIN role, user override semantics, and My Preferences storage remain unchanged.
- Privileged role-matrix and user-override endpoints require SETTINGS.PERMISSIONS server-side.
- /api/menu/me and /api/menu/me/preferences remain self-service and intentionally independent of SETTINGS.PERMISSIONS.
- Permissions UI consumes shared display layout/density metadata and normalizes role casing.
- GL Account Permissions remains a hidden release-gated future capability; its workflow is still scheduled.
- No migration is required; Alembic head remains 8c4e2a7d1f90.

Current batch:
- Phase 3.4.26 Sidebar compatibility retrofit is next.

Next action:
1. Preserve the legacy /dashboard/settings/sidebar compatibility route while landing users on Permissions → My Preferences.
2. Preserve personal sidebar order/hide behavior and backend-authoritative resolved-menu rendering.
3. Verify compatibility behavior in E2E and keep legacy API semantics compatible.
4. Fix CI reds autonomously, update ledgers/handoff, and continue to the next planned compatibility batch.

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
