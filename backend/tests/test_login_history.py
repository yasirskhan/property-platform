from __future__ import annotations

import json

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from starlette.requests import Request

import init_db  # noqa: F401
import app.routers.auth as auth_router
import app.routers.my_settings as my_settings_router
from app.core.database import Base
from app.core.security import hash_password
from app.models.audit_log import AuditLog
from app.models.user import Organization, User, UserRole
from app.schemas.auth import LoginRequest
from app.services.login_history import record_login_event


def _session():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, expire_on_commit=False)(), engine


def _request(ip: str = "203.0.113.9", user_agent: str = "pytest-browser/1.0") -> Request:
    return Request({"type": "http", "http_version": "1.1", "method": "POST", "scheme": "https", "path": "/auth/login", "raw_path": b"/auth/login", "query_string": b"", "headers": [(b"user-agent", user_agent.encode("utf-8"))], "client": (ip, 43123), "server": ("testserver", 443)})


def _seed(db):
    org = Organization(name="Login History Org", slug="login-history-org")
    db.add(org)
    db.flush()
    user = User(email="history@example.com", hashed_password=hash_password("test1234"), first_name="History", last_name="User", role=UserRole.ADMIN, organization_id=org.id, is_active=True)
    other = User(email="other-history@example.com", hashed_password=hash_password("test1234"), first_name="Other", last_name="User", role=UserRole.MANAGER, organization_id=org.id, is_active=True)
    db.add_all([user, other])
    db.commit()
    return user, other


def test_login_records_success_and_known_user_failure():
    db, engine = _session()
    try:
        user, _ = _seed(db)
        result = auth_router.login(LoginRequest(email=user.email, password="test1234"), request=_request(), db=db)
        assert result.access_token
        with pytest.raises(HTTPException) as exc:
            auth_router.login(LoginRequest(email=user.email, password="wrong-password"), request=_request(ip="203.0.113.10", user_agent="bad-client"), db=db)
        assert exc.value.status_code == 401
        rows = db.query(AuditLog).filter(AuditLog.entity_type == "user_login", AuditLog.entity_id == user.id).order_by(AuditLog.id.asc()).all()
        assert [row.action for row in rows] == ["login_success", "login_failed"]
        assert rows[0].ip_address == "203.0.113.9"
        assert json.loads(rows[0].new_value)["user_agent"] == "pytest-browser/1.0"
        assert json.loads(rows[1].new_value)["reason"] == "invalid_credentials"
    finally:
        db.close()
        engine.dispose()


def test_login_history_is_self_only_and_newest_first():
    db, engine = _session()
    try:
        user, other = _seed(db)
        record_login_event(db, user=other, request=_request(ip="198.51.100.1"), success=True, auth_method="PASSWORD")
        first = record_login_event(db, user=user, request=_request(ip="198.51.100.2"), success=False, auth_method="PASSWORD", reason="invalid_credentials")
        second = record_login_event(db, user=user, request=_request(ip="198.51.100.3"), success=True, auth_method="TWO_FACTOR")
        db.commit()
        items = my_settings_router.get_login_history(limit=20, db=db, current_user=user)
        assert [item.id for item in items] == [second.id, first.id]
        assert [item.status for item in items] == ["SUCCESS", "FAILED"]
        assert items[0].auth_method == "TWO_FACTOR"
        assert items[0].ip_address == "198.51.100.3"
        assert all(item.ip_address != "198.51.100.1" for item in items)
    finally:
        db.close()
        engine.dispose()
