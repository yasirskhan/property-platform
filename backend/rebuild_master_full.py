"""
Rebuild PROJECT_MASTER.md with:
  - Phase 2 Steps 5 + 6 marked complete
  - Next action = Step 7 (Bank Deposits)
  - New Section 46 — Mobile Strategy (native app = Phase 12)
  - Phase 12 added to build order
"""

from pathlib import Path

MASTER = Path(r"C:\Projects\property-platform\docs\PROJECT_MASTER.md")

CONTENT = r"""# PROJECT MASTER

**Property Management Platform (AppFolio-equivalent)**
**Single source of truth for the project.**
**Last updated: 2026-09-20**

---

# ═══════════════════════════════════════════════════
# PART A — CURRENT STATE
# ═══════════════════════════════════════════════════

## A1. WHERE WE ARE RIGHT NOW

**Current activity:** Phase 2 (Accounting). Steps 1, 2, 5, 6 COMPLETE. Next is Step 7 (Bank Deposits).

**Last completed work:**
- Phase 1 (Menu Permissions) shipped and working
- Phase 2 Step 1 (Chart of Accounts) — 60 accounts, CRUD, UI
- Phase 2 Step 2 (General Ledger) — tables, posting service, reports, UI
- Phase 2 Step 5 (Receipts) — tenant / owner / other + reversal,
  3 tables, `post_receipt()` service, list + new pages, tenant
  charges auto-fill, centered detail modal
- Phase 2 Step 6 (Bills) — two-step accrual payables, multi-line,
  enter + pay + reverse, GL account 2100 Accounts Payable added,
  list + new pages, centered detail modal

**What's NOT built yet (designed, not coded):**
- Phase 2 remaining: Universal Notes + Attachments (Step 3), Bank
  Accounts (Step 4), Bank Deposits (Step 7), Diagnostics (Step 8),
  Management Fees (Step 9), Owner Statements (Step 10), Manual
  Journal Entry form (Step 2b)
- Write Checks flow (find bills -> confirm -> print)
- Recurring Bills, Convert Work Order -> Bill
- Vendors (real entity), Smart Maintenance, Messaging
- Portals (owner, tenant, crew, vendor)
- Internal team + `platform_users`
- Subscription & Billing engine, Support ticket system
- **Native mobile app (iOS + Android) — Phase 12, after web is done**

## A2. WHAT'S BUILT (WORKING)

- Sessions 1-17 (auth, properties, units, people, leases, work orders,
  password reset, org email, uploads, team UI, property detail tabs,
  financials, taxes, policies, utilities, insurance, expenses, income,
  tenant insurance, applicant role, screening, OCR settings)
- Phase 1 — Menu Permissions System (4-layer gating, full UI)
- Phase 2 Step 1 — Chart of Accounts (61 accounts after Step 6)
- Phase 2 Step 2 — General Ledger (posting service, reports, UI)
- Phase 2 Step 5 — Receipts (3 types + reversal, 2 tables,
  `post_receipt()`, list + new pages, tenant charges auto-fill)
- Phase 2 Step 6 — Bills (two-step accrual, 2 tables,
  `post_bill()` + `pay_bill()` + `reverse_bill()`, list + new pages,
  centered detail modal, GL account 2100 AP seeded)

## A3. TECH STACK

Backend:
- Python 3.12 + FastAPI
- SQLAlchemy ORM
- SQLite (dev) -> PostgreSQL (production later, AWS RDS)
- Alembic for migrations (hand-written only)
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

Deployment target:
- AWS (Lightsail + RDS Postgres for launch; migrate to ECS Fargate later)
- S3 for file uploads
- CloudFront for CDN

## A4. WORKING RULES

1. User is a non-coder. Never ask them to write code. Give whole files, not fragments.
2. Every command must be labelled BACKEND or FRONTEND.
3. Every file must be given whole. Never "add this line."
4. User runs commands and reports back. If error, they paste it.
5. One step at a time. Never give 5 steps at once.
6. Backend commands from C:\Projects\property-platform\backend. Venv at backend\venv (NOT .venv). Activate: .\venv\Scripts\Activate.ps1
7. Frontend commands from C:\Projects\property-platform\frontend.
8. Test accounts (all use test1234): admin@test.com (ADMIN),
   owner1@test.com (OWNER), manager1@test.com (MANAGER),
   crew1@test.com (CREW), tenant1@test.com (TENANT)
9. Never use Alembic autogenerate. Write migrations by hand.
10. Back up DB before risky migrations. DB is property_platform.db.
11. Role values are UPPERCASE. Menu keys are UPPERCASE and dotted.
12. If Next.js 404s on pages that exist, check for stray frontend\app folder.
13. Every GL posting goes through post_transaction(). Never write to GL tables directly.
14. GL account seed count: 61 per org (60 original + 2100 AP from Step 6).

## A5. CURRENT OPEN DECISIONS

- Auto-description rules for Receipt lines: rent rows get "{Month} rent",
  fee rows get "{Fee} — {tenant}". Revisit later.
- Bill auto-description: not built yet. Could add "{Vendor} — {note}".
- Reverse confirmation uses window.confirm(). Upgrade to styled modal later.
- Back-navigation: Trial Balance has smart-back button (history -> fallback
  to /dashboard). Roll this pattern out to other pages when we polish.
- Mobile: desktop-first for manager app; portals mobile-first (Phase 7);
  native app = Phase 12 (see Section 46).

---

# ═══════════════════════════════════════════════════
# PART B — NEXT ACTION
# ═══════════════════════════════════════════════════

## B1. IMMEDIATE NEXT ACTION

**Phase 2 Step 7: Bank Deposits.**

Group un-deposited receipts into a single bank deposit. Bank
account, deposit date, deposit #, description, checkbox list of
receipts, All/None, Make Deposit. Once deposited, a receipt is
locked from being re-deposited.

Deliverable:
- `deposits` table + `deposit_lines` table
- Alembic migration (hand-written)
- Backend: model + schema + router + `post_deposit()` service
- Frontend: Deposits list page + New Deposit page (receipt picker)
- Add `is_deposited` + `deposit_id` to `receipts` (migration)

Design notes (from Section 19):
- Cannot be reversed; corrections via journal entry
- Later: bank reconciliation (Section 37)
- GL: usually tags receipts as "deposited", does not move cash
  between accounts (receipts already hit cash). Optionally a
  BANK_DEPOSIT transaction if a cash-on-hand -> cash-at-bank
  transfer is modeled later.

Roughly 2-3 sessions.

## B2. AFTER THAT (Phase 2 continued)

1. DONE: Chart of Accounts
2. DONE: General Ledger
3. Universal Notes + Attachments (Step 3) — deferred
4. Bank Accounts (Step 4)
5. DONE: Receipts (Step 5)
6. DONE: Bills / Payables (Step 6)
7. **Bank Deposits (Step 7) — NEXT**
8. Financial Diagnostics (Step 8)
9. Management Fees (Step 9)
10. Owner Statements (Step 10)
11. Manual Journal Entry form (Step 2b)

## B3. AFTER PHASE 2

Phase 3 — Property Detail Placeholders (~4 sessions).
Phase 4 — Vendors (~6 sessions).
Phase 5 — Smart Maintenance (~20 sessions).
Phase 6 — Messaging (~6 sessions).
Phase 7 — Portals (~15 sessions) — mobile-first.
Level 1 responsive pass on manager app (~3 sessions).
Phase 8 — Integrations (~10 sessions).
Phase 9 — Internal Team + Support (~10 sessions).
Phase 10 — Subscription & Billing (~12 sessions).
Phase 11 — Production / AWS (~5 sessions).
Phase 12 — Native Mobile App (~40-60 sessions).

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
   Tenant/Vendor/Applicant). Own subdomain.
2. INTERNAL SIDE (ours) — Sales / Billing / Tech / Support / Dev.
3. PUBLIC SIDE — listings, applications, portal access links.

Six isolation levels:
- L6 Platform Support (us), L5 Buyer/Admin, L4 Owners/Managers/Staff,
  L3 Crew/Vendors, L2 Tenants, L1 Applicants.
No level sees another. No customer sees another.

---

# SECTION 3 — DEPLOYMENT MODES

Mode 1 — PM Company. Mode 2 — Single Owner. Mode 3 — Multi-Owner.
Customer types: Landlord, Multi-Property, Management Company,
Firm/Brokerage, HOA (later), Enterprise.

---

# SECTION 4 — USER ROLES

Customer-side (org-scoped): ADMIN, OWNER, MANAGER, CREW, TENANT,
VENDOR, VENDOR_CREW, APPLICANT.
Internal-side (separate platform_users table, Phase 9):
platform_admin, platform_sales, platform_billing, platform_tech,
platform_support, platform_dev.
Hard rule: customer users and platform_users NEVER mix.

---

# SECTION 5 — NAVIGATION STRUCTURE

Sidebar: DASHBOARD, CALENDAR, LEASING, PROPERTIES, PEOPLE,
ACCOUNTING, MAINTENANCE, REPORTING, COMMUNICATION, WHAT'S NEW.
Accounting sub-items: Receipts, Bills, Bank Accounts, Journal Entries,
Bank Transfers, GL Accounts, Diagnostics, Online Payments.
Layout: sidebar 220px + content + optional right panel. Menu visibility
driven by Menu Permissions (Section 42).

---

# SECTION 6 — PAGE STRUCTURE PATTERNS

List pages: header + primary action, filters, table, pagination.
Detail pages: header + Edit/Delete, tabs.
Form pages: label above field, required *, Save/Cancel, inline validation.
Modal pattern (Bills, Receipts): dark backdrop, centered card,
click-outside to close, max-w-2xl, max-h-90vh.

---

# SECTION 7 — UI STYLE GUIDE

Colors: Top bar #1e5aa8, sidebar #1e2a3a, active #2c7be5,
background white/very light gray, table header #f5f5f5, text #333,
border #e0e0e0.
Status: Cancelled RED, Completed GREEN, Pending YELLOW, In Progress BLUE.
Buttons ~36px tall, radius 4-6px, icons lucide-react.

---

# SECTION 8 — UNIVERSAL PATTERNS (every entity)

1. Notes  2. Attachments  3. Audit Log  4. Soft delete
5. Created by / at  6. Updated by / at.

---

# SECTION 9 — THE 4-LAYER MENU GATING (BUILT)

L1 plan (stub) | L2 menu_permissions | L3 user_permissions |
L4 sidebar_preferences. All four must pass. L2/3/4 only SUBTRACT.
ADMIN immutable. Parent hidden -> children hidden. Audited.

---

# SECTION 10 — DATABASE

Tables (~36):
Core: organizations, users, audit_log, platform_settings,
  sidebar_preferences
Menu: menu_permissions, user_permissions
Accounting: gl_accounts, gl_transactions, gl_entries,
  receipts, receipt_lines, bills, bill_lines
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

Multi-tenancy: organization_id on every customer table.
Soft delete: is_active. Timestamps everywhere.

organizations.state: ACTIVE | PAST_DUE | RESTRICTED | SUSPENDED |
CANCELLED (not enforced yet — Phase 10).

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
- HEAD: 71eda8a9ba77

---

# SECTION 12 — THE 61 GL ACCOUNTS

1xxx Assets (8): 1150 Rental Trust, 1160 Security Deposit Cash,
1300 Accounts Receivable, 1610 Land, 1710 Buildings, 1720 Accumulated
Depreciation, 1810 Other Assets, 1820 Other Depreciation.

2xxx Liabilities (5): 2100 Accounts Payable (added Step 6),
2101 Security Deposits, 2300 Prepayment, 2401 Owner Funds, 2600 Mortgage.

4xxx Income (26): 4100 Rent, 4105 Section 8, 4110 M2M, 4115 GPR,
4120 Loss/Gain, 4210 Concessions, 4405 NSF, 4415 Pet Fee (deprecated),
4416 Pet Fee, 4420 Application Fee, 4425 Insurance, 4430 Late Fee,
4435 Utility, 4440 Violation, 4445 Default, 4450 MRA, 4455 Lease
Initiation, 4457 Renewal Fee, 4460 Eviction, 4465 Notice,
4470 Early Termination, 4478 RBP, 4480 PM Charge, 4483 Utility
Reduction, 4490 Option Consideration, 4805 PM Charge.

6xxx Expenses (22): 6001 Management Fees, 6005 Leasing Fee,
6015 Vendor Discounts, 6025 Unknown, 6074 Landscaping, 6076 Cleaning,
6091 Insurance, 6121 Mortgage, 6144 HVAC, 6171 Electric, 6173 Water,
6174 Sewer, 6175 Garbage, 6176 Cable, 6192 Bank Fees, 6215 Water
(RUBs), 6852 Plumbing, 6855 HVAC, 6858 Rekey, 6865 Electrical.

8xxx Admin (2): 8010 Pest, 8050 Computer.

Total: 61 accounts per org.

---

# SECTION 13 — BANK ACCOUNTS

Two physical: Client Trust (Operating), Security Deposit Trust (Escrow).
Two GL: 1150 Rental Trust, 1160 Security Deposit Cash.
Mapping: 1150 <-> Client Trust, 1160 <-> Security Deposit Trust.

---

# SECTION 14 — KEY CORRELATIONS

$300 Correlation: Maintenance Limit = max spend without approval.
$855.95 Correlation: One Other Receipt -> 4420 ($110), 4455 ($150),
4478 ($45.95), 4416 ($550).
-$110 Correlation: Two $55 app fees refunded -> 4420 negative ->
Other Receipt cleared -> Diagnostic passed.
Two-Tier Fee: 9% on Rent, 100% on additional fees.
Reversal pattern: original marked Reversed, new marked Reversal, net $0.
Mgmt Fee Exclusion: checkbox on Other Receipts.

---

# SECTION 15 — PROPERTIES MODULE

Property: name, address, type, year built, sq ft, policies, notes,
audit log. Unit: number, bed/bath, rent, deposit, status.
Property Detail tabs (12+): Overview, Units, Photos, Utilities,
Insurance, Financials, Taxes, Policies, Amenities, Appliances,
Improvements, Expenses, History.
Property Groups + Budget tab + Map tab.

---

# SECTION 16 — PEOPLE MODULE

Sub-tabs: Tenants, Owners, Vendors.
Tags across everyone. Searchable. Importable.

---

# SECTION 17 — TENANT LIFECYCLE

Move In (5 steps). Move Out (5 steps). Renew. Increase Rent.
Convert to M2M. Additional Tenants. Details in AppFolio guide.

---

# SECTION 18 — LEASING MODULE

Listings, Applications, Screening, Lease Templates, CRM.

---

# SECTION 19 — ACCOUNTING MODULE

Top tabs: Receipts | Bills | Bank Accounts | Journal Entries |
Bank Transfers | GL Accounts | Diagnostics | Online Payments.

Chart of Accounts: 61 per org.
General Ledger: every transaction; reversal only.
Receipts (BUILT, Step 5): 3 types.
Bills (BUILT, Step 6): two-step accrual (Enter -> DR Expense / CR AP;
Pay -> DR AP / CR Cash; Reverse only if unpaid).
Recurring Bills (later). Write Checks (later). Credits. Owner Draw.
Management Fees (Step 9). Pay Owners. Tenant Payable. Transfers.
Bank Deposits (Step 7 — NEXT). Bank Accounts (Step 4). Reconcile.
Journal Entries. Post GPR.

---

# SECTION 20 — MAINTENANCE MODULE

Work Orders, Recurring, Inspections, Unit Turns, Projects, Purchase
Orders, Inventory, Fixed Assets. Convert WO -> Bill (one click).

---

# SECTION 21 — SMART MAINTENANCE

Groups, Urgencies, Contacts, Dispatch, On-Call, Preferred Vendors,
Assignment logic, Escalation.

---

# SECTION 22 — TENANT PORTAL

Home, Payments, Maintenance, Contact Us, Shared Documents, Insurance,
Property Details, Account Profile, Help. Smart intake. Duplicate detect.
Mobile-first (Phase 7).

---

# SECTION 23 — OWNER PORTAL

One-time email link. Owner Packet. Statement with transaction table,
beginning/ending cash, property cash summary. Mobile-first.

---

# SECTION 24 — VENDOR PORTAL

Created on first WO email click. Work Order card. Invoices. Notes with
photos. Mobile-first.

---

# SECTION 25 — CREW PORTAL

Home, My Work Orders, My Schedule, Time Tracking, Messages, Profile.
Accept/Reject jobs, ETA, log hours. Mobile-first.

---

# SECTION 26 — MESSAGING LAYER

In-app chat (WebSockets), then native mobile push, then WhatsApp optional.
Read receipts, attachments, email mirroring.

---

# SECTION 27 — NOTIFICATION LAYER

Date, time, sent by, channel, recipient, status, body, template,
attachments, reply, related entity. In-app + email always; SMS if offline.
Tracking page token-protected. Templates. Twilio for SMS/Voice.

---

# SECTION 28 — INTERNAL TEAM

Roles: Sales, Billing, Tech, Support, Dev. Lifecycle:
Sales -> Billing -> Tech -> Support -> Dev. Isolated platform_users table.

---

# SECTION 29 — SUPPORT TICKET SYSTEM

Category, priority, thread, status. Routing by category. Temp access
via time-limited tokens. Logged. Auto-expires.

---

# SECTION 30 — SUBSCRIPTION & BILLING

Property count tiers, modules, packages vs à la carte (hybrid
recommended). Provider: Stripe. Lifecycle:
ACTIVE -> PAST_DUE -> RESTRICTED -> SUSPENDED -> CANCELLED.

---

# SECTION 31 — SETTINGS MODULE

12 sections. Company, Accounting, My Settings, Users, Menu Permissions,
Auditing Center.

---

# SECTION 32 — APPFOLIO MANAGER GUIDE EXTRACT

Reports catalog: Tenant (7), Property & Unit (12), Owner & Vendor (5),
Accounting (12), Transaction (9). Letters with mail merge.

---

# SECTION 33 — BANK ACCOUNTS + ACH SETUP

Establish ACH. Setup in system. Test with $0 file.

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

Receipt, eCheck, CC receipt, Reversed Receipt, Reversal Receipt, Bank
Transfer, Transfer, Check, Clearing Account, Owner Contribution,
Management Fee.

---

# SECTION 37 — BANK RECONCILIATION

Account to Reconcile, Statement Date, Ending Balance. Check off
deposits + credits, checks + payments. QIF Import. Balanced -> Reconcile.

---

# SECTION 38 — FULL BUILD ORDER

Phase 1  — Menu Permissions System: DONE
Phase 2  — Accounting: IN PROGRESS
  1. DONE Chart of Accounts
  2. DONE General Ledger
  3. Universal Notes + Attachments (deferred)
  4. Bank Accounts
  5. DONE Receipts
  6. DONE Bills / Payables
  7. Bank Deposits <- NEXT
  8. Financial Diagnostics
  9. Management Fees
 10. Owner Statements
 11. Manual Journal Entry form
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
3. Backend commands from backend folder, venv active.
4. Frontend commands from frontend folder.
5. Every new model imported in init_db.py.
6. Every new router gets 2 lines in main.py.
7. Verify file size after saving (0 bytes = paste failed).
8. Hard refresh (Ctrl+Shift+R) after frontend changes.
9. Restart servers after config changes.
10. Commit to Git after every working module.
11. bcrypt==4.0.1 stays pinned.
12. Never Alembic autogenerate.
13. Always write migrations by hand.
14. Always back up DB before risky migrations.
15. DB is property_platform.db.
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

Canonical keys in app/constants/menu_keys.py (46 keys). Display in
src/lib/menuConfig.ts.
Tables: menu_permissions, user_permissions, sidebar_preferences.
Resolver: app/services/menu_resolver.py.
Endpoints under /api/menu.
Layers 2/3/4 only subtract. ADMIN immutable. Every change audited.

---

# SECTION 43 — THREE-BOUNDARY ARCHITECTURE

B1 Data isolation: organization_id everywhere.
B2 Identity isolation: users vs platform_users never mix.
B3 Commercial channel: subscriptions, invoices, tickets, provisioning.
Support access = time-limited token scoped to a ticket.

---

# SECTION 44 — GENERAL LEDGER (BUILT)

The GL is the single source of truth for all money movement.

Tables: gl_transactions (parent), gl_entries (children).
Rule: ALL writes through post_transaction() in
app/services/gl_posting.py. Never write to GL tables directly.
Enforces: valid type, >=2 lines, exactly one of DR/CR per line,
DR total == CR total, org scope, property scope, unit scope.
Reversal: never edit/delete. Call reverse_transaction().
Endpoints under /api/accounting.

---

# SECTION 45 — RECEIPTS (BUILT — Phase 2 Step 5)

Three types: TENANT, OWNER, OTHER.
Tables: receipts, receipt_lines.
Migration: 64dec42acecf (down_revision = b2d5f9e1c3a7).
Rule: all postings via post_receipt() (calls post_transaction with
transaction_type="RECEIPT"). DR cash, CR income lines. Sum must equal
receipt.amount.
Reversal: reverse_receipt() calls reverse_transaction().
Endpoints under /api/accounting/receipts:
  GET "" list
  GET /tenant/{user_id}/open-charges
  GET /{receipt_id}
  POST ""
  POST /{receipt_id}/reverse
Note: Lease has no organization_id; scope via Unit -> Property.
Lease uses tenant_id, not tenant_user_id.
Frontend: /dashboard/accounting/receipts (list) and /new (3 tabs).
Menu: ACCOUNTING.RECEIVABLES -> Receipts.
Auto-description: 4100 -> "{Month} rent"; 4105 -> "{Month} Section 8";
4110 -> "{Month} rent (M2M)"; 4416..4480, 2101 -> "{Label} — {tenant}";
fallback -> GL account name. Never overwrites manual text.

---

# SECTION 46 — MOBILE STRATEGY

End goal: full native mobile app (Level 3) for iOS + Android.

Interim plan (do these in order):
1. Desktop-first for the manager web app (now -> end of Phase 10).
2. Mobile-first for portals (Phase 7). Cards, bottom nav, big taps.
3. Level 1 responsive pass on manager web app (~3 sessions after
   Phase 7): sidebar collapses to hamburger below 768px; tables get
   horizontal scroll; modals go full-screen on mobile; form grids
   stack to single column. Result: usable on a phone, still desktop UI.
4. Phase 12 — Native Mobile App (after Phase 11). React Native / Expo.
   Reuses the same backend APIs.

Why native comes last:
- Backend is the foundation. APIs must exist first.
- Building earlier = rebuild every time the backend changes.
- Mobile-optimized web app is enough until real demand.

Native app cost & effort (Phase 12):
- ~40-60 sessions
- Apple Developer: $99/year
- Google Play: $25 one-time
- Push: Firebase (free tier covers early scale)
- Ongoing maintenance per OS release

Native app v1 scope:
- Tenant: balance, pay rent, submit maintenance, push, docs
- Crew: accept/reject, log hours, photos, ETA pushes
- Manager: approvals, WO triage, notifications
- Owner: statements, approve spend over maintenance limit

Rule for now: don't spend time on mobile-specific code in the web app
beyond what Phase 7 portals already need.

---

# SECTION 47 — BILLS (BUILT — Phase 2 Step 6)

Two-step accrual payables.
Enter -> GL: DR Expense line(s) / CR Accounts Payable.
Pay   -> GL: DR Accounts Payable / CR Cash.
Reverse (only if unpaid) -> flips the original GL entry.

Tables: bills, bill_lines.
Migration: 71eda8a9ba77 (down_revision = 64dec42acecf).
Also seeded GL account 2100 Accounts Payable for every org.

Bill fields: bill_number (auto B-00001 if blank), payee_name,
payee_user_id (optional link to a User), bill_date, due_date,
reference_number, amount, amount_paid, status (UNPAID | PARTIAL |
PAID | VOID), property_id, unit_id, payable_gl_account_id,
remarks, notes, source_type, source_id, gl_transaction_id,
is_reversed, reversal_of_id, is_active.

BillLine fields: bill_id, gl_account_id, property_id, unit_id,
description, amount.

Services: post_bill(), pay_bill(), reverse_bill() in
app/services/bill_posting.py.

Endpoints under /api/accounting/bills:
  GET  ""                          list (date/status/payee filters)
  GET  /{bill_id}                  detail + lines
  POST ""                          enter bill
  POST /{bill_id}/pay              pay (partial allowed)
  POST /{bill_id}/reverse          reverse (only if unpaid)

Frontend pages:
- /dashboard/accounting/bills        list + filters + centered modal
- /dashboard/accounting/bills/new    enter bill (multi-line)

Menu: ACCOUNTING.PAYABLES -> Bills (label updated from "Payables").

Detail modal includes an inline Pay form (amount, date, cash account,
reference, remarks). No browser prompts.

---

# END OF PROJECT_MASTER.md
"""


def main() -> None:
    MASTER.parent.mkdir(parents=True, exist_ok=True)
    MASTER.write_text(CONTENT, encoding="utf-8")
    print(f"Wrote {len(CONTENT):,} bytes to {MASTER}")


if __name__ == "__main__":
    main()