"""Canonical customer report catalog for Phase 3.7.

The catalog is intentionally metadata-only. Report implementations plug into
this registry as they ship, which keeps navigation, tiering, and authorization
consistent without duplicating a reporting shell on every report page.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


ReportTier = Literal["STANDARD", "ENHANCED"]
ReportPresentation = Literal["BUTTON", "TAB"]


@dataclass(frozen=True)
class ReportDefinition:
    key: str
    title: str
    category: str
    tier: ReportTier
    presentation: ReportPresentation
    available: bool = False
    href: str | None = None
    description: str | None = None


def _standard(key: str, title: str, category: str, *, href: str | None = None, description: str | None = None) -> ReportDefinition:
    return ReportDefinition(
        key=key,
        title=title,
        category=category,
        tier="STANDARD",
        presentation="BUTTON",
        available=href is not None,
        href=href,
        description=description,
    )


def _enhanced(key: str, title: str, category: str, *, href: str | None = None, description: str | None = None) -> ReportDefinition:
    return ReportDefinition(
        key=key,
        title=title,
        category=category,
        tier="ENHANCED",
        presentation="TAB",
        available=href is not None,
        href=href,
        description=description,
    )


REPORT_CATALOG: tuple[ReportDefinition, ...] = (
    _standard(
        "owner.packet", "Send Owner Packets", "Owner & Vendor",
        href="/dashboard/accounting/owner-statements/packets",
        description="Review frozen owner statement and cash-summary CSV packet before email.",
    ),
    _standard(
        "mailing.letters", "Letters", "Mailings",
        href="/dashboard/reporting/letters",
        description="Custom tenant letters and reviewed 3-day notice drafts.",
    ),
    _standard(
        "tax.1099_preparation", "1099 Preparation", "Tax",
        href="/dashboard/reporting/1099",
        description="Encrypted taxpayer profiles and paper W-9 readiness; filing not enabled.",
    ),
    _standard(
        "mailing.labels", "Create Labels Report", "Mailings",
        href="/dashboard/reporting/labels",
        description="Mail-merge CSV for authorized property and current-tenant addresses.",
    ),
    # Tenant
    _enhanced(
        "tenant.delinquency", "Delinquency", "Tenant",
        href="/dashboard/reporting/delinquency",
        description="Current overdue rent-invoice balances. Unpaid charges have a separate report.",
    ),
    _standard(
        "tenant.security_deposit_funds_detail", "Security Deposit Funds Detail", "Tenant",
        href="/dashboard/reporting/security-deposits",
        description="Posted deposit-liability GL entries; not bank-held cash or lease deposit contracts.",
    ),
    _standard(
        "tenant.directory", "Tenant Directory", "Tenant",
        href="/dashboard/reporting/tenants",
        description="Current tenant lease associations; administrators also see unassigned tenant users.",
    ),
    _enhanced(
        "tenant.ledger", "Tenant Ledger", "Tenant",
        href="/dashboard/reporting/tenant-ledger",
        description="Current invoice and standalone charge balances, not a reconstructed payment history.",
    ),
    _standard(
        "tenant.tickler", "Tenant Tickler", "Tenant",
        href="/dashboard/reporting/tickler",
        description="Tenant contacts with latest recorded lease event; no inferred notice/move-out dates.",
    ),
    _standard(
        "tenant.unpaid_charges", "Tenant Unpaid Charges", "Tenant",
        href="/dashboard/reporting/unpaid-charges",
        description="Current positive standalone Charge balances only; rent invoices are separate.",
    ),
    _standard(
        "tenant.summary", "Tenant Unpaid Charges Summary", "Tenant",
        href="/dashboard/reporting/unpaid-charges-summary",
        description="Per-tenant/property current unpaid standalone Charges; excludes rent invoices.",
    ),

    # Property and unit
    _enhanced(
        "property.budget_comparison", "Budget Comparison", "Property & Unit",
        href="/dashboard/reporting/budget-comparison",
        description="Explicit monthly budget lines compared with dated posted GL movements (accrual only).",
    ),
    _standard(
        "property.budget_detail", "Budget Detail", "Property & Unit",
        href="/dashboard/reporting/budget-detail",
        description="Explicit budget amounts by income/expense account and month; blanks are unconfigured.",
    ),
    _enhanced(
        "property.gross_potential_rent", "Gross Potential Rent", "Property & Unit",
        href="/dashboard/reporting/gross-potential-rent",
        description="Current market/lease rent projection with separate journal posting markers; not a historical snapshot.",
    ),
    _standard(
        "property.lease_expiration_detail", "Lease Expiration Detail", "Property & Unit",
        href="/dashboard/reporting/lease-expirations",
        description="Recorded active/expired lease contract end dates; not confirmed move-outs.",
    ),
    _standard(
        "property.lease_expiration_summary", "Lease Expiration Summary by Month", "Property & Unit",
        href="/dashboard/reporting/lease-expirations/summary",
        description="Count recorded lease contract end dates by property and month.",
    ),
    _standard(
        "property.directory", "Property Directory", "Property & Unit",
        href="/dashboard/reporting/property-directory",
        description="Recorded active property addresses and active unit counts, scoped to your assignments.",
    ),
    _standard(
        "property.group_directory", "Property Group Directory", "Property & Unit",
        href="/dashboard/reporting/property-groups",
        description="Explicitly saved group memberships; manager view includes assigned properties only.",
    ),
    _enhanced(
        "property.performance", "Property Performance", "Property & Unit",
        href="/dashboard/reporting/property-performance",
        description="Posted property-tagged accrual GL income, expenses and net; not cash or return on investment.",
    ),
    _enhanced(
        "property.rent_roll", "Rent Roll", "Property & Unit",
        href="/dashboard/reporting/rent-roll",
        description="Current recorded unit/lease rent; no collection or historical occupancy inferred.",
    ),
    _standard(
        "property.unit_directory", "Unit Directory", "Property & Unit",
        href="/dashboard/reporting/unit-directory",
        description="Recorded active unit configuration and editable availability/listing flags; not verified occupancy.",
    ),
    _standard(
        "property.unit_inspection", "Unit Inspection", "Property & Unit",
        href="/dashboard/reporting/unit-inspections",
        description="Explicit staff-recorded dated unit inspection entries; not Phase 5 mobile inspections.",
    ),
    _standard(
        "property.unit_vacancy_detail", "Unit Vacancy Detail", "Property & Unit",
        href="/dashboard/reporting/unit-vacancy-detail",
        description="Units without an eligible currently recorded lease; not verified physical vacancy.",
    ),

    # Owner and vendor
    _standard(
        "owner.directory", "Owner Directory", "Owner & Vendor",
        href="/dashboard/reporting/owner-directory",
        description="Current recorded owner contacts; no inferred mailing or tax profile data.",
    ),
    _enhanced(
        "owner.statement",
        "Owner Statement",
        "Owner & Vendor",
        href="/dashboard/accounting/owner-statements",
        description="Uses the verified frozen owner-statement workflow.",
    ),
    _standard(
        "vendor.directory", "Vendor Directory", "Owner & Vendor",
        href="/dashboard/reporting/vendor-directory",
        description="Recorded vendor user contacts only; no unlinked bill payees or private taxpayer data.",
    ),
    _enhanced(
        "vendor.ledger", "Vendor Ledger", "Owner & Vendor",
        href="/dashboard/reporting/vendor-ledger",
        description="Recorded linked vendor bills and AP status, not unlinked payees or a tax register.",
    ),
    _standard(
        "maintenance.work_order", "Work Order", "Owner & Vendor",
        href="/dashboard/reporting/work-orders",
        description="Recorded maintenance work order summary; no private access notes or inferred costs.",
    ),

    # Accounting
    _standard(
        "accounting.account_totals", "Account Totals", "Accounting",
        href="/dashboard/reporting/account-totals",
        description="Posted GL debit, credit and signed net by account (accrual basis only).",
    ),
    _enhanced(
        "accounting.balance_sheet", "Balance Sheet", "Accounting",
        href="/dashboard/reporting/balance-sheet",
        description="Posted accrual GL assets, liabilities and equity including unclosed earnings; not audited.",
    ),
    _standard(
        "accounting.bank_activity", "Bank Account Activity", "Accounting",
        href="/dashboard/reporting/bank-activity",
        description="Posted GL cash-book activity by linked bank account; not a bank statement or cleared balance.",
    ),
    _standard("accounting.bank_association", "Bank Account Association", "Accounting"),
    _enhanced("accounting.cash_flow", "Cash Flow", "Accounting"),
    _enhanced("accounting.cash_flow_12_month", "Cash Flow 12-Month", "Accounting"),
    _standard(
        "accounting.chart_of_accounts",
        "Chart of Accounts",
        "Accounting",
        href="/dashboard/accounting/gl-accounts",
        description="Opens the verified Chart of Accounts.",
    ),
    _standard("accounting.expense_distribution", "Expense Distribution", "Accounting"),
    _enhanced(
        "accounting.general_ledger",
        "General Ledger",
        "Accounting",
        href="/dashboard/accounting/gl-accounts",
        description="Choose an account to open its verified ledger.",
    ),
    _enhanced("accounting.income_statement", "Income Statement", "Accounting"),
    _enhanced(
        "accounting.trial_balance",
        "Trial Balance",
        "Accounting",
        href="/dashboard/accounting/trial-balance",
        description="Existing verified trial-balance report.",
    ),
    _enhanced("accounting.trust_account_balance", "Trust Account Balance", "Accounting"),
    _enhanced("accounting.trust_account_detail", "Trust Account Detail", "Accounting"),

    # Transactions
    _standard("transaction.aged_payables", "Aged Payables", "Transaction"),
    _standard("transaction.aged_receivables", "Aged Receivables", "Transaction"),
    _standard("transaction.bill_detail", "Bill Detail", "Transaction"),
    _standard("transaction.charge_detail", "Charge Detail", "Transaction"),
    _standard("transaction.check_register", "Check Register", "Transaction"),
    _standard("transaction.check_register_detail", "Check Register Detail", "Transaction"),
    _standard("transaction.deposit_register", "Deposit Register", "Transaction"),
    _standard("transaction.expense_register", "Expense Register", "Transaction"),
    _standard("transaction.income_register", "Income Register", "Transaction"),
    _standard("transaction.journal_entry_register", "Journal Entry Register", "Transaction"),
)


def report_catalog() -> tuple[list[ReportDefinition], list[ReportDefinition]]:
    standard = [item for item in REPORT_CATALOG if item.tier == "STANDARD"]
    enhanced = [item for item in REPORT_CATALOG if item.tier == "ENHANCED"]
    return standard, enhanced
