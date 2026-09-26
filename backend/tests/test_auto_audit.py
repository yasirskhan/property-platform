from __future__ import annotations

from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import init_db  # noqa: F401
from app.core.database import Base
from app.models.audit_log import AuditLog
from app.models.property import Property, PropertyType, Unit
from app.models.user import Organization, User, UserRole
from app.services.audit import append_audit_log
from app.services.auto_audit import bind_customer_audit_actor


def _session():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, expire_on_commit=False)(), engine


def _seed(db):
    org = Organization(name="Audit Org", slug="audit-org")
    db.add(org)
    db.flush()
    user = User(
        email="audit@example.com",
        hashed_password="not-used",
        first_name="Audit",
        last_name="Admin",
        role=UserRole.ADMIN,
        organization_id=org.id,
        is_active=True,
    )
    prop = Property(
        organization_id=org.id,
        name="Original Property",
        property_type=PropertyType.MULTI_FAMILY,
        address_line1="100 Audit Ave",
        city="Cleveland",
        state="OH",
        zip_code="44113",
        country="USA",
        is_active=True,
    )
    db.add_all([user, prop])
    db.commit()
    return org, user, prop


def test_authenticated_update_is_audited_without_business_values():
    db, engine = _session()
    try:
        org, user, prop = _seed(db)
        assert db.query(AuditLog).count() == 0

        bind_customer_audit_actor(db, user)
        prop.name = "Renamed Property"
        db.commit()

        rows = db.query(AuditLog).filter(
            AuditLog.entity_type == "properties",
            AuditLog.entity_id == prop.id,
        ).all()
        assert len(rows) == 1
        row = rows[0]
        assert row.user_id == user.id
        assert row.organization_id == org.id
        assert row.action == "updated"
        assert row.field_name == "name"
        assert row.old_value is None
        assert row.new_value is None
    finally:
        db.close()
        engine.dispose()


def test_authenticated_create_and_soft_delete_are_audited():
    db, engine = _session()
    try:
        org, user, prop = _seed(db)
        bind_customer_audit_actor(db, user)

        unit = Unit(
            property_id=prop.id,
            unit_number="A1",
            bedrooms=1,
            bathrooms=1,
            monthly_rent=1000,
            is_available=True,
            is_active=True,
        )
        db.add(unit)
        db.commit()

        created = db.query(AuditLog).filter(
            AuditLog.entity_type == "units",
            AuditLog.entity_id == unit.id,
            AuditLog.action == "created",
        ).one()
        assert created.user_id == user.id
        assert created.organization_id == org.id

        prop.is_active = False
        prop.deleted_at = datetime.utcnow()
        db.commit()

        deleted = db.query(AuditLog).filter(
            AuditLog.entity_type == "properties",
            AuditLog.entity_id == prop.id,
            AuditLog.action == "soft_deleted",
        ).one()
        assert set((deleted.field_name or "").split(",")) == {"deleted_at", "is_active"}
    finally:
        db.close()
        engine.dispose()


def test_explicit_semantic_audit_prevents_generic_update_duplicate():
    db, engine = _session()
    try:
        org, user, prop = _seed(db)
        bind_customer_audit_actor(db, user)

        prop.name = "Explicit Audit Property"
        append_audit_log(
            db,
            user_id=user.id,
            organization_id=org.id,
            entity_type="properties",
            entity_id=prop.id,
            action="property_renamed",
            field_name="name",
            old_value="Original Property",
            new_value="Explicit Audit Property",
        )
        db.commit()

        rows = db.query(AuditLog).filter(
            AuditLog.entity_type == "properties",
            AuditLog.entity_id == prop.id,
        ).all()
        assert [row.action for row in rows] == ["property_renamed"]
    finally:
        db.close()
        engine.dispose()


def test_rollback_does_not_leave_audit_row_or_pending_state():
    db, engine = _session()
    try:
        _org, user, prop = _seed(db)
        bind_customer_audit_actor(db, user)

        prop.name = "Rolled Back"
        db.flush()
        db.rollback()

        assert db.query(AuditLog).filter(
            AuditLog.entity_type == "properties",
            AuditLog.entity_id == prop.id,
        ).count() == 0

        prop.name = "Committed Later"
        db.commit()
        rows = db.query(AuditLog).filter(
            AuditLog.entity_type == "properties",
            AuditLog.entity_id == prop.id,
        ).all()
        assert len(rows) == 1
        assert rows[0].action == "updated"
    finally:
        db.close()
        engine.dispose()
