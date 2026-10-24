"""P5-PM-05 full original-occurrence recovery review: no invisible corruption."""
from datetime import date, timedelta
import pytest
from fastapi import HTTPException
from app.models.audit_log import AuditLog
from app.models.preventive_maintenance import PreventiveMaintenanceOccurrence as Occurrence
from app.models.work_order import WorkOrder
from app.services import preventive_maintenance as pm
from test_preventive_maintenance import seeded


def _make_schedule(db, admin, unit_id, *, days_ago=1):
    return pm.create_schedule(
        db, admin, unit_id=unit_id,
        title="Daily recovery audit check",
        description="Review original scheduled repair evidence without changes",
        interval_days=1, next_due_date=date.today()-timedelta(days=days_ago),
    )


def test_full_reconciliation_of_original_orders_is_read_only_and_bounded():
    db,engine,actors,properties,units=seeded()
    try:
        admin,manager,tenant,outsider=actors
        schedule=_make_schedule(db,admin,units[0].id)
        first,created=pm.generate_due(db,manager,schedule.id,as_of=date.today())
        assert created
        second,created=pm.generate_due(db,manager,schedule.id,as_of=date.today())
        assert created and first.id!=second.id
        before=db.query(AuditLog).count()
        for viewer in (admin,manager):
            result=pm.reconcile_occurrences(db,viewer,schedule.id)
            assert result["integrity_status"]=="VERIFIED"
            assert result["verified_occurrences"]==2
            assert result["latest_due_date"]==date.today()
            assert result["latest_work_order_id"]==second.id
            assert result["next_due_date"]==date.today()+timedelta(days=1)
            assert result["read_only"] is True
            assert result["work_orders_created"]==0
            assert result["automatic_dispatch"] is False
            assert result["financial_posted"] is False
        assert db.query(AuditLog).count()==before
        assert db.query(WorkOrder).count()==2
        for actor in (tenant,outsider):
            with pytest.raises(HTTPException):
                pm.reconcile_occurrences(db,actor,schedule.id)
    finally:
        db.close();engine.dispose()


def test_reconciliation_rejects_cross_org_occurrence_without_hidden_history():
    db,engine,actors,properties,units=seeded()
    try:
        admin,manager,tenant,outsider=actors
        schedule=_make_schedule(db,admin,units[0].id)
        order,_=pm.generate_due(db,admin,schedule.id,as_of=date.today())
        occurrence=db.query(Occurrence).filter_by(work_order_id=order.id).one()
        occurrence.organization_id=outsider.organization_id
        db.commit()
        assert pm.list_occurrences(db,admin,schedule.id)==[]
        with pytest.raises(HTTPException) as blocked:
            pm.reconcile_occurrences(db,admin,schedule.id)
        assert blocked.value.status_code==409
        assert db.query(WorkOrder).count()==1
    finally:
        db.close();engine.dispose()


def test_reconciliation_does_not_certify_foreign_repointed_order():
    db,engine,actors,properties,units=seeded()
    try:
        admin,manager,tenant,outsider=actors
        schedule=_make_schedule(db,admin,units[0].id)
        order,_=pm.generate_due(db,admin,schedule.id,as_of=date.today())
        order.unit_id=units[2].id
        order.property_id=properties[2].id
        db.commit()
        assert pm.list_occurrences(db,admin,schedule.id)==[]
        with pytest.raises(HTTPException) as blocked:
            pm.reconcile_occurrences(db,admin,schedule.id)
        assert blocked.value.status_code==409
    finally:
        db.close();engine.dispose()


def test_reconciliation_rejects_missing_original_occurrence_creation_proof():
    db,engine,actors,properties,units=seeded()
    try:
        admin,manager,tenant,outsider=actors
        schedule=_make_schedule(db,admin,units[0].id)
        work,_=pm.generate_due(db,admin,schedule.id,as_of=date.today())
        generated=db.query(AuditLog).filter_by(
            organization_id=admin.organization_id,
            entity_type="preventive_maintenance_occurrence",entity_id=schedule.id,
            action="generated",
        ).one()
        # A real DB update is forbidden: simulate a forged audit only inside
        # the current session, without flushing or dropping integrity triggers.
        generated.new_value='{"schedule_id":0,"work_order_id":0}'
        with db.no_autoflush:
            with pytest.raises(HTTPException) as blocked:
                pm.reconcile_occurrences(db,manager,schedule.id)
        assert blocked.value.status_code==409
        db.rollback()
        assert pm.reconcile_occurrences(db,admin,schedule.id)["latest_work_order_id"]==work.id
    finally:
        db.close();engine.dispose()


def test_reconciliation_flags_recovery_cursor_rewind_without_creating_order():
    db,engine,actors,properties,units=seeded()
    try:
        admin=actors[0]
        schedule=_make_schedule(db,admin,units[0].id)
        work,_=pm.generate_due(db,admin,schedule.id,as_of=date.today())
        schedule.next_due_date=date.today()-timedelta(days=1)
        db.commit()
        with pytest.raises(HTTPException) as blocked:
            pm.reconcile_occurrences(db,admin,schedule.id)
        assert blocked.value.status_code==409
        assert db.query(WorkOrder).count()==1
    finally:
        db.close();engine.dispose()
