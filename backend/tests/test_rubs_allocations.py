"""Phase 4.9 RUBs allocation rules remain explicit, versioned and non-posting."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi import HTTPException, Response
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import init_db  # noqa: F401
from app.core.database import Base
from app.models.charge import Charge
from app.models.gl_transaction import GLTransaction
from app.models.property import Property, PropertyAssignment, Unit
from app.models.user import Organization, User, UserRole
from app.models.utility import (
    PaidBy,
    PropertyUtility,
    UtilityAllocationRuleRevision,
    UtilityAllocationSnapshot,
    UtilityBill,
    UtilityType,
)
from app.routers import rubs_readiness as api
from app.schemas.utility import (
    AllocationPreviewRequest,
    AllocationRuleAuthorize,
    AllocationRuleCreate,
    AllocationUnitInput,
    AllocationSnapshotSave,
    TrueUpPreviewRequest,
    TrueUpUnitWeight,
)


def _db():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, expire_on_commit=False)(), engine


@pytest.fixture(autouse=True)
def gates(monkeypatch):
    monkeypatch.setattr(api, "permission_allows_user", lambda *a, **kw: True)
    monkeypatch.setattr(
        api,
        "resolve_customer_features",
        lambda *a, **kw: [SimpleNamespace(key=api.FEATURE_KEY, allowed=True)],
    )


def _seed(db):
    org = Organization(name="RUBs Allocation", slug="rubs-allocation")
    other_org = Organization(name="RUBs Foreign", slug="rubs-foreign")
    db.add_all([org, other_org])
    db.flush()

    admin = User(
        organization_id=org.id,
        role=UserRole.ADMIN,
        first_name="Alloc",
        last_name="Admin",
        email="alloc-admin@example.com",
        hashed_password="x",
        is_active=True,
    )
    manager = User(
        organization_id=org.id,
        role=UserRole.MANAGER,
        first_name="Alloc",
        last_name="Manager",
        email="alloc-manager@example.com",
        hashed_password="x",
        is_active=True,
    )
    db.add_all([admin, manager])
    db.flush()

    prop = Property(
        organization_id=org.id,
        name="Allocation Property",
        address_line1="1 Ratio Ave",
        city="Cleveland",
        state="OH",
        zip_code="44113",
        is_active=True,
    )
    foreign_prop = Property(
        organization_id=other_org.id,
        name="Foreign Property",
        address_line1="2 Ratio Ave",
        city="Cleveland",
        state="OH",
        zip_code="44113",
        is_active=True,
    )
    db.add_all([prop, foreign_prop])
    db.flush()
    db.add(
        PropertyAssignment(
            property_id=prop.id,
            user_id=manager.id,
            role=UserRole.MANAGER,
            is_active=True,
        )
    )

    unit_a = Unit(
        property_id=prop.id,
        unit_number="A",
        bedrooms=1,
        bathrooms=1,
        square_feet=600,
        monthly_rent=Decimal("1000"),
        is_active=True,
    )
    unit_b = Unit(
        property_id=prop.id,
        unit_number="B",
        bedrooms=1,
        bathrooms=1,
        square_feet=400,
        monthly_rent=Decimal("1000"),
        is_active=True,
    )
    foreign_unit = Unit(
        property_id=foreign_prop.id,
        unit_number="X",
        bedrooms=1,
        bathrooms=1,
        square_feet=500,
        monthly_rent=Decimal("1000"),
        is_active=True,
    )
    db.add_all([unit_a, unit_b, foreign_unit])
    db.flush()

    utility = PropertyUtility(
        property_id=prop.id,
        utility_type=UtilityType.WATER,
        company_name="Shared Water",
        paid_by=PaidBy.SHARED,
        is_active=True,
    )
    db.add(utility)
    db.flush()
    bill = UtilityBill(
        utility_id=utility.id,
        billing_period_start=date(2026, 9, 1),
        billing_period_end=date(2026, 9, 30),
        amount=Decimal("100.01"),
    )
    db.add(bill)
    db.commit()
    return admin, manager, prop, utility, bill, unit_a, unit_b, foreign_unit


def test_square_feet_rule_requires_authorization_and_preview_is_finance_neutral():
    db, engine = _db()
    try:
        admin, manager, prop, utility, bill, unit_a, unit_b, _ = _seed(db)
        payload = AllocationRuleCreate(
            basis="SQUARE_FEET",
            effective_date=date(2026, 9, 1),
            units=[
                AllocationUnitInput(unit_id=unit_a.id),
                AllocationUnitInput(unit_id=unit_b.id),
            ],
            request_key="allocation-rule-001",
        )
        draft = api.create_allocation_rule(
            prop.id, utility.id, payload, db=db, current_user=manager
        )
        assert draft["revision_number"] == 1
        assert draft["status"] == "DRAFT"
        assert draft["is_authorized"] is False

        with pytest.raises(HTTPException) as exc:
            api.preview_allocation(
                prop.id,
                utility.id,
                AllocationPreviewRequest(
                    rule_revision_id=draft["id"],
                    bill_id=bill.id,
                ),
                Response(),
                db=db,
                current_user=manager,
            )
        assert exc.value.status_code == 409

        authorized = api.authorize_allocation_rule(
            prop.id,
            utility.id,
            draft["id"],
            AllocationRuleAuthorize(request_key="authorize-rule-001"),
            db=db,
            current_user=admin,
        )
        assert authorized["is_authorized"] is True

        preview = api.preview_allocation(
            prop.id,
            utility.id,
            AllocationPreviewRequest(
                rule_revision_id=draft["id"],
                bill_id=bill.id,
            ),
            Response(),
            db=db,
            current_user=manager,
        )
        assert preview["allocated_total"] == Decimal("100.01")
        assert [
            (item["unit_id"], item["amount"]) for item in preview["items"]
        ] == [
            (unit_a.id, Decimal("60.01")),
            (unit_b.id, Decimal("40.00")),
        ]
        assert preview["posting_created"] is False
        assert db.query(Charge).count() == 0
        assert db.query(GLTransaction).count() == 0

        snapshot = api.save_allocation_snapshot(
            prop.id,
            utility.id,
            AllocationSnapshotSave(
                rule_revision_id=draft["id"],
                bill_id=bill.id,
                request_key="allocation-snapshot-001",
            ),
            db=db,
            current_user=manager,
        )
        replay = api.save_allocation_snapshot(
            prop.id,
            utility.id,
            AllocationSnapshotSave(
                rule_revision_id=draft["id"],
                bill_id=bill.id,
                request_key="allocation-snapshot-001",
            ),
            db=db,
            current_user=manager,
        )
        assert replay["id"] == snapshot["id"]
        assert db.query(UtilityAllocationSnapshot).count() == 1

        true_up = api.preview_year_end_true_up(
            prop.id,
            utility.id,
            TrueUpPreviewRequest(
                period_start=date(2026, 9, 1),
                period_end=date(2026, 9, 30),
                snapshot_ids=[snapshot["id"]],
                actual_total=Decimal("110.01"),
                unit_weights=[
                    TrueUpUnitWeight(unit_id=unit_a.id, weight=Decimal("600")),
                    TrueUpUnitWeight(unit_id=unit_b.id, weight=Decimal("400")),
                ],
            ),
            Response(),
            db=db,
            current_user=admin,
        )
        assert true_up["prior_allocated_total"] == Decimal("100.01")
        assert true_up["actual_total"] == Decimal("110.01")
        assert true_up["adjustment_total"] == Decimal("10.00")
        assert [
            (item["unit_id"], item["difference"]) for item in true_up["items"]
        ] == [
            (unit_a.id, Decimal("6.00")),
            (unit_b.id, Decimal("4.00")),
        ]
        assert true_up["posting_created"] is False
        assert db.query(Charge).count() == 0
        assert db.query(GLTransaction).count() == 0

        second_bill = UtilityBill(
            utility_id=utility.id,
            billing_period_start=date(2026, 10, 1),
            billing_period_end=date(2026, 10, 31),
            amount=Decimal("80.00"),
        )
        db.add(second_bill)
        db.commit()
        with pytest.raises(HTTPException) as exc:
            api.save_allocation_snapshot(
                prop.id,
                utility.id,
                AllocationSnapshotSave(
                    rule_revision_id=draft["id"],
                    bill_id=second_bill.id,
                    request_key="allocation-snapshot-001",
                ),
                db=db,
                current_user=admin,
            )
        assert exc.value.status_code == 409

        second = api.create_allocation_rule(
            prop.id,
            utility.id,
            payload.model_copy(update={"request_key": "allocation-rule-002"}),
            db=db,
            current_user=admin,
        )
        assert second["revision_number"] == 2
        assert second["is_authorized"] is False
        assert db.query(UtilityAllocationRuleRevision).count() == 2
    finally:
        db.close()
        engine.dispose()


def test_explicit_weights_scope_and_bill_period_overlap_fail_closed():
    db, engine = _db()
    try:
        admin, _, prop, utility, bill, unit_a, unit_b, foreign_unit = _seed(db)

        with pytest.raises(HTTPException) as exc:
            api.create_allocation_rule(
                prop.id,
                utility.id,
                AllocationRuleCreate(
                    basis="OCCUPANCY",
                    effective_date=date(2026, 9, 1),
                    units=[AllocationUnitInput(unit_id=unit_a.id)],
                    request_key="allocation-rule-003",
                ),
                db=db,
                current_user=admin,
            )
        assert exc.value.status_code == 422

        with pytest.raises(HTTPException) as exc:
            api.create_allocation_rule(
                prop.id,
                utility.id,
                AllocationRuleCreate(
                    basis="MANUAL_WEIGHT",
                    effective_date=date(2026, 9, 1),
                    units=[
                        AllocationUnitInput(
                            unit_id=foreign_unit.id,
                            weight=Decimal("1"),
                        )
                    ],
                    request_key="allocation-rule-004",
                ),
                db=db,
                current_user=admin,
            )
        assert exc.value.status_code == 422

        rule = api.create_allocation_rule(
            prop.id,
            utility.id,
            AllocationRuleCreate(
                basis="FIXTURES",
                effective_date=date(2026, 9, 1),
                units=[
                    AllocationUnitInput(unit_id=unit_a.id, weight=Decimal("2")),
                    AllocationUnitInput(unit_id=unit_b.id, weight=Decimal("1")),
                ],
                request_key="allocation-rule-005",
            ),
            db=db,
            current_user=admin,
        )
        api.authorize_allocation_rule(
            prop.id,
            utility.id,
            rule["id"],
            AllocationRuleAuthorize(request_key="authorize-rule-005"),
            db=db,
            current_user=admin,
        )
        db.add(
            UtilityBill(
                utility_id=utility.id,
                billing_period_start=date(2026, 9, 30),
                billing_period_end=date(2026, 10, 31),
                amount=Decimal("80.00"),
            )
        )
        db.commit()

        with pytest.raises(HTTPException) as exc:
            api.preview_allocation(
                prop.id,
                utility.id,
                AllocationPreviewRequest(
                    rule_revision_id=rule["id"],
                    bill_id=bill.id,
                ),
                Response(),
                db=db,
                current_user=admin,
            )
        assert exc.value.status_code == 422
        assert "overlaps" in exc.value.detail
        assert db.query(Charge).count() == 0
        assert db.query(GLTransaction).count() == 0
    finally:
        db.close()
        engine.dispose()
