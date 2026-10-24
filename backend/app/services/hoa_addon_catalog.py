"""One-time seed of the prelaunch HOA commercial catalog for fresh databases.

Existing databases receive the same values via Alembic d1e3f5a7b9c2.
Do not add subscriptions or promote the hidden release gate here.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.billing import Module, ModuleFeature
from app.models.billing_extras import AddOn
from app.models.release_gate import ReleaseGate, ReleaseStage


def seed_unreleased_hoa_catalog(db: Session) -> None:
    module = db.query(Module).filter(Module.key == "hoa").one_or_none()
    if module is None:
        module = Module(
            key="hoa", name="HOA",
            description="HOA add-on, release and authorization gated",
            is_core=False, is_active=True,
        )
        db.add(module)
        db.flush()
    if module.is_core:
        raise RuntimeError("HOA paid module must not be core")
    if db.query(ModuleFeature.id).filter(
        ModuleFeature.module_id == module.id,
        ModuleFeature.feature_key == "hoa",
    ).first() is None:
        db.add(ModuleFeature(
            module_id=module.id, feature_key="hoa",
            description="Independent HOA commercial entitlement",
        ))
    offer = db.query(AddOn).filter(AddOn.code == "hoa_monthly").one_or_none()
    if offer is None:
        db.add(AddOn(
            code="hoa_monthly", name="HOA monthly add-on",
            description="Planned $79/month HOA add-on. Not purchasable until checkout integration.",
            unit_price_cents=7900, currency="USD", is_active=False,
        ))
    elif offer.unit_price_cents != 7900 or offer.currency != "USD":
        raise RuntimeError("Existing HOA catalog price conflicts with approved $79/month")
    if db.query(ReleaseGate.id).filter(
        ReleaseGate.key == "release.properties.hoa",
    ).first() is None:
        db.add(ReleaseGate(
            key="release.properties.hoa", stage=ReleaseStage.HIDDEN,
            description="Dedicated HOA add-on, hidden until operator release",
        ))
    db.flush()
