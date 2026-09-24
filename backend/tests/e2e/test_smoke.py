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
                ("/dashboard/team", "Team"),
            ]:
                page.goto(f"{BASE_URL}{path}", wait_until="domcontentloaded")
                expect(page.get_by_role("heading", name=heading, exact=True)).to_be_visible()
                expect(page).not_to_have_url(re.compile(r"/login"))

            page.goto(
                f"{BASE_URL}/dashboard/settings/sidebar",
                wait_until="domcontentloaded",
            )
            page.wait_for_url(
                re.compile(r"/dashboard/settings/permissions/?$"),
                timeout=15_000,
            )
            expect(
                page.get_by_role("heading", name="Permissions", exact=True)
            ).to_be_visible()


            page.goto(
                f"{BASE_URL}/dashboard/properties/{PROPERTY_ID}",
                wait_until="domcontentloaded",
            )
            expect(
                page.get_by_role("heading", name="E2E Test Property", exact=True)
            ).to_be_visible()
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
