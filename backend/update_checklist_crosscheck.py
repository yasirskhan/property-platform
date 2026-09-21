# update_checklist_crosscheck.py
#
# Adds the AppFolio cross-check items to APPFOLIO_PARITY_CHECKLIST.json.
# Updates _meta. Idempotent. Backs up before writing.
#
# Source of truth for what's added: PROJECT_MASTER.md Section 66 (roadmap).
# Source for what's already there: existing APPFOLIO_PARITY_CHECKLIST.json.

from pathlib import Path
import json
import shutil
import sys
from datetime import date

JSON_PATH = Path(r"C:\Projects\property-platform\docs\APPFOLIO_PARITY_CHECKLIST.json")
BACKUP_PATH = JSON_PATH.with_suffix(".json.backup-before-crosscheck")

if not JSON_PATH.exists():
    print(f"ERROR: {JSON_PATH} not found.")
    sys.exit(1)

# Backup once
if not BACKUP_PATH.exists():
    shutil.copy2(JSON_PATH, BACKUP_PATH)
    print(f"Backed up to {BACKUP_PATH}")
else:
    print(f"Backup already exists at {BACKUP_PATH} (not overwritten)")

data = json.loads(JSON_PATH.read_text(encoding="utf-8"))

if "items" not in data or not isinstance(data["items"], list):
    print("ERROR: JSON missing top-level 'items' list.")
    sys.exit(2)

existing_ids = {it["id"] for it in data["items"]}
print(f"Existing items: {len(existing_ids)}")

# ------------------------------------------------------------------
# New items to add (from Section 66 Gap Summary).
# Format matches existing items: id, area, feature, status, phase.
# All default to status="scheduled" unless noted.
# ------------------------------------------------------------------
NEW_ITEMS = [
    # --- Accounting / Chart of Accounts ---
    {"id": "accounting.coa.recalculate_balances", "area": "Accounting / Chart of Accounts",
     "feature": "Recalculate Balances button (rebuild cached balances after COA edits)", "phase": "3.6"},
    {"id": "accounting.coa.hide_semantics", "area": "Accounting / Chart of Accounts",
     "feature": "GL account Hide (excluded from pickers, still on reports)", "phase": "3.6"},

    # --- Accounting / Journal Entries ---
    {"id": "accounting.je.sub_tabs", "area": "Accounting / Journal Entries",
     "feature": "Journal Entry sub-tabs (History | Recurring)", "phase": "3.6"},
    {"id": "accounting.je.manually_post", "area": "Accounting / Journal Entries",
     "feature": "Manually Post Journal Entries (search + post)", "phase": "3.6"},
    {"id": "accounting.je.remarks_vs_description", "area": "Accounting / Journal Entries",
     "feature": "Remarks (statement-level) vs Description (line-level) rule", "phase": "3.6"},

    # --- Accounting / Receipts ---
    {"id": "accounting.receipts.print", "area": "Accounting / Receipts",
     "feature": "Print receipt", "phase": "3.6"},
    {"id": "accounting.receipts.repeat", "area": "Accounting / Receipts",
     "feature": "Repeat Receipt button", "phase": "3.6"},
    {"id": "accounting.receipts.edit_lock_after_deposit", "area": "Accounting / Receipts",
     "feature": "Lock GL Account + Cash Account after deposit", "phase": "3.6"},
    {"id": "accounting.receipts.cash_account_automatic", "area": "Accounting / Receipts",
     "feature": "Cash Account 'Automatic' default (uses property default bank)", "phase": "3.6"},

    # --- Accounting / Charges ---
    {"id": "accounting.charges.enter_charge", "area": "Accounting / Charges",
     "feature": "Enter Charge (standalone form)", "phase": "3.6"},
    {"id": "accounting.charges.list_view", "area": "Accounting / Charges",
     "feature": "Charges list view (From/To date, Show, drill-down)", "phase": "3.6"},
    {"id": "accounting.charges.edit_rules", "area": "Accounting / Charges",
     "feature": "Charge edit rules (paid floor, no charge->credit conversion)", "phase": "3.6"},

    # --- Accounting / Bills ---
    {"id": "accounting.bills.cash_account_field", "area": "Accounting / Bills",
     "feature": "Cash Account field on Enter Bill (not only Pay step)", "phase": "3.6"},
    {"id": "accounting.bills.post_codes", "area": "Accounting / Bills",
     "feature": "Post Codes for recurring bills", "phase": "3.6"},
    {"id": "accounting.bills.manually_post", "area": "Accounting / Bills",
     "feature": "Manually Post Bills (search + select + Post)", "phase": "3.6"},
    {"id": "accounting.bills.delete_rules", "area": "Accounting / Bills",
     "feature": "Delete Bill only if unpaid (link visibility rule)", "phase": "3.6"},

    # --- Accounting / Checks ---
    {"id": "accounting.checks.list_view", "area": "Accounting / Checks",
     "feature": "Checks list view (From/To date, Show, drill-down)", "phase": "3.6"},
    {"id": "accounting.checks.void", "area": "Accounting / Checks",
     "feature": "Void Check (Void Payment link + confirmation)", "phase": "3.6"},

    # --- Accounting / Transfer Funds ---
    {"id": "accounting.transfer_funds", "area": "Accounting / Transfer Funds",
     "feature": "Transfer Funds (from property, to property, direction arrow, amount, date)", "phase": "3.6"},

    # --- Accounting / Deposits ---
    {"id": "accounting.deposits.print", "area": "Accounting / Deposits",
     "feature": "Print Bank Deposit (deposit slip)", "phase": "3.6"},
    {"id": "accounting.deposits.date_warning", "area": "Accounting / Deposits",
     "feature": "Receipt-vs-deposit date mismatch warning dialog", "phase": "3.6"},
    {"id": "accounting.deposits.number_per_bank", "area": "Accounting / Deposits",
     "feature": "Deposit number auto-increment per bank account", "phase": "3.6"},
    {"id": "accounting.deposits.edit", "area": "Accounting / Deposits",
     "feature": "Edit bank deposit after creation", "phase": "3.6"},

    # --- Accounting / Bank Accounts ---
    {"id": "accounting.bank_accounts.adjustments", "area": "Accounting / Bank Accounts",
     "feature": "Bank Account Adjustments (entity + sub-tab list + Make Adjustment)", "phase": "3.6"},
    {"id": "accounting.banks.zero_dollar_test_file", "area": "Accounting / Bank Accounts",
     "feature": "$0 ACH Test File generation", "phase": "3.6"},

    # --- Accounting / Owners ---
    {"id": "accounting.owners.owner_held_security_deposits", "area": "Accounting / Owners",
     "feature": "Owner Held Security Deposits (GL setup + Key Accounts + Move In use)", "phase": "3.6"},

    # --- Accounting / Reports (named in 3.7) ---
    {"id": "accounting.reports.security_deposit_detail", "area": "Accounting / Reports",
     "feature": "Security Deposit Funds Detail report", "phase": "3.7"},
    {"id": "accounting.reports.aged_receivables", "area": "Accounting / Reports",
     "feature": "Aged Receivables Summary report", "phase": "3.7"},
    {"id": "accounting.reports.charge_detail", "area": "Accounting / Reports",
     "feature": "Charge Detail report", "phase": "3.7"},
    {"id": "accounting.reports.expense_register", "area": "Accounting / Reports",
     "feature": "Expense Register report", "phase": "3.7"},
    {"id": "accounting.reports.income_register", "area": "Accounting / Reports",
     "feature": "Income Register report", "phase": "3.7"},

    # --- Settings / Accounting ---
    {"id": "settings.accounting.accounting_basis", "area": "Settings / Accounting",
     "feature": "Accounting Basis toggle (Accrual default | Cash) — report layer only", "phase": "3.6"},

    # --- People / Tenants ---
    {"id": "people.tenants.adjust_move_out_disposition", "area": "People / Tenants",
     "feature": "Adjust Move Out Disposition (new charges/credits post-move-out)", "phase": "3.5"},

    # --- People / Vendors ---
    {"id": "people.vendors.list_view", "area": "People / Vendors",
     "feature": "Vendor list view with filters (trade, 1099, insurance expiring)", "phase": "4"},

    # --- Reporting ---
    {"id": "reporting.framework", "area": "Reporting",
     "feature": "Report framework (standard vs enhanced, tabs vs buttons)", "phase": "3.7"},
    {"id": "reporting.print_email_export", "area": "Reporting",
     "feature": "Print / Email / CSV Export on every report", "phase": "3.7"},
    {"id": "reporting.labels_reports", "area": "Reporting",
     "feature": "Create a Labels Report (mail merge via CSV export)", "phase": "3.7"},
    {"id": "reporting.1099", "area": "Reporting",
     "feature": "Generate 1099 Forms & Reports (FIRE file + Print)", "phase": "3.7"},

    # --- Maintenance / Work Orders ---
    {"id": "maintenance.work_orders.delete_rules", "area": "Maintenance / Work Orders",
     "feature": "Delete WO only if no bill created", "phase": "5"},
    {"id": "maintenance.work_orders.edit_does_not_cascade", "area": "Maintenance / Work Orders",
     "feature": "Editing WO does not modify its bill", "phase": "5"},
    {"id": "maintenance.work_orders.list_view", "area": "Maintenance / Work Orders",
     "feature": "Work Order list view with tabs (Open/Completed/All) + filters", "phase": "5"},
    {"id": "maintenance.work_orders.status_auto_dates", "area": "Maintenance / Work Orders",
     "feature": "Status change auto-updates step timestamps", "phase": "5"},
    {"id": "maintenance.work_orders.email_vendor", "area": "Maintenance / Work Orders",
     "feature": "Email work order to vendor (PDF)", "phase": "5"},
    {"id": "maintenance.work_orders.print", "area": "Maintenance / Work Orders",
     "feature": "Print work order", "phase": "5"},
    {"id": "maintenance.work_orders.tenant_intake", "area": "Maintenance / Work Orders",
     "feature": "Tenant intake (smart form, duplicate detection, urgency reconfirm)", "phase": "5"},
    {"id": "maintenance.work_orders.timeline", "area": "Maintenance / Work Orders",
     "feature": "Work order timeline / updates table UI", "phase": "5"},
    {"id": "maintenance.work_orders.vendor_visibility", "area": "Maintenance / Work Orders",
     "feature": "Vendor-safe field visibility in vendor portal", "phase": "5"},
    {"id": "maintenance.work_orders.vendor_picker", "area": "Maintenance / Work Orders",
     "feature": "Vendor picker with inline create on WO form", "phase": "4"},

    # --- Communication ---
    {"id": "communication.notifications_log", "area": "Communication",
     "feature": "Notification log (all channels: email, SMS, voice, in-app)", "phase": "6"},
    {"id": "communication.inbox_ui", "area": "Communication",
     "feature": "Inbox UI (thread list, filters, compose, attachments)", "phase": "6"},

    # --- Portals ---
    {"id": "portals.access_management", "area": "Portals",
     "feature": "Portal access management (grant/revoke, tokens, access log)", "phase": "7"},
    {"id": "portals.auth_methods", "area": "Portals",
     "feature": "Portal auth methods (email link | password | SMS code)", "phase": "7"},
    {"id": "portals.public_vacancies", "area": "Portals",
     "feature": "Public Vacancies page (filter, sort, status colors)", "phase": "7"},
    {"id": "portals.vacancy_list_export", "area": "Portals",
     "feature": "Vacancy List print/email", "phase": "7"},

    # --- Integrations ---
    {"id": "integrations.twilio_voice", "area": "Integrations",
     "feature": "Twilio Voice (autocall, IVR accept/reject, recording)", "phase": "8"},
    {"id": "integrations.email_providers", "area": "Integrations",
     "feature": "Enhanced email providers (SendGrid / SES / Postmark)", "phase": "8"},
    {"id": "integrations.webhooks", "area": "Integrations",
     "feature": "Webhook framework (inbound provider endpoints + outbound org webhooks)", "phase": "8"},

    # --- Internal Team ---
    {"id": "internal.admin_portal", "area": "Internal Team",
     "feature": "Internal admin portal shell (admin.yourcompany.com)", "phase": "9"},
    {"id": "internal.platform_audit", "area": "Internal Team",
     "feature": "Platform-side audit view (staff actions)", "phase": "9"},
    {"id": "internal.ticket_email_bridge", "area": "Internal Team",
     "feature": "Support ticket email bridge (reply-by-email into ticket thread)", "phase": "9"},
    {"id": "internal.ticket_sla", "area": "Internal Team",
     "feature": "Support ticket SLA tracking", "phase": "9"},

    # --- Billing ---
    {"id": "billing.pricing_tiers", "area": "Billing",
     "feature": "Pricing tiers by property count (1, 2-10, 11-50, ...)", "phase": "10"},
    {"id": "billing.add_ons", "area": "Billing",
     "feature": "Add-ons (extra storage, SMS credits, etc.)", "phase": "10"},
    {"id": "billing.discounts", "area": "Billing",
     "feature": "Discount codes (percent / flat, applies-to, valid window)", "phase": "10"},
    {"id": "billing.quotes", "area": "Billing",
     "feature": "Quotes (create, send, accept → subscription)", "phase": "10"},
    {"id": "billing.subscription_items", "area": "Billing",
     "feature": "Subscription line items (modules, addons, seats)", "phase": "10"},
    {"id": "billing.invoices", "area": "Billing",
     "feature": "Subscription invoices (generated, emailed, Stripe paid)", "phase": "10"},
    {"id": "billing.subscription_events", "area": "Billing",
     "feature": "Subscription events log (created, upgraded, downgraded, cancelled, ...)", "phase": "10"},
    {"id": "billing.usage_records", "area": "Billing",
     "feature": "Metered usage records (property count, SMS, storage, API)", "phase": "10"},
    {"id": "billing.payment_methods", "area": "Billing",
     "feature": "Customer payment methods on file (card / ACH)", "phase": "10"},
    {"id": "billing.settings", "area": "Billing",
     "feature": "Billing settings (email, address, tax id, auto-pay, currency)", "phase": "10"},
    {"id": "billing.signup_flow", "area": "Billing",
     "feature": "Signup / onboarding flow (plan + Stripe + org creation)", "phase": "10"},
    {"id": "billing.management_ui", "area": "Billing",
     "feature": "Subscription management UI (change, upgrade, cancel, invoices)", "phase": "10"},
    {"id": "billing.enforcement_layers", "area": "Billing",
     "feature": "Subscription enforcement layers (soft PAST_DUE / hard RESTRICTED / kill SUSPENDED)", "phase": "10"},

    # --- Production ---
    {"id": "production.aws_infra", "area": "Production",
     "feature": "AWS infrastructure (Lightsail + RDS, later ECS Fargate + ALB)", "phase": "11"},
    {"id": "production.postgres_migration", "area": "Production",
     "feature": "SQLite → PostgreSQL migration (test on staging, cutover)", "phase": "11"},
    {"id": "production.s3_uploads", "area": "Production",
     "feature": "S3 for uploads + signed URLs + CloudFront CDN", "phase": "11"},
    {"id": "production.secrets", "area": "Production",
     "feature": "Secrets management (AWS Secrets Manager / Parameter Store)", "phase": "11"},
    {"id": "production.cicd", "area": "Production",
     "feature": "CI/CD (GitHub Actions: lint, test, build, deploy)", "phase": "11"},
    {"id": "production.backups", "area": "Production",
     "feature": "Backups + disaster recovery (RDS daily + S3 versioning + DR drills)", "phase": "11"},
    {"id": "production.observability", "area": "Production",
     "feature": "Observability (logs, metrics, traces, alerts, status page)", "phase": "11"},
    {"id": "production.security", "area": "Production",
     "feature": "Security hardening (WAF, rate limiting, CSP, pen test)", "phase": "11"},
    {"id": "production.email_deliverability", "area": "Production",
     "feature": "Production email (DKIM/SPF/DMARC, warm-up, bounce handling)", "phase": "11"},

    # --- Mobile ---
    {"id": "mobile.tenant", "area": "Native Mobile",
     "feature": "Mobile: Tenant (balance, pay, requests, push, docs)", "phase": "12"},
    {"id": "mobile.crew", "area": "Native Mobile",
     "feature": "Mobile: Crew (jobs, hours, photos, ETA)", "phase": "12"},
    {"id": "mobile.manager", "area": "Native Mobile",
     "feature": "Mobile: Manager (approvals, triage, notifications)", "phase": "12"},
    {"id": "mobile.owner", "area": "Native Mobile",
     "feature": "Mobile: Owner (statements, approvals)", "phase": "12"},
    {"id": "mobile.push_notifications", "area": "Native Mobile",
     "feature": "Mobile push notifications (Firebase)", "phase": "12"},
    {"id": "mobile.app_store", "area": "Native Mobile",
     "feature": "App store submission (Apple + Google)", "phase": "12"},

    # --- Compliance reports ---
    {"id": "compliance.hoa.reports", "area": "Compliance",
     "feature": "HOA reports (Dues Aging, Violations Log, Reserve Fund, Budget vs Actual)", "phase": "4.5"},
    {"id": "compliance.affordable.reports", "area": "Compliance",
     "feature": "Affordable reports (Income Cert Status, Recert Due, AMI, HUD Rent Roll)", "phase": "4.5"},
    {"id": "compliance.commercial.reports", "area": "Compliance",
     "feature": "Commercial reports (Lease Abstract, Rent Roll, CAM Recon, % Rent, Options)", "phase": "4.5"},
    {"id": "compliance.rubs.reports", "area": "Compliance",
     "feature": "RUBs reports (allocation detail per bill period)", "phase": "4.5"},

    # --- Property tabs ---
    {"id": "properties.tabs.compliance", "area": "Properties / Tabs",
     "feature": "Compliance tab (program enrollment, recerts, insurance, violations)", "phase": "4.5"},

    # --- Universal ---
    {"id": "universal.hide_semantics", "area": "Universal Patterns",
     "feature": "Hide semantics (excluded from reports/history/search; Show Hidden checkbox)", "phase": "3.5"},
    {"id": "universal.powerful_search", "area": "Universal Patterns",
     "feature": "Powerful universal search (active search, hidden toggle, refine-as-type)", "phase": "3.5"},
    {"id": "universal.repeat_form", "area": "Universal Patterns",
     "feature": "Repeat Form / Field (CTRL+K / CTRL+J) across bill/charge/receipt forms", "phase": "3.5"},
]

# ------------------------------------------------------------------
# Add items that don't already exist
# ------------------------------------------------------------------
added = 0
skipped = 0
for item in NEW_ITEMS:
    if item["id"] in existing_ids:
        skipped += 1
        continue
    record = {
        "id": item["id"],
        "area": item["area"],
        "feature": item["feature"],
        "status": "scheduled",
        "phase": item["phase"],
    }
    data["items"].append(record)
    existing_ids.add(item["id"])
    added += 1

# ------------------------------------------------------------------
# Update _meta
# ------------------------------------------------------------------
data.setdefault("_meta", {})
data["_meta"]["last_updated"] = date.today().isoformat()
data["_meta"]["migration_head"] = "00bc0d143eac"
data["_meta"]["roadmap_section"] = "PROJECT_MASTER.md Section 66"

# ------------------------------------------------------------------
# Write
# ------------------------------------------------------------------
JSON_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

print(f"Added: {added} new items")
print(f"Skipped (already present): {skipped}")
print(f"Total items now: {len(data['items'])}")
print(f"Wrote {JSON_PATH}")