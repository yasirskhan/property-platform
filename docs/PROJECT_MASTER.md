# PROJECT MASTER

**Property Management Platform (AppFolio-equivalent)**
**Single source of truth for the project.**
**Last updated: 2026-09-20**

---

# ═══════════════════════════════════════════════════
# PART A — CURRENT STATE
# ═══════════════════════════════════════════════════

## A1. WHERE WE ARE RIGHT NOW

**Current activity:** Phase 2 (Accounting). Steps 1, 2, 5, 6, 7, 8, 9, 10 COMPLETE. Next is Step 4 (Bank Accounts) then Step 2b (Manual Journal Entry).

**Last completed work:**
- Phase 1 (Menu Permissions) shipped and working
- Phase 2 Step 1 (Chart of Accounts) — 60 accounts, CRUD, UI
- Phase 2 Step 2 (General Ledger) — tables, posting service, reports, UI
  - End-to-end proven: rent receipt posted, plumber bill posted,
    trial balance balanced at $1,775.50
- Phase 2 Step 5 (Receipts) — tenant / owner / other receipts,
  reversal support, GL posting via post_receipt(), tenant
  charges auto-fill, list + new pages, centered detail modal,
  wired into ACCOUNTING.RECEIVABLES menu link
- Phase 2 Step 6 (Bills) — two-step accrual payables, multi-line,
  enter bill + pay bill + reverse, added GL account 2100
  Accounts Payable, list + new pages, centered detail modal,
  wired into ACCOUNTING.PAYABLES menu link (labelled "Bills")
- Phase 2 Step 7 (Bank Deposits) — group un-deposited receipts
  into batches, tag receipts as deposited via deposit_lines,
  list + new pages with centered detail modal, new
  ACCOUNTING.DEPOSITS menu key added. Deposits do NOT post
  to the GL (receipts already credited cash).
- Phase 2 Step 8a (Owner Sub-Ledger Foundation) — added
  owner_id to receipts/bills/gl_entries; created property_owners
  join table + Property.owner_id + ownership_pct for
  AppFolio-parity co-ownership; built owner_ledger service
  (get_owner_subledger, get_all_owner_subledger_totals).
- Phase 2 Step 8b (Financial Diagnostics) — six checks
  (Security Deposit Mismatch, Escrow Cash Mismatch, Clearing
  Accounts, Negative Fee, Positive Fee, Trust 3-Way
  Reconciliation); endpoint + report page replace placeholder.
- Phase 2 Step 9 (Management Fees) — AppFolio-parity two-step
  flow: Run creates a Bill (DR 6001 Management Fees / CR 2100
  Accounts Payable), the manager pays the Bill separately
  (existing Bills flow → DR 2100 AP / CR 1150 Rental Trust).
  Two-tier rate (9% rent + 100% other eligible income).
  Respects subject_to_mgmt_fees, exclude_from_mgmt_fee,
  mgmt_fee_end_date, and mgmt_fee_flat/min overrides.
  new management_fee_runs table; ACCOUNTING.MANAGEMENT_FEES
  menu key.
- Phase 2 Step 10 (Owner Statements) — frozen snapshot per
  owner per period. One section per property (AppFolio default;
  no consolidated view). Per-property beginning cash, running
  balance per transaction, ending cash. Global print CSS hides
  sidebar/top bar so Print gives a clean statement. New
  owner_statements table; ACCOUNTING.OWNER_STATEMENTS menu key.

**What's NOT built yet (designed, not coded):**
- Phase 2 remaining: Universal Notes + Attachments (Step 3),
  Bank Accounts (Step 4), Manual Journal Entry form (Step 2b)
- Write Checks flow (find bills -> confirm -> print) — after Step 7
- Recurring Bills (Section 19)
- Convert Work Order -> Bill (one click) — after Phase 5
- Vendors (as real entity)
- Smart Maintenance (full system)
- Messaging (in-app chat, SMS, email mirror)
- Portals (owner, tenant, crew, vendor)
- Internal team system + platform_users table
- Subscription & Billing engine
- Support ticket system
- Native mobile app (iOS + Android) — Phase 12, after web is done

## A2. WHAT'S BUILT (WORKING)

- Sessions 1-17 (auth, properties, units, people, leases, work
  orders, password reset, org email, uploads, team UI, property
  detail tabs, financials, taxes, policies, utilities, insurance,
  expenses, income, tenant insurance, applicant role, screening,
  OCR settings)
- Phase 1 — Menu Permissions System (4-layer gating, full UI)
- Phase 2 Step 1 — Chart of Accounts (60 accounts, CRUD, UI)
- Phase 2 Step 2 — General Ledger (tables, posting service, reports, UI)
- Phase 2 Step 5 — Receipts (tenant / owner / other + reversal,
  3 tables, post_receipt() service, list + new pages,
  tenant charges auto-fill, centered detail modal)
- Phase 2 Step 6 — Bills (two-step accrual: enter + pay + reverse,
  2 tables, post_bill() + pay_bill() + reverse_bill() services,
  list + new pages, centered detail modal with inline pay form,
  GL account 2100 Accounts Payable seeded)

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
- Reuses the same backend APIs

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

## A5. CURRENT OPEN DECISIONS

- Auto-description rules for Receipt lines: currently rent rows get
  "{Month} rent", fee rows get "{Fee} — {tenant name}". Revisit
  later for finer control (owner-paid insurance, etc.).
- Bill auto-description: not yet built. Could add a similar rule
  later ("Plumbing — kitchen sink" from GL account + free text).
- Reverse confirmation still uses window.confirm(). Fine for now;
  upgrade to a styled modal when we do the polish pass.
- Back-navigation: Trial Balance and Deposits have a smart-back
  button (browser history if present, else /dashboard). Roll this
  out to Receipts/Bills/GL Accounts during the polish pass.
- Mobile: desktop-first for manager app; portals mobile-first
  (Phase 7); native app = Phase 12 (see Section 46).
- Bank Deposits do NOT post to the GL. If we later add a "cash on
  hand" GL account (undeposited funds), we'd add a DR Bank / CR
  Cash on Hand posting in create_deposit(). Documented in
  Section 50.
- Diagnostics currently flag real issues (e.g. the $1,234 tenant
  receipt misclassified as income instead of security-deposit
  liability). Auto-fix postings (e.g. "Refund Negative Diagnostic")
  are deferred; the report is detection only for now.
- Section 12 says 61 GL accounts, but the header comment in
  gl_account.py still says 57. Fix in the next cleanup pass.

---

# ═══════════════════════════════════════════════════
# PART B — NEXT ACTION
# ═══════════════════════════════════════════════════

## B1. IMMEDIATE NEXT ACTION

**Phase 2 Step 4: Bank Accounts.**

Model the two physical trust accounts (Client Trust / Operating
and Security Deposit Trust / Escrow) that map to GL 1150 and
1160. Track bank name, routing #, account #, and (later) ACH
format.

Deliverable:
- `bank_accounts` table (id, organization_id, name,
  bank_name, routing_number, account_number, gl_account_id,
  account_type (OPERATING | ESCROW), ach_format (CSV | NACHA),
  is_active, timestamps)
- Migration: seed the two standard accounts (Client Trust ↔ 1150,
  Security Deposit Trust ↔ 1160) for every existing org
- Backend: model + schema + router
- Frontend: Bank Accounts list + edit pages
- Wire into ACCOUNTING.BANK_ACCOUNTS menu link

Design notes (from Section 13, Section 33):
- Routing # and Account # are sensitive → mark in UI, but
  store plaintext for now (dev). Encrypt at rest in Phase 11.
- ACH setup fields (File Format, Header Options) come with
  the Bank Reconciliation step later; leave columns nullable.
- Link to GL account is required and unique per (org, gl).

Roughly 1 session.

## B1b. AFTER BANK ACCOUNTS

**Phase 2 Step 2b: Manual Journal Entry form.**

The public "create a transaction" endpoint we deferred from
Step 2. Manager picks a date, memo, and at least two lines
(account, debit OR credit, property/unit optional). Must
balance. POST /api/accounting/journal-entries.

Frontend: /dashboard/accounting/journal-entries/new

Roughly 1 session.

That closes Phase 2. Then Phase 3 (Property Detail placeholders).

## B2. AFTER THAT (Phase 2 continued)

1. DONE: Chart of Accounts
2. DONE: General Ledger
3. Universal Notes + Attachments (Step 3) — deferred
4. Bank Accounts (Step 4) — NEXT
5. DONE: Receipts (Step 5)
6. DONE: Bills / Payables (Step 6)
7. DONE: Bank Deposits (Step 7)
8. DONE: Financial Diagnostics (Step 8) — includes owner sub-ledger
9. DONE: Management Fees (Step 9)
10. DONE: Owner Statements (Step 10)
11. Manual Journal Entry form (Step 2b) — after Step 4

## B3. AFTER PHASE 2

Phase 3 — Property Detail Placeholders — ~4 sessions.
Phase 4 — Vendors — ~6 sessions.
Phase 5 — Smart Maintenance — ~20 sessions.
Phase 6 — Messaging — ~6 sessions.
Phase 7 — Portals — ~15 sessions — mobile-first.
Level 1 responsive pass on manager app — ~3 sessions.
Phase 8 — Integrations — ~10 sessions.
Phase 9 — Internal Team + Support — ~10 sessions.
Phase 10 — Subscription & Billing — ~12 sessions.
Phase 11 — Production / AWS — ~5 sessions.
Phase 12 — Native Mobile App — ~40-60 sessions.

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
- Label every command BACKEND or FRONTEND.
- One step at a time. Wait for me to run and report back.
- If I paste an error, fix it and give the next command.
- Backend venv is at backend\venv (not .venv). DB is property_platform.db.
- Role values are UPPERCASE. Menu keys are UPPERCASE and dotted.
- Every GL posting goes through post_transaction().

Then paste this entire file.

---

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

# SECTION 9 — THE 4-LAYER MENU GATING (BUILT)

Layer 1 — Plan gating: STUBBED (always allows). Wires to subscriptions
in Phase 10.
Layer 2 — Role gating: menu_permissions table.
Layer 3 — User overrides: user_permissions table.
Layer 4 — Personal hiding: sidebar_preferences (per-user).

All 4 must pass. If any fails -> hidden.

Hard rules:
- Layers 2, 3, 4 can only SUBTRACT visibility. Only Layer 1 can grant.
- ADMIN role is immutable.
- Parent hidden -> all children hidden.
- Case-insensitive role comparison.
- Every permission change writes to audit_log.

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
Properties: properties, units, property_assignments, property_taxes,
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
- HEAD: 4aa1c77e213c

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

Phase 1  — Menu Permissions System: DONE
Phase 2  — Accounting: IN PROGRESS
  1. DONE Chart of Accounts (60 accounts, seeded; +2100 AP in Step 6)
  2. DONE General Ledger (reversal support)
  3. Universal Notes + Attachments (deferred)
  4. Bank Accounts (Operating + Escrow) <- NEXT
  5. DONE Receipts (tenant + owner + other)
  6. DONE Bills / Payables (two-step accrual)
  7. DONE Bank Deposits (batching, NSF)
  8. DONE Financial Diagnostics (6 checks, includes 3-way recon)
  9. DONE Management Fees (AppFolio two-step: creates a Bill)
 10. DONE Owner Statements
 11. Manual Journal Entry form (Step 2b)
Phase 3  — Property Detail Placeholders (~4 sessions)
Phase 4  — Vendors (~6 sessions)
Phase 5  — Smart Maintenance (~20 sessions)
Phase 6  — Messaging (~6 sessions)
Phase 7  — Portals (~15 sessions, mobile-first)
Level 1  — Responsive pass on manager app (~3 sessions)
Phase 8  — Integrations (~10 sessions)
Phase 9  — Internal Team + Support (~10 sessions)
Phase 10 — Subscription & Billing (~12 sessions)
Phase 11 — Production / AWS (~5 sessions)
Phase 12 — Native Mobile App (React Native, iOS + Android)
           (~40-60 sessions)

Total: ~108 sessions to full web parity, then ~40-60 more for
native mobile.

---

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

# END OF PROJECT_MASTER.md
       '''
       def main():
           MASTER.parent.mkdir(parents=True, exist_ok=True)
           MASTER.write_text(CONTENT, encoding="utf-8")
           print(f"Wrote {len(CONTENT):,} bytes to {MASTER}")
       if __name__ == "__main__":
           main()

3. Run it:
       python rebuild_master_full.py

4. Delete the script:
       Remove-Item rebuild_master_full.py

5. Verify the file:
       Select-String -Path C:\Projects\property-platform\docs\PROJECT_MASTER.md -Pattern "^# SECTION" | Measure-Object | Select-Object -ExpandProperty Count
       Get-Content C:\Projects\property-platform\docs\PROJECT_MASTER.md -Tail 5

   Section count must match the last section number (47 as of
   Step 6). Tail must show "# END OF PROJECT_MASTER.md".

**If the file is too big to fit in a single chat message:**
Split into two scripts (part1 = Parts A+B + Sections 1-20;
part2 = appends Sections 21-47 + footer). Pattern used for the
Step 6 rebuild — see chat history. Verify by section count, not
by eyeballing.

**After the doc is updated:** commit + push (see Section 49).

**Also update the doc when any of these change:**
- Migration chain (Section 11) — new revision IDs go at the bottom
- GL account count (Section 12) — if accounts are added/removed
- Database tables list (Section 10)
- Build order (Section 38) — mark done, mark next
- Part A1 — "Last completed work" bullet
- Part A1 — "What's NOT built yet"
- Part A2 — "What's built"
- Part B1 — "Immediate next action"
- Part B2 — step list (mark done)
- Add a new reference section for the new module (like 45, 47)

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

# END OF PROJECT_MASTER.md
