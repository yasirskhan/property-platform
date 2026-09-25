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
- Management Fees — Pay Owners is COMPLETE/VERIFIED.
- Management Fees — Overcollection Strategy is COMPLETE/VERIFIED.
- Management Fees — Post GPR is COMPLETE/VERIFIED.
- Management Fee Exclusions is COMPLETE/VERIFIED.
- Diagnostics — Auto-fix Refund Negative Diagnostic is COMPLETE/VERIFIED.
- Diagnostics — Bank Reconciliation Lapses 60-day check is COMPLETE/VERIFIED.
- Diagnostics — Real Positive Fee check (must_clear) is COMPLETE/VERIFIED.
- Diagnostics — Additional checks to reach 9 total is COMPLETE/VERIFIED.
- Owner Statements — Required Reserves + Prepaid Rent + Property Cash Summary is COMPLETE/VERIFIED.
- Owner Packets — Customizer fields is COMPLETE/VERIFIED.
- Current batch: Settings — Accounting Settings (Key Accounts, GPR, Receipts, Checks, Reports). IMPLEMENTATION PREPARED; CI pending.

# Latest Verified Green Checkpoint

Owner Packet customizer checkpoint:
- 825a3eaef5834a8c3dcc08550cc7d409445add62
- "Phase 3.6: add owner packet customizer settings"

Hosted CI:
- Run 36200032326: SUCCESS
- Backend: 344 passed, 3 deselected, 2799 warnings in 55.94s
- E2E: 3 passed in 8.50s
- Frontend: SUCCESS
- Platform admin: SUCCESS
- Security: SUCCESS
- PostgreSQL bootstrap + backup/restore: SUCCESS
- Staging build/start/health: SUCCESS
- Parity/registry consistency: CLEAN
- Secret-pattern scan: CLEAN

Current parity source-of-truth:
- total_items: 628
- built_count: 252
- scheduled_count: 376
- in_progress_count: 0
- migration_head: a6c8e0f2b4d7
- expected model-table count: 94

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

# Pay Owners — COMPLETE / VERIFIED

Implementation is verified on the branch.

Backend:
- durable owner_payouts table; migration head d3f5a7c9e1b4; expected model-table count 93
- preview uses the existing org-scoped owner sub-ledger and source-bank GL book balance
- owner ACH readiness is checked, but only masked destination last4 is exposed or stored on payout history
- only ADMIN/MANAGER can prepare or confirm payouts
- Pay Owners remains behind release.accounting.pay_owners + owner_payouts entitlement + ACCOUNTING.MANAGEMENT_FEES
- draft creation validates positive owner balances, enabled ACH destinations, duplicate owners, and source-bank book balance
- creating a draft does not move funds and does not post the GL
- after staff confirms a payment was completed externally, the accounting step posts OWNER_DRAW through central post_transaction()
- external confirmation debits GL 2401 Owner Funds and credits the configured operating-bank cash GL; only the cash line carries owner_id so the owner sub-ledger is reduced once
- an already-confirmed batch cannot be confirmed twice
- no automatic ACH payment transmission or payout-file creation is wired into this flow

Frontend:
- live Pay Owners link replaces the compatibility placeholder for ADMIN/MANAGER
- new page previews owner balances and masked ACH readiness, creates reviewable drafts, shows history, and requires an explicit human confirmation before accounting is posted
- the confirmation copy states that the app does not move funds

Verification:
- regression coverage: backend/tests/test_owner_payouts.py
- PostgreSQL/prepare-database guards advanced to d3f5a7c9e1b4 / 93 model tables
- TESTS NOT RUN locally in this connector-only session.
- Hosted CI run 36108140538 stopped at parity/registry consistency before backend tests because FEATURE_REGISTRY used a non-canonical 🟨 status marker for Pay Owners. Corrected to the canonical ⬜ marker in df09d8a53e9ac1ec0699b28a30d0dad90c6f2ecb.
- Hosted CI run 36181435831 reached the backend suite: 313 passed, 3 deselected, 3 failed. Two failures were stale test_migrations.py schema-head/table-count guards; the third was a missing-ACH regression fixture whose owner had no positive balance, so validation correctly failed earlier.
- CI guard/fixture corrections landed in 81cc4ae9466af243d8aff2e6881fe20a71d7e654.
- Hosted CI run 36181749221: SUCCESS.
- Backend: 316 passed, 3 deselected, 2479 warnings in 42.42s.
- E2E: 3 passed in 12.66s.
- Frontend, platform-admin, security, PostgreSQL bootstrap/backup/restore, staging, parity/registry consistency, and secret scan: SUCCESS.

# Overcollection Strategy — COMPLETE / VERIFIED

Implementation:
- Organization.management_fee_overcollection_strategy stores the org policy.
- Allowed values: CREDITS_THEN_RECEIPTS and RECEIPTS_THEN_CREDITS.
- CREDITS_THEN_RECEIPTS is the default/recommended setting.
- GET/PUT /api/accounting/management-fees/overcollection-strategy are protected by ACCOUNTING.MANAGEMENT_FEES plus release.accounting.management_fees.overcollection.
- Updates append an immutable audit-log record.
- Customer workflow: /dashboard/accounting/management-fees/overcollection.
- Migration head e4f6a8c0d2b5; model-table count remains 93.
- Regression coverage: backend/tests/test_management_fee_overcollection.py.
- TESTS NOT RUN locally in this connector-only session.
- Hosted CI run 36184596917: SUCCESS.
- Backend: 320 passed, 3 deselected, 2493 warnings in 52.51s.
- E2E: 3 passed in 12.20s.
- Frontend, platform-admin, security, PostgreSQL bootstrap/backup/restore, staging, parity/registry consistency, and secret scan: SUCCESS.

# Management Fees Post GPR — COMPLETE / VERIFIED

Implementation:
- Independent gate: release.accounting.management_fees.post_gpr.
- Authorization: ACCOUNTING.MANAGEMENT_FEES plus existing ADMIN/OWNER/MANAGER write-role policy.
- Reuses the verified central GPR candidate/posting engine; no duplicate accounting path was introduced.
- Duplicate unit/month protection is shared with Journal Entries Post GPR.
- Customer workflow: /dashboard/accounting/management-fees/post-gpr.
- No schema migration; migration head remains e4f6a8c0d2b5 and model-table count remains 93.
- Regression coverage: backend/tests/test_management_fee_post_gpr.py.
- Hosted CI run 36186643771: SUCCESS.
- Backend: 323 passed, 3 deselected, 2505 warnings in 55.08s.
- E2E: 3 passed in 9.27s.
- Frontend, platform-admin, security, PostgreSQL bootstrap/backup/restore, staging, parity/registry consistency, and secret scan: SUCCESS.
- TESTS NOT RUN locally in this connector-only session.

# Management Fee Exclusions — COMPLETE / VERIFIED

Implementation:
- Read-only audit list over the existing Receipt.exclude_from_mgmt_fee flag.
- Independent gate: release.accounting.management_fees.exclusions.
- Authorization remains ACCOUNTING.MANAGEMENT_FEES; no new mutation path was introduced.
- Source receipt reversals may be included for audit history, while generated reversal mirrors are never listed as source exclusions.
- Organization/date/property filtering is enforced in the backend query.
- Customer workflow: /dashboard/accounting/management-fees/exclusions.
- Posted receipt immutability and the verified fee calculation remain unchanged.
- No schema migration; head remains e4f6a8c0d2b5 / 93 model tables.
- Regression coverage: backend/tests/test_management_fee_exclusions.py.
- TESTS NOT RUN locally in this connector-only session.
- Hosted CI run 36187449354: SUCCESS.
- Backend: 325 passed, 3 deselected, 2539 warnings in 53.64s.
- E2E: 3 passed in 9.38s.
- Frontend, platform-admin, security, PostgreSQL bootstrap/backup/restore, staging, parity/registry consistency, and secret scan: SUCCESS.

# Diagnostics — Auto-fix Refund Negative Diagnostic — COMPLETE / VERIFIED

Implementation:
- Adds independent gate release.accounting.diagnostics.refund_negative.
- GET diagnostics now enforces ACCOUNTING.DIAGNOSTICS server-side.
- Correction is one account at a time and requires ADMIN/OWNER/MANAGER plus the diagnostics permission/gate.
- Only active 44xx INCOME accounts with a real negative balance are eligible.
- The fee account must have an explicit active same-org offset_account; the workflow never guesses a cash/expense/liability account.
- Posts REFUND_NEGATIVE_DIAGNOSTIC through central post_transaction(): debit configured offset, credit fee account for the exact deficit.
- Locked accounting periods and GL posting restrictions remain authoritative.
- Repeating the action after the balance is fixed fails safely because the account is no longer negative.
- Customer diagnostics page exposes the action only behind the release gate and disables it until an offset account is configured.
- No schema migration; head remains e4f6a8c0d2b5 / 93 model tables.
- TESTS NOT RUN locally in this connector-only session.
- Hosted CI run 36189649244: SUCCESS.
- Backend: 329 passed, 3 deselected, 2605 warnings in 54.32s.
- E2E: 3 passed in 8.75s.
- Frontend, platform-admin, security, PostgreSQL bootstrap/backup/restore, staging, parity/registry consistency, and secret scan: SUCCESS.

# Diagnostics — Bank Reconciliation Lapses — COMPLETE / VERIFIED

Implementation:
- Adds a seventh diagnostics check over active organization bank accounts.
- A reconciled account is flagged when its latest RECONCILED statement date is more than 60 days before the report date.
- A never-reconciled account is flagged once the bank account itself is more than 60 days old.
- Exactly 60 days is still within the allowed window.
- Inactive and other-organization bank accounts are excluded.
- Read-only diagnostic only; no GL posting or reconciliation mutation is introduced.
- No schema migration; head remains e4f6a8c0d2b5 / 93 model tables.
- TESTS NOT RUN locally in this connector-only session.
- Hosted CI run 36191470527: SUCCESS.
- Backend: 331 passed, 3 deselected, 2640 warnings in 56.57s.
- E2E: 3 passed in 8.79s.
- Frontend, platform-admin, security, PostgreSQL bootstrap/backup/restore, staging, parity/registry consistency, and secret scan: SUCCESS.

# Diagnostics — Real Positive Fee Check — COMPLETE / VERIFIED

Implementation:
- Replaces the placeholder positive-fee diagnostic with real must_clear-driven balance logic.
- Evaluates only active same-org INCOME accounts explicitly marked must_clear.
- Uses the existing immutable GL as the balance source; no cached balance or mutation path is introduced.
- Positive natural income balances greater than $0.01 are warnings; zero and negative balances pass this check.
- Non-must-clear, inactive, and other-organization accounts are excluded.
- The must_clear model/API/Chart-of-Accounts UI already exists, so no schema migration is required.
- Migration head remains e4f6a8c0d2b5 / 93 model tables.
- TESTS NOT RUN locally in this connector-only session.
- Hosted CI run 36192333662: SUCCESS.
- Backend and all required CI gates passed after the inactive-account fixture correction in a769588935994ea0d588d71779d13d6bb7479792.

# Diagnostics — Additional Checks to Reach 9 Total — COMPLETE / VERIFIED

Implementation:
- Adds Posted GL Transaction Integrity: detects transactions with fewer than two lines, zero-sided totals, or debit/credit differences over one cent.
- Adds Bank Account GL Mapping Health: every active bank account must map to an active same-organization ASSET GL account.
- Both checks are read-only, organization-scoped, and reuse existing ledger/bank data.
- No schema migration; head remains e4f6a8c0d2b5 / 93 model tables.
- Regression coverage: backend/tests/test_diagnostic_integrity.py.
- TESTS NOT RUN locally in this connector-only session.
- Hosted CI run 36196379096: SUCCESS.
- Backend: 336 passed, 3 deselected, 2743 warnings in 55.21s.
- E2E: 3 passed in 9.62s.
- Frontend, platform-admin, security, PostgreSQL bootstrap/backup/restore, staging, parity/registry consistency, and secret scan: SUCCESS.

# Owner Statements — Current Batch

Plan:
- Implement Required Reserves from an explicit durable property-level configuration; do not fabricate a value.
- Compute Prepaid Rent from the existing 2300 Prepayment liability where property-scoped GL entries exist.
- Freeze both values into generated owner-statement property snapshots so later changes do not rewrite historical statements.
- Add a Property Cash Summary derived from the frozen per-property statement values.
- Preserve existing owner-statement permissions, organization isolation, ownership behavior, and frozen-snapshot contract.
- Inspect property configuration and receipt/prepayment source behavior before implementation.
Implementation prepared in this batch:
- Property.required_reserve_amount is the explicit durable non-negative reserve source.
- Owner-statement previews freeze required reserve plus GL 2300 Prepayment natural liability balances per property at period end.
- Frozen property blocks include required_reserves, prepaid_rent, and available_cash.
- Detail totals are derived from frozen property_data for backward-compatible historical snapshots.
- Property Cash Summary is served by a dedicated backend endpoint protected by release.accounting.owner_statements.cash_summary and ACCOUNTING.OWNER_STATEMENTS.
- Property edit exposes Required Owner Reserve; statement preview/detail show real reserve/prepaid/available values.
- Migration head advances to f5a7c9e1b3d6; model-table count remains 93.
- Regression coverage added for frozen reserve/prepaid/cash behavior and feature authorization.
- TESTS NOT RUN locally in this connector-only session.
- Hosted CI run 36197438770: SUCCESS.
- Backend, frontend, E2E, security, PostgreSQL bootstrap/backup/restore, staging, parity/registry consistency, and secret scan: SUCCESS.

# Owner Packets — Current Batch

Implementation prepared:
- Durable organization-level owner packet settings store report selections, email-owner preference, and optional cover message.
- Current selectable reports are Owner Statement and Property Cash Summary; at least one is required.
- GET/PUT configuration is protected by release.owner_portal.packet_customizer plus ACCOUNTING.OWNER_STATEMENTS.
- Only ADMIN/MANAGER may change organization-wide packet settings; OWNER cannot change global configuration.
- Customer workflow replaces the compatibility placeholder with /dashboard/accounting/owner-statements/packet-settings.
- This batch stores customization only; packet generation/sending remains Phase 3.7.
- Migration head advances to a6c8e0f2b4d7; expected model-table count 94.
- Regression coverage added in backend/tests/test_owner_packet_settings.py.
- TESTS NOT RUN locally in this connector-only session.
- Hosted CI run 36200032326: SUCCESS.
- Backend: 344 passed, 3 deselected, 2799 warnings in 55.94s.
- E2E: 3 passed in 8.50s.
- Frontend, platform-admin, security, PostgreSQL bootstrap/backup/restore, staging, parity/registry consistency, and secret scan: SUCCESS.

# Next Work

Locked order from PROJECT_MASTER:
1. Settings — Accounting Settings (Key Accounts, GPR, Receipts, Checks, Reports)
2. Settings — Accounting Basis toggle (Accrual default | Cash), report layer only
3. Settings — My Settings
4. Settings — Auditing Center
5. Settings — Two-step verification
6. Settings — Login history
7. Universal — delete_reason UI
8. Universal — Notes expansion
9. Universal — Audit Log expansion
10. Continue into Phase 3.7 without stopping at the phase boundary

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


# Accounting Settings — Current Batch

Implementation prepared:
- New org-scoped AccountingSettings row stores optional GPR account overrides, optional default receipt cash account, report export format, and fiscal-year start month.
- GPR posting preserves verified standard 4100/4115/4120 behavior when no override exists; configured overrides must be active same-org INCOME accounts.
- Receipt posting preserves explicit receipt selections and existing Automatic bank/1150 fallback; an org default only participates when explicitly configured and must be an active same-org ASSET account.
- Key Accounts are read from the existing accounting_key_accounts source; no duplicate key-account storage.
- Check Writing is summarized from existing BankAccount/BankCheckSetup rows and links to the verified per-bank Check Setup workflow; no duplicate check configuration.
- Management-fee overcollection remains in its existing verified workflow and is linked, not duplicated.
- New backend route: GET/PUT /api/settings/accounting.
- New customer route: /dashboard/settings/accounting.
- New menu key SETTINGS.ACCOUNTING is release-gated by release.settings.accounting; default visibility is ADMIN/OWNER only.
- Organization-wide writes are ADMIN/OWNER only and append immutable audit history.
- FEATURE_REGISTRY permission is finalized as SETTINGS.ACCOUNTING.
- Accounting Basis is intentionally NOT included here; it remains the next separate report-layer batch.
- Migration head advances to b7d9f1a3c5e8; expected model-table count 95.
- Regression coverage added in backend/tests/test_accounting_settings.py.
- TESTS NOT RUN locally in this connector-only session.
- Hosted CI verification pending.
