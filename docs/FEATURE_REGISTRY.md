# FEATURE REGISTRY

**The surface map. Every page. Every slot. Every flag.**
**Last updated: 2026-09-22**

Companion to PROJECT_MASTER.md and PLAN_GAPS.md.

This file is the map. It defines, for every page in the app:

1. Every tab, field, button, section, and behavior AppFolio has on
   that page (or that the plan calls for), whether or not we've built
   it yet.
2. The feature flag that gates each slot.
3. The platform stage that flag is currently at
   (HIDDEN / BETA / ROLLOUT / ALL_ORGS).
4. Which backend endpoints the slot needs.

**The rule (Section 79 of the master doc):** every page ships with
its full planned surface — every slot below exists in the code,
gated by its flag. Unbuilt features render as hidden slots. Flipping
a flag makes a feature appear. No page is ever rewritten.

`check_parity.py` reads this file, verifies every slot is present
in the page source, and fails the build if not. See Section E1 of
PLAN_GAPS.md.

---

## How to read a page block

Each page has:

- **Route** — where the page lives
- **AppFolio reference** — which pages of the Manager Guide this
  maps to
- **JSON id** — the parity checklist item this page belongs to
- **Surface table** — every slot, with its flag, stage, and status
- **Backend endpoints** — what the full surface requires
- **Notes** — edge cases, dependencies, decisions

The **stage** column values:
- **BUILT** — feature is on for all orgs (all_orgs stage + implemented)
- **HIDDEN** — flag exists, code slot exists, feature is off for everyone
- **BETA** — on for specific pilot orgs (list lives in the DB, not this file)
- **ROLLOUT** — on for specific orgs (list lives in the DB)
- **ALL_ORGS** — on for every org (but the slot still needs to be implemented)

The **flag** column is the canonical flag key. Every flag in this
file gets a row in the `feature_flags` table on first migration.
Default stage for any new flag is HIDDEN.

The **status** column tracks whether the slot exists in the code yet:
- ✅ **present** — slot exists and works
- ⬜ **hidden** — slot exists in code, gated by flag, currently off
- ❌ **missing** — not in code yet (this is what the retrofit fixes)

---

## Naming convention

Flags are dotted, lowercase, hierarchical:

    accounting.receipts.tabs
    accounting.receipts.fields.date
    accounting.receipts.cash_automatic
    accounting.receipts.print

Top-level page flag: `{module}.{page}` (e.g. `accounting.receipts`).
Every slot under that page uses the same prefix.

Cross-page flags (like CTRL+K repeat form) live at the top:
`universal.repeat_form`, `universal.repeat_field`.

---

## Page index

*(as pages are added to this file, they appear here)*

| Route | Section in this file | Status |
|---|---|---|
| `/dashboard/accounting/receipts` | §Receipts — list | ✅ written |
| `/dashboard/accounting/receipts/new` | §Receipts — new | ✅ written |
| ... (expands as pages are added) | | |

---

# §Receipts — list page

**Route:** `/dashboard/accounting/receipts`
**AppFolio reference:** Manager Guide pp. 68–72
**JSON id:** `accounting.receipts`
**Page flag:** `accounting.receipts.list`

## Surface

| Slot | Type | Flag | Stage | Status | Notes |
|---|---|---|---|---|---|
| List table | section | accounting.receipts.list.table | ALL_ORGS | ✅ present | |
| Date range filter | field | accounting.receipts.list.filter_date | ALL_ORGS | ✅ present | |
| Type filter (Tenant/Owner/Other) | field | accounting.receipts.list.filter_type | ALL_ORGS | ✅ present | |
| Property filter | field | accounting.receipts.list.filter_property | ALL_ORGS | ✅ present | |
| Include-reversed checkbox | field | accounting.receipts.list.include_reversed | ALL_ORGS | ✅ present | |
| Row: date column | column | accounting.receipts.list.col_date | ALL_ORGS | ✅ present | |
| Row: type column | column | accounting.receipts.list.col_type | ALL_ORGS | ✅ present | |
| Row: from column | column | accounting.receipts.list.col_from | ALL_ORGS | ✅ present | |
| Row: cash account column | column | accounting.receipts.list.col_cash | ALL_ORGS | ✅ present | |
| Row: amount column | column | accounting.receipts.list.col_amount | ALL_ORGS | ✅ present | |
| Detail modal | modal | accounting.receipts.list.detail_modal | ALL_ORGS | ✅ present | |
| Reverse button (in modal) | button | accounting.receipts.reverse | ALL_ORGS | ✅ present | |
| Footer total row | row | accounting.receipts.list.footer_total | ALL_ORGS | ✅ present | |
| **Print button (row)** | button | accounting.receipts.print | HIDDEN | ❌ missing | Opens print layout for one receipt |
| **Repeat button (row)** | button | accounting.receipts.repeat | HIDDEN | ❌ missing | Copies a prior receipt into a new one |
| **Edit-lock after deposit indicator** | indicator | accounting.receipts.edit_lock_after_deposit | HIDDEN | ❌ missing | Row shows a lock icon once deposited |
| **Export CSV / Excel** | button | reporting.export | HIDDEN | ❌ missing | Cross-page, governed by org export-format setting |
| **Print list** | button | accounting.receipts.list.print | HIDDEN | ❌ missing | Print-friendly view of the list |
| **Process NSF button** | button | accounting.receipts.process_nsf | HIDDEN | ❌ missing | Opens NSF workflow (bank fee + tenant charge) |
| **Bulk select + bulk action** | behavior | accounting.receipts.list.bulk | HIDDEN | ❌ missing | Select multiple rows for batch operations |

## Backend endpoints the full surface requires

| Endpoint | Supports flag |
|---|---|
| GET /api/accounting/receipts (list) | built |
| GET /api/accounting/receipts/{id} | built |
| POST /api/accounting/receipts/{id}/reverse | built |
| GET /api/accounting/receipts/{id}/print-data | accounting.receipts.print |
| POST /api/accounting/receipts/{id}/repeat | accounting.receipts.repeat |
| POST /api/accounting/receipts/{id}/process-nsf | accounting.receipts.process_nsf |
| GET /api/accounting/receipts/export | reporting.export |
| GET /api/accounting/receipts/print-view | accounting.receipts.list.print |

## Notes

- Reverse button uses `window.confirm()` today — will move to the
  styled confirm modal during retrofit (Phase 3.5.5).
- Bulk select is a real slot (AppFolio has it) but low priority —
  staging at HIDDEN keeps the code path present without shipping UI.
- Edit-lock indicator reads `deposit_lines` membership — that data
  already exists, so the slot is a UI add only.

---

# §Receipts — new page

**Route:** `/dashboard/accounting/receipts/new`
**AppFolio reference:** Manager Guide pp. 68–72
**JSON id:** `accounting.receipts`
**Page flag:** `accounting.receipts.new`

## Surface — Common (all tabs)

| Slot | Type | Flag | Stage | Status | Notes |
|---|---|---|---|---|---|
| Receipt date field | field | accounting.receipts.fields.date | ALL_ORGS | ✅ present | |
| Cash account dropdown | field | accounting.receipts.fields.cash | ALL_ORGS | ✅ present | |
| Property field | field | accounting.receipts.fields.property | ALL_ORGS | ✅ present | |
| Reference # field | field | accounting.receipts.fields.reference | ALL_ORGS | ✅ present | |
| Remarks field | field | accounting.receipts.fields.remarks | ALL_ORGS | ✅ present | |
| **Cash Account "Automatic" option** | field-option | accounting.receipts.cash_automatic | HIDDEN | ❌ missing | Uses property's default bank |
| **CTRL+K repeat form** | keyboard | universal.repeat_form | HIDDEN | ❌ missing | Copies field values from prior entry |
| **CTRL+J repeat field** | keyboard | universal.repeat_field | HIDDEN | ❌ missing | Repeats the last value typed in this field |
| **Print preview** | button | accounting.receipts.print | HIDDEN | ❌ missing | Print after save |

## Surface — Tenant tab

| Slot | Type | Flag | Stage | Status | Notes |
|---|---|---|---|---|---|
| Tenant picker | field | accounting.receipts.tabs.tenant | ALL_ORGS | ✅ present | |
| Charges table | section | accounting.receipts.charges_table | ALL_ORGS | ✅ present | |
| Auto-description from GL | behavior | accounting.receipts.auto_description | ALL_ORGS | ✅ present | |
| Prepayment checkbox | field | accounting.receipts.prepayment | ALL_ORGS | ✅ present | |
| "+ Add line" button | button | accounting.receipts.tabs.tenant.add_line | ALL_ORGS | ✅ present | |
| Line remove button | button | accounting.receipts.tabs.tenant.remove_line | ALL_ORGS | ✅ present | |
| Running total row | row | accounting.receipts.tabs.tenant.total | ALL_ORGS | ✅ present | |
| **Charge Late Fees button** | button | accounting.receipts.tabs.tenant.charge_late_fees | HIDDEN | ❌ missing | Opens late fee bulk workflow |
| **Charge per-lease picker (multi-unit tenant)** | field | accounting.receipts.tabs.tenant.lease_picker | HIDDEN | ❌ missing | Tenant with multiple leases picks which one |

## Surface — Owner tab

| Slot | Type | Flag | Stage | Status | Notes |
|---|---|---|---|---|---|
| Owner picker | field | accounting.receipts.tabs.owner | ALL_ORGS | ✅ present | |
| Payer name field | field | accounting.receipts.tabs.owner.payer | ALL_ORGS | ✅ present | |
| Amount field | field | accounting.receipts.tabs.owner.amount | ALL_ORGS | ✅ present | |
| Income account dropdown | field | accounting.receipts.tabs.owner.income_account | ALL_ORGS | ✅ present | |

## Surface — Other tab

| Slot | Type | Flag | Stage | Status | Notes |
|---|---|---|---|---|---|
| Received-from field | field | accounting.receipts.tabs.other.received_from | ALL_ORGS | ✅ present | |
| Amount field | field | accounting.receipts.tabs.other.amount | ALL_ORGS | ✅ present | |
| Income account dropdown | field | accounting.receipts.tabs.other.income_account | ALL_ORGS | ✅ present | |
| Exclude-from-mgmt-fee checkbox | field | accounting.receipts.exclude_mgmt_fee | ALL_ORGS | ✅ present | |

## Surface — Application Fee (new tab)

| Slot | Type | Flag | Stage | Status | Notes |
|---|---|---|---|---|---|
| Application Fee tab | tab | accounting.receipts.application_fee_form | HIDDEN | ❌ missing | Dedicated form. Separate from Other. |
| Applicant name field | field | accounting.receipts.application_fee_form.name | HIDDEN | ❌ missing | |
| Amount field | field | accounting.receipts.application_fee_form.amount | HIDDEN | ❌ missing | |
| Property + unit pickers | field | accounting.receipts.application_fee_form.unit | HIDDEN | ❌ missing | |
| GL account (defaults to 4420) | field | accounting.receipts.application_fee_form.gl | HIDDEN | ❌ missing | |
| Cash account | field | accounting.receipts.application_fee_form.cash | HIDDEN | ❌ missing | |
| Reference # | field | accounting.receipts.application_fee_form.reference | HIDDEN | ❌ missing | |

## Backend endpoints the full surface requires

| Endpoint | Supports flag |
|---|---|
| POST /api/accounting/receipts (create) | built |
| GET /api/accounting/receipts/tenant/{id}/open-charges | built |
| GET /api/properties/{id}/default-bank-account | accounting.receipts.cash_automatic |
| POST /api/accounting/receipts/{id}/charge-late-fees | accounting.receipts.tabs.tenant.charge_late_fees |
| POST /api/accounting/receipts/application-fee | accounting.receipts.application_fee_form |

## Notes

- The Cash Account "Automatic" option is AppFolio behavior: when
  selected, the system uses the property's default bank account.
  This depends on `properties.default_bank_account_id` which is a
  Phase 3.5 item (see PLAN_GAPS.md / Section 57).
- The Application Fee tab is a separate form because AppFolio
  separates applicant fees from normal tenant receipts.
- CTRL+K / CTRL+J are universal, not Receipts-specific. They live at
  `universal.repeat_form` and `universal.repeat_field`, gated once,
  used everywhere.

---

# END OF FEATURE_REGISTRY.md (v1 — Receipts sample)

*(The remaining 13 pages will be added in the follow-up session —
the format above is the template.)*