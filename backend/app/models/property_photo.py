# ============================================================
# property_photo.py
# ------------------------------------------------------------
# A photo attached to a property. The physical file lives in
# backend/uploads/. This record points at it and carries the
# display metadata (caption, cover flag, marketing flag, order).
#
# AppFolio parity:
#   * is_cover: one per property (server enforces uniqueness)
#   * is_marketing: shown in listings / tenant-facing gallery
#   * caption: optional
#   * sort_order: manual drag order
# ============================================================

from datetime import datetime

from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    Text,
    DateTime,
    ForeignKey,
)
from sqlalchemy.orm import relationship

from app.core.database import Base


class PropertyPhoto(Base):
    __tablename__ = "property_photos"

    id = Column(Integer, primary_key=True, index=True)

    organization_id = Column(
        Integer,
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    property_id = Column(
        Integer,
        ForeignKey("properties.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Path returned by /uploads, e.g. "/uploads/abc123.jpg"
    url = Column(String(500), nullable=False)

    # Server-side filename (UUID-based)
    filename = Column(String(200), nullable=False)

    # What the user's file was originally called
    original_name = Column(String(300), nullable=True)

    content_type = Column(String(80), nullable=True)
    size_bytes = Column(Integer, nullable=True)

    caption = Column(String(500), nullable=True)

    # Show in listing / marketing gallery
    is_marketing = Column(Boolean, nullable=False, default=False)

    # The primary/cover photo (only one per property)
    is_cover = Column(Boolean, nullable=False, default=False)

    # Manual drag order (low numbers first)
    sort_order = Column(Integer, nullable=False, default=0)

    is_active = Column(Boolean, nullable=False, default=True, index=True)
    deleted_at = Column(DateTime, nullable=True, index=True)
    delete_reason = Column(Text, nullable=True)

    created_by_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    organization = relationship("Organization")
    property = relationship("Property")
    created_by = relationship("User", foreign_keys=[created_by_id])

    def __repr__(self) -> str:
        return (
            f"<PropertyPhoto {self.id} property={self.property_id} "
            f"url={self.url}>"
        )