"""Phase 4.11 age-restriction records must remain scoped and non-certifying."""
from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import pytest
from fastapi import HTTPException, Response
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import init_db  # noqa: F401
from app.core.database import Base
from app.models.audit_log import AuditLog
from app.models.charge import Charge
from app.models.gl_transaction import GLTransaction
from app.models.property import Property, PropertyAssignment
from app.models.senior_housing import SeniorAgeRestriction
from app.models.user import Organization, User, UserRole
from app.routers import senior_housing as api
from app.schemas.senior_housing import SeniorAgeRestrictionIn


def _db():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, expire_on_commit=False)(), engine


def _seed(db):
    org = Organization(name="Senior One", slug="senior-one")
    foreign_org = Organization(name="Senior Two", slug="senior-two")
    db.add_all([org, foreign_org]); db.flush()
    users = []
    for organization, role, name in (
        (org, UserRole.ADMIN, "admin"), (org, UserRole.OWNER, "owner"),
        (org, UserRole.MANAGER, "manager"), (org, UserRole.TENANT, "tenant"),
        (foreign_org, UserRole.ADMIN, "foreign"),
    ):
        user = User(
            organization_id=organization.id, role=role,
            email=f"senior-{name}@example.com", first_name=name, last_name="Housing",
            hashed_password="x", is_active=True,
        )
        db.add(user); users.append(user)
    db.flush()
    props = []
    for organization, name in ((org, "Assigned"), (org, "Unassigned"), (foreign_org, "Foreign")):
        prop = Property(
            organization_id=organization.id, name=name, address_line1="55 Main",
            city="Cleveland", state="OH", zip_code="44113", is_active=True,
        )
        db.add(prop); props.append(prop)
    db.flush()
    db.add(PropertyAssignment(
        property_id=props[0].id, user_id=users[2].id,
        role=UserRole.MANAGER, is_active=True,
    ))
    db.commit()
    return users, props


@pytest.fixture(autouse=True)
def gates(monkeypatch):
    monkeypatch.setattr(api, "permission_allows_user", lambda *a, **k: True)
    monkeypatch.setattr(api, "resolve_customer_features", lambda *a, **k: [
        SimpleNamespace(key=api.FEATURE_KEY, allowed=True),
    ])


def _payload(**overrides):
    data = {
        "restriction_type": "AGE_55_PLUS",
        "label": "Recorded 55+ restriction",
        "minimum_age": 55,
        "recorded_authority": "Staff-recorded governing reference",
        "reference_identifier": "REF-55",
        "effective_start": date(2026, 1, 1),
        "notes": "Reference only; not a compliance determination.",
    }
    data.update(overrides)
    return SeniorAgeRestrictionIn(**data)


def test_age_restriction_lifecycle_scoped_audited_and_finance_neutral():
    db, engine = _db()
    try:
        (admin, owner, manager, tenant, foreign), (assigned, unassigned, other) = _seed(db)
        created = api.create_age_restriction(assigned.id, _payload(), db=db, current_user=admin)
        assert created.minimum_age == 55 and created.restriction_type == "AGE_55_PLUS"

        response = Response()
        listed = api.list_age_restrictions(assigned.id, response, db=db, current_user=manager)
        assert [row.id for row in listed] == [created.id]
        assert response.headers["cache-control"] == "no-store"

        for actor, prop in ((manager, unassigned), (manager, other), (foreign, assigned)):
            with pytest.raises(HTTPException) as exc:
                api.list_age_restrictions(prop.id, Response(), db=db, current_user=actor)
            assert exc.value.status_code == 404

        for actor in (manager, tenant):
            with pytest.raises(HTTPException) as exc:
                api.create_age_restriction(
                    assigned.id, _payload(label=f"No write {actor.role.value}"),
                    db=db, current_user=actor,
                )
            assert exc.value.status_code == 403

        updated = api.update_age_restriction(
            assigned.id, created.id,
            _payload(restriction_type="AGE_62_PLUS", minimum_age=62, label="Recorded 62+ restriction"),
            db=db, current_user=owner,
        )
        assert updated.minimum_age == 62

        api.archive_age_restriction(assigned.id, created.id, db=db, current_user=admin)
        assert api.list_age_restrictions(assigned.id, Response(), db=db, current_user=admin) == []

        assert db.query(SeniorAgeRestriction).count() == 1
        assert db.query(AuditLog).filter(AuditLog.entity_type == "senior_age_restriction").count() == 3
        assert db.query(Charge).count() == 0
        assert db.query(GLTransaction).count() == 0
        columns = set(SeniorAgeRestriction.__table__.columns.keys())
        assert "resident_id" not in columns
        assert "eligible" not in columns
        assert "certified" not in columns
    finally:
        db.close(); engine.dispose()


def test_age_restriction_validation_duplicates_and_revoked_feature(monkeypatch):
    db, engine = _db()
    try:
        (admin, _owner, _manager, _tenant, _foreign), (assigned, _unassigned, _other) = _seed(db)
        api.create_age_restriction(assigned.id, _payload(), db=db, current_user=admin)
        with pytest.raises(HTTPException) as exc:
            api.create_age_restriction(assigned.id, _payload(), db=db, current_user=admin)
        assert exc.value.status_code == 409
        with pytest.raises(ValueError):
            _payload(effective_start=date(2026, 10, 1), effective_end=date(2026, 9, 1))
        with pytest.raises(ValueError):
            _payload(minimum_age=62)

        monkeypatch.setattr(api, "resolve_customer_features", lambda *a, **k: [
            SimpleNamespace(key=api.FEATURE_KEY, allowed=False),
        ])
        with pytest.raises(HTTPException) as exc:
            api.list_age_restrictions(assigned.id, Response(), db=db, current_user=admin)
        assert exc.value.status_code == 404
    finally:
        db.close(); engine.dispose()
