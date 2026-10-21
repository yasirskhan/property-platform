"""Authenticated seven-day/month on-call coverage calendar acceptance."""
import calendar
import os
import re

import pytest

pw = pytest.importorskip("playwright.sync_api")
pytestmark = pytest.mark.e2e
BASE_URL = os.environ.get("E2E_BASE_URL", "http://127.0.0.1:3000")
EMAIL = os.environ.get("E2E_ADMIN_EMAIL", "e2e-admin@example.com")
PASSWORD = os.environ.get("E2E_ADMIN_PASSWORD", "test1234")


def _month_days(iso: str) -> int:
    year, month, _ = map(int, iso.split("-"))
    return calendar.monthrange(year, month)[1]


def test_on_call_month_switch_navigates_actual_calendar_months():
    with pw.sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page()
        try:
            page.goto(BASE_URL + "/login", wait_until="domcontentloaded")
            page.locator('input[type="email"]').fill(EMAIL)
            page.locator('input[type="password"]').fill(PASSWORD)
            page.get_by_role("button", name="Log In", exact=True).click()
            page.wait_for_url(re.compile(r"/dashboard/?$"), timeout=15_000)
            pw.expect(page.get_by_text("Signed in as", exact=True)).to_be_visible(timeout=15_000)
            page.goto(BASE_URL + "/dashboard/maintenance/on-call", wait_until="domcontentloaded")
            pw.expect(page.get_by_role("heading", name="Maintenance on-call calendar")).to_be_visible(timeout=15_000)
            weekly = page.locator("section[aria-label='Seven-day on-call coverage'] article")
            pw.expect(weekly).to_have_count(7, timeout=15_000)

            page.get_by_label("On-call calendar view").select_option("month")
            first_month = page.get_by_label("On-call calendar start").input_value()
            assert first_month.endswith("-01")
            month_cards = page.locator("section[aria-label='Monthly on-call coverage'] article")
            pw.expect(month_cards).to_have_count(_month_days(first_month), timeout=15_000)
            pw.expect(page.get_by_role("button", name="Next month")).to_be_visible()
            pw.expect(page.get_by_role("button", name="Previous month")).to_be_visible()
            page.get_by_role("button", name="Next month").click()
            second_month = page.get_by_label("On-call calendar start").input_value()
            assert second_month != first_month and second_month.endswith("-01")
            pw.expect(month_cards).to_have_count(_month_days(second_month), timeout=15_000)
            page.get_by_role("button", name="Previous month").click()
            assert page.get_by_label("On-call calendar start").input_value() == first_month
            pw.expect(month_cards).to_have_count(_month_days(first_month), timeout=15_000)
            page.get_by_label("On-call calendar view").select_option("week")
            pw.expect(weekly).to_have_count(7, timeout=15_000)
            pw.expect(page.get_by_role("button", name="Next week")).to_be_visible()
        finally:
            browser.close()
