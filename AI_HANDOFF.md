─────────────────────────────────────────────────────────
AI_HANDOFF.md LOCATION RULE (READ FIRST)
─────────────────────────────────────────────────────────
This file lives at the REPO ROOT and is the single resume point.
Keep it here and overwrite it after every meaningful batch.
─────────────────────────────────────────────────────────

# Current Resume State

Branch: chatgpt/checkpoint-005-safety

IMPORTANT:
- Do NOT resume old Phase 3.4.x work.
- Phase 3.4.S and Phases 3.4.3 through 3.4.26 are COMPLETE/VERIFIED.
- Phase 3.5.5 compatibility pass is COMPLETE.
- Current work is Phase 3.6 — Accounting Polish.
- Bank Accounts subsection is now COMPLETE through Bank Feed import.
- Next ordered item: $0 ACH Test File.

# Latest Verified Green Checkpoint

Bank Feed verification trigger:
- 84469ab3473ecc682d35b1c9ff12d2b164fd8dae
- "Docs: trigger Bank Feed revalidation checkpoint"

Hosted CI:
- Run 36099568648: SUCCESS
- Backend: 298 passed, 3 deselected, 2184 warnings in 36.14s
- E2E: 3 passed in 13.65s
- Frontend: SUCCESS
- Platform admin: SUCCESS
- Security: SUCCESS
- PostgreSQL bootstrap + backup/restore: SUCCESS
- Staging build/start/health: SUCCESS
- Parity/registry consistency: CLEAN
- Secret-pattern scan: CLEAN

Current parity source-of-truth:
- total_items: 628
- built_count: 238
- scheduled_count: 390
- in_progress_count: 0
- migration_head: b6d8f0a2c4e7
- expected model-table count: 91

# Bank Adjustments

COMPLETE/VERIFIED.
- Backend ledger workflow: dc84db4602b2de4e04c93ac35dc6a4ff29525bad
- Customer workflow: 4d037b6608c07d142974c758e2aecee406f373d7
- Verification: CI run 36097448099
- Uses GLTransaction, source_type=bank_adjustment, central posting/reversal, org-scoped offset validation, locked-period protection, immutable reversal, reconciliation visibility.

# Bank Feed

COMPLETE/VERIFIED.

Implementation:
- 1c1e3128429c0ca0e48bfe053c1fb81b33947b99 — durable CSV import/matching backend
- cbedb3f015cf71d8881b77972afce6b055cffc78 — customer import workflow
- b655d3274644ea515fb34b1f5bb9c66ae9d7878a — schema checkpoint expectations

Key files:
- backend/app/models/bank_feed.py
- backend/app/schemas/bank_feed.py
- backend/app/services/bank_feed.py
- backend/app/routers/bank_feed.py
- backend/alembic/versions/a4b6c8d0e2f1_bank_feed_transactions.py
- backend/tests/test_bank_feed.py
- frontend/src/lib/bankFeed.ts
- frontend/src/app/dashboard/accounting/bank-accounts/[id]/bank-feed/page.tsx

Design contract:
- provider-neutral durable inbox
- manual CSV import in Phase 3.6; Plaid/provider connectivity stays Phase 8
- duplicate protection via external IDs or normalized occurrence hashes
- exact unique date+amount matching to reconciliation-equivalent bank activity
- durable matched source identity; unmatched rows can be rematched
- import/rematch do not create, modify, or reverse GL transactions
- release.accounting.bank_feed + bank_feeds entitlement + ACCOUNTING.BANK_ACCOUNTS remain authoritative

Closeout metadata commits:
- 52fe05a7433e0032c2f1113efad6201bfadcadfd — FEATURE_REGISTRY
- d3a94ac8dcb33637b91b10fd1da397f6bc4b9404 — parity JSON
- 4400e4cafb5c3cdb0759f724dc8c9b2c53caaab8 — FILE_CATALOG locator
- 8991512adb9a12e0c8581eecab4aabce5856a909 — PROJECT_MASTER advance to Owners

# Owner ACH Setup — COMPLETE / VERIFIED

Verified in hosted CI run 36100394485:
- Backend: 302 passed, 3 deselected
- E2E: 3 passed
- Frontend: SUCCESS
- Platform admin: SUCCESS
- Security: SUCCESS
- PostgreSQL backup/restore: SUCCESS
- Staging: SUCCESS
- Parity/registry consistency: CLEAN
- Secret-pattern scan: CLEAN

Backend:
- backend/app/models/owner_ach.py
- backend/app/schemas/owner_ach.py
- backend/app/services/owner_ach.py
- backend/app/routers/owner_ach.py
- backend/alembic/versions/b6d8f0a2c4e7_owner_ach_accounts.py
- backend/tests/test_owner_ach.py
- backend/init_db.py
- backend/app/main.py
- backend/app/constants/organization_features.py
- migration checkpoint tests advanced to b6d8f0a2c4e7 / 91 model tables

Frontend:
- frontend/src/lib/ownerAch.ts
- frontend/src/app/dashboard/accounting/owners/[id]/ach/page.tsx
- owner detail links to ACH setup when release.accounting.owner_ach_setup is enabled

Security / behavior:
- no duplicate owner identity model; owner_id references existing User(role=OWNER)
- unique one ACH configuration per organization + owner
- full account numbers are never returned by the read API
- ABA routing reuses the verified ACH validator
- ADMIN may manage same-org owners
- OWNER may manage self only
- MANAGER and other-owner access is denied
- setup changes create no payment and no GL entry
- release.accounting.owner_ach_setup uses ach_payments + PEOPLE.OWNERS
- gate is registered in FEATURE_REGISTRY so normal release-gate seeding can discover it

Verification checkpoint:
- 3e1b273af6d82fcb9488a0d9cb18d32610450db6
- CI run 36100394485: SUCCESS
- TESTS NOT RUN locally in this connector-only session.

# $0 ACH Test File — Current Batch

Implementation is on the branch and awaiting hosted CI verification.

Backend:
- backend/app/schemas/ach_file.py: ACHTestFileIn / ACHTestFileOut
- backend/app/services/ach_file.py: CSV zero-dollar test row + NACHA prenote generation
- backend/app/routers/owner_ach.py: gated owner test-file endpoint
- backend/tests/test_ach_test_file.py: CSV/NACHA/validation coverage

Frontend:
- frontend/src/lib/ownerAch.ts: typed test-file API
- frontend/src/app/dashboard/accounting/owners/[id]/ach/page.tsx: source-bank selection and download workflow

Behavior:
- release.accounting.ach_test_file remains independently gated
- uses configured source BankAccount and enabled OwnerACHAccount in the same organization
- ADMIN or owner-self scope is preserved
- CSV output carries amount 0.00
- NACHA uses credit prenote transaction codes 23 (checking) / 33 (savings) with a zero amount
- company_id is required for NACHA
- generation does not create a payment, GL transaction, or GL entry
- no schema migration is required; head remains b6d8f0a2c4e7 / 91 model tables

Verification:
- Hosted CI on the final batch checkpoint is pending.
- TESTS NOT RUN locally in this connector-only session.

# Next: $0 ACH Test File

Locked order from PROJECT_MASTER:
1. $0 ACH Test File
2. Owner Held Security Deposits
3. Continue remaining Phase 3.6 items in PROJECT_MASTER order

Known existing contracts to preserve:
- Owners are customer-side User rows with role OWNER, scoped by organization_id.
- Owner ACH should not create a duplicate owner identity model.
- Reuse verified ACH validation/generation behavior where appropriate.
- Backend authorization is authoritative; UI hiding is never security.
- Release, entitlement, org-config, permission, and user preference layers remain separate.
- Never write financial GL state directly; use central accounting/posting services.
- Never use Alembic autogenerate.

# Working Rules

- Work only on chatgpt/checkpoint-005-safety.
- Never touch main.
- Never create or switch branches.
- Inspect real source before editing.
- Fix CI reds autonomously.
- Keep AI_HANDOFF.md current after every meaningful batch.
- Use real test numbers only.
- If tests did not run, say TESTS NOT RUN.
- Do not stop at phase boundaries.
- Stop only for a true blocker that cannot be resolved.
