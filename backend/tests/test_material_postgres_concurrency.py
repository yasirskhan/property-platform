"""PostgreSQL physical-stock issue/approval race certification, P5-PROC-06.

The two workers use independent real database sessions/connections. Their
business operations use the actual HTTP service functions and live DB locks;
there are no mocks of transaction acquisition or the stock audit.
"""
from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import init_db  # noqa: F401
from app.core.database import Base
from app.models.audit_log import AuditLog
from app.models.maintenance_material import MaintenanceMaterialIssue as Issue
from app.models.property import Property, PropertyAssignment, Unit
from app.models.user import Organization, User, UserRole
from app.models.vendor import Vendor
from app.models.work_order import WorkOrder, WorkOrderStatus
from app.routers import maintenance_materials as m

pytestmark = pytest.mark.integration


def test_independent_postgres_issues_and_reversals_preserve_physical_stock():
    url = os.environ.get("TEST_DATABASE_URL", "")
    if not url.startswith("postgresql"):
        pytest.skip("Real PostgreSQL test connections are required")

    engine = create_engine(url, pool_size=5, max_overflow=0)
    try:
        Base.metadata.create_all(engine)
        tag = uuid4().hex[:12]
        with Session(engine) as db:
            org = Organization(name="Stock race " + tag, slug="stock-race-" + tag)
            db.add(org)
            db.flush()

            def new_staff(role: UserRole, label: str) -> User:
                member = User(
                    organization_id=org.id, role=role,
                    first_name="Concurrent", last_name=label,
                    email=label.lower() + "-" + tag + "@example.com",
                    hashed_password="disabled", is_active=True,
                )
                db.add(member)
                db.flush()
                return member

            admin = new_staff(UserRole.ADMIN, "ReviewerAdmin")
            owner = new_staff(UserRole.OWNER, "ReviewerOwner")
            receiver = new_staff(UserRole.MANAGER, "ReceiverOne")
            other = new_staff(UserRole.MANAGER, "ReceiverTwo")
            prop = Property(
                organization_id=org.id, name="Stock race property " + tag,
                address_line1="100 Ledger Lane", city="Cleveland", state="OH",
                zip_code="44113", is_active=True,
            )
            db.add(prop)
            db.flush()
            unit = Unit(property_id=prop.id, unit_number="STOCK-" + tag,
                        bedrooms=1, bathrooms=1, monthly_rent=100)
            vendor = Vendor(
                organization_id=org.id, company_name="Race parts " + tag,
                trade="general", is_active=True,
            )
            db.add_all([unit, vendor])
            db.flush()
            db.add_all([
                PropertyAssignment(
                    property_id=prop.id, user_id=receiver.id,
                    role=UserRole.MANAGER, is_active=True,
                ),
                PropertyAssignment(
                    property_id=prop.id, user_id=other.id,
                    role=UserRole.MANAGER, is_active=True,
                ),
            ])
            wo = WorkOrder(
                property_id=prop.id, unit_id=unit.id, tenant_id=None,
                request_origin="staff", requested_by_user_id=admin.id,
                status=WorkOrderStatus.SUBMITTED,
                title="Replace physical stock filters " + tag,
                description="Controlled PostgreSQL concurrent stock use",
                permission_to_enter=False,
            )
            db.add(wo)
            db.flush()
            ids = {
                "admin": admin.id, "owner": owner.id,
                "receiver": receiver.id, "other": other.id,
                "property": prop.id, "work": wo.id, "vendor": vendor.id,
                "org": org.id,
            }
            db.commit()

        with Session(engine) as db:
            manager = db.get(User, ids["receiver"])
            reviewer = db.get(User, ids["admin"])
            order = m.create_order(m.NewOrder(
                work_order_id=ids["work"],
                request_key="RACE-MATERIAL-ORDER-" + tag.upper(),
                vendor_id=ids["vendor"], sku="RACE-FILTER-01",
                item_name="Maintenance filter stock race",
                quantity=3, unit_cost_cents=1500,
                reason="Independently approved actual physical maintenance filters",
            ), db=db, current_user=manager)
            source_id = order["id"]
            m.decide_order(source_id, m.Decision(
                approved=True,
                reason="Independent administrator approval of stock purchase",
            ), db=db, current_user=reviewer)
            m.receive_materials(source_id, m.Receipt(
                reference="RACE-RECEIVED-3", quantity=3,
                notes="Three physical filter parts independently counted onsite",
            ), db=db, current_user=manager)

        start = Barrier(2)

        def issue(actor_id: int, ref: str):
            with Session(engine) as session:
                actor = session.get(User, actor_id)
                start.wait(timeout=15)
                try:
                    result = m.issue_materials(source_id, m.IssueStock(
                        target_work_order_id=ids["work"], reference=ref,
                        quantity=2,
                        notes="Two filters independently fitted to the work order",
                    ), db=session, current_user=actor)
                    return ("issued", result["net_issued"])
                except HTTPException as exc:
                    session.rollback()
                    return ("denied", exc.status_code)

        with ThreadPoolExecutor(max_workers=2) as pool:
            a = pool.submit(issue, ids["receiver"], "USE-RACE-A")
            b = pool.submit(issue, ids["other"], "USE-RACE-B")
            results = [a.result(timeout=40), b.result(timeout=40)]
        assert sorted(results) == [("denied", 409), ("issued", 2)]

        with Session(engine) as db:
            reviewer = db.get(User, ids["admin"])
            rows = m.list_orders(work_order_id=ids["work"], limit=50,
                                 db=db, current_user=reviewer)
            row = next(x for x in rows if x["id"] == source_id)
            assert row["net_received"] == 3
            assert row["available_stock"] == 1
            assert row["net_issued"] == 2
            issue_id = next(e["id"] for e in row["material_issues"] if e["delta_qty"] > 0)
            assert len(row["material_issues"]) == 1

        start_review = Barrier(2)

        def reverse(actor_id: int):
            with Session(engine) as session:
                actor = session.get(User, actor_id)
                start_review.wait(timeout=15)
                try:
                    result = m.reverse_material_issue(
                        source_id, issue_id,
                        m.Correction(reason="Independent stock correction after audit"),
                        db=session, current_user=actor)
                    return ("reversed", result["net_issued"])
                except HTTPException as exc:
                    session.rollback()
                    return ("denied", exc.status_code)

        with ThreadPoolExecutor(max_workers=2) as pool:
            a = pool.submit(reverse, ids["admin"])
            b = pool.submit(reverse, ids["owner"])
            reviewed = [a.result(timeout=40), b.result(timeout=40)]
        assert sorted(reviewed) == [("denied", 409), ("reversed", 0)]

        with Session(engine) as db:
            owner = db.get(User, ids["owner"])
            current = m.stock_at_property(ids["property"], db=db, current_user=owner)
            assert current[0]["quantity"] == 3
            history = db.query(Issue).filter_by(material_order_id=source_id).all()
            assert len(history) == 2 and sum(x.delta_qty for x in history) == 0
            assert sum(x.reverses_id is not None for x in history) == 1
            assert db.query(AuditLog).filter_by(
                organization_id=ids["org"],
                entity_type="maintenance_material_issue",
                action="stock_issued_to_work_order",
            ).count() == 1
            assert db.query(AuditLog).filter_by(
                organization_id=ids["org"],
                entity_type="maintenance_material_issue",
                action="stock_issue_reversed",
            ).count() == 1

        # A manager who participated in the original real transaction loses
        # all fresh issue rights as soon as their live property grant is revoked.
        with Session(engine) as db:
            grant = db.query(PropertyAssignment).filter_by(
                user_id=ids["receiver"], property_id=ids["property"],
                role=UserRole.MANAGER,
            ).one()
            grant.is_active = False
            db.commit()
        with Session(engine) as db:
            revoked = db.get(User, ids["receiver"])
            with pytest.raises(HTTPException) as blocked:
                m.issue_materials(source_id, m.IssueStock(
                    target_work_order_id=ids["work"], reference="REVOKED-ISSUE",
                    quantity=1, notes="Revoked property manager cannot allocate stock",
                ), db=db, current_user=revoked)
            assert blocked.value.status_code in (403, 404)
            db.rollback()
            assert db.query(Issue).filter_by(material_order_id=source_id).count() == 2
    finally:
        engine.dispose()
