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
