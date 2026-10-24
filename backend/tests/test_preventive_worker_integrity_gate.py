"""Full-history gate for daily/manual preventive generation and staff recovery health."""
from datetime import date, timedelta
import json

import pytest
from fastapi import HTTPException

from app.models.audit_log import AuditLog
from app.models.preventive_maintenance import PreventiveMaintenanceOccurrence as Occurrence
from app.models.work_order import WorkOrder
from app.services import preventive_maintenance as pm
from test_preventive_maintenance import seeded


def _due_with_two_originals(db, admin, unit):
    schedule = pm.create_schedule(
        db, admin, unit_id=unit.id, title="Preventive worker original integrity",
        description="Check emergency equipment and verify original work history",
        interval_days=1, next_due_date=date.today(),
    )
    schedule.next_due_date = date.today() - timedelta(days=2)
    db.commit()
    first, fresh = pm.generate_due(db, admin, schedule.id, as_of=date.today())
    assert fresh
    second, fresh = pm.generate_due(db, admin, schedule.id, as_of=date.today())
    assert fresh
    return schedule, first, second


def test_worker_and_manual_generation_refuse_earlier_foreign_original_but_health_explains():
    db, engine, actors, _, units = seeded()
    try:
        admin, manager, tenant, outsider = actors
        schedule, first, second = _due_with_two_originals(db, admin, units[0])
        earlier = db.query(Occurrence).filter_by(work_order_id=first.id).one()
        earlier.organization_id = outsider.organization_id
        db.commit()
        # The latest original remains valid; the historical first original
        # must not become invisible to the worker or the staff health inbox.
        assert pm.list_occurrences(db, admin, schedule.id)[0].work_order_id == second.id
        health = pm.execution_status(db, admin, schedule.id)
        assert health["status"] == "blocked"
        assert health["block_reason"] == "ORIGINAL_EVIDENCE_INTEGRITY_FAILURE"
        assert health["due"] is False
        assert pm.batch_execution_health(db, admin, [schedule.id])[0] == health
        for caller in (admin, manager):
            with pytest.raises(HTTPException) as denied:
                pm.generate_due(db, caller, schedule.id, as_of=date.today())
            assert denied.value.status_code == 409
        result = pm.sweep_due(db, as_of=date.today())
        assert result["created"] == 0 and result["skipped"] >= 1
        assert db.query(WorkOrder).count() == 2
        for caller in (tenant, outsider):
            with pytest.raises(HTTPException):
                pm.execution_status(db, caller, schedule.id)
        earlier.organization_id = admin.organization_id
        db.commit()
        assert pm.execution_status(db, admin, schedule.id)["status"] == "ready"
        result = pm.sweep_due(db, as_of=date.today())
        assert result["created"] == 1
        assert db.query(WorkOrder).count() == 3
        assert all(order.tenant_id is None and not order.permission_to_enter
                   for order in db.query(WorkOrder).all())
    finally:
        db.close()
        engine.dispose()


def test_generation_and_health_reject_orphan_original_audit_without_side_effects():
    from app.services.audit import append_audit_log
    db, engine, actors, _, units = seeded()
    try:
        admin = actors[0]
        schedule = pm.create_schedule(
            db, admin, unit_id=units[0].id,
            title="Audit reconstruction smoke check",
            description="Review due scheduling and prevent unverified restoration",
            interval_days=1, next_due_date=date.today(),
        )
        schedule.next_due_date = date.today() - timedelta(days=1)
        db.commit()
        first, fresh = pm.generate_due(db, admin, schedule.id, as_of=date.today())
        assert fresh
        append_audit_log(
            db, organization_id=admin.organization_id, user_id=admin.id,
            entity_type="preventive_maintenance_occurrence", entity_id=schedule.id,
            action="generated",
            new_value={"schedule_id": schedule.id,
                       "due_date": date.today().isoformat(),
                       "work_order_id": first.id},
        )
        db.commit()
        health = pm.execution_status(db, admin, schedule.id)
        assert health["status"] == "blocked"
        assert health["block_reason"] == "ORIGINAL_EVIDENCE_INTEGRITY_FAILURE"
        with pytest.raises(HTTPException) as denied:
            pm.generate_due(db, admin, schedule.id, as_of=date.today())
        assert denied.value.status_code == 409
        assert pm.sweep_due(db, as_of=date.today())["created"] == 0
        assert db.query(WorkOrder).count() == 1
    finally:
        db.close()
        engine.dispose()
