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

            # The selector must use the authorized property-specific roster,
            # not the organization-wide user list (which offers unassigned crew).
            with page.expect_response(
                lambda response: "/properties/900001/assignments" in response.url
                    and response.request.method == "GET",
                timeout=15_000,
            ) as roster_response:
                page.goto(BASE_URL + "/dashboard/maintenance/work-orders/" + str(work_order_id),
                          wait_until="domcontentloaded")
            assert roster_response.value.status == 200, roster_response.value.text()
            eligible = [row["user_id"] for row in roster_response.value.json()
                        if row["role"] == "CREW"]
            pw.expect(
                page.get_by_role("heading", name="Work order #" + str(work_order_id) + ": E2E maintenance activity")
            ).to_be_visible(timeout=15_000)
            pw.expect(page.get_by_role("heading", name="Recorded activity")).to_be_visible()
            pw.expect(page.get_by_text("E2E Test Property · Unit E2E-1", exact=True)).to_be_visible()
            # A committed state change must remain successful even when a
            # follow-up detail GET fails (same guarantee as comments).
            def block_detail_get(route):
                if route.request.method == "GET":
                    route.fulfill(status=503, body="Refresh temporarily unavailable")
                else:
                    route.continue_()
            page.route(re.compile(r"/work-orders/" + str(work_order_id) + r"$"), block_detail_get)
            pw.expect(page.get_by_role("button", name="Acknowledge", exact=True)).to_be_visible()
            page.get_by_role("button", name="Acknowledge", exact=True).click()
            pw.expect(page.get_by_text("Work order acknowledged.", exact=True)).to_be_visible(timeout=15_000)
            pw.expect(page.get_by_text("acknowledged", exact=True)).to_be_visible(timeout=15_000)
            pw.expect(page.get_by_role("button", name="Assign crew", exact=True)).to_be_visible()
            crew_options = page.get_by_label("Assigned crew member", exact=True).locator("option")
            pw.expect(crew_options).to_have_count(1 + len(eligible), timeout=15_000)
            assert {int(value) for value in crew_options.evaluate_all(
                "(nodes) => nodes.map(node => node.value).filter(Boolean)"
            )} == set(eligible)
            # The same read outage must not make the subsequent comment POST
            # look like a failed save or remove the open detail.
            page.get_by_label("Work order activity note").fill("E2E follow-up activity note")
            page.get_by_role("button", name="Save activity note").click()
            pw.expect(
                page.get_by_text("Comment recorded in the work order activity history.")
            ).to_be_visible(timeout=15_000)
            pw.expect(page.get_by_text("E2E follow-up activity note")).to_be_visible()
            assert page.get_by_role("button", name="Save activity note").count() == 1
            # Destructive status changes require a second, explicit decision.
            page.get_by_role("button", name="Cancel work order").click()
            pw.expect(page.get_by_role("button", name="Confirm cancellation")).to_be_visible()
            pw.expect(page.get_by_role("button", name="Confirm cancellation")).to_be_disabled()
            page.get_by_label("Cancellation reason").fill("Duplicate request recorded in error")
            pw.expect(page.get_by_role("button", name="Confirm cancellation")).to_be_enabled()
            page.get_by_role("button", name="Keep work order").click()
            pw.expect(page.get_by_text("acknowledged", exact=True)).to_be_visible()
            page.get_by_role("button", name="Cancel work order").click()
            pw.expect(page.get_by_label("Cancellation reason")).to_have_value("")
            page.get_by_label("Cancellation reason").fill("Duplicate request recorded in error")
            page.get_by_role("button", name="Confirm cancellation").click()
            pw.expect(page.get_by_text("Work order cancelled.", exact=True)).to_be_visible(timeout=15_000)
            pw.expect(page.get_by_text("cancelled", exact=True)).to_be_visible(timeout=15_000)
            pw.expect(page.get_by_role("button", name="Cancel work order")).to_have_count(0)
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


def test_emergency_triage_links_to_a_real_authorized_order() -> None:
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
            token = page.evaluate("() => localStorage.getItem('token')")
            assert token
            page.goto(BASE_URL + "/dashboard/maintenance/work-orders/new", wait_until="domcontentloaded")
            pw.expect(page.get_by_role("option", name="E2E Test Property · Unit E2E-1")).to_be_attached(timeout=15_000)
            title = "E2E Emergency triage evidence"
            created = page.request.post(
                API_URL + "/work-orders",
                headers={"Authorization": "Bearer " + token},
                data={
                    "unit_id": 900001,
                    "title": title,
                    "description": "Test emergency requires explicit staff review.",
                    "priority": "emergency",
                    "permission_to_enter": False,
                },
            )
            assert created.status == 201, created.text()
            work_order_id = created.json()["id"]
            page.goto(BASE_URL + "/dashboard/maintenance/work-orders", wait_until="domcontentloaded")
            pw.expect(page.get_by_role("heading", name="Emergency work requiring attention")).to_be_visible()
            triage = page.get_by_role("region", name="Emergency maintenance triage")
            link = triage.get_by_role("link", name="#" + str(work_order_id) + " · " + title)
            pw.expect(link).to_be_visible(timeout=15_000)
            pw.expect(triage.get_by_text("E2E Test Property · Unit E2E-1", exact=True)).to_be_visible()
            link.click()
            page.wait_for_url(re.compile(r"/maintenance/work-orders/" + str(work_order_id) + r"$"), timeout=15_000)
            pw.expect(page.get_by_role("heading", name="Work order #" + str(work_order_id) + ": " + title)).to_be_visible()
        finally:
            browser.close()
