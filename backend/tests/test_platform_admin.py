from __future__ import annotations

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import init_db  # noqa: F401
from app.core.database import Base
from app.core.security import hash_password
from app.models.audit_log import AuditLog
from app.models.menu_permission import MenuPermission
from app.models.platform_user import PlatformUser, PlatformUserRole
from app.models.release_gate import ReleaseGate, ReleaseStage
from app.routers.platform_admin import (
    create_platform_organization,
    create_platform_plan,
    list_platform_audit,
    list_platform_organizations,
    list_platform_plans,
    update_platform_plan,
)
from app.routers.platform_flags import list_release_gates
from app.schemas.platform_admin import (
    PlatformOrganizationCreateIn,
    PlatformPlanCreateIn,
    PlatformPlanUpdateIn,
    PlatformPricingTierCreateIn,
)
from app.services.audit import append_audit_log


def _session():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)(), engine


def _platform_user(db, role: PlatformUserRole) -> PlatformUser:
    user = PlatformUser(
        email=f"{role.value}-{db.query(PlatformUser).count()}@example.com",
        hashed_password=hash_password("test-platform-password"),
        first_name="Platform",
        last_name="Staff",
        role=role,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def test_sales_can_provision_enterprise_org_and_support_can_read_it() -> None:
    db, engine = _session()
    try:
        sales = _platform_user(db, PlatformUserRole.PLATFORM_SALES)
        support = _platform_user(db, PlatformUserRole.PLATFORM_SUPPORT)

        created = create_platform_organization(
            PlatformOrganizationCreateIn(
                name="Enterprise Test LLC",
                currency="usd",
                data_region="us-east-1",
            ),
            db=db,
            current_user=sales,
        )
        assert created.name == "Enterprise Test LLC"
        assert created.slug == "enterprise-test-llc"
        assert created.state == "PENDING_BILLING"
        assert created.currency == "USD"
        assert created.subscription_status is None
        assert (
            db.query(MenuPermission)
            .filter(MenuPermission.organization_id == created.id)
            .count()
            > 0
        )

        audit = (
            db.query(AuditLog)
            .filter(
                AuditLog.entity_type == "organization",
                AuditLog.entity_id == created.id,
            )
            .one()
        )
        assert audit.platform_user_id == sales.id
        assert audit.user_id is None

        listed = list_platform_organizations(
            q="Enterprise",
            organization_state="PENDING_BILLING",
            limit=100,
            db=db,
            current_user=support,
        )
        assert [row.id for row in listed] == [created.id]
    finally:
        db.close()
        engine.dispose()


def test_support_cannot_provision_enterprise_org() -> None:
    db, engine = _session()
    try:
        support = _platform_user(db, PlatformUserRole.PLATFORM_SUPPORT)
        with pytest.raises(HTTPException) as exc:
            create_platform_organization(
                PlatformOrganizationCreateIn(name="Blocked Org"),
                db=db,
                current_user=support,
            )
        assert exc.value.status_code == 403
    finally:
        db.close()
        engine.dispose()


def test_billing_can_create_update_plan_and_sales_is_read_only() -> None:
    db, engine = _session()
    try:
        billing = _platform_user(db, PlatformUserRole.PLATFORM_BILLING)
        sales = _platform_user(db, PlatformUserRole.PLATFORM_SALES)
        payload = PlatformPlanCreateIn(
            code="growth",
            name="Growth",
            description="Growth plan",
            pricing_tiers=[
                PlatformPricingTierCreateIn(
                    min_properties=1,
                    max_properties=10,
                    monthly_price_cents=4900,
                    currency="USD",
                ),
                PlatformPricingTierCreateIn(
                    min_properties=11,
                    max_properties=None,
                    monthly_price_cents=9900,
                    currency="USD",
                ),
            ],
        )
        created = create_platform_plan(payload, db=db, current_user=billing)
        assert created.code == "growth"
        assert [tier.min_properties for tier in created.pricing_tiers] == [1, 11]

        updated = update_platform_plan(
            created.id,
            PlatformPlanUpdateIn(name="Growth Plus", is_active=False),
            db=db,
            current_user=billing,
        )
        assert updated.name == "Growth Plus"
        assert updated.is_active is False

        visible = list_platform_plans(
            include_inactive=True,
            db=db,
            current_user=sales,
        )
        assert [row.id for row in visible] == [created.id]

        with pytest.raises(HTTPException) as exc:
            create_platform_plan(payload, db=db, current_user=sales)
        assert exc.value.status_code == 403

        plan_audits = (
            db.query(AuditLog)
            .filter(AuditLog.entity_type == "plan")
            .order_by(AuditLog.id.asc())
            .all()
        )
        assert [row.action for row in plan_audits] == [
            "platform_created",
            "platform_updated",
        ]
        assert all(row.platform_user_id == billing.id for row in plan_audits)
    finally:
        db.close()
        engine.dispose()


def test_plan_creation_rejects_overlapping_tiers() -> None:
    db, engine = _session()
    try:
        admin = _platform_user(db, PlatformUserRole.PLATFORM_ADMIN)
        with pytest.raises(HTTPException) as exc:
            create_platform_plan(
                PlatformPlanCreateIn(
                    code="overlap",
                    name="Overlap",
                    pricing_tiers=[
                        PlatformPricingTierCreateIn(
                            min_properties=1,
                            max_properties=10,
                            monthly_price_cents=1000,
                        ),
                        PlatformPricingTierCreateIn(
                            min_properties=10,
                            max_properties=20,
                            monthly_price_cents=2000,
                        ),
                    ],
                ),
                db=db,
                current_user=admin,
            )
        assert exc.value.status_code == 400
        assert "must not overlap" in exc.value.detail
    finally:
        db.close()
        engine.dispose()


def test_platform_audit_is_staff_only_and_excludes_nonplatform_rows() -> None:
    db, engine = _session()
    try:
        support = _platform_user(db, PlatformUserRole.PLATFORM_SUPPORT)
        sales = _platform_user(db, PlatformUserRole.PLATFORM_SALES)
        append_audit_log(
            db,
            platform_user_id=support.id,
            entity_type="support_probe",
            entity_id=1,
            action="viewed",
        )
        append_audit_log(
            db,
            entity_type="customer_probe",
            entity_id=2,
            action="created",
        )
        db.commit()

        rows = list_platform_audit(
            entity_type=None,
            organization_id=None,
            platform_user_id=None,
            limit=100,
            db=db,
            current_user=support,
        )
        assert len(rows) == 1
        assert rows[0].entity_type == "support_probe"
        assert rows[0].platform_user_email == support.email

        with pytest.raises(HTTPException) as exc:
            list_platform_audit(
                entity_type=None,
                organization_id=None,
                platform_user_id=None,
                limit=100,
                db=db,
                current_user=sales,
            )
        assert exc.value.status_code == 403
    finally:
        db.close()
        engine.dispose()


def test_dev_can_list_release_gates() -> None:
    db, engine = _session()
    try:
        dev = _platform_user(db, PlatformUserRole.PLATFORM_DEV)
        db.add_all(
            [
                ReleaseGate(key="release.beta", stage=ReleaseStage.BETA),
                ReleaseGate(key="release.alpha", stage=ReleaseStage.HIDDEN),
            ]
        )
        db.commit()
        rows = list_release_gates(db=db, current_user=dev)
        assert [row.key for row in rows] == ["release.alpha", "release.beta"]
    finally:
        db.close()
        engine.dispose()
