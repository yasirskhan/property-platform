"""Authenticate and verify manually recorded inspection evidence."""
from __future__ import annotations
from datetime import date
import os
import re
import pytest

pw = pytest.importorskip("playwright.sync_api")
pytestmark = pytest.mark.e2e
BASE_URL = os.environ.get("E2E_BASE_URL", "http://127.0.0.1:3000")
EMAIL = os.environ.get("E2E_ADMIN_EMAIL", "e2e-admin@example.com")
PASSWORD = os.environ.get("E2E_ADMIN_PASSWORD", "test1234")


def test_staff_records_inspection_without_invented_mobile_workflow():
    with pw.sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page()
        try:
            page.goto(BASE_URL + "/login", wait_until="domcontentloaded")
            page.locator('input[type="email"]').fill(EMAIL)
            page.locator('input[type="password"]').fill(PASSWORD)
            page.get_by_role("button", name="Log In", exact=True).click()
            page.wait_for_url(re.compile(r"/dashboard/?$"), timeout=15_000)
            # Ensure the authenticated shell completed initialization before
            # navigating again. A URL transition alone can race auth checks.
            pw.expect(page.get_by_text("Signed in as", exact=True)).to_be_visible(timeout=15_000)
            assert page.evaluate("() => !!localStorage.getItem('token')")

            page.goto(BASE_URL + "/dashboard/maintenance/work-orders", wait_until="domcontentloaded")
            page.get_by_role("link", name="Staff inspection records").click()
            page.wait_for_url(re.compile(r"/maintenance/staff-inspection-records/?$"), timeout=15_000)
            pw.expect(page.get_by_role("heading", name="Inspection records")).to_be_visible()
            pw.expect(page.get_by_role("option", name="E2E Test Property · Unit E2E-1")).to_be_attached(timeout=15_000)
            # The initial first 100 choices are not the only selectable units.
            # Search uses the existing permission-scoped server-side picker.
            page.get_by_label("Search inspection units").fill("E2E-1")
            page.get_by_role("button", name="Find units").click()
            pw.expect(page.get_by_role("button", name="Find units")).to_be_enabled(timeout=15_000)
            pw.expect(page.get_by_role("option", name="E2E Test Property · Unit E2E-1")).to_be_attached()
            page.get_by_label("Inspection unit", exact=True).select_option("900001")
            page.get_by_label("Inspection date").fill(date.today().isoformat())
            page.get_by_label("Inspection condition").select_option("ATTENTION_NEEDED")
            page.get_by_label("Inspection findings").fill("Inspected window latch by staff")
            page.get_by_role("button", name="Save inspection record").click()
            pw.expect(page.get_by_role("status").filter(
                has_text="Inspection evidence recorded and audited."
            )).to_be_visible(timeout=15_000)
            pw.expect(page.get_by_text("Inspected window latch by staff")).to_be_visible()
        finally:
            browser.close()
