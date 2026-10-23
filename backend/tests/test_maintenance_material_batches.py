"""P5-PROC-06 audited atomic internal multi-line requisition and decision safety."""
import pytest
from fastapi import HTTPException
from app.models.audit_log import AuditLog
from app.models.gl_transaction import GLTransaction
from app.models.maintenance_material import (
    MaintenanceMaterialOrder as Order,
    MaintenanceMaterialBatch as Batch,
    MaintenanceMaterialBatchLine as BatchLine,
)
from app.routers import maintenance_materials as m
from test_maintenance_materials import setup


def body(work_order_id, vendor_id, *, key="VALID-MULTI-LINE-REQ-0001"):
    return m.MaterialBatchRequest(
        batch_key=key, work_order_id=work_order_id, vendor_id=vendor_id,
        reason="Two different parts required for independently authorized maintenance",
        lines=[
            m.BatchItem(sku="KIT-A1",item_name="HVAC filter set",
                quantity=3,unit_cost_cents=1200),
            m.BatchItem(sku="KIT-B2",item_name="Filter mounting bracket",
                quantity=2,unit_cost_cents=350),
        ],
    )


def test_multiple_lines_are_atomic_independently_approved_and_receivable():
    db,engine,actors,properties,orders,vendor,foreign_vendor=setup()
    try:
        admin,manager,tenant,_,_,foreign=actors
        request=body(orders[1].id,vendor.id)
        made=m.create_material_batch(request,db=db,current_user=manager)
        batch_id=made["id"]
        assert made["status"]=="REQUESTED"
        assert made["line_count"]==2
        assert made["estimated_total_cents"]==4300
        assert len(made["lines"])==2
        assert db.query(Order).count()==2 and db.query(BatchLine).count()==2
        assert m.create_material_batch(request,db=db,current_user=manager)==made
        with pytest.raises(HTTPException) as conflicting:
            m.create_material_batch(body(orders[1].id,vendor.id,
                key="VALID-MULTI-LINE-REQ-0001").model_copy(update={
                    "lines":[m.BatchItem(sku="KIT-C3",item_name="Conflicting changed line",
                                        quantity=1,unit_cost_cents=200),
                             request.lines[1]],
                }),db=db,current_user=manager)
        assert conflicting.value.status_code==409
        for actor in (manager,tenant,foreign):
            with pytest.raises(HTTPException):
                m.decide_material_batch(batch_id,m.Decision(
                    approved=True,reason="Independent two-line request approval"),
                    db=db,current_user=actor)
        first=made["lines"][0]["order_id"]
        with pytest.raises(HTTPException) as standalone:
            m.decide_order(first,m.Decision(
                approved=True,reason="Cannot only approve one line"),
                db=db,current_user=admin)
        assert standalone.value.status_code==409
        decision=m.decide_material_batch(batch_id,m.Decision(
            approved=True,reason="Independent two-line request approval"),
            db=db,current_user=admin)
        assert decision["status"]=="APPROVED"
        assert decision["reviewed_by_id"]==admin.id
        assert all(db.get(Order,item["order_id"]).status=="APPROVED" for item in decision["lines"])
        assert m.decide_material_batch(batch_id,m.Decision(
            approved=True,reason="Independent two-line request approval"),
            db=db,current_user=admin)["status"]=="APPROVED"
        with pytest.raises(HTTPException):
            m.decide_material_batch(batch_id,m.Decision(
                approved=False,reason="Contradictory independent decision"),
                db=db,current_user=admin)
        for idx,item in enumerate(decision["lines"]):
            rec=m.receive_materials(item["order_id"],m.Receipt(
                reference="ACTUAL-MULTI-LINE-"+str(idx),
                quantity=item["quantity"],
                notes="Material line separately counted at source property"),
                db=db,current_user=manager)
            assert rec["net_received"]==item["quantity"]
        data=m.stock_at_property(properties[0].id,db=db,current_user=admin)
        assert sum(item["quantity"] for item in data)==5
        assert db.query(GLTransaction).count()==0
        assert db.query(AuditLog).filter_by(
            entity_type="maintenance_material_batch",action="requested").count()==1
        assert db.query(AuditLog).filter_by(
            entity_type="maintenance_material_batch",action="reviewed").count()==1
        assert db.query(AuditLog).filter_by(
            entity_type="maintenance_material_order",action="reviewed").count()==2
    finally:
        db.close();engine.dispose()


def test_batch_audit_failure_rolls_back_all_lines_no_partial_submissions(monkeypatch):
    db,engine,actors,_,orders,vendor,_=setup()
    try:
        manager=actors[1]
        original=m.append_audit_log
        seen=0
        def broken(*args,**kwargs):
            nonlocal seen
            seen+=1
            if seen==2:
                raise RuntimeError("second line audit write failed")
            return original(*args,**kwargs)
        monkeypatch.setattr(m,"append_audit_log",broken)
        with pytest.raises(RuntimeError,match="second line"):
            m.create_material_batch(body(orders[1].id,vendor.id),
                db=db,current_user=manager)
        db.rollback()
        monkeypatch.setattr(m,"append_audit_log",original)
        assert db.query(Order).count()==0
        assert db.query(Batch).count()==0
        assert db.query(BatchLine).count()==0
        assert db.query(AuditLog).filter_by(
            entity_type="maintenance_material_order",action="requested").count()==0
        again=m.create_material_batch(body(orders[1].id,vendor.id),
            db=db,current_user=manager)
        assert again["line_count"]==2
        assert db.query(Order).count()==2
    finally:
        db.close();engine.dispose()


def test_batch_review_failure_rolls_back_all_line_decisions(monkeypatch):
    db,engine,actors,_,orders,vendor,_=setup()
    try:
        admin,manager=actors[:2]
        made=m.create_material_batch(body(orders[1].id,vendor.id),
            db=db,current_user=manager)
        original=m.append_audit_log
        def broken(*args,**kwargs):
            if kwargs.get("action")=="reviewed" and kwargs.get("entity_type")=="maintenance_material_batch":
                raise RuntimeError("final batch review audit failure")
            return original(*args,**kwargs)
        monkeypatch.setattr(m,"append_audit_log",broken)
        with pytest.raises(RuntimeError,match="final batch"):
            m.decide_material_batch(made["id"],m.Decision(
                approved=True,reason="Independent audit failure simulation"),
                db=db,current_user=admin)
        db.rollback()
        monkeypatch.setattr(m,"append_audit_log",original)
        assert db.query(Batch).one().status=="REQUESTED"
        assert all(x.status=="REQUESTED" for x in db.query(Order).all())
        accepted=m.decide_material_batch(made["id"],m.Decision(
            approved=True,reason="Independent audit failure simulation"),
            db=db,current_user=admin)
        assert accepted["status"]=="APPROVED"
    finally:
        db.close();engine.dispose()


def test_multiline_foreign_property_and_corrupted_provenance_fail_closed():
    db,engine,actors,properties,orders,vendor,foreign_vendor=setup()
    try:
        admin,manager,tenant,other_tenant,crew,foreign=actors
        request=body(orders[1].id,vendor.id)
        for actor in (tenant,foreign):
            with pytest.raises(HTTPException):
                m.create_material_batch(request,db=db,current_user=actor)
        with pytest.raises(HTTPException):
            m.create_material_batch(body(orders[1].id,foreign_vendor.id),
                db=db,current_user=manager)
        made=m.create_material_batch(request,db=db,current_user=manager)
        assert m.list_material_batches(work_order_id=None,limit=20,
                    db=db,current_user=admin)[0]["id"]==made["id"]
        with pytest.raises(HTTPException):
            m.list_material_batches(work_order_id=None,limit=20,
                    db=db,current_user=foreign)
        # Mutate the estimated total in ORM state: business reader must validate
        # immutable original audit rather than trusting mutable header bytes.
        header=db.get(Batch,made["id"])
        header.estimated_total_cents=4301
        db.flush()
        with pytest.raises(HTTPException) as tampered:
            m.list_material_batches(work_order_id=None,limit=20,
                db=db,current_user=admin)
        assert tampered.value.status_code==409
        db.rollback()
        binding=db.query(BatchLine).first()
        original_order=binding.order_id
        binding.order_id=orders[2].id
        db.flush()
        with pytest.raises(HTTPException):
            m.list_material_batches(work_order_id=None,limit=20,
                db=db,current_user=admin)
        db.rollback()
        assert db.query(BatchLine).first().order_id==original_order
    finally:
        db.close();engine.dispose()


def test_multiline_denial_is_atomic_and_physical_receipt_prohibited():
    db,engine,actors,_,orders,vendor,_=setup()
    try:
        admin,manager=actors[:2]
        made=m.create_material_batch(body(orders[1].id,vendor.id),
            db=db,current_user=manager)
        ended=m.decide_material_batch(made["id"],m.Decision(
            approved=False,reason="Owner denies all unverified requisition lines"),
            db=db,current_user=admin)
        assert ended["status"]=="DENIED"
        assert all(db.get(Order,i["order_id"]).status=="DENIED" for i in ended["lines"])
        for item in ended["lines"]:
            with pytest.raises(HTTPException):
                m.receive_materials(item["order_id"],m.Receipt(
                    reference="CANNOT-RECEIVE",quantity=1,
                    notes="Physical receiving denied before approval"),
                    db=db,current_user=manager)
    finally:
        db.close();engine.dispose()
