"""Authenticated preventive schedule: create, generate due, replay, pause, history."""
from __future__ import annotations
from datetime import date, timedelta
import os
import re
import pytest

pw = pytest.importorskip("playwright.sync_api")
pytestmark = pytest.mark.e2e
BASE_URL = os.environ.get("E2E_BASE_URL", "http://127.0.0.1:3000")
EMAIL = os.environ.get("E2E_ADMIN_EMAIL", "e2e-admin@example.com")
PASSWORD = os.environ.get("E2E_ADMIN_PASSWORD", "test1234")


def test_staff_creates_preventive_schedule_and_one_tenantless_due_work_order():
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
            page.goto(BASE_URL + "/dashboard/maintenance/preventive", wait_until="domcontentloaded")
            pw.expect(page.get_by_role("heading", name="Preventive maintenance schedules")).to_be_visible(timeout=15_000)
            pw.expect(page.get_by_text(re.compile(r"Showing [0-9]+ authorized preventive maintenance schedules"))).to_be_visible(timeout=15_000)
            pw.expect(page.get_by_role("option", name="E2E Test Property · Unit E2E-1")).to_be_attached(timeout=15_000)
            page.get_by_label("Preventive maintenance unit", exact=True).select_option("900001")
            page.get_by_label("Preventive task title").fill("E2E HVAC scheduled filter check")
            page.get_by_label("Preventive task description").fill("Inspect and replace air filters every thirty days.")
            page.get_by_label("Preventive schedule interval").fill("30")
            page.get_by_label("Preventive first due date").fill(date.today().isoformat())
            page.get_by_role("button", name="Save schedule").click()
            pw.expect(page.get_by_role("status").filter(
                has_text="No work order was generated at creation"
            )).to_be_visible(timeout=15_000)
            card = page.locator("article").filter(has_text="E2E HVAC scheduled filter check").first
            pw.expect(card).to_contain_text("Active")
            card.get_by_role("button", name="Check execution status").click()
            pw.expect(card.get_by_text(re.compile(r"Execution: ready"))).to_be_visible(timeout=15_000)
            card.get_by_role("button", name="Take over schedule execution").click()
            card.get_by_label(re.compile(r"Execution transfer reason")).fill(
                "Confirm current administrator operates this preventive schedule"
            )
            card.get_by_role("button", name="Confirm execution takeover").click()
            pw.expect(page.get_by_role("status").filter(
                has_text="Schedule execution responsibility recorded"
            )).to_be_visible(timeout=15_000)
            card.get_by_role("button", name="Preview due backlog").click()
            pw.expect(card.get_by_role("heading", name="Due backlog preview — no work orders created")).to_be_visible(timeout=15_000)
            pw.expect(card).to_contain_text(date.today().isoformat())
            card.get_by_role("button", name="Generate due work order").click()
            pw.expect(page.get_by_role("status").filter(
                has_text="generated without a tenant or automatic charge"
            )).to_be_visible(timeout=15_000)
            card.get_by_role("button", name="Occurrence history").click()
            pw.expect(card.get_by_role("link", name=re.compile(r"Work order #[0-9]+"))).to_be_visible(timeout=15_000)
            card.get_by_role("button", name="Generate due work order").click()
            pw.expect(page.get_by_role("status").filter(
                has_text="Due occurrence already exists"
            )).to_be_visible(timeout=15_000)
            card.get_by_role("button", name="Pause", exact=True).click()
            pw.expect(card).to_contain_text("Paused", timeout=15_000)
            pw.expect(card.get_by_role("button", name="Generate due work order")).to_be_disabled()
            card.get_by_role("button", name="Edit paused schedule").click()
            card.get_by_label(re.compile(r"Edit preventive title")).fill("E2E revised filter schedule")
            card.get_by_label(re.compile(r"Edit preventive instructions")).fill("Inspect safety filters and ventilation thoroughly")
            card.get_by_label(re.compile(r"Edit preventive interval")).fill("45")
            card.get_by_label(re.compile(r"Edit preventive end date")).fill(
                (date.today() + timedelta(days=60)).isoformat()
            )
            card.get_by_role("button", name="Save schedule changes").click()
            pw.expect(page.get_by_role("status").filter(
                has_text="settings updated and audited"
            )).to_be_visible(timeout=15_000)
            updated_card = page.locator("article").filter(
                has_text="E2E revised filter schedule"
            ).first
            pw.expect(updated_card).to_contain_text("Every 45 days")
            pw.expect(updated_card).to_contain_text("Ends ")
            pw.expect(updated_card.get_by_role("link", name=re.compile(r"Work order #[0-9]+"))).to_be_visible()
            updated_card.get_by_role("button", name="Resume").click()
            pw.expect(updated_card).to_contain_text("Active", timeout=15_000)
            page.reload(wait_until="domcontentloaded")
            fresh = page.locator("article").filter(has_text="E2E revised filter schedule").first
            pw.expect(fresh).to_contain_text("Every 45 days", timeout=15_000)
            pw.expect(fresh).to_contain_text("Ends ")
        finally:
            browser.close()
