"""Accounting Key Accounts used by accounting workflows."""
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, UniqueConstraint, Index
from sqlalchemy.orm import relationship

from app.core.database import Base


class AccountingKeyAccount(Base):
    __tablename__ = "accounting_key_accounts"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(
        Integer,
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    key_type = Column(String(50), nullable=False, index=True)
    gl_account_id = Column(
        Integer,
        ForeignKey("gl_accounts.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    created_by_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    gl_account = relationship("GLAccount", foreign_keys=[gl_account_id])

    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "key_type",
            "gl_account_id",
            name="uq_accounting_key_account_org_type_gl",
        ),
        Index(
            "ix_accounting_key_accounts_org_type",
            "organization_id",
            "key_type",
        ),
    )
