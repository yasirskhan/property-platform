"""HOA $79 add-on is hidden, paid, org-scoped and never self-activated."""
from __future__ import annotations

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import init_db  # noqa: F401
from app.core.database import Base
from app.models.billing import Module, Plan, Subscription, SubscriptionItem, SubscriptionStatus
from app.models.billing_extras import AddOn
from app.models.organization_feature_setting import OrganizationFeatureSetting
from app.models.release_gate import ReleaseGate, ReleaseStage
from app.models.user import Organization, User, UserRole
from app.routers import hoa_associations as hoa
from app.services import customer_features
from app.services.entitlement_resolver import entitlement_allows_feature
from app.services.hoa_addon_catalog import seed_unreleased_hoa_catalog


def _setup(db, slug):
    org = Organization(name=slug, slug=slug)
    db.add(org)
    db.flush()
    admin = User(
        organization_id=org.id, email=f"{slug}@example.test",
        first_name="Admin", last_name="HOA",
        role=UserRole.ADMIN, hashed_password="x", is_active=True,
    )
    db.add(admin)
    db.flush()
    return org, admin


def test_hidden_hoa_catalog_pricing_and_subscription_feature_gate(monkeypatch):
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    db = sessionmaker(bind=engine, expire_on_commit=False)()
    try:
        org, admin = _setup(db, "hoa-gated")
        foreign, foreign_admin = _setup(db, "hoa-foreign")
        seed_unreleased_hoa_catalog(db)
        seed_unreleased_hoa_catalog(db)
        db.add(ReleaseGate(
            key="release.properties.compliance", stage=ReleaseStage.ALL_ORGS,
        ))
        db.commit()
        offer = db.query(AddOn).filter(AddOn.code == "hoa_monthly").one()
        module = db.query(Module).filter(Module.key == "hoa").one()
        assert offer.unit_price_cents == 7900
        assert offer.currency == "USD" and offer.is_active is False
        assert module.is_core is False
        assert db.query(Module).filter(Module.key == "hoa").count() == 1
        assert db.query(Subscription).count() == 0
        monkeypatch.setattr(hoa, "permission_allows_user", lambda *a, **k: True)
        monkeypatch.setattr(customer_features, "permission_allows_user", lambda *a, **k: True)
        assert entitlement_allows_feature(
            db, organization_id=org.id, feature_key="hoa",
        ) is False

        # Opening compliance for affordable does not unlock paid HOA.
        base = next(item for item in customer_features.resolve_customer_features(
            db, user=admin,
        ) if item.key == hoa.FEATURE_KEY)
        assert base.allowed is True
        with pytest.raises(HTTPException) as exc:
            hoa._access(db, admin)
        assert exc.value.status_code == 404

        gate = db.query(ReleaseGate).filter(
            ReleaseGate.key == "release.properties.hoa",
        ).one()
        gate.stage = ReleaseStage.ALL_ORGS
        db.commit()
        with pytest.raises(HTTPException) as exc:
            hoa._access(db, admin)
        assert exc.value.status_code == 404

        plan = Plan(code="synthetic-hoa", name="Synthetic HOA Test")
        db.add(plan)
        db.flush()
        subscription = Subscription(
            organization_id=org.id, plan_id=plan.id,
            status=SubscriptionStatus.ACTIVE,
        )
        db.add(subscription)
        db.commit()
        with pytest.raises(HTTPException) as exc:
            hoa._access(db, admin)
        assert exc.value.status_code == 404

        item = SubscriptionItem(
            subscription_id=subscription.id,
            module_id=module.id, unit_price_cents=7900,
        )
        db.add(item)
        db.commit()
        assert hoa._access(db, admin) == org.id
        with pytest.raises(HTTPException):
            hoa._access(db, foreign_admin)

        subscription.status = SubscriptionStatus.SUSPENDED
        db.commit()
        with pytest.raises(HTTPException):
            hoa._access(db, admin)
        subscription.status = SubscriptionStatus.ACTIVE
        db.add(OrganizationFeatureSetting(
            organization_id=org.id, feature_key="release.properties.hoa",
            enabled=False,
        ))
        db.commit()
        with pytest.raises(HTTPException):
            hoa._access(db, admin)
        db.query(OrganizationFeatureSetting).filter(
            OrganizationFeatureSetting.organization_id == org.id,
            OrganizationFeatureSetting.feature_key == "release.properties.hoa",
        ).one().enabled = True
        gate.stage = ReleaseStage.HIDDEN
        db.commit()
        with pytest.raises(HTTPException):
            hoa._access(db, admin)
        assert db.query(SubscriptionItem).count() == 1
        assert db.query(AddOn).count() == 1
        # These metadata changes have no provider checkout or billing side effect.
    finally:
        db.close()
        engine.dispose()
