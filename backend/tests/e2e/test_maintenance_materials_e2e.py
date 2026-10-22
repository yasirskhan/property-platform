"""Authenticated procurement from an actual work order to corrected physical stock."""
from datetime import date
import os
import re
from uuid import uuid4
import pytest

pw = pytest.importorskip("playwright.sync_api")
pytestmark = pytest.mark.e2e
BASE_URL = os.environ.get("E2E_BASE_URL", "http://127.0.0.1:3000")
EMAIL = os.environ.get("E2E_ADMIN_EMAIL", "e2e-admin@example.com")
PASSWORD = os.environ.get("E2E_ADMIN_PASSWORD", "test1234")


def test_materials_approval_receipt_and_independent_stock_correction_in_browser():
    from app.core.database import SessionLocal
    from app.models.audit_log import AuditLog
    from app.models.property import Property, Unit, PropertyAssignment
    from app.models.user import User, UserRole
    from app.models.work_order import WorkOrder, WorkOrderStatus
    from app.models.vendor import Vendor
    from app.models.maintenance_material import MaintenanceMaterialMovement
    from app.routers import maintenance_materials as m

    tag = uuid4().hex[:10]
    db = SessionLocal()
    try:
        admin = db.query(User).filter(User.email == EMAIL).one()
        prop, unit = db.query(Property, Unit).join(
            Unit, Unit.property_id == Property.id,
        ).filter(
            Property.organization_id == admin.organization_id,
            Unit.unit_number == "E2E-1", Property.is_active.is_(True),
        ).first()
        assert unit is not None and prop is not None
        manager = User(
            organization_id=admin.organization_id, role=UserRole.MANAGER,
            first_name="Material", last_name="Receiver",
            email="material-" + tag + "@example.com",
            hashed_password="nonlogin", is_active=True,
        )
        supplier = Vendor(
            organization_id=admin.organization_id,
            company_name="E2E Material Supplier " + tag,
            trade="general", is_active=True,
        )
        db.add_all([manager, supplier])
        db.flush()
        db.add(PropertyAssignment(
            property_id=prop.id, user_id=manager.id,
            role=UserRole.MANAGER, is_active=True,
        ))
        order = WorkOrder(
            property_id=prop.id, unit_id=unit.id, tenant_id=None,
            request_origin="staff", requested_by_user_id=admin.id,
            status=WorkOrderStatus.SUBMITTED, title="Material replacement " + tag,
            description="Physical material receipt E2E verification",
            permission_to_enter=False,
        )
        db.add(order)
        db.commit()
        initial = m.create_order(m.NewOrder(
            work_order_id=order.id, vendor_id=supplier.id, sku="E2E-"+tag.upper(),
            item_name="Maintenance filter set " + tag,
            quantity=5, unit_cost_cents=1900,
            reason="Maintenance needs independently approved filter stock",
        ), db=db, current_user=manager)
        purchase_id = initial["id"]
        work_order_id = order.id
        manager_id = manager.id
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
            page.goto(BASE_URL + "/dashboard/maintenance/material-orders?work_order_id="+str(work_order_id),
                      wait_until="domcontentloaded")
            pw.expect(page.get_by_role("heading", name="Material purchasing and physical receipts")).to_be_visible(timeout=15_000)
            card = page.locator("article").filter(has_text="Maintenance filter set " + tag).first
            pw.expect(card).to_be_visible(timeout=15_000)
            pw.expect(card).to_contain_text("Status: REQUESTED")
            card.get_by_label("Material decision reason "+str(purchase_id)).fill(
                "Verified maintenance needs these replacement parts")
            card.get_by_role("button", name="Approve internal request").click()
            pw.expect(page.get_by_role("status").filter(
                has_text="Purchase approved internally"
            )).to_be_visible(timeout=15_000)
            pw.expect(card).to_contain_text("Status: APPROVED")
            card.get_by_label("Material receipt reference "+str(purchase_id)).fill("E2E-FIRST-"+tag)
            card.get_by_label("Material receipt quantity "+str(purchase_id)).fill("3")
            card.get_by_label("Material receipt notes "+str(purchase_id)).fill(
                "Inspected three delivered filter sets in person")
            card.get_by_role("button", name="Record received stock").click()
            pw.expect(card).to_contain_text("Net received 3", timeout=15_000)
            card.get_by_role("button", name="View physical property stock").click()
            pw.expect(card).to_contain_text("3 units", timeout=15_000)

            # A different live manager attests the second physical receipt.
            db = SessionLocal()
            try:
                admin = db.query(User).filter(User.email == EMAIL).one()
                manager = db.query(User).filter(User.id == manager_id).one()
                received = m.receive_materials(purchase_id, m.Receipt(
                    reference="E2E-SECOND-"+tag, quantity=2,
                    notes="Independently inspected two additional filter kits",
                ), db=db, current_user=manager)
                positive = next(x for x in received["physical_receipts"]
                                if x["reference"] == "E2E-SECOND-"+tag)
                receipt_id = positive["id"]
            finally:
                db.close()
            card.get_by_role("button", name="View physical property stock").click()
            page.get_by_role("button", name="Refresh purchase history").click()
            pw.expect(card).to_contain_text("Net received 5", timeout=15_000)
            page.once("dialog", lambda dialog: dialog.accept(
                "Correction after independent physical recount"))
            correction = card.locator("p").filter(has_text="E2E-SECOND-"+tag)
            correction.get_by_role("button", name="Reverse receipt").click()
            pw.expect(card).to_contain_text("Net received 3", timeout=15_000)
            page.reload(wait_until="domcontentloaded")
            card = page.locator("article").filter(has_text="Maintenance filter set " + tag).first
            pw.expect(card).to_contain_text("Net received 3", timeout=15_000)
            pw.expect(card).to_contain_text("reverses #"+str(receipt_id))
        finally:
            browser.close()

    db = SessionLocal()
    try:
        events = db.query(MaintenanceMaterialMovement).filter_by(order_id=purchase_id).all()
        assert len(events) == 3 and sum(item.delta_qty for item in events) == 3
        assert sum(item.reverses_id is not None for item in events) == 1
        assert db.query(AuditLog).filter_by(
            entity_type="maintenance_material_movement", action="physical_receipt_reversed",
        ).count() >= 1
    finally:
        db.close()
