# ============================================================
# charge.py
# ------------------------------------------------------------
# Standalone tenant charges.
#
# A charge is an amount owed by a tenant (late fee, damage,
# utility, misc). Distinct from rent_invoices (auto-generated
# per active lease). Distinct from receipt_lines (payments).
#
# amount_paid + is_paid let us compute outstanding balance
# without scanning the ledger.
#
# See PROJECT_MASTER.md Section 19.
# ============================================================

from datetime import datetime

from sqlalchemy import (
    Column,
    Integer,
    String,
    Date,
    DateTime,
    ForeignKey,
    Boolean,
    Numeric,
)
from sqlalchemy.orm import relationship

from app.core.database import Base


class Charge(Base):
    __tablename__ = "charges"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(
        Integer,
        ForeignKey("organizations.id"),
        nullable=False,
        index=True,
    )

    tenant_user_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )
    unit_id = Column(
        Integer,
        ForeignKey("units.id"),
        nullable=True,
        index=True,
    )
    property_id = Column(
        Integer,
        ForeignKey("properties.id"),
        nullable=True,
        index=True,
    )
    gl_account_id = Column(
        Integer,
        ForeignKey("gl_accounts.id"),
        nullable=False,
        index=True,
    )

    charge_date = Column(Date, nullable=False, index=True)
    description = Column(String(500), nullable=False)
    amount = Column(Numeric(14, 2), nullable=False)
    amount_paid = Column(Numeric(14, 2), nullable=False, default=0)
    is_paid = Column(Boolean, nullable=False, default=False)

    is_active = Column(Boolean, nullable=False, default=True)
    delete_reason = Column(String(500), nullable=True)

    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    tenant = relationship("User", foreign_keys=[tenant_user_id])
    gl_account = relationship("GLAccount")
    property = relationship("Property")
    unit = relationship("Unit")