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


def test_login_and_core_authenticated_pages() -> None:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page()
        try:
            page.goto(f"{BASE_URL}/login", wait_until="networkidle")
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
            ]:
                page.goto(f"{BASE_URL}{path}", wait_until="networkidle")
                expect(page.get_by_role("heading", name=heading, exact=True)).to_be_visible()
                expect(page).not_to_have_url(re.compile(r"/login"))
        finally:
            browser.close()