"""Register an unreleased $79/month HOA add-on and independent paid entitlement.

Revision ID: d1e3f5a7b9c2
Revises: c0d2e4f6a8b1

No existing organization is subscribed, billed, upgraded or entitled here.
"""
from datetime import datetime
from alembic import op
import sqlalchemy as sa

revision = "d1e3f5a7b9c2"
down_revision = "c0d2e4f6a8b1"
branch_labels = None
depends_on = None

HOA_MODULE = "hoa"
HOA_ADDON = "hoa_monthly"
HOA_GATE = "release.properties.hoa"
HOA_PRICE_CENTS = 7900


def upgrade() -> None:
    connection = op.get_bind()
    now = datetime.utcnow()
    module = connection.execute(
        sa.text("SELECT id, is_core FROM modules WHERE key = :key"), {"key": HOA_MODULE},
    ).first()
    if module is None:
        connection.execute(sa.text(
            "INSERT INTO modules (key, name, description, is_core, is_active, created_at, updated_at) "
            "VALUES (:key, :name, :description, :is_core, :is_active, :now, :now)"
        ), {"key": HOA_MODULE, "name": "HOA", "description": "HOA add-on, release and authorization gated",
            "is_core": False, "is_active": True, "now": now})
        module = connection.execute(
            sa.text("SELECT id, is_core FROM modules WHERE key = :key"), {"key": HOA_MODULE},
        ).first()
    if bool(module.is_core):
        raise RuntimeError("HOA commercial module must not be marked core")
    if connection.execute(sa.text(
        "SELECT id FROM module_features WHERE module_id = :id AND feature_key = 'hoa'"
    ), {"id": module.id}).first() is None:
        connection.execute(sa.text(
            "INSERT INTO module_features (module_id, feature_key, description, created_at) "
            "VALUES (:id, :feature, :description, :now)"
        ), {"id": module.id, "feature": HOA_MODULE,
            "description": "Independent HOA commercial entitlement", "now": now})

    offer = connection.execute(sa.text(
        "SELECT unit_price_cents, currency FROM add_ons WHERE code = :code"
    ), {"code": HOA_ADDON}).first()
    if offer is None:
        connection.execute(sa.text(
            "INSERT INTO add_ons (code, name, description, unit_price_cents, currency, is_active,"
            " created_at, updated_at) VALUES (:code, :name, :description, :price, 'USD', :active, :now, :now)"
        ), {"code": HOA_ADDON, "name": "HOA monthly add-on",
            "description": "Planned $79/month HOA add-on. Not purchasable until checkout integration.",
            "price": HOA_PRICE_CENTS, "active": False, "now": now})
    elif int(offer.unit_price_cents) != HOA_PRICE_CENTS or offer.currency != "USD":
        raise RuntimeError("Existing HOA add-on price conflicts with approved $79/month catalog")

    if connection.execute(sa.text(
        "SELECT id FROM release_gates WHERE key = :key"
    ), {"key": HOA_GATE}).first() is None:
        connection.execute(sa.text(
            "INSERT INTO release_gates (key, stage, description, created_at, updated_at) "
            "VALUES (:key, 'HIDDEN', :description, :now, :now)"
        ), {"key": HOA_GATE, "description": "Dedicated HOA add-on, hidden until operator release",
            "now": now})


def downgrade() -> None:
    connection = op.get_bind()
    module = connection.execute(sa.text(
        "SELECT id FROM modules WHERE key = :key"
    ), {"key": HOA_MODULE}).first()
    if module is not None:
        if connection.execute(sa.text(
            "SELECT id FROM subscription_items WHERE module_id = :id "
            "UNION ALL SELECT id FROM plan_modules WHERE module_id = :id LIMIT 1"
        ), {"id": module.id}).first() is not None:
            raise RuntimeError("Cannot downgrade an assigned HOA add-on")
        connection.execute(sa.text(
            "DELETE FROM module_features WHERE module_id = :id AND feature_key = 'hoa'"
        ), {"id": module.id})
        connection.execute(sa.text("DELETE FROM modules WHERE id = :id"), {"id": module.id})
    connection.execute(sa.text("DELETE FROM add_ons WHERE code = :code"), {"code": HOA_ADDON})
    connection.execute(sa.text("DELETE FROM release_gates WHERE key = :key"), {"key": HOA_GATE})
