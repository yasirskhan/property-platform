"""Human dispatch review lifecycle: scope, durable evidence, safe retries."""
import pytest
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from app.models.audit_log import AuditLog
from app.models.maintenance_dispatch_review import MaintenanceDispatchReview
from app.models.property import PropertyAssignment
from app.models.user import UserRole
from app.models.work_order import WorkOrderStatus
from app.routers.maintenance_dispatch_reviews import (
    open_dispatch_review, close_dispatch_review, list_dispatch_reviews,
)
from app.schemas.maintenance_dispatch_review import DispatchReviewOpen, DispatchReviewClose
from test_work_order_queue_filters import _seed_queue


def _open(db, actor, wo, reason="On-call coverage was unavailable for urgent maintenance"):
    return open_dispatch_review(
        wo.id, DispatchReviewOpen(reason=reason), db=db, current_user=actor,
    )


def _close(db, actor, case, reason="Manager reviewed the request and documented manual follow-up"):
    return close_dispatch_review(
        case.id, DispatchReviewClose(resolution_note=reason),
        db=db, current_user=actor,
    )


def test_manual_review_create_exact_retry_close_reopen_and_immutable_evidence():
    db, engine, actors, props, orders = _seed_queue()
    try:
        admin, manager, tenant, _other, crew, outsider = actors
        wo = orders[1]
        row = _open(db, manager, wo)
        assert row.status == "open" and row.externally_notified is False
        assert row.work_order_id == wo.id
        assert _open(db, manager, wo).id == row.id
        assert db.query(MaintenanceDispatchReview).count() == 1
        assert db.query(AuditLog).filter_by(
            entity_type="maintenance_dispatch_review", entity_id=row.id, action="opened",
        ).count() == 1
        assert [x.id for x in list_dispatch_reviews(db=db, current_user=manager)] == [row.id]
        with pytest.raises(HTTPException) as conflict:
            _open(db, admin, wo, reason="Different explanatory review request, conflicting open case")
        assert conflict.value.status_code == 409

        closed = _close(db, admin, row)
        assert closed.status == "closed" and closed.closed_by_user_id == admin.id
        assert closed.externally_notified is False
        assert _close(db, admin, row).id == row.id
        assert list_dispatch_reviews(db=db, current_user=admin) == []
        assert [x.id for x in list_dispatch_reviews(
            db=db, current_user=manager, include_closed=True,
        )] == [row.id]
        assert db.query(AuditLog).filter_by(
            entity_type="maintenance_dispatch_review", entity_id=row.id, action="closed",
        ).count() == 1
        assert db.query(MaintenanceDispatchReview).get(row.id).open_work_order_id is None
        with pytest.raises(HTTPException) as conflict:
            _close(db, admin, row, reason="Another different resolution was already recorded")
        assert conflict.value.status_code == 409
        second = _open(db, admin, wo, reason="Another on-call coverage issue needs independent review")
        assert second.id != row.id
        assert len(list_dispatch_reviews(db=db, current_user=admin, include_closed=True)) == 2
        assert db.query(MaintenanceDispatchReview).filter_by(
            open_work_order_id=wo.id,
        ).count() == 1
    finally:
        db.close(); engine.dispose()


def test_manual_review_denies_tenant_crew_foreign_and_wrong_manager_role():
    db, engine, actors, props, orders = _seed_queue()
    try:
        admin, manager, tenant, _other, crew, outsider = actors
        a, b, c, foreign = orders
        for actor in (tenant, crew, outsider):
            with pytest.raises(HTTPException):
                _open(db, actor, b)
            with pytest.raises(HTTPException):
                list_dispatch_reviews(db=db, current_user=actor) if actor != outsider else _open(db, actor, b)
        row = _open(db, admin, b)
        assert list_dispatch_reviews(db=db, current_user=outsider) == []
        for actor in (tenant, crew, outsider):
            with pytest.raises(HTTPException):
                _close(db, actor, row)
        with pytest.raises(HTTPException):
            _open(db, manager, c)  # No assigned property.
        assigned = db.query(PropertyAssignment).filter_by(
            property_id=props[0].id, user_id=manager.id,
        ).one()
        assigned.role = UserRole.CREW
        db.commit()
        with pytest.raises(HTTPException) as denied:
            _open(db, manager, a)
        assert denied.value.status_code == 403
        assert list_dispatch_reviews(db=db, current_user=manager) == []
        with pytest.raises(HTTPException):
            _close(db, manager, row)
        assigned.role = UserRole.MANAGER
        assigned.is_active = False
        db.commit()
        assert list_dispatch_reviews(db=db, current_user=manager) == []
        admin.is_active = False
        db.commit()
        with pytest.raises(HTTPException):
            _open(db, admin, a)
    finally:
        db.close(); engine.dispose()


def test_review_does_not_approve_resolved_assignment_or_ignore_retired_location():
    db, engine, actors, props, orders = _seed_queue()
    try:
        admin = actors[0]
        a, b, *_ = orders
        a.status = WorkOrderStatus.ASSIGNED
        a.assignment_response = "accepted"
        db.commit()
        with pytest.raises(HTTPException) as closed_work:
            _open(db, admin, a)
        assert closed_work.value.status_code == 409
        row = _open(db, admin, b)
        props[0].is_active = False
        db.commit()
        with pytest.raises(HTTPException) as retired:
            _open(db, admin, a)
        assert retired.value.status_code == 409
        # Closing original historical evidence is allowed even after retirement.
        assert _close(db, admin, row).status == "closed"
    finally:
        db.close(); engine.dispose()


def test_database_rejects_duplicate_open_case_and_corrupt_lifecycle():
    db, engine, actors, props, orders = _seed_queue()
    try:
        admin = actors[0]
        wo = orders[1]
        row = _open(db, admin, wo)
        clone = MaintenanceDispatchReview(
            organization_id=admin.organization_id,
            work_order_id=wo.id, open_work_order_id=wo.id,
            opened_by_user_id=admin.id, status="open", reason="Competing record",
        )
        db.add(clone)
        with pytest.raises(IntegrityError):
            db.flush()
        db.rollback()
        row = db.query(MaintenanceDispatchReview).filter_by(id=row.id).one()
        row.status = "closed"  # Constraint prohibits closed with live open key.
        with pytest.raises(IntegrityError):
            db.flush()
        db.rollback()
    finally:
        db.close(); engine.dispose()
