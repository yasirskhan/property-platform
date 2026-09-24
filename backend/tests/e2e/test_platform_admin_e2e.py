"""Browser proof for the separate internal platform administration application."""
from __future__ import annotations

import os
import re

import pytest

playwright_sync = pytest.importorskip("playwright.sync_api")
expect = playwright_sync.expect
sync_playwright = playwright_sync.sync_playwright

pytestmark = pytest.mark.e2e

PLATFORM_BASE_URL = os.environ.get(
    "E2E_PLATFORM_BASE_URL", "http://127.0.0.1:3001"
)
PLATFORM_EMAIL = os.environ.get(
    "E2E_PLATFORM_ADMIN_EMAIL", "e2e-platform-admin@example.com"
)
PLATFORM_PASSWORD = os.environ.get(
    "E2E_PLATFORM_ADMIN_PASSWORD", "platform-test1234"
)


def test_platform_admin_login_uses_separate_identity_and_session() -> None:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page()
        try:
            page.goto(
                f"{PLATFORM_BASE_URL}/login",
                wait_until="domcontentloaded",
            )
            expect(
                page.get_by_role("heading", name="Platform Admin", exact=True)
            ).to_be_visible()
            expect(
                page.get_by_text(
                    re.compile(r"Customer accounts cannot sign in here")
                )
            ).to_be_visible()

            page.locator('input[type="email"]').fill(PLATFORM_EMAIL)
            page.locator('input[type="password"]').fill(PLATFORM_PASSWORD)
            page.get_by_role("button", name="Sign in", exact=True).click()

            page.wait_for_url(
                re.compile(r"/dashboard/?$"),
                timeout=15_000,
            )
            expect(
                page.get_by_role("heading", name="Platform Admin", exact=True)
            ).to_be_visible()
            expect(
                page.get_by_role("button", name="Organizations", exact=True)
            ).to_be_visible()
            expect(
                page.get_by_role("button", name="Plans", exact=True)
            ).to_be_visible()
            expect(
                page.get_by_role("button", name="Release Gates", exact=True)
            ).to_be_visible()
            expect(
                page.get_by_role("button", name="Fraud Review", exact=True)
            ).to_be_visible()
            expect(
                page.get_by_role("button", name="Staff Audit", exact=True)
            ).to_be_visible()

            platform_token = page.evaluate(
                "() => localStorage.getItem('platform_access_token')"
            )
            customer_token = page.evaluate(
                "() => localStorage.getItem('token')"
            )
            assert isinstance(platform_token, str)
            assert platform_token
            assert customer_token is None
        finally:
            browser.close()
