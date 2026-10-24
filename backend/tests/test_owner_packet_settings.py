from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import init_db  # noqa: F401
import app.routers.owner_statements as owner_statements
from app.core.database import Base
from app.models.owner_statement import OwnerPacketSettings
from app.models.user import Organization, User, UserRole
from app.schemas.owner_statement import OwnerPacketSettingsUpdate


def _session():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, expire_on_commit=False)(), engine


def _seed(db):
    org = Organization(name="Packet Org", slug="packet-org")
    db.add(org)
    db.flush()
    admin = User(
        email="packet-admin@example.com",
        hashed_password="x",
        first_name="Packet",
        last_name="Admin",
        role=UserRole.ADMIN,
        organization_id=org.id,
        is_active=True,
    )
    db.add(admin)
    db.commit()
    return org, admin


def _allow_feature(monkeypatch):
    monkeypatch.setattr(
        owner_statements, "permission_allows_user", lambda *args, **kwargs: True
    )
    monkeypatch.setattr(
        owner_statements,
        "resolve_customer_features",
        lambda *args, **kwargs: [
            SimpleNamespace(
                key=owner_statements.PACKET_CUSTOMIZER_FEATURE,
                allowed=True,
            )
        ],
    )


def test_owner_packet_settings_default_and_update(monkeypatch):
    db, engine = _session()
    try:
        org, admin = _seed(db)
        _allow_feature(monkeypatch)

        initial = owner_statements.get_packet_settings(db=db, current_user=admin)
        assert initial.organization_id == org.id
        assert initial.included_reports == [
            "OWNER_STATEMENT",
            "PROPERTY_CASH_SUMMARY",
        ]
        assert initial.email_owner is False
        assert db.get(OwnerPacketSettings, org.id) is None

        updated = owner_statements.update_packet_settings(
            OwnerPacketSettingsUpdate(
                included_reports=["PROPERTY_CASH_SUMMARY"],
                email_owner=True,
                cover_message="September owner packet",
            ),
            db=db,
            current_user=admin,
        )
        assert updated.included_reports == ["PROPERTY_CASH_SUMMARY"]
        assert updated.email_owner is True
        assert updated.cover_message == "September owner packet"
        stored = db.get(OwnerPacketSettings, org.id)
        assert stored is not None
        assert stored.organization_id == org.id
    finally:
        db.close()
        engine.dispose()


def test_owner_packet_settings_rejects_owner_global_write():
    with pytest.raises(HTTPException) as exc:
        owner_statements._require_packet_settings_write(
            SimpleNamespace(role=UserRole.OWNER)
        )
    assert exc.value.status_code == 403


def test_owner_packet_settings_requires_feature(monkeypatch):
    monkeypatch.setattr(
        owner_statements, "permission_allows_user", lambda *args, **kwargs: True
    )
    monkeypatch.setattr(
        owner_statements, "resolve_customer_features", lambda *args, **kwargs: []
    )
    with pytest.raises(HTTPException) as exc:
        owner_statements._require_packet_customizer_feature(
            object(), SimpleNamespace(organization_id=9)
        )
    assert exc.value.status_code == 403


def test_owner_packet_reports_are_validated():
    with pytest.raises(ValueError):
        OwnerPacketSettingsUpdate(included_reports=["UNKNOWN_REPORT"])
    with pytest.raises(ValueError):
        OwnerPacketSettingsUpdate(included_reports=[])
