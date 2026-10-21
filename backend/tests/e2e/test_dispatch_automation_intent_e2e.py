"""Owner/Admin can request future dispatch automation without activating delivery."""
import os
import re
import pytest

pw = pytest.importorskip("playwright.sync_api")
pytestmark = pytest.mark.e2e
URL = os.environ.get("E2E_BASE_URL", "http://127.0.0.1:3000")
API = os.environ.get("E2E_API_BASE_URL", "http://127.0.0.1:8000")


def test_owner_dispatch_automation_intent_is_saved_and_reversible():
    with pw.sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page()
        try:
            page.goto(URL + "/login", wait_until="domcontentloaded")
            page.locator('input[type="email"]').fill(os.environ.get("E2E_ADMIN_EMAIL", "e2e-admin@example.com"))
            page.locator('input[type="password"]').fill(os.environ.get("E2E_ADMIN_PASSWORD", "test1234"))
            page.get_by_role("button", name="Log In", exact=True).click()
            page.wait_for_url(re.compile(r"/dashboard/?$"), timeout=15_000)
            token = page.evaluate("() => localStorage.getItem('token')")
            assert token
            page.goto(URL + "/dashboard/maintenance/dispatch-settings", wait_until="domcontentloaded")
            option = page.get_by_role("option", name=re.compile("DEFAULT"))
            pw.expect(option).to_be_attached(timeout=15_000)
            toggle = page.get_by_label("Request future automated dispatch")
            pw.expect(toggle).to_be_visible()
            toggle.check()
            page.get_by_role("button", name="Save group settings").click()
            pw.expect(page.get_by_text("Maintenance group settings and property membership saved.",
                                       exact=True)).to_be_visible(timeout=15_000)
            headers = {"Authorization": "Bearer " + token}
            result = page.request.get(API + "/api/maintenance/dispatch-groups", headers=headers)
            assert result.status == 200, result.text()
            assert next(item for item in result.json() if item["is_default"])["automation_requested"] is True
            toggle.uncheck()
            page.get_by_role("button", name="Save group settings").click()
            pw.expect(page.get_by_text("Maintenance group settings and property membership saved.",
                                       exact=True)).to_be_visible(timeout=15_000)
            result = page.request.get(API + "/api/maintenance/dispatch-groups", headers=headers)
            assert result.status == 200, result.text()
            assert next(item for item in result.json() if item["is_default"])["automation_requested"] is False
        finally:
            browser.close()
