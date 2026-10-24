"""P5-PM-05: recovery reason audit failure cannot leave unproved orders."""
from datetime import date, timedelta

import pytest
from app.models.audit_log import AuditLog
from app.models.preventive_maintenance import PreventiveMaintenanceOccurrence as Occurrence
from app.models.work_order import WorkOrder
from app.services import preventive_maintenance as pm
from test_preventive_maintenance import seeded


def test_failed_review_audit_rolls_back_first_order_and_safe_retry(monkeypatch):
    db, engine, actors, _, units = seeded()
    try:
        admin, manager = actors[:2]
        schedule = pm.create_schedule(
            db, admin, unit_id=units[0].id,
            title="Operator rollback review",
            description="Repair missed maintenance after independent evidence review",
            interval_days=1, next_due_date=date.today(),
        )
        schedule.next_due_date = date.today() - timedelta(days=1)
        db.commit()
        expected = schedule.next_due_date
        original = pm.append_audit_log

        def fail_recovery_audit(*args, **kwargs):
            if kwargs.get("action") == "operator_recovery_initiated":
                raise RuntimeError("recovery evidence store failed")
            return original(*args, **kwargs)

        monkeypatch.setattr(pm, "append_audit_log", fail_recovery_audit)
        with pytest.raises(RuntimeError, match="evidence store failed"):
            pm.catch_up_due(
                db, manager, schedule.id, as_of=date.today(),
                expected_next_due_date=expected,
                recovery_reason="Original evidence checked; recovery authorization documented",
            )
        db.rollback()
        assert db.query(WorkOrder).count() == 0
        assert db.query(Occurrence).count() == 0
        assert db.query(AuditLog).filter_by(
            action="operator_recovery_initiated",
        ).count() == 0

        monkeypatch.setattr(pm, "append_audit_log", original)
        retried = pm.catch_up_due(
            db, manager, schedule.id, as_of=date.today(),
            expected_next_due_date=expected,
            recovery_reason="Original evidence checked; recovery authorization documented",
        )
        assert len(retried["created_work_order_ids"]) == 2
        assert db.query(AuditLog).filter_by(
            action="operator_recovery_initiated",
        ).count() == 1
        assert pm.reconcile_occurrences(db, admin, schedule.id)[
            "verified_occurrences"
        ] == 2
    finally:
        db.close()
        engine.dispose()


def test_second_occurrence_audit_failure_keeps_first_and_recovers_from_new_cursor(monkeypatch):
    db, engine, actors, _, units = seeded()
    try:
        admin, manager = actors[:2]
        schedule = pm.create_schedule(
            db, admin, unit_id=units[0].id,
            title="Partial batch incident recovery",
            description="Recover recorded missed safety inspections without duplicates",
            interval_days=1, next_due_date=date.today(),
        )
        schedule.next_due_date = date.today() - timedelta(days=2)
        db.commit()
        initial = schedule.next_due_date
        original = pm.append_audit_log
        generated = 0

        def fail_second_generated(*args, **kwargs):
            nonlocal generated
            if kwargs.get("entity_type") == "preventive_maintenance_occurrence" and kwargs.get("action") == "generated":
                generated += 1
                if generated == 2:
                    raise RuntimeError("second occurrence storage unavailable")
            return original(*args, **kwargs)

        monkeypatch.setattr(pm, "append_audit_log", fail_second_generated)
        with pytest.raises(RuntimeError, match="second occurrence storage unavailable"):
            pm.catch_up_due(
                db, manager, schedule.id, as_of=date.today(),
                expected_next_due_date=initial,
                recovery_reason="Independent operator inspected complete original evidence",
            )
        db.rollback()
        rows = db.query(Occurrence).filter_by(schedule_id=schedule.id).all()
        assert len(rows) == 1
        original_id = rows[0].work_order_id
        assert rows[0].due_date == initial
        assert db.query(WorkOrder).count() == 1
        assert db.query(AuditLog).filter_by(action="operator_recovery_initiated").count() == 1
        assert pm.reconcile_occurrences(db, admin, schedule.id)["verified_occurrences"] == 1
        with pytest.raises(HTTPException) as stale:
            pm.catch_up_due(
                db, admin, schedule.id, as_of=date.today(),
                expected_next_due_date=initial,
                recovery_reason="Old cursor must never be reused after partial write",
            )
        assert stale.value.status_code == 409

        monkeypatch.setattr(pm, "append_audit_log", original)
        db.refresh(schedule)
        recovery = pm.catch_up_due(
            db, admin, schedule.id, as_of=date.today(),
            expected_next_due_date=schedule.next_due_date,
            recovery_reason="Second reviewer rechecked committed occurrence before resuming",
        )
        assert len(recovery["created_work_order_ids"]) == 2
        assert original_id not in recovery["created_work_order_ids"]
        assert db.query(WorkOrder).count() == 3
        assert db.query(Occurrence).count() == 3
        assert db.query(AuditLog).filter_by(action="operator_recovery_initiated").count() == 2
        assert pm.reconcile_occurrences(db, admin, schedule.id)["verified_occurrences"] == 3
    finally:
        db.close()
        engine.dispose()
