# PROJECT MASTER

**Property Management Platform (AppFolio-equivalent)**
**Single source of truth for the project.**
**Last updated: 2026-09-24**

---

# ═══════════════════════════════════════════════════
# PART A — CURRENT STATE

## A1. WHERE WE ARE RIGHT NOW

**Current activity:** Phase **3.6 — Accounting Polish: Bills** is IN PROGRESS. Chart of Accounts, Journal Entries, Receipts, the Bills lifecycle, Recurring Bills/Credits, Post Codes, Manually Post Bills, and Vendor Credits are verified. The next unfinished ordered Bills subsection is Write Checks / Checks.

**GitHub working state:** draft PR #2 from `chatgpt/checkpoint-005-safety` into `main`. `main` remains untouched until Yasir explicitly approves a merge.

**Verified in hosted GitHub CI on 2026-09-23:**
- Python 3.12 backend suite against PostgreSQL 16;
- parity/registry consistency and committed-secret scan;
- frontend `npm ci`, lint, TypeScript, and production build;
- fresh PostgreSQL bootstrap and deterministic E2E seed;
- PostgreSQL `pg_dump` / restore verification;
- authenticated Playwright login + Dashboard / Properties / Receipts / Bills;
- staging Compose rendering, backend/frontend image builds, live stack startup, backend `/health`, and frontend `/login` in CI run 35916148970.

**Real defects found and fixed by the safety gate:**
- E2E seed used a reserved `.test` email domain rejected by Pydantic; changed to a valid example-domain address.
- Playwright waited for `networkidle`, which is unreliable for a live client app; the smoke test now waits for DOM/UI readiness.
- GL reversal posting previously used two financial commits; reversal + original `is_reversed` state now commit atomically with regression coverage.
- Fresh database bootstrap/model registration gaps were corrected and the complete current model registry is guarded by tests.
- Staging initially failed because the PostgreSQL `psycopg` driver was only a dev dependency; it is now a runtime dependency and the live staging smoke passes.

**3.4.S closeout:** COMPLETE. Portable private-repo security checks (Bandit, pip-audit, npm audit, committed-secret scan, Dependabot) replaced the unavailable mandatory CodeQL upload gate and passed in hosted CI run 35917804417. CodeQL remains optional/manual if GitHub Code Security is enabled later.

**Migration head:** `ad3e5f7b9c21`.

**Current parity inventory:** 226 built, 0 in progress, 402 scheduled, 628 total. `check_parity.py CLEAN` means planning consistency; behavioral proof comes from the automated gates.

## A2. WHAT'S BUILT (WORKING)## A2. WHAT'S BUILT (WORKING)

- Sessions 1-17 (auth, properties, units, people, leases, work
  orders, password reset, org email, uploads, team UI, property
  detail tabs, financials, taxes, policies, utilities, insurance,
  expenses, income, tenant insurance, applicant role, screening,
  OCR settings)
- Phase 1 — Menu Permissions System (4-layer gating, full UI)
- Phase 2 Step 1 — Chart of Accounts (61 accounts, CRUD, UI)
- Phase 2 Step 2 — General Ledger
- Phase 2 Step 2b — Manual Journal Entry
- Phase 2 Step 4 — Bank Accounts (Client Trust + Security Deposit Trust)
- Phase 2 Step 5 — Receipts (tenant / owner / other + reversal)
- Phase 2 Step 6 — Bills (two-step accrual)
- Phase 2 Step 7 — Bank Deposits
- Phase 2 Step 8a — Owner Sub-Ledger Foundation
- Phase 2 Step 8b — Financial Diagnostics (six checks)
- Phase 2 Step 9 — Management Fees (two-step: creates a Bill)
- Phase 2 Step 10 — Owner Statements (frozen snapshots, print-ready)
- Phase 3 Step 3a — Amenities (fee + availability)
- Phase 3 Step 3b — Appliances (condition)
- Phase 3 Step 3c — Improvements (warranty_expires)
- Phase 3 Step 3d — Photos (upload, cover, marketing, lightbox)
- Phase 3.5 — SETTINGS menu group + Display Settings page +
  Custom Currencies CRUD + per-org currency + Sidebar preferences
  per-user fix
- Phase 3.6 Step 1 — Charges feature (table, model, router,
  list page, new page, menu key)

## A3. TECH STACK

Backend:
- Python 3.12 + FastAPI
- SQLAlchemy ORM
- SQLite (dev) -> PostgreSQL (production on AWS RDS)
- Alembic for migrations (hand-written only, never autogenerate)
- JWT auth, bcrypt==4.0.1 (pinned)

Frontend (web):
- Next.js 16.3.5 (App Router, Turbopack in dev)
- React 19, TypeScript, Tailwind CSS
- lucide-react, @dnd-kit

Frontend (mobile — Phase 12, planned):
- React Native / Expo

Environment:
- Windows 11, PowerShell, VS Code
- Node v24.19.0, npm 11.17.0

Deployment target (Phase 11):
- AWS (Lightsail + RDS Postgres for launch; migrate to ECS Fargate later)
- S3 for file uploads
- CloudFront for CDN

## A4. WORKING RULES

1. User is a non-coder. Never ask them to write code. Give whole files, not fragments.
2. Every command must be labelled BACKEND or FRONTEND.
3. Every file must be given whole. Never "add this line."
4. User runs commands and reports back. If error, they paste it.
5. One step at a time. Never give 5 steps at once.
6. Backend commands from C:\Projects\property-platform\backend. Venv is at backend\venv (NOT .venv). Activate: .\venv\Scripts\Activate.ps1
7. Frontend commands from C:\Projects\property-platform\frontend.
8. Test accounts (all use test1234):
   - admin@test.com (ADMIN)
   - owner1@test.com (OWNER)
   - manager1@test.com (MANAGER)
   - crew1@test.com (CREW)
   - tenant1@test.com (TENANT)
9. Never use Alembic autogenerate. Write migrations by hand.
10. Back up DB before risky migrations. DB is property_platform.db.
11. Role values are UPPERCASE. Menu keys are UPPERCASE and dotted.
12. If Next.js 404s on pages that exist, check for stray frontend\app folder.
13. Every GL posting goes through post_transaction(). Never write to GL tables directly.
14. GL account seed count: 61 per org (60 original + 2100 AP added in Step 6).
15. `push.bat` on the desktop is the one-click way to save to GitHub.
16. Every new page uses shared primitives and the Hybrid Capability Gating rules. Gate independently releasable capabilities, not routine fields/columns/filters. Backend authorization remains authoritative. See Sections 67, 70, 79, and 80.

## A5. CURRENT OPEN DECISIONS

- Auto-description rules for Receipt lines: rent rows get
  "{Month} rent", fee rows get "{Fee} — {tenant}". Revisit later.
- Bill auto-description: not yet built.
- Reverse confirmation uses styled modal on Amenities/Appliances/
  Improvements. Still window.confirm() on Receipts/Bills/etc. Roll
  out styled modal everywhere during Phase 3.5.5.
- Back-navigation: Trial Balance and Deposits have smart-back.
  Roll out to Receipts/Bills/GL Accounts during Phase 3.5.5.
- Mobile: desktop-first for manager app; portals mobile-first
  (Phase 7); native app = Phase 12.
- Bank Deposits do NOT post to the GL. If we later add a "cash on
  hand" GL account, add DR Bank / CR Cash on Hand in create_deposit().
- Diagnostics currently detect only. Auto-fix postings deferred
  to Phase 3.6.
- Currencies Display dropdown is API-backed and verified in Phase 3.4.23.
- Display settings theme/density/font/accent/reduce-motion consumption is being completed in Phase 3.4.24; number-format rendering remains deferred until the formatter consumes it.
- Section 12 says 61 GL accounts; header comment in gl_account.py
  still says 57. Fix in the next cleanup pass.

# ═══════════════════════════════════════════════════
# PART B — NEXT ACTION
# ═══════════════════════════════════════════════════

## B1. IMMEDIATE NEXT ACTION

**Continue Phase 3.6 — Accounting Polish: Write Checks / Checks.**

1. Recurring Bills/Credits, Post Codes, Manually Post Bills, and positive-value Vendor Credits are VERIFIED in CI run 36083621549. Backend: 280 passed, 3 deselected. E2E: 3 passed. Continue with Write Checks (Find Bills -> Confirm & Finalize -> Print), then Checks list, Void Check, and Check Memo.
2. Preserve verified two-step accrual, partial payment, reversal, organization isolation, locked-period behavior, recurring posting idempotency, and central post_transaction() accounting contracts.
3. Keep release control, entitlement, org configuration, role permission, and user preference independent where applicable; backend authorization remains authoritative.
4. Verify in hosted CI, fix reds autonomously, update checkpoint/planning state, then continue to the next Phase 3.6 subsection without stopping.

## B2. AFTER THAT## B2. AFTER THAT (Phase 3.5 onward)

See Section 38 for the full build order including:
- Phase 3.5 — Property Detail Polish
- Phase 3.5.5 — Compliance Pass (retrofit existing pages)
- Phase 3.6 — Accounting Polish
- Phase 3.7 — Reports + Universal Attachments
- Phase 4 — Vendors
- Phase 4.5 — Compliance (HOA / Affordable / Commercial / RUBs)
- Phases 5-12 (Smart Maintenance, Messaging, Portals, Integrations,
  Internal Team, Billing, Production, Mobile)

## B3. AFTER PHASE 3

See Section 38.

## B4. HOW TO RESUME IN A NEW CHAT

Paste this to any new assistant:

I'm continuing to build a property management platform (AppFolio clone).

Read this PROJECT_MASTER.md file fully. It has three parts:
- Part A: Current state
- Part B: Next action
- Part C: Full reference

Then continue from the immediate next action listed in Part B1.

Rules you must follow:
- I am a non-coder. Never ask me to write code.
- Give whole files, not fragments. I select-all, delete, paste, save.
- Label every command BACKEND or FRONTEND with a colored square.
- One step at a time. Wait for me to run and report back.
- If I paste an error, fix it and give the next command.
- Backend venv is at backend\venv (not .venv). DB is property_platform.db.
- Role values are UPPERCASE. Menu keys are UPPERCASE and dotted.
- Every GL posting goes through post_transaction().
- Every new page uses money() / date() / useDisplay() and gates
  future features behind flags. See Section 67 close-out rules.

Then paste this entire file.

# END OF PART A + PART B
# ═══════════════════════════════════════════════════
# PART C — FULL REFERENCE
# ═══════════════════════════════════════════════════

# SECTION 1 — PROJECT IDENTITY

Goal: Build a property management SaaS functionally equivalent to
AppFolio, with our own code.

Owner: Yasir (non-coder, Windows 11)
Location: C:\Projects\property-platform\
Working style: Module-by-module. Assistant writes whole files. User
pastes into VS Code, runs commands, reports back.
Key principle: The chat is disposable. Everything on disk is permanent.

---

# SECTION 2 — SYSTEM ARCHITECTURE

Three sides:

1. CUSTOMER SIDE — what customers log into (Admin/Owner/Manager/Crew/
   Tenant/Vendor/Applicant). Their properties, leases, accounting,
   maintenance, messaging. Own subdomain.

2. INTERNAL SIDE (ours) — Sales / Billing / Tech / Support / Dev.
   admin.yourcompany.com

3. PUBLIC SIDE — tenant-facing listing pages, applications, portal
   access links. No login for listings.

Six isolation levels:
- Level 6 — Platform Support (us). Isolated from all customers.
- Level 5 — Buyer (admin or top-level owner). Controls entire account.
- Level 4 — Owners, Managers, Internal Staff. Scoped by assignment.
- Level 3 — Crew, Vendors, Vendor Crew. See only assigned work orders.
- Level 2 — Tenants. See only own unit and lease.
- Level 1 — Applicants. See only own application.

No level sees another. No customer sees another. Support sees customer
data only via granted access.

---

# SECTION 3 — DEPLOYMENT MODES

Mode 1 — PM Company: management company owns the account, property
owners are clients.
Mode 2 — Single Owner: one owner buys the system, Owner = top-level.
Mode 3 — Multi-Owner: one account, multiple landlords, each owner has
own properties + managers, Owner A cannot see Owner B's data.

Customer types: Landlord (single), Multi-Property Landlord, Management
Company, Firm/Brokerage, HOA (later), Enterprise (custom).

---

# SECTION 4 — USER ROLES

Customer-side (all org-scoped):
- ADMIN — boss of their OWN customer company. Cannot see other
  companies. Cannot see our internal tools.
- OWNER, MANAGER, CREW, TENANT
- VENDOR, VENDOR_CREW
- APPLICANT

Internal-side (ours — SEPARATE platform_users table, Phase 9):
- platform_admin, platform_sales, platform_billing, platform_tech,
  platform_support, platform_dev

Lifecycle: Sales -> Billing -> Tech -> Support -> (Dev for bugs).

Hard rule: Customer users and platform_users NEVER mix.

NOTE on AppFolio's role model: The Manager Guide (PDF p.97) describes
eight roles from President (full access) down to View Only. Our model
(ADMIN, OWNER, MANAGER, CREW, TENANT, VENDOR, VENDOR_CREW, APPLICANT)
is functionally equivalent but structured for a multi-tenant SaaS
instead of a single-company install. No change planned.

---

# SECTION 5 — NAVIGATION STRUCTURE

Customer sidebar (10 items):
DASHBOARD, CALENDAR, LEASING, PROPERTIES, PEOPLE, ACCOUNTING,
MAINTENANCE, REPORTING, COMMUNICATION, WHAT'S NEW

Sub-items:
- Leasing: Listings, Applications, CRM, Lease Templates
- Properties: All Properties, Add Property, Units, Property Groups
- People: Team, Tenants, Owners, Vendors, Contacts
- Accounting: Receipts, Bills, Bank Accounts, Journal Entries,
  Bank Transfers, GL Accounts, Diagnostics, Online Payments
- Maintenance: Work Orders, Recurring, Inspections, Unit Turns,
  Projects, Purchase Orders, Inventory, Fixed Assets, Smart Maintenance
- Reporting: All reports + custom report builder
- Communication: Inbox, Messages, Templates, Surveys

Layout: Sidebar (220px) + Content + Right panel (280px, hidden by default).
Top bar (blue): Search | Add Functionality | Help & Training | User menu.
Sidebar customization: driven by Menu Permissions (Section 42).

NOTE: AppFolio's Manager Guide (PDF p.6) lists Vacancies as a
top-level tab alongside Properties, People, Accounting, Reports.
We place Vacancies under Leasing -> Listings. Functionally equivalent,
different information architecture. See Section 18.

---

# SECTION 6 — PAGE STRUCTURE PATTERNS

List pages: header + primary action, filters, table, inline Edit,
pagination, right panel.
Detail pages: header + Edit + Delete, tabs, right panel.
Form pages: label above field, required *, Save/Cancel, inline validation.
Modal pattern (Bills, Receipts): dark backdrop, centered card,
click-outside to close, max-w-2xl, max-h-90vh.

---

# SECTION 7 — UI STYLE GUIDE

Colors:
- Top bar: #1e5aa8
- Left sidebar: #1e2a3a
- Sidebar active item / Primary button: #2c7be5
- Section headers: Blue
- Background: White / very light gray
- Table header: #f5f5f5
- Right panel: #fafafa
- Text: #333
- Border: #e0e0e0

Status ribbons: Cancelled RED, Completed GREEN, Pending YELLOW,
In Progress BLUE, Default GREEN pill.

Typography: Page title dark navy bold ~20-24px, section header bold
~16-18px, body dark gray ~14px, labels lighter gray ~12-13px.

Layout: padding 20-24px inside cards, 40-60px around content, row
height ~40px, gap ~24px, border-radius 4-6px, buttons ~36px tall.

Icons: lucide-react, line icons.

---

# SECTION 8 — UNIVERSAL PATTERNS (every entity)

1. Notes — free text, timestamped
2. Attachments — with Share with Tenants/Owners option
3. Audit Log — every change tracked
4. Soft delete — is_active = false
5. Created by / Created at
6. Updated by / Updated at

---

# SECTION 9 — THE 5-LAYER MENU GATING (BUILT)

NOTE (2026-09-22): The gating stack was extended from 4 to 5 layers.
The original 4 layers stay exactly as they were. A new Platform layer
was added on top as Layer 1. See Section 80 (Platform Feature Gating)
for the full four-stage platform model (HIDDEN / BETA / ROLLOUT /
ALL_ORGS).

Layer 1 — Platform stage (BUILT as part of Section 80's design, wired
in Phase 9). Controls whether a menu key is live at all on our end.
Stages: HIDDEN (invisible to all orgs), BETA (visible only to specific
pilot orgs), ROLLOUT (visible only to specific orgs, growing set),
ALL_ORGS (visible to every org). This is our top-level switch.
Layer 2 — Plan gating: STUBBED (always allows). Wires to subscriptions
in Phase 10.
Layer 3 — Role gating: menu_permissions table.
Layer 4 — User overrides: user_permissions table.
Layer 5 — Personal hiding: sidebar_preferences (per-user).

All 5 must pass. If any fails -> hidden.

Hard rules:
- Layers 3, 4, 5 can only SUBTRACT visibility. Layers 1 and 2 can
  grant or deny (they are top-level gates we control).
- ADMIN role is immutable.
- Parent hidden -> all children hidden.
- Case-insensitive role comparison.
- Every permission change writes to audit_log.
- Every menu key carries a platform stage. Default for anything new
  is HIDDEN until we advance it.

---

# SECTION 10 — DATABASE

Tables (~45):
Core: organizations, users, audit_log, platform_settings, sidebar_preferences
Menu Permissions: menu_permissions, user_permissions
Accounting: gl_accounts, gl_transactions, gl_entries, receipts,
  receipt_lines, bills, bill_lines, deposits, deposit_lines
Ownership: property_owners (join table for co-ownership)
Fees: management_fee_runs (one row per property per fee period)
Statements: owner_statements (frozen snapshot documents)
Banking: bank_accounts (physical accounts mapped to GL cash)
JE: (no new table — manual JEs use gl_transactions
  with transaction_type=JOURNAL_ENTRY, source_type=manual_je)
Properties: properties, units, property_assignments, property_taxes,
property_amenities, property_appliances, property_improvements,
property_photos,
property_tax_payments, property_utilities, utility_bills,
trash_pickup_schedule, property_insurance, property_expenses,
property_income
Leases: leases, rent_invoices, payments
Work Orders: work_orders, work_order_updates
Auth: password_reset_tokens
Settings: organization_email_settings
Screening: screening_providers, organization_screening_settings
Applications: lease_applications, application_payments, tenant_insurance

Rules: id PK, organization_id for multi-tenancy, created_at/updated_at,
soft delete, cascade FKs, JSON for lists.

organizations.state: ACTIVE | PAST_DUE | RESTRICTED | SUSPENDED |
CANCELLED. Not enforced yet (Phase 10).

---

# SECTION 11 — MIGRATION STRATEGY

Commands:
  alembic revision -m "description"
  alembic upgrade head

Never autogenerate on existing tables. Write by hand.

Chain:
- 660bc48a3454_baseline
- 1d77e94a0fb5_add_sidebar_preferences_table
- 8a3f2c1e9b44_add_menu_permissions_system
- 9f4b7c1a2d55_org_state_and_backfill_orgless_users
- a1c4e8f9b2d3_add_gl_accounts_and_seed
- b2d5f9e1c3a7_add_gl_transactions_and_gl_entries
- 64dec42acecf_add_receipts_and_receipt_lines
- 71eda8a9ba77_add_bills_and_bill_lines_and_ap_account
- e266f7c76a7c_add_deposits_and_deposit_lines
- 3b50fb7fd91a_add_owner_id_to_receipts_bills_gl_entries
- bdc8b2be19d9_add_property_owners_and_ownership
- 0cf6edacce77_add_management_fee_runs_and_property_fee_fields
- 4aa1c77e213c_add_owner_statements
- 7ca4251074bc_add_bank_accounts
- e5d4a58b8e85_add_property_amenities
- dadbb391cc03_add_property_appliances
- 35529ce17750_add_property_improvements
- 59a25b856f18_add_phase3_parity_fields
- 00bc0d143eac_add_property_photos
- 8c2e766863c0_add_org_currency                 (organizations.currency)
- 521035d0e411_add_user_display_preferences     (user_display_preferences table)
- 15d92d8a1eea_add_settings_menu_keys           (SETTINGS.* menu seeds)
- 8e1243432666_add_currencies_table             (currencies table + 9 seeds)
- f49b93dcb1e2_add_charges_table                (charges table)
- 3909fd7c7792_add_charges_menu_key             (ACCOUNTING.CHARGES)
- c0e4ac6f46b2_sidebar_pref_user_id_not_null    (user_id NOT NULL)
- 5949df11e460_drop_unique_org_index_sidebar    <- HEAD

---

# SECTION 12 — THE 61 GL ACCOUNTS

1xxx Assets (8): 1150 Rental Trust, 1160 Security Deposit Cash,
1300 Accounts Receivable, 1610 Land, 1710 Buildings, 1720 Accumulated
Depreciation, 1810 Other Assets, 1820 Other Depreciation

2xxx Liabilities (5): 2100 Accounts Payable (added Step 6),
2101 Security Deposits, 2300 Prepayment, 2401 Owner Funds, 2600 Mortgage

4xxx Income (26): 4100 Rent, 4105 Section 8, 4110 Month-to-Month,
4115 Gross Potential Rent, 4120 Loss/Gain, 4210 Concessions, 4405 NSF,
4415 Pet Fee (deprecated), 4416 Pet Fee, 4420 Application Fee,
4425 Insurance, 4430 Late Fee, 4435 Utility, 4440 Violation,
4445 Default, 4450 MRA, 4455 Lease Initiation, 4457 Renewal Fee,
4460 Eviction, 4465 Notice, 4470 Early Termination, 4478 RBP,
4480 PM Charge, 4483 Utility Reduction, 4490 Option Consideration,
4805 PM Charge

6xxx Expenses (22): 6001 Management Fees, 6005 Leasing Fee,
6015 Vendor Discounts, 6025 Unknown, 6074 Landscaping, 6076 Cleaning,
6091 Insurance, 6121 Mortgage, 6144 HVAC, 6171 Electric, 6173 Water,
6174 Sewer, 6175 Garbage, 6176 Cable, 6192 Bank Fees, 6215 Water
(RUBs), 6852 Plumbing, 6855 HVAC, 6858 Rekey, 6865 Electrical

8xxx Admin (2): 8010 Pest, 8050 Computer

Total: 61 accounts per org (60 original + 2100 AP added by Step 6).

NOTE (2026-09-21): The header comment in app/models/gl_account.py
still says "57" — this is stale. The actual seed count is 61.
Fix the code comment on the next cleanup pass.

---

# SECTION 13 — BANK ACCOUNTS

Two physical: Client Trust (Operating), Security Deposit Trust (Escrow).
Two GL: 1150 Rental Trust, 1160 Security Deposit Cash.
Mapping: 1150 <-> Client Trust, 1160 <-> Security Deposit Trust.

---

# SECTION 14 — KEY CORRELATIONS

$300 Correlation: Maintenance Limit = max spend without approval;
Property Reserve = money held for repairs.

$855.95 Correlation: One Other Receipt -> 4 GL accounts: 4420 ($110),
4455 ($150), 4478 ($45.95), 4416 ($550) = $855.95.

-$110 Correlation: Two $55 app fees refunded -> 4420 went negative ->
Other Receipt cleared to $0 -> Diagnostic passed.

Two-Tier Fee: 9% on Rent Income (4100), 100% on additional fees.

Universal Pattern: Notes + Attachments + Audit Log on every entity.

Reversal Pattern: Original marked "Reversed", new entry marked
"Reversal", net $0.

Management Fee Exclusion: "Exclude from Mgmt Fee" checkbox on Other
Receipts.

---

# SECTION 15 — PROPERTIES MODULE

Property: Name, address, type (SFR/MFR/Condo), year built, renovated,
sq ft, stories, parking, estimated rent, security deposit, ownership
status, policies (pets, smoking, lease terms, renters insurance,
laundry), public description, internal notes, soft delete, audit log.

Unit: number, bed/bath, sq ft, monthly rent, security deposit, pet
deposit, pet rent, application fee, admin fee, available from, lease
term, marketing info, is_listed, is_available, is_active.

Property Detail tabs (12+):
Overview, Units, Photos, Utilities, Insurance, Financials, Taxes,
Policies, Amenities, Appliances, Improvements, Expenses, History

Property Groups: Named groups for filtering, access, reporting.

Budget tab, Map tab.

---

# SECTION 16 — PEOPLE MODULE

Three sub-tabs: Tenants, Owners, Vendors

Tenant: contact, screening, late fee config, lease, charges, notes,
attachments, primary flag, additional tenants.

Owner: contact, tax ID, properties owned (%), payment type (Net/Gross),
ACH bank info, reserve funds, Vendor 1099 Payer, notes, attachments.

Vendor: company, contact, address, insurance + expiration, notes,
attachments.

Tags: everyone can be tagged, searchable, importable.

---

# SECTION 17 — TENANT LIFECYCLE

Move In (5 steps):
1. Profile (Name, Phones, Emails, Move-in Date)
2. Select Unit
3. Lease Details (dates, term, monthly charges, one-time)
4. Schedule Move In (Lease Signed Date, Scheduled Move-In Date)
5. Move In (finalize charges)

Save for Later -> moves to In Progress tab.

Move Out (5 steps):
1. Record Notice (Notice Date, Scheduled Move-Out Date)
2. Forwarding Info
3. Record Move Out (Actual Move-Out Date)
4. Add Charges (final charges + credits)
5. Create Disposition (Print Disposition Letter, Print Envelope)

Renew Lease: Edit tenant -> Lease From + Lease To -> Save.

Increase Rent:
1. Set Increase (Increase Date, New Rent) -> Preview
2. Confirm & Schedule
3. Notify Residents

Convert to Month-to-Month: Edit tenant -> Month To Month checkbox -> Save.

Additional Tenants: Add after Move In via link. Included on letters,
checks, statements.

---

# SECTION 18 — LEASING MODULE

Listings: Post to Craigslist, Company Website, Internet (Oodle). HTML
for website integration. QR codes per property/group.

Applications: online rental app. Required: Name, Email, Phone, Current
Address, Previous Addresses, Personal Info, Financial Info. Fee payment.
Guest cards.

Screening: TransUnion SmartMove, Experian, Equifax. Criteria + Policies.
Report.

Lease Templates: 3-level (Template + Addenda + Attachments). Per-
property or database-wide.

CRM: Track prospects, marketing effectiveness.

---

# SECTION 19 — ACCOUNTING MODULE (the spine)

Top tabs: Receipts | Bills | Bank Accounts | Journal Entries |
Bank Transfers | GL Accounts | Diagnostics | Online Payments |
Management Fees | Owner Statements | Bank Deposits

Chart of Accounts: 61 accounts. Each: GL Number, Name, Type, Sub-account
of, Offset Account, Subject to Mgmt Fees, Include on Cash Flow.

General Ledger: Every transaction posts here. Reversal support. Reports:
GL, Trial Balance, Balance Sheet, Income Statement, Cash Flow.

Receipts — three types:
1. Tenant Receipt — Tenant, Amount, Property, Receipt Date, Check #,
   Cash Account, Remarks + charges table (Account, Date, Description,
   Balance, Amount to Pay, Prepayment).
2. Owner Receipt — Owner, Amount, Property, Receipt Date, GL Account
   (defaults to Owner Contributions), Payer, Check #, Cash Account,
   Remarks.
3. Other Receipt — Received From, Amount, Property, Unit, Receipt Date,
   GL Account, Cash Account, Check #, Remarks + Exclude from Mgmt Fee.

Reverse Receipt: Original date locked, Reversal date editable, reversal
line added, net $0, line-through on list.

Process NSF: NSF Date, Bank Fee, Tenant Charge. Requires receipt
deposited first.

Charges: Tenant, Date, Unit (auto), Total, Description. Paid charges
cannot be edited below paid amount.

Charge Late Fees: Filters -> list with checkboxes. Base + Daily Late
Fees. Current month only.

Application Fee: Name, Amount, Property, Unit, GL Account, Receipt
Date, Cash Account, Check #.

Bills (Enter Bill) — TWO-STEP ACCRUAL:
- Enter: Payee, Bill Date, Reference, Due Date, Remarks, multi-line
  (GL Account, Description, Amount). Posts DR Expense / CR AP.
- Pay: from bill detail. Posts DR AP / CR Cash. Partial allowed.
- Reverse: only if unpaid. Flips original GL entry.
- Bill status: UNPAID | PARTIAL | PAID | VOID.

Recurring Bills: Bill or Credit, Payee, Total, Start/End Date, Bill Day,
Due Day, Post Code, Repeats Monthly.

Checks: Write Checks flow — Find Bills -> Confirm & Finalize -> Print.

Credits: Enter Credit (not negative bill).

Owner Draw: Owner, Date, Cash Account, Total, Remarks, Property, Unit,
GL Account, Description, Amount.

Pay Management Fees: Two-tier 9% rent + 100% additional fees.

Pay Owners: Same flow. ACH auto-processed.

Tenant Payable: Payee, Bill Date, GL Account, Due Date, Cash Account,
Total, Description.

Transfer Funds: Property 1 -> Property 2, direction arrow, Amount, Date.

Bank Deposits: Bank Account, Deposit Date, Deposit #, Description,
list of receipts with checkboxes, All/None, Make Deposit. Cannot be
reversed — use journal entry.

Bank Accounts: Name, Bank Name, Routing #, Account #. ACH Format (CSV
or NACHA). Check setup. Reconcile: Statement Date, Ending Balance,
check off, QIF Import.

Journal Entries: Must balance. Remarks vs Description. Recurring.
Manually Post. Post GPR.

---

# SECTION 20 — MAINTENANCE MODULE

Work Orders: Status, Vendor Invoice #, Approved By Owner, Tenants
Notified, Description, Vendor Instructions, Property, Unit, Tenant
(auto), Vendor, Details table (GL Account, Description, Amount),
Notes, Files. Buttons: Save, Email, Print, Create Bill, Delete.

Recurring: Repeats Monthly (with month selection) | On Move In | On
Move Out. Start/End.

Convert WO to Bill: One click.

Inspections: Mobile, offline, photos + notes + checklist.

Unit Turns, Projects, Purchase Orders (approval workflow), Inventory,
Fixed Assets.

---

# SECTION 21 — SMART MAINTENANCE

Maintenance Groups: Properties grouped. Each has own dispatch rules.
One DEFAULT group. Columns: Groups | Dispatch | Contacts | Urgencies |
Vendors.

Issue Urgencies (per group): Normal / Low (Resident Responsibility) /
Emergency. Conditional rules. Alarm always Emergency.

Primary Contacts (per group): Business + After Hours. Multiple.

Dispatch Instructions (per group): For each Urgency x Time: Who, How,
Autocall, Escalation timeout, Cycling order. EMERGENCY x AFTER HOURS
most aggressive.

On-Call Calendar: Month view, shifts.

Preferred Vendors (per property): By trade, ranked 1st/2nd/3rd.
Notification via call + SMS + email.

Assignment Logic: EMERGENCY -> crew first, then preferred vendor
escalating 1st -> 2nd -> 3rd. NORMAL/LOW -> crew on calendar, else vendor.

Missed Call / Rejection Escalation: reason popup or auto-timeout. Both
escalate to manager + owner.

---

# SECTION 22 — TENANT PORTAL

Nav: Home | Payments | Maintenance | Contact Us | Shared Documents |
Insurance | Property Details | Account Profile | Help.

Home: Balance card (green), Insurance card (pink), Maintenance card
(orange).

New Request: "Tell us what's going on" (max 950 chars). Smart intake.
Reconfirms urgency. Duplicate detection. Follow-up questions.

Maintenance List: Cards with status ribbons. Closed on right.

After Acceptance: "Crew on the way". Crew name + phone. ETA.

Payments: Current Bills. Pay / Auto Pay. Balance Due.

---

# SECTION 23 — OWNER PORTAL

Access: One-time email link (no password). Subdomain login.

Owner Packet: Customizable. Reports to include. Email checkbox.

Statement: Header, Owner info, Property info, Transaction table (Date,
Payee/Payer, Check#, Description, Income, Expense, Balance), Beginning
Cash, Ending Cash, Totals, Property Cash Summary (Required Reserves,
Prepaid Rent).

---

# SECTION 24 — VENDOR PORTAL

Access: Created on first work order email click. Three sign-in methods.

Work Order Card: WO # + Company, Address, Details, Description, Vendor
Instructions, Decline/Accept.

Status Tabs: In Progress, Estimated, Work Done, Completed.

Invoices: Line items. Add Attachments. Total Due.

Notes: Add Note (up to 10 photos). Edited tag.

Account Settings: Contact, Insurance Expiration.

Mobile: Add to Home Screen.

Vendor Crew: Vendor adds own crew. Auto-assign if vendor doesn't.

---

# SECTION 25 — CREW PORTAL

Nav: Home | My Work Orders | My Schedule | Time Tracking | Messages |
My Profile.

Home: Stat cards, On-Call Now, Pending assignments (Accept/Reject),
Upcoming jobs.

Work Orders: Filters (All / Open / In Progress / Done / Emergency /
Normal).

Detail: Full issue + photos, Property + permission, Resident name +
phone, Intake answers, Timeline, Actions (Accept, Reject, Start, Update,
Complete). After accept: ETA, message, photos, log hours.

Schedule: Month view. Read-only.

Time Tracking: Auto-timer. Travel + on-site separated.

---

# SECTION 26 — MESSAGING LAYER

Three phases:
1. In-app chat (WebSockets). One-to-one + group threads. Read/delivered/
   sent. Attachments. Email copy if offline.
2. Native mobile app (React Native). Push notifications.
3. WhatsApp Business API (optional, paid).

Status: Sent / Delivered / Read (blue). Read receipts. Typing
indicator. Online/offline. Attachments. Emoji. Reply. Search.

Who can message whom: Manager <-> Tenant, Manager <-> Crew, Manager <->
Vendor, Manager <-> Owner, Crew <-> Tenant, Vendor <-> Crew.

Group chat per work order. Invite-only.

Email mirroring: Every in-app message + email copy.

Participant preferences: In-app / Email / Both / SMS also.

---

# SECTION 27 — NOTIFICATION LAYER

Every message record: Date, Time, Sent by, Channel (Email/SMS/Phone),
Recipient, Status (Sent/Delivered/Read/Failed/Bounced/Answered/No
Answer), Body, Template, Attachments, Reply, Related entity.

Three views: In work order (threaded), In Communication module (all),
In backup.

Two-tier: In-app + Email always. SMS if offline for X min.

Tracking page: Public, token-protected. Shows request details, status,
technician, ETA. Accept/Reject.

Templates: SMS, Email, Voice. Variables.

Providers: Email SMTP (built), SMS Twilio, Voice Twilio.

---

# SECTION 28 — INTERNAL TEAM

Roles: Sales, Billing, Tech, Support, Dev.
Lifecycle: Sales -> Billing -> Tech -> Support -> (Dev).
Access isolation per role. Every action logged.
Implementation: SEPARATE platform_users table (Phase 9).

---

# SECTION 29 — SUPPORT TICKET SYSTEM

Who: Admin (always), Owner (if enabled), Manager (if enabled), Others
(if enabled).

Contents: Category (Bug/Feature/Billing/Training/Emergency), Description
+ screenshots, Priority (Low/Normal/High/Critical), Auto-attached
context, Thread of replies, Status (Open/In Progress/Waiting/Resolved/
Closed).

Routing: Bug -> Tech/Dev. Billing -> Billing. Feature -> Sales/Dev.
How-to -> Support. Urgent -> Support.

Temp access: Time-limited token. Logged. Auto-expires.

---

# SECTION 30 — SUBSCRIPTION & BILLING

Dimensions:
Property count: 1, 2-10, 11-50, 51-200, 201-500, 501-1000, 1000+
Modules: Core (free), Accounting, Maintenance, Smart Maintenance,
Owner Portal, Tenant Portal, Vendor Portal, Crew Portal, Leasing,
Communication, Reporting, Documents, Compliance, Affordable Housing,
API, White-Label.

Models: A (a la carte), B (packages only), C (hybrid — recommended).

Fully customizable. Module dependencies.

Feature gating: same 4-layer as Section 9.

Provider: Stripe.

Tables: plans, plan_modules, modules, module_features, pricing_tiers,
add_ons, discounts, quotes, quote_line_items, subscriptions,
subscription_items, subscription_invoices, subscription_events,
usage_records, payment_methods, billing_settings.

Lifecycle: ACTIVE -> PAST_DUE -> RESTRICTED -> SUSPENDED -> CANCELLED.
Placeholder: organizations.state.

---

# SECTION 31 — SETTINGS MODULE

Structure (12 sections):
General, Accounting, Approvals, Users, Property Groups, Workflow,
Owners, Leasing, Documents, Maintenance, Communication, Risk/Tags/
Affordable Housing.

Company Settings: Company Name, Phone, Fax, Time Zone, Address, Federal
Tax Info (EIN, Taxpayer ID, TCC), Owner Packet cover, Logos, Portfolios.

Accounting Settings: Key Accounts, GPR Accounts, Receipts handling,
Check Writing, Management Fees overcollection, Reports defaults.

My Settings: Profile, Property Staff, Notification preferences, Email
signature, Reply-to, Two-step verification, Login history.

Users: Add/Edit/Delete. No user limit, no per-user charge.

Menu Permissions: Settings -> Permissions (3 tabs: Roles | Users | My
Preferences). Built (Section 42).

GL Account Permissions: Separate feature, not yet built.

Auditing Center: All activity. Filter, Export.

---

# SECTION 32 — APPFOLIO MANAGER GUIDE EXTRACT

Login URL: http://yourcompany.appfolio.com.

Navigation: Tabs (Start Page | Properties | People | Vacancies |
Accounting | Reports). Sub-tabs. Right Task Pane. Universal Search.
CTRL+K (repeat bill), CTRL+J (repeat field). Tags. Drill-downs. Notes +
Attachments. Workflows with Save for Later + In Progress tab. Hide.

Move In / Move Out Workflows (see Section 17).

Reports catalog:
Tenant (7): Delinquency, Security Deposit Funds Detail, Tenant Directory,
Tenant Ledger, Tenant Tickler, Tenant Unpaid Charges, Tenant Unpaid
Charges Summary.
Property & Unit (12): Budget Comparison, Budget Detail, Gross Potential
Rent, Lease Expiration Detail/Summary by Month, Property Directory,
Property Group Directory, Property Performance, Rent Roll, Unit
Directory, Unit Inspection, Unit Vacancy Detail.
Owner & Vendor (5): Owner Directory, Owner Statement, Vendor Directory,
Vendor Ledger, Work Order.
Accounting (12): Account Totals, Balance Sheet, Bank Account Activity,
Bank Account Association, Cash Flow, Cash Flow 12 Month, Chart of
Accounts, Expense Distribution, General Ledger, Income Statement,
Trial Balance, Trust Account Balance, Trust Account Detail.
Transaction (9): Aged Payables, Aged Receivables, Bill Detail, Charge
Detail, Check Register, Check Register Detail, Deposit Register,
Expense Register, Income Register, Journal Entry Register.

Letters: 3 Day Notice, Deposit Disposition Amount Due/Refund, Rent
Increase, Tenant Unpaid Charges, Cancellation of Management, Management
Contract Renewal, Insurance Requirements. Custom letters with mail
merge.

---

# SECTION 33 — BANK ACCOUNTS + ACH SETUP

Step 1 — Establish ACH: Bank Name, Routing, Account #, File Format
(CSV/NACHA), File Header Options, Batch Header Options.

Step 2 — Setup in AppFolio: Business setup, Owner setup (ACH Setup).
Fields: Owner Paid by ACH, Routing, Account #.

Step 3 — Test with $0 file.

---

# SECTION 34 — PROPERTY DETAIL TABS (Full List)

Header, Activities, Property Info, Non-Revenue, Staff, Rental Info,
Amenities, Tenants, Past Tenants, Hidden Tenants, Marketing, Lease
Settings, Owners, Mgmt Fees, Additional Fees, Late Fee Policy, Fixed
Assets, RUBs, Property Groups, Statement Settings, Bank Accounts,
Photos, Marketing Photos, Notes, Audit Log, Keys, Maintenance Info.

---

# SECTION 35 — FINANCIAL DIAGNOSTICS (6 checks)

1. Security Deposit Funds Mismatch
2. Escrow Cash Account Balance Mismatch
3. Non-Zero Security Clearing Account Balances
4. Negative Balance on Fee GL Accounts
5. Positive Balance on Fee GL Accounts
6. Trust Account 3-Way Reconciliation

Auto-post: "Refund Negative Diagnostic".

---

# SECTION 36 — TRANSACTION TYPES

Receipt, eCheck, CC receipt, Reversed Receipt, Reversal Receipt, Reverse
Receipt, Refund Negative Diagnostic, Bank Transfer, Transfer, Check,
Clearing Account, Owner Contribution, Management Fee.

---

# SECTION 37 — BANK RECONCILIATION

Fields: Account to Reconcile, Statement Date, Ending Statement Balance.

Process: Check off Deposits + Credits. Check off Checks + Payments. QIF
Import. Calculator shows status. Balanced -> Reconcile.

Notes: Interest charges distributed by ratio of ending cash balance.
Adjust beginning balance only via journal entry.

---

# SECTION 38 — FULL BUILD ORDER

## Foundation Pass (Phase 3.4) — SHIPS FIRST

The Foundation Pass (12 sessions) makes every subsequent feature
ship by flipping a flag. It replaces the old plan order.

Order: 3.4.1 (this session — planning + PLAN_GAPS.md + FEATURE_REGISTRY
v1) → 3.4.2 (FEATURE_REGISTRY full + check_parity.py v2) → 3.4.3
(identity boundary) → 3.4.4 (flags + jobs) → 3.4.5 (multi-region
schema) → 3.4.6 (billing) → 3.4.7 (signup) → 3.4.8 (fraud) → 3.4.9
(internal admin app) → 3.4.10 (customer flag consumption) → 3.4.11
(unit enforcement) → 3.4.12 (retrofit Receipts) → 3.4.13+ (retrofit
remaining pages).

See Section 82 for the full table.

Then phases resume as originally ordered, with these changes:

Phase 1  — Menu Permissions System: DONE
Phase 2  — Accounting: DONE (core); polish deferred to 3.6
  1. DONE Chart of Accounts
  2. DONE General Ledger
  2b. DONE Manual Journal Entry
  3. Universal Notes + Attachments — DEFERRED to Phase 3.7
  4. DONE Bank Accounts
  5. DONE Receipts
  6. DONE Bills
  7. DONE Bank Deposits
  8. DONE Financial Diagnostics
  9. DONE Management Fees
  10. DONE Owner Statements
Phase 3  — Property Detail tabs: IN PROGRESS
  3a. DONE Amenities
  3b. DONE Appliances
  3c. DONE Improvements
  3d. DONE Photos
Phase 3.5 — Property Detail Polish (28 items remaining — see JSON)
  DONE this session:
  - Display settings page (layout mode, theme, date format, currency)
  - Per-org currency (organizations.currency, Admin/Owner save)
  - Custom currencies CRUD (add/edit/delete per-org currencies)
  - SETTINGS menu group (Display, Currencies, Menu Permissions, Sidebar)

  Remaining items:
  - Amenities: fee_amount, availability_status
  - Appliances: condition
  - Improvements: warranty_expires
  - Photos: image editor (crop / rotate)
  - Photos: drag-to-reorder UI
  - Late Fee automation engine
  - Rent Increase workflow (Set -> Preview -> Notify -> Apply)
  - Move In / Move Out 5-step workflows (Section 17)
  - Adjust Move Out Disposition
  - Delinquency automation (aging, notices)
  - Tenant Insurance workflow (verify, track, notify)
  - Insurance expiration alerts
  - Owner Reserve tracking
  - Letters / mail merge (base)
  - Property Groups
  - Budget tab
  - Map tab
  - Keys tracking tab
  - Statement Settings tab
  - Non-Revenue tab
  - Staff tab (assignments)
  - Universal Hide semantics
  - Universal Powerful Search
  - Universal Repeat Form / Field (CTRL+K / CTRL+J)
  - Universal styled confirm modal rollout
Phase 3.5.5 — Compliance Pass (behavior-preserving retrofit)
  Retrofit each existing page (Receipts, Bills, Deposits, GL,
  Owner Statements, Management Fees, Bank Accounts, Journal
  Entries, Charges, Currencies, Display, Permissions, Sidebar,
  Properties) so it:
  - uses formatMoney() / formatDate() for every value
  - reads theme / layout / density from useDisplay()
  - renders every planned tab, field, button, and section as a
    hidden slot until its platform feature flag is advanced
    past HIDDEN
  Behavior-preserving: nothing changes visually until a flag
  moves. See Section 79 (Build-In-Place Policy) and Section 80
  (Platform Feature Gating). One page at a time.
Phase 3.6 — Accounting Polish (73 items — see JSON for full list)
  Chart of Accounts:
  - Recalculate Balances button
  - Hide semantics for GL accounts
  - GL Account Permissions (who can post to what)
  - offset_account UI
  - must_clear flag UI
  Journal Entries:
  - Sub-tabs (History | Recurring)
  - Recurring JEs
  - Manually Post JEs
  - Post GPR
  - Remarks vs Description rule
  Receipts:
  - Application Fee dedicated form
  - Process NSF
  - Print receipt
  - Repeat receipt
  - Edit lock after deposit
  - Cash Account "Automatic" default
  Charges:
  - Enter Charge (standalone)
  - Charges list view
  - Charge edit rules (paid floor)
  Bills:
  - Reverse after partial payment
  - Recurring Bills + Bill/Credit toggle + Post Codes
  - Write Checks flow
  - Enter Credit
  - Delete Bill only if unpaid
  - Manually Post Bills
  - Cash Account field on bill
  - Vendor link (after Phase 4)
  Checks:
  - Checks list view
  - Void Check
  - Check Memo
  Deposits:
  - Print Bank Deposit
  - Date-mismatch warning
  - Per-bank-account numbering
  - Edit deposit
  Bank Accounts:
  - Bank Reconciliation (Section 37)
  - QIF Import
  - Check setup
  - ACH file generation (NACHA / CSV)
  - Bank Adjustments (entity + sub-tab)
  - Bank feed import
  Owners:
  - Owner ACH Setup page
  - $0 ACH Test File
  - Owner Held Security Deposits (whole feature)
  Management Fees:
  - Pay Owners flow
  - Overcollection strategy setting
  - Post GPR
  - Management Fee Exclusions list
  Diagnostics:
  - Auto-fix Refund Negative Diagnostic
  - Bank Reconciliation Lapses 60 days
  - Real Positive Fee check (must_clear flag)
  - Additional checks to reach 9 total
  Owner Statements:
  - Required Reserves
  - Prepaid Rent
  - Property Cash Summary
  Owner Packets:
  - Customizer fields
  Settings:
  - Accounting Settings (Key Accounts, GPR, Receipts, Checks, Reports)
  - Accounting Basis toggle (Accrual default | Cash) — report layer only
  - My Settings
  - Auditing Center
  - Two-step verification
  - Login history
  Universal:
  - delete_reason UI
  - Notes expansion
  - Audit Log expansion
Phase 3.7 — Reports + Universal Attachments (57 items — see JSON for full list)
  Foundation:
  - Universal Attachments (one system, every entity)
  - Report framework (standard vs enhanced)
  - Print / Email / CSV Export on every report
  - Custom Report Builder (saved configurations)
  - Create Labels Report (mail merge via CSV)
  - Generate 1099 Forms & Reports (FIRE file)
  Letters:
  - Letters Overview + View/Edit + Custom + Print/Email + 3-Day Notice
  - Send Owner Packets
  Tenant Reports:
  - Delinquency, Security Deposit Funds Detail, Tenant Directory,
    Tenant Ledger, Tenant Tickler, Tenant Unpaid Charges, Summary
  Property & Unit Reports:
  - Budget Comparison, Budget Detail, Gross Potential Rent,
    Lease Expiration Detail/Summary by Month, Property Directory,
    Property Group Directory, Property Performance, Rent Roll,
    Unit Directory, Unit Inspection, Unit Vacancy Detail
  Owner & Vendor Reports:
  - Owner Directory, Owner Statement, Vendor Directory, Vendor Ledger,
    Work Order
  Accounting Reports:
  - Account Totals, Balance Sheet, Bank Account Activity,
    Bank Account Association, Cash Flow, Cash Flow 12-Month,
    Chart of Accounts, Expense Distribution, General Ledger,
    Income Statement, Trial Balance, Trust Account Balance,
    Trust Account Detail
  Transaction Reports:
  - Aged Payables, Aged Receivables, Bill Detail, Charge Detail,
    Check Register, Check Register Detail, Deposit Register,
    Expense Register, Income Register, Journal Entry Register
Phase 4  — Vendors
Phase 4.5 — Compliance (HOA / Affordable / Commercial / RUBs / Escrow)
Phase 5  — Smart Maintenance
Phase 6  — Messaging
Phase 7  — Portals
Phase 8  — Integrations (Stripe, SMS, screening, Deposit Alternatives)
Phase 9  — Internal Team + Support
Phase 10 — Subscription & Billing
Phase 11 — Production / AWS
Phase 12 — Native Mobile App

Total (web): ~230 sessions
Total (with mobile): ~290 sessions

# SECTION 39 — CRITICAL RULES

1. Never paste Python into PowerShell — use VS Code.
2. Prompt: (venv) PS C:\Projects\property-platform\backend>
3. Backend commands run from backend folder, venv active. Venv at
   backend\venv, activate .\venv\Scripts\Activate.ps1.
4. Frontend commands from frontend folder.
5. Every new model imported in init_db.py.
6. Every new router gets 2 lines in main.py.
7. Verify file size after saving (0 bytes = paste failed).
8. Hard refresh (Ctrl+Shift+R) after frontend changes.
9. Restart servers after config changes.
10. Commit to Git after every working module.
11. bcrypt==4.0.1 stays pinned.
12. Never Alembic autogenerate on existing tables.
13. Always write migrations by hand.
14. Always back up DB before risky migrations.
15. DB is property_platform.db (not app.db).
16. Role values UPPERCASE everywhere.
17. Menu keys UPPERCASE and dotted.
18. If Next.js 404s on pages that exist, check for stray frontend\app.
19. Run `python check_parity.py` at the START of every session to see
    the exact state of AppFolio parity. Run it again BEFORE every push.
    It must print "CLEAN". If it prints "FAILURES", add the missing items
    to docs/APPFOLIO_PARITY_CHECKLIST.json before pushing.
20. Nothing gets built unless it's in the parity checklist. Nothing
    gets marked done unless the checklist says so. The checklist is
    the single source of truth for what exists, what's scheduled, and
    what has no plan.

---

# SECTION 40 — REFERENCE FILES ON DISK

C:\Projects\property-platform\docs\
- PROJECT_MASTER.md (this file)
- MASTER_HANDOFF_v2.txt
- CHECKPOINT_1_Smart_Maintenance.txt
- AppFolio reference PDFs

---

# SECTION 41 — HOW TO CONTINUE IN A NEW CHAT

Paste this to any new assistant:

I'm continuing to build a property management platform (AppFolio clone).

Read this PROJECT_MASTER.md file fully. It has three parts:
- Part A: Current state
- Part B: Next action
- Part C: Full reference

Then continue from the immediate next action listed in Part B1.

Rules you must follow:
- I am a non-coder. Never ask me to write code.
- Give whole files, not fragments. I select-all, delete, paste, save.
- Label every command BACKEND or FRONTEND.
- One step at a time. Wait for me to run and report back.
- If I paste an error, fix it and give the next command.
- Backend venv is at backend\venv (not .venv). DB is property_platform.db.
- Role values are UPPERCASE. Menu keys are UPPERCASE and dotted.
- Every GL posting goes through post_transaction().

Then paste this entire file.

---

# SECTION 42 — MENU PERMISSIONS SYSTEM (BUILT)

Canonical menu keys: app/constants/menu_keys.py. 61 keys (46 original + ACCOUNTING.DEPOSITS + ACCOUNTING.MANAGEMENT_FEES + ACCOUNTING.OWNER_STATEMENTS + the previous additions). Format:
PARENT or PARENT.CHILD, uppercase. Frontend display info in
src/lib/menuConfig.ts.

Tables:
- menu_permissions — (organization_id, role, menu_key, visible)
- user_permissions — (organization_id, user_id, menu_key, visible,
  set_by_user_id)
- sidebar_preferences — per user (user_id UNIQUE, organization_id,
  order JSON, hidden JSON)

Resolver: app/services/menu_resolver.py -> resolve_menu_for_user().

Endpoints (under /api/menu):
- GET /me
- GET /roles
- PUT /roles/{role}
- POST /roles/{role}/reset
- GET /users
- GET /users/{user_id}
- PUT /users/{user_id}
- DELETE /users/{user_id}/overrides
- GET /me/preferences
- PUT /me/preferences

Frontend pieces:
- src/contexts/MenuContext.tsx
- src/lib/menuPermissions.ts
- src/lib/menuConfig.ts
- src/components/shell/Sidebar.tsx
- src/components/permissions/RoleMatrix.tsx
- src/components/permissions/UserOverrides.tsx
- src/components/permissions/MyPreferences.tsx
- src/app/dashboard/settings/permissions/page.tsx

Seed: On signup, create_user seeds new org. Existing orgs seeded by
migration 8a3f2c1e9b44.

Hard rules: Layers 2/3/4 can only subtract. ADMIN immutable. Parent
hidden -> children hidden. Every change audited.

Editor scoping: Admin = everyone below. Owner = MANAGER+below.
Manager = CREW/TENANT/VENDOR. Others = own prefs only.

---

# SECTION 43 — THREE-BOUNDARY ARCHITECTURE

Boundary 1 — Data isolation (built): Every customer table has
organization_id.

Boundary 2 — Identity isolation (partial): users (customer, org-
scoped) and platform_users (us, Phase 9) never mix.

Boundary 3 — Commercial channel (Phase 9+10): The only interface
between us and customers is subscriptions, invoices, tickets,
provisioning events, usage counters.

Platform access to customer data: default NO. With grant: time-limited
token scoped to a ticket. Logged. Expires automatically.

Subscription lifecycle: ACTIVE -> PAST_DUE -> RESTRICTED -> SUSPENDED ->
CANCELLED. Three enforcement layers. Daily job. Configurable per plan.
Stripe webhooks. organizations.state placeholder exists.

---

# SECTION 44 — GENERAL LEDGER (BUILT)

The GL is the single source of truth for all money movement.

Tables:
- gl_transactions (parent) — id, organization_id, transaction_date,
  posted_at, transaction_type, reference_number, memo, source_type,
  source_id, created_by_id, is_reversed, reversal_of_id, timestamps
- gl_entries (children) — id, organization_id, transaction_id,
  gl_account_id, property_id, unit_id, description, debit, credit,
  created_at

The rule: ALL writes go through post_transaction() in
app/services/gl_posting.py. It enforces:
1. Valid transaction_type
2. At least 2 lines
3. Each line: exactly one of debit/credit > 0
4. Sum(debit) == Sum(credit) within 0.01
5. All GL accounts belong to org, active
6. All properties belong to org
7. All units belong to given property
8. Rolls back entirely on failure

Never write to gl_transactions or gl_entries directly.

Reversal: Never edit or delete. Call reverse_transaction(). New
transaction with every line flipped. Original marked is_reversed=True.
Net effect: zero.

Endpoints (under /api/accounting):
- GET /gl-transactions (filters)
- GET /gl-transactions/{id}
- GET /gl-accounts/{id}/ledger
- GET /gl-accounts/{id}/balance
- GET /reports/trial-balance

Frontend pages:
- /dashboard/accounting/gl-accounts
- /dashboard/accounting/gl-accounts/{id}/ledger
- /dashboard/accounting/journal-entries/{id}
- /dashboard/accounting/trial-balance
- /dashboard/accounting/diagnostics (placeholder)

Balance: SUM(debit) - SUM(credit) per account. On demand. No cache.

---

# SECTION 45 — RECEIPTS (BUILT — Phase 2 Step 5)

Three types (mirrors Section 19):
1. TENANT  — tenant pays rent/fees. One row per charge (or ad-hoc).
             Amount auto-fills from open charges; description
             auto-fills from GL account ({Month} rent / {Fee} — {tenant}).
2. OWNER   — owner sends money in. Single line, defaults to 2401.
3. OTHER   — anything else. Single line, has "exclude from mgmt fee".

Tables:
- receipts — id, organization_id, type, receipt_date, amount,
  cash_gl_account_id, tenant_user_id, owner_user_id,
  income_gl_account_id, payer_name, received_from,
  exclude_from_mgmt_fee, property_id, unit_id, reference_number,
  remarks, notes, gl_transaction_id, is_reversed, reversal_of_id,
  is_active, created_by_id, timestamps
- receipt_lines — id, organization_id, receipt_id, gl_account_id,
  property_id, unit_id, description, amount_to_pay, line_date,
  is_prepayment, timestamps

Migration: 64dec42acecf_add_receipts_and_receipt_lines
(down_revision = b2d5f9e1c3a7).

The rule: ALL receipt postings go through post_receipt() in
app/services/receipt_posting.py, which calls post_transaction()
with transaction_type="RECEIPT". GL lines: DR cash, CR each income
line. Sum of credits must equal receipt.amount.

Reversal: reverse_receipt() calls reverse_transaction(), marks
original is_reversed=True, creates a mirror Receipt row linked via
reversal_of_id.

Endpoints (under /api/accounting/receipts):
- GET  ""                              list (date/type/property filters)
- GET  /tenant/{user_id}/open-charges  charges helper for tenant tab
- GET  /{receipt_id}                   detail + lines
- POST ""                              create + post to GL
- POST /{receipt_id}/reverse           reverse

Note on open-charges: Lease has no organization_id (Section 10).
We scope through Unit -> Property -> organization_id. Lease uses
tenant_id, not tenant_user_id.

Frontend pages:
- /dashboard/accounting/receipts        list + filters + centered modal
- /dashboard/accounting/receipts/new    3 tabs (Tenant/Owner/Other)

Wired into ACCOUNTING.RECEIVABLES menu key (label "Receipts",
href /dashboard/accounting/receipts).

Auto-description rule (current):
- 4100 Rent            -> "{Month} rent"
- 4105 Section 8       -> "{Month} Section 8"
- 4110 M2M             -> "{Month} rent (M2M)"
- 4416..4480, 2101     -> "{Label} — {tenant}"  (name omitted if no tenant)
- fallback             -> GL account name
Description auto-fills only when field is empty OR matches the
prior auto-description. Never overwrites manual text.

---

# SECTION 46 — MOBILE STRATEGY

End goal: full native mobile app (Level 3) for iOS + Android.

Interim plan (do these in order):
1. Desktop-first for the manager web app (now -> end of Phase 10).
   Every new page we build is desktop-focused. Managers work at desks.
2. Mobile-first for portals (Phase 7). Tenant, Owner, Vendor, Crew
   portals are built responsive from the start — those users mostly
   use phones. Cards instead of tables, bottom nav, big tap targets.
3. Level 1 responsive pass on the manager web app (~3 sessions,
   after Phase 7). Sidebar collapses to hamburger below 768px; tables
   get horizontal scroll; modals go full-screen on mobile; form grids
   stack to single column. Result: usable on a phone, still desktop UI.
4. Phase 12 — Native Mobile App (after Phase 11). React Native / Expo.
   Reuses all the same backend APIs.

Why native comes last:
- Backend is the foundation. Every API the mobile app needs must
  exist first.
- Building earlier = rebuilding every time the backend changes.
- A mobile-optimized web app (Level 1) is enough until real demand.

Native app cost & effort (Phase 12, one-time):
- ~40-60 sessions
- Apple Developer Program: $99/year
- Google Play: $25 one-time
- Push notifications: Firebase (free tier covers early scale)
- Ongoing maintenance: per OS release

Native app v1 scope:
- Tenant: view balance, pay rent, submit maintenance requests,
  receive push notifications, view documents
- Crew: accept/reject jobs, log hours, upload photos, get ETA pushes
- Manager: quick approvals, work order triage, notifications
- Owner: view statements, approve spend over maintenance limits

Rule for now: don't spend time on mobile-specific code in the web
app beyond what Phase 7 portals already need. Everything we're
building in Phases 2-6 is manager-facing desktop work.

---

# SECTION 47 — BILLS (BUILT — Phase 2 Step 6)

Two-step accrual payables (mirrors Section 19).

Flow:
- Enter Bill -> GL: DR Expense line(s) / CR Accounts Payable
- Pay Bill   -> GL: DR Accounts Payable / CR Cash
- Reverse (only if unpaid) -> flips the original GL entry

Tables:
- bills — id, organization_id, bill_number (auto B-00001 if blank),
  payee_name, payee_user_id (optional link to User), bill_date,
  due_date, reference_number, amount, amount_paid, status
  (UNPAID | PARTIAL | PAID | VOID), property_id, unit_id,
  payable_gl_account_id, remarks, notes, source_type, source_id,
  gl_transaction_id, is_reversed, reversal_of_id, is_active,
  created_by_id, timestamps
- bill_lines — id, organization_id, bill_id, gl_account_id,
  property_id, unit_id, description, amount, timestamps

Migration: 71eda8a9ba77_add_bills_and_bill_lines_and_ap_account
(down_revision = 64dec42acecf). Also seeds GL account 2100 Accounts
Payable for every existing org.

Services: post_bill(), pay_bill(), reverse_bill() in
app/services/bill_posting.py. All call post_transaction().

Endpoints (under /api/accounting/bills):
- GET  ""                     list (date/status/payee filters)
- GET  /{bill_id}             detail + lines
- POST ""                     enter bill (posts DR Expense / CR AP)
- POST /{bill_id}/pay         pay (partial allowed) (DR AP / CR Cash)
- POST /{bill_id}/reverse     reverse (only if unpaid)

Frontend pages:
- /dashboard/accounting/bills        list + filters + centered modal
- /dashboard/accounting/bills/new    enter bill (multi-line)

Menu: ACCOUNTING.PAYABLES -> Bills (label updated from "Payables").

Detail modal includes an inline Pay form (amount, date, cash account,
reference, remarks). No browser prompts.

NOTE on accrual vs. cash basis: The AppFolio Manager Guide (PDF p.54)
says "The General Ledger is not affected by bills until the check is
written." That describes cash-basis posting (older AppFolio behavior).
We post on accrual (DR Expense / CR AP at bill entry), which is the
correct double-entry model and matches modern AppFolio. Orgs that want
cash-basis *reports* can switch the per-org Accounting Basis toggle
(see Settings -> Accounting). GL postings never change — only reports.
JSON id: settings.accounting.accounting_basis (Phase 3.6).

---

# SECTION 48 — HOW TO UPDATE THIS DOCUMENT

Rule: NEVER edit PROJECT_MASTER.md by hand (find-and-replace,
VS Code edits). The file is large (~47 KB) and manual edits are
easy to break silently.

Instead, use a Python rebuild script. Pattern:

1. In the backend folder, create a script:
       code rebuild_master_full.py

2. The script contains the ENTIRE new PROJECT_MASTER.md as a
   Python string, and writes it to:
       C:\Projects\property-platform\docs\PROJECT_MASTER.md

   Template:

       from pathlib import Path
       MASTER = Path(r"C:\Projects\property-platform\docs\PROJECT_MASTER.md")
       CONTENT = r'''# PROJECT MASTER
       ... entire file contents here ...
       
---

# SECTION 50 — BANK DEPOSITS (BUILT — Phase 2 Step 7)

Group un-deposited receipts into a batch for the bank.

IMPORTANT: Deposits do NOT post to the GL. Receipts already
credit the cash GL account when they are posted. Deposits
simply tag receipts as deposited by inserting rows into
deposit_lines.

deposit_lines is the SINGLE SOURCE OF TRUTH for "is this
receipt deposited?". We do NOT store is_deposited on receipts.
This avoids SQLite batch_alter_table FK pain and stays
consistent on Postgres. Membership in a deposit IS the fact.

Tables:
- deposits — id, organization_id, bank_gl_account_id,
  deposit_date, deposit_number (auto D-00001 if blank),
  description, total, notes, is_active, created_by_id,
  timestamps
- deposit_lines — id, organization_id, deposit_id, receipt_id,
  created_at. UNIQUE index on receipt_id (a receipt can be in
  at most one deposit).

Migration: e266f7c76a7c_add_deposits_and_deposit_lines
(down_revision = 71eda8a9ba77). Also seeds the new
ACCOUNTING.DEPOSITS menu key for every existing org
(visible to ADMIN/OWNER/MANAGER; hidden from CREW/TENANT/
VENDOR/VENDOR_CREW/APPLICANT).

Menu key added to app/constants/menu_keys.py (MENU_KEYS
list) and to DEFAULT_MATRIX["MANAGER"]. ADMIN and OWNER see
it automatically because they use set(MENU_KEYS).

Services (app/services/deposit_posting.py):
- create_deposit() — validates receipts (exist, same org,
  not reversed, not already deposited), computes total from
  receipts, saves deposit + deposit_lines, auto-numbers as
  D-NNNNN if blank. Raises PostingError on any issue.
- list_undeposited_receipts() — returns receipts not in any
  deposit_lines row. Optional bank_gl_account_id filter.

No GL posting. Reverse not supported — corrections via
journal entry (Section 19). If we later model "cash on hand"
as a separate GL account, a DR Bank / CR Cash on Hand posting
would be added inside create_deposit().

Endpoints under /api/accounting/deposits:
- GET  ""                          list (date/bank filters)
- GET  /undeposited-receipts       picker (optional bank filter)
- GET  /{deposit_id}               detail + receipts
- POST ""                          create deposit

Note: the /undeposited-receipts route MUST be defined before
/{deposit_id} or FastAPI will try to parse the string as int.

Frontend pages:
- /dashboard/accounting/deposits        list + centered detail modal
- /dashboard/accounting/deposits/new    picker with All/None

Menu: ACCOUNTING.DEPOSITS -> Bank Deposits
(href /dashboard/accounting/deposits).


---

# SECTION 51 — OWNER SUB-LEDGER (BUILT — Phase 2 Step 8a)

AppFolio-parity owner scoping. This is the "third leg" of the
trust account three-way reconciliation.

Data model:
- receipts.owner_id (nullable FK to users)
- bills.owner_id (nullable FK to users)
- gl_entries.owner_id (nullable FK to users)  <- the tag that matters
- properties.owner_id (nullable FK, primary owner) + ownership_pct
- property_owners (property_id, user_id, ownership_pct, is_primary)
  join table for co-ownership / split 1099s

Migration IDs:
- 3b50fb7fd91a_add_owner_id_to_receipts_bills_gl_entries
- bdc8b2be19d9_add_property_owners_and_ownership

Service: app/services/owner_ledger.py
- get_owner_subledger(db, org, owner_id) -> one owner's balance + properties
- get_all_owner_subledger_totals(db, org) -> per-owner list + grand total
- get_owner_subledger_total(db, org) -> convenience (just the total)

Sign convention:
- INCOME credited -> increases what owner is owed
- EXPENSE debited -> decreases what owner is owed
- ASSET debited -> increases owner equity
- LIABILITY credited -> decreases owner equity
- EQUITY credited -> increases owner equity

Company-level GL lines (owner_id = NULL) are excluded from the
sub-ledger and surface as "unallocated" in the reconciliation.

When more postings carry owner_id, the sub-ledger total converges
to the trust cash balance.

---

# SECTION 52 — FINANCIAL DIAGNOSTICS (BUILT — Phase 2 Step 8b)

Six financial health checks. Endpoint:
  GET /api/accounting/diagnostics

Service: app/services/diagnostics.py
- check_security_deposit_mismatch()  — GL 2101 vs GL 1160
- check_escrow_cash_mismatch()       — GL 1160.offset_account check
- check_clearing_accounts()          — any "Clearing" account must net to $0
- check_negative_fee_accounts()      — 44xx INCOME never negative
- check_positive_fee_accounts()      — placeholder (no must_clear flag yet)
- check_three_way_reconciliation()   — trust cash 1150 vs owner sub-ledger total
- run_all_diagnostics()              — runs all, returns summary

Each check returns:
  {key, label, passed, severity, message, details[]}
severity is "ok" | "warning" | "error".

Frontend:
- src/lib/diagnostics.ts        — client
- src/app/dashboard/accounting/diagnostics/page.tsx
  — real report page (replaces placeholder)

Read-only. Auto-fix (e.g. "Refund Negative Diagnostic") is deferred.


---

# SECTION 53 — MANAGEMENT FEES (BUILT — Phase 2 Step 9)

AppFolio-parity two-step flow:

  1. Pay Management Fees -> creates a BILL
       DR 6001 Management Fees
       CR 2100 Accounts Payable
  2. Pay the Bill (existing Bills flow)
       DR 2100 Accounts Payable
       CR 1150 Rental Trust

This mirrors how AppFolio hands you a Bill for the management
fees and lets you pay it like any other payable.

Two-tier rate:
- Rent income (GL 4100 Rent, 4105 Section 8) -> property.mgmt_fee_pct
  (default 9.00, overridable per property)
- Other eligible income -> 100.00 always

Eligibility rules:
- Only GL accounts with `subject_to_mgmt_fees = True`
- Only GL entries that came from a Receipt (source_type = "receipt")
- Receipt.exclude_from_mgmt_fee = False
- Receipt.is_reversed = False
- Transaction date within [period_start, period_end]

Overrides:
- property.mgmt_fee_flat (if set) -> ignore percentages, charge flat
- property.mgmt_fee_min  (if set) -> never charge less than the floor
- property.mgmt_fee_end_date -> no fees if period_end is after this

Tables:
- management_fee_runs — one row per property per fee period.
  Fields: id, organization_id, property_id, period_start, period_end,
  rent_income_total, other_fee_income_total, rent_fee_pct, other_fee_pct,
  rent_fee_amount, other_fee_amount, total_fee, expense_gl_account_id,
  cash_gl_account_id (stores the AP account id on the credit side),
  gl_transaction_id, notes, is_reversed, reversal_of_id, is_active,
  created_by_id, timestamps

Migration: 0cf6edacce77_add_management_fee_runs_and_property_fee_fields
(down_revision = bdc8b2be19d9). Also seeds
ACCOUNTING.MANAGEMENT_FEES menu key.

Property new columns: mgmt_fee_pct, mgmt_fee_flat, mgmt_fee_min,
mgmt_fee_end_date.

Service: app/services/management_fee_posting.py
- preview_management_fee()     -> read-only calculation
- run_management_fee()         -> posts GL + creates a Bill + saves run
- reverse_management_fee_run() -> flips the GL txn

Endpoints under /api/accounting/management-fees:
- POST /preview             compute (read-only)
- POST /run                 post (creates run + Bill + GL txn)
- GET  ""                   list
- GET  /{run_id}            detail
- POST /{run_id}/reverse    reverse

Frontend:
- /dashboard/accounting/management-fees        list + centered modal
- /dashboard/accounting/management-fees/new    preview + post flow

Menu: ACCOUNTING.MANAGEMENT_FEES -> Management Fees
(href /dashboard/accounting/management-fees).


---

# SECTION 54 — OWNER STATEMENTS (BUILT — Phase 2 Step 10)

Frozen snapshot model — matches AppFolio.

Flow:
  1. Pick owner + period -> Preview (read-only)
  2. Generate -> freezes a snapshot row in owner_statements
  3. View / Print -> clean print layout (sidebar hidden via
     global print CSS)
  4. Owner receives PDF

Snapshot semantics:
  * Once generated, the statement NEVER changes — even if GL
    is corrected later. This is the AppFolio behavior and the
    correct accounting practice.
  * To "regenerate," create a new statement with a new ID.

Structure:
  * One section per property the owner has a stake in
    (Property.owner_id + property_owners join table)
  * Per property: Beginning Cash, per-transaction running
    balance, Ending Cash, Income, Expense, Net
  * Top summary: Total Beginning Cash / Income / Expense /
    Ending Cash across all properties

Where numbers come from:
  * Beginning Cash = sum of (debit - credit) on 11xx ASSET
    accounts for that property BEFORE period_start
  * Transactions = every GL transaction in the period that
    touches that property, with its cash movement and
    income/expense movement per row
  * Running balance starts at Beginning Cash and accumulates
    cash movement row by row
  * Ending Cash = Beginning Cash + sum of cash movement in
    period

Table: owner_statements
- id, organization_id, owner_id
- period_start, period_end, generated_at
- total_beginning_cash, total_ending_cash
- total_income, total_expense, total_net
- property_data (JSON snapshot of the per-property breakdown
  and full transaction list)
- pdf_url (nullable), notes
- is_active, generated_by_id, timestamps

Migration: 4aa1c77e213c_add_owner_statements
(down_revision = 0cf6edacce77). Also seeds
ACCOUNTING.OWNER_STATEMENTS menu key.

Service: app/services/owner_statements.py
- preview_owner_statement()    -> read-only calculation
- generate_owner_statement()   -> freezes snapshot
- helpers: _properties_for_owner(), _cash_account_ids(),
  _cash_activity_for_property(), _transactions_for_property()

Endpoints under /api/accounting/owner-statements:
- POST /preview             compute (no save)
- POST /generate            freeze & save
- GET  ""                   list
- GET  /{statement_id}      detail (expanded)

Frontend:
- /dashboard/accounting/owner-statements        list
- /dashboard/accounting/owner-statements/new    preview + generate
- /dashboard/accounting/owner-statements/{id}   detail/print

Print CSS:
- src/app/globals.css @media print block hides aside/nav/
  header/footer so Print gives a clean statement.
- Print/Save as PDF button calls window.print().

Menu: ACCOUNTING.OWNER_STATEMENTS -> Owner Statements
(href /dashboard/accounting/owner-statements).


---

# SECTION 55 — BANK ACCOUNTS (BUILT — Phase 2 Step 4)

Physical bank accounts mapped to GL cash accounts.

AppFolio parity:
- Client Trust (OPERATING) ↔ GL 1150 Rental Trust
- Security Deposit Trust (ESCROW) ↔ GL 1160 Security Deposit Cash

Both are seeded automatically for every org by migration
7ca4251074bc_add_bank_accounts.

Table: bank_accounts
- id, organization_id
- name ("Client Trust", "Security Deposit Trust")
- bank_name, routing_number, account_number (all nullable)
- gl_account_id (required, unique per (org, gl))
- account_type — OPERATING | ESCROW
- ach_format — CSV | NACHA (nullable, set later)
- notes
- is_active, created_by_id, timestamps

Routing and account numbers are stored as strings (leading
zeros matter). Encrypt at rest in Phase 11.

Endpoints under /api/accounting/bank-accounts:
- GET    ""                       list
- GET    /{id}                    detail
- POST   ""                       create
- PATCH  /{id}                    update
- DELETE /{id}                    soft delete (is_active=False)

Frontend:
- /dashboard/accounting/bank-accounts — list + centered edit modal

Menu: ACCOUNTING.BANK_ACCOUNTS -> Bank Accounts
(href /dashboard/accounting/bank-accounts) — key existed from
Phase 1, just pointed at the real page now.

Bank Reconciliation (Section 37) is a separate future step that
will use these accounts.


---

# SECTION 56 — MANUAL JOURNAL ENTRY (BUILT — Phase 2 Step 2b)

The public write endpoint for GL transactions that was
deferred from Step 2.

Routes through the same post_transaction() validation as
everything else — balance, valid accounts, org scope, etc.

Endpoints under /api/accounting/journal-entries:
- GET  ""   list (transaction_type = JOURNAL_ENTRY only)
- POST ""   create + post a manual JE

Request body (POST):
  {
    "transaction_date": "YYYY-MM-DD",
    "reference_number": "optional",
    "memo": "optional",
    "lines": [
      {gl_account_id, property_id?, unit_id?, owner_id?,
       description?, debit, credit},
      ...
    ]
  }

Validation (enforced in both the Pydantic schema and
post_transaction):
  * At least 2 lines
  * Each line: exactly one of debit/credit > 0
  * Sum(debits) == Sum(credits) within 0.01
  * All accounts belong to org and are active
  * All properties belong to org
  * All units belong to given property

On success: creates a GLTransaction with
  transaction_type = "JOURNAL_ENTRY"
  source_type = "manual_je"

Reading a JE uses the existing
/dashboard/accounting/journal-entries/{id} detail page and
GET /api/accounting/gl-transactions/{id}.

Frontend:
- /dashboard/accounting/journal-entries       list
- /dashboard/accounting/journal-entries/new   form with live
  balance check
- /dashboard/accounting/journal-entries/{id}  detail (existing)

Menu: ACCOUNTING.JOURNAL_ENTRIES -> Journal Entries
(href /dashboard/accounting/journal-entries) — key existed
from Phase 1; just wired to the real list page.

No new migration — manual JEs reuse gl_transactions and
gl_entries.


---

# SECTION 57 — APPFOLIO FEATURE PARITY AUDIT

Complete inventory of AppFolio features vs. our build.
Status legend:
  ✅ BUILT
  🔵 IN PROGRESS
  ⬜ SCHEDULED (phase shown)
  ⚠️  BUILT WITH BEHAVIOR MISMATCH
  ❌ NOT PLANNED -> scheduled by this doc

NOTE (2026-09-22): The canonical, item-by-item inventory lives in
docs/APPFOLIO_PARITY_CHECKLIST.json (385+ items). This section is the
human-readable summary. If they disagree, the JSON wins. Run
`python check_parity.py` from backend/ before every push.

NEW (2026-09-21/22):
- ✅ Charges feature (standalone Enter Charge + list view + edit rules)
  — accounting.charges.enter_charge, .list_view, .edit_rules
- ✅ Custom Currencies CRUD — settings.currencies.* (list/add/edit/
  delete/seed_defaults/ui). PARTIAL: Display dropdown still hardcoded.
- ✅ Display Settings page — settings.display.* (page saves; no page
  consumes yet). PARTIAL: consumption pending Phase 3.5.5.
- ✅ SETTINGS menu group — settings.menu.group
- ✅ Sidebar preferences per-user fix (drop stale unique index,
  user_id NOT NULL, race-safe get-or-create)
- ✅ My Preferences tab bug fix (IntegrityError import)

Additional items from the AppFolio Manager Guide (PDF cross-check,
2026-09-21) — these are tracked in the JSON but were missing from
the summary:

## Accounting — additions (from PDF pp. 27–80)

- ⬜ Owner Held Security Deposits (whole feature) — Phase 3.6 [PDF p.33]
- ⬜ Bank Account Adjustments (entity + sub-tab list) — Phase 3.6 [PDF p.44]
- ⬜ Recalculate Balances button on GL Accounts — Phase 3.6 [PDF p.48]
- ⬜ Post Codes for recurring bills — Phase 3.6 [PDF p.55]
- ⬜ $0 ACH Test File — Phase 3.6 [PDF p.28]
- ⬜ Transfer Funds (property to property) — Phase 3.6 [PDF p.67]
- ⬜ Manually Post Journal Entries — Phase 3.6 [PDF p.51]
- ⬜ Manually Post Bills — Phase 3.6 [PDF p.61]
- ⬜ Process NSF (bank fee + tenant charge + reversal) — Phase 3.6 [PDF p.80]
- ⬜ Enter Charge (standalone) + Charges list view — Phase 3.6 [PDF p.74–75]
- ⬜ Check list view + Void Check — Phase 3.6 [PDF pp.57, 59]
- ⬜ Print receipt / Repeat receipt / Repeat form (CTRL+K, CTRL+J) — Phase 3.6 [PDF pp.6, 68–72]
- ⬜ Receipt edit lock after deposit — Phase 3.6 [PDF pp.70–72]
- ⬜ Receipt Cash Account "Automatic" default — Phase 3.6 [PDF pp.69–72]
- ⬜ Bank Deposit print / date-mismatch warning / per-bank numbering — Phase 3.6 [PDF p.79]
- ⬜ Enter Bill Cash Account field (moved onto bill) — Phase 3.6 [PDF p.54]
- ⬜ Delete Bill only if unpaid — Phase 3.6 [PDF p.56]
- ⬜ Check Memo — Phase 3.6 [PDF p.58]

## Reporting — additions (from PDF pp. 81–95)

- ⬜ Report framework (standard vs enhanced) — Phase 3.7 [PDF p.81]
- ⬜ Print / Email / CSV Export on every report — Phase 3.7 [PDF pp.83–86]
- ⬜ Create Labels Report — Phase 3.7 [PDF p.87]
- ⬜ Generate 1099 Forms & Reports (FIRE file + print) — Phase 3.7 [PDF p.89]
- ⬜ Letters module (Overview, View/Edit, Custom, Print/Email, 3-Day Notice) — Phase 3.7 [PDF pp.90–95]
- ⬜ Send Owner Packets — Phase 3.7 [PDF pp.30, 95]
- ⬜ Security Deposit Funds Detail report — Phase 3.7 [PDF p.81]
- ⬜ Aged Receivables Summary report — Phase 3.7 [PDF p.82]
- ⬜ Charge Detail report — Phase 3.7 [PDF p.82]
- ⬜ Expense Register report — Phase 3.7 [PDF p.82]
- ⬜ Income Register report — Phase 3.7 [PDF p.82]

## Properties / Units — additions (from PDF pp. 8–12)

- ⬜ Property: default bank account field (PDF p.43 "Property-Bank-Cash account relationship") — Phase 3.5
- ⬜ Unit: marketing title / description / photos / marketing rent / marketing availability — Phase 3.5 [PDF p.9]

## Universal — additions (from PDF pp. 6–7)

- ⬜ Hiding Records (distinct from soft-delete; excluded from search/reports) — Phase 3.5 [PDF p.7]
- ⬜ Powerful Search (active search, hidden toggle) — Phase 3.5 [PDF p.6]
- ⬜ Repeat Form / Field (CTRL+K, CTRL+J) — Phase 3.5 [PDF p.6]

## Accounting — Chart of Accounts

- ✅ GL accounts (list, add, edit, deactivate)
- ✅ Sub-accounts
- ✅ 61 standard accounts seeded per org
- ⬜ GL Account Permissions (who can post to what) — Phase 3.6
- ⬜ Account Offset Account field — Phase 3.6
- ⬜ Account-level note/attachment — Phase 3.7

## Accounting — General Ledger

- ✅ Double-entry posting
- ✅ Reversal-only edits
- ✅ Trial Balance report
- ✅ General Ledger report (account ledger)
- ⬜ Balance Sheet report — Phase 3.7
- ⬜ Income Statement report — Phase 3.7
- ⬜ Cash Flow report — Phase 3.7
- ⬜ Cash Flow 12-Month report — Phase 3.7
- ⬜ Account Totals report — Phase 3.7
- ⬜ Expense Distribution report — Phase 3.7
- ⬜ Chart of Accounts report — Phase 3.7

## Accounting — Receipts

- ✅ Tenant Receipt
- ✅ Owner Receipt
- ✅ Other Receipt
- ✅ Charges table auto-fill
- ✅ Auto-description
- ✅ Prepayment checkbox
- ✅ Reverse receipt
- ✅ Centered detail modal
- ⬜ Application Fee dedicated form — Phase 3.6
- ⬜ Process NSF — Phase 3.6
- ⬜ eCheck receipt — Phase 8
- ⬜ CC receipt — Phase 8
- ⬜ Auto-pay / recurring receipts — Phase 8
- ⬜ Bank-drafted receipt — Phase 8

## Accounting — Bills / Payables

- ✅ Enter Bill (multi-line)
- ✅ Two-step accrual (DR Expense / CR AP)
- ✅ Pay Bill (partial allowed)
- ✅ Bill status (Unpaid / Partial / Paid / Void)
- ⚠️  Reverse rule too strict — allow reversal after partial payment — Phase 3.6
- ⬜ Recurring Bills — Phase 3.6
- ⬜ Write Checks flow — Phase 3.6
- ⬜ Enter Credit (vendor credits) — Phase 3.6
- ⬜ Convert Work Order -> Bill — Phase 5
- ⬜ Vendor dropdown (link to real Vendor entity) — Phase 4
- ⬜ Aged Payables report — Phase 3.7
- ⬜ Bill Detail report — Phase 3.7
- ⬜ Check Register / Detail reports — Phase 3.7
- ⬜ Owner Draw — Phase 3.6
- ⬜ Tenant Payable — Phase 3.6

## Accounting — Bank Deposits

- ✅ Group receipts into batch
- ✅ All / None quick-select
- ✅ Cannot reverse (corrections via JE)
- ⬜ Process NSF on deposit — Phase 3.6
- ⬜ Deposit Register report — Phase 3.7

## Accounting — Bank Accounts

- ✅ Client Trust (Operating) <-> GL 1150
- ✅ Security Deposit Trust (Escrow) <-> GL 1160
- ✅ Bank name / routing / account #
- ✅ ACH format field (CSV / NACHA)
- ✅ List + edit modal
- ⬜ Bank Reconciliation flow (Section 37) — Phase 3.6
- ⬜ QIF Import — Phase 3.6
- ⬜ Check setup — Phase 3.6
- ⬜ ACH file generation (NACHA / CSV) — Phase 3.6
- ⬜ Check printing — Phase 3.6
- ⬜ Bank feed import — Phase 3.6
- ⬜ Bank Account Activity report — Phase 3.7
- ⬜ Bank Account Association report — Phase 3.7
- ⬜ Trust Account Balance report — Phase 3.7
- ⬜ Trust Account Detail report — Phase 3.7

## Accounting — Management Fees

- ✅ Two-tier (9% rent + 100% additional fees)
- ✅ Two-step flow (creates a Bill)
- ✅ subject_to_mgmt_fees rule
- ✅ exclude_from_mgmt_fee rule
- ✅ Flat fee override
- ✅ Minimum fee override
- ✅ Mgmt End Date
- ✅ Preview + Run + Reverse
- ⬜ Pay Owners flow (distribute remaining trust to owners via ACH) — Phase 3.6
- ⬜ Overcollection strategy setting (Credits then Receipts / vice versa) — Phase 3.6
- ⬜ Management Fee Exclusions list — Phase 3.6
- ⬜ Post GPR — Phase 3.6

## Accounting — Owner Statements

- ✅ One section per property
- ✅ Frozen snapshot model
- ✅ Beginning / Ending cash
- ✅ Running balance per transaction
- ✅ Print / Save as PDF
- ⬜ Required Reserves line — Phase 3.6
- ⬜ Prepaid Rent line — Phase 3.6
- ⬜ Property Cash Summary — Phase 3.6
- ⬜ Owner Packet customizer — Phase 7
- ⬜ Email statement to owner — Phase 7
- ⬜ Owner Statement report — Phase 3.7
- ⬜ Owner Ledger report — Phase 3.7
- ⬜ Owner Directory report — Phase 3.7

## Accounting — Financial Diagnostics

- ✅ Security Deposit Funds Mismatch
- ✅ Escrow Cash Account Mismatch
- ✅ Non-Zero Clearing Account
- ✅ Negative Balance on Fee GLs
- ⚠️  Positive Balance on Fee GLs (placeholder — needs must_clear flag) — Phase 3.6
- ✅ Trust Account 3-Way Reconciliation (real)
- ⬜ Auto-fix Refund Negative Diagnostic — Phase 3.6
- ⬜ Bank Reconciliation Lapses 60 days — Phase 3.6
- ⬜ Additional AppFolio diagnostics (7-9 total) — Phase 3.6

## Accounting — Journal Entries

- ✅ Balanced multi-line manual JE
- ✅ Live balance check
- ✅ Detail page
- ⬜ Post GPR — Phase 3.6
- ⬜ Recurring JEs — Phase 3.6
- ⬜ Journal Entry Register report — Phase 3.7

## Properties — Core

- ✅ Add / edit / soft delete
- ✅ Property types (SFR/MFR/Condo/etc.)
- ✅ Address, physical details, financial fields
- ✅ Policies (pets, smoking, lease terms, insurance, laundry)
- ✅ Photos (placeholder tab)
- ✅ Utilities tab
- ✅ Insurance tab
- ✅ Financials tab
- ✅ Taxes tab
- ✅ Expenses tab
- ✅ History tab (audit)
- ⬜ Property Groups — Phase 3.5
- ⬜ Budget tab — Phase 3.5
- ⬜ Map tab — Phase 3.5
- ⬜ Staff tab (assignments) — Phase 3.5
- ✅ Amenities tab (fee + availability) — done
- ✅ Appliances tab (condition) — done
- ✅ Improvements tab (warranty) — done
- ✅ Photos tab (upload, cover, marketing, lightbox, sort)
- ⬜ Amenities / Appliances / Improvements attachments — Phase 3.7
- ⬜ Keys tracking tab — Phase 3.5
- ⬜ Fixed Assets tab — Phase 5
- ⬜ RUBs tab — Phase 4.5
- ⬜ Statement Settings tab — Phase 3.5
- ⬜ Non-Revenue tab — Phase 3.5
- ⬜ Property Directory report — Phase 3.7
- ⬜ Property Group Directory report — Phase 3.7
- ⬜ Property Performance report — Phase 3.7
- ⬜ Rent Roll report — Phase 3.7

## Properties — Units

- ✅ Unit CRUD
- ✅ Add unit / edit
- ✅ Rent, deposit, fees
- ⬜ Unit Directory report — Phase 3.7
- ⬜ Unit Inspection report — Phase 3.7
- ⬜ Unit Vacancy Detail report — Phase 3.7

## People — Tenants

- ✅ Tenant list, add, edit
- ✅ Screening settings
- ✅ Tenant insurance tracking
- ✅ Move In / Move Out fields (partial)
- ⬜ Move In 5-step wizard — Phase 3.5
- ⬜ Move Out 5-step wizard — Phase 3.5
- ⬜ Renew Lease workflow — Phase 3.5
- ⬜ Increase Rent workflow — Phase 3.5
- ⬜ Convert to Month-to-Month — Phase 3.5
- ⬜ Additional Tenants — Phase 3.5
- ⬜ Tenant Directory report — Phase 3.7
- ⬜ Tenant Ledger report — Phase 3.7
- ⬜ Delinquency report — Phase 3.7
- ⬜ Tenant Tickler report — Phase 3.7
- ⬜ Tenant Unpaid Charges report — Phase 3.7

## People — Owners

- ✅ Owner list
- ✅ Owner ID card
- ⬜ Owner ACH setup — Phase 3.6
- ⬜ Owner Reserve Funds — Phase 3.5
- ⬜ Vendor 1099 Payer — Phase 4
- ⬜ Owner Directory report — Phase 3.7
- ⬜ Owner Portal — Phase 7

## People — Vendors

- ⬜ Full Vendor entity — Phase 4
- ⬜ Vendor insurance + expiration — Phase 4
- ⬜ Vendor insurance alerts — Phase 3.5
- ⬜ Vendor Directory report — Phase 3.7
- ⬜ Vendor Ledger report — Phase 3.7
- ⬜ Vendor Portal — Phase 7

## People — Contacts / Tags

- ⬜ Contacts — Phase 4
- ⬜ Tags (universal) — Phase 4
- ⬜ Import / export — Phase 4

## Leasing

- ⬜ Listings — Phase 7 (public)
- ⬜ Applications — Phase 4 (expand existing)
- ⬜ Screening (TransUnion / Experian / Equifax) — Phase 8
- ⬜ Lease Templates — Phase 4
- ⬜ CRM / Prospects — Phase 4
- ⬜ Guest cards — Phase 4
- ⬜ QR codes on listings — Phase 7
- ⬜ Lease Expiration report — Phase 3.7

## Maintenance

- ✅ Work orders (basic)
- ⬜ Work Order -> Bill — Phase 5
- ⬜ Recurring work orders — Phase 5
- ⬜ Inspections — Phase 5
- ⬜ Unit Turns — Phase 5
- ⬜ Projects — Phase 5
- ⬜ Purchase Orders — Phase 5
- ⬜ Inventory — Phase 5
- ⬜ Fixed Assets — Phase 5
- ⬜ Smart Maintenance (groups, dispatch, on-call, preferred vendors) — Phase 5
- ⬜ Work Order report — Phase 3.7

## Communication

- ⬜ In-app chat — Phase 6
- ⬜ SMS (Twilio) — Phase 8
- ⬜ Email mirror — Phase 6
- ⬜ Templates — Phase 6
- ⬜ Surveys — Phase 6
- ⬜ Tracking page — Phase 6
- ⬜ Letters / mail merge — Phase 3.5

## Reporting

- ✅ Trial Balance
- ✅ General Ledger
- ✅ Chart of Accounts
- ⬜ Balance Sheet — Phase 3.7
- ⬜ Income Statement — Phase 3.7
- ⬜ Cash Flow — Phase 3.7
- ⬜ Cash Flow 12-Month — Phase 3.7
- ⬜ All 45 AppFolio reports (see Section 32) — Phase 3.7
- ⬜ Custom Report Builder — Phase 3.7

## Settings

- ✅ Company settings (partial)
- ✅ Users
- ✅ Menu Permissions (built)
- ✅ Email settings
- ✅ Screening settings
- ✅ OCR settings
- ✅ Platform settings
- ⬜ Accounting settings (Key Accounts, GPR Accounts, Receipts, Check Writing, Mgmt Fee overcollection, Reports defaults) — Phase 3.6
- ⬜ Approvals settings — Phase 5
- ⬜ Property Groups settings — Phase 3.5
- ⬜ Workflow settings — Phase 3.5
- ⬜ Owner settings — Phase 3.6
- ⬜ Leasing settings — Phase 4
- ⬜ Documents settings — Phase 3.7
- ⬜ Maintenance settings — Phase 5
- ⬜ Communication settings — Phase 6
- ⬜ Risk / Tags / Affordable Housing settings — Phase 4.5
- ⬜ Auditing Center — Phase 3.6
- ⬜ GL Account Permissions (separate feature) — Phase 3.6
- ⬜ Two-step verification — Phase 3.6
- ⬜ Login history — Phase 3.6
- ⬜ My Settings (profile, notifications, signature, reply-to) — Phase 3.6

## Portals

- ⬜ Tenant Portal — Phase 7
- ⬜ Owner Portal — Phase 7
- ⬜ Vendor Portal — Phase 7
- ⬜ Crew Portal — Phase 7
- ⬜ Public Listings — Phase 7

## Billing & Subscription

- ⬜ Plans / modules / features — Phase 10
- ⬜ Stripe integration — Phase 10
- ⬜ Lifecycle enforcement — Phase 10
- ⬜ Plan-based menu gating (real) — Phase 10

## Compliance (product lines)

- ⬜ HOA — Phase 4.5
- ⬜ Affordable Housing — Phase 4.5
- ⬜ Commercial — Phase 4.5
- ⬜ RUBs (utility billing) — Phase 4.5
- ⬜ Maintenance Escrow / Capital Reserves — Phase 4.5
- ⬜ Section 8 / HAP workflow — Phase 4

## Integrations

- ⬜ Stripe (payments, eCheck, CC) — Phase 8
- ⬜ TransUnion / Experian / Equifax — Phase 8
- ⬜ Twilio (SMS, voice) — Phase 8
- ⬜ Deposit Alternatives (Rhino / Jetty) — Phase 8
- ⬜ Listing syndication (Zillow, etc.) — Phase 8
- ⬜ Bank feeds — Phase 8

## Universal Patterns (Section 8)

- ✅ Soft delete (all entities)
- ✅ Created by / at
- ✅ Updated by / at
- ⚠️  Notes (present on some — properties, leases) — expand to all — Phase 3.6
- ⬜ Attachments (every entity) — Phase 3.7
- ⚠️  Audit Log (partial coverage) — expand everywhere — Phase 3.6
- ⬜ Soft-delete reason universal — Phase 3.6

## Internal Side (ours)

- ⬜ platform_users table — Phase 9
- ⬜ Support ticket system — Phase 9
- ⬜ Time-limited customer data access — Phase 9
- ⬜ Auditing center — Phase 3.6
- ⬜ Internal team roles (Sales / Billing / Tech / Support / Dev) — Phase 9

## Native Mobile App

- ⬜ iOS + Android (React Native) — Phase 12

---

**Nothing in this section is unplanned.** Every item has a phase.


---

# SECTION 58 — DISPLAY SETTINGS (BUILT — Phase 3.5, PARTIAL)

STATUS (2026-09-22): COMPLETE for currency + date-format rendering.
The Display page saves (theme, layout mode, date format, currency,
density, number format, font size, accent, reduce motion).
The frontend currency/date sweep finished this session — every page
now calls formatMoney()/formatDate() from lib/money.ts. Currency
changes persist. Date format changes re-render every money/date
display in the app.

STILL PENDING (Phase 3.5.5): layout mode, theme (dark CSS), density,
font size, accent, reduce motion are saved but no page or stylesheet
consumes them yet. Behavior-preserving retrofit queued.

One page under Settings → Display. Per-user preferences.
Infrastructure built once, every page inherits both layouts/themes.

Route: /dashboard/settings/display
Menu key: SETTINGS.DISPLAY (added to menu_keys.py in Phase 3.5)

Storage: new table user_display_preferences
- id, user_id (unique), organization_id
- layout_mode: "TABS" | "VERTICAL" (default TABS)
- theme: "LIGHT" | "DARK" | "AUTO" (default LIGHT)
- density: "COMPACT" | "COMFORTABLE" | "SPACIOUS" (default COMFORTABLE)
- date_format: "US" | "ISO" | "EU" (default US)
- number_format: "US" | "EU" | "SPACE" (default US)
- font_size: "SMALL" | "NORMAL" | "LARGE" (default NORMAL)
- accent_color: string (nullable)
- reduce_motion: boolean (default false)
- created_at, updated_at

API: GET/PUT /api/settings/display

Frontend:
- Display page: /dashboard/settings/display
- DisplayContext (reads layout_mode, theme, and all future settings)
- LayoutContext (reads layout_mode; property detail and every
  multi-section page renders either tabs or vertical)
- ThemeContext (reads theme; sets data-theme on <html>)
- Tailwind config + globals.css extend for dark theme

Behavior:
- Layout mode: "Tabs" = sections at top; "Vertical" = stacked in a
  long scroll (AppFolio-style), with sticky sidebar nav
- Theme: "Light" = current; "Dark" = dark backgrounds, light text;
  "Auto" = follows OS
- All other settings are wired up the same way (one column each)

Build order:
- Phase 3.5 — build table + endpoint + settings page +
  DisplayContext + ThemeContext; wire layout_mode + theme
- Phase 3.6 — density, date format, number format
- Phase 3.7 — font size, accent color, reduce motion

Default for new users: Tabs + Light (matches today's look)

---

# SECTION 59 — PER-ORG CURRENCY (BUILT — Phase 3.5, PARTIAL)

STATUS (2026-09-22): COMPLETE. The organizations.currency column is
persisted for ADMIN/OWNER by PUT /api/settings/display. Custom
currencies CRUD is BUILT (Section 68). The Display page currency
dropdown fetches the org's real currency list from
GET /api/settings/currencies — custom currencies appear. A real bug
was fixed this session: the save payload now includes `currency`, so
changing it actually persists.

Every page now uses formatMoney() from lib/money.ts. The frontend
sweep is DONE (21 files touched, 3 commits: e9f569c, 90500b0,
3d52105). No hardcoded $ remains anywhere in the codebase.

Each customer organization operates in ONE currency.
No exchange, no conversion, no cross-currency transactions.

Org picks from: USD, EUR, GBP, INR, AUD, CAD, NZD, SGD, AED, and
more later. All amounts within that org are in that currency.

Storage:
- organizations.currency (VARCHAR(3), default "USD")

Formatting:
- A single helper src/lib/money.ts with formatMoney(amount)
- Reads the org's currency from CurrencyContext
- Uses Intl.NumberFormat with the correct locale for the currency:
    * USD -> "en-US" -> $1,234.56
    * INR -> "en-IN" -> ₹1,23,456.78 (Indian numbering)
    * GBP -> "en-GB" -> £1,234.56
    * EUR -> "de-DE" -> 1.234,56 €

Refactor:
- Every existing `toLocaleString("en-US", { currency: "USD" })` call
  is replaced with `formatMoney(...)`.
- ~100+ call sites across the frontend.

Where the customer sets it:
- On signup (default based on their locale)
- Or in Settings -> General -> Currency (editable once)

Why per-org, not per-user:
- A PM company + its tenants/owners are all in one country -> one
  currency. Changing per-user would confuse reports.

Build order:
- Phase 3.5 — organizations.currency column + migration +
  CurrencyContext + money.ts helper + Settings -> General currency
  dropdown
- Phase 3.5 — sweep all pages replacing hardcoded USD formatting
- Level 3 (true multi-currency with exchange rates) NOT planned.
  Deferred indefinitely; only if a real client asks.

Effort: ~1 session for the migration + helper + Settings. ~1 session
for the frontend sweep.

STATUS (2026-09-21): Org-level currency (organizations.currency) is BUILT.
The dropdown on the Display page persists for ADMIN/OWNER.
Custom (customer-addable) currencies are BUILT — see Section 68.

---

# SECTION 60 — PROPERTY AMENITIES (BUILT — Phase 3 Step 3a)

AppFolio-parity fields:
- Name (required)
- Category (Building / Unit / Outdoor / Community / Other)
- Notes
- fee_amount (money — optional)
- availability_status: INCLUDED | EXTRA_FEE | NOT_AVAILABLE
- delete_reason (soft-delete pattern)

Table: property_amenities
- id, organization_id, property_id
- name, category, notes
- fee_amount NUMERIC(14,2)
- availability_status VARCHAR(30)
- is_active, delete_reason, created_by_id, timestamps

Migration: e5d4a58b8e85_add_property_amenities
(parity fields added by 59a25b856f18)

Endpoints under /api/properties/{property_id}/amenities:
- GET    ""                    list
- POST   ""                    create
- PATCH  /{amenity_id}         update
- DELETE /{amenity_id}         soft delete

Frontend:
- src/lib/propertyAmenities.ts
- src/components/property/AmenitiesTab.tsx
- Renders inline in the Property Detail page

Remaining gap: Attachments (Phase 3.7 — universal attachments).

---

# SECTION 61 — PROPERTY APPLIANCES (BUILT — Phase 3 Step 3b)

AppFolio-parity fields:
- Name (required)
- Brand
- Model #
- Serial #
- Purchase date
- Purchase price
- Warranty expiration
- Condition: NEW | GOOD | FAIR | NEEDS_REPAIR
- Notes
- delete_reason

Table: property_appliances
- id, organization_id, property_id
- name, brand, model_number, serial_number
- purchase_date DATE, purchase_price NUMERIC(14,2)
- warranty_expires DATE
- condition VARCHAR(30)
- notes, is_active, delete_reason, created_by_id, timestamps

Migration: dadbb391cc03_add_property_appliances
(condition + delete_reason added by 59a25b856f18)

Endpoints under /api/properties/{property_id}/appliances:
- GET    ""                     list
- POST   ""                     create
- PATCH  /{appliance_id}        update
- DELETE /{appliance_id}        soft delete

Frontend:
- src/lib/propertyAppliances.ts
- src/components/property/AppliancesTab.tsx

Remaining gap: Attachments (Phase 3.7).

---

# SECTION 62 — PROPERTY IMPROVEMENTS (BUILT — Phase 3 Step 3c)

AppFolio-parity fields:
- improvement_date (required)
- description (required, max 500)
- cost
- contractor
- category (Kitchen / Bath / Roof / HVAC / Flooring / Electrical /
  Plumbing / Exterior / Other)
- warranty_expires
- notes
- delete_reason

Table: property_improvements
- id, organization_id, property_id
- improvement_date DATE, description VARCHAR(500)
- cost NUMERIC(14,2)
- contractor VARCHAR(200), category VARCHAR(60)
- warranty_expires DATE
- notes, is_active, delete_reason, created_by_id, timestamps

Migration: 35529ce17750_add_property_improvements
(warranty_expires + delete_reason added by 59a25b856f18)

Endpoints under /api/properties/{property_id}/improvements:
- GET    ""                       list (newest first)
- POST   ""                       create
- PATCH  /{improvement_id}        update
- DELETE /{improvement_id}        soft delete

Frontend:
- src/lib/propertyImprovements.ts
- src/components/property/ImprovementsTab.tsx

Remaining gaps: Attachments (Phase 3.7) and Vendor entity link
(Phase 4).

---

# SECTION 63 — PHASE 3 PARITY MIGRATION (BUILT — 59a25b856f18)

Closed the small gaps found in the AppFolio parity audit.

Added:
- property_amenities.fee_amount
- property_amenities.availability_status
- property_amenities.delete_reason
- property_appliances.condition
- property_appliances.delete_reason
- property_improvements.warranty_expires
- property_improvements.delete_reason
- gl_accounts.must_clear (boolean, default 0)

Purpose:
- fee/availability/condition/warranty close the AppFolio feature
  gaps in the three Phase 3 tabs.
- delete_reason universally supports the soft-delete-with-reason
  pattern (UI for it comes in Phase 3.5).
- must_clear powers the REAL "Positive Balance on Fee GL Accounts"
  diagnostic (was a placeholder; the check will be wired in
  Phase 3.6).

Downgrade reverses all of the above.




---

# SECTION 49 — GIT WORKFLOW

Repo: https://github.com/yasirskhan/property-platform (private)
Local folder: C:\Projects\property-platform

**Commit + push after every working module.**

Standard commands (from C:\Projects\property-platform):

    git add .
    git commit -m "<short description>"
    git push

**Commit message style:**
    Phase 2 Step 6 complete: Bills (two-step accrual, enter/pay/reverse,
    AP account 2100); centered modals on Bills + Receipts; smart back
    on Trial Balance; master doc update

Rules:
- One commit per completed module. Don't mix unrelated changes.
- Never commit without a message.
- Never force-push (git push --force). Ever.
- If push fails with "no upstream branch" -> git push -u origin main
- If push fails with auth -> a browser window opens for GitHub login.
- If push fails with "rejected (non-fast-forward)" -> someone
  (probably you) pushed from elsewhere; run git pull --rebase first.

**What gets committed:**
- All source code (backend/app, frontend/src)
- Alembic migrations (backend/alembic/versions)
- PROJECT_MASTER.md (docs)
- Config files (.gitignore, requirements.txt, package.json)
- NOT: venv/, node_modules/, .next/, *.db, uploads/

The .gitignore already excludes the big/regenerable stuff.

**Before committing, DB backup:**
    cd C:\Projects\property-platform\backend
    Copy-Item property_platform.db "property_platform.db.backup-YYYY-MM-DD-phase2-stepN"

Silent = success. Do this before any risky migration.

**Git identity** (set once, already done):
    git config user.name  "Yasir Khan"
    git config user.email "yasirskhan@users.noreply.github.com"

**When the master doc changes:**
Commit the code AND the doc together, or as a separate commit —
either is fine. Never push code without pushing the doc update
if both changed in the same session.

---



---

# SECTION 64 — PROPERTY PHOTOS (BUILT — Phase 3 Step 3d)

Upload, view, and manage photos on a property.

AppFolio-parity fields:
- url (path under /uploads)
- filename (UUID-based server filename)
- original_name (user's original filename)
- content_type (image/jpeg, etc.)
- size_bytes
- caption (optional)
- is_marketing (flag for listings / public gallery)
- is_cover (only one per property, enforced)
- sort_order (manual drag order)

Table: property_photos
- id, organization_id, property_id
- url VARCHAR(500), filename VARCHAR(200)
- original_name VARCHAR(300), content_type VARCHAR(80),
  size_bytes INTEGER
- caption VARCHAR(500)
- is_marketing BOOLEAN (default false)
- is_cover BOOLEAN (default false)
- sort_order INTEGER (default 0)
- is_active, delete_reason, created_by_id, timestamps

Migration: 00bc0d143eac_add_property_photos
(down_revision = 59a25b856f18)

Endpoints under /api/properties/{property_id}/photos:
- GET    ""                 list (cover first, then sort_order, then id)
- POST   ""                 create
- PATCH  /{photo_id}        update (caption / marketing / cover / sort)
- DELETE /{photo_id}        soft delete

Cover enforcement:
- When a photo is created or updated with is_cover=true,
  the server automatically unsets is_cover on every other photo
  of the same property. Exactly one cover at any time.

Frontend:
- src/lib/propertyPhotos.ts
- src/components/property/PhotosTab.tsx
- Grid of thumbnails; each shows ★ Cover and Marketing badges
- "+ Upload Photos" button accepts multiple files at once
- Two-step upload: apiUpload(file) -> then createPhoto(...)
- Click a photo -> lightbox with large view
- Per-photo actions: Edit (caption + flags), Set cover,
  Mark/Unmark marketing, Remove (styled confirm modal)
- Grid orders by: is_cover desc, sort_order asc, id asc

Remaining gaps on this tab:
- Image editor (crop / rotate) — Phase 3.5
- Drag-to-reorder sort_order UI — Phase 3.5 (backend column exists)
- Bulk-select multiple photos for one-shot actions — Phase 3.5

Menu: none — Photos is a tab inside Property Detail.


# SECTION 65 — HANDOFF PROCEDURE (HOW TO CONTINUE IN A NEW CHAT)

This section is the complete, self-contained procedure for
starting a new chat and picking up exactly where we left off.
Follow it every time.

## What you paste in the new chat (in this order)

1. The handoff prompt (from Section 41):

       I'm continuing to build a property management platform (AppFolio clone).

       Read this PROJECT_MASTER.md file fully. It has three parts:
       - Part A: Current state
       - Part B: Next action
       - Part C: Full reference

       Then continue from the immediate next action listed in Part B1.

       Rules you must follow:
       - I am a non-coder. Never ask me to write code.
       - Give whole files, not fragments. I select-all, delete, paste, save.
       - Label every command BACKEND or FRONTEND.
       - One step at a time. Wait for me to run and report back.
       - If I paste an error, fix it and give the next command.
       - Backend venv is at backend\venv (not .venv). DB is property_platform.db.
       - Role values are UPPERCASE. Menu keys are UPPERCASE and dotted.
       - Every GL posting goes through post_transaction().

2. The whole PROJECT_MASTER.md — paste it right after.

3. The whole APPFOLIO_PARITY_CHECKLIST.json — paste it right after that.

That's three pastes. That's it.

## What each file is for (so the new agent understands)

### PROJECT_MASTER.md (the doc)

The full history and reference. It contains:

- Part A — current state (what we've built, what's next)
- Part B — immediate next action (what to do right now)
- Part C — 65+ sections of full reference (every module, every
  rule, every design decision)

How it gets updated: via a Python script that replaces blocks
(find-and-replace on # SECTION markers) or appends new sections
before

# SECTION 67 - SESSION CLOSE CHECKLIST (MANDATORY)

Every session that changes the project MUST end with these steps,
in this exact order. No exceptions. No "I'll do it next time."

## The rule

If you finish a module without touching BOTH the master doc AND
the parity JSON, the session is NOT complete. Do not push.

## The steps

### 1. Update the master doc

Script names (in backend/):

    update_master_p1.py   -- content edits (blocks, sections)
    update_master_p2.py   -- new section appends

Both scripts write the whole updated file. Never hand-edit
PROJECT_MASTER.md. Delete the scripts after running them.

What goes in the master doc:
- Part A1 -- current state ("last completed work")
- Part B1 -- immediate next action
- Section 38 -- build order status
- Section 57 -- parity audit summary
- Any new Section for a new module

### 2. Update the parity JSON

File:  docs/APPFOLIO_PARITY_CHECKLIST.json

Two ways to update:

    (a) small changes -- open in VS Code, edit by hand
    (b) bulk changes  -- write  update_checklist.py  in backend/,
                         run it, then delete it

What goes in the JSON:
- Flip completed items from "scheduled" to "built"
- Add any new features that were not tracked
- Every new item MUST have a status and (if scheduled) a phase
- Never remove an item -- mark it "built" or add a note

### 3. Verify

    python check_parity.py          -> must print CLEAN
    count sections in the master doc -> must equal last section number
    git status                       -> must show only the files you meant to commit

If check_parity.py prints FAILURES, the session is not done.

### 4. Delete one-off scripts

Remove from backend/:

    update_master_p1.py
    update_master_p2.py
    update_checklist.py
    fix_*.py
    rebuild_*.py
    patch_*.py
    add_*.py

They are gitignored, but delete them anyway. Do not let them pile up.

### 5. Regenerate the FILE CATALOG (if new files were added or renamed)

Run:

    cd backend
    python generate_file_catalog.py

This rewrites docs/FILE_CATALOG.md with an up-to-date
inventory of every backend Python file and every frontend
TS/TSX file - classes, routes, exports, migration chain.

Run this step if the session added, renamed, or deleted
any source files. Skip only if the session was a pure edit
to existing files with no new filenames.

This keeps Section 69 (FILE MAP) and FILE_CATALOG.md in
sync with reality, so the next session never has to guess
where something lives.

### 6. Push

Milestone commits -- open PowerShell, cd to project root:

    git add .
    git commit -m "<descriptive message>"
    git push

Routine saves -- double-click push.bat on the desktop.

push.bat refuses to push backups (.backup-*, *.bak) or one-off
scripts (update_*, fix_*, rebuild_*, patch_*). If it aborts,
delete those files and re-run.

### 7. Report back

Say: "Session closed. HEAD = <hash>. check_parity.py CLEAN."

This is the signal that the session is truly complete.

## Why this matters

The master doc, the JSON, and the code drift apart quickly if any
one of them is updated without the others. Every prior session
that forgot one of them created a mismatch that took a later
session to untangle. Do all three, in order, every time.

## Compatibility rule (added 2026-09-22)

No new Section, item, or flag may remove, disable, rename, re-scope,
or change the default of an existing feature. Sections 70+ are
additive. Existing features keep their current behavior, availability,
and default state. If a change would affect an existing feature's
behavior, it must be scheduled as its own item with its own migration
-- never folded silently into a new section.

## Complete-page rule (revised 2026-09-23)

`docs/FEATURE_REGISTRY.md` is the page/capability surface contract. It records what exists, what is missing, and which independently releasable capabilities have access metadata. Routine fields, columns, filters, labels, sorting, and ordinary form controls do not need individual release gates.

`check_parity.py` verifies planning/registry/route consistency. A CLEAN result does **not** prove that a workflow works. Behavioral confidence comes from the automated checks in Section 84.

## Primitives rule## Primitives rule (added 2026-09-22)

Every page uses the shared primitives: money() / formatMoney(),
formatDate(), and useDisplay(). No hardcoded $, "USD", "MM/DD/YYYY",
or hardcoded theme colors. Existing pages are retrofitted once in
Phase 3.5.5 (Compatibility Pass) -- behavior-preserving.

## Gating rule (revised 2026-09-23)

Use Hybrid Capability Gating from Sections 70 and 80. Pages and major capabilities receive release gates only when they can reasonably be released, disabled, beta-tested, sold, or granted independently. Routine fields, columns, filters, labels, sorting, and form controls do not get independent release gates. Backend enforcement is authoritative for entitlements and permissions.

## What NOT to do## What NOT to do

- Do not push without running check_parity.py.
- Do not update the master doc without updating the JSON.
- Do not update the JSON without updating the master doc.
- Do not hand-edit PROJECT_MASTER.md.
- Do not commit backup files or one-off scripts.
- Do not skip the push just because "nothing changed" -- if nothing
  changed, you did not do any work this session.
- Do not remove, disable, rename, re-scope, or change the default of
  any existing feature.


# SECTION 68 — CUSTOM CURRENCIES (BUILT — Phase 3.5, PARTIAL)

STATUS (2026-09-22): COMPLETE. Table, model, router, CRUD page, 9
seeded system currencies per org. The Display page currency dropdown
fetches the org's real list from GET /api/settings/currencies —
custom currencies appear in the dropdown. Every page uses
formatMoney() from lib/money.ts (frontend sweep complete).

Customers can pick a currency, and can add their own.

## What exists

Two concepts:

1. **Organizations.currency** — the ONE currency the org uses.
   Stored on `organizations.currency`. VARCHAR(3), default "USD".
   Set by ADMIN/OWNER on the Display page. Persisted via
   `PUT /api/settings/display`.

2. **The currencies list** — what the org can pick from.
   Stored in the `currencies` table. One row per currency per org.
   Seeded with 9 system currencies on first migration. Customer
   can add more (custom rows) from the Currencies page.

## The currencies table

    id, organization_id, code, name, symbol, locale,
    decimal_places, is_system, is_active, timestamps

- `code`: 3 uppercase letters (USD, PKR)
- `symbol`: displayed char ($, ₹)
- `locale`: BCP-47 (en-US, en-IN) — tells Intl.NumberFormat how to format
- `is_system`: True means seeded default, cannot be deleted
- `is_active`: soft delete — False means hidden from pickers

Unique on (organization_id, code).

## Seeded defaults (migration 8e1243432666)

USD, EUR, GBP, INR, AUD, CAD, NZD, SGD, AED.

## Endpoints (under /api/settings/currencies)

- GET    ""        list all currencies for the org
- POST   ""        add custom currency (ADMIN/OWNER)
- PATCH  /{id}     edit name/symbol/locale/decimals/is_active (ADMIN/OWNER)
- DELETE /{id}     soft delete (ADMIN/OWNER). Refuses system rows and
                   the org's current currency.

## Rules

- No exchange, no conversion. Currency is a display/label concept.
- Org-level, not per-user.
- Cannot delete a system currency.
- Cannot delete the currency currently selected by the org.

## Frontend

- Page: /dashboard/settings/currencies
- Menu key: SETTINGS.CURRENCIES
- Backed by CurrencyContext (list not fetched there yet — the page
  fetches directly). Wired to the sidebar via menuConfig.ts.

## Next steps for this area

- Frontend sweep: replace hardcoded `$` / `"USD"` in existing pages
  with `formatMoney()` from lib/money.ts.
- CurrencyContext should expose the currency list too so any page
  can render a picker without a second fetch.
- Add a "change currency" confirm dialog: warn the user that all
  amounts re-render at the new currency symbol (no conversion).


# SECTION 69 — FILE MAP (where everything lives)

**Root:** C:\Projects\property-platform\

## Companion document: docs/FILE_CATALOG.md

`FILE_CATALOG.md` is an auto-generated inventory of every
source file in the project - classes, routes, exports, and
the migration chain, all extracted from the real code.

Regenerate it any time with:

    cd backend
    python generate_file_catalog.py

Section 67 requires regenerating it at the end of any session
that added, renamed, or deleted source files.

**Use this section (69) to know WHERE things live.
Use FILE_CATALOG.md to know WHAT is inside each file.**

## Documentation

    docs\PROJECT_MASTER.md                 this file
    docs\APPFOLIO_PARITY_CHECKLIST.json    coverage tracker (385 items)
    docs\appfolio.pdf                      source PDF

## Backend (Python / FastAPI) — root is backend\

    app\main.py                            FastAPI app + router registration
    app\core\config.py                     settings loader
    app\core\database.py                   SQLAlchemy Base + get_db
    app\core\security.py                   JWT + bcrypt

    app\constants\menu_keys.py             canonical menu keys + role defaults

    app\models\                            one file per DB table
      user.py                                Organization + User
      user_display_preference.py             display settings (Section 58)
      currency.py                            currencies (Section 68)
      property.py, unit.py, lease.py
      gl_account.py, gl_transaction.py, gl_entry.py
      receipt.py, bill.py, deposit.py, bank_account.py
      management_fee_run.py, owner_statement.py
      menu_permission.py, user_permission.py, sidebar_preference.py
      property_amenity.py, property_appliance.py,
      property_improvement.py, property_photo.py

    app\routers\                           one file per feature area
      auth.py                                login/signup/get_current_user
      settings_display.py                    GET/PUT /api/settings/display
      currencies.py                          CRUD /api/settings/currencies
      properties.py, units.py, leases.py, payments.py
      users.py, work_orders.py
      taxes.py, utilities.py, insurance.py, expenses.py,
      tenant_insurance.py
      menu_permissions.py, sidebar_preference.py
      gl_accounts.py, gl_transactions.py, gl_reports.py
      receipts.py, bills.py, deposits.py, diagnostics.py
      management_fees.py, owner_statements.py
      bank_accounts.py, journal_entries.py
      property_amenities.py, property_appliances.py,
      property_improvements.py, property_photos.py

    app\schemas\                           Pydantic in/out shapes
    app\services\                          business logic
      gl_posting.py                          post_transaction()
      receipt_posting.py, bill_posting.py
      deposit_posting.py, management_fee_posting.py
      owner_ledger.py, owner_statements.py
      diagnostics.py, menu_resolver.py

    alembic\versions\                      migration files
      ... many prior migrations ...
      8c2e766863c0_add_org_currency.py              (currency column)
      521035d0e411_add_user_display_preferences.py  (display table)
      15d92d8a1eea_add_settings_menu_keys.py        (SETTINGS menu seeds)
      8e1243432666_add_currencies_table.py          (currencies table + seed)

    check_parity.py                         parity enforcer
    property_platform.db                    SQLite database
    venv\                                   virtualenv (activate: .\venv\Scripts\Activate.ps1)

## Frontend (Next.js 16) — root is frontend\

    src\app\dashboard\                     all dashboard pages (App Router)
      layout.tsx                             wraps CurrencyProvider + DisplayProvider + MenuProvider
      settings\display\page.tsx             Display settings page
      settings\currencies\page.tsx          Currencies CRUD page
      settings\permissions\page.tsx         Menu Permissions page
      settings\sidebar\page.tsx             Sidebar customization
      accounting\...                        receipts, bills, deposits, etc.
      properties\[id]\                      property detail
      ... (40 routes total)

    src\components\shell\
      Sidebar.tsx                            renders resolved menu + ICON_MAP
      TopBar.tsx

    src\contexts\
      CurrencyContext.tsx                    loads /api/settings/display, exposes currency + prefs
      DisplayContext.tsx                     applies theme/density/font to <html>
      MenuContext.tsx                        loads /api/menu/me

    src\lib\
      money.ts                               formatMoney() + formatDate()
      menuConfig.ts                          MENU_ENTRIES (labels + icons + hrefs)
      api.ts                                 apiGet/apiPost/apiPut/apiDelete

## Git + tooling

    .gitignore                              excludes venv\, node_modules\, .next\, *.db,
                                            *.backup-*, update_*.py, fix_*.py, rebuild_*.py
    push.bat                                (on Desktop) one-click git push

## Where to look for what

    "What's next?"                     -> PROJECT_MASTER.md Part B1
    "What's built vs scheduled?"       -> docs/APPFOLIO_PARITY_CHECKLIST.json
    "Is the project consistent?"       -> python check_parity.py (must print CLEAN)
    "Where does feature X live?"       -> this section (69)
    "How do I hand off to a new chat?" -> Section 65 + Section 67
    "What's the accounting spine?"     -> Section 19 + Section 44
    "Where's the display/currency spec?" -> Sections 58 + 59 + 68


. Never edited by hand.

### APPFOLIO_PARITY_CHECKLIST.json (the checklist)

The complete inventory of every AppFolio feature and its status:

- built — we have it and it works
- in_progress — being built now
- scheduled — has a phase assigned

Every scheduled item MUST have a phase field.
No item can be unplanned.

Why it exists: so nothing gets lost. If a feature isn't in the
checklist, it doesn't exist as far as the process is concerned.
When you ask "does this match AppFolio?", the checklist answers
with certainty.

How it gets updated: by editing the JSON directly (adding new
items, changing statuses).

### check_parity.py (the enforcement script)

Reads the checklist, prints a summary, and fails (exit code 1)
if:

- Any item has status unplanned or planned_no_phase
- Any scheduled item is missing a phase

How it gets run: `python check_parity.py` from the backend
folder, venv active. Must print CLEAN before every push.

## The three workflows (how each thing gets updated)

### Workflow 1 — Update the master doc

Pattern: Two small scripts (part 1 and part 2) that either
replace a block of the doc or append new sections before

Why two scripts: the doc is 85+ KB. Pasted as one giant script,
the paste truncates. Split into two, each part is small enough
to paste safely.

Steps:

1. In backend, create `update_master_p1.py` — a Python script
   that:
   - Reads PROJECT_MASTER.md
   - Replaces a block between two markers (# PART A ... # PART B,
     for example)
   - Writes the file back
2. Run it: `python update_master_p1.py`
3. Create `update_master_p2.py` — a second script that:
   - Appends new sections before # END OF PROJECT_MASTER.md
4. Run it: `python update_master_p2.py`
5. Verify:
       Select-String -Path ...\PROJECT_MASTER.md -Pattern "^# SECTION" | Measure-Object | Select-Object -ExpandProperty Count
   Section count must equal the last section number.
6. Delete the scripts:
       Remove-Item update_master_p1.py, update_master_p2.py
7. Push: double-click push.bat

Common pitfalls:

- Marker not found -> the exact text in the doc doesn't match
  what the script expects. Fix = read the actual text on disk
  and match it exactly.
- Duplicate sections -> running the append script twice.
  Fix = a small cleanup script that removes the second
  occurrence.

Where the script lives: in backend\ at the project root.
Never committed — added to .gitignore.

### Workflow 2 — Update the parity checklist

Pattern: Open the JSON in VS Code, add/edit items, save.

Steps:

1. `code C:\Projects\property-platform\docs\APPFOLIO_PARITY_CHECKLIST.json`
2. Find the item you want to change (Ctrl+F the id)
3. Change "status" or "phase"
4. To add a new item, copy an existing item and edit its fields
5. Save
6. Verify: `python check_parity.py` — must still print CLEAN
7. Push: double-click push.bat

JSON item format:

    {
      "id": "properties.tabs.photos",
      "area": "Properties / Tabs",
      "feature": "Photos tab (upload, cover, marketing, bulk, captions, sort)",
      "status": "built",
      "phase": "3d"
    }

- id — unique, dotted, lowercase (e.g. accounting.receipts.process_nsf)
- area — the module (e.g. Accounting / Receipts)
- feature — human description
- status — built, in_progress, scheduled
- phase — required if status is scheduled (e.g. 3.5, 4, 5, 7, 8)

Rule: if you build a feature and don't update the checklist,
check_parity.py still says CLEAN — but it's lying. The checklist
is only as good as its upkeep.

### Workflow 3 — Push to GitHub

Pattern: push.bat on the desktop. One double-click. Done.

What push.bat does:

1. cd into C:\Projects\property-platform
2. `git add .` — stage everything that changed
3. `git commit -m "auto-push <date> <time>"` — commit with a timestamp
4. `git push` — send to GitHub
5. Prints `DONE. Everything is on GitHub.` on success
6. Waits for a keypress before closing

When to use it: always, unless you want a custom commit message.

When to use a custom message: for significant milestones, open
PowerShell, cd C:\Projects\property-platform, then:

    git add . ; git commit -m "Phase 3 complete: Photos tab + parity checklist" ; git push

What's NOT pushed (via .gitignore):

- property_platform.db and backups
- venv\, node_modules\, .next\
- One-off scripts: update_master*.py, fix_*.py, add_*.py,
  patch_*.py, rebuild_*.py
- __pycache__

Common errors:

- Everything up-to-date -> nothing changed, but it still pushed
  (safe)
- rejected (non-fast-forward) -> someone else pushed. Run
  `git pull --rebase` then push.bat again.
- Auth prompt -> GitHub opens a browser for login. Sign in once,
  it remembers.

## Before every push, this checklist

1. `python check_parity.py` -> must say CLEAN
2. If a feature was completed -> update its checklist item to built
3. If a new feature was added -> add it to the checklist with
   status + phase
4. If a phase was completed -> update Part B1 of the master doc
5. Delete any one-off scripts from backend\
6. Double-click push.bat

If all six are done, nothing gets lost. Ever.

## What to paste next time (recap)

Three pastes, in this order:

1. The Section 41 handoff prompt (above)
2. The entire PROJECT_MASTER.md
3. The entire APPFOLIO_PARITY_CHECKLIST.json

The new agent reads everything, follows the rules, starts from
Part B1, and uses the three workflows above to keep everything
current.


# SECTION 70 — HYBRID CAPABILITY GATING (DESIGNED)

The platform uses **Hybrid Capability Gating**. Pages and major capabilities may have release gates. Ordinary fields, columns, filters, labels, sort orders, and routine form controls do not get independent gates.

A gate exists only when the item can reasonably be released, disabled, beta-tested, sold, or granted independently.

## Five independent access concerns

1. **Release control** — is this code ready to be exposed? Controlled by us through HIDDEN / BETA / ROLLOUT / ALL_ORGS.
2. **Commercial entitlement** — does the customer's plan include the capability?
3. **Organization configuration** — does the customer's Admin/Owner want the capability enabled, where customer choice is meaningful?
4. **Authorization / permission** — may this role/user perform the operation? Backend enforcement is authoritative.
5. **User presentation preference** — may the user hide this item from their own UI? Presentation only, never security.

Each concern is optional per capability. A non-applicable concern passes automatically.

    effective_access =
        release_allowed
        AND entitlement_allowed_if_required
        AND org_enabled_if_configurable
        AND permission_allowed_if_permissioned
        AND user_visible_if_hideable

**UI hiding is never security.** Protected endpoints/services independently enforce entitlement and permission requirements.

## Registry metadata

The Feature Registry records, where applicable:

    release_gate
    entitlement
    org_configurable
    permission_key
    user_hideable

Release state, plan entitlements, org settings, permissions, and user preferences remain separate storage/models even when displayed together in the registry.

# SECTION 71# SECTION 71 — SETTINGS UNIVERSE (DESIGNED)

The full catalog of every setting across the platform, grouped by
section, with its scope and who can change it.

## Scopes

- **org** — one value per organization, set by Admin (and Owner).
  Applies to everyone in the org.
- **user** — one value per user, set by the user themselves.
- **property** — one value per property, set by Admin/Owner.
- **portal** — one value per portal (Tenant/Owner/Vendor/Crew).

## Who can change what

- **org** settings: ADMIN always; OWNER for most; MANAGER for some
  (configurable via the Role Matrix, Section 42).
- **user** settings: the user themselves.
- **property** settings: ADMIN, OWNER.
- **portal** settings: ADMIN, OWNER.

## The catalog

### Identity / Branding (org)

Company Name, Tagline, Logo, Favicon, Address (line 1, line 2, city,
state, zip, country), Phone, General Email, Support Email, Billing
Email, Website, Legal Name, DBA, Tax ID / EIN, Business Hours, Time
Zone, Owner Packet cover letter text.

Logo spec: recommended 400×100px, auto-scaled with `max-height`,
aspect ratio preserved, never cropped or stretched, fallback to
company name text if no logo.

Where each field shows: portal headers, sidebar, email headers,
invoice/bill/statement PDFs, letters, public listings (see Section 72).

### Language & Locale (org, with user override)

Default Language (English, Spanish, etc.), Date Format (US / ISO / EU),
Number Format (US / EU / Space), Currency (Section 59), First Day of
Week (Sunday / Monday), Measurement System (Imperial / Metric).

### Accounting (org)

Fiscal Year Start Month, Accounting Basis (Accrual default | Cash) —
report layer only, Key Accounts (each default GL account), GPR
Accounts, Receipts application order (oldest first / GL order /
manual), Check Numbering, Management Fee defaults, 1099 settings,
Approval thresholds.

### Operations (org)

Business Hours, Weekend / Holiday Calendar, Default Lease Term,
Default Application Fee, Default Screening Criteria, Late Fee
defaults, Delinquency aging buckets, Work Order priorities and SLAs.

### Security (org, feature-flagged)

Two-Factor Authentication (always / optional / never), Session
Timeout (minutes of inactivity before logout; default off until org
turns it on), Idle Warning (minutes before logout), Maximum Session
Length (hard cap), Concurrent Sessions Allowed (1 / N / unlimited),
IP Allowlist, Password Policy (min length, complexity), Login History
(on/off), Active Sessions (view and revoke).

### Notifications (org + user)

Which events send emails, Who receives them, SMS on/off, Reply-to
address, Signature (per-user), Quiet hours (per-user).

### Documents (org)

Invoice template, Email templates (per event), Statement template,
Letter templates, File retention policy.

### Integrations (org)

SMTP (built), SMS provider, Screening provider (built), Payment
processor (Stripe), Bank feeds (Plaid), Listing syndication partners,
Webhook endpoints, API keys.

### Data (org)

Export preferences (default CSV / Excel / Both — see Section 72),
Backup Schedule (frequency, time, retention, destination),
Audit log retention (default 1 year, configurable 30 days to forever).

### Display (user)

Layout mode (Tabs / Vertical), Theme (Light / Dark / Auto), Density
(Compact / Comfortable / Spacious), Date format, Number format,
Font size, Accent color, Reduce motion.

### My Settings (user)

Profile (name, email, phone, photo), Password, Two-factor, Login
history, Active sessions, Notification preferences, Language
override, Export format override.

### Per-property (org)

Property-specific bank account, Property-specific statement format,
Property-specific late fee policy, Property-specific default GL
accounts, Per-property logo (feature-flagged).

### Per-portal (org)

Logo, colors, welcome text, enabled features for each portal
(Tenant / Owner / Vendor / Crew). Feature-flagged.

## The rule

Every setting is scoped. Every setting declares who can change it.
No setting is ambiguous. The Settings → Features page (Section 70)
lists toggles that gate the optional settings. Turning a feature off
removes its settings from the UI without losing data.

## Where this lands in the plan

- Company branding + time zone: Phase 3.6
- Display settings: built (Phase 3.5, partial)
- Security settings: Phase 4
- Notifications: Phase 6
- Documents templates: Phase 3.7
- Integrations: Phase 8
- Data (export, backup, retention): Phase 4
- Per-property / per-portal branding: Phase 3.6 / Phase 7


# SECTION 72 — DOCUMENTS & EXPORTS (DESIGNED)

Every report, every list, every generated document. Print, PDF, and
export-format controls. Customizable templates. Per-role exports.

## Reports and lists

Every report and every list a user can see has:
- **Print** button — opens the browser's print dialog with a print-
  optimized layout (no sidebar, no top bar, no buttons).
- **Download PDF** button — server-side PDF, consistent across
  browsers.
- **Export** button — CSV or Excel, depending on the org's setting.

One export button per report. Not two, not a dropdown of everything.
The format is controlled by the org setting:

- `CSV` — button says "Export CSV"
- `EXCEL` — button says "Export Excel"
- `BOTH` — button says "Export ▾" with a dropdown (CSV / Excel)

Where the setting lives: Settings → Reports → Export Format.
Default: CSV.

## Documents

Every generated document has **Download PDF**:
- Invoices (rent invoices)
- Bills
- Receipts
- Owner statements
- Owner packets
- Letters (3-Day Notice, Rent Increase, Deposit Disposition, etc.)
- Lease documents
- Work orders
- Paystubs (when payroll is added)

All PDFs use:
- The org's logo, name, tagline, address, phone, email (Section 71)
- The org's merge-field template for that document type
- The org's color / font preferences where applicable

## Merge tags in templates

Templates support a bracketed merge-tag syntax:
- `[COMPANY.NAME]` → Acme Property Management
- `[COMPANY.TAGLINE]`
- `[COMPANY.LOGO]`
- `[ADDRESS.LINE_1]`
- `[ADDRESS.CITY_STATE_ZIP]`
- `[PHONE.MAIN]`
- `[EMAIL.SUPPORT]`
- `[EMAIL.BILLING]`
- `[WEBSITE]`
- `[TAX.ID]`
- `[INVOICE.NUMBER]`, `[INVOICE.DATE]`, `[INVOICE.AMOUNT]`
- `[TENANT.FIRST_NAME]`, `[TENANT.LAST_NAME]`
- `[OWNER.FIRST_NAME]`
- `[PROPERTY.NAME]`, `[PROPERTY.ADDRESS]`
- `[TODAY.DATE]`

Templates are plain text + merge tags. No HTML. No JavaScript. No CSS.
No logic. Only substitution.

## Customization is presentation-only

No template, no logo, no color, no font can change:
- What a report calculates
- What an invoice totals
- What a GL posting does
- Any workflow, status, or system behavior

The only operational field affected is time zone (Section 71), and
it's a controlled dropdown, not freeform.

## Per-role exports

Every role exports their own data in the org's format:
- **Tenant** — payment history, charge history, invoices, receipts,
  lease, shared documents
- **Owner** — statements, packets, transaction history
- **Vendor** — work orders, invoices submitted, payments received,
  insurance/W9 copies
- **Crew** — work orders, schedule, time entries, paystubs
- **Applicant** — application status, submitted documents, screening
  result
- **Manager / Admin / Owner** — everything they have access to

Backend enforces scope: a tenant hitting `/api/export/payments` gets
only their own payments. No role can export another role's data.

## E-signatures

Integration with DocuSign (or an alternative) for leases, addenda,
and disclosures. Phase 8.

## Secure document sending

Expiring links, optional password, view-only mode. Phase 7/8.

## Where this lands in the plan

- Report Print + PDF + Export buttons: Phase 3.7
- Merge-field templates: Phase 3.7
- Invoice / bill / receipt / statement / letter PDFs: Phase 3.7
- Per-role exports: Phase 7 (portals)
- E-signature integration: Phase 8
- Secure document sending: Phase 7/8


# SECTION 73 — API SECURITY MODEL (DESIGNED)

Every endpoint respects three levels of isolation. No exception.

## Level 1 — Organization isolation

Every table with customer data has `organization_id`. Every query
filters by the caller's `organization_id`. No cross-org data leaves
the database.

## Level 2 — Role isolation

Every endpoint declares which roles can call it. Enforced server-side,
never trusted from the UI. Hitting an endpoint without permission
returns 403 (or 404 if we don't want to leak existence).

## Level 3 — Row-level isolation

Within an org, non-admin roles see only their own records:
- Tenant → own lease, charges, payments, documents, work orders
- Owner → own properties, statements, packets
- Vendor → own work orders, invoices, payments
- Crew → own work orders, time logs
- Applicant → own application

If a user tries `/api/invoices/999` and 999 isn't theirs, backend
returns 404.

## Public endpoint whitelist

The only routes accessible without authentication:
- `/auth/login`
- `/auth/signup`
- `/auth/forgot-password`
- `/auth/reset-password`
- `/health`
- Public listings page (read-only, no tenant data)
- Public tracking page (token-protected, single request)
- Stripe webhook (signature-verified)

Every other endpoint requires JWT + org + role + row-level access.

## No public API docs in production

`/docs` and `/openapi.json` are disabled in production. The internal
admin panel (Phase 9) can access them.

## Every access audited

Who called what, when, from what IP. Auth failures, permission
denials, and rate-limit hits are logged. Audit is queryable in the
Auditing Center (Section 71).

## Defense in depth

1. JWT required on every endpoint except the whitelist.
2. Org filter on every query.
3. Role check on every endpoint.
4. Row-level filter on every returned record.
5. 404-not-403 for out-of-scope records.
6. Every access logged.
7. Rate limiting (Phase 11).
8. Optional IP allowlist for admin accounts (Phase 4).

## Where this lands in the plan

- Levels 1–3 already enforced in current code, tracked for audit:
  Phase 1 (already built)
- Public endpoint whitelist, no public docs: Phase 11
- Audit log of every access: Phase 4
- Rate limiting, WAF, CSP: Phase 11


# SECTION 74 — SQL INJECTION PREVENTION (BUILT, RULES)

No user input ever becomes raw SQL. Every query is parameterized.
Every value is bound. No exceptions.

## Rules

1. All database access goes through SQLAlchemy ORM or bound
   `.text()` with a params dict. No f-string or `%` into SQL.
2. Sort / group / filter column names come from a whitelist dict,
   never from user input directly.
3. LIMIT is always clamped to a maximum (we already do:
   `limit: int = Query(200, ge=1, le=2000)`).
4. All query parameters are validated (type, length, pattern) via
   Pydantic before use.
5. LIKE patterns escape user-supplied `%` and `_` when the user
   shouldn't wildcard.
6. No `exec`, `eval`, or dynamic imports from user input.
7. File names are validated against traversal.
8. Every input schema declares types, lengths, and patterns.
   Missing validation = rejected.
9. Fuzz test per user-facing search / filter field, in CI:
   at least one SQL injection attempt per field, expecting 422 or a
   safe result.

## What we already have

- SQLAlchemy ORM everywhere.
- post_transaction() and all services use bound queries.
- FastAPI + Pydantic validates every request body.
- `/uploads/{filename}` has traversal checks.

## What we add

- Shared whitelist helper for sort / group columns: Phase 4.
- Fuzz test suite in CI: Phase 11.
- Penetration test before launch: Phase 11.

## Where this lands in the plan

- Rules documented (this section): now
- Sort whitelist helper: Phase 4
- Fuzz tests in CI: Phase 11
- Penetration test: Phase 11


# SECTION 75 — FILE UPLOAD SECURITY (DESIGNED)

Thirteen layers of defense. The user's original filename NEVER
touches a query, a path, or a shell.

## The layers

1. **Extension allowlist** — only .png, .jpg, .jpeg, .gif, .webp,
   .svg (sanitized), .pdf, .doc, .docx, .xls, .xlsx. No .php, .py,
   .js, .html, .exe, .sh, .bat, .ps1, .zip, .tar, .gz.
2. **Magic-byte check** — read the file's first bytes to confirm
   its true type matches the claimed extension. Do not trust the
   `Content-Type` header from the browser.
3. **UUID rename** — the user's filename is display-only. The
   stored filename is an app-generated UUID plus the validated
   extension. Kills path traversal, shell names, overwrite, and
   SQL injection via filename.
4. **Outside web root** — files land in `uploads/` which is never
   served directly by the web server.
5. **Content-Disposition: attachment** — never inline a PDF, SVG,
   or HTML file. Forces download.
6. **Antivirus scan** — every uploaded file is scanned with ClamAV
   (or a cloud AV API). Known signatures rejected, file deleted,
   event logged.
7. **Content Disarm & Reconstruction** for Office / PDF — strip
   macros, JavaScript, embedded objects, and shells. For SVG,
   sanitize with defusedxml + strip `<script>`, `onload=`,
   `xlink:href`, external references.
8. **Size limits** — per-file max 10 MB (configurable per org).
   No `.zip`, `.tar`, `.gz` (ZIP bomb prevention).
9. **CSRF protection** — upload endpoint requires JWT; SameSite
   cookies + CSRF token if cookies are ever used.
10. **HTML-encode filenames** for display — prevents stored XSS
    via a filename like `<script>alert(1)</script>.pdf`.
11. **Permission check per upload** — the uploader must have
    access to the entity they're attaching to (row-level scope,
    same as everything else).
12. **Audit every upload** — who, when, what file, from where,
    hash of the file, scan result. Every rejection logged with
    reason.
13. **No execution** — the backend server never executes anything
    in the uploads folder. In production, uploads go to S3.

## Where this lands in the plan

- Layers 1–13: Phase 4
- CDR (Content Disarm & Reconstruction): Phase 4
- S3 migration: Phase 11


# SECTION 76 — APPFOLIO PARITY & MIGRATION STRATEGY (DESIGNED)

Most clients migrating to us come from AppFolio. Everything here is
about making that migration smooth and the product familiar.

## Data import wizard

CSV upload + column mapping + validation + dry run + commit.
Properties, units, tenants, owners, vendors, leases, charges,
payments, GL history. Phase 4.

## Onboarding checklist

What a new org does first: add property → add units → add team →
set currency → set branding → import data → publish listings.
Phase 4.

## Terminology map

Use the same labels AppFolio uses. Bills not Payables. Receipts not
Payments In. Owner Statements not Owner Reports. Keeps the switch
painless. Already applied (see Section 47).

## Navigation alignment

Same top-level nav order: Dashboard, Properties, People, Accounting,
Maintenance, Reporting, Communication, Settings. Same sub-item names
where possible. Already applied (Section 5).

## Workflow alignment

Move In 5-step, Move Out 5-step, Increase Rent, Charge Late Fees.
Same sequence as AppFolio so it feels familiar. Already applied
(Section 17).

## Feature parity items from AppFolio

- Loan tracking — monitor loans payable, automated transaction
  creation. Phase 4.5.
- Bulk tenant charges — upload multiple charges at once.
  Phase 3.6.
- Tenant Debt Collections workflow — standardized collections
  process. Phase 4.
- Deposit refunds directly from escrow. Phase 3.6.
- Auto bank reconciliation via Plaid — we planned generic bank
  feeds (Phase 8). Plaid specifically.
- E-signature integration. Phase 8.
- Secure document sending. Phase 7/8.

## Where this lands in the plan

- Data import wizard: Phase 4
- Onboarding checklist: Phase 4
- Loan tracking: Phase 4.5
- Bulk charges: Phase 3.6
- Collections workflow: Phase 4
- Escrow refunds: Phase 3.6
- E-signature: Phase 8
- Secure send: Phase 7/8
- Plaid bank feeds: Phase 8


# SECTION 77 — ADVANCED SECURITY & FRAUD PREVENTION (DESIGNED)

Everything AppFolio does on the security and fraud side that we
should match or exceed.

## Continuous monitoring

Every auth event (success, failure, MFA, password reset) is logged
with IP, user-agent, and geolocation. Auth patterns are monitored.
Anomalies trigger alerts. Phase 4.

## Login anomaly detection

New IP for a user, new device, rapid failures, impossible travel —
flagged. High-risk logins require re-authentication or step-up MFA.
Phase 4.

## Identity verification

For applicants, owners, vendors. Integrate with a provider
(Stripe Identity, Persona, Jumio). Phase 8.

## Transaction monitoring

Flag suspicious payment patterns — many small charges, rapid
reversals, unusual amounts, changes to ACH details. Phase 8.

## OFAC / geographic restrictions

Block signups and logins from sanctioned regions. Phase 11.

## Security testing

- Penetration test before public launch. Phase 11.
- Dependency scanning in CI (Dependabot, Snyk). Phase 11.
- SAST / DAST in CI. Phase 11.

## Where this lands in the plan

- Continuous monitoring + login anomaly: Phase 4
- Identity verification: Phase 8
- Transaction monitoring: Phase 8
- OFAC / geo: Phase 11
- Security testing: Phase 11


# SECTION 78 — RESPONSIBLE AI FRAMEWORK (DESIGNED)

We do not currently use AI for any tenant-facing decision (screening,
rent determination, maintenance priority, or lease approval). If we
add AI features in the future, they follow this framework.

## Five principles (mirroring AppFolio for migration familiarity)

1. **Fairness** — no bias in AI outputs. No protected class used as
   input. Regular fairness audits on any deployed AI feature.
2. **Reliability** — AI works as intended, resistant to misuse.
   Fallback to a human path is always available.
3. **Privacy & Security** — data protection, governance compliance.
   No customer data used for model training without explicit consent.
4. **Transparency** — AI is easy to understand. Users know when
   they're interacting with AI vs. a human.
5. **Accountability** — we own the impact. Regular reviews of every
   deployed AI feature.

## Hard rules

- **Human-in-the-loop** for anything consequential. AI never
  approves a lease, denies an applicant, sets rent, or closes a work
  order on its own.
- **No AI for screening decisions.** Fair Housing Act compliance
  requires human decision-making with documented rationale.
- **No AI for lease approval.**
- **No AI for financial decisions.**
- **Audit trail** of every AI-assisted action: model version, prompt,
  human approver, timestamp.
- **Data protection** — no customer data used for training without
  explicit consent.
- **Vendor assessment** — if we integrate third-party AI, we verify
  their responsible AI posture first.

## Planned AI features (Phase 12+)

- **ai.maintenance_intake** — guide residents through self-help
  troubleshooting before dispatch. Human always reviews before any
  work order is created.
- **ai.message_drafting** — suggest replies to resident messages.
  Manager edits and sends. Draft never goes out unedited.
- **ai.report_summarization** — plain-English summaries of reports.
  Read-only. Never changes numbers.
- **ai.leasing_lead_draft** — draft responses to prospects. Manager
  approves before sending.

Every AI feature is behind a feature flag (Section 70). Default is
HIDDEN. AI features never bypass human-in-the-loop.

## Where this lands in the plan

- This framework: now (documented)
- Maintenance intake AI: Phase 12+
- Message drafting AI: Phase 12+
- Report summarization AI: Phase 12+
- Leasing lead draft AI: Phase 12+


# SECTION 79 — BUILD-IN-PLACE & COMPATIBLE REFACTOR POLICY (DESIGNED)

Pages should be designed so future major capabilities can be added without repeatedly rebuilding the surrounding page. The Feature Registry is the surface contract.

A page is complete when its currently required behavior works and its planned capability boundaries are represented clearly enough that future work can be added without guessing. Routine fields/columns/filters do not require their own release gates.

**Refactoring is allowed.** Do not unnecessarily rebuild working pages, but safe refactors are allowed when public behavior/contracts are preserved unless intentionally changed, migrations are deliberate, regression tests protect verified behavior, and registry/handoff records are updated.

The promise is compatibility, not immobility: build reusable primitives once, avoid unnecessary rewrites, and use automated regression coverage to make future changes safe.

# SECTION 80 — RELEASE STAGES & ACCESS RESOLUTION (DESIGNED)

Release control is only one of the five independent access concerns. It answers whether code is ready to be exposed to an organization; it does not replace subscriptions, org settings, permissions, or user preferences.

## Release stages

1. **HIDDEN**
2. **BETA**
3. **ROLLOUT**
4. **ALL_ORGS**

A request may additionally need plan entitlement, org configuration, permission, and user-presentation checks. Non-applicable layers pass automatically.

The frontend may use the resolved result for presentation, but backend endpoints/services independently enforce entitlement and permission requirements.

Conceptually:

    release passes
    AND plan entitlement passes if required
    AND org setting passes if configurable
    AND permission passes if required
    AND personal hiding passes if supported

Release-stage changes are audited. Org configuration does not change the platform release stage.

# SECTION 81# SECTION 81 — BUILT & VERIFIED (LIVING LEDGER)

Detailed, chronological record of every shipped item. Used to know
what to trust. Updated at the end of every session.

## Status legend

- **DONE** — works end-to-end, verified in browser
- **PARTIAL** — infrastructure built, consumption / wiring pending
- **PENDING** — planned, not built

## Session 2026-09-22 — Foundation planning (second half of the day)

### DONE

- **`docs/PLAN_GAPS.md` written.** The complete supplement to the
  master doc. Every gap in the plan (multi-region, GDPR, CCPA, SOC 2,
  FCRA, PCI, Arq, Redis, observability, all sub-phases 4.6–4.17,
  migration per competitor, trust interest, positive pay, 1099
  e-filing, year-end close, internal admin, white-label, status page,
  support SLA) with its decision, phase, cost, and dependencies.
  See Section 82.

- **`docs/FEATURE_REGISTRY.md` v1 written.** The surface map. Every
  page, every slot, every flag. v1 = structure + Receipts page as
  the format sample. Remaining 13 pages land in Session 3.4.2. See
  Section 83.

- **Master doc restructured.** Part A1, Part B1 rewritten. New
  Sections 82 (Plan Gaps & Foundation Pass) and 83 (Feature Registry
  — Surface Map). Section 38 gained the Foundation Pass at the top.
  Section 67's Complete-Page rule now references `check_parity.py`
  v2. This entry.

- **Parity JSON grew from 528 → 612 items.** 84 new items from
  PLAN_GAPS.md. 15 existing items reassigned to new phases (billing
  into foundation, internal admin moved earlier, compliance sub-phases
  split). Phases normalized (F1–F12 → 3.4.1–3.4.12). `check_parity.py`
  prints CLEAN.

### PARTIAL

(None this session — the second half was planning, not building.)

### PENDING

- Session 3.4.2 (next) — finish `FEATURE_REGISTRY.md`, write
  `check_parity.py` v2.
- Sessions 3.4.3 through 3.4.12 — the rest of the foundation pass.
- Phase 3.5.5 and Phase 3.6 resume after the foundation pass.

### Decisions this session

All decisions from `PLAN_GAPS.md` are now recorded in Section 82.
Key ones: Model B multi-region, Option Y (US-only today), Arq + Redis
for jobs, Stripe Billing, Track1099 for 1099 e-filing, Enterprise
non-self-serve, all sub-phases confirmed.

## Session 2026-09-22 — Frontend currency/date sweep

### DONE

- **Frontend currency/date sweep (21 files, 3 commits).**
  Every page that rendered money or dates now imports
  `formatMoney` / `formatDate` from `frontend/src/lib/money.ts`.
  No hardcoded `$`, `"USD"`, `toLocaleString("en-US", ...)`,
  `style: "currency"`, or hardcoded date strings remain anywhere
  except `lib/money.ts` itself (the legitimate home of
  `Intl.NumberFormat`) and two `Intl.NumberFormat` previews on the
  Display and Currencies settings pages (which use a specific row's
  locale, on purpose).

  **Files touched (Batch 1 — accounting, 12 files):**
  `accounting/bills/new/page.tsx`, `accounting/bills/page.tsx`,
  `accounting/deposits/page.tsx`, `accounting/deposits/new/page.tsx`,
  `accounting/journal-entries/new/page.tsx`,
  `accounting/management-fees/new/page.tsx`,
  `accounting/management-fees/page.tsx`,
  `accounting/owner-statements/new/page.tsx`,
  `accounting/owner-statements/[id]/page.tsx`,
  `accounting/owner-statements/page.tsx`,
  `accounting/receipts/new/page.tsx`,
  `accounting/receipts/page.tsx`.
  Commits: `e9f569c`.

  **Files touched (Batch 2 — property pages + tabs, 9 files):**
  `components/property/AmenitiesTab.tsx`,
  `components/property/AppliancesTab.tsx`,
  `components/property/ImprovementsTab.tsx`,
  `components/property/ExpensesTab.tsx`,
  `components/property/InsuranceTab.tsx`,
  `components/property/TenantInsuranceSection.tsx`,
  `components/property/UtilitiesTab.tsx`,
  `app/dashboard/properties/[id]/page.tsx`,
  `app/dashboard/tenant/page.tsx`.
  Commits: `2f91ae8`.

  **Files touched (Batch 3 — glTransactions cleanup + final tail, 4 files):**
  `lib/glTransactions.ts` (deleted duplicate `formatMoney` +
  `formatBalance` helpers),
  `accounting/gl-accounts/[id]/ledger/page.tsx`,
  `accounting/journal-entries/[id]/page.tsx`,
  `accounting/trial-balance/page.tsx`,
  `app/dashboard/settings/display/page.tsx`.
  Commits: `90500b0`, `3d52105`.

  Verification: `npx tsc --noEmit` silent after every batch.
  `python check_parity.py` CLEAN.

- **Display page currency dropdown now fetches the API.**
  Was hardcoded (9-currency array). Now calls
  `GET /api/settings/currencies` and populates from the org's real
  list. Fallback list kept only for offline/error cases.
  Closes the last PARTIAL from Sections 58, 59, 68.

- **Real bug fixed — Display page currency was not persisted.**
  The save payload was missing `currency`, so changing the dropdown
  only updated the local preview. Backend was already set up to
  persist it (see `settings_display.py`); the frontend was silently
  dropping the field. Now included.

- **glTransactions.ts duplicate helpers removed.**
  The file had its own `formatMoney` and `formatBalance` that
  hardcoded USD — shadowing `lib/money.ts` for any page that
  imported them. Deleted. Three pages (`ledger`, `journal-entries/[id]`,
  `trial-balance`) split their import block:
  types/API from `glTransactions`, formatters from `lib/money`.
  Each of the three now defines a small local `formatBalance()`
  that wraps `formatMoney` and preserves the "show `$0.00` for
  zero/null instead of an em-dash" semantics that totals rows need.

- **Mojibake cleanup.**
  Many files displayed `â€"`, `Â·`, `â€¦`, `ðŸ"¥`, etc. from
  earlier Windows-console UTF-8 confusion. The on-disk bytes were
  already correct UTF-8; the display artifacts are gone now that
  every file has been rewritten through VS Code's UTF-8 pipeline.

### Lessons learned

- **Do not script context-dependent edits across a codebase.**
  A first attempt at an automated sweep
  (`sweep_formatting.py`) produced double-brace JSX artifacts in
  the biggest file (`properties/[id]/page.tsx`). Recovered from
  backup; the script was abandoned. Every file in the final sweep
  was edited by hand — whole-file replacement, no regex.
  The `properties/[id]/page.tsx` fix used a Python script with
  byte-exact literal anchors (`fix_property_detail.py`), which is
  the safe middle ground: literal strings, no regex, aborts on
  mismatch, writes once, deletes itself after.

- **PowerShell `[id]` folder paths need `-LiteralPath`.**
  `Test-Path "src\...[id]\..."` returns False silently because
  `[` is a wildcard character in PowerShell. Always use
  `-LiteralPath` for any path containing `[` or `]`.

### Files deleted

- `backend/sweep_formatting.py` (abandoned automated sweep)
- `backend/fix_property_detail.py` (one-off; ran once, deleted)
- `frontend/src/app/dashboard/properties/[id]/page.tsx.backup-before-*`
- `frontend/src/components/property/TenantInsuranceSection.tsx.backup-before-*`

### PARTIAL

(No new PARTIAL items this session — two existing PARTIALs became DONE.)

## Session 2026-09-21 / 2026-09-22

### DONE

- **Sidebar preferences per-user fix.**
  Dropped stale UNIQUE index on `sidebar_preferences.organization_id`
  (leftover from the original org-scoped design). Made `user_id`
  NOT NULL. Race-safe get-or-create in both routers. Added missing
  `IntegrityError` import.
  Migrations: `c0e4ac6f46b2`, `5949df11e460`.
  Files: `backend/app/models/sidebar_preference.py`,
  `backend/app/routers/sidebar_preference.py`,
  `backend/app/routers/menu_permissions.py`.
  Verification: My Preferences tab works for all users.

- **My Preferences tab in Settings → Permissions.**
  Now saves. Race-safe. Same migrations and files as above.

- **Custom Currencies CRUD.** (See also PARTIAL below.)
  Table `currencies`, model `Currency`, router
  `/api/settings/currencies`, page
  `/dashboard/settings/currencies`.
  Migrations: `8e1243432666` (table + 9 seeds).
  Menu key: `SETTINGS.CURRENCIES` + migration `15d92d8a1eea`.
  Files: `backend/app/models/currency.py`,
  `backend/app/routers/currencies.py`,
  `frontend/src/app/dashboard/settings/currencies/page.tsx`.

- **Display Settings page.**
  Layout mode, theme, date format, currency, density, number format,
  font size, accent, reduce motion — all save.
  Migrations: `8c2e766863c0` (org currency column),
  `521035d0e411` (user_display_preferences table).
  Files: `frontend/src/app/dashboard/settings/display/page.tsx`,
  `frontend/src/contexts/CurrencyContext.tsx`,
  `frontend/src/contexts/DisplayContext.tsx`,
  `frontend/src/lib/money.ts`,
  `backend/app/routers/settings_display.py`.

- **SETTINGS menu group.**
  Display, Currencies, Menu Permissions, Sidebar wired to the sidebar.
  Migration `15d92d8a1eea`.
  Files: `backend/app/constants/menu_keys.py`,
  `frontend/src/lib/menuConfig.ts`,
  `frontend/src/components/shell/Sidebar.tsx`.

- **Charges feature** (Phase 3.6 item 1).
  Table `charges`, model, router, list page, new page, menu key.
  Migrations: `f49b93dcb1e2` (table), `3909fd7c7792` (menu key).
  Files: `backend/app/models/charge.py`,
  `backend/app/routers/charges.py`,
  `frontend/src/app/dashboard/accounting/charges/page.tsx`,
  `frontend/src/app/dashboard/accounting/charges/new/page.tsx`.

- **FILE_CATALOG.md generator.**
  `backend/generate_file_catalog.py` writes
  `docs/FILE_CATALOG.md` with every source file and what's inside.
  Regenerate at the end of any session that added / renamed / deleted
  files.

- **Master doc repairs and updates this session.**
  Repaired three corruptions (duplicate END markers, orphaned
  Section 67 body inside Section 65, triple Companion block in
  Section 69). Rewrote Part A + Part B. Extended Section 9 to
  5-layer. Updated Section 11 HEAD. Inserted Phase 3.5.5 in
  Section 38. Updated Sections 57, 58, 59, 67, 68 with status.
  Added this section and Sections 70–80.

### PARTIAL

- **Currency in the Display page.**
  * Saves: `PUT /api/settings/display` persists
    `organizations.currency` for ADMIN/OWNER.
  * Missing: the Display page currency dropdown is still hardcoded.
    It does NOT fetch custom currencies from
    `/api/settings/currencies`. Custom currencies don't appear there.
  * Missing: no page uses `formatMoney()` yet. Every amount still
    renders with a hardcoded `$`.
  * Fix: Phase 3.5.5 (Compliance Pass).

- **Display settings consumption.**
  * Theme saves and sets `data-theme` on `<html>`; no dark-mode CSS
    exists yet, so nothing visually changes.
  * Layout mode saves; no page reads it.
  * Date format saves; no page calls `formatDate()`.
  * Density, font size, number format, accent, reduce motion: saved
    on backend, UI shows "Coming soon", nothing consumes them.
  * Fix: Phase 3.5.5.

### PENDING

- **Phase 3.5.5 Compliance Pass** — retrofit existing pages to use
  the shared primitives and gate every future feature behind a flag.
  Behavior-preserving. See Section 79.

- **Phase 3.6 continues** — 69 of ~70 items remain.

- **All of Sections 70–80** — designed, not yet built. Each has its
  phase listed in its own section.

## Earlier sessions

- Sessions 1–17: auth, properties, units, people, leases, work
  orders, password reset, org email, uploads, team UI, property
  detail tabs, financials, taxes, policies, utilities, insurance,
  expenses, income, tenant insurance, applicant role, screening,
  OCR settings.
- Phase 1: Menu Permissions System.
- Phase 2 Steps 1, 2, 2b, 4, 5, 6, 7, 8a, 8b, 9, 10.
- Phase 3 Steps 3a, 3b, 3c, 3d.

## Page Surface Completeness

For each existing page, the plan lists what it should have. Currently
most pages show only the built portion. The retrofit (Phase 3.5.5)
adds the full planned surface with unbuilt slots hidden behind flags.

Status (all pending Phase 3.5.5 retrofit):

- Receipts — uses `$` hardcoded. Needs: primitives, Print, Repeat,
  edit-lock-after-deposit, cash-account-automatic.
- Bills — needs: primitives, cash-account-field, recurring, write-
  checks, enter-credit, delete-rules, post-codes.
- Deposits — needs: primitives, Print, date-warning, number-per-bank,
  edit.
- GL Accounts — needs: primitives, recalculate-balances, hide-
  semantics, offset-account UI, must-clear UI.
- Journal Entries — needs: primitives, sub-tabs, recurring, manually-
  post, post-gpr, remarks-vs-description.
- Management Fees — needs: primitives, pay-owners flow,
  overcollection, exclusions-list.
- Owner Statements — needs: primitives, required-reserves,
  prepaid-rent, property-cash-summary, packet-customizer.
- Bank Accounts — needs: primitives, reconciliation, QIF, check-setup,
  ACH-file-gen, adjustments, bank-feed.
- Charges — needs: primitives (was just built — the primitives rule
  applies starting now), edit-rules already enforced.
- Properties — needs: primitives on every tab.
- Currencies — needs: primitives; display-dropdown-fetch is the
  key item.
- Display — needs: primitives on its own controls; layout-mode
  consumed by pages; theme consumed by CSS; date format consumed
  by pages.
- Permissions — needs: primitives.
- Sidebar — needs: primitives.

The retrofit is one page at a time. Behavior-preserving. Every page
stays exactly the same visually until a flag flips.


# SECTION 82 — PLAN GAPS & REVISED FOUNDATION ORDER

**Companion:** `docs/PLAN_GAPS.md`  
**Revised:** 2026-09-23

The gap review identified compliance, infrastructure, product-scope, and operational work that was under-specified. Those items remain tracked in the parity JSON, but verification now comes before aggressive expansion.

## Revised foundation sequence

| Order | Phase | Focus |
|---|---|---|
| 1 | 3.4.1 | Planning + PLAN_GAPS + FEATURE_REGISTRY v1 |
| 2 | 3.4.2 | Complete FEATURE_REGISTRY with Hybrid Capability Gating + registry/parity tooling |
| 3 | **3.4.S** | Engineering Safety Foundation |
| 4 | 3.4.3 | Identity boundary + immutable audit |
| 5 | 3.4.4 | Release-gate storage/resolver + jobs runtime foundation |
| 6 | 3.4.5 | Locked accounting periods + core org settings |
| 7 | 3.4.6 | End-to-end verification of existing core product |
| 8 | 3.4.7 | Basic billing foundation |
| 9 | 3.4.8 | Self-serve signup/payment flow |
| 10 | 3.4.9 | Fraud / abuse foundation: Stripe Radar, internal signals, review queue |
| 11 | 3.4.10 | Separate internal admin app: organizations, release gates, plans, fraud, audit |
| 12 | 3.4.11 | Customer release-gate consumption + Settings → Features |
| 13 | 3.4.12 | Unit / plan-limit enforcement + upgrade path |
| 14 | 3.4.13 | Receipts compatibility retrofit (proof pattern) |
| 15 | 3.4.14+ | Remaining compatibility page retrofits |
| then | core product | Resume Phase 3.6 through launch |
| post-launch | expansion | Specialized product lines unless business priority changes |

Key corrections: Engineering Safety is mandatory before broad AI-assisted development; per-field flagging is replaced by Hybrid Capability Gating; `check_parity.py CLEAN` proves planning consistency only; core launch precedes expansion products; and safe refactoring is allowed under regression protection.

# SECTION 83 — FEATURE REGISTRY (SURFACE & ACCESS MAP)

**Companion:** `docs/FEATURE_REGISTRY.md`  
**Revised:** 2026-09-23

The Feature Registry is the page/capability contract. It records routes, meaningful surface slots, independent release gates, entitlement keys, org configurability, permission keys, user-hideability, implementation status, and backend endpoints/access requirements.

It deliberately does **not** assign a release flag to every field, column, filter, label, sorting control, or routine form element. Release control, plan entitlement, org configuration, permission, and user preference remain separate mechanisms.

`check_parity.py` verifies registry structure and current routes. It is not a behavioral test.

**Session 3.4.2 COMPLETE:** 24 current routes, 211 meaningful rows, and 67 distinct release gates under the final Hybrid Capability Gating schema.

# SECTION 84 — ENGINEERING SAFETY FOUNDATION (FINAL HOSTED VERIFICATION)

**Phase:** `3.4.S`  
**Started:** 2026-09-23

The project does not accelerate into broad AI-assisted batches until the codebase can verify its own correctness.

## Required gates

- parity/registry consistency;
- backend unit/integration tests;
- PostgreSQL integration;
- migration/bootstrap verification;
- frontend lint + TypeScript + production build;
- Playwright authenticated smoke/E2E;
- accounting invariants for money movement;
- backup/restore proof;
- basic staging build/start/health proof;
- dependency/static security scanning;
- documented idempotency rules and Definition of Done.

## Evidence already green

Hosted GitHub CI has passed backend/PostgreSQL, frontend lint/type/build, fresh DB bootstrap, E2E seed, PostgreSQL dump/restore, authenticated browser smoke, staging image/config checks, and live Docker Compose startup/health verification. CI run 35916148970 proved backend `/health` and frontend `/login` from the running stack.

Phase 3.4.S is complete. Hosted CI uses portable security gates that work for this private repository: Bandit, pip-audit, npm audit, committed-secret scanning, and Dependabot. CodeQL remains an optional manual workflow if GitHub Code Security is enabled later.

## Permanent rules

- Implemented is not VERIFIED.
- `check_parity.py CLEAN` is necessary planning consistency, not behavioral proof.
- Financial changes require accounting invariant + atomic failure coverage.
- Retryable/financial/external-side-effect workflows require stable idempotency identity and database-backed duplicate prevention.
- Existing verified behavior is a contract; safe refactors are allowed only with regression protection.
- `docs/AI_HANDOFF.md` is maintained by the assistant after meaningful verified batches. Yasir is never responsible for reconstructing AI context.

# END OF PROJECT_MASTER.md# END OF PROJECT_MASTER.md


# SECTION 85 — FOUNDATION 3.4.3 (COMPLETE)

**Phase:** `3.4.3`  
**Completed:** 2026-09-23

## Identity boundary

- Separate `platform_users` table with no customer `organization_id`.
- Platform roles remain independent from customer roles.
- One-time guarded `seed_platform_admin.py`; no self-signup path for platform staff.
- Customer and platform JWTs require separate audience claims and are not interchangeable.
- Hosted CI run 35922527217 passed after migration/schema-count guards were updated.

## Immutable audit foundation

- Existing `audit_log` remains the canonical history table.
- New canonical append service flushes into the caller's transaction and does not force an independent commit.
- ORM UPDATE/DELETE attempts are rejected.
- PostgreSQL fresh bootstrap creates an immutable trigger; existing versioned databases receive it through Alembic revision `a6e4c8f2b1d0`.
- Direct PostgreSQL UPDATE and DELETE attempts are regression-tested and rejected.
- Existing `app.core.audit.log_action()` now routes through the canonical append-only service.
- Hosted CI run 35924373985 passed backend, security, frontend, E2E, backup/restore, and live staging checks.

## Next

Phase **3.4.4 — release-gate storage/resolver + jobs runtime foundation**. The parity checklist keeps Redis/Arq queue, scheduler, standard retry/dead-letter patterns, and Redis standup in 3.4.4.


# SECTION 86 — FOUNDATION 3.4.4 (COMPLETE)

**Phase:** `3.4.4`  
**Completed:** 2026-09-23  
**Verification:** hosted CI run `35931322493`

## Hybrid Capability Gating runtime

The old five-state / sticky / three-tier feature-flag wording is retired. The locked architecture remains PROJECT_MASTER Sections 70 and 80:

- release stages: `HIDDEN`, `BETA`, `ROLLOUT`, `ALL_ORGS`;
- release control is independent from entitlement, org configuration, authorization, and user presentation;
- a non-applicable layer passes automatically;
- UI hiding never grants backend access.

Implemented:

- `release_gates` and `release_gate_organizations` storage;
- explicit beta/rollout organization allowlists;
- fail-closed release resolver;
- five-layer access composition without cross-layer grants;
- platform-audience-only `PUT /api/platform/flags/{key}`;
- immutable audit of release-stage/allowlist changes with `platform_user_id`;
- idempotent `seed_release_gates.py` from FEATURE_REGISTRY metadata, creating missing gates as HIDDEN without overwriting existing state.

## Jobs runtime foundation

PostgreSQL is the durable source of truth. Redis is dispatch.

Implemented:

- `job_runs` with unique `(job_name, idempotency_key)`;
- `job_dead_letters`;
- DB-first reserve/commit before queue dispatch;
- deterministic Arq job IDs;
- scheduled/deferred dispatch;
- handler registry;
- bounded exponential retries;
- per-job max attempts;
- durable dead-letter transition;
- minute-level recovery cron for due PENDING/RETRYING jobs and lost DB-first dispatches;
- platform-only job list, summary, and dead-letter monitoring endpoints.

Operational contract: `docs/JOBS_RUNTIME.md`.

## Redis / staging

Staging now proves the complete runtime stack:

- PostgreSQL;
- Redis with persistence + health check;
- FastAPI backend;
- Arq worker;
- Next.js frontend.

The runtime uses provider-neutral `REDIS_URL`. Managed environments may supply the planned Upstash development URL or ElastiCache production endpoint without application-code changes.

## Sentry observability

Optional `sentry-sdk` wiring covers:

- FastAPI backend exceptions;
- Arq worker handler exceptions;
- bounded Next.js client-error relay through `/api/observability/client-error`.

No `SENTRY_DSN` means the integration is inert. Default PII collection is disabled.

## Next

Phase **3.4.5 — locked accounting periods + core organization settings**. Follow the revised foundation sequence in Section 82 when legacy phase assignments conflict with the locked architecture.


# SECTION 86 — FOUNDATION 3.4.5 (COMPLETE)

**Phase:** `3.4.5`  
**Completed:** 2026-09-23

## Locked accounting periods

- `organizations.locked_through_date` closes all GL posting dates on or before the configured date.
- Enforcement lives in `post_transaction()`, so existing receipts, bills, journals, deposits, management fees, transfers, and reversals inherit the rule.
- Regression tests prove a locked post creates no GL transaction or entries and the first open day can post normally.

## Core organization settings

- `organizations.data_region` defaults to `us-east-1`; `properties.data_region` may override it.
- `get_db_for_org()` provides the Model B logical routing seam, uses explicit regional DB mappings, and fails closed for unknown regions.
- `data_retention_policies` supports 30d / 365d / 2555d / forever with org-specific overrides.
- Organization Admin foundation-settings GET/PUT endpoints manage lock date, logical region, and retention overrides with same-org authorization and immutable audit logging.

## GDPR schema foundation

- Every model class that uses `is_active` as a soft-delete/status mechanism now also has `deleted_at`.
- The retrofit is split across small Alembic migrations; current head is `46c3d8f2ab10`.

## Verification

Hosted CI run **35934453373** passed backend/PostgreSQL, frontend, security, migration/bootstrap, pg_dump/restore, authenticated E2E, and live staging.

## Next

Phase **3.4.6 — end-to-end verification of the existing core product**. This phase verifies existing behavior before 3.4.7 begins basic billing foundation work.


# SECTION 87 — FOUNDATION 3.4.9 (COMPLETE)

**Phase:** `3.4.9`  
**Completed:** 2026-09-24  
**Implementation commit:** `27fdf78524ddb4665bf3cc416b59c8289e4e8d51`  
**Verification:** hosted CI run `35960071377`

## Fraud / abuse foundation

- Added durable `fraud_cases` and `fraud_signals` storage.
- Signed Stripe Radar early-fraud-warning and review events plus fraud-related disputes feed an idempotent internal review queue.
- No raw card data is stored by the fraud layer.
- Internal checkout-attempt velocity creates HIGH / CRITICAL signals in a one-hour window.
- New Checkout requests fail closed while an unresolved CRITICAL fraud case exists.
- Platform-only fraud list/detail/review APIs enforce platform roles and audit review decisions.
- Existing durable Arq/Redis jobs runtime schedules an hourly fraud refresh.
- Alembic head is `6f1a9c4d2e7b`; model table count is 75.

## Verification evidence

- Backend/PostgreSQL: **154 passed, 2 deselected, 1096 warnings in 35.89s**.
- E2E: **2 passed in 6.63s**.
- Frontend lint / TypeScript / production build: SUCCESS.
- Security gates: SUCCESS.
- Staging build / live smoke: SUCCESS.
- Parity/registry and committed-secret checks: SUCCESS.

## Next

Phase **3.4.11 — customer release-gate consumption + Settings → Features**. Customer-side capability visibility must consume release-stage resolution without conflating it with plan entitlement, organization configuration, role permission, or user preference.


# SECTION 88 — FOUNDATION 3.4.10 (COMPLETE)

**Phase:** `3.4.10`  
**Completed:** 2026-09-24  
**Platform-control API commit:** `764f6816b8334490c93d095a47a721b8ccbf380d`  
**Internal-app commit:** `02ddfa7a622d9b155ca1c71899316c6b163755a2`  
**Browser-proof commits:** `39e7d3e3a39c77dbc9a1b3388f2115e400b2cdc6`, `e195a2b98e0a1d5686580f89842ccd56726b0f0c`  
**Verification:** hosted CI run `35981504331`

## Separate internal administration application

- Added a separate Next.js application under `platform-admin/`; platform staff are not mixed into the customer frontend.
- Platform login uses the platform JWT audience and a separate browser token key, `platform_access_token`.
- Customer JWTs and the customer `token` key are not reused by the internal application.
- Internal surfaces cover organizations, plans, release gates, fraud review, and platform staff audit.
- Backend platform-role authorization remains authoritative for every privileged operation.

## Platform controls

- Platform staff can list customer organizations and authorized sales/admin staff can provision enterprise organizations without creating customer credentials.
- Billing/admin staff can manage the plan catalog; sales remains read-only.
- Platform admin/dev can inspect and update release stages and organization allowlists.
- Authorized platform staff can review fraud cases.
- Platform audit reads expose platform-actor activity only.
- Privileged mutations are immutably audited.

## CI and browser proof

- CI has a dedicated platform-admin lint, TypeScript, and production-build job plus npm audit.
- Disposable E2E setup seeds a platform administrator and runs the internal app on port 3001 beside the customer frontend.
- Playwright proves platform login, the core internal surfaces, a populated `platform_access_token`, and absence of the customer `token` key.
- Backend/PostgreSQL: **160 passed, 3 deselected, 1132 warnings in 39.14s**.
- E2E: **3 passed in 9.49s**.
- Customer frontend, platform-admin frontend, security, backup/restore, and staging smoke: SUCCESS.
- Alembic head remains `6f1a9c4d2e7b`; this phase added no migration.

## Next

Phase **3.4.11 — customer release-gate consumption + Settings → Features**.

# SECTION 89 — FOUNDATION 3.4.11 (COMPLETE)

**Phase:** `3.4.11`  
**Completed:** 2026-09-24  
**Capability API commit:** `d32682c153b6ebbe83c262dc755e4104b0774710`  
**Customer UI commit:** `bb43ad66e4aeb8608a0ec42e82f8c8a1b6e4bbf1`  
**UX/E2E fix commit:** `d49368a07e6df74e78ed6d03f71e8afc3b3029aa`  
**Verification:** hosted CI run `35985275368`

## Customer capability consumption

- Customer runtime resolves platform release state, commercial entitlement, organization configuration, and role/user permission as independent layers.
- Hidden/unreleased platform stages are not exposed to customer clients.
- Organization feature choices live in their own `organization_feature_settings` table and cannot mutate platform release state.
- `SETTINGS.FEATURES` is itself release-gated; its organization toggle cannot self-disable the control surface.
- Customer sidebar consumes the release gate while backend authorization remains authoritative.

## Customer UI primitives

- Added `FeatureProvider`, `useFlag()`, and the reusable `<Flag>` wrapper.
- Added Settings → Features for ADMIN/OWNER organizations with org-level capability toggles.
- Toggles update optimistically and roll back on API failure.
- Deterministic E2E coverage proves a released configurable capability can be disabled and remains disabled after reload.

## Verification evidence

- Backend/PostgreSQL: **165 passed, 3 deselected, 1187 warnings in 43.02s**.
- E2E: **3 passed in 9.05s**.
- Customer frontend lint / TypeScript / production build: SUCCESS.
- Platform-admin lint / TypeScript / production build: SUCCESS.
- Security gates, PostgreSQL backup/restore, and live staging smoke: SUCCESS.
- Alembic head: `3b8d1f5c7a20`; model table count: 76.

## Next

Phase **3.4.12 — unit / plan-limit enforcement + upgrade path**. Enforce limits on backend unit creation/restoration first; customer upgrade messaging may explain the limit but never replace server enforcement.

# SECTION 90 — FOUNDATION 3.4.21 (COMPLETE)

**Phase:** `3.4.21`  
**Completed:** 2026-09-24  
**Implementation commit:** `7148b788315be7c6a245884da8d2dec5e0f02913`  
**Verification:** hosted CI run `36051620935`

## Charges compatibility retrofit

- Preserve existing standalone-charge rules: org-scoped tenant/account validation, INCOME-only GL accounts, paid-floor edits, and no deletion of fully paid charges.
- Backend list/detail access is governed by `ACCOUNTING.CHARGES`; create/update/delete additionally require ADMIN/OWNER/MANAGER.
- Charges list/new pages consume shared display preferences.
- Bulk Tenant Charges Upload is represented as `release.accounting.charges.bulk_upload`, a hidden compatibility slot only; the actual bulk-import workflow remains scheduled.
- Regression coverage verifies access/write-role helpers, and authenticated E2E verifies the unreleased bulk action stays hidden.
- No migration is required; Alembic head remains `8c4e2a7d1f90`.

## Verification evidence

- Backend/PostgreSQL: **233 passed, 3 deselected, 1266 warnings in 36.78s**.
- E2E: **3 passed in 11.77s**.
- Customer frontend, platform-admin, security, parity/registry, backup/restore, and staging smoke: SUCCESS.
- Alembic head remains `8c4e2a7d1f90`.

## Next

Phase **3.4.22 — Properties compatibility retrofit**. Preserve verified property/unit behavior while adding only planned compatibility boundaries and authoritative permission coverage.

# SECTION 91 — FOUNDATION 3.4.22 (COMPLETE)

**Phase:** `3.4.22`  
**Completed:** 2026-09-24

## Properties compatibility retrofit

- Existing organization/assignment property scope and unit plan-limit enforcement remain intact.
- Backend routes layer menu authorization onto scope: `PROPERTIES.ALL` for property reads/core mutations, `PROPERTIES.ADD` for property creation, and `PROPERTIES.UNITS` for unit routes.
- Existing role contracts remain authoritative: property create/update/delete/restore are ADMIN/OWNER; unit create/update/delete are ADMIN/OWNER/MANAGER; unit restore remains ADMIN/OWNER.
- Customer list/detail/new/edit/unit surfaces consume shared display preferences and normalize role casing.
- The property Edit link/page now matches backend ADMIN/OWNER authorization while MANAGER retains unit and allowed child-tab management.
- Property Groups, Map View, Photo Editor, Keys, Statement Settings, Attachments, Non-Revenue, Staff, Budget, Fixed Assets, RUBs, and Compliance are represented only as hidden release-gated compatibility slots. Their workflows remain scheduled.
- Existing routine/missing fields such as default bank account are not converted into feature flags.
- No migration is required; Alembic head remains `8c4e2a7d1f90`.

## Verification evidence

- Final repair commit: `d26b2f4e8eee85e09643a29fcda68948d98c5192`.
- Hosted CI run `36056943124`: SUCCESS.
- Backend/PostgreSQL: **239 passed, 3 deselected, 1266 warnings in 36.66s**.
- E2E: **3 passed in 10.40s**.
- Customer frontend, platform-admin, security, parity/registry, backup/restore, and staging smoke: SUCCESS.
- Alembic head remains `8c4e2a7d1f90`.

## Next

Phase **3.4.23 — Currencies compatibility retrofit**. Preserve verified currency behavior while replacing hardcoded Display currency choices with the existing organization currency API and applying shared display compatibility.



# SECTION 92 — FOUNDATION 3.4.23 (COMPLETE)

**Phase:** `3.4.23`  
**Completed:** 2026-09-24

## Currencies compatibility retrofit

- Existing per-organization currency catalog CRUD is preserved.
- System currencies remain non-deletable and the organization’s active currency remains protected from delete/deactivation.
- `SETTINGS.CURRENCIES` is now enforced server-side for currency catalog routes; ADMIN/OWNER remain the only mutation roles.
- The Currencies page consumes shared display layout/density metadata and aligns mutation controls with backend write roles.
- Display currency choices are sourced from `/api/settings/currencies`; alternate hardcoded fallback choices are removed, while the current organization currency remains available if catalog loading fails.
- Routine currency fields are not feature-flagged.
- No migration is required; Alembic head remains `8c4e2a7d1f90`.

## Verification evidence

- Implementation commit: `9b9dad9eec699887035f6acd9fbb6bbb7b150729`.
- Hosted CI run `36057866985`: SUCCESS.
- Backend/PostgreSQL: **249 passed, 3 deselected, 1266 warnings in 42.14s**.
- E2E: **3 passed in 13.23s**.
- Customer frontend, platform-admin, security, parity/registry, backup/restore, and staging smoke: SUCCESS.
- Alembic head remains `8c4e2a7d1f90`.

## Next

Phase **3.4.24 — Display compatibility retrofit**.


# SECTION 93 — FOUNDATION 3.4.24 (COMPLETE)

**Phase:** `3.4.24`  
**Completed:** 2026-09-24

## Display compatibility retrofit

- Existing per-user display preference storage and API payload remain intact.
- `SETTINGS.DISPLAY` is enforced server-side for GET/PUT display settings.
- Existing ADMIN/OWNER-only organization-currency mutation semantics remain unchanged.
- Shared CSS now consumes DisplayContext attributes for explicit light/dark theme, density-sensitive inputs, base font size, reduce-motion behavior, and accent color.
- The Display page consumes shared layout/density metadata and exposes the already-persisted density, font-size, accent-color, and reduce-motion settings.
- Date format remains consumed by the shared formatter. Number-format rendering remains deferred because `formatMoney()` does not yet consume that preference.
- No migration is required; Alembic head remains `8c4e2a7d1f90`.

## Verification evidence

- Implementation commit: `4a58e2513004b3ad235d495b964a5749e5780faf`.
- Hosted CI run `36058923158`: SUCCESS.
- Backend/PostgreSQL: **252 passed, 3 deselected, 1266 warnings in 41.71s**.
- E2E: **3 passed in 11.93s**.
- Customer frontend, platform-admin, security, parity/registry, backup/restore, and staging smoke: SUCCESS.
- Alembic head remains `8c4e2a7d1f90`.

## Next

Phase **3.4.25 — Permissions compatibility retrofit**.


# SECTION 94 — FOUNDATION 3.4.25 (COMPLETE)

**Phase:** `3.4.25`  
**Completed:** 2026-09-24

## Permissions compatibility retrofit

- Existing menu resolver behavior, editor-role hierarchy, immutable ADMIN matrix, subtract-only user override behavior, and personal sidebar preferences are preserved.
- Privileged role-matrix and per-user override management endpoints require `SETTINGS.PERMISSIONS` server-side.
- Resolved-menu reads and each user’s own `/api/menu/me/preferences` remain self-service and are intentionally independent of privileged permission-management access.
- The Permissions page consumes shared display layout/density metadata and normalizes role casing.
- GL Account Permissions is represented only as a hidden `release.accounting.gl_account_permissions` compatibility slot; the workflow remains scheduled.
- No migration is required; Alembic head remains `8c4e2a7d1f90`.

## Verification evidence

- Implementation commit: `9a0680914e0f1f3ac96a93e2751d6db180a2eadf`.
- Hosted CI run `36060022264`: SUCCESS.
- Backend/PostgreSQL: **256 passed, 3 deselected, 1266 warnings in 41.97s**.
- E2E: **3 passed in 10.77s**.
- Customer frontend, platform-admin, security, parity/registry, backup/restore, and staging smoke: SUCCESS.
- Alembic head remains `8c4e2a7d1f90`.

## Next

Phase **3.4.26 — Sidebar compatibility retrofit**. Preserve the legacy route while sending users directly to Permissions → My Preferences, keep personal sidebar customization self-service, and preserve backend-authoritative menu resolution.


# SECTION 95 — FOUNDATION 3.4.26 (COMPLETE)

**Phase:** `3.4.26`  
**Completed:** 2026-09-24

## Sidebar compatibility retrofit

- The legacy `/dashboard/settings/sidebar` customer route remains available for old bookmarks.
- It now deep-links to `/dashboard/settings/permissions?tab=preferences` so ADMIN/OWNER/MANAGER users land on **My Preferences** instead of the privileged Roles tab.
- The Permissions page accepts an allowed `tab` query selection while preserving role-based tab visibility and its existing default behavior when no tab is requested.
- Existing personal sidebar order/hide storage, `/api/menu/me/preferences`, legacy `/settings/sidebar` API behavior, and backend-authoritative `/api/menu/me` resolution are unchanged.
- Browser smoke coverage verifies the compatibility redirect reaches the self-service preference surface.
- No migration is required; Alembic head remains `8c4e2a7d1f90`.

## Verification evidence

- Implementation commit: `b223d5746d5f19c361bf00b2ec749be0af25e756`.
- Hosted CI run `36066815450`: SUCCESS.
- Backend/PostgreSQL: **256 passed, 3 deselected, 1266 warnings in 40.31s**.
- E2E: **3 passed in 9.03s**.
- Customer frontend, platform-admin, security, parity/registry, backup/restore, and staging smoke: SUCCESS.
- Alembic head remains `8c4e2a7d1f90`.

## Next

Phase **3.6 — Accounting Polish** begins with Chart of Accounts. The 3.5.5 compatibility pass is complete.
