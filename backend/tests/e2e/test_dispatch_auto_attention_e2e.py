"""Authenticated end-to-end recorded in-app escalation with real policy/DB/UI."""
import os
import re
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.core.database import SessionLocal
from app.models.property import Property, PropertyAssignment, PropertyType, Unit
from app.models.user import User, UserRole
from app.models.work_order import MaintenanceOnCallShift, WorkOrder
from app.services.maintenance_dispatch_auto_attention import sweep_due_auto_notices

pw = pytest.importorskip("playwright.sync_api")
pytestmark = pytest.mark.e2e
BASE = os.environ.get("E2E_BASE_URL", "http://127.0.0.1:3000")
API = os.environ.get("E2E_API_BASE_URL", "http://127.0.0.1:8000")
EMAIL = os.environ.get("E2E_ADMIN_EMAIL", "e2e-admin@example.com")
PASSWORD = os.environ.get("E2E_ADMIN_PASSWORD", "test1234")


def test_policy_auto_attention_appears_on_real_authorized_staff_inbox():
    with pw.sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page()
        try:
            page.goto(BASE + "/login", wait_until="domcontentloaded")
            page.locator('input[type="email"]').fill(EMAIL)
            page.locator('input[type="password"]').fill(PASSWORD)
            page.get_by_role("button", name="Log In", exact=True).click()
            page.wait_for_url(re.compile(r"/dashboard/?$"), timeout=15_000)
            token = page.evaluate("() => localStorage.getItem('token')")
            assert token
            headers = {"Authorization": "Bearer " + token}

            # Isolated real property, crew membership and current coverage.
            # E2E fixture owns its disposable PostgreSQL database, shared
            # with the running FastAPI process.
            db = SessionLocal()
            try:
                admin = db.query(User).filter(User.email == EMAIL).one()
                tag = uuid4().hex[:12]
                prop = Property(
                    organization_id=admin.organization_id,
                    name="E2E Auto Escalation " + tag,
                    property_type=PropertyType.MULTI_FAMILY,
                    address_line1="100 Automated Test Street",
                    city="Cleveland", state="OH", zip_code="44113",
                    country="USA", is_active=True,
                )
                db.add(prop)
                db.flush()
                unit = Unit(
                    property_id=prop.id, unit_number="AUTO-1",
                    bedrooms=1, bathrooms=1, monthly_rent=1000,
                    is_active=True, is_available=True,
                )
                crew = User(
                    organization_id=admin.organization_id, role=UserRole.CREW,
                    first_name="E2E", last_name="AutoCrew",
                    email="auto-crew-" + tag + "@example.com",
                    hashed_password="e2e-nonlogin", is_active=True,
                )
                # This user is listed by shared staff APIs with EmailStr validation.
                # A reserved .invalid domain breaks unrelated authenticated pages.
                db.add_all([unit, crew])
                db.flush()
                assert crew.id is not None, 'Fixture crew must have a persisted ID'
                db.add(PropertyAssignment(
                    property_id=prop.id, user_id=crew.id,
                    role=UserRole.CREW, is_active=True,
                ))
                now = datetime.utcnow()
                db.add(MaintenanceOnCallShift(
                    organization_id=admin.organization_id,
                    property_id=prop.id, crew_user_id=crew.id,
                    starts_at=now - timedelta(minutes=2),
                    ends_at=now + timedelta(minutes=30),
                    created_by_user_id=admin.id,
                ))
                prop_id, unit_id, crew_id = prop.id, unit.id, crew.id
                db.commit()
            finally:
                db.close()

            created = page.request.post(
                API + "/api/maintenance/dispatch-groups", headers=headers,
                data={
                    "name": "Auto Escalation " + tag,
                    "property_ids": [prop_id],
                    "timezone_name": "America/New_York",
                    "business_start_hour": 9, "business_end_hour": 17,
                    "automation_requested": True,
                },
            )
            assert created.status == 201, created.text()
            group = created.json()
            assert group["automation_requested"] is True
            for daypart in ("business_hours", "after_hours"):
                result = page.request.put(
                    API + f"/api/maintenance/dispatch-groups/{group['id']}/rules/normal/{daypart}",
                    headers=headers,
                    data={
                        "first_target": "crew", "backup_target": "manager",
                        "timeout_minutes": 1, "escalate": True,
                    },
                )
                assert result.status == 200, result.text()

            created = page.request.post(API + "/work-orders", headers=headers, data={
                "unit_id": unit_id, "title": "Overdue policy offer " + tag,
                "description": "Policy-bound in-app crew offer requires a human review after expiry.",
                "priority": "medium", "permission_to_enter": False,
            })
            assert created.status == 201, created.text()
            order_id = created.json()["id"]
            acknowledged = page.request.post(
                API + f"/work-orders/{order_id}/acknowledge", headers=headers,
            )
            assert acknowledged.status == 200, acknowledged.text()
            offered = page.request.post(
                API + f"/api/maintenance/policy-offers/work-orders/{order_id}",
                headers=headers,
            )
            assert offered.status == 200, offered.text()
            assert offered.json()["assigned_to_id"] == crew_id
            assert offered.json()["assignment_response"] == "pending"

            db = SessionLocal()
            try:
                stored = db.query(WorkOrder).filter(WorkOrder.id == order_id).one()
                now_due = stored.assigned_at.replace(tzinfo=timezone.utc) + timedelta(minutes=3)
                materialized = sweep_due_auto_notices(db, now_utc=now_due, execution_enabled=True)
                assert materialized["created"] == 1
            finally:
                db.close()

            response = page.request.get(
                API + "/api/maintenance/dispatch-attention?limit=100", headers=headers,
            )
            assert response.status == 200, response.text()
            row = next(x for x in response.json() if x["work_order_id"] == order_id)
            assert row["recorded_auto_notice_at"] is not None
            assert row["assignment_response"] == "pending"
            page.goto(BASE + "/dashboard/maintenance/dispatch-attention",
                      wait_until="domcontentloaded")
            pw.expect(page.get_by_role("heading", name="Maintenance dispatch attention")).to_be_visible(timeout=15_000)
            article = page.get_by_role("article").filter(has_text="Overdue policy offer " + tag)
            pw.expect(article).to_be_visible(timeout=15_000)
            pw.expect(article.get_by_text(re.compile("Automated in-app attention recorded"))).to_be_visible(timeout=15_000)
            pw.expect(article.get_by_text(re.compile("no external message was delivered", re.I))).to_be_visible(timeout=15_000)
        finally:
            browser.close()
