# FEATURE REGISTRY

**The surface and access map. Every page. Every capability. Every slot.**
**Last updated: 2026-09-23**

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
| Print one receipt | capability | release.accounting.receipts.print | core | no | ACCOUNTING.RECEIVABLES | no | ❌ missing | Internal rollout/kill switch; not a separate paid feature |
| Repeat prior receipt | capability | release.accounting.receipts.repeat | core | no | ACCOUNTING.RECEIVABLES | no | ❌ missing | Copies prior receipt into new form |
| Edit-lock-after-deposit indicator | behavior | — | core | no | ACCOUNTING.RECEIVABLES | no | ❌ missing | Data integrity behavior, not a saleable/release module |
| Export CSV / Excel | capability | release.reporting.export | core | yes | REPORTING.ALL | no | ❌ missing | Cross-page export capability |
| Print receipts list | capability | release.accounting.receipts.list_print | core | no | ACCOUNTING.RECEIVABLES | no | ❌ missing | Print-friendly list |
| Process NSF | capability | release.accounting.receipts.process_nsf | nsf_processing | yes | ACCOUNTING.RECEIVABLES | no | ❌ missing | Backend must enforce entitlement + permission |
| Bulk actions | capability | release.accounting.receipts.bulk | core | no | ACCOUNTING.RECEIVABLES | no | ❌ missing | Batch operations |

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
| Cash Account “Automatic” option | behavior | — | core | yes | ACCOUNTING.RECEIVABLES | no | ❌ missing | Configuration/behavior, not independently released |
| CTRL+K repeat form | capability | release.universal.repeat_form | core | yes | — | no | ❌ missing | Cross-page productivity capability |
| CTRL+J repeat field | capability | release.universal.repeat_field | core | yes | — | no | ❌ missing | Cross-page productivity capability |
| Print preview | capability | release.accounting.receipts.print | core | no | ACCOUNTING.RECEIVABLES | no | ❌ missing | Same print capability as list page |

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
| Charge Late Fees | capability | release.accounting.late_fees | late_fees | yes | ACCOUNTING.RECEIVABLES | no | ❌ missing | Separate workflow |
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
| Application Fee mode/tab | capability | release.accounting.receipts.application_fee | application_fees | yes | ACCOUNTING.RECEIVABLES | no | ❌ missing | Independently releasable workflow |
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
| Reverse after partial payment | behavior | — | core | no | ACCOUNTING.PAYABLES | no | ❌ missing | Planned AppFolio behavior fix |
| Recurring Bills | capability | release.accounting.bills.recurring | recurring_bills | yes | ACCOUNTING.PAYABLES | no | ❌ missing | Independent recurring workflow |
| Write Checks | capability | release.accounting.write_checks | check_writing | yes | ACCOUNTING.PAYABLES | no | ❌ missing | Payment/check workflow |
| Enter Credit | capability | release.accounting.vendor_credits | vendor_credits | yes | ACCOUNTING.PAYABLES | no | ❌ missing | Vendor credit workflow |
| Manually Post Bills | capability | release.accounting.bills.manual_post | core | no | ACCOUNTING.PAYABLES | no | ❌ missing | Search/select/post workflow |
| Owner Draw | capability | release.accounting.owner_draw | core | yes | ACCOUNTING.PAYABLES | no | ❌ missing | Owner payable workflow |
| Tenant Payable | capability | release.accounting.tenant_payable | core | yes | ACCOUNTING.PAYABLES | no | ❌ missing | Tenant payable workflow |
| Convert Work Order to Bill | capability | release.maintenance.work_order_to_bill | maintenance | yes | ACCOUNTING.PAYABLES | no | ❌ missing | Cross-module workflow |

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
| Real Vendor entity picker | behavior | — | core | no | ACCOUNTING.PAYABLES | no | ❌ missing | Current UI uses payee text; vendor entity planned |
| Cash Account field at bill entry | field | — | — | — | — | — | ❌ missing | Planned parity field |
| Post Code for recurring bill | field | — | — | — | — | — | ❌ missing | Applies when recurring capability is active |
| Delete visibility rule | behavior | — | core | no | ACCOUNTING.PAYABLES | no | ❌ missing | Delete only when unpaid |

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
| Print Bank Deposit | capability | release.accounting.deposits.print | core | no | ACCOUNTING.DEPOSITS | no | ❌ missing | Deposit slip / printable view |
| Edit Bank Deposit | capability | release.accounting.deposits.edit | core | no | ACCOUNTING.DEPOSITS | no | ❌ missing | Post-creation edit rules required |
| Process NSF from deposit | capability | release.accounting.deposits.process_nsf | nsf_processing | yes | ACCOUNTING.DEPOSITS | no | ❌ missing | Links deposit/receipt correction workflow |
| Escrow refund | capability | release.accounting.deposits.escrow_refund | escrow_refunds | yes | ACCOUNTING.DEPOSITS | no | ❌ missing | Deposit refund from escrow |

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
| Date mismatch warning | behavior | — | core | no | ACCOUNTING.DEPOSITS | no | ❌ missing | Warn when receipt and deposit dates differ |
| Deposit number auto-increment per bank | behavior | — | core | yes | ACCOUNTING.DEPOSITS | no | ❌ missing | Bank-specific numbering rule |

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
| Must-clear-to-zero setting | field | — | — | — | — | — | ❌ missing | Supports positive-fee diagnostic |
| GL Account Permissions | capability | release.accounting.gl_account_permissions | core | yes | SETTINGS.PERMISSIONS | no | ❌ missing | Restricts posting by account |
| Recalculate Balances | capability | release.accounting.gl_accounts.recalculate | core | no | ACCOUNTING.GL_ACCOUNTS | no | ❌ missing | Administrative rebuild action |
| Hide semantics | behavior | — | core | yes | ACCOUNTING.GL_ACCOUNTS | no | ❌ missing | Hidden from pickers, retained in reports |

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
| History / Recurring tabs | capability | release.accounting.journal_entries.recurring | recurring_journal_entries | yes | ACCOUNTING.JOURNAL_ENTRIES | no | ❌ missing | Adds recurring-JE management |
| Post GPR | capability | release.accounting.journal_entries.post_gpr | gpr_posting | yes | ACCOUNTING.JOURNAL_ENTRIES | no | ❌ missing | Gross Potential Rent posting |
| Manually Post Journal Entries | capability | release.accounting.journal_entries.manual_post | core | no | ACCOUNTING.JOURNAL_ENTRIES | no | ❌ missing | Search/select/post workflow |

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
| Remarks vs line description rule | behavior | — | core | no | ACCOUNTING.JOURNAL_ENTRIES | no | ❌ missing | Statement-level vs line-level semantics |

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
| Pay Owners | capability | release.accounting.pay_owners | owner_payouts | yes | ACCOUNTING.MANAGEMENT_FEES | no | ❌ missing | Distribute remaining trust funds |
