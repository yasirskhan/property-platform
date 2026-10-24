"""P5-PM-05: real two-connection reviewed recovery certification.

A complete original-history review and cursor compare must serialize with the
first durable occurrence. This test does not mock PostgreSQL row locks.
"""
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from threading import Barrier
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

import init_db  # noqa: F401
from app.core.database import Base
from app.models.audit_log import AuditLog
from app.models.preventive_maintenance import PreventiveMaintenanceOccurrence as Occurrence
from app.models.property import Property, PropertyAssignment, Unit
from app.models.user import Organization, User, UserRole
from app.models.work_order import WorkOrder
from app.services import preventive_maintenance as pm

pytestmark = pytest.mark.integration


def test_two_postgres_managers_cannot_accept_the_same_recovery_cursor():
    url = os.environ.get("TEST_DATABASE_URL", "")
    if not url.startswith("postgresql"):
        pytest.skip("Separate real PostgreSQL connections required")
    if "test" not in (make_url(url).database or "").lower():
        pytest.fail("Refuse live database writes outside a named test database")

    engine = create_engine(url, pool_size=4, max_overflow=0)
    try:
        Base.metadata.create_all(engine)
        tag = uuid4().hex[:12]
        with Session(engine, expire_on_commit=False) as db:
            org = Organization(name="Reviewed recovery " + tag, slug="reviewed-pm-" + tag)
            db.add(org)
            db.flush()

            def staff(label):
                actor = User(
                    organization_id=org.id, role=UserRole.MANAGER,
                    first_name="Operator", last_name=label,
                    email=label.lower() + "-" + tag + "@example.com",
                    hashed_password="disabled", is_active=True,
                )
                db.add(actor)
                db.flush()
                return actor

            a = staff("First")
            b = staff("Second")
            prop = Property(
                organization_id=org.id, name="Recovery property " + tag,
                address_line1="100 Recovery Road", city="Cleveland",
                state="OH", zip_code="44113", is_active=True,
            )
            db.add(prop)
            db.flush()
            unit = Unit(property_id=prop.id, unit_number="PM-" + tag, is_active=True)
            db.add(unit)
            db.flush()
            db.add_all([
                PropertyAssignment(
                    property_id=prop.id, user_id=a.id,
                    role=UserRole.MANAGER, is_active=True,
                ),
                PropertyAssignment(
                    property_id=prop.id, user_id=b.id,
                    role=UserRole.MANAGER, is_active=True,
                ),
            ])
            db.commit()
            schedule = pm.create_schedule(
                db, a, unit_id=unit.id, title="Safety backup recovery",
                description="Review overdue safety equipment in two real sessions",
                interval_days=1, next_due_date=date.today(),
            )
            schedule.next_due_date = date.today() - timedelta(days=1)
            db.commit()
            ids = (a.id, b.id)
            schedule_id = schedule.id
            expected = schedule.next_due_date

        gate = Barrier(2)

        def recover(actor_id):
            with Session(engine) as db:
                actor = db.get(User, actor_id)
                gate.wait(timeout=15)
                try:
                    outcome = pm.catch_up_due(
                        db, actor, schedule_id, as_of=date.today(),
                        expected_next_due_date=expected,
                        recovery_reason="Independently reviewed original due evidence",
                        limit=12,
                    )
                    return ("accepted", outcome["created_work_order_ids"])
                except HTTPException as error:
                    db.rollback()
                    return ("rejected", error.status_code)

        with ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(recover, ids[0])
            second = pool.submit(recover, ids[1])
            outcomes = [first.result(timeout=45), second.result(timeout=45)]

        accepted = [result for state, result in outcomes if state == "accepted"]
        rejected = [result for state, result in outcomes if state == "rejected"]
        assert len(accepted) == len(rejected) == 1
        assert rejected == [409]
        assert len(accepted[0]) == 2 and len(set(accepted[0])) == 2

        with Session(engine) as db:
            actor = db.get(User, ids[0])
            occurrences = db.query(Occurrence).filter_by(
                schedule_id=schedule_id,
            ).order_by(Occurrence.due_date).all()
            assert [row.due_date for row in occurrences] == [
                expected, date.today(),
            ]
            assert {row.work_order_id for row in occurrences} == set(accepted[0])
            orders = db.query(WorkOrder).filter(
                WorkOrder.id.in_(accepted[0]),
            ).all()
            assert len(orders) == 2
            assert all(
                order.tenant_id is None and order.permission_to_enter is False
                and order.total_cost is None and order.request_origin == "staff"
                for order in orders
            )
            assert db.query(AuditLog).filter_by(
                entity_type="preventive_maintenance_schedule",
                entity_id=schedule_id, action="operator_recovery_initiated",
            ).count() == 1
            assert pm.reconcile_occurrences(db, actor, schedule_id)[
                "verified_occurrences"
            ] == 2
    finally:
        engine.dispose()
