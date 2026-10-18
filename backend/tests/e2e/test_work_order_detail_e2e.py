"""Authenticated customer work-order detail and activity regression."""
from __future__ import annotations

import os
import re

import pytest

pw = pytest.importorskip("playwright.sync_api")
pytestmark = pytest.mark.e2e
BASE_URL = os.environ.get("E2E_BASE_URL", "http://127.0.0.1:3000")
API_URL = os.environ.get("E2E_API_BASE_URL", "http://127.0.0.1:8000")
EMAIL = os.environ.get("E2E_ADMIN_EMAIL", "e2e-admin@example.com")
PASSWORD = os.environ.get("E2E_ADMIN_PASSWORD", "test1234")


def test_authenticated_work_order_detail_and_comment_history() -> None:
    with pw.sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page()
        try:
            page.goto(BASE_URL + "/login", wait_until="domcontentloaded")
            page.locator('input[type="email"]').fill(EMAIL)
            page.locator('input[type="password"]').fill(PASSWORD)
            page.get_by_role("button", name="Log In", exact=True).click()
            page.wait_for_url(re.compile(r"/dashboard/?$"), timeout=15_000)
            token = page.evaluate("() => localStorage.getItem('token')")
            assert isinstance(token, str) and token

            create = page.request.post(
                API_URL + "/work-orders",
                headers={"Authorization": "Bearer " + token},
                data={
                    "unit_id": 900001,
                    "title": "E2E maintenance activity",
                    "description": "A test issue requiring a follow-up note.",
                    "permission_to_enter": False,
                },
            )
            assert create.status == 201, create.text()
            work_order_id = create.json()["id"]

            page.goto(BASE_URL + "/dashboard/maintenance/work-orders/" + str(work_order_id),
                      wait_until="domcontentloaded")
            pw.expect(
                page.get_by_role("heading", name="Work order #" + str(work_order_id) + ": E2E maintenance activity")
            ).to_be_visible(timeout=15_000)
            pw.expect(page.get_by_role("heading", name="Recorded activity")).to_be_visible()
            pw.expect(page.get_by_role("button", name="Acknowledge", exact=True)).to_be_visible()
            page.get_by_role("button", name="Acknowledge", exact=True).click()
            pw.expect(page.get_by_text("Work order acknowledged.", exact=True)).to_be_visible(timeout=15_000)
            page.get_by_label("Work order activity note").fill("E2E follow-up activity note")
            page.get_by_role("button", name="Save activity note").click()
            pw.expect(
                page.get_by_text("Comment recorded in the work order activity history.")
            ).to_be_visible(timeout=15_000)
            pw.expect(page.get_by_text("E2E follow-up activity note")).to_be_visible()
            assert page.get_by_role("button", name="Save activity note").count() == 1
        finally:
            browser.close()
