"""Phase 5 material purchasing and immutable physical-stock receipt movements.
No vendor dispatch, payment, GL posting or tenant liability is implied.
"""
from datetime import datetime
from sqlalchemy import (Column, Integer, String, Text, DateTime, ForeignKey,
                        CheckConstraint, UniqueConstraint)
from app.core.database import Base


class MaintenanceMaterialOrder(Base):
    __tablename__ = "maintenance_material_orders"
    __table_args__ = (
        CheckConstraint("requested_qty > 0 AND requested_qty <= 10000",
                        name="ck_material_order_quantity"),
        CheckConstraint("unit_cost_cents >= 0 AND unit_cost_cents <= 100000000",
                        name="ck_material_order_unit_cost"),
        CheckConstraint("status IN ('REQUESTED','APPROVED','DENIED')",
                        name="ck_material_order_status"),
    )
    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False, index=True)
    property_id = Column(Integer, ForeignKey("properties.id", ondelete="RESTRICT"), nullable=False, index=True)
    work_order_id = Column(Integer, ForeignKey("work_orders.id", ondelete="RESTRICT"), nullable=False, index=True)
    vendor_id = Column(Integer, ForeignKey("vendors.id", ondelete="RESTRICT"), nullable=False)
    sku = Column(String(60), nullable=False)
    item_name = Column(String(255), nullable=False)
    requested_qty = Column(Integer, nullable=False)
    unit_cost_cents = Column(Integer, nullable=False)
    reason = Column(Text, nullable=False)
    status = Column(String(16), nullable=False, default="REQUESTED")
    requested_by_id = Column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    requested_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    reviewed_by_id = Column(Integer, ForeignKey("users.id", ondelete="RESTRICT"))
    reviewed_at = Column(DateTime)
    decision_reason = Column(Text)


class MaintenanceMaterialMovement(Base):
    """Immutable net physical count. A reversal is a separate negative row."""
    __tablename__ = "maintenance_material_movements"
    __table_args__ = (
        UniqueConstraint("order_id", "reference", name="uq_material_movement_reference"),
        UniqueConstraint("reverses_id", name="uq_material_movement_reversal"),
        CheckConstraint("delta_qty != 0 AND delta_qty BETWEEN -10000 AND 10000",
                        name="ck_material_movement_delta"),
    )
    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False, index=True)
    order_id = Column(Integer, ForeignKey("maintenance_material_orders.id", ondelete="RESTRICT"), nullable=False, index=True)
    reference = Column(String(100), nullable=False)
    delta_qty = Column(Integer, nullable=False)
    received_by_id = Column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    reverses_id = Column(Integer, ForeignKey("maintenance_material_movements.id", ondelete="RESTRICT"), unique=True)
    reason = Column(Text, nullable=False)
    recorded_at = Column(DateTime, nullable=False, default=datetime.utcnow)
