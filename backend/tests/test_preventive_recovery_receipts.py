"""P5-PM-05: every reviewed recovery commit has original bound receipt evidence."""
from datetime import date,timedelta
import pytest
from fastapi import HTTPException
from app.models.audit_log import AuditLog
from app.models.preventive_maintenance import PreventiveMaintenanceOccurrence as Occurrence
from app.models.work_order import WorkOrder
from app.services import preventive_maintenance as pm
from test_preventive_maintenance import seeded


def test_reviewed_batch_receipt_maps_every_original_and_replays_read_only():
    db,engine,actors,_,units=seeded()
    try:
        admin,manager,tenant,outsider=actors
        row=pm.create_schedule(db,admin,unit_id=units[0].id,
            title="Reviewed full receipt chain",
            description="Run independently verified service recovery and examine immutable provenance",
            interval_days=1,next_due_date=date.today())
        row.next_due_date=date.today()-timedelta(days=2)
        db.commit()
        start=row.next_due_date
        reason="Original work order evidence inspected before durable backlog repair"
        result=pm.catch_up_due(db,manager,row.id,as_of=date.today(),
            expected_next_due_date=start,recovery_reason=reason)
        assert len(result["created_work_order_ids"])==3
        receipts=pm.recovery_receipts(db,manager,row.id)
        assert len(receipts)==1
        receipt=receipts[0]
        assert receipt["reason"]==reason
        assert receipt["operator_user_id"]==manager.id
        assert receipt["root_work_order_id"]==result["created_work_order_ids"][0]
        assert [item["work_order_id"] for item in receipt["created_work_orders"]]==result["created_work_order_ids"]
        assert db.query(AuditLog).filter_by(action="operator_recovery_initiated").count()==1
        assert db.query(AuditLog).filter_by(action="operator_recovery_continued").count()==2
        before=db.query(AuditLog).count()
        assert pm.recovery_receipts(db,admin,row.id)==receipts
        assert db.query(AuditLog).count()==before
        for actor in (tenant,outsider):
            with pytest.raises(HTTPException):
                pm.recovery_receipts(db,actor,row.id)
        assert db.query(WorkOrder).count()==3
    finally:
        db.close();engine.dispose()


def test_recovery_receipt_does_not_certify_changed_original_pointer():
    db,engine,actors,_,units=seeded()
    try:
        admin,manager,tenant,outsider=actors
        row=pm.create_schedule(db,admin,unit_id=units[0].id,
            title="Receipt corruption guard",
            description="Reject forged original reference rather than show private identifiers",
            interval_days=1,next_due_date=date.today())
        pm.catch_up_due(db,admin,row.id,as_of=date.today(),
            expected_next_due_date=row.next_due_date,
            recovery_reason="Keep a valid original before corrupt link simulation")
        event=db.query(AuditLog).filter_by(action="operator_recovery_initiated").one()
        event.new_value='{"first_work_order_id":999999,"root_work_order_id":999999,"work_order_id":999999,"due_date":"2000-01-01","reason":"Corrupt"}'
        with db.no_autoflush:
            with pytest.raises(HTTPException) as denied:
                pm.recovery_receipts(db,manager,row.id)
        assert denied.value.status_code==409
        db.rollback()
    finally:
        db.close();engine.dispose()


def test_recovery_receipt_rejects_forged_foreign_operator_identity():
    db,engine,actors,_,units=seeded()
    try:
        admin,manager,_,outsider=actors
        row=pm.create_schedule(db,admin,unit_id=units[0].id,
            title="Operator identity evidence",
            description="Verify original reviewer belongs to the actual service organization",
            interval_days=1,next_due_date=date.today())
        pm.catch_up_due(db,manager,row.id,as_of=date.today(),
            expected_next_due_date=row.next_due_date,
            recovery_reason="Operator original identity and service reason must be retained")
        entry=db.query(AuditLog).filter_by(action="operator_recovery_initiated").one()
        entry.user_id=outsider.id
        with db.no_autoflush:
            with pytest.raises(HTTPException) as wrong:
                pm.recovery_receipts(db,admin,row.id)
        assert wrong.value.status_code==409
        db.rollback()
        assert len(pm.recovery_receipts(db,admin,row.id))==1
    finally:
        db.close();engine.dispose()
