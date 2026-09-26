from __future__ import annotations

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import init_db  # noqa: F401
from app.core.database import Base
from app.core.security import hash_password
from app.models.entity_note import EntityNote
from app.models.property import Property, PropertyAssignment, PropertyType
from app.models.user import Organization, User, UserRole
from app.routers.entity_notes import add_entity_note, list_entity_notes
from app.schemas.entity_note import EntityNoteCreateIn


def _session():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, expire_on_commit=False)(), engine


def _user(db, *, org, email: str, role: UserRole) -> User:
    row = User(
        email=email,
        hashed_password=hash_password("test1234"),
        first_name=role.value.title(),
        last_name="Notes",
        role=role,
        organization_id=org.id,
        is_active=True,
    )
    db.add(row)
    db.flush()
    return row


def _property(db, *, org, name: str) -> Property:
    row = Property(
        organization_id=org.id,
        name=name,
        property_type=PropertyType.MULTI_FAMILY,
        address_line1="100 Test Avenue",
        city="Cleveland",
        state="OH",
        zip_code="44113",
        country="USA",
        is_active=True,
    )
    db.add(row)
    db.flush()
    return row


def test_property_notes_are_timestamped_scoped_and_audited():
    db, engine = _session()
    try:
        org = Organization(name="Notes Org", slug="notes-org")
        other_org = Organization(name="Other Notes Org", slug="other-notes-org")
        db.add_all([org, other_org])
        db.flush()
        admin = _user(db, org=org, email="notes-admin@example.com", role=UserRole.ADMIN)
        other_admin = _user(db, org=other_org, email="other-notes-admin@example.com", role=UserRole.ADMIN)
        prop = _property(db, org=org, name="Notes Property")
        db.commit()

        created = add_entity_note(
            entity_type="properties",
            entity_id=prop.id,
            payload=EntityNoteCreateIn(body="  Called owner about reserve.  "),
            db=db,
            current_user=admin,
        )
        assert created.body == "Called owner about reserve."
        assert created.created_by_id == admin.id
        assert created.created_by_name == "Admin Notes"
        assert created.created_at is not None

        listed = list_entity_notes(
            entity_type="properties",
            entity_id=prop.id,
            db=db,
            current_user=admin,
        )
        assert listed.total == 1
        assert listed.items[0].body == "Called owner about reserve."
        assert db.query(EntityNote).filter(EntityNote.organization_id == org.id).count() == 1

        with pytest.raises(HTTPException) as exc:
            list_entity_notes(
                entity_type="properties",
                entity_id=prop.id,
                db=db,
                current_user=other_admin,
            )
        assert exc.value.status_code == 403
    finally:
        db.close()
        engine.dispose()


def test_manager_requires_property_assignment_for_notes():
    db, engine = _session()
    try:
        org = Organization(name="Manager Notes Org", slug="manager-notes-org")
        db.add(org)
        db.flush()
        manager = _user(db, org=org, email="notes-manager@example.com", role=UserRole.MANAGER)
        prop = _property(db, org=org, name="Assigned Notes Property")
        db.commit()

        with pytest.raises(HTTPException) as exc:
            list_entity_notes(
                entity_type="properties",
                entity_id=prop.id,
                db=db,
                current_user=manager,
            )
        assert exc.value.status_code == 403

        db.add(
            PropertyAssignment(
                property_id=prop.id,
                user_id=manager.id,
                role=UserRole.MANAGER,
                is_active=True,
            )
        )
        db.commit()

        created = add_entity_note(
            entity_type="properties",
            entity_id=prop.id,
            payload=EntityNoteCreateIn(body="Manager follow-up"),
            db=db,
            current_user=manager,
        )
        assert created.body == "Manager follow-up"
    finally:
        db.close()
        engine.dispose()


def test_internal_platform_tables_are_not_note_targets():
    db, engine = _session()
    try:
        org = Organization(name="Forbidden Notes Org", slug="forbidden-notes-org")
        db.add(org)
        db.flush()
        admin = _user(db, org=org, email="forbidden-notes@example.com", role=UserRole.ADMIN)
        db.commit()

        with pytest.raises(HTTPException) as exc:
            list_entity_notes(
                entity_type="audit_log",
                entity_id=1,
                db=db,
                current_user=admin,
            )
        assert exc.value.status_code == 404
    finally:
        db.close()
        engine.dispose()
