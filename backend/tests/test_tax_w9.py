"""W-9 evidence never enters unencrypted storage or unscoped responses."""
from __future__ import annotations

import asyncio
import json
from datetime import date
from types import SimpleNamespace

import pytest
from cryptography.fernet import Fernet
from fastapi import HTTPException, Response
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import init_db  # noqa: F401
from app.core.config import settings
from app.core.database import Base
from app.models.audit_log import AuditLog
from app.models.tax_profile import TaxProfile
from app.models.tax_w9_document import TaxW9Document
from app.models.user import Organization, User, UserRole
from app.routers import tax_w9 as routes
from app.services import tax_profiles, tax_w9
from app.services.entity_notes import _model_for_table


PDF = b"%PDF-1.7\n1 0 obj\n<< /Type /Catalog /Secret (private 123-45-6789) >>\nendobj\ntrailer\n<<>>\n%%EOF\n"
RECEIVED = date(2026, 9, 25)


@pytest.fixture
def setup(monkeypatch):
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    db = sessionmaker(bind=engine, expire_on_commit=False)()
    key = Fernet.generate_key().decode()
    monkeypatch.setattr(settings, "TAX_PROFILE_ENCRYPTION_KEY", key)
    monkeypatch.setattr(settings, "TAX_PROFILE_PREVIOUS_KEYS_JSON", "[]")
    monkeypatch.setattr(tax_profiles, "permission_allows_user", lambda *a, **kw: True)
    org = Organization(name="Signed W9 One", slug="signed-w9-one")
    other = Organization(name="Signed W9 Two", slug="signed-w9-two")
    db.add_all([org, other])
    db.flush()
    users = []
    for idx, (scope, role) in enumerate((
        (org, UserRole.ADMIN), (org, UserRole.OWNER),
        (other, UserRole.ADMIN), (other, UserRole.OWNER),
        (org, UserRole.MANAGER), (org, UserRole.VENDOR),
    )):
        user = User(
            organization_id=scope.id, role=role,
            email=f"w9-{idx}@example.com", hashed_password="x",
            first_name="W9", last_name=str(idx), is_active=True,
        )
        db.add(user)
        users.append(user)
    db.flush()
    profiles = []
    for who, typ in ((users[1], "OWNER"), (users[3], "OWNER"), (users[5], "VENDOR")):
        row = TaxProfile(
            organization_id=who.organization_id, subject_type=typ,
            subject_id=who.id,
            encrypted_payload=Fernet(key.encode()).encrypt(
                json.dumps({"tin": "123456789"}).encode()).decode(),
        )
        db.add(row)
        profiles.append(row)
    db.commit()
    try:
        yield SimpleNamespace(db=db, engine=engine, key=key, users=users, profiles=profiles)
    finally:
        db.close()
        engine.dispose()


def _save(ctx, user=None, profile=None, pdf=PDF, signed=True):
    return tax_w9.archive_signed_w9(
        ctx.db, current_user=user or ctx.users[0],
        tax_profile_id=(profile or ctx.profiles[0]).id,
        contents=pdf, received_on=RECEIVED,
        signed_original_confirmed=signed,
    )


def test_ciphertext_metadata_audit_and_download_headers(setup):
    ctx = setup
    saved = _save(ctx)
    row = ctx.db.query(TaxW9Document).one()
    assert row.encrypted_pdf != PDF
    assert b"123-45-6789" not in row.encrypted_pdf
    assert row.organization_id == ctx.users[0].organization_id
    assert saved.model_dump().keys() == {
        "id", "tax_profile_id", "size_bytes", "received_on", "uploaded_at", "uploaded_by_id",
    }
    assert ctx.db.query(TaxProfile).filter_by(id=saved.tax_profile_id).one().w9_on_file
    docs = tax_w9.list_archived_w9(ctx.db, current_user=ctx.users[0],
                                    tax_profile_id=saved.tax_profile_id)
    assert len(docs) == 1 and docs[0].id == saved.id
    response = routes.download_w9_document(
        saved.tax_profile_id, saved.id, db=ctx.db, current_user=ctx.users[0])
    assert response.body == PDF
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["content-disposition"].startswith("attachment;")
    assert response.headers["x-content-type-options"] == "nosniff"
    logs = ctx.db.query(AuditLog).order_by(AuditLog.id).all()
    assert [row.action for row in logs] == ["archived", "metadata_listed", "downloaded"]
    for log in logs:
        assert "123-45-6789" not in str(log.new_value)
        assert "private" not in str(log.new_value)
    assert ctx.db.query(TaxW9Document).count() == 1


def test_cross_organization_role_revocation_and_other_profile_probes(setup):
    ctx = setup
    saved = _save(ctx)
    for user, profile in (
        (ctx.users[2], ctx.profiles[0]),
        (ctx.users[4], ctx.profiles[0]),
        (ctx.users[1], ctx.profiles[0]),
        (ctx.users[0], ctx.profiles[1]),
    ):
        with pytest.raises(HTTPException) as exc:
            tax_w9.download_archived_w9(
                ctx.db, current_user=user, tax_profile_id=profile.id,
                document_id=saved.id,
            )
        assert exc.value.status_code in {403, 404}
    ctx.users[0].is_active = False
    ctx.db.commit()
    with pytest.raises(HTTPException) as exc:
        tax_w9.list_archived_w9(
            ctx.db, current_user=ctx.users[0], tax_profile_id=saved.tax_profile_id)
    assert exc.value.status_code == 403


def test_invalid_documents_and_missing_key_never_write_plaintext(setup, monkeypatch):
    ctx = setup
    for pdf, signed, code in (
        (b"", True, 422), (b"%PDF-1.4 not really a PDF", True, 422),
        (b"x" * (tax_w9.MAX_W9_BYTES + 1), True, 413),
        (PDF, False, 422),
    ):
        with pytest.raises(HTTPException) as exc:
            _save(ctx, pdf=pdf, signed=signed)
        assert exc.value.status_code == code
    monkeypatch.setattr(settings, "TAX_PROFILE_ENCRYPTION_KEY", "")
    with pytest.raises(HTTPException) as exc:
        _save(ctx)
    assert exc.value.status_code == 503
    assert ctx.db.query(TaxW9Document).count() == 0
    assert not ctx.db.query(TaxProfile).filter_by(id=ctx.profiles[0].id).one().w9_on_file


def test_corrupted_ciphertext_and_previous_key_decryption(setup, monkeypatch):
    ctx = setup
    doc = _save(ctx)
    row = ctx.db.query(TaxW9Document).one()
    old_key = ctx.key
    new_key = Fernet.generate_key().decode()
    monkeypatch.setattr(settings, "TAX_PROFILE_ENCRYPTION_KEY", new_key)
    monkeypatch.setattr(settings, "TAX_PROFILE_PREVIOUS_KEYS_JSON", json.dumps([old_key]))
    assert tax_w9.download_archived_w9(
        ctx.db, current_user=ctx.users[0], tax_profile_id=doc.tax_profile_id,
        document_id=doc.id) == PDF
    renewed = _save(ctx)
    Fernet(new_key.encode()).decrypt(
        ctx.db.query(TaxW9Document).filter_by(id=renewed.id).one().encrypted_pdf)
    row.encrypted_pdf = b"broken-ciphertext"
    ctx.db.commit()
    with pytest.raises(HTTPException) as exc:
        tax_w9.download_archived_w9(
            ctx.db, current_user=ctx.users[0], tax_profile_id=doc.tax_profile_id,
            document_id=doc.id)
    assert exc.value.status_code == 503


def test_generic_note_and_attachment_lookup_denied(setup):
    ctx = setup
    _save(ctx)
    with pytest.raises(HTTPException) as exc:
        _model_for_table("tax_w9_documents")
    assert exc.value.status_code == 404


def test_raw_upload_stream_bounds_and_authorization(setup):
    ctx = setup
    class FakeRequest:
        def __init__(self, pdf, content_type="application/pdf", length=None):
            self.pdf = pdf
            self.headers = {"content-type": content_type}
            if length is not None:
                self.headers["content-length"] = length
        async def stream(self):
            for i in range(0, len(self.pdf), 7):
                yield self.pdf[i:i+7]

    async def invoke(req, who=None):
        return await routes.upload_w9_document(
            ctx.profiles[0].id, req, Response(),
            received_on=RECEIVED, signed_original_confirmed=True,
            db=ctx.db, current_user=who or ctx.users[0],
        )
    saved = asyncio.run(invoke(FakeRequest(PDF)))
    assert saved.size_bytes == len(PDF)
    for req, code in (
        (FakeRequest(PDF, "multipart/form-data"), 415),
        (FakeRequest(PDF, length="invalid"), 400),
        (FakeRequest(PDF, length=str(tax_w9.MAX_W9_BYTES + 1)), 413),
        (FakeRequest(b"x" * (tax_w9.MAX_W9_BYTES + 1)), 413),
    ):
        with pytest.raises(HTTPException) as exc:
            asyncio.run(invoke(req))
        assert exc.value.status_code == code
    with pytest.raises(HTTPException) as exc:
        asyncio.run(invoke(FakeRequest(PDF), who=ctx.users[4]))
    assert exc.value.status_code == 403
    assert ctx.db.query(TaxW9Document).count() == 1
