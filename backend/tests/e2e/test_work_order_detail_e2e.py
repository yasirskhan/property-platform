"""Authenticated customer work-order detail and activity regression."""
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
            pw.expect(page.get_by_text(re.compile(r"Request source: Staff request"))).to_be_visible(timeout=15_000)
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
            # Resolve the card from the unique, visible work-order link.
            # A scoped `has=link` filter can fail because Playwright treats
            # the inner locator as relative to each candidate list item.
            card = link.locator("xpath=../..")
            pw.expect(card.get_by_text(
                "E2E Test Property · Unit E2E-1", exact=True
            )).to_be_visible(timeout=15_000)
            link.click()
            page.wait_for_url(re.compile(r"/maintenance/work-orders/" + str(work_order_id) + r"$"), timeout=15_000)
            pw.expect(page.get_by_role("heading", name="Work order #" + str(work_order_id) + ": " + title)).to_be_visible()
        finally:
            browser.close()


def test_crew_accepts_and_rejects_dispatch_with_audited_reassignment() -> None:
    """Browser flow from manager assignment to a crew decision, without tenant consent."""
    with pw.sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        admin = browser.new_page()
        crew_page = browser.new_page()
        try:
            admin.goto(BASE_URL + "/login", wait_until="domcontentloaded")
            admin.locator('input[type="email"]').fill(EMAIL)
            admin.locator('input[type="password"]').fill(PASSWORD)
            admin.get_by_role("button", name="Log In", exact=True).click()
            admin.wait_for_url(re.compile(r"/dashboard/?$"), timeout=15_000)
            pw.expect(admin.get_by_text("Signed in as", exact=True)).to_be_visible(timeout=15_000)
            token = admin.evaluate("() => localStorage.getItem('token')")
            assert token
            auth = {"Authorization": "Bearer " + token}
            identity = admin.request.get(API_URL + "/auth/me", headers=auth)
            assert identity.status == 200, identity.text()
            org_id = identity.json()["organization_id"]
            email = "maintenance-crew-" + uuid4().hex[:16] + "@example.com"
            password = "E2eCrewSecret!2026"
            created = admin.request.post(API_URL + "/users/crew", headers=auth, data={
                "email": email, "password": password, "first_name": "Maintenance",
                "last_name": "Crew", "organization_id": org_id, "role": "CREW",
            })
            assert created.status == 201, created.text()
            crew_id = created.json()["id"]
            assigned_property = admin.request.post(
                API_URL + "/properties/900001/assignments?user_id=" + str(crew_id),
                headers=auth,
            )
            assert assigned_property.status == 201, assigned_property.text()

            def dispatch(title: str) -> int:
                submitted = admin.request.post(API_URL + "/work-orders", headers=auth, data={
                    "unit_id": 900001, "title": title,
                    "description": "Verify explicit crew offer decisions and management recovery.",
                    "permission_to_enter": False,
                })
                assert submitted.status == 201, submitted.text()
                order_id = submitted.json()["id"]
                ack = admin.request.post(API_URL + "/work-orders/" + str(order_id) + "/acknowledge",
                                         headers=auth)
                assert ack.status == 200, ack.text()
                assign = admin.request.post(API_URL + "/work-orders/" + str(order_id) + "/assign",
                                            headers=auth, data={"crew_user_id": crew_id})
                assert assign.status == 200, assign.text()
                assert assign.json()["assignment_response"] == "pending"
                return order_id

            first = dispatch("E2E crew accepts maintenance dispatch")
            second = dispatch("E2E crew rejects maintenance dispatch")

            crew_page.goto(BASE_URL + "/login", wait_until="domcontentloaded")
            crew_page.locator('input[type="email"]').fill(email)
            crew_page.locator('input[type="password"]').fill(password)
            crew_page.get_by_role("button", name="Log In", exact=True).click()
            crew_page.wait_for_url(re.compile(r"/dashboard/?$"), timeout=15_000)
            pw.expect(crew_page.get_by_text("Signed in as", exact=True)).to_be_visible(timeout=15_000)
            crew_page.goto(BASE_URL + "/dashboard/maintenance/work-orders/" + str(first),
                           wait_until="domcontentloaded")
            pw.expect(crew_page.get_by_role("heading", name=re.compile(r"Work order #" + str(first)))).to_be_visible(timeout=15_000)
            pw.expect(crew_page.get_by_role("button", name="Start work")).to_have_count(0)
            crew_page.get_by_role("button", name="Accept assignment").click()
            pw.expect(crew_page.get_by_text("Work order assignment accepted.", exact=True)).to_be_visible(timeout=15_000)
            pw.expect(crew_page.get_by_role("button", name="Start work")).to_be_visible(timeout=15_000)
            crew_page.get_by_role("button", name="Start work").click()
            pw.expect(crew_page.get_by_text("Work order started.", exact=True)).to_be_visible(timeout=15_000)

            crew_page.goto(BASE_URL + "/dashboard/maintenance/work-orders/" + str(second),
                           wait_until="domcontentloaded")
            pw.expect(crew_page.get_by_role("heading", name=re.compile(r"Work order #" + str(second)))).to_be_visible(timeout=15_000)
            crew_page.get_by_role("button", name="Reject assignment").click()
            pw.expect(crew_page.get_by_role("button", name="Confirm assignment rejection")).to_be_disabled()
            crew_page.get_by_label("Crew rejection reason").fill("Unavailable for the overnight maintenance shift")
            crew_page.get_by_role("button", name="Confirm assignment rejection").click()
            pw.expect(crew_page.get_by_text(
                "Work order assignment rejected for reassignment.", exact=True
            )).to_be_visible(timeout=15_000)
            after = admin.request.get(API_URL + "/work-orders/" + str(second), headers=auth)
            assert after.status == 200, after.text()
            assert after.json()["status"] == "acknowledged"
            assert after.json()["assigned_to_id"] is None
            assert after.json()["assignment_response"] == "rejected"
        finally:
            crew_page.close()
            admin.close()
            browser.close()
