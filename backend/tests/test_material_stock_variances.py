"""P5-PROC-06 immutable, independently reviewed physical discrepancy regression."""
import pytest
from fastapi import HTTPException
from app.models.user import User, UserRole
from app.models.audit_log import AuditLog
from app.models.gl_transaction import GLTransaction
from app.models.maintenance_material import (
    MaintenanceMaterialVariance as V,
    MaintenanceMaterialVarianceDecision as D,
    MaintenanceMaterialVarianceRestoration as R,
)
from app.routers import maintenance_materials as m
from test_maintenance_materials import setup, request


def seed_stock():
    db, engine, actors, properties, orders, vendor, _ = setup()
    admin, manager = actors[:2]
    owner = User(organization_id=admin.organization_id, role=UserRole.OWNER,
                 first_name="Material", last_name="RecountOwner",
                 email="material-recount-owner@example.com",
                 hashed_password="disabled", is_active=True)
    db.add(owner)
    db.commit()
    row=request(orders[1].id, vendor, db=db, actor=manager)
    m.decide_order(row["id"], m.Decision(
        approved=True,reason="Independent authorized stock purchase review"),
        db=db,current_user=admin)
    m.receive_materials(row["id"],m.Receipt(
        reference="COUNT-RECEIPT-5",quantity=5,
        notes="Five stocked parts counted in person onsite"),
        db=db,current_user=manager)
    return db,engine,actors,properties,orders,row,owner


def test_recount_lifecycle_replay_failure_isolation_conservation_and_recovery(monkeypatch):
    db,engine,actors,properties,orders,row,owner=seed_stock()
    try:
        admin,manager,tenant,_,_,outsider=actors
        body=m.StockVarianceInput(
            request_key="VARIANCE-SHORT-COUNT-0001",quantity=2,
            reason="Physical shelf recount found two approved filter parts missing")
        for actor in (tenant,outsider):
            with pytest.raises(HTTPException):
                m.report_stock_variance(row["id"],body,db=db,current_user=actor)
        original=m.append_audit_log
        def failed(*args,**kwargs):
            raise RuntimeError("simulated variance evidence storage failure")
        monkeypatch.setattr(m,"append_audit_log",failed)
        with pytest.raises(RuntimeError,match="variance evidence"):
            m.report_stock_variance(row["id"],body,db=db,current_user=manager)
        db.rollback()
        monkeypatch.setattr(m,"append_audit_log",original)
        assert db.query(V).count()==0
        draft=m.report_stock_variance(row["id"],body,db=db,current_user=manager)
        request_id=draft["stock_variances"][0]["id"]
        assert draft["net_missing"]==0 and draft["available_stock"]==5
        again=m.report_stock_variance(row["id"],body,db=db,current_user=manager)
        assert again["stock_variances"]==draft["stock_variances"]
        with pytest.raises(HTTPException):
            m.report_stock_variance(row["id"],m.StockVarianceInput(
                request_key=body.request_key,quantity=3,reason=body.reason),
                db=db,current_user=manager)
        with pytest.raises(HTTPException):
            m.review_stock_variance(row["id"],request_id,
                m.Decision(approved=True,reason="Cannot self approve witnessed loss"),
                db=db,current_user=manager)
        approved=m.review_stock_variance(row["id"],request_id,
            m.Decision(approved=True,
                       reason="Independent recount confirms two missing units"),
            db=db,current_user=admin)
        assert approved["net_missing"]==2 and approved["available_stock"]==3
        assert m.stock_at_property(properties[0].id,db=db,current_user=owner)[0]["quantity"]==3
        with pytest.raises(HTTPException):
            m.issue_materials(row["id"],m.IssueStock(
                target_work_order_id=orders[1].id,reference="TOO-MUCH-STOCK",
                quantity=4,notes="Cannot issue four when two are missing"),
                db=db,current_user=manager)
        with pytest.raises(HTTPException):
            m.reverse_receipt(row["id"],approved["physical_receipts"][0]["id"],
                m.Correction(reason="Cannot reverse receipt after approved loss"),
                db=db,current_user=admin)
        with pytest.raises(HTTPException):
            m.restore_stock_variance(row["id"],request_id,
                m.Correction(reason="Prior approval is not independent restoration"),
                db=db,current_user=admin)
        assert m.review_stock_variance(row["id"],request_id,
            m.Decision(approved=True,reason="Independent recount confirms two missing units"),
            db=db,current_user=admin)["net_missing"]==2
        restored=m.restore_stock_variance(row["id"],request_id,
            m.Correction(reason="Separate owner recovered both missing filters onsite"),
            db=db,current_user=owner)
        assert restored["net_missing"]==0 and restored["available_stock"]==5
        assert restored["stock_variances"][0]["status"]=="RESTORED"
        assert m.restore_stock_variance(row["id"],request_id,
            m.Correction(reason="Separate owner recovered both missing filters onsite"),
            db=db,current_user=owner)["available_stock"]==5
        assert db.query(V).count()==1 and db.query(D).count()==1 and db.query(R).count()==1
        assert db.query(GLTransaction).count()==0
        for action in ("physical_variance_requested","physical_variance_reviewed",
                       "physical_variance_restored"):
            assert db.query(AuditLog).filter_by(
                entity_type="maintenance_material_variance",action=action).count()==1
    finally:
        db.close();engine.dispose()


def test_intervening_stock_consumption_denies_stale_shortage_approval():
    db,engine,actors,_,orders,row,owner=seed_stock()
    try:
        admin,manager=actors[:2]
        proposed=m.report_stock_variance(row["id"],m.StockVarianceInput(
            request_key="STALE-MISSING-COUNT-0001",quantity=4,
            reason="Observed four units missing before new maintenance work"),
            db=db,current_user=manager)
        m.issue_materials(row["id"],m.IssueStock(
            target_work_order_id=orders[1].id,reference="ACTUAL-USE-2",
            quantity=2,notes="Installed two legitimate filters during maintenance"),
            db=db,current_user=admin)
        key=proposed["stock_variances"][0]["id"]
        with pytest.raises(HTTPException) as stale:
            m.review_stock_variance(row["id"],key,m.Decision(
                approved=True,reason="Cannot approve stock already used"),
                db=db,current_user=owner)
        assert stale.value.status_code==409
        denied=m.review_stock_variance(row["id"],key,m.Decision(
            approved=False,reason="Recount required after stock consumption"),
            db=db,current_user=owner)
        assert denied["available_stock"]==3 and denied["net_missing"]==0
    finally:
        db.close();engine.dispose()
