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
            page.get_by_label("Inspection condition", exact=True).select_option("ATTENTION_NEEDED")
            page.get_by_label("SAFETY condition").select_option("ATTENTION_NEEDED")
            page.get_by_label("SAFETY notes").fill("Replace hall smoke alarm")
            page.get_by_label("PLUMBING condition").select_option("SATISFACTORY")
            page.get_by_label("Inspection findings").fill("Inspected window latch by staff")
            page.get_by_role("button", name="Save inspection record").click()
            pw.expect(page.get_by_role("status").filter(
                has_text="Inspection evidence recorded and audited."
            )).to_be_visible(timeout=15_000)
            pw.expect(page.get_by_text("Inspected window latch by staff")).to_be_visible()
            card = page.locator("section li").filter(has_text="Inspected window latch by staff").first
            pw.expect(card).to_contain_text("SAFETY: ATTENTION NEEDED")
            pw.expect(card).to_contain_text("Replace hall smoke alarm")
            pw.expect(card).to_contain_text("PLUMBING: SATISFACTORY")
            # Reload from the API to prove the checklist was persisted, not
            # merely reflected from the successful POST response.
            page.reload(wait_until="domcontentloaded")
            persisted = page.locator("section li").filter(has_text="Inspected window latch by staff").first
            pw.expect(persisted).to_contain_text("SAFETY: ATTENTION NEEDED", timeout=15_000)
            pw.expect(persisted).to_contain_text("Replace hall smoke alarm")
            persisted.get_by_role("link", name=re.compile(r"Inspection #[0-9]+")).click()
            page.wait_for_url(re.compile(r"/maintenance/staff-inspection-records/[0-9]+$"), timeout=15_000)
            pw.expect(page.get_by_role("heading", name=re.compile(r"Inspection #[0-9]+"))).to_be_visible(timeout=15_000)
            pw.expect(page.get_by_text("Inspected window latch by staff")).to_be_visible()
            pw.expect(page.get_by_text("Replace hall smoke alarm")).to_be_visible()
            page.get_by_role("link", name="Back to inspection records").click()
            page.wait_for_url(re.compile(r"/maintenance/staff-inspection-records/?$"), timeout=15_000)
            page.get_by_label("Filter inspection unit").select_option("900001")
            page.get_by_label("Filter inspection condition").select_option("ATTENTION_NEEDED")
            page.get_by_label("Inspection history start date").fill(date.today().isoformat())
            page.get_by_role("button", name="Filter history").click()
            pw.expect(page.locator("section li").filter(
                has_text="Inspected window latch by staff"
            ).first).to_contain_text("ATTENTION NEEDED", timeout=15_000)
            pw.expect(page.locator("section li").filter(
                has_text="Inspected window latch by staff"
            ).first).to_contain_text("Unit E2E-1")
            # Follow up on the recorded inspection in a real, scoped work order.
            saved_row = page.locator("section li").filter(
                has_text="Inspected window latch by staff"
            ).first
            saved_row.get_by_role("link", name=re.compile(r"Inspection #[0-9]+")).click()
            page.get_by_role("link", name="Create follow-up work order").click()
            page.wait_for_url(re.compile(r"/maintenance/work-orders/new[?]source_inspection_id=[0-9]+"), timeout=15_000)
            pw.expect(page.get_by_label("Maintenance problem title")).to_have_value(
                re.compile(r"Inspection follow-up #[0-9]+"), timeout=15_000
            )
            pw.expect(page.get_by_role("option", name="E2E Test Property · Unit E2E-1")).to_be_attached(timeout=15_000)
            pw.expect(page.get_by_label("Maintenance request unit")).to_have_value("900001", timeout=15_000)
            pw.expect(page.get_by_label("Maintenance problem description")).to_have_value(
                re.compile("Inspected window latch by staff")
            )
            page.get_by_role("button", name="Submit maintenance request").click()
            page.wait_for_url(re.compile(r"/maintenance/work-orders/[0-9]+$"), timeout=15_000)
            pw.expect(page.get_by_role("link", name=re.compile(r"staff inspection #[0-9]+"))).to_be_visible(timeout=15_000)
            page.get_by_role("link", name=re.compile(r"staff inspection #[0-9]+")).click()
            page.wait_for_url(re.compile(r"/maintenance/staff-inspection-records/[0-9]+$"), timeout=15_000)
            pw.expect(page.get_by_role("heading", name="Linked maintenance work orders")).to_be_visible()
            pw.expect(page.get_by_role("link", name=re.compile(r"Work order #[0-9]+: Inspection follow-up #[0-9]+"))).to_be_visible(timeout=15_000)
        finally:
            browser.close()

def test_independent_inspection_review_is_saved_through_authenticated_browser():
    """A second authorized staff member reviews evidence without editing it."""
    from uuid import uuid4
    from app.core.database import SessionLocal
    from app.models.audit_log import AuditLog
    from app.models.property import Property, PropertyAssignment, Unit
    from app.models.unit_inspection import UnitInspectionRecord, UnitInspectionReview
    from app.models.user import User, UserRole
    from app.services.audit import append_audit_log

    db = SessionLocal()
    try:
        admin = db.query(User).filter(User.email == EMAIL).one()
        prop, unit = db.query(Property, Unit).join(
            Unit, Unit.property_id == Property.id,
        ).filter(
            Property.organization_id == admin.organization_id,
            Unit.unit_number == "E2E-1",
            Property.is_active.is_(True),
        ).first()
        tag = uuid4().hex[:12]
        inspector = User(
            organization_id=admin.organization_id, role=UserRole.MANAGER,
            first_name="E2E", last_name="IndependentInspector",
            email="e2e-inspector-" + tag + "@example.com",
            hashed_password="e2e-nonlogin", is_active=True,
        )
        db.add(inspector)
        db.flush()
        db.add(PropertyAssignment(
            property_id=prop.id, user_id=inspector.id,
            role=UserRole.MANAGER, is_active=True,
        ))
        evidence = UnitInspectionRecord(
            organization_id=admin.organization_id,
            property_id=prop.id, unit_id=unit.id,
            inspection_date=date.today(),
            recorded_condition="ATTENTION_NEEDED",
            findings="Independent follow-up review " + tag,
            recorded_by_id=inspector.id,
        )
        db.add(evidence)
        db.flush()
        append_audit_log(
            db, organization_id=admin.organization_id, user_id=inspector.id,
            entity_type="unit_inspection_record", entity_id=evidence.id,
            action="created",
            new_value={"unit_id": unit.id, "findings": evidence.findings},
        )
        evidence_id = evidence.id
        inspector_id = inspector.id
        db.commit()
    finally:
        db.close()

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
            page.goto(BASE_URL + f"/dashboard/maintenance/staff-inspection-records/{evidence_id}",
                      wait_until="domcontentloaded")
            pw.expect(page.get_by_text("Independent follow-up review " + tag)).to_be_visible(timeout=15_000)
            pw.expect(page.get_by_role("heading", name="Independent inspection review")).to_be_visible(timeout=15_000)
            page.context.set_offline(True)
            page.get_by_label("Inspection photo").set_input_files({
                "name": "inspection-photo.png",
                "mimeType": "image/png",
                "buffer": bytes.fromhex("89504e470d0a1a0a") + b"inspection browser fixture",
            })
            page.get_by_role("button", name="Save locally to sync later").click()
            pw.expect(page.get_by_text("1 unsent photos on this device")).to_be_visible(timeout=15_000)
            page.get_by_role("button", name="Sync pending photos").click()
            pw.expect(page.get_by_text(re.compile("Unsent photos remain on this device"))).to_be_visible(timeout=15_000)
            pw.expect(page.get_by_text("1 unsent photos on this device")).to_be_visible(timeout=15_000)
            page.context.set_offline(False)
            # Transport and ID/size success are insufficient to purge a local
            # draft: a forged checksum or mismatched organization must retain it.
            def wrong_digest(route):
                result = route.fetch()
                route.fulfill(response=result, json={**result.json(), "sha256": "0" * 64})
            page.route("**/api/unit-inspections/*/photos", wrong_digest, times=1)
            page.get_by_role("button", name="Sync pending photos").click()
            pw.expect(page.get_by_text("1 unsent photos on this device")).to_be_visible(timeout=15_000)
            pw.expect(page.get_by_text(re.compile("Unsent photos remain on this device"))).to_be_visible(timeout=15_000)
            def wrong_organization(route):
                result = route.fetch()
                acknowledged = result.json()
                route.fulfill(response=result, json={
                    **acknowledged, "organization_id": acknowledged["organization_id"] + 1})
            page.route("**/api/unit-inspections/*/photos", wrong_organization, times=1)
            page.get_by_role("button", name="Sync pending photos").click()
            pw.expect(page.get_by_text("1 unsent photos on this device")).to_be_visible(timeout=15_000)
            page.get_by_role("button", name="Sync pending photos").click()
            pw.expect(page.get_by_role("button", name=re.compile("inspection-photo.png"))).to_be_visible(timeout=15_000)
            pw.expect(page.get_by_text("1 unsent photos on this device")).to_have_count(0)
            # Another same-account tab queues a new private draft AFTER the
            # reviewer's first tab last examined device-local evidence.
            other_tab = page.context.new_page()
            other_tab.goto(BASE_URL + f"/dashboard/maintenance/staff-inspection-records/{evidence_id}",
                           wait_until="domcontentloaded")
            pw.expect(other_tab.get_by_role("heading", name="Independent inspection review")).to_be_visible(timeout=15_000)
            other_tab.get_by_label("Inspection photo").set_input_files({
                "name": "second-tab-proof.png", "mimeType": "image/png",
                "buffer": bytes.fromhex("89504e470d0a1a0a") + b"second tab evidence",
            })
            other_tab.get_by_role("button", name="Save locally to sync later").click()
            pw.expect(other_tab.get_by_text("1 unsent photos on this device")).to_be_visible(timeout=15_000)
            other_tab.close()
            page.get_by_label("Independent review decision").select_option("FOLLOW_UP_REQUIRED")
            page.get_by_label("Review explanation").fill("Follow up on the observed exterior condition")
            page.get_by_role("button", name="Record independent review").click()
            pw.expect(page.get_by_text("Unsent device-local evidence was found", exact=False)).to_be_visible(timeout=15_000)
            pw.expect(page.get_by_text("1 unsent photos on this device")).to_be_visible(timeout=15_000)
            pw.expect(page.get_by_text("Independent inspection review recorded and audited.")).to_have_count(0)
            page.get_by_role("button", name="Sync pending photos").click()
            pw.expect(page.get_by_text("1 unsent photos on this device")).to_have_count(0, timeout=15_000)
            pw.expect(page.get_by_role("button", name=re.compile("second-tab-proof.png"))).to_be_visible(timeout=15_000)
            page.get_by_role("button", name="Record independent review").click()
            pw.expect(page.get_by_text(re.compile(r"Reviewed by .*user #"))).to_be_visible(timeout=15_000)
            pw.expect(page.get_by_role("status").filter(
                has_text="Independent inspection review recorded and audited."
            )).to_be_visible(timeout=15_000)
            pw.expect(page.get_by_text("Decision: FOLLOW UP REQUIRED")).to_be_visible(timeout=15_000)
            pw.expect(page.get_by_role("button", name="Add private evidence")).to_have_count(0)
            page.reload(wait_until="domcontentloaded")
            pw.expect(page.get_by_text("Decision: FOLLOW UP REQUIRED")).to_be_visible(timeout=15_000)
            pw.expect(page.get_by_text("Follow up on the observed exterior condition")).to_be_visible()
            pw.expect(page.get_by_text("Independent follow-up review " + tag)).to_be_visible()

            db = SessionLocal()
            try:
                stored = db.query(UnitInspectionReview).filter_by(inspection_id=evidence_id).one()
                assert stored.decision == "FOLLOW_UP_REQUIRED"
                assert stored.reviewer_id != inspector_id
                assert db.query(AuditLog).filter_by(
                    entity_type="unit_inspection_review", entity_id=stored.id,
                    action="independent_review_recorded",
                ).count() == 1
            finally:
                db.close()
        finally:
            browser.close()
