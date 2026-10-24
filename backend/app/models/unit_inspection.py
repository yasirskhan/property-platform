"""Explicit staff-recorded unit inspections, NOT the Phase 5 mobile workflow."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, String, Text, Index, CheckConstraint, DDL, event

from app.core.database import Base


class UnitInspectionRecord(Base):
    __tablename__ = "unit_inspection_records"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    property_id = Column(Integer, ForeignKey("properties.id", ondelete="RESTRICT"), nullable=False, index=True)
    unit_id = Column(Integer, ForeignKey("units.id", ondelete="RESTRICT"), nullable=False, index=True)
    inspection_date = Column(Date, nullable=False, index=True)
    recorded_condition = Column(String(24), nullable=False)
    findings = Column(Text, nullable=False, default="")
    checklist_json = Column(Text, nullable=True)
    recorded_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    recorded_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_unit_inspections_org_property_date", "organization_id", "property_id", "inspection_date"),
    )

class UnitInspectionReview(Base):
    """Independent, append-only review decision for recorded inspection evidence."""
    __tablename__ = "unit_inspection_reviews"
    __table_args__ = (
        CheckConstraint("decision IN ('CONFIRMED','FOLLOW_UP_REQUIRED')",
                        name="ck_unit_inspection_review_decision"),
    )

    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False, index=True)
    inspection_id = Column(Integer, ForeignKey("unit_inspection_records.id", ondelete="RESTRICT"),
                           nullable=False, unique=True, index=True)
    reviewer_id = Column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    decision = Column(String(24), nullable=False)
    notes = Column(String(1000), nullable=False)
    reviewed_at = Column(DateTime, nullable=False, default=datetime.utcnow)


def _reject_inspection_review_mutation(*_args, **_kwargs) -> None:
    raise RuntimeError("unit_inspection_reviews is append-only")


event.listen(UnitInspectionReview, "before_update", _reject_inspection_review_mutation)
event.listen(UnitInspectionReview, "before_delete", _reject_inspection_review_mutation)

_PG_REVIEW_FUNCTION = DDL("""
    CREATE OR REPLACE FUNCTION prevent_inspection_review_mutation()
    RETURNS trigger AS $$
    BEGIN
        RAISE EXCEPTION 'unit_inspection_reviews is append-only';
    END;
    $$ LANGUAGE plpgsql;
""").execute_if(dialect="postgresql")
_PG_REVIEW_TRIGGER = DDL("""
    CREATE TRIGGER unit_inspection_review_immutable
    BEFORE UPDATE OR DELETE ON unit_inspection_reviews
    FOR EACH ROW EXECUTE FUNCTION prevent_inspection_review_mutation();
""").execute_if(dialect="postgresql")
_SQLITE_REVIEW_UPDATE = DDL("""
    CREATE TRIGGER unit_inspection_review_no_update BEFORE UPDATE ON unit_inspection_reviews
    BEGIN SELECT RAISE(ABORT, 'unit_inspection_reviews is append-only'); END;
""").execute_if(dialect="sqlite")
_SQLITE_REVIEW_DELETE = DDL("""
    CREATE TRIGGER unit_inspection_review_no_delete BEFORE DELETE ON unit_inspection_reviews
    BEGIN SELECT RAISE(ABORT, 'unit_inspection_reviews is append-only'); END;
""").execute_if(dialect="sqlite")
for _guard in (_PG_REVIEW_FUNCTION, _PG_REVIEW_TRIGGER, _SQLITE_REVIEW_UPDATE, _SQLITE_REVIEW_DELETE):
    event.listen(UnitInspectionReview.__table__, "after_create", _guard)
