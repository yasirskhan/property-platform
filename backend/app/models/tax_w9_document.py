"""Signed-paper W-9 evidence stored only as authenticated ciphertext."""
from datetime import datetime

from sqlalchemy import Column, Date, DateTime, ForeignKey, Index, Integer, LargeBinary

from app.core.database import Base


class TaxW9Document(Base):
    __tablename__ = "tax_w9_documents"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    tax_profile_id = Column(Integer, ForeignKey("tax_profiles.id", ondelete="RESTRICT"), nullable=False, index=True)
    encrypted_pdf = Column(LargeBinary, nullable=False)
    size_bytes = Column(Integer, nullable=False)
    received_on = Column(Date, nullable=False)
    uploaded_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    uploaded_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_tax_w9_org_profile", "organization_id", "tax_profile_id", "id"),
    )
