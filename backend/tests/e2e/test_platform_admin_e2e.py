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


def test_doorloop_admin_console_read_only_source_discovery() -> None:
    """Exercise the real signed-in DoorLoop staff page, not just its TypeScript build."""
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page()
        try:
            page.goto(f"{PLATFORM_BASE_URL}/login", wait_until="domcontentloaded")
            page.locator('input[type="email"]').fill(PLATFORM_EMAIL)
            page.locator('input[type="password"]').fill(PLATFORM_PASSWORD)
            page.get_by_role("button", name="Sign in", exact=True).click()
            page.wait_for_url(re.compile(r"/dashboard/?$"), timeout=15_000)

            page.get_by_role("button", name="DoorLoop Migration", exact=True).click()
            page.wait_for_url(re.compile(r"/migrations/doorloop/?$"), timeout=15_000)
            expect(
                page.get_by_role("heading", name="DoorLoop export review", exact=True)
            ).to_be_visible()
            expect(
                page.get_by_role("heading", name="Import capability and safety", exact=True)
            ).to_be_visible()
            expect(
                page.get_by_text(re.compile("source-discovery mode"))
            ).to_be_visible()
            # This message is sourced from the authenticated backend readiness
            # route. A successful page build without working API access fails.
            expect(
                page.get_by_text(re.compile("DoorLoop resource contracts"))
            ).to_be_visible(timeout=15_000)
            expect(
                page.get_by_role("button", name="Create DRAFT run", exact=True)
            ).to_be_visible()
            assert page.get_by_role("button", name=re.compile(r"stage import|commit import", re.I)).count() == 0

            # Disposable E2E source export. Find the organization by authorized
            # platform API access instead of assuming a database-generated ID.
            platform_token = page.evaluate(
                "() => localStorage.getItem('platform_access_token')"
            )
            assert isinstance(platform_token, str) and platform_token
            api_url = os.environ.get("E2E_API_BASE_URL", "http://127.0.0.1:8000")
            org_response = page.request.get(
                f"{api_url}/api/platform/admin/organizations",
                headers={"Authorization": f"Bearer {platform_token}"},
            )
            assert org_response.ok
            organizations = org_response.json()
            org = next(
                (item for item in organizations
                 if item.get("name") == "E2E Test Organization"
                 and item.get("is_active")),
                None,
            )
            assert org is not None, "Seeded active E2E organization was not listed"
            page.get_by_label("Organization ID").fill(str(org["id"]))
            page.get_by_label("Nonsecret source label").fill("e2e-doorloop-export")
            page.get_by_role("button", name="Create DRAFT run", exact=True).click()
            expect(
                page.get_by_text(re.compile("DRAFT run created and audited"))
            ).to_be_visible(timeout=15_000)

            # Verify the whole in-memory export workflow through the real API.
            # A duplicate source identity is reported only as a count.
            page.locator('input[type="file"]').set_input_files({
                "name": "doorloop-e2e.csv",
                "mimeType": "text/csv",
                "buffer": b"External ID,Label\nID-1,Alpha\nID-1,Beta\n",
            })
            page.get_by_role("button", name="Inspect source", exact=True).click()
            expect(
                page.get_by_text(re.compile("Export inspected without storing source rows"))
            ).to_be_visible(timeout=15_000)
            expect(
                page.get_by_text(re.compile(r"2 data rows"))
            ).to_be_visible()
            page.get_by_role("button", name="Add field", exact=True).click()
            page.get_by_label("Proposed field name").fill("external_id")
            page.get_by_label("Source column").select_option(label="External ID")
            page.get_by_label("Identity field for duplicate check (optional)").select_option("external_id")
            page.get_by_role("button", name="Preview quality (read only)").click()
            expect(page.get_by_text("Rows assessed: 2", exact=True)).to_be_visible(timeout=15_000)
            expect(page.get_by_text("Duplicate nonempty identities: 1", exact=True)).to_be_visible()
            expect(
                page.get_by_text(re.compile("No mapping authorization, data staging, customer mutation"))
            ).to_be_visible()
        finally:
            browser.close()
