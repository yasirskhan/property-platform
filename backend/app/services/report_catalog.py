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
    _enhanced("tenant.delinquency", "Delinquency", "Tenant"),
    _standard("tenant.security_deposit_funds_detail", "Security Deposit Funds Detail", "Tenant"),
    _standard("tenant.directory", "Tenant Directory", "Tenant"),
    _enhanced("tenant.ledger", "Tenant Ledger", "Tenant"),
    _standard("tenant.tickler", "Tenant Tickler", "Tenant"),
    _standard("tenant.unpaid_charges", "Tenant Unpaid Charges", "Tenant"),
    _standard("tenant.summary", "Tenant Summary", "Tenant"),

    # Property and unit
    _enhanced("property.budget_comparison", "Budget Comparison", "Property & Unit"),
    _standard("property.budget_detail", "Budget Detail", "Property & Unit"),
    _enhanced("property.gross_potential_rent", "Gross Potential Rent", "Property & Unit"),
    _standard("property.lease_expiration_detail", "Lease Expiration Detail", "Property & Unit"),
    _standard("property.lease_expiration_summary", "Lease Expiration Summary by Month", "Property & Unit"),
    _standard("property.directory", "Property Directory", "Property & Unit"),
    _standard("property.group_directory", "Property Group Directory", "Property & Unit"),
    _enhanced("property.performance", "Property Performance", "Property & Unit"),
    _enhanced("property.rent_roll", "Rent Roll", "Property & Unit"),
    _standard("property.unit_directory", "Unit Directory", "Property & Unit"),
    _standard("property.unit_inspection", "Unit Inspection", "Property & Unit"),
    _standard("property.unit_vacancy_detail", "Unit Vacancy Detail", "Property & Unit"),

    # Owner and vendor
    _standard("owner.directory", "Owner Directory", "Owner & Vendor"),
    _enhanced(
        "owner.statement",
        "Owner Statement",
        "Owner & Vendor",
        href="/dashboard/accounting/owner-statements",
        description="Uses the verified frozen owner-statement workflow.",
    ),
    _standard("vendor.directory", "Vendor Directory", "Owner & Vendor"),
    _enhanced("vendor.ledger", "Vendor Ledger", "Owner & Vendor"),
    _standard("maintenance.work_order", "Work Order", "Owner & Vendor"),

    # Accounting
    _standard("accounting.account_totals", "Account Totals", "Accounting"),
    _enhanced("accounting.balance_sheet", "Balance Sheet", "Accounting"),
    _standard("accounting.bank_activity", "Bank Account Activity", "Accounting"),
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
