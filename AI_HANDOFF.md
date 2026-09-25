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
- Bank Accounts subsection is COMPLETE through Bank Feed import.
- Owner ACH Setup, $0 ACH Test File, and Owner Held Security Deposits are COMPLETE/VERIFIED.
- Next ordered item: Management Fees — Pay Owners flow.

# Latest Verified Green Checkpoint

Owner Held Security Deposits checkpoint:
- b234e308f05a43e88b1a3ac670374a8600cf976e
- "CI: advance schema checkpoint expectations"

Hosted CI:
- Run 36103471013: SUCCESS
- Backend: 310 passed, 3 deselected, 2322 warnings in 51.75s
- E2E: 3 passed in 12.82s
- Frontend: SUCCESS
- Platform admin: SUCCESS
- Security: SUCCESS
- PostgreSQL bootstrap + backup/restore: SUCCESS
- Staging build/start/health: SUCCESS
- Parity/registry consistency: CLEAN
- Secret-pattern scan: CLEAN

Current parity source-of-truth:
- total_items: 628
- built_count: 240
- scheduled_count: 388
- in_progress_count: 0
- migration_head: c1e3a5d7f9b2
- expected model-table count: 92

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

# $0 ACH Test File — COMPLETE / VERIFIED

Implementation is verified on the branch.

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
- CI run 36101023004 attempt 1 had a transient Playwright login-navigation timeout only; backend/frontend/security/staging all passed.
- Re-running the failed E2E job produced attempt 2 SUCCESS.
- Backend: 305 passed, 3 deselected, 2239 warnings in 44.50s.
- E2E: 3 passed in 11.96s.
- Frontend, platform-admin, security, PostgreSQL backup/restore, staging, parity/registry consistency, and secret scan: SUCCESS.
- TESTS NOT RUN locally in this connector-only session.

# Owner Held Security Deposits — COMPLETE / VERIFIED

Implementation:
- 73e657fac05d4e3afb4c935c2b62c2caeb8bbf5d — feature implementation
- b234e308f05a43e88b1a3ac670374a8600cf976e — schema checkpoint guards

Design:
- reuses custom GL Accounts for the liability-account setup
- adds an org-scoped AccountingKeyAccount registry for deposit liability choices
- validates owner-held deposit accounts as active LIABILITY accounts offset to the org's Operating Cash GL
- rejects accounts subject to management fees or included on cash flow
- stores the selected approved deposit account on the Lease for move-in use
- customer page configures Key Accounts and assigns the account/amount to a lease
- no new GL posting path is introduced; existing receipt posting remains authoritative

Schema:
- new table accounting_key_accounts
- new leases.security_deposit_gl_account_id
- migration head c1e3a5d7f9b2
- expected model tables 92

Verification:
- Hosted CI run 36103471013: SUCCESS.
- Backend: 310 passed, 3 deselected, 2322 warnings in 51.75s.
- E2E: 3 passed in 12.82s.
- Frontend, platform-admin, security, PostgreSQL bootstrap/backup/restore, staging, parity/registry consistency, and secret scan: SUCCESS.
- Owner Held Security Deposits regression coverage remains included in the green backend suite.
- TESTS NOT RUN locally in this connector-only session.

# Next: Management Fees — Pay Owners flow

Locked order from PROJECT_MASTER:
1. Pay Owners flow
2. Overcollection strategy setting
3. Post GPR
4. Management Fee Exclusions list
5. Continue remaining Phase 3.6 items in Section 38 order

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
