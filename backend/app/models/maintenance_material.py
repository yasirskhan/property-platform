"""Phase 5 material purchasing and immutable physical-stock receipt movements.
No vendor dispatch, payment, GL posting or tenant liability is implied.
"""
from datetime import datetime
from sqlalchemy import (Column, Integer, BigInteger, String, Text, DateTime, ForeignKey,
                        CheckConstraint, UniqueConstraint)
from app.core.database import Base


class MaintenanceMaterialOrder(Base):
    __tablename__ = "maintenance_material_orders"
    __table_args__ = (
        CheckConstraint("requested_qty > 0 AND requested_qty <= 10000",
                        name="ck_material_order_quantity"),
        CheckConstraint("unit_cost_cents >= 0 AND unit_cost_cents <= 100000000",
                        name="ck_material_order_unit_cost"),
        UniqueConstraint("organization_id", "request_key", name="uq_material_order_org_request"),
        CheckConstraint("status IN ('REQUESTED','APPROVED','DENIED')",
                        name="ck_material_order_status"),
    )
    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False, index=True)
    property_id = Column(Integer, ForeignKey("properties.id", ondelete="RESTRICT"), nullable=False, index=True)
    work_order_id = Column(Integer, ForeignKey("work_orders.id", ondelete="RESTRICT"), nullable=False, index=True)
    vendor_id = Column(Integer, ForeignKey("vendors.id", ondelete="RESTRICT"), nullable=False)
    request_key = Column(String(80), nullable=False)
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
    reverses_id = Column(Integer, ForeignKey("maintenance_material_movements.id", ondelete="RESTRICT"))
    reason = Column(Text, nullable=False)
    recorded_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class MaintenanceMaterialIssue(Base):
    """Append-only issue/use allocation; negative rows reverse original issues.

    Source is one approved purchase order on the SAME property; consumption
    never posts a GL entry, creates a payable or charges a tenant.
    """
    __tablename__ = "maintenance_material_issues"
    __table_args__ = (
        UniqueConstraint("material_order_id", "reference", name="uq_material_issue_reference"),
        UniqueConstraint("reverses_id", name="uq_material_issue_reversal"),
        CheckConstraint("delta_qty != 0 AND delta_qty BETWEEN -10000 AND 10000",
                        name="ck_material_issue_quantity"),
    )
    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="RESTRICT"),
                             nullable=False, index=True)
    material_order_id = Column(Integer, ForeignKey("maintenance_material_orders.id", ondelete="RESTRICT"),
                               nullable=False, index=True)
    target_work_order_id = Column(Integer, ForeignKey("work_orders.id", ondelete="RESTRICT"),
                                  nullable=False)
    reference = Column(String(100), nullable=False)
    delta_qty = Column(Integer, nullable=False)
    issued_by_id = Column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    reverses_id = Column(Integer, ForeignKey("maintenance_material_issues.id", ondelete="RESTRICT"))
    reason = Column(Text, nullable=False)
    recorded_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class MaintenanceMaterialVariance(Base):
    """Immutable physical shortage/recount request, not a financial write-off."""
    __tablename__ = "maintenance_material_variances"
    __table_args__ = (
        UniqueConstraint("organization_id", "request_key", name="uq_material_variance_request"),
        CheckConstraint("quantity > 0 AND quantity <= 10000", name="ck_material_variance_qty"),
    )
    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False, index=True)
    material_order_id = Column(Integer, ForeignKey("maintenance_material_orders.id", ondelete="RESTRICT"), nullable=False, index=True)
    request_key = Column(String(80), nullable=False)
    quantity = Column(Integer, nullable=False)
    reason = Column(Text, nullable=False)
    reported_by_id = Column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    reported_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class MaintenanceMaterialVarianceDecision(Base):
    """Separate append-only independent approval/denial of physical shortage."""
    __tablename__ = "maintenance_material_variance_decisions"
    __table_args__ = (
        UniqueConstraint("variance_id", name="uq_material_variance_decision"),
        CheckConstraint("approved IN (0,1)", name="ck_material_variance_approval"),
    )
    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False, index=True)
    variance_id = Column(Integer, ForeignKey("maintenance_material_variances.id", ondelete="RESTRICT"), nullable=False)
    approved = Column(Integer, nullable=False)
    reason = Column(Text, nullable=False)
    reviewed_by_id = Column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    reviewed_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class MaintenanceMaterialVarianceRestoration(Base):
    """Append-only evidence for independently confirmed return of missing units."""
    __tablename__ = "maintenance_material_variance_restorations"
    __table_args__ = (
        UniqueConstraint("variance_id", name="uq_material_variance_restore"),
    )
    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False, index=True)
    variance_id = Column(Integer, ForeignKey("maintenance_material_variances.id", ondelete="RESTRICT"), nullable=False)
    reason = Column(Text, nullable=False)
    restored_by_id = Column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    restored_at = Column(DateTime, nullable=False, default=datetime.utcnow)

class MaintenanceMaterialBatch(Base):
    """Atomic 2–20 line internal requisition, not an external purchase order."""
    __tablename__ = "maintenance_material_batches"
    __table_args__ = (
        UniqueConstraint("organization_id", "batch_key", name="uq_material_batch_org_key"),
        CheckConstraint("line_count BETWEEN 2 AND 20", name="ck_material_batch_line_count"),
        CheckConstraint("estimated_total_cents >= 0 AND estimated_total_cents <= 20000000000000",
                        name="ck_material_batch_total"),
        CheckConstraint("status IN ('REQUESTED','APPROVED','DENIED')", name="ck_material_batch_status"),
    )
    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False, index=True)
    property_id = Column(Integer, ForeignKey("properties.id", ondelete="RESTRICT"), nullable=False)
    work_order_id = Column(Integer, ForeignKey("work_orders.id", ondelete="RESTRICT"), nullable=False)
    vendor_id = Column(Integer, ForeignKey("vendors.id", ondelete="RESTRICT"), nullable=False)
    batch_key = Column(String(64), nullable=False)
    reason = Column(Text, nullable=False)
    line_count = Column(Integer, nullable=False)
    estimated_total_cents = Column(BigInteger, nullable=False)
    requested_by_id = Column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    requested_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    status = Column(String(16), nullable=False, default="REQUESTED")
    reviewed_by_id = Column(Integer, ForeignKey("users.id", ondelete="RESTRICT"))
    reviewed_at = Column(DateTime)
    review_reason = Column(Text)


class MaintenanceMaterialBatchLine(Base):
    """Append-only mapping to existing audited per-line material source orders."""
    __tablename__ = "maintenance_material_batch_lines"
    __table_args__ = (
        UniqueConstraint("batch_id", "line_number", name="uq_material_batch_line_number"),
        UniqueConstraint("order_id", name="uq_material_batch_source_order"),
        CheckConstraint("line_number BETWEEN 1 AND 20", name="ck_material_batch_line_number"),
    )
    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False)
    batch_id = Column(Integer, ForeignKey("maintenance_material_batches.id", ondelete="RESTRICT"), nullable=False, index=True)
    order_id = Column(Integer, ForeignKey("maintenance_material_orders.id", ondelete="RESTRICT"), nullable=False)
    line_number = Column(Integer, nullable=False)
