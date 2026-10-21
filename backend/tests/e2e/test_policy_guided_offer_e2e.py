"""Authenticated policy-guided dispatch workflow, including safe no-coverage state."""
from uuid import uuid4
import os
import re
import pytest

pw = pytest.importorskip("playwright.sync_api")
pytestmark = pytest.mark.e2e

BASE_URL = os.environ.get("E2E_BASE_URL", "http://127.0.0.1:3000")
API_URL = os.environ.get("E2E_API_BASE_URL", "http://127.0.0.1:8000")
EMAIL = os.environ.get("E2E_ADMIN_EMAIL", "e2e-admin@example.com")
PASSWORD = os.environ.get("E2E_ADMIN_PASSWORD", "test1234")


def test_policy_guided_offer_is_visible_to_staff_only_with_real_coverage():
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
            auth = {"Authorization": "Bearer " + token}
            name = "E2E Rule Guided " + uuid4().hex[:12]
            created = page.request.post(
                API_URL + "/api/maintenance/dispatch-groups", headers=auth,
                data={"name": name, "property_ids": [900001],
                      "timezone_name": "America/New_York",
                      "business_start_hour": 9, "business_end_hour": 17},
            )
            assert created.status == 201, created.text()
            group_id = created.json()["id"]
            for daypart in ("business_hours", "after_hours"):
                rule = page.request.put(
                    API_URL + "/api/maintenance/dispatch-groups/"
                    + str(group_id) + "/rules/normal/" + daypart,
                    headers=auth,
                    data={"first_target": "crew", "backup_target": "manager",
                          "timeout_minutes": 9, "escalate": True},
                )
                assert rule.status == 200, rule.text()
            new_order = page.request.post(API_URL + "/work-orders", headers=auth, data={
                "unit_id": 900001, "title": "E2E crew policy dispatch " + uuid4().hex[:8],
                "description": "Record the effective crew policy before any explicit in-app dispatch.",
                "permission_to_enter": False,
            })
            assert new_order.status == 201, new_order.text()
            order_id = new_order.json()["id"]
            accepted = page.request.post(
                API_URL + "/work-orders/" + str(order_id) + "/acknowledge", headers=auth,
            )
            assert accepted.status == 200, accepted.text()
            readiness = page.request.get(
                API_URL + "/work-orders/" + str(order_id) + "/dispatch-readiness", headers=auth,
            )
            assert readiness.status == 200, readiness.text()
            policy = readiness.json()["effective_policy"]
            assert policy["group_name"] == name
            assert policy["configured"] is True
            assert policy["first_target"] == "crew"
            page.goto(
                BASE_URL + "/dashboard/maintenance/work-orders/" + str(order_id),
                wait_until="domcontentloaded",
            )
            panel = page.get_by_role("region", name="Current on-call dispatch readiness")
            pw.expect(panel.get_by_text("Effective group: " + name)).to_be_visible(timeout=15_000)
            if readiness.json()["can_offer"]:
                pw.expect(panel.get_by_role(
                    "button", name="Confirm policy-guided crew offer (in-app)",
                )).to_be_visible(timeout=15_000)
                panel.get_by_role("button", name="Confirm policy-guided crew offer (in-app)").click()
                pw.expect(page.get_by_text(re.compile(
                    "Configured crew policy applied and in-app offer recorded",
                ))).to_be_visible(timeout=15_000)
            else:
                pw.expect(panel.get_by_role(
                    "button", name="Confirm policy-guided crew offer (in-app)",
                )).to_have_count(0)
                attempted = page.request.post(
                    API_URL + "/api/maintenance/policy-offers/work-orders/" + str(order_id),
                    headers=auth,
                )
                assert attempted.status == 409, attempted.text()
        finally:
            browser.close()
