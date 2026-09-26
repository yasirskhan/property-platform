from __future__ import annotations

import asyncio
from io import BytesIO

import pytest
from fastapi import HTTPException, UploadFile
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from starlette.datastructures import Headers

import init_db  # noqa: F401
from app.core.config import settings
from app.core.database import Base
from app.core.security import hash_password
from app.models.entity_attachment import EntityAttachment
from app.models.tax_profile import TaxProfile
from app.models.property import Property, PropertyType
from app.models.release_gate import ReleaseGate, ReleaseStage
from app.models.user import Organization, User, UserRole
from app.routers.entity_attachments import (
    delete_entity_attachment,
    download_entity_attachment,
    list_entity_attachments,
    upload_entity_attachment,
)
from app.services.attachment_storage import attachment_path


def _session():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, expire_on_commit=False)(), engine


def _seed(db):
    org = Organization(name="Attachment Org", slug="attachment-org")
    other = Organization(name="Other Attachment Org", slug="other-attachment-org")
    db.add_all([org, other])
    db.flush()
    admin = User(
        email="attachment-admin@example.com",
        hashed_password=hash_password("test1234"),
        first_name="Attachment",
        last_name="Admin",
        role=UserRole.ADMIN,
        organization_id=org.id,
        is_active=True,
    )
    other_admin = User(
        email="other-attachment-admin@example.com",
        hashed_password=hash_password("test1234"),
        first_name="Other",
        last_name="Admin",
        role=UserRole.ADMIN,
        organization_id=other.id,
        is_active=True,
    )
    prop = Property(
        organization_id=org.id,
        name="Attachment Property",
        property_type=PropertyType.MULTI_FAMILY,
        address_line1="100 Attachment Ave",
        city="Cleveland",
        state="OH",
        zip_code="44113",
        country="USA",
        is_active=True,
    )
    db.add_all([admin, other_admin, prop])
    db.add(ReleaseGate(key="release.documents.attachments", stage=ReleaseStage.ALL_ORGS, description="Universal attachments"))
    db.commit()
    return org, other, admin, other_admin, prop


def _pdf(name: str = "lease.pdf") -> UploadFile:
    return UploadFile(
        file=BytesIO(b"%PDF-1.4 test attachment"),
        filename=name,
        headers=Headers({"content-type": "application/pdf"}),
    )


def test_attachment_upload_list_download_and_soft_remove(tmp_path):
    db, engine = _session()
    old_upload_dir = settings.UPLOAD_DIR
    settings.UPLOAD_DIR = str(tmp_path)
    try:
        org, _other, admin, _other_admin, prop = _seed(db)
        created = asyncio.run(
            upload_entity_attachment(
                entity_type="properties",
                entity_id=prop.id,
                file=_pdf(),
                share_with_tenants=True,
                share_with_owners=False,
                db=db,
                current_user=admin,
            )
        )
        assert created.organization_id == org.id
        assert created.original_name == "lease.pdf"
        assert created.share_with_tenants is True
        assert created.size_bytes > 0

        stored = db.query(EntityAttachment).filter(EntityAttachment.id == created.id).one()
        assert attachment_path(stored.storage_key).exists()

        listed = list_entity_attachments(entity_type="properties", entity_id=prop.id, db=db, current_user=admin)
        assert listed.total == 1
        response = download_entity_attachment(attachment_id=created.id, db=db, current_user=admin)
        assert response.filename == "lease.pdf"

        delete_entity_attachment(attachment_id=created.id, db=db, current_user=admin)
        db.refresh(stored)
        assert stored.is_active is False
        assert stored.deleted_at is not None
        assert attachment_path(stored.storage_key).exists()
        assert list_entity_attachments(entity_type="properties", entity_id=prop.id, db=db, current_user=admin).total == 0
    finally:
        settings.UPLOAD_DIR = old_upload_dir
        db.close()
        engine.dispose()


def test_attachment_target_is_organization_scoped(tmp_path):
    db, engine = _session()
    old_upload_dir = settings.UPLOAD_DIR
    settings.UPLOAD_DIR = str(tmp_path)
    try:
        _org, _other, admin, other_admin, prop = _seed(db)
        created = asyncio.run(
            upload_entity_attachment(
                entity_type="properties",
                entity_id=prop.id,
                file=_pdf(),
                share_with_tenants=False,
                share_with_owners=False,
                db=db,
                current_user=admin,
            )
        )
        with pytest.raises(HTTPException) as exc:
            download_entity_attachment(attachment_id=created.id, db=db, current_user=other_admin)
        assert exc.value.status_code == 404
        with pytest.raises(HTTPException) as exc:
            list_entity_attachments(entity_type="properties", entity_id=prop.id, db=db, current_user=other_admin)
        assert exc.value.status_code == 403
    finally:
        settings.UPLOAD_DIR = old_upload_dir
        db.close()
        engine.dispose()


def test_attachment_feature_fails_closed_when_release_gate_hidden(tmp_path):
    db, engine = _session()
    old_upload_dir = settings.UPLOAD_DIR
    settings.UPLOAD_DIR = str(tmp_path)
    try:
        _org, _other, admin, _other_admin, prop = _seed(db)
        gate = db.query(ReleaseGate).filter(ReleaseGate.key == "release.documents.attachments").one()
        gate.stage = ReleaseStage.HIDDEN
        db.commit()
        with pytest.raises(HTTPException) as exc:
            list_entity_attachments(entity_type="properties", entity_id=prop.id, db=db, current_user=admin)
        assert exc.value.status_code == 404
    finally:
        settings.UPLOAD_DIR = old_upload_dir
        db.close()
        engine.dispose()



def test_tax_profiles_refuse_generic_unencrypted_attachments(tmp_path):
    db, engine = _session()
    old_upload_dir = settings.UPLOAD_DIR
    settings.UPLOAD_DIR = str(tmp_path)
    try:
        org, _other, admin, _other_admin, _property = _seed(db)
        tax = TaxProfile(
            organization_id=org.id, subject_type="ORGANIZATION",
            subject_id=org.id, encrypted_payload="ciphertext-only",
        )
        db.add(tax)
        db.commit()
        with pytest.raises(HTTPException) as exc:
            list_entity_attachments(entity_type="tax_profiles", entity_id=tax.id,
                                    db=db, current_user=admin)
        assert exc.value.status_code == 404
        with pytest.raises(HTTPException) as exc:
            asyncio.run(upload_entity_attachment(
                entity_type="tax_profiles", entity_id=tax.id,
                file=_pdf("sensitive-w9.pdf"), share_with_tenants=False,
                share_with_owners=False, db=db, current_user=admin,
            ))
        assert exc.value.status_code == 404
        assert db.query(EntityAttachment).count() == 0
    finally:
        settings.UPLOAD_DIR = old_upload_dir
        db.close()
        engine.dispose()
