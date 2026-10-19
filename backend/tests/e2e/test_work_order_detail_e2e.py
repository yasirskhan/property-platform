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
            page.goto(BASE_URL + "/dashboard/maintenance/work-orders/new", wait_until="domcontentloaded")
            pw.expect(page.get_by_role("heading", name="New maintenance request")).to_be_visible()
            pw.expect(page.get_by_role("option", name="E2E Test Property · Unit E2E-1")).to_be_attached(timeout=15_000)

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
            page.goto(BASE_URL + "/dashboard/maintenance/work-orders/new", wait_until="domcontentloaded")
            pw.expect(page.get_by_role("heading", name="New maintenance request")).to_be_visible()
            page.get_by_label("Maintenance request unit").select_option("900001")
            page.get_by_label("Maintenance problem title").fill("E2E maintenance activity")
            page.get_by_role("button", name="Check similar requests").click()
            pw.expect(page.get_by_role("link", name=re.compile(
                str(work_order_id) + r".*E2E maintenance activity"
            ))).to_be_visible(timeout=15_000)

            # The crew selector must call the enum-valid uppercase CREW filter,
            # not the lowercase value rejected by backend validation (HTTP 422).
            with page.expect_response(
                lambda response: "/users?role=CREW" in response.url,
                timeout=15_000,
            ) as crew_response:
                page.goto(BASE_URL + "/dashboard/maintenance/work-orders/" + str(work_order_id),
                          wait_until="domcontentloaded")
            assert crew_response.value.status == 200, crew_response.value.text()
            pw.expect(
                page.get_by_role("heading", name="Work order #" + str(work_order_id) + ": E2E maintenance activity")
            ).to_be_visible(timeout=15_000)
            pw.expect(page.get_by_role("heading", name="Recorded activity")).to_be_visible()
            pw.expect(page.get_by_role("button", name="Acknowledge", exact=True)).to_be_visible()
            page.get_by_role("button", name="Acknowledge", exact=True).click()
            pw.expect(page.get_by_text("Work order acknowledged.", exact=True)).to_be_visible(timeout=15_000)
            pw.expect(page.get_by_role("button", name="Assign crew", exact=True)).to_be_visible()
            page.get_by_label("Work order activity note").fill("E2E follow-up activity note")
            page.get_by_role("button", name="Save activity note").click()
            pw.expect(
                page.get_by_text("Comment recorded in the work order activity history.")
            ).to_be_visible(timeout=15_000)
            pw.expect(page.get_by_text("E2E follow-up activity note")).to_be_visible()
            assert page.get_by_role("button", name="Save activity note").count() == 1
        finally:
            browser.close()


def test_customer_maintenance_request_form_saves_a_new_order() -> None:
    with pw.sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page()
        try:
            page.goto(BASE_URL + "/login", wait_until="domcontentloaded")
            page.locator('input[type="email"]').fill(EMAIL)
            page.locator('input[type="password"]').fill(PASSWORD)
            page.get_by_role("button", name="Log In", exact=True).click()
            page.wait_for_url(re.compile(r"/dashboard/?$"), timeout=15_000)
            # Wait until the authenticated dashboard shell has finished its
            # async /auth/me and billing checks before a second navigation.
            # A location change while the shell is still initializing can be
            # redirected back to /login by the outstanding auth effect.
            pw.expect(page.get_by_text("Signed in as", exact=True)).to_be_visible(
                timeout=15_000
            )
            assert page.evaluate("() => !!localStorage.getItem('token')")
            page.goto(BASE_URL + "/dashboard/maintenance/work-orders", wait_until="domcontentloaded")
            pw.expect(page.get_by_role("link", name="New maintenance request")).to_be_visible(timeout=15_000)
            page.goto(BASE_URL + "/dashboard/maintenance/work-orders/new", wait_until="domcontentloaded")
            pw.expect(page.get_by_role("heading", name="New maintenance request")).to_be_visible()
            page.get_by_label("Maintenance request unit").select_option("900001")
            page.get_by_label("Maintenance problem title").fill("E2E request form check")
            page.get_by_label("Maintenance problem description").fill(
                "A disposable work order submitted from the actual intake form."
            )
            page.get_by_label("Maintenance urgency").select_option("emergency")
            pw.expect(page.get_by_text("This form does not dispatch emergency services")).to_be_visible()
            page.get_by_role("button", name="Submit maintenance request").click()
            page.wait_for_url(re.compile(r"/maintenance/work-orders/[0-9]+$"), timeout=15_000)
            pw.expect(
                page.get_by_role("heading", name=re.compile("E2E request form check"))
            ).to_be_visible(timeout=15_000)
        finally:
            browser.close()
