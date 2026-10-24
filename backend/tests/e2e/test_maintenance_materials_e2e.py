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
    from app.models.maintenance_material import (MaintenanceMaterialMovement,
        MaintenanceMaterialIssue, MaintenanceMaterialVariance,
        MaintenanceMaterialVarianceDecision, MaintenanceMaterialVarianceRestoration,
        MaintenanceMaterialBatch)
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
            work_order_id=order.id, request_key="E2E-REQUEST-"+tag.upper(), vendor_id=supplier.id, sku="E2E-"+tag.upper(),
            item_name="Maintenance filter set " + tag,
            quantity=5, unit_cost_cents=1900,
            reason="Maintenance needs independently approved filter stock",
        ), db=db, current_user=manager)
        purchase_id = initial["id"]
        work_order_id = order.id
        manager_id = manager.id
        supplier_id = supplier.id
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
            pw.expect(page.get_by_label("Material work order")).to_have_value(str(work_order_id), timeout=15_000)
            page.get_by_role("button", name="Find eligible company vendors").click()
            page.get_by_label("Material vendor").select_option(str(supplier_id))
            page.get_by_label("Material SKU").fill("EXTRA-"+tag.upper())
            page.get_by_label("Material item name").fill("Additional maintenance cable")
            page.get_by_label("Material requested quantity").fill("1")
            page.get_by_label("Material unit cost cents").fill("600")
            page.get_by_label("Material request reason").fill("Replacement cable needed for the maintenance work order")
            page.get_by_role("button", name="Submit internal material request").click()
            pw.expect(page.get_by_role("status").filter(
                has_text="Purchase request recorded"
            )).to_be_visible(timeout=15_000)
            # The admin requester cannot approve their own submitted request.
            self_card = page.locator("article").filter(has_text="Additional maintenance cable").first
            pw.expect(self_card).to_be_visible(timeout=15_000)
            pw.expect(self_card.get_by_role("button", name="Approve internal request")).to_have_count(0)
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
            pw.expect(card).to_contain_text("Available from this request 3", timeout=15_000)
            issue_button = card.get_by_role("button", name="Record physical material usage")
            pw.expect(issue_button).to_be_visible(timeout=15_000)
            issue_qty = card.get_by_label("Material issue quantity "+str(purchase_id))
            pw.expect(issue_qty).to_be_visible(timeout=15_000)
            issue_qty.fill("2")
            card.get_by_label("Material issue work order "+str(purchase_id)).fill(str(work_order_id))
            card.get_by_label("Material issue reference "+str(purchase_id)).fill("E2E-ISSUE-"+tag)
            card.get_by_label("Material issue notes "+str(purchase_id)).fill(
                "Installed two verified filter parts for this work order")
            card.get_by_role("button", name="View physical property stock").click()
            pw.expect(card).to_contain_text("3 units", timeout=15_000)
            card.get_by_role("button", name="Record physical material usage").click()
            pw.expect(card).to_contain_text("Available from this request 1", timeout=15_000)
            pw.expect(card).to_contain_text("Issued to work orders 2")
            page.get_by_role("button",name="Preview unposted material cost").click()
            estimate=page.get_by_role("region",name="Verified unposted material cost preview")
            pw.expect(estimate).to_contain_text("Total unposted estimate: 38.00 USD",timeout=15_000)
            pw.expect(estimate).to_contain_text("GL: not posted")
            pw.expect(estimate).to_contain_text("Tenant: not charged")
            card.get_by_role("button", name="View physical property stock").click()
            pw.expect(card).to_contain_text("1 units", timeout=15_000)
            # Posting no money remains an invariant of material use.

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
                manager_issue = m.issue_materials(purchase_id, m.IssueStock(
                    target_work_order_id=work_order_id,
                    reference="E2E-MANAGER-USE-"+tag, quantity=1,
                    notes="A manager personally installed one additional replacement part",
                ), db=db, current_user=manager)
                manager_issue_id = next(i["id"] for i in manager_issue["material_issues"]
                                        if i["reference"] == "E2E-MANAGER-USE-"+tag)
            finally:
                db.close()
            card.get_by_role("button", name="View physical property stock").click()
            page.get_by_role("button", name="Refresh purchase history").click()
            pw.expect(card).to_contain_text("Net received 5", timeout=15_000)
            pw.expect(card).to_contain_text("Issued to work orders 3", timeout=15_000)
            page.once("dialog", lambda dialog: dialog.accept(
                "Owner independently verified manager use was entered twice"))
            manager_record = card.locator("p").filter(has_text="E2E-MANAGER-USE-"+tag)
            manager_record.get_by_role("button", name="Reverse material usage").click()
            pw.expect(card).to_contain_text("Issued to work orders 2", timeout=15_000)
            pw.expect(card).to_contain_text("reverses usage #"+str(manager_issue_id))
            page.get_by_role("button",name="Preview unposted material cost").click()
            pw.expect(page.get_by_role("region",name="Verified unposted material cost preview")
                ).to_contain_text("Total unposted estimate: 38.00 USD",timeout=15_000)
            page.once("dialog", lambda dialog: dialog.accept(
                "Correction after independent physical recount"))
            correction = card.locator("p").filter(has_text="E2E-SECOND-"+tag)
            correction.get_by_role("button", name="Reverse receipt").click()
            pw.expect(card).to_contain_text("Net received 3", timeout=15_000)
            pw.expect(card).to_contain_text("Available from this request 1", timeout=15_000)
            page.reload(wait_until="domcontentloaded")
            card = page.locator("article").filter(has_text="Maintenance filter set " + tag).first
            pw.expect(card).to_contain_text("Net received 3", timeout=15_000)
            pw.expect(card).to_contain_text("reverses #"+str(receipt_id))

            # A manager reports one physically missing, otherwise unallocated
            # unit. The independent logged-in admin must review it in the UI.
            db = SessionLocal()
            try:
                manager = db.query(User).filter(User.id == manager_id).one()
                proposed = m.report_stock_variance(purchase_id,
                    m.StockVarianceInput(request_key="E2E-VARIANCE-"+tag.upper(),
                        quantity=1,
                        reason="Manager personally counted one missing physical filter"),
                    db=db, current_user=manager)
                variance_id = proposed["stock_variances"][0]["id"]
                admin = db.query(User).filter(User.email == EMAIL).one()
                owner = User(
                    organization_id=admin.organization_id, role=UserRole.OWNER,
                    first_name="Independent",last_name="Restorer",
                    email="stock-restorer-"+tag+"@example.com",
                    hashed_password="nonlogin",is_active=True)
                db.add(owner)
                db.commit()
                owner_id = owner.id
            finally:
                db.close()
            page.get_by_role("button", name="Refresh purchase history").click()
            pw.expect(card).to_contain_text("Report #"+str(variance_id)+" · REQUESTED", timeout=15_000)
            page.once("dialog", lambda dialog: dialog.accept(
                "Administrator reviewed independent count of missing unit"))
            card.get_by_role("button", name="Approve counted shortage").click()
            pw.expect(card).to_contain_text("Approved missing 1", timeout=15_000)
            pw.expect(card).to_contain_text("Available from this request 0")
            db = SessionLocal()
            try:
                owner = db.query(User).filter(User.id == owner_id).one()
                complete = m.restore_stock_variance(purchase_id,variance_id,
                    m.Correction(reason="Independent owner located original missing filter"),
                    db=db,current_user=owner)
                assert complete["net_missing"] == 0
            finally:
                db.close()
            page.get_by_role("button", name="Refresh purchase history").click()
            pw.expect(card).to_contain_text("Report #"+str(variance_id)+" · RESTORED", timeout=15_000)
            pw.expect(card).to_contain_text("Available from this request 1")

            # Two real work-order material lines must be approved as one whole
            # requisition through the visible independent staff interface.
            db = SessionLocal()
            try:
                manager = db.query(User).filter(User.id == manager_id).one()
                batch = m.create_material_batch(m.MaterialBatchRequest(
                    batch_key="E2E-BATCH-MANAGER-"+tag.upper(),
                    work_order_id=work_order_id,vendor_id=supplier_id,
                    reason="Two separate repair parts require independent approval",
                    lines=[
                        m.BatchItem(sku="E2E-A-"+tag.upper(),
                            item_name="Filter bracket "+tag,quantity=2,unit_cost_cents=800),
                        m.BatchItem(sku="E2E-B-"+tag.upper(),
                            item_name="Pipe bracket "+tag,quantity=1,unit_cost_cents=1200),
                    ],
                ),db=db,current_user=manager)
                batch_id=batch["id"]
            finally:
                db.close()
            page.get_by_role("button",name="Refresh purchase history").click()
            group=page.locator("article").filter(has_text="Internal request #"+str(batch_id)).first
            pw.expect(group).to_contain_text("REQUESTED",timeout=15_000)
            group.get_by_label("Batch decision reason "+str(batch_id)).fill(
                "Independent administrator reviewed and approved both items")
            group.get_by_role("button",name="Approve entire requisition").click()
            pw.expect(group).to_contain_text("APPROVED",timeout=15_000)
            db = SessionLocal()
            try:
                manager = db.query(User).filter(User.id == manager_id).one()
                for line in batch["lines"]:
                    receipt=m.receive_materials(line["order_id"],m.Receipt(
                        reference="E2E-BATCH-"+str(line["line_number"])+"-"+tag,
                        quantity=line["quantity"],
                        notes="Independent physical receipt and count of this material line",
                    ),db=db,current_user=manager)
                    assert receipt["net_received"]==line["quantity"]
            finally:
                db.close()

            # Submit two lines using the actual staff creation UI, then prove
            # the requester cannot self-approve. The separate owner decides.
            page.get_by_role("button",name="Find eligible supplier for multi-line request").click()
            vendor_dropdown = page.get_by_label("Material vendor")
            vendor_dropdown.select_option(str(supplier_id))
            pw.expect(vendor_dropdown).to_have_value(str(supplier_id))
            pw.expect(page.get_by_label("Material work order")).to_have_value(str(work_order_id))
            page.get_by_label("Batch SKU 1").fill("E2E-OWN-A-"+tag.upper())
            page.get_by_label("Batch material name 1").fill("First service duct "+tag)
            page.get_by_label("Batch quantity 1").fill("2")
            page.get_by_label("Batch unit cost 1").fill("100")
            page.get_by_label("Batch SKU 2").fill("E2E-OWN-B-"+tag.upper())
            page.get_by_label("Batch material name 2").fill("Second service duct "+tag)
            page.get_by_label("Batch quantity 2").fill("1")
            page.get_by_label("Batch unit cost 2").fill("200")
            page.get_by_label("Batch material reason").fill(
                "Two additional parts submitted for independent whole-batch review")
            pw.expect(page.get_by_role("button",name="Submit all lines together for independent approval")).to_be_enabled()
            page.get_by_role("button",name="Submit all lines together for independent approval").click()
            pw.expect(page.get_by_role("status").filter(
                has_text="All material lines saved together")).to_be_visible(timeout=15_000)
            db=SessionLocal()
            try:
                admin=db.query(User).filter(User.email==EMAIL).one()
                own_batch=db.query(MaintenanceMaterialBatch).filter(
                    MaintenanceMaterialBatch.organization_id==admin.organization_id,
                    MaintenanceMaterialBatch.requested_by_id==admin.id,
                    MaintenanceMaterialBatch.reason==
                        "Two additional parts submitted for independent whole-batch review",
                ).order_by(MaintenanceMaterialBatch.id.desc()).first()
                assert own_batch is not None and own_batch.status=="REQUESTED"
                own_id=own_batch.id
            finally:
                db.close()
            own_card=page.locator("article").filter(
                has_text="Internal request #"+str(own_id)).first
            pw.expect(own_card).to_contain_text("REQUESTED",timeout=15_000)
            pw.expect(own_card.get_by_role("button",name="Approve entire requisition")
                ).to_have_count(0)
            db=SessionLocal()
            try:
                independent_owner=db.query(User).filter(User.id==owner_id).one()
                reviewed=m.decide_material_batch(own_id,m.Decision(
                    approved=True,reason="Owner independently approved both requisition lines",
                ),db=db,current_user=independent_owner)
                assert reviewed["status"]=="APPROVED"
            finally:
                db.close()
            page.get_by_role("button",name="Refresh purchase history").click()
            pw.expect(own_card).to_contain_text("APPROVED",timeout=15_000)
        finally:
            browser.close()

    db = SessionLocal()
    try:
        events = db.query(MaintenanceMaterialMovement).filter_by(order_id=purchase_id).all()
        assert len(events) == 3 and sum(item.delta_qty for item in events) == 3
        used = db.query(MaintenanceMaterialIssue).filter_by(material_order_id=purchase_id).all()
        assert len(used) == 3 and sum(item.delta_qty for item in used) == 2
        assert sum(item.reverses_id is not None for item in used) == 1
        assert db.query(MaintenanceMaterialVariance).filter_by(material_order_id=purchase_id).count() == 1
        assert db.query(MaintenanceMaterialVarianceDecision).count() >= 1
        assert db.query(MaintenanceMaterialVarianceRestoration).count() >= 1
        assert sum(item.reverses_id is not None for item in events) == 1
        assert db.query(AuditLog).filter_by(
            entity_type="maintenance_material_movement", action="physical_receipt_reversed",
        ).count() >= 1
    finally:
        db.close()
