# ============================================================
# models/audit_log.py
# ------------------------------------------------------------
# Append-only audit history.
#
# Audit rows may be inserted, but never updated or deleted. The ORM
# guards below enforce this in every environment. PostgreSQL also gets
# a database trigger so direct SQL cannot rewrite history.
# ============================================================

from datetime import datetime

from sqlalchemy import (
    Column,
    DateTime,
    DDL,
    ForeignKey,
    Integer,
    String,
    Text,
    event,
)
from sqlalchemy.orm import relationship

from app.core.database import Base

# Import related models so SQLAlchemy can resolve relationships.
from app.models.user import User  # noqa: F401
from app.models.platform_user import PlatformUser  # noqa: F401


class AuditLog(Base):
    __tablename__ = "audit_log"

    id = Column(Integer, primary_key=True, index=True)

    # Who made the change. Customer and platform actors remain separate.
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    platform_user_id = Column(
        Integer,
        ForeignKey("platform_users.id"),
        nullable=True,
        index=True,
    )
    organization_id = Column(
        Integer,
        ForeignKey("organizations.id"),
        nullable=True,
        index=True,
    )

    # What changed.
    entity_type = Column(String(50), nullable=False, index=True)
    entity_id = Column(Integer, nullable=False, index=True)

    # What happened.
    action = Column(String(50), nullable=False)
    field_name = Column(String(100), nullable=True)
    old_value = Column(Text, nullable=True)
    new_value = Column(Text, nullable=True)

    # Where from.
    ip_address = Column(String(45), nullable=True)

    # When.
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    user = relationship("User")
    platform_user = relationship("PlatformUser")

    def __repr__(self) -> str:
        return f"<AuditLog {self.entity_type}#{self.entity_id} {self.action}>"


def _reject_mutation(*_args, **_kwargs) -> None:
    raise RuntimeError("audit_log is append-only; UPDATE and DELETE are forbidden")


event.listen(AuditLog, "before_update", _reject_mutation, propagate=True)
event.listen(AuditLog, "before_delete", _reject_mutation, propagate=True)

_POSTGRES_AUDIT_FUNCTION = DDL(
    """
    CREATE OR REPLACE FUNCTION prevent_audit_log_mutation()
    RETURNS trigger AS $$
    BEGIN
        RAISE EXCEPTION 'audit_log is append-only; UPDATE and DELETE are forbidden';
    END;
    $$ LANGUAGE plpgsql;
    """
).execute_if(dialect="postgresql")

_POSTGRES_AUDIT_TRIGGER = DDL(
    """
    CREATE TRIGGER audit_log_immutable
    BEFORE UPDATE OR DELETE ON audit_log
    FOR EACH ROW
    EXECUTE FUNCTION prevent_audit_log_mutation();
    """
).execute_if(dialect="postgresql")

event.listen(AuditLog.__table__, "after_create", _POSTGRES_AUDIT_FUNCTION)
event.listen(AuditLog.__table__, "after_create", _POSTGRES_AUDIT_TRIGGER)
