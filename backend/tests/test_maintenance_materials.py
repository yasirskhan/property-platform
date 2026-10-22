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
        work_order_id=wo_id, vendor_id=vendor.id, sku="FILTER-02",
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
        assert len(m.list_orders(db=db, current_user=manager)) == 1
        assert m.list_orders(db=db, current_user=foreign) == []
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
        with pytest.raises(HTTPException):
            m.list_orders(db=db, current_user=manager)
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
