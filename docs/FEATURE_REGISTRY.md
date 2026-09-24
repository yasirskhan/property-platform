# FEATURE REGISTRY

**The surface and access map. Every page. Every capability. Every slot.**
**Last updated: 2026-09-24**

Companion to PROJECT_MASTER.md and PLAN_GAPS.md.

This registry records the planned surface of each page and enough
metadata to implement access correctly without guessing. It follows
Hybrid Capability Gating from PROJECT_MASTER Sections 70, 79, and 80.

## Core rules

1. Pages and independently releasable capabilities may have a release
   gate.
2. Ordinary fields, columns, filters, labels, sorting, and routine form
   controls do **not** get independent release gates.
3. Release control, plan entitlement, org configuration, permissions,
   and user preferences are separate concerns.
4. A non-applicable access layer passes automatically.
5. Backend entitlement/permission enforcement is authoritative. UI
   hiding is never security.
6. `check_parity.py` checks plan/coverage consistency only. Automated
   tests are required to prove behavior.

## How to read a page block

Each page records:

- **Route** — page location
- **AppFolio reference** — reference used for parity planning
- **JSON id** — parity-checklist grouping
- **Page release gate** — only when independent page rollout is useful
- **Surface table** — every meaningful slot
- **Backend endpoints** — backend surface required
- **Notes** — dependencies and edge cases

### Surface columns

- **Release gate** — `release.*` key or `—`
- **Entitlement** — commercial capability key, `core`, or `—`
- **Org config** — `yes`, `no`, or `—`
- **Permission** — permission/menu/action key or `—`
- **User hide** — `yes`, `no`, or `—`
- **Status** — ✅ present / ⬜ hidden implementation present / ❌ missing

A release gate does not imply that a capability is separately saleable.
For example, Print can have an internal release/kill switch while its
entitlement remains `core` or `—`.

## Naming conventions

Release gates are dotted and prefixed with `release.`:

    release.accounting.receipts
    release.accounting.receipts.application_fee
    release.accounting.receipts.process_nsf

Commercial entitlements are stable business-capability keys:

    application_fees
    nsf_processing
    bank_reconciliation

Permission keys use the existing uppercase permission/menu convention
where possible. Action-level permission keys may be introduced later
when a capability needs finer authorization than its page.

---

## Page index

| Route / family | Section | Status |
|---|---|---|
| `/dashboard/accounting/receipts` + `/new` | §Receipts | ✅ written |
| `/dashboard/accounting/bills` + `/new` | §Bills | ✅ written |
| `/dashboard/accounting/deposits` + `/new` | §Bank Deposits | ✅ written |
| `/dashboard/accounting/gl-accounts` | §GL Accounts | ✅ written |
| `/dashboard/accounting/journal-entries` + `/new` + `/[id]` | §Journal Entries | ✅ written |
| `/dashboard/accounting/management-fees` + `/new` | §Management Fees | ✅ written |
| `/dashboard/accounting/owner-statements` + `/new` + `/[id]` | §Owner Statements | ✅ written |
| `/dashboard/accounting/bank-accounts` | §Bank Accounts | ✅ written |
| `/dashboard/accounting/charges` + `/new` | §Charges | ✅ written |
| `/dashboard/properties` + `/[id]` | §Properties | ✅ written |
| `/dashboard/settings/display` | §Settings — Display | ✅ written |
| `/dashboard/settings/currencies` | §Settings — Currencies | ✅ written |
| `/dashboard/settings/permissions` | §Settings — Permissions | ✅ written |
| `/dashboard/settings/sidebar` | §Settings — compatibility route | ✅ written |
| Future settings families | §Settings — planned capability pages | ✅ planned surface written |

## Internal platform application

Phase 3.4.10 added a separate `platform-admin/` Next.js application for platform staff. It is intentionally outside the customer `/dashboard` route registry and uses the platform JWT audience plus its own browser token namespace.

Verified internal surfaces:
- Organizations: platform list/detail and authorized enterprise provisioning.
- Plans: read/manage catalog according to platform role.
- Release Gates: platform stage and organization-allowlist control.
- Fraud Review: platform review queue and audited decisions.
- Staff Audit: platform-actor audit history.

These platform surfaces do not change the customer five-layer access model. Customer release consumption and Settings → Features begin in Phase 3.4.11.


---

# §Receipts — list page

**Route:** `/dashboard/accounting/receipts`  
**AppFolio reference:** Manager Guide pp. 68–72  
**JSON id:** `accounting.receipts`  
**Page release gate:** `release.accounting.receipts`

## Surface

| Slot | Type | Release gate | Entitlement | Org config | Permission | User hide | Status | Notes |
|---|---|---|---|---|---|---|---|---|
| Receipts list page | page | release.accounting.receipts | core | no | ACCOUNTING.RECEIVABLES | yes | ✅ present | Top-level release boundary |
| List table | section | — | — | — | — | — | ✅ present | Inherits page access |
| Date range filter | filter | — | — | — | — | — | ✅ present | Routine control |
| Type filter | filter | — | — | — | — | — | ✅ present | Routine control |
| Property filter | filter | — | — | — | — | — | ✅ present | Routine control |
| Include-reversed checkbox | field | — | — | — | — | — | ✅ present | Routine control |
| Date / type / from / cash / amount columns | columns | — | — | — | — | — | ✅ present | Routine table columns |
| Detail modal | modal | — | — | — | — | — | ✅ present | Part of page |
| Reverse receipt action | action | — | core | no | ACCOUNTING.RECEIVABLES | no | ✅ present | Backend authorization still required; no independent rollout currently needed |
| Footer total row | row | — | — | — | — | — | ✅ present | Routine UI |
| Print one receipt | capability | release.accounting.receipts.print | core | no | ACCOUNTING.RECEIVABLES | no | ⬜ hidden implementation present | Compatibility slot rendered through Flag; endpoint remains planned |
| Repeat prior receipt | capability | release.accounting.receipts.repeat | core | no | ACCOUNTING.RECEIVABLES | no | ⬜ hidden implementation present | Compatibility slot rendered through Flag; workflow remains planned |
| Edit-lock-after-deposit indicator | behavior | — | core | no | ACCOUNTING.RECEIVABLES | no | ⬜ hidden implementation present | Structural compatibility slot present; integrity behavior remains Phase 3.6 |
| Export CSV / Excel | capability | release.reporting.export | core | yes | REPORTING.ALL | no | ⬜ hidden implementation present | Flagged compatibility slot; export endpoint remains planned |
| Print receipts list | capability | release.accounting.receipts.list_print | core | no | ACCOUNTING.RECEIVABLES | no | ⬜ hidden implementation present | Flagged compatibility slot; print view remains planned |
| Process NSF | capability | release.accounting.receipts.process_nsf | nsf_processing | yes | ACCOUNTING.RECEIVABLES | no | ⬜ hidden implementation present | Flagged compatibility slot only; backend workflow remains planned |
| Bulk actions | capability | release.accounting.receipts.bulk | core | no | ACCOUNTING.RECEIVABLES | no | ⬜ hidden implementation present | Flagged compatibility slot; batch workflow remains planned |

## Backend endpoints the full surface requires

| Endpoint | Access requirement | Status |
|---|---|---|
| GET /api/accounting/receipts | page access + permission | built |
| GET /api/accounting/receipts/{id} | page access + row scope | built |
| POST /api/accounting/receipts/{id}/reverse | permission + row scope | built |
| GET /api/accounting/receipts/{id}/print-data | release print + permission | planned |
| POST /api/accounting/receipts/{id}/repeat | release repeat + permission | planned |
| POST /api/accounting/receipts/{id}/process-nsf | release NSF + entitlement if required + org config + permission | planned |
| GET /api/accounting/receipts/export | release export + permission | planned |
| GET /api/accounting/receipts/print-view | release list-print + permission | planned |

## Notes

- Reverse currently uses `window.confirm()` and will move to the shared
  styled confirmation pattern during compatibility work.
- Deposit locking is an integrity rule. It should not disappear merely
  because a release flag is off.
- The existing permission model currently authorizes the Receivables
  area broadly. Action-level permission keys can be added later where
  a real authorization need exists.

---

# §Receipts — new page

**Route:** `/dashboard/accounting/receipts/new`  
**AppFolio reference:** Manager Guide pp. 68–72  
**JSON id:** `accounting.receipts`  
**Page release gate:** `release.accounting.receipts`

## Surface — common

| Slot | Type | Release gate | Entitlement | Org config | Permission | User hide | Status | Notes |
|---|---|---|---|---|---|---|---|---|
| New receipt page | page | release.accounting.receipts | core | no | ACCOUNTING.RECEIVABLES | no | ✅ present | Shares Receipts page release boundary |
| Receipt date | field | — | — | — | — | — | ✅ present | Routine field |
| Cash account | field | — | — | — | — | — | ✅ present | Routine field |
| Property | field | — | — | — | — | — | ✅ present | Routine field |
| Reference # | field | — | — | — | — | — | ✅ present | Routine field |
| Remarks | field | — | — | — | — | — | ✅ present | Routine field |
| Cash Account “Automatic” option | behavior | — | core | yes | ACCOUNTING.RECEIVABLES | no | ⬜ hidden implementation present | Structural compatibility slot present; current 1150 default behavior preserved |
| CTRL+K repeat form | capability | release.universal.repeat_form | core | yes | — | no | ⬜ hidden implementation present | Flagged compatibility slot; shortcut behavior remains planned |
| CTRL+J repeat field | capability | release.universal.repeat_field | core | yes | — | no | ⬜ hidden implementation present | Flagged compatibility slot; shortcut behavior remains planned |
| Print preview | capability | release.accounting.receipts.print | core | no | ACCOUNTING.RECEIVABLES | no | ⬜ hidden implementation present | Flagged compatibility slot; print behavior remains planned |

## Surface — Tenant receipt

| Slot | Type | Release gate | Entitlement | Org config | Permission | User hide | Status | Notes |
|---|---|---|---|---|---|---|---|---|
| Tenant receipt mode | mode | — | core | no | ACCOUNTING.RECEIVABLES | no | ✅ present | Core receipt type |
| Tenant picker | field | — | — | — | — | — | ✅ present | Routine field |
| Charges table | section | — | — | — | — | — | ✅ present | Core tenant-receipt workflow |
| Auto-description from GL | behavior | — | — | — | — | — | ✅ present | Core behavior |
| Prepayment checkbox | field | — | — | — | — | — | ✅ present | Routine field |
| Add/remove line controls | controls | — | — | — | — | — | ✅ present | Routine controls |
| Running total | row | — | — | — | — | — | ✅ present | Routine UI |
| Charge Late Fees | capability | release.accounting.late_fees | late_fees | yes | ACCOUNTING.RECEIVABLES | no | ⬜ hidden implementation present | Flagged compatibility slot; late-fee workflow remains planned |
| Per-lease picker for multi-lease tenant | field | — | — | — | — | — | ❌ missing | Appears when data requires it; not a release capability |

## Surface — Owner receipt

| Slot | Type | Release gate | Entitlement | Org config | Permission | User hide | Status | Notes |
|---|---|---|---|---|---|---|---|---|
| Owner receipt mode | mode | — | core | no | ACCOUNTING.RECEIVABLES | no | ✅ present | Core receipt type |
| Owner picker | field | — | — | — | — | — | ✅ present | |
| Payer name | field | — | — | — | — | — | ✅ present | |
| Amount | field | — | — | — | — | — | ✅ present | |
| Income account | field | — | — | — | — | — | ✅ present | |

## Surface — Other receipt

| Slot | Type | Release gate | Entitlement | Org config | Permission | User hide | Status | Notes |
|---|---|---|---|---|---|---|---|---|
| Other receipt mode | mode | — | core | no | ACCOUNTING.RECEIVABLES | no | ✅ present | Core receipt type |
| Received-from | field | — | — | — | — | — | ✅ present | |
| Amount | field | — | — | — | — | — | ✅ present | |
| Income account | field | — | — | — | — | — | ✅ present | |
| Exclude from management fee | field | — | — | — | — | — | ✅ present | Core accounting field |

## Surface — Application Fee

| Slot | Type | Release gate | Entitlement | Org config | Permission | User hide | Status | Notes |
|---|---|---|---|---|---|---|---|---|
| Application Fee mode/tab | capability | release.accounting.receipts.application_fee | application_fees | yes | ACCOUNTING.RECEIVABLES | no | ⬜ hidden implementation present | Flagged compatibility tab slot; application-fee backend remains planned |
| Applicant name | field | — | — | — | — | — | ❌ missing | Inherits Application Fee access |
| Amount | field | — | — | — | — | — | ❌ missing | |
| Property + unit | fields | — | — | — | — | — | ❌ missing | |
| GL account | field | — | — | — | — | — | ❌ missing | Defaults to 4420 per current plan |
| Cash account | field | — | — | — | — | — | ❌ missing | |
| Reference # | field | — | — | — | — | — | ❌ missing | |

## Backend endpoints the full surface requires

| Endpoint | Access requirement | Status |
|---|---|---|
| POST /api/accounting/receipts | page access + permission | built |
| GET /api/accounting/receipts/tenant/{id}/open-charges | permission + tenant/org scope | built |
| GET /api/properties/{id}/default-bank-account | permission + property/org scope | planned |
| POST /api/accounting/receipts/{id}/charge-late-fees | late-fee release/entitlement/config + permission | planned |
| POST /api/accounting/receipts/application-fee | application-fee release/entitlement/config + permission | planned |

## Notes

- The registry intentionally does not assign gates to every field.
- Access checks for protected workflows must exist on the backend even
  when the frontend also hides the capability.
- The exact commercial packaging of `application_fees`, `nsf_processing`,
  and `late_fees` can evolve without changing the release-gate model.

---
---

# §Bills — list page

**Route:** `/dashboard/accounting/bills`  
**AppFolio reference:** Accounting / Bills & Payables  
**JSON id:** `accounting.bills`  
**Page release gate:** `release.accounting.bills`

## Surface

| Slot | Type | Release gate | Entitlement | Org config | Permission | User hide | Status | Notes |
|---|---|---|---|---|---|---|---|---|
| Bills list page | page | release.accounting.bills | core | no | ACCOUNTING.PAYABLES | yes | ✅ present | Core AP page |
| Date / status / payee filters | filters | — | — | — | — | — | ✅ present | Routine controls |
| Bill table + unpaid footer | section | — | — | — | — | — | ✅ present | Bill #, payee, dates, amount, balance, status |
| Bill detail modal | modal | — | — | — | ACCOUNTING.PAYABLES | — | ✅ present | Includes line details and payment history |
| Pay Bill | capability | — | core | no | ACCOUNTING.PAYABLES | no | ✅ present | Partial payment allowed |
| Reverse unpaid bill | action | — | core | no | ACCOUNTING.PAYABLES | no | ✅ present | Existing reversal rule |
| Reverse after partial payment | behavior | — | core | no | ACCOUNTING.PAYABLES | no | ⬜ hidden implementation present | Structural compatibility slot present; behavior fix remains planned |
| Recurring Bills | capability | release.accounting.bills.recurring | recurring_bills | yes | ACCOUNTING.PAYABLES | no | ⬜ hidden implementation present | Flagged compatibility slot; workflow remains planned |
| Write Checks | capability | release.accounting.write_checks | check_writing | yes | ACCOUNTING.PAYABLES | no | ⬜ hidden implementation present | Flagged compatibility slot; workflow remains planned |
| Enter Credit | capability | release.accounting.vendor_credits | vendor_credits | yes | ACCOUNTING.PAYABLES | no | ⬜ hidden implementation present | Flagged compatibility slot; workflow remains planned |
| Manually Post Bills | capability | release.accounting.bills.manual_post | core | no | ACCOUNTING.PAYABLES | no | ⬜ hidden implementation present | Flagged compatibility slot; workflow remains planned |
| Owner Draw | capability | release.accounting.owner_draw | core | yes | ACCOUNTING.PAYABLES | no | ⬜ hidden implementation present | Flagged compatibility slot; workflow remains planned |
| Tenant Payable | capability | release.accounting.tenant_payable | core | yes | ACCOUNTING.PAYABLES | no | ⬜ hidden implementation present | Flagged compatibility slot; workflow remains planned |
| Convert Work Order to Bill | capability | release.maintenance.work_order_to_bill | maintenance | yes | ACCOUNTING.PAYABLES | no | ⬜ hidden implementation present | Flagged compatibility slot; workflow remains planned |

## Backend surface

| Endpoint / service | Access requirement | Status |
|---|---|---|
| GET `/api/accounting/bills` | release + ACCOUNTING.PAYABLES | built |
| GET `/api/accounting/bills/{id}` | permission + org scope | built |
| POST `/api/accounting/bills/{id}/pay` | permission + org scope + accounting rules | built |
| POST `/api/accounting/bills/{id}/reverse` | permission + org scope + reversal rules | built |
| POST `/api/accounting/bills` | permission + posting rules | built |
| Recurring / credits / check-writing / manual-post services | corresponding release + entitlement/config where applicable + permission | planned |

---

# §Bills — new page

**Route:** `/dashboard/accounting/bills/new`  
**JSON id:** `accounting.bills`  
**Page release gate:** `release.accounting.bills`

## Surface

| Slot | Type | Release gate | Entitlement | Org config | Permission | User hide | Status | Notes |
|---|---|---|---|---|---|---|---|---|
| New Bill page | page | release.accounting.bills | core | no | ACCOUNTING.PAYABLES | no | ✅ present | Core bill-entry workflow |
| Payee / bill date / due date / reference / remarks | fields | — | — | — | — | — | ✅ present | Routine fields |
| Multi-line account/property/description/amount table | section | — | — | — | — | — | ✅ present | Two-step accrual entry |
| Add/remove line controls + total | controls | — | — | — | — | — | ✅ present | Routine controls |
| Real Vendor entity picker | behavior | — | core | no | ACCOUNTING.PAYABLES | no | ⬜ hidden implementation present | Structural compatibility slot present; current payee text behavior preserved |
| Cash Account field at bill entry | field | — | — | — | — | — | ⬜ hidden implementation present | Structural compatibility slot present; field behavior remains planned |
| Post Code for recurring bill | field | — | — | — | — | — | ⬜ hidden implementation present | Structural compatibility slot present; recurring workflow remains planned |
| Delete visibility rule | behavior | — | core | no | ACCOUNTING.PAYABLES | no | ⬜ hidden implementation present | Structural compatibility slot present; delete workflow remains planned |

---

# §Bank Deposits — list page

**Route:** `/dashboard/accounting/deposits`  
**AppFolio reference:** Accounting / Bank Deposits  
**JSON id:** `accounting.deposits`  
**Page release gate:** `release.accounting.deposits`

## Surface

| Slot | Type | Release gate | Entitlement | Org config | Permission | User hide | Status | Notes |
|---|---|---|---|---|---|---|---|---|
| Deposits list page | page | release.accounting.deposits | core | no | ACCOUNTING.DEPOSITS | yes | ✅ present | Core banking workflow |
| Date / bank filters | filters | — | — | — | — | — | ✅ present | Routine controls |
| Deposit table + total footer | section | — | — | — | — | — | ✅ present | Deposit #, date, account, description, total |
| Deposit detail modal | modal | — | — | — | ACCOUNTING.DEPOSITS | — | ✅ present | Shows included receipts |
| No direct reverse rule | behavior | — | core | no | ACCOUNTING.DEPOSITS | no | ✅ present | Corrections through accounting workflow |
| Print Bank Deposit | capability | release.accounting.deposits.print | core | no | ACCOUNTING.DEPOSITS | no | ⬜ hidden implementation present | Flagged compatibility slot; printable view remains planned |
| Edit Bank Deposit | capability | release.accounting.deposits.edit | core | no | ACCOUNTING.DEPOSITS | no | ⬜ hidden implementation present | Flagged compatibility slot; post-creation edit workflow remains planned |
| Process NSF from deposit | capability | release.accounting.deposits.process_nsf | nsf_processing | yes | ACCOUNTING.DEPOSITS | no | ⬜ hidden implementation present | Flagged compatibility slot; correction workflow remains planned |
| Escrow refund | capability | release.accounting.deposits.escrow_refund | escrow_refunds | yes | ACCOUNTING.DEPOSITS | no | ⬜ hidden implementation present | Flagged compatibility slot; escrow-refund workflow remains planned |

---

# §Bank Deposits — new page

**Route:** `/dashboard/accounting/deposits/new`  
**JSON id:** `accounting.deposits`  
**Page release gate:** `release.accounting.deposits`

## Surface

| Slot | Type | Release gate | Entitlement | Org config | Permission | User hide | Status | Notes |
|---|---|---|---|---|---|---|---|---|
| New Bank Deposit page | page | release.accounting.deposits | core | no | ACCOUNTING.DEPOSITS | no | ✅ present | Batch undeposited receipts |
| Bank account / date / deposit # / description | fields | — | — | — | — | — | ✅ present | Routine fields |
| Available receipts table | section | — | — | — | — | — | ✅ present | Select receipts for batch |
| All / None quick select | controls | — | — | — | — | — | ✅ present | Core batch helper |
| Running included count + total | row | — | — | — | — | — | ✅ present | Core UI |
| Date mismatch warning | behavior | — | core | no | ACCOUNTING.DEPOSITS | no | ✅ present | Warns when any selected receipt date differs from the deposit date |
| Deposit number auto-increment per bank | behavior | — | core | yes | ACCOUNTING.DEPOSITS | no | ⬜ hidden implementation present | Structural compatibility slot present; current global deposit numbering remains unchanged |

---

# §GL Accounts

**Route:** `/dashboard/accounting/gl-accounts`  
**AppFolio reference:** Accounting / Chart of Accounts  
**JSON id:** `accounting.coa`  
**Page release gate:** `release.accounting.gl_accounts`

## Surface

| Slot | Type | Release gate | Entitlement | Org config | Permission | User hide | Status | Notes |
|---|---|---|---|---|---|---|---|---|
| Chart of Accounts page | page | release.accounting.gl_accounts | core | no | ACCOUNTING.GL_ACCOUNTS | yes | ✅ present | Core accounting configuration |
| Account groups/list | section | — | — | — | — | — | ✅ present | Existing list surface |
| Add / edit / deactivate account | capability | — | core | no | ACCOUNTING.GL_ACCOUNTS | no | ✅ present | Core CRUD |
| Sub-account nesting | behavior | — | core | no | ACCOUNTING.GL_ACCOUNTS | no | ✅ present | Parent relationship |
| Offset account | field | — | — | — | — | — | ✅ present | Routine account field |
| Subject to management fees | field | — | — | — | — | — | ✅ present | Accounting field |
| Include on cash flow | field | — | — | — | — | — | ✅ present | Accounting field |
| Account ledger link | navigation | — | core | no | ACCOUNTING.GL_ACCOUNTS | no | ✅ present | Links to per-account ledger |
| Must-clear-to-zero setting | field | — | — | — | — | — | ✅ present | Existing model flag is exposed through API, drawer, and list |
| GL Account Permissions | capability | release.accounting.gl_account_permissions | core | yes | SETTINGS.PERMISSIONS | no | ⬜ hidden implementation present | Release-gated compatibility slot; per-account posting rules remain planned |
| Recalculate Balances | capability | release.accounting.gl_accounts.recalculate | core | no | ACCOUNTING.GL_ACCOUNTS | no | ⬜ hidden implementation present | Release-gated compatibility slot; rebuild workflow remains planned |
| Hide semantics | behavior | — | core | yes | ACCOUNTING.GL_ACCOUNTS | no | ✅ present | Existing soft deactivation hides inactive accounts from default pickers while historical references remain |

---

# §Journal Entries — list page

**Route:** `/dashboard/accounting/journal-entries`  
**AppFolio reference:** Accounting / Journal Entries  
**JSON id:** `accounting.je`  
**Page release gate:** `release.accounting.journal_entries`

## Surface

| Slot | Type | Release gate | Entitlement | Org config | Permission | User hide | Status | Notes |
|---|---|---|---|---|---|---|---|---|
| Journal Entries page | page | release.accounting.journal_entries | core | no | ACCOUNTING.JOURNAL_ENTRIES | yes | ✅ present | Core GL workflow |
| Date filters + list | section | — | — | — | — | — | ✅ present | Existing history view |
| History / Recurring tabs | capability | release.accounting.journal_entries.recurring | recurring_journal_entries | yes | ACCOUNTING.JOURNAL_ENTRIES | no | ⬜ hidden implementation present | Release-gated recurring-JE compatibility slot; recurring management remains planned |
| Post GPR | capability | release.accounting.journal_entries.post_gpr | gpr_posting | yes | ACCOUNTING.JOURNAL_ENTRIES | no | ⬜ hidden implementation present | Release-gated compatibility slot; GPR posting workflow remains planned |
| Manually Post Journal Entries | capability | release.accounting.journal_entries.manual_post | core | no | ACCOUNTING.JOURNAL_ENTRIES | no | ✅ present | Existing New Journal Entry workflow posts balanced manual entries through the GL posting service |

---

# §Journal Entries — new page

**Route:** `/dashboard/accounting/journal-entries/new`  
**JSON id:** `accounting.je`  
**Page release gate:** `release.accounting.journal_entries`

## Surface

| Slot | Type | Release gate | Entitlement | Org config | Permission | User hide | Status | Notes |
|---|---|---|---|---|---|---|---|---|
| New Journal Entry page | page | release.accounting.journal_entries | core | no | ACCOUNTING.JOURNAL_ENTRIES | no | ✅ present | Manual balanced JE |
| Date / reference / memo | fields | — | — | — | — | — | ✅ present | Routine fields |
| Multi-line account/property/description/debit/credit grid | section | — | — | — | — | — | ✅ present | Core JE entry |
| Add/remove line controls | controls | — | — | — | — | — | ✅ present | Routine controls |
| Live debit/credit balance | behavior | — | core | no | ACCOUNTING.JOURNAL_ENTRIES | no | ✅ present | Prevents unbalanced submit |
| Remarks vs line description rule | behavior | — | core | no | ACCOUNTING.JOURNAL_ENTRIES | no | ✅ present | Header memo is transaction-level while each posting line carries its own description |

---

# §Journal Entries — detail page

**Route:** `/dashboard/accounting/journal-entries/[id]`  
**JSON id:** `accounting.je`  
**Page release gate:** `release.accounting.journal_entries`

## Surface

| Slot | Type | Release gate | Entitlement | Org config | Permission | User hide | Status | Notes |
|---|---|---|---|---|---|---|---|---|
| Journal Entry detail | page | release.accounting.journal_entries | core | no | ACCOUNTING.JOURNAL_ENTRIES | no | ✅ present | Reads GL transaction detail |
| Header / source / reference metadata | section | — | — | — | — | — | ✅ present | Core detail |
| Debit/credit lines | section | — | — | — | — | — | ✅ present | Core detail |
| Reversal-only integrity | behavior | — | core | no | ACCOUNTING.JOURNAL_ENTRIES | no | ✅ present | No edit/delete of posted GL transaction |

---

# §Management Fees

**Routes:** `/dashboard/accounting/management-fees`, `/dashboard/accounting/management-fees/new`  
**AppFolio reference:** Accounting / Management Fees  
**JSON id:** `accounting.mgmt_fees`  
**Page release gate:** `release.accounting.management_fees`

## Surface

| Slot | Type | Release gate | Entitlement | Org config | Permission | User hide | Status | Notes |
|---|---|---|---|---|---|---|---|---|
| Management Fee runs list | page | release.accounting.management_fees | core | yes | ACCOUNTING.MANAGEMENT_FEES | yes | ✅ present | Existing fee-run history |
| Date filters / detail view | controls | — | — | — | — | — | ✅ present | Routine UI |
| New fee run / preview | page | release.accounting.management_fees | core | yes | ACCOUNTING.MANAGEMENT_FEES | no | ✅ present | Preview before posting |
| Two-tier fee calculation | behavior | — | core | yes | ACCOUNTING.MANAGEMENT_FEES | no | ✅ present | Rent + other income rules |
| Flat / minimum / end-date overrides | settings | — | — | — | — | — | ✅ present | Existing per-property inputs |
| Creates Bill as second step | behavior | — | core | no | ACCOUNTING.MANAGEMENT_FEES | no | ✅ present | Existing accounting spine |
| Pay Owners | capability | release.accounting.pay_owners | owner_payouts | yes | ACCOUNTING.MANAGEMENT_FEES | no | ⬜ hidden implementation present | Release-gated compatibility slot; owner payout workflow remains planned |
| Overcollection strategy | capability | release.accounting.management_fees.overcollection | core | yes | ACCOUNTING.MANAGEMENT_FEES | no | ⬜ hidden implementation present | Release-gated compatibility slot; accounting policy workflow remains planned |
| Management Fee Exclusions | capability | release.accounting.management_fees.exclusions | core | yes | ACCOUNTING.MANAGEMENT_FEES | no | ⬜ hidden implementation present | Release-gated compatibility slot; central exclusions workflow remains planned |
| Post GPR | capability | release.accounting.management_fees.post_gpr | gpr_posting | yes | ACCOUNTING.MANAGEMENT_FEES | no | ⬜ hidden implementation present | Release-gated compatibility slot; GPR-related fee workflow remains planned |

---

# §Owner Statements

**Routes:** `/dashboard/accounting/owner-statements`, `/dashboard/accounting/owner-statements/new`, `/dashboard/accounting/owner-statements/[id]`  
**AppFolio reference:** Accounting / Owner Statements  
**JSON id:** `accounting.owner_statements`  
**Page release gate:** `release.accounting.owner_statements`

## Surface

| Slot | Type | Release gate | Entitlement | Org config | Permission | User hide | Status | Notes |
|---|---|---|---|---|---|---|---|---|
| Statements list | page | release.accounting.owner_statements | core | yes | ACCOUNTING.OWNER_STATEMENTS | yes | ✅ present | Period filter + history |
| Generate statement page | page | release.accounting.owner_statements | core | yes | ACCOUNTING.OWNER_STATEMENTS | no | ✅ present | Owner/period preview and creation |
| Frozen statement detail | page | release.accounting.owner_statements | core | yes | ACCOUNTING.OWNER_STATEMENTS | no | ✅ present | Snapshot prevents later drift |
| Per-property sections | behavior | — | core | no | ACCOUNTING.OWNER_STATEMENTS | no | ✅ present | Existing snapshot structure |
| Running balance | behavior | — | core | no | ACCOUNTING.OWNER_STATEMENTS | no | ✅ present | Existing transaction rendering |
| Beginning / ending cash | behavior | — | core | no | ACCOUNTING.OWNER_STATEMENTS | no | ✅ present | Existing summary |
| Print / Save PDF | capability | — | core | no | ACCOUNTING.OWNER_STATEMENTS | no | ✅ present | Browser print-ready output |
| Required Reserves line | behavior | — | core | yes | ACCOUNTING.OWNER_STATEMENTS | no | ⬜ hidden implementation present | Structural compatibility slot present; real reserve configuration/accounting source remains planned |
| Prepaid Rent line | behavior | — | core | yes | ACCOUNTING.OWNER_STATEMENTS | no | ⬜ hidden implementation present | Structural compatibility slot present; real prepaid-rent accounting source remains planned |
| Property Cash Summary | capability | release.accounting.owner_statements.cash_summary | core | yes | ACCOUNTING.OWNER_STATEMENTS | no | ⬜ hidden implementation present | Release-gated compatibility slot; enhanced owner reporting workflow remains planned |
| Owner Packet customizer | capability | release.owner_portal.packet_customizer | owner_portal | yes | ACCOUNTING.OWNER_STATEMENTS | no | ⬜ hidden implementation present | Release-gated compatibility slot; Phase 7 portal/document workflow remains planned |
| Email statement | capability | release.owner_statements.email | owner_portal | yes | ACCOUNTING.OWNER_STATEMENTS | no | ⬜ hidden implementation present | Release-gated compatibility slot; delivery workflow remains planned |

---

# §Bank Accounts

**Route:** `/dashboard/accounting/bank-accounts`  
**AppFolio reference:** Accounting / Bank Accounts & Reconciliation  
**JSON id:** `accounting.banks`  
**Page release gate:** `release.accounting.bank_accounts`

## Surface

| Slot | Type | Release gate | Entitlement | Org config | Permission | User hide | Status | Notes |
|---|---|---|---|---|---|---|---|---|
| Bank Accounts page | page | release.accounting.bank_accounts | core | no | ACCOUNTING.BANK_ACCOUNTS | yes | ✅ present | Core physical-bank configuration |
| List / detail / add / edit / deactivate | capability | — | core | no | ACCOUNTING.BANK_ACCOUNTS | no | ✅ present | Existing CRUD |
| Bank name / routing / account number | fields | — | — | — | — | — | ✅ present | Sensitive data; backend scope required |
| ACH format | field | — | — | — | — | — | ✅ present | CSV / NACHA field exists |
| Bank Reconciliation | capability | release.accounting.bank_reconciliation | bank_reconciliation | yes | ACCOUNTING.BANK_ACCOUNTS | no | ⬜ hidden implementation present | Major independently releasable workflow |
| QIF Import | capability | release.accounting.bank_reconciliation.qif | bank_reconciliation | yes | ACCOUNTING.BANK_ACCOUNTS | no | ⬜ hidden implementation present | Reconciliation import helper |
| Check Setup | capability | release.accounting.check_setup | check_writing | yes | ACCOUNTING.BANK_ACCOUNTS | no | ⬜ hidden implementation present | Check-layout/configuration |
| ACH File Generation | capability | release.accounting.ach_files | ach_payments | yes | ACCOUNTING.BANK_ACCOUNTS | no | ⬜ hidden implementation present | NACHA / CSV generation |
| $0 ACH Test File | capability | release.accounting.ach_test_file | ach_payments | yes | ACCOUNTING.BANK_ACCOUNTS | no | ⬜ hidden implementation present | Setup verification |
| Check Printing | capability | release.accounting.check_printing | check_writing | yes | ACCOUNTING.BANK_ACCOUNTS | no | ⬜ hidden implementation present | Physical check workflow |
| Bank Feed | capability | release.accounting.bank_feed | bank_feeds | yes | ACCOUNTING.BANK_ACCOUNTS | no | ⬜ hidden implementation present | Future Plaid/generic feed integration |
| Adjustments | capability | release.accounting.bank_adjustments | core | yes | ACCOUNTING.BANK_ACCOUNTS | no | ⬜ hidden implementation present | Adjustment entity/sub-tab |

---

# §Charges — list page

**Route:** `/dashboard/accounting/charges`  
**JSON id:** `accounting.charges`  
**Page release gate:** `release.accounting.charges`

## Surface

| Slot | Type | Release gate | Entitlement | Org config | Permission | User hide | Status | Notes |
|---|---|---|---|---|---|---|---|---|
| Charges list | page | release.accounting.charges | core | no | ACCOUNTING.CHARGES | yes | ✅ present | Existing standalone charges page |
| Date / status filters | filters | — | — | — | — | — | ✅ present | Routine controls |
| Charge table / drill-down | section | — | — | — | — | — | ✅ present | Existing list surface |
| Charge edit rules | behavior | — | core | no | ACCOUNTING.CHARGES | no | ✅ present | Paid floor; no charge-to-credit conversion |
| Bulk tenant charges upload | capability | release.accounting.charges.bulk_upload | bulk_charges | yes | ACCOUNTING.CHARGES | no | ❌ missing | Independent bulk workflow |

---

# §Charges — new page

**Route:** `/dashboard/accounting/charges/new`  
**JSON id:** `accounting.charges`  
**Page release gate:** `release.accounting.charges`

## Surface

| Slot | Type | Release gate | Entitlement | Org config | Permission | User hide | Status | Notes |
|---|---|---|---|---|---|---|---|---|
| New Charge page | page | release.accounting.charges | core | no | ACCOUNTING.CHARGES | no | ✅ present | Core charge-entry workflow |
| Tenant / account / date / amount / description | fields | — | — | — | — | — | ✅ present | Routine fields |
| Submit / cancel | controls | — | — | — | — | — | ✅ present | Routine controls |

---

# §Properties — list page

**Route:** `/dashboard/properties`  
**AppFolio reference:** Properties / Property Directory  
**JSON id:** `properties.core`  
**Page release gate:** `release.properties`

## Surface

| Slot | Type | Release gate | Entitlement | Org config | Permission | User hide | Status | Notes |
|---|---|---|---|---|---|---|---|---|
| Properties list | page | release.properties | core | no | PROPERTIES.ALL | yes | ✅ present | Core property-management page |
| Property cards / unit summary | section | — | — | — | — | — | ✅ present | Existing list surface |
| Add Property navigation | action | — | core | no | PROPERTIES.ADD | no | ✅ present | Existing create route |
| Property Groups | capability | release.properties.groups | property_groups | yes | PROPERTIES.GROUPS | no | ❌ missing | Grouping/filtering capability |
| Map view | capability | release.properties.map | core | yes | PROPERTIES.ALL | no | ❌ missing | Planned map tab/view |

---

# §Property Detail

**Route:** `/dashboard/properties/[id]`  
**AppFolio reference:** Property Detail full tab set  
**JSON id:** `properties.tabs`  
**Page release gate:** `release.properties`

## Current surface

| Slot | Type | Release gate | Entitlement | Org config | Permission | User hide | Status | Notes |
|---|---|---|---|---|---|---|---|---|
| Property header / edit / delete | section | — | core | no | PROPERTIES.ALL | no | ✅ present | Row/org scope required |
| Overview tab | tab | — | core | no | PROPERTIES.ALL | no | ✅ present | Property identity + financial/internal notes summary |
| Units tab | tab | — | core | no | PROPERTIES.UNITS | no | ✅ present | Unit list and unit CRUD navigation |
| Photos tab | tab | — | core | yes | PROPERTIES.ALL | no | ✅ present | Upload, cover, marketing, captions/sort planned/built per current component |
| Utilities tab | tab | — | core | yes | PROPERTIES.ALL | no | ✅ present | Existing property utilities |
| Insurance tab | tab | — | core | yes | PROPERTIES.ALL | no | ✅ present | Existing property insurance |
| Financials tab | tab | — | core | no | PROPERTIES.ALL | no | ✅ present | Financial summary/ownership |
| Taxes tab | tab | — | core | no | PROPERTIES.ALL | no | ✅ present | Tax records CRUD |
| Policies tab | tab | — | core | yes | PROPERTIES.ALL | no | ✅ present | Pet/smoking/lease/insurance/laundry policies |
| Amenities tab | tab | — | core | yes | PROPERTIES.ALL | no | ✅ present | Fee + availability fields |
| Appliances tab | tab | — | core | yes | PROPERTIES.ALL | no | ✅ present | Condition/warranty fields |
| Improvements tab | tab | — | core | yes | PROPERTIES.ALL | no | ✅ present | Cost/category/contractor/warranty |
| Expenses tab | tab | — | core | no | PROPERTIES.ALL | no | ✅ present | Existing expense tracking |
| History tab | tab | — | core | no | PROPERTIES.ALL | no | ✅ present | Audit/history view |
| Default bank account | field | — | — | — | — | — | ❌ missing | Drives Receipt Cash Account “Automatic” |

## Planned additional property capabilities

| Slot | Type | Release gate | Entitlement | Org config | Permission | User hide | Status | Notes |
|---|---|---|---|---|---|---|---|---|
| Photo editor | capability | release.properties.photo_editor | core | yes | PROPERTIES.ALL | no | ❌ missing | Crop / rotate |
| Keys tracking | capability | release.properties.keys | core | yes | PROPERTIES.ALL | no | ❌ missing | Physical key inventory |
| Statement Settings | capability | release.properties.statement_settings | owner_statements | yes | PROPERTIES.ALL | no | ❌ missing | Property-specific owner-statement behavior |
| Non-Revenue tab | capability | release.properties.non_revenue | core | yes | PROPERTIES.ALL | no | ❌ missing | Planned parity tab |
| Staff tab | capability | release.properties.staff | core | yes | PROPERTIES.ALL | no | ❌ missing | Property assignments |
| Budget tab | capability | release.properties.budget | budgeting | yes | PROPERTIES.ALL | no | ❌ missing | Budget workflow |
| Fixed Assets tab | capability | release.properties.fixed_assets | fixed_assets | yes | PROPERTIES.ALL | no | ❌ missing | Maintenance/asset module |
| RUBs tab | capability | release.properties.rubs | rubs | yes | PROPERTIES.ALL | no | ❌ missing | Expansion product |
| Compliance tab | capability | release.properties.compliance | compliance | yes | PROPERTIES.ALL | no | ❌ missing | Program enrollment/recerts/etc. |
| Universal attachments | capability | release.documents.attachments | core | yes | PROPERTIES.ALL | no | ❌ missing | Shared attachment framework across tabs |

## Backend surface

| Endpoint / service | Access requirement | Status |
|---|---|---|
| GET `/properties` | release + PROPERTIES.ALL + org/assignment scope | built |
| POST `/properties` | PROPERTIES.ADD + org scope | built |
| GET/PATCH/DELETE `/properties/{id}` | permission + row scope | built |
| GET `/properties/{id}/history` | permission + row scope | built |
| Unit CRUD under `/properties/{id}/units` | PROPERTIES.UNITS + row scope | built |
| Taxes / utilities / insurance / expenses / amenities / appliances / improvements / photos routers | page permission + property/org scope | built |
| Planned property capability endpoints | corresponding release/entitlement/config + permission + property scope | planned |

---

# §Settings — Display

**Route:** `/dashboard/settings/display`  
**JSON id:** `settings.display`  
**Page release gate:** `release.settings.display`

## Surface

| Slot | Type | Release gate | Entitlement | Org config | Permission | User hide | Status | Notes |
|---|---|---|---|---|---|---|---|---|
| Display settings page | page | release.settings.display | core | no | SETTINGS.DISPLAY | yes | ✅ present | User display preferences |
| Currency selector | field | — | — | — | — | — | ✅ present | Uses org currency list |
| Layout mode | field | — | — | — | — | — | ✅ present | Tabs / Vertical |
| Theme | field | — | — | — | — | — | ✅ present | Light / Dark / Auto |
| Density | field | — | — | — | — | — | ✅ present | Compact / Comfortable / Spacious |
| Date format | field | — | — | — | — | — | ✅ present | US / ISO / EU |
| Number format | field | — | — | — | — | — | ✅ present | US / EU / SPACE |
| Font size | field | — | — | — | — | — | ✅ present | Small / Normal / Large |
| Accent color | field | — | — | — | — | — | ✅ present | User presentation setting |
| Reduce motion | field | — | — | — | — | — | ✅ present | Accessibility preference |

---

# §Settings — Currencies

**Route:** `/dashboard/settings/currencies`  
**JSON id:** `settings.currencies`  
**Page release gate:** `release.settings.currencies`

## Surface

| Slot | Type | Release gate | Entitlement | Org config | Permission | User hide | Status | Notes |
|---|---|---|---|---|---|---|---|---|
| Currencies page | page | release.settings.currencies | core | no | SETTINGS.CURRENCIES | yes | ✅ present | Per-org currency catalog |
| List seeded/custom currencies | section | — | — | — | — | — | ✅ present | 9 defaults seeded per org |
| Add custom currency | action | — | core | yes | SETTINGS.CURRENCIES | no | ✅ present | Code/name/symbol/locale/decimals |
| Edit custom currency | action | — | core | yes | SETTINGS.CURRENCIES | no | ✅ present | Existing CRUD |
| Soft-delete custom currency | action | — | core | yes | SETTINGS.CURRENCIES | no | ✅ present | Existing CRUD |

---

# §Settings — Permissions

**Route:** `/dashboard/settings/permissions`  
**JSON id:** `settings.menu_permissions`  
**Page release gate:** `release.settings.permissions`

## Surface

| Slot | Type | Release gate | Entitlement | Org config | Permission | User hide | Status | Notes |
|---|---|---|---|---|---|---|---|---|
| Permissions page | page | release.settings.permissions | core | no | SETTINGS.PERMISSIONS | yes | ✅ present | Backend re-enforces all edits |
| Roles tab | capability | — | core | yes | SETTINGS.PERMISSIONS | no | ✅ present | Role-by-menu matrix |
| Users tab | capability | — | core | yes | SETTINGS.PERMISSIONS | no | ✅ present | Per-user overrides |
| My Preferences tab | capability | — | core | yes | — | no | ✅ present | Personal order/hiding |
| GL Account Permissions | capability | release.accounting.gl_account_permissions | core | yes | SETTINGS.PERMISSIONS | no | ❌ missing | Finer posting authorization |

---

# §Settings — Sidebar compatibility route

**Route:** `/dashboard/settings/sidebar`  
**JSON id:** `settings.menu_permissions`  
**Page release gate:** —

## Surface

| Slot | Type | Release gate | Entitlement | Org config | Permission | User hide | Status | Notes |
|---|---|---|---|---|---|---|---|---|
| Redirect to Permissions → My Preferences | compatibility route | — | core | no | — | no | ✅ present | Preserves old bookmarks; standalone sidebar page is deprecated |

---

# §Settings — planned capability pages

These settings families are planned but do not yet have current routes
under `/dashboard/settings`. Their eventual route names are finalized
when the page is implemented; capability keys below are the durable
access boundary.

| Capability | Type | Release gate | Entitlement | Org config | Permission | User hide | Status | Notes |
|---|---|---|---|---|---|---|---|---|
| Company / Branding | settings family | release.settings.company | core | yes | SETTINGS | no | ❌ missing | Company identity, logo, address, time zone, packet cover |
| Accounting Settings | settings family | release.settings.accounting | core | yes | ACCOUNTING | no | ❌ missing | Key accounts, GPR, receipts, check writing, basis, fiscal year |
| Security | settings family | release.settings.security | security_controls | yes | SETTINGS | no | ❌ missing | MFA, sessions, IP allowlist, password policy |
| Data / Backup / Retention | settings family | release.settings.data | core | yes | SETTINGS | no | ❌ missing | Backup schedule/restore/export preferences |
| Features | settings family | release.settings.features | core | yes | SETTINGS | no | ✅ built | Org-level capability configuration; release, entitlement, org config, permission, and user preference remain independent |
| Documents | settings family | release.settings.documents | documents | yes | SETTINGS | no | ❌ missing | Templates/export/document defaults |
| Leasing | settings family | release.settings.leasing | leasing | yes | SETTINGS | no | ❌ missing | Leasing configuration |
| Maintenance | settings family | release.settings.maintenance | maintenance | yes | SETTINGS | no | ❌ missing | Maintenance configuration |
| Owners | settings family | release.settings.owners | owner_portal | yes | SETTINGS | no | ❌ missing | Owner configuration |
| Communication | settings family | release.settings.communication | messaging | yes | SETTINGS | no | ❌ missing | Channel/template/quiet-hours configuration |
| Approvals | settings family | release.settings.approvals | approvals | yes | SETTINGS | no | ❌ missing | Approval workflow settings |
| Auditing Center | settings family | release.settings.audit | audit_center | yes | SETTINGS | no | ❌ missing | Queryable audit access/retention |
| Property Groups | settings family | release.settings.property_groups | property_groups | yes | SETTINGS | no | ❌ missing | Property group management |
| Risk / Tags / Affordable | settings family | release.settings.risk_tags_affordable | compliance | yes | SETTINGS | no | ❌ missing | Expansion/compliance settings |
| Developer / API Keys | settings family | release.settings.developer | api_access | yes | SETTINGS | no | ❌ missing | External API keys/integration controls |

---

# Registry completion notes

1. Routine fields and controls intentionally inherit their containing
   page/capability and therefore have no independent release gate.
2. Entitlement keys identify commercial capability boundaries; they do
   not imply that current pricing has already been finalized.
3. Permission keys reuse current menu permissions where available.
   Action-level permissions can be introduced when a real authorization
   need is identified.
4. Backend authorization and entitlement checks remain authoritative.
5. Expansion-product capabilities stay in the registry but do not block
   the Core Launch milestone.

# END OF FEATURE_REGISTRY.md
