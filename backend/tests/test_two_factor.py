from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from starlette.requests import Request

import init_db  # noqa: F401
import app.routers.auth as auth_router
from app.core.database import Base
from app.core.security import decode_access_token, decode_two_factor_challenge_token, hash_password
from app.models.user import Organization, User, UserRole
from app.schemas.auth import LoginRequest
from app.schemas.two_factor import TwoFactorLoginVerifyRequest
from app.services.two_factor import (
    begin_setup,
    decrypt_secret,
    enable,
    get_settings,
    totp_code,
    verify_login_code,
)


def _session():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, expire_on_commit=False)(), engine


def _request() -> Request:
    return Request({"type": "http", "http_version": "1.1", "method": "POST", "scheme": "https", "path": "/auth/login", "raw_path": b"/auth/login", "query_string": b"", "headers": [(b"user-agent", b"pytest-mfa")], "client": ("203.0.113.20", 41000), "server": ("testserver", 443)})


def _user(db):
    org = Organization(name="MFA Org", slug="mfa-org")
    db.add(org)
    db.flush()
    user = User(
        email="mfa@example.com",
        hashed_password=hash_password("test1234"),
        first_name="MFA",
        last_name="User",
        role=UserRole.ADMIN,
        organization_id=org.id,
        is_active=True,
    )
    db.add(user)
    db.commit()
    return user


def test_two_factor_setup_encrypts_secret_and_hashes_recovery_codes():
    db, engine = _session()
    try:
        user = _user(db)
        row, secret, codes = begin_setup(db, user=user)
        db.commit()

        assert secret not in row.secret_ciphertext
        assert decrypt_secret(row.secret_ciphertext) == secret
        assert len(codes) == 10
        assert all(code not in row.recovery_code_hashes for code in codes)
        assert row.is_enabled is False
    finally:
        db.close()
        engine.dispose()


def test_enabled_two_factor_blocks_normal_token_until_challenge_is_verified():
    db, engine = _session()
    try:
        user = _user(db)
        row, secret, _ = begin_setup(db, user=user)
        enable(db, user=user, code=totp_code(secret))
        db.commit()

        login = auth_router.login(LoginRequest(email=user.email, password="test1234"), request=_request(), db=db)
        assert login.two_factor_required is True
        assert login.access_token is None
        assert login.challenge_token
        assert decode_access_token(login.challenge_token) is None
        challenge = decode_two_factor_challenge_token(login.challenge_token)
        assert challenge is not None
        assert challenge["sub"] == str(user.id)

        verified = auth_router.verify_two_factor_login(
            TwoFactorLoginVerifyRequest(
                challenge_token=login.challenge_token,
                code=totp_code(secret),
            ),
            request=_request(),
            db=db,
        )
        assert verified.two_factor_required is False
        assert verified.access_token
        payload = decode_access_token(verified.access_token)
        assert payload is not None and payload["sub"] == str(user.id)
    finally:
        db.close()
        engine.dispose()


def test_recovery_code_is_one_time():
    db, engine = _session()
    try:
        user = _user(db)
        row, secret, codes = begin_setup(db, user=user)
        enable(db, user=user, code=totp_code(secret))
        db.commit()

        code = codes[0]
        assert verify_login_code(db, row=row, code=code) is True
        db.commit()
        db.refresh(row)
        assert len(row.recovery_code_hashes) == 9
        assert verify_login_code(db, row=row, code=code) is False
    finally:
        db.close()
        engine.dispose()


def test_user_without_two_factor_keeps_existing_login_contract():
    db, engine = _session()
    try:
        user = _user(db)
        login = auth_router.login(LoginRequest(email=user.email, password="test1234"), request=_request(), db=db)
        assert login.two_factor_required is False
        assert login.challenge_token is None
        assert login.access_token
        assert decode_access_token(login.access_token)["sub"] == str(user.id)
        assert get_settings(db, user.id) is None
    finally:
        db.close()
        engine.dispose()
