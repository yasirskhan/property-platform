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
    # Production deliberately disallows creating schedules in the past.
    # Create a valid schedule, then simulate historical delayed worker runs
    # by moving the persisted cursor, as the existing PM backlog tests do.
    row = pm.create_schedule(
        db, admin, unit_id=unit_id,
        title="Daily recovery audit check",
        description="Review original scheduled repair evidence without changes",
        interval_days=1, next_due_date=date.today(),
    )
    if days_ago:
        row.next_due_date = date.today()-timedelta(days=days_ago)
        db.commit()
    return row


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


def test_reviewed_recovery_requires_fresh_cursor_and_audits_original_order():
    db, engine, actors, _, units = seeded()
    try:
        admin, manager, tenant, outsider = actors
        schedule = _make_schedule(db, admin, units[0].id, days_ago=2)
        expected = schedule.next_due_date
        reason = "Operator reviewed original evidence and overdue maintenance"
        for rejected in (tenant, outsider):
            with pytest.raises(HTTPException):
                pm.catch_up_due(db, rejected, schedule.id, as_of=date.today(),
                    expected_next_due_date=expected, recovery_reason=reason)
        with pytest.raises(HTTPException) as invalid:
            pm.catch_up_due(db, manager, schedule.id, as_of=date.today(),
                expected_next_due_date=expected, recovery_reason="short")
        assert invalid.value.status_code == 422
        with pytest.raises(HTTPException) as stale:
            pm.catch_up_due(db, manager, schedule.id, as_of=date.today(),
                expected_next_due_date=expected + timedelta(days=1), recovery_reason=reason)
        assert stale.value.status_code == 409
        assert db.query(WorkOrder).count() == 0
        result = pm.catch_up_due(db, manager, schedule.id, as_of=date.today(),
            expected_next_due_date=expected, recovery_reason=reason)
        assert len(result["created_work_order_ids"]) == 3
        audits = db.query(AuditLog).filter_by(entity_type="preventive_maintenance_schedule",
            entity_id=schedule.id, action="operator_recovery_initiated").all()
        assert len(audits) == 1
        evidence = __import__("json").loads(audits[0].new_value)
        assert evidence["reason"] == reason
        assert evidence["first_work_order_id"] == result["created_work_order_ids"][0]
        assert pm.reconcile_occurrences(db, admin, schedule.id)["verified_occurrences"] == 3
        with pytest.raises(HTTPException) as replay:
            pm.catch_up_due(db, manager, schedule.id, as_of=date.today(),
                expected_next_due_date=expected, recovery_reason=reason)
        assert replay.value.status_code == 409
        db.refresh(schedule)
        empty = pm.catch_up_due(db, admin, schedule.id, as_of=date.today(),
            expected_next_due_date=schedule.next_due_date, recovery_reason=reason)
        assert empty["created_work_order_ids"] == []
        assert db.query(AuditLog).filter_by(action="operator_recovery_initiated").count() == 1
        assert db.query(WorkOrder).count() == 3
    finally:
        db.close(); engine.dispose()


def test_reviewed_recovery_rejects_hidden_foreign_original():
    db, engine, actors, _, units = seeded()
    try:
        admin, _, _, outsider = actors
        schedule = _make_schedule(db, admin, units[0].id)
        order, _ = pm.generate_due(db, admin, schedule.id, as_of=date.today())
        occurrence = db.query(Occurrence).filter_by(work_order_id=order.id).one()
        occurrence.organization_id = outsider.organization_id
        db.commit()
        with pytest.raises(HTTPException) as bad:
            pm.catch_up_due(db, admin, schedule.id, as_of=date.today(),
                expected_next_due_date=schedule.next_due_date,
                recovery_reason="Refuse incomplete original independent evidence")
        assert bad.value.status_code == 409
        assert db.query(WorkOrder).count() == 1
        assert db.query(AuditLog).filter_by(action="operator_recovery_initiated").count() == 0
    finally:
        db.close(); engine.dispose()


def test_recovery_reconciliation_detects_orphan_append_only_original_audit():
    """A lost occurrence must not be hidden simply because history has fewer rows."""
    from app.services.audit import append_audit_log
    db, engine, actors, _, units = seeded()
    try:
        admin = actors[0]
        schedule = _make_schedule(db, admin, units[0].id, days_ago=0)
        work, created = pm.generate_due(db, admin, schedule.id, as_of=date.today())
        assert created
        assert pm.reconcile_occurrences(db, admin, schedule.id)["verified_occurrences"] == 1
        append_audit_log(
            db, entity_type="preventive_maintenance_occurrence",
            entity_id=schedule.id, organization_id=admin.organization_id,
            user_id=admin.id, action="generated",
            new_value={"schedule_id": schedule.id,
                       "due_date": (date.today() - timedelta(days=1)).isoformat(),
                       "work_order_id": work.id},
        )
        db.flush()
        with pytest.raises(HTTPException) as bad:
            pm.reconcile_occurrences(db, admin, schedule.id)
        assert bad.value.status_code == 409
        db.rollback()
        assert pm.reconcile_occurrences(db, admin, schedule.id)["verified_occurrences"] == 1
    finally:
        db.close(); engine.dispose()


def test_recovery_reconciliation_rejects_foreign_org_creation_proof():
    """Do not certify cross-organization audit provenance for a local schedule."""
    from app.services.audit import append_audit_log
    db, engine, actors, _, units = seeded()
    try:
        admin, _, _, outsider = actors
        schedule = _make_schedule(db, admin, units[0].id, days_ago=0)
        work, created = pm.generate_due(db, admin, schedule.id, as_of=date.today())
        assert created
        append_audit_log(
            db, entity_type="preventive_maintenance_occurrence",
            entity_id=schedule.id, organization_id=outsider.organization_id,
            user_id=outsider.id, action="generated",
            new_value={"schedule_id": schedule.id,
                       "due_date": date.today().isoformat(),
                       "work_order_id": work.id},
        )
        db.flush()
        with pytest.raises(HTTPException) as bad:
            pm.reconcile_occurrences(db, admin, schedule.id)
        assert bad.value.status_code == 409
    finally:
        db.rollback()
        db.close(); engine.dispose()
