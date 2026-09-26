"""Real browser smoke coverage for the core authenticated shell."""
from __future__ import annotations

import os
import re

import pytest

playwright_sync = pytest.importorskip("playwright.sync_api")
expect = playwright_sync.expect
sync_playwright = playwright_sync.sync_playwright

pytestmark = pytest.mark.e2e

BASE_URL = os.environ.get("E2E_BASE_URL", "http://127.0.0.1:3000")
EMAIL = os.environ.get("E2E_ADMIN_EMAIL", "e2e-admin@example.com")
PASSWORD = os.environ.get("E2E_ADMIN_PASSWORD", "test1234")
PROPERTY_ID = 900001
UNIT_ID = 900001


def test_signup_page_uses_hosted_payment_flow_without_card_fields() -> None:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page()
        try:
            page.goto(f"{BASE_URL}/signup", wait_until="domcontentloaded")
            expect(
                page.get_by_role("heading", name="Create your account", exact=True)
            ).to_be_visible()
            expect(page.get_by_label("Company name", exact=True)).to_be_visible()
            expect(page.get_by_label("Email", exact=True)).to_be_visible()
            expect(page.get_by_label("Password", exact=True)).to_be_visible()
            expect(page.locator('input[autocomplete="cc-number"]')).to_have_count(0)
            expect(page.locator('input[name="card_number"]')).to_have_count(0)
            expect(page.locator('input[name="cvc"]')).to_have_count(0)
            expect(
                page.get_by_text(
                    re.compile(r"Payment details are entered only on Stripe Checkout")
                )
            ).to_be_visible()
        finally:
            browser.close()


def test_login_and_core_authenticated_pages() -> None:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page()
        try:
            page.goto(f"{BASE_URL}/login", wait_until="domcontentloaded")
            expect(page.get_by_role("heading", name="Welcome back")).to_be_visible()

            page.locator('input[type="email"]').fill(EMAIL)
            page.locator('input[type="password"]').fill(PASSWORD)
            page.get_by_role("button", name="Log In").click()
            page.wait_for_url(re.compile(r"/dashboard/?$"), timeout=15_000)
            expect(page.get_by_role("heading", name=re.compile(r"Welcome, E2E"))).to_be_visible()

            for path, heading in [
                ("/dashboard/properties", "Properties"),
                ("/dashboard/accounting/receipts", "Receipts"),
                ("/dashboard/accounting/bills", "Bills"),
                ("/dashboard/accounting/deposits", "Bank Deposits"),
                ("/dashboard/accounting/gl-accounts", "Chart of Accounts"),
                ("/dashboard/accounting/journal-entries", "Journal Entries"),
                ("/dashboard/accounting/management-fees", "Management Fees"),
                ("/dashboard/accounting/owner-statements", "Owner Statements"),
                ("/dashboard/accounting/bank-accounts", "Bank Accounts"),
                ("/dashboard/accounting/charges", "Charges"),
                ("/dashboard/settings/display", "Display"),
                ("/dashboard/settings/currencies", "Currencies"),
                ("/dashboard/settings/permissions", "Permissions"),
                ("/dashboard/settings/features", "Features"),
                ("/dashboard/team", "Team"),
            ]:
                page.goto(f"{BASE_URL}{path}", wait_until="domcontentloaded")
                expect(page.get_by_role("heading", name=heading, exact=True)).to_be_visible()
                expect(page).not_to_have_url(re.compile(r"/login"))

            page.goto(
                f"{BASE_URL}/dashboard/accounting/receipts",
                wait_until="domcontentloaded",
            )
            expect(page.get_by_role("heading", name="Receipts", exact=True)).to_be_visible()
            expect(page.get_by_role("button", name="Export", exact=True)).to_have_count(0)
            expect(page.get_by_role("button", name="Print list", exact=True)).to_have_count(0)
            expect(page.get_by_role("button", name="Bulk actions", exact=True)).to_have_count(0)

            page.goto(
                f"{BASE_URL}/dashboard/accounting/bills",
                wait_until="domcontentloaded",
            )
            expect(page.get_by_role("heading", name="Bills", exact=True)).to_be_visible()
            expect(page.get_by_role("button", name="Recurring Bills", exact=True)).to_have_count(0)
            expect(page.get_by_role("button", name="Write Checks", exact=True)).to_have_count(0)
            expect(page.get_by_role("button", name="Enter Credit", exact=True)).to_have_count(0)

            page.goto(
                f"{BASE_URL}/dashboard/accounting/deposits",
                wait_until="domcontentloaded",
            )
            expect(
                page.get_by_role("heading", name="Bank Deposits", exact=True)
            ).to_be_visible()
            expect(page).not_to_have_url(re.compile(r"/login"))

            page.goto(
                f"{BASE_URL}/dashboard/accounting/gl-accounts",
                wait_until="domcontentloaded",
            )
            expect(
                page.get_by_role("heading", name="Chart of Accounts", exact=True)
            ).to_be_visible()
            expect(
                page.get_by_role("button", name="GL Account Permissions", exact=True)
            ).to_have_count(0)
            expect(
                page.get_by_role("button", name="Recalculate Balances", exact=True)
            ).to_have_count(0)

            page.goto(
                f"{BASE_URL}/dashboard/accounting/journal-entries",
                wait_until="domcontentloaded",
            )
            expect(
                page.get_by_role("heading", name="Journal Entries", exact=True)
            ).to_be_visible()
            expect(
                page.get_by_role("button", name="Recurring Journal Entries", exact=True)
            ).to_have_count(0)
            expect(
                page.get_by_role("button", name="Post GPR", exact=True)
            ).to_have_count(0)

            page.goto(
                f"{BASE_URL}/dashboard/accounting/management-fees",
                wait_until="domcontentloaded",
            )
            expect(
                page.get_by_role("heading", name="Management Fees", exact=True)
            ).to_be_visible()
            for hidden_action in [
                "Pay Owners",
                "Overcollection Strategy",
                "Management Fee Exclusions",
                "Post GPR",
            ]:
                expect(
                    page.get_by_role("button", name=hidden_action, exact=True)
                ).to_have_count(0)

            page.goto(
                f"{BASE_URL}/dashboard/accounting/owner-statements",
                wait_until="domcontentloaded",
            )
            expect(
                page.get_by_role("heading", name="Owner Statements", exact=True)
            ).to_be_visible()
            for hidden_action in [
                "Property Cash Summary",
                "Owner Packet",
                "Email Statement",
            ]:
                expect(
                    page.get_by_role("button", name=hidden_action, exact=True)
                ).to_have_count(0)

            page.goto(
                f"{BASE_URL}/dashboard/accounting/bank-accounts",
                wait_until="domcontentloaded",
            )
            expect(page.get_by_role("heading", name="Bank Accounts", exact=True)).to_be_visible()
            for hidden_action in [
                "Bank Reconciliation", "QIF Import", "Check Setup",
                "ACH File Generation", "$0 ACH Test File", "Check Printing",
                "Bank Feed", "Adjustments",
            ]:
                expect(page.get_by_role("button", name=hidden_action, exact=True)).to_have_count(0)

            page.goto(
                f"{BASE_URL}/dashboard/accounting/charges",
                wait_until="domcontentloaded",
            )
            expect(
                page.get_by_role("heading", name="Charges", exact=True)
            ).to_be_visible()
            expect(
                page.get_by_role(
                    "button", name="Bulk Tenant Charges Upload", exact=True
                )
            ).to_have_count(0)

            page.goto(
                f"{BASE_URL}/dashboard/settings/features",
                wait_until="domcontentloaded",
            )
            map_toggle = page.get_by_role(
                "checkbox",
                name="Map view",
                exact=True,
            )
            expect(map_toggle).to_be_checked()
            map_toggle.uncheck()
            expect(map_toggle).not_to_be_checked()
            page.reload(wait_until="domcontentloaded")
            expect(
                page.get_by_role("checkbox", name="Map view", exact=True)
            ).not_to_be_checked()

            page.goto(
                f"{BASE_URL}/dashboard/accounting/owner-statements/packets",
                wait_until="domcontentloaded",
            )
            expect(page.get_by_role("heading", name="Send Owner Packets", exact=True)).to_be_visible()
            expect(page.get_by_role("button", name="Send packet email", exact=True)).to_have_count(0)

            page.goto(
                f"{BASE_URL}/dashboard/reporting/delinquency",
                wait_until="domcontentloaded",
            )
            expect(page.get_by_role("heading", name="Tenant Delinquency", exact=True)).to_be_visible()

            page.goto(
                f"{BASE_URL}/dashboard/reporting/1099",
                wait_until="domcontentloaded",
            )
            expect(
                page.get_by_role("heading", name="1099 preparation", exact=True)
            ).to_be_visible()
            expect(page.get_by_text("Tax filing is not enabled", exact=True)).to_be_visible()
            expect(
                page.get_by_role("heading", name="Manual 1099 data review", exact=True)
            ).to_be_visible()
            for prohibited_filing_action in [
                "Submit to IRS",
                "File 1099",
                "Export IRIS",
                "Transmit return",
            ]:
                expect(
                    page.get_by_role("button", name=prohibited_filing_action, exact=True)
                ).to_have_count(0)

            page.goto(
                f"{BASE_URL}/dashboard/settings/sidebar",
                wait_until="domcontentloaded",
            )
            page.wait_for_url(
                re.compile(r"/dashboard/settings/permissions\?tab=preferences$"),
                timeout=15_000,
            )
            expect(
                page.get_by_role("heading", name="Permissions", exact=True)
            ).to_be_visible()
            expect(
                page.get_by_text(re.compile(r"Drag to reorder"))
            ).to_be_visible()


            page.goto(
                f"{BASE_URL}/dashboard/properties",
                wait_until="domcontentloaded",
            )
            expect(page.get_by_role("button", name="Property Groups", exact=True)).to_have_count(0)
            expect(page.get_by_role("button", name="Map View", exact=True)).to_have_count(0)

            page.goto(
                f"{BASE_URL}/dashboard/properties/{PROPERTY_ID}",
                wait_until="domcontentloaded",
            )
            expect(
                page.get_by_role("heading", name="E2E Test Property", exact=True)
            ).to_be_visible()
            for hidden_action in [
                "Photo Editor",
                "Keys",
                "Statement Settings",
                "Attachments",
                "Non-Revenue",
                "Staff",
                "Budget",
                "Fixed Assets",
                "RUBs",
                "Compliance",
            ]:
                expect(
                    page.get_by_role("button", name=hidden_action, exact=True)
                ).to_have_count(0)

            page.get_by_role("button", name="Units", exact=True).click()
            expect(page.get_by_role("link", name="E2E-1", exact=True)).to_be_visible()

            page.goto(
                f"{BASE_URL}/dashboard/properties/{PROPERTY_ID}/edit",
                wait_until="domcontentloaded",
            )
            expect(
                page.get_by_role("heading", name="Edit Property", exact=True)
            ).to_be_visible()

            page.goto(
                f"{BASE_URL}/dashboard/properties/{PROPERTY_ID}/units/{UNIT_ID}/edit",
                wait_until="domcontentloaded",
            )
            expect(
                page.get_by_role("heading", name="Edit Unit E2E-1", exact=True)
            ).to_be_visible()
        finally:
            browser.close()
