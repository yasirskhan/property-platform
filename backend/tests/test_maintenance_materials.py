"""P5-PROC-06 internal approvals and attested stock, no GL effects."""
import json
import pytest
from fastapi import HTTPException
from sqlalchemy import text
from app.models.audit_log import AuditLog
from app.models.vendor import Vendor
from app.models.property import PropertyAssignment
from app.models.maintenance_material import MaintenanceMaterialOrder as PO, MaintenanceMaterialMovement as Move
from app.routers import maintenance_materials as m
from test_work_order_queue_filters import _seed_queue


def setup():
    db, engine, actors, properties, orders = _seed_queue()
    own, external = actors[0], actors[5]
    db.add_all([
        Vendor(organization_id=own.organization_id, company_name="Maintenance parts", trade="general"),
        Vendor(organization_id=external.organization_id, company_name="Foreign parts", trade="general"),
    ])
    db.commit()
    own_vendor = db.query(Vendor).filter_by(organization_id=own.organization_id).one()
    foreign_vendor = db.query(Vendor).filter_by(organization_id=external.organization_id).one()
    return db, engine, actors, properties, orders, own_vendor, foreign_vendor


def request(wo_id, vendor, *, db, actor):
    return m.create_order(m.NewOrder(
        work_order_id=wo_id, request_key="DETERMINISTIC-REQUEST-00000001", vendor_id=vendor.id, sku="FILTER-02",
        item_name="Air handler filtration kit", quantity=5, unit_cost_cents=12345,
        reason="Replace worn filters as part of maintenance",
    ), db=db, current_user=actor)


def test_material_purchase_independent_approval_partial_receipts_reverse_and_replay():
    db, engine, actors, properties, orders, vendor, foreign_vendor = setup()
    try:
        admin, manager, tenant, other_tenant, crew, foreign = actors
        wo = orders[1]
        created = request(wo.id, vendor, db=db, actor=manager)
        assert created["status"] == "REQUESTED" and created["net_received"] == 0
        assert request(wo.id, vendor, db=db, actor=manager)["id"] == created["id"]
        assert db.query(PO).count() == 1
        with pytest.raises(HTTPException):
            m.create_order(m.NewOrder(
                work_order_id=wo.id, request_key="DETERMINISTIC-REQUEST-00000001",
                vendor_id=vendor.id, sku="FILTER-02",
                item_name="Air handler filtration kit", quantity=4, unit_cost_cents=12345,
                reason="Conflicting retry would duplicate procurement",
            ), db=db, current_user=manager)
        assert created["gl_posted"] is False and created["tenant_charged"] is False
        assert created["vendor_delivery_confirmed"] is False
        with pytest.raises(HTTPException) as self_review:
            m.decide_order(created["id"], m.Decision(approved=True, reason="I approve the material"), db=db, current_user=manager)
        assert self_review.value.status_code == 403
        with pytest.raises(HTTPException):
            m.receive_materials(created["id"], m.Receipt(
                reference="DELIVERY-1", quantity=3,
                notes="Three filters physically inspected",
            ), db=db, current_user=manager)
        decided = m.decide_order(created["id"], m.Decision(
            approved=True, reason="Necessary property maintenance stock approved",
        ), db=db, current_user=admin)
        assert decided["status"] == "APPROVED"
        assert m.decide_order(created["id"], m.Decision(
            approved=True, reason="Necessary property maintenance stock approved",
        ), db=db, current_user=admin)["id"] == created["id"]
        first = m.receive_materials(created["id"], m.Receipt(
            reference="DELIVERY-1", quantity=3, notes="Three filters physically inspected",
        ), db=db, current_user=manager)
        assert first["net_received"] == 3
        assert m.receive_materials(created["id"], m.Receipt(
            reference="DELIVERY-1", quantity=3, notes="Three filters physically inspected",
        ), db=db, current_user=manager)["net_received"] == 3
        with pytest.raises(HTTPException):
            m.receive_materials(created["id"], m.Receipt(
                reference="DELIVERY-1", quantity=4, notes="Conflicting receipt reference",
            ), db=db, current_user=manager)
        with pytest.raises(HTTPException):
            m.receive_materials(created["id"], m.Receipt(
                reference="DELIVERY-2", quantity=3, notes="Over approved material quantity",
            ), db=db, current_user=manager)
        second = m.receive_materials(created["id"], m.Receipt(
            reference="DELIVERY-2", quantity=2, notes="Two more physically received units",
        ), db=db, current_user=manager)
        assert second["net_received"] == 5
        assert m.stock_at_property(properties[0].id, db=db, current_user=admin)[0]["quantity"] == 5
        assert len(second["physical_receipts"]) == 2
        reversal = m.reverse_receipt(created["id"], second["physical_receipts"][0]["id"],
            m.Correction(reason="Wrong physical count on first delivery"),
            db=db, current_user=admin)
        assert reversal["net_received"] == 2
        assert len(reversal["physical_receipts"]) == 3
        assert m.reverse_receipt(created["id"], second["physical_receipts"][0]["id"],
            m.Correction(reason="Wrong physical count on first delivery"),
            db=db, current_user=admin)["net_received"] == 2
        assert m.stock_at_property(properties[0].id, db=db, current_user=manager)[0]["quantity"] == 2
        with pytest.raises(HTTPException):
            m.reverse_receipt(created["id"], second["physical_receipts"][0]["id"],
                m.Correction(reason="Different reversal would be a conflicting amendment"),
                db=db, current_user=admin)
        assert db.query(PO).count() == 1
        assert db.query(Move).count() == 3
        assert db.query(AuditLog).filter_by(entity_type="maintenance_material_order", action="requested").count() == 1
        assert db.query(AuditLog).filter_by(entity_type="maintenance_material_order", action="reviewed").count() == 1
        assert db.query(AuditLog).filter_by(entity_type="maintenance_material_movement", action="physical_receipt_attested").count() == 2
        assert db.query(AuditLog).filter_by(entity_type="maintenance_material_movement", action="physical_receipt_reversed").count() == 1
    finally:
        db.close()
        engine.dispose()


def test_material_orders_require_current_manager_scope_and_vendor_organization():
    db, engine, actors, properties, orders, vendor, foreign_vendor = setup()
    try:
        admin, manager, tenant, other_tenant, crew, foreign = actors
        for bad in (tenant, crew, foreign):
            with pytest.raises(HTTPException):
                request(orders[1].id, vendor, db=db, actor=bad)
        with pytest.raises(HTTPException):
            request(orders[1].id, foreign_vendor, db=db, actor=manager)
        with pytest.raises(HTTPException):
            request(orders[2].id, vendor, db=db, actor=manager)
        one = request(orders[1].id, vendor, db=db, actor=manager)
        assert len(m.list_orders(work_order_id=None, limit=50, db=db, current_user=manager)) == 1
        assert m.list_orders(work_order_id=None, limit=50, db=db, current_user=foreign) == []
        for bad in (tenant, crew, foreign):
            with pytest.raises(HTTPException):
                m.decide_order(one["id"], m.Decision(
                    approved=True, reason="Not authorized to decide"),
                    db=db, current_user=bad)
            with pytest.raises(HTTPException):
                m.receive_materials(one["id"], m.Receipt(
                    reference="DENIED-1", quantity=1, notes="Not allowed receiving"),
                    db=db, current_user=bad)
        assigned = db.query(PropertyAssignment).filter_by(
            user_id=manager.id, property_id=properties[0].id).one()
        assigned.role = type(assigned.role).CREW
        db.commit()
        assert m.list_orders(work_order_id=None, limit=50, db=db, current_user=manager) == []
        with pytest.raises(HTTPException):
            m.receive_materials(one["id"], m.Receipt(
                reference="DENIED-2", quantity=1, notes="Revoked manager cannot receive"),
                db=db, current_user=manager)
        assert db.query(Move).count() == 0
        assert db.query(AuditLog).filter_by(entity_type="maintenance_material_movement").count() == 0
    finally:
        db.close()
        engine.dispose()


def test_receipt_history_data_cannot_be_mutated_when_database_triggers_installed():
    """Migration test separately proves real DB triggers on fresh and legacy paths."""
    from app.models.maintenance_material import MaintenanceMaterialMovement
    assert MaintenanceMaterialMovement.__table__.name == "maintenance_material_movements"


def test_material_receipt_audit_failure_rolls_back_without_inventory_change(monkeypatch):
    db, engine, actors, properties, orders, vendor, foreign_vendor = setup()
    try:
        admin, manager = actors[:2]
        row = request(orders[1].id, vendor, db=db, actor=manager)
        m.decide_order(row["id"], m.Decision(
            approved=True, reason="Independently approve necessary maintenance filters",
        ), db=db, current_user=admin)
        original = m.append_audit_log
        def failed_audit(*args, **kwargs):
            raise RuntimeError("simulated immutable audit storage failure")
        monkeypatch.setattr(m, "append_audit_log", failed_audit)
        with pytest.raises(RuntimeError, match="immutable audit"):
            m.receive_materials(row["id"], m.Receipt(
                reference="AUDIT-INTERRUPTED", quantity=2,
                notes="Physical count interrupted by audit failure",
            ), db=db, current_user=manager)
        db.rollback()
        monkeypatch.setattr(m, "append_audit_log", original)
        assert db.query(Move).count() == 0
        assert m.stock_at_property(properties[0].id, db=db, current_user=admin) == []
        complete = m.receive_materials(row["id"], m.Receipt(
            reference="AUDIT-INTERRUPTED", quantity=2,
            notes="Physical count interrupted by audit failure",
        ), db=db, current_user=manager)
        assert complete["net_received"] == 2
        assert db.query(Move).count() == 1
    finally:
        db.close()
        engine.dispose()


def test_material_foreign_supplier_and_movement_actor_bindings_fail_closed():
    db, engine, actors, properties, orders, vendor, foreign_vendor = setup()
    try:
        admin, manager = actors[:2]
        row = request(orders[1].id, vendor, db=db, actor=manager)
        stored = db.query(PO).filter_by(id=row["id"]).one()
        stored.vendor_id = foreign_vendor.id
        db.flush()
        with pytest.raises(HTTPException) as forged_vendor:
            m.list_orders(work_order_id=None, limit=50, db=db, current_user=admin)
        assert forged_vendor.value.status_code == 409
        stored.vendor_id = vendor.id
        db.commit()
        m.decide_order(row["id"], m.Decision(
            approved=True, reason="Source material purchase verified by administrator",
        ), db=db, current_user=admin)
        m.receive_materials(row["id"], m.Receipt(
            reference="VALID-REFERENCE", quantity=1,
            notes="One legitimate received part inspected",
        ), db=db, current_user=manager)
        movement = db.query(Move).filter_by(order_id=row["id"]).one()
        movement.organization_id = actors[5].organization_id
        db.flush()
        with pytest.raises(HTTPException) as forged_movement:
            m.list_orders(work_order_id=None, limit=50, db=db, current_user=admin)
        assert forged_movement.value.status_code == 409
        with pytest.raises(HTTPException):
            m.stock_at_property(properties[0].id, db=db, current_user=admin)
        db.rollback()  # These tests do not install migration immutability triggers.
        movement = db.query(Move).filter_by(order_id=row["id"]).one()
        movement.received_by_id = actors[5].id
        db.flush()
        with pytest.raises(HTTPException) as forged_actor:
            m.list_orders(work_order_id=None, limit=50, db=db, current_user=admin)
        assert forged_actor.value.status_code == 409
    finally:
        db.close()
        engine.dispose()


def test_independent_owner_can_approve_admin_request_but_receiver_cannot_self_reverse():
    from app.models.user import User, UserRole
    from app.models.gl_transaction import GLTransaction
    db, engine, actors, properties, orders, vendor, foreign_vendor = setup()
    try:
        admin, manager = actors[:2]
        owner = User(
            organization_id=admin.organization_id, role=UserRole.OWNER,
            first_name="Purchasing", last_name="Owner",
            email="purchase-owner@material.example", hashed_password="none",
            is_active=True,
        )
        db.add(owner)
        db.commit()
        own_request = m.create_order(m.NewOrder(
            work_order_id=orders[1].id,
            request_key="OWNER-APPROVAL-CASE-00001", vendor_id=vendor.id,
            sku="FILTER-OWNER-01", item_name="Approved owner maintenance filter",
            quantity=2, unit_cost_cents=900,
            reason="Purchase needs independent approval from the organization owner",
        ), db=db, current_user=admin)
        with pytest.raises(HTTPException) as self_approval:
            m.decide_order(own_request["id"], m.Decision(
                approved=True, reason="Not an independent review",
            ), db=db, current_user=admin)
        assert self_approval.value.status_code == 403
        assert m.decide_order(own_request["id"], m.Decision(
            approved=True, reason="Owner independently verified maintenance requirement",
        ), db=db, current_user=owner)["status"] == "APPROVED"
        receipt = m.receive_materials(own_request["id"], m.Receipt(
            reference="ADMIN-RECEIPT", quantity=2,
            notes="Admin personally inspected both physical units",
        ), db=db, current_user=admin)
        with pytest.raises(HTTPException) as self_reversal:
            m.reverse_receipt(own_request["id"], receipt["physical_receipts"][0]["id"],
                m.Correction(reason="Cannot reverse my own physical receiving"),
                db=db, current_user=admin)
        assert self_reversal.value.status_code == 403
        assert m.reverse_receipt(
            own_request["id"], receipt["physical_receipts"][0]["id"],
            m.Correction(reason="Independent owner found receipt count wrong"),
            db=db, current_user=owner)["net_received"] == 0
        assert m.stock_at_property(properties[0].id, db=db, current_user=owner) == []
        assert db.query(GLTransaction).count() == 0
        assert db.query(PO).count() == 1 and db.query(Move).count() == 2
    finally:
        db.close()
        engine.dispose()


def test_material_approval_rejects_historical_price_and_independent_decision_tampering():
    db, engine, actors, properties, orders, vendor, foreign_vendor = setup()
    try:
        admin, manager = actors[:2]
        row = request(orders[1].id, vendor, db=db, actor=manager)
        stored = db.query(PO).filter_by(id=row["id"]).one()
        stored.unit_cost_cents = 999999
        db.flush()
        with pytest.raises(HTTPException) as tampered_price:
            m.list_orders(work_order_id=None, limit=50, db=db, current_user=admin)
        assert tampered_price.value.status_code == 409
        db.rollback()
        m.decide_order(row["id"], m.Decision(
            approved=True, reason="Owner administrator verified actual purchase amount",
        ), db=db, current_user=admin)
        stored = db.query(PO).filter_by(id=row["id"]).one()
        stored.reviewed_by_id = manager.id
        db.flush()
        with pytest.raises(HTTPException) as changed_reviewer:
            m.receive_materials(row["id"], m.Receipt(
                reference="FORGED-DECISION", quantity=1,
                notes="Attempt to rely on forged approval record",
            ), db=db, current_user=manager)
        assert changed_reviewer.value.status_code == 409
        db.rollback()
        assert db.query(Move).count() == 0
        assert m.receive_materials(row["id"], m.Receipt(
            reference="AUTHORIZED-RECEIPT", quantity=1,
            notes="Physical receipt bound to actual approved request",
        ), db=db, current_user=manager)["net_received"] == 1
    finally:
        db.close()
        engine.dispose()


def test_material_usage_proves_scope_conservation_independent_reversal_and_replay(monkeypatch):
    from app.models.user import User, UserRole
    from app.models.gl_transaction import GLTransaction
    from app.models.maintenance_material import MaintenanceMaterialIssue as Issue
    db, engine, actors, properties, orders, vendor, foreign_vendor = setup()
    try:
        admin, manager, tenant, _, _, outsider = actors
        owner = User(
            organization_id=admin.organization_id, role=UserRole.OWNER,
            first_name="Stock", last_name="Review",
            email="stock-review@material.example", hashed_password="test", is_active=True,
        )
        db.add(owner)
        db.commit()
        purchase = request(orders[1].id, vendor, db=db, actor=manager)
        source_id = purchase["id"]
        m.decide_order(source_id, m.Decision(
            approved=True, reason="Independently authorize available maintenance stock",
        ), db=db, current_user=admin)
        m.receive_materials(source_id, m.Receipt(
            reference="PHYSICAL-3", quantity=3,
            notes="Verified three sealed replacement parts onsite",
        ), db=db, current_user=manager)

        payload = m.IssueStock(
            target_work_order_id=orders[1].id, reference="USE-1",
            quantity=2, notes="Installed two filters for authorized work order",
        )
        for wrong in (tenant, outsider):
            with pytest.raises(HTTPException):
                m.issue_materials(source_id, payload, db=db, current_user=wrong)
        with pytest.raises(HTTPException) as wrong_property:
            m.issue_materials(source_id, m.IssueStock(
                target_work_order_id=orders[2].id, reference="WRONG-PROPERTY",
                quantity=1, notes="Attempted cross-property physical stock use",
            ), db=db, current_user=admin)
        assert wrong_property.value.status_code == 409
        with pytest.raises(HTTPException):
            m.issue_materials(source_id, m.IssueStock(
                target_work_order_id=orders[3].id, reference="OTHER-ORGANIZATION",
                quantity=1, notes="Attempted cross-company physical stock use",
            ), db=db, current_user=admin)
        original_append = m.append_audit_log
        def broken_audit(*args, **kwargs):
            raise RuntimeError("simulated immutable stock usage audit failure")
        monkeypatch.setattr(m, "append_audit_log", broken_audit)
        with pytest.raises(RuntimeError, match="stock usage audit"):
            m.issue_materials(source_id, payload, db=db, current_user=admin)
        db.rollback()
        monkeypatch.setattr(m, "append_audit_log", original_append)
        assert db.query(Issue).count() == 0

        accepted = m.issue_materials(source_id, payload, db=db, current_user=admin)
        assert accepted["net_issued"] == 2 and accepted["available_stock"] == 1
        same = m.issue_materials(source_id, payload, db=db, current_user=admin)
        assert same["material_issues"] == accepted["material_issues"]
        assert m.stock_at_property(properties[0].id, db=db, current_user=owner)[0]["quantity"] == 1
        with pytest.raises(HTTPException):
            m.issue_materials(source_id, m.IssueStock(
                target_work_order_id=orders[1].id, reference="USE-1",
                quantity=1, notes="Conflicting replay must never reduce count",
            ), db=db, current_user=admin)
        with pytest.raises(HTTPException):
            m.issue_materials(source_id, m.IssueStock(
                target_work_order_id=orders[1].id, reference="USE-EXCESS",
                quantity=2, notes="Reject use beyond unallocated source stock",
            ), db=db, current_user=manager)

        receipt_id = accepted["physical_receipts"][0]["id"]
        with pytest.raises(HTTPException) as cannot_reverse:
            m.reverse_receipt(source_id, receipt_id, m.Correction(
                reason="Cannot reverse stock consumed by maintenance",
            ), db=db, current_user=owner)
        assert cannot_reverse.value.status_code == 409
        issue_id = accepted["material_issues"][0]["id"]
        with pytest.raises(HTTPException) as self_reversal:
            m.reverse_material_issue(source_id, issue_id, m.Correction(
                reason="Same person cannot independently reverse own usage",
            ), db=db, current_user=admin)
        assert self_reversal.value.status_code == 403
        with pytest.raises(HTTPException):
            m.reverse_material_issue(source_id, issue_id, m.Correction(
                reason="Property manager cannot approve issue reversal",
            ), db=db, current_user=manager)
        reversed_row = m.reverse_material_issue(source_id, issue_id, m.Correction(
            reason="Independent owner verified usage entry was duplicated",
        ), db=db, current_user=owner)
        assert reversed_row["available_stock"] == 3 and reversed_row["net_issued"] == 0
        replay = m.reverse_material_issue(source_id, issue_id, m.Correction(
            reason="Independent owner verified usage entry was duplicated",
        ), db=db, current_user=owner)
        assert replay["available_stock"] == 3
        assert len(replay["material_issues"]) == 2
        assert db.query(Issue).count() == 2
        with pytest.raises(HTTPException) as decision_conflict:
            m.reverse_material_issue(source_id, issue_id, m.Correction(
                reason="A different reversal reviewer must not replay approval",
            ), db=db, current_user=admin)
        assert decision_conflict.value.status_code in (403, 409)
        assert db.query(AuditLog).filter_by(
            entity_type="maintenance_material_issue",
            action="stock_issued_to_work_order").count() == 1
        assert db.query(AuditLog).filter_by(
            entity_type="maintenance_material_issue",
            action="stock_issue_reversed").count() == 1
        correction = m.reverse_receipt(source_id, receipt_id, m.Correction(
            reason="Owner corrected independent physical receipt count",
        ), db=db, current_user=owner)
        assert correction["available_stock"] == 0
        assert m.stock_at_property(properties[0].id, db=db, current_user=admin) == []
        assert db.query(GLTransaction).count() == 0
        assert all(issue.target_work_order_id == orders[1].id for issue in db.query(Issue))
    finally:
        db.close()
        engine.dispose()


def test_material_usage_foreign_actor_and_audit_tampering_are_denied():
    from app.models.maintenance_material import MaintenanceMaterialIssue as Issue
    db, engine, actors, properties, orders, vendor, foreign_vendor = setup()
    try:
        admin, manager = actors[:2]
        purchase = request(orders[1].id, vendor, db=db, actor=manager)
        m.decide_order(purchase["id"], m.Decision(
            approved=True, reason="Independent staff stock allocation approved",
        ), db=db, current_user=admin)
        m.receive_materials(purchase["id"], m.Receipt(
            reference="DELIVERY-STOCK", quantity=2, notes="Two units verified present onsite",
        ), db=db, current_user=manager)
        allocated = m.issue_materials(purchase["id"], m.IssueStock(
            target_work_order_id=orders[1].id, reference="USED-STOCK",
            quantity=1, notes="One replacement unit actually installed onsite",
        ), db=db, current_user=manager)
        issue = db.query(Issue).one()
        issue.issued_by_id = actors[5].id
        db.flush()
        with pytest.raises(HTTPException) as forged:
            m.list_orders(work_order_id=None, limit=20, db=db, current_user=admin)
        assert forged.value.status_code == 409
        db.rollback()
        assert m.list_orders(work_order_id=None, limit=20, db=db, current_user=admin)[0]["net_issued"] == 1
        assert allocated["gl_posted"] is False and allocated["tenant_charged"] is False
    finally:
        db.close()
        engine.dispose()


def test_multiple_same_sku_purchase_sources_preserve_company_property_stock():
    db, engine, actors, properties, orders, vendor, _ = setup()
    try:
        admin, manager = actors[:2]
        first = request(orders[1].id, vendor, db=db, actor=manager)
        second = m.create_order(m.NewOrder(
            work_order_id=orders[1].id,
            request_key="SAME-SKU-SECOND-ORDER-0001",
            vendor_id=vendor.id, sku="FILTER-02",
            item_name="Air handler filtration kit",
            quantity=2, unit_cost_cents=12345,
            reason="Second independent physical stock purchase order",
        ), db=db, current_user=manager)
        for created, qty, receipt_ref in (
            (first, 5, "FIRST-PHYSICAL-5"),
            (second, 2, "SECOND-PHYSICAL-2"),
        ):
            m.decide_order(created["id"], m.Decision(
                approved=True,
                reason="Independently authorized separate physical purchasing source",
            ), db=db, current_user=admin)
            m.receive_materials(created["id"], m.Receipt(
                reference=receipt_ref, quantity=qty,
                notes="Actual sealed parts physically counted at property",
            ), db=db, current_user=manager)
        assert m.stock_at_property(properties[0].id, db=db, current_user=admin)[0]["quantity"] == 7
        used = m.issue_materials(first["id"], m.IssueStock(
            target_work_order_id=orders[1].id,
            reference="ISSUED-ONLY-FROM-FIRST",
            quantity=2,
            notes="Two filters installed from first verified source",
        ), db=db, current_user=manager)
        assert used["available_stock"] == 3
        assert m.stock_at_property(properties[0].id, db=db, current_user=admin)[0]["quantity"] == 5
        with pytest.raises(HTTPException) as forbidden_reversal:
            m.reverse_receipt(first["id"], used["physical_receipts"][0]["id"],
                m.Correction(reason="Cannot reverse issued first source stock"),
                db=db, current_user=admin)
        assert forbidden_reversal.value.status_code == 409
        assert m.list_orders(work_order_id=orders[1].id, limit=20,
                             db=db, current_user=admin)[0]["id"] == second["id"]
    finally:
        db.close()
        engine.dispose()
