from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models.billing import Module, ModuleFeature, Plan, PlanModule, Subscription
from app.models.user import Organization, User, UserRole
from app.services.menu_resolver import resolve_menu_for_user


def _session():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, expire_on_commit=False)(), engine


def _admin(db, *, slug: str):
    org = Organization(name="Example", slug=slug)
    db.add(org)
    db.flush()
    user = User(
        email=f"{slug}@example.com",
        hashed_password="unused",
        first_name="Admin",
        last_name="User",
        role=UserRole.ADMIN,
        organization_id=org.id,
        is_active=True,
    )
    db.add(user)
    db.flush()
    return org, user


def test_paid_menu_parent_is_hidden_until_plan_includes_module() -> None:
    db, engine = _session()
    try:
        org, admin = _admin(db, slug="menu-paid")
        module = Module(key="accounting", name="Accounting")
        db.add(module)
        db.flush()
        db.add(ModuleFeature(module_id=module.id, feature_key="ACCOUNTING"))
        db.commit()

        keys = {item["key"] for item in resolve_menu_for_user(db, admin)}
        assert "ACCOUNTING" not in keys
        assert "ACCOUNTING.RECEIVABLES" not in keys
        assert "DASHBOARD" in keys

        plan = Plan(code="menu-pro", name="Pro")
        db.add(plan)
        db.flush()
        db.add(PlanModule(plan_id=plan.id, module_id=module.id))
        db.add(Subscription(organization_id=org.id, plan_id=plan.id))
        db.commit()

        keys = {item["key"] for item in resolve_menu_for_user(db, admin)}
        assert "ACCOUNTING" in keys
    finally:
        db.close()
        engine.dispose()


def test_core_menu_does_not_require_subscription() -> None:
    db, engine = _session()
    try:
        _, admin = _admin(db, slug="menu-core")
        module = Module(key="maintenance", name="Maintenance", is_core=True)
        db.add(module)
        db.flush()
        db.add(ModuleFeature(module_id=module.id, feature_key="MAINTENANCE"))
        db.commit()

        keys = {item["key"] for item in resolve_menu_for_user(db, admin)}
        assert "MAINTENANCE" in keys
    finally:
        db.close()
        engine.dispose()
