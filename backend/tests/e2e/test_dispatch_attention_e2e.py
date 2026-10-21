"""Authenticated dispatch attention follows real work-order state, not invented delivery."""
from __future__ import annotations

import os
import re
from uuid import uuid4
import pytest

pw = pytest.importorskip("playwright.sync_api")
pytestmark = pytest.mark.e2e
BASE_URL = os.environ.get("E2E_BASE_URL", "http://127.0.0.1:3000")
API_URL = os.environ.get("E2E_API_BASE_URL", "http://127.0.0.1:8000")
EMAIL = os.environ.get("E2E_ADMIN_EMAIL", "e2e-admin@example.com")
PASSWORD = os.environ.get("E2E_ADMIN_PASSWORD", "test1234")


def test_dispatch_attention_shows_authorized_new_work_order_without_phantom_communication():
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
            assert token
            title = "E2E dispatch attention " + uuid4().hex[:12]
            created = page.request.post(API_URL + "/work-orders",
                headers={"Authorization": "Bearer " + token},
                data={"unit_id": 900001, "title": title,
                      "description": "Dispatch queue visibility and access verification",
                      "priority": "emergency", "permission_to_enter": False})
            assert created.status == 201, created.text()
            number = created.json()["id"]
            data = page.request.get(API_URL + "/api/maintenance/dispatch-attention?limit=100",
                headers={"Authorization": "Bearer " + token})
            assert data.status == 200, data.text()
            assert any(row["work_order_id"] == number for row in data.json())
            page.goto(BASE_URL + "/dashboard/maintenance/dispatch-attention",
                      wait_until="domcontentloaded")
            pw.expect(page.get_by_role("heading", name="Maintenance dispatch attention")).to_be_visible(timeout=15_000)
            entries = page.get_by_role("region", name="Dispatch attention items")
            pw.expect(entries.get_by_role("link", name=re.compile(str(number) + r".*" + title))).to_be_visible(timeout=15_000)
            pw.expect(entries.get_by_text("Work order needs staff acknowledgement.").first).to_be_visible()
            pw.expect(page.get_by_text(re.compile("A timeout does not recall an assignment"))).to_be_visible()

            # Manager-follow-up cases are durable and require a real human
            # reason and closure. Creating a case is not a sent notification.
            page.get_by_role("link", name="Manual reviews").click()
            pw.expect(page.get_by_role("heading", name="Manual dispatch reviews")).to_be_visible(timeout=15_000)
            page.get_by_label("Manual review work order").select_option(str(number))
            page.get_by_label("Manual dispatch review reason").fill(
                "Emergency case requires a manual crew coverage review")
            page.get_by_role("button", name="Record manual review (no notification)").click()
            pw.expect(page.get_by_text(
                "Manual review recorded. No crew, vendor, or manager was automatically contacted."
            )).to_be_visible(timeout=15_000)
            cases = page.get_by_role("region", name="Manual dispatch review history")
            review = cases.get_by_role("article").filter(has_text="Work order #" + str(number))
            pw.expect(review).to_be_visible(timeout=15_000)
            pw.expect(review.get_by_text("External delivery confirmed: No")).to_be_visible()
            review.get_by_label(re.compile(r"Manual review resolution case")).fill(
                "Manager reviewed current coverage and documented manual follow-up")
            review.get_by_role("button", name="Close case with recorded outcome").click()
            pw.expect(page.get_by_text(
                "Review closure and reason were recorded in immutable audit history."
            )).to_be_visible(timeout=15_000)
            case_list = page.request.get(
                API_URL + "/api/maintenance/dispatch-reviews?include_closed=true&limit=100",
                headers={"Authorization": "Bearer " + token},
            )
            assert case_list.status == 200, case_list.text()
            assert any(
                item["work_order_id"] == number and item["status"] == "closed"
                and item["externally_notified"] is False
                for item in case_list.json()
            )
        finally:
            browser.close()
