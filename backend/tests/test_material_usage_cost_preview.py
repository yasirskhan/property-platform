"""P5-PROC-06 actual physical usage × original unposted estimate only."""
import pytest
from fastapi import HTTPException
from app.models.audit_log import AuditLog
from app.models.gl_transaction import GLTransaction
from app.models.property import PropertyAssignment
from app.models.user import UserRole
from app.routers import maintenance_materials as m
from test_maintenance_materials import setup, request


def stock_with_two_original_prices():
    db,engine,actors,properties,orders,vendor,_=setup()
    admin,manager=actors[:2]
    first=request(orders[1].id,vendor,db=db,actor=manager)
    second=m.create_order(m.NewOrder(
        work_order_id=orders[1].id,
        request_key="COST-SECOND-SOURCE-REQUEST-0001",
        vendor_id=vendor.id,sku="FILTER-02",item_name="Small replacement bracket",
        quantity=3,unit_cost_cents=500,
        reason="Physical original stock with a different internal estimated cost",
    ),db=db,current_user=manager)
    for item in (first,second):
        m.decide_order(item["id"],m.Decision(
            approved=True,reason="Independent approval of physical maintenance materials",
        ),db=db,current_user=admin)
    m.receive_materials(first["id"],m.Receipt(
        reference="COST-FIRST-RECEIPT",quantity=5,
        notes="Five physical replacement parts counted at property",
    ),db=db,current_user=manager)
    m.receive_materials(second["id"],m.Receipt(
        reference="COST-SECOND-RECEIPT",quantity=3,
        notes="Three original brackets counted at property",
    ),db=db,current_user=manager)
    original=m.issue_materials(first["id"],m.IssueStock(
        target_work_order_id=orders[1].id,
        reference="COST-FIRST-ISSUE",quantity=2,
        notes="Installed two replacement filters in original work order",
    ),db=db,current_user=manager)
    m.issue_materials(first["id"],m.IssueStock(
        target_work_order_id=orders[0].id,
        reference="COST-OTHER-WORK-ISSUE",quantity=1,
        notes="Installed a third filter for a different same-property job",
    ),db=db,current_user=manager)
    m.issue_materials(second["id"],m.IssueStock(
        target_work_order_id=orders[1].id,
        reference="COST-SECOND-ISSUE",quantity=1,
        notes="Installed one original replacement bracket at property",
    ),db=db,current_user=manager)
    original_id=next(x["id"] for x in original["material_issues"]
                     if x["reference"]=="COST-FIRST-ISSUE")
    return db,engine,actors,properties,orders,first,second,original_id


def test_cost_preview_reconciles_original_prices_per_source_and_independent_reversal():
    db,engine,actors,properties,orders,first,second,issue_id=stock_with_two_original_prices()
    try:
        admin,manager=actors[:2]
        target=orders[1].id
        preview=m.preview_work_order_material_cost(work_order_id=target,
            db=db,current_user=manager)
        assert preview["preview_only"] is True
        assert preview["gl_posted"] is False
        assert preview["tenant_charged"] is False
        assert preview["supplier_invoiced"] is False
        assert preview["total_unposted_cost_cents"]==2*12345+500
        assert [(x["source_order_id"],x["net_used_qty"],x["unposted_cost_cents"])
                for x in preview["source_lines"]] == [
                   (first["id"],2,24690),(second["id"],1,500)]
        other=m.preview_work_order_material_cost(
            work_order_id=orders[0].id,db=db,current_user=admin)
        assert other["total_unposted_cost_cents"]==12345
        assert len(other["source_lines"])==1

        m.reverse_material_issue(first["id"],issue_id,
            m.Correction(reason="Independent inspector confirmed first installation duplicated"),
            db=db,current_user=admin)
        corrected=m.preview_work_order_material_cost(work_order_id=target,
            db=db,current_user=manager)
        assert corrected["total_unposted_cost_cents"]==500
        assert [item["source_order_id"] for item in corrected["source_lines"]]==[second["id"]]
        assert m.preview_work_order_material_cost(work_order_id=orders[0].id,
            db=db,current_user=manager)["total_unposted_cost_cents"]==12345
        assert db.query(GLTransaction).count()==0
    finally:
        db.close();engine.dispose()


def test_cost_preview_is_scoped_nonfinancial_and_rejects_tampered_issue_evidence():
    db,engine,actors,properties,orders,first,second,_=stock_with_two_original_prices()
    try:
        admin,manager,tenant,other_tenant,crew,outsider=actors
        for actor in (tenant,crew,outsider):
            with pytest.raises(HTTPException):
                m.preview_work_order_material_cost(
                    work_order_id=orders[1].id,db=db,current_user=actor)
        for actor in (manager,admin):
            with pytest.raises(HTTPException):
                m.preview_work_order_material_cost(
                    work_order_id=orders[3].id,db=db,current_user=actor)
        with pytest.raises(HTTPException):
            m.preview_work_order_material_cost(
                work_order_id=orders[2].id,db=db,current_user=manager)
        assert m.preview_work_order_material_cost(
            work_order_id=orders[2].id,db=db,current_user=admin
        )["total_unposted_cost_cents"]==0
        event=db.query(AuditLog).filter_by(
            entity_type="maintenance_material_issue",
            action="stock_issued_to_work_order",
        ).first()
        # Simulate a corrupted audit record strictly inside this ORM session:
        # a real UPDATE would (correctly) be rejected by the DB's immutable
        # audit trigger before the reader could inspect the changed payload.
        # Suppress autoflush so the read path sees the forged in-memory value
        # without ever attempting to write or weakening the append-only guard.
        event.new_value='{"unposted_cost_cents":999999999}'
        with db.no_autoflush:
            with pytest.raises(HTTPException) as corrupt:
                m.preview_work_order_material_cost(
                    work_order_id=orders[1].id,db=db,current_user=admin)
        assert corrupt.value.status_code==409
        db.rollback()
        assert m.preview_work_order_material_cost(
            work_order_id=orders[1].id,db=db,current_user=admin
        )["total_unposted_cost_cents"]==25190
    finally:
        db.close();engine.dispose()


def test_revoked_manager_cannot_read_estimated_material_cost():
    db,engine,actors,properties,orders,_,_,_=stock_with_two_original_prices()
    try:
        admin,manager=actors[:2]
        grant=db.query(PropertyAssignment).filter_by(
            property_id=properties[0].id,user_id=manager.id,
            role=UserRole.MANAGER,
        ).one()
        grant.is_active=False
        db.commit()
        with pytest.raises(HTTPException):
            m.preview_work_order_material_cost(
                work_order_id=orders[1].id,db=db,current_user=manager)
        assert m.preview_work_order_material_cost(
            work_order_id=orders[1].id,db=db,current_user=admin
        )["total_unposted_cost_cents"]==25190
    finally:
        db.close();engine.dispose()
