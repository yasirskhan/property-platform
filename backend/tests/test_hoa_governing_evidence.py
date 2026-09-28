"""Association-specific document references never certify governing authority."""
from __future__ import annotations

from types import SimpleNamespace
import pytest
from fastapi import HTTPException, Response
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import init_db  # noqa: F401
from app.core.database import Base
from app.models.audit_log import AuditLog
from app.models.charge import Charge
from app.models.entity_attachment import EntityAttachment
from app.models.gl_transaction import GLTransaction
from app.models.hoa_governing_evidence import HOAGoverningEvidence
from app.models.lease import Lease
from app.models.property import Property, PropertyAssignment
from app.models.user import Organization, User, UserRole
from app.routers import hoa_associations as hoa
from app.routers import hoa_governing_evidence as api
from app.routers import entity_attachments as attachments
from app.schemas.hoa_association import HOAAssociationIn
from app.schemas.hoa_governing_evidence import HOAEvidenceLinkIn
from app.schemas.entity_attachment import EntityAttachmentShareUpdate
from app.services.entity_notes import _model_for_table


@pytest.fixture(autouse=True)
def grants(monkeypatch):
    monkeypatch.setattr(hoa, "permission_allows_user", lambda *a, **kw: True)
    monkeypatch.setattr(hoa, "resolve_customer_features", lambda *a, **kw: [
        SimpleNamespace(key=hoa.FEATURE_KEY, allowed=True)
    ])
    monkeypatch.setattr(api, "resolve_customer_features", lambda *a, **kw: [
        SimpleNamespace(key=api.ATTACHMENT_FEATURE, allowed=True)
    ])
    monkeypatch.setattr(attachments, "resolve_customer_features", lambda *a, **kw: [
        SimpleNamespace(key=attachments.ATTACHMENTS_FEATURE_KEY, allowed=True)
    ])
    monkeypatch.setattr(
        __import__("app.services.entity_notes", fromlist=["permission_allows_user"]),
        "permission_allows_user", lambda *a, **kw: True,
    )


def _db():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, expire_on_commit=False)(), engine


def _seed(db):
    org = Organization(name="HOA Evidence", slug="hoa-evidence")
    foreign_org = Organization(name="Foreign HOA Evidence", slug="foreign-hoa-evidence")
    db.add_all([org, foreign_org]); db.flush()
    users = []
    for scope, role, name in (
        (org, UserRole.ADMIN, "admin"), (org, UserRole.OWNER, "owner"),
        (org, UserRole.MANAGER, "manager"), (org, UserRole.CREW, "crew"),
        (org, UserRole.TENANT, "tenant"), (foreign_org, UserRole.ADMIN, "foreign"),
    ):
        row = User(organization_id=scope.id, role=role,
                   first_name=name, last_name="Evidence",
                   email=f"hoa-evidence-{name}@example.test",
                   hashed_password="x", is_active=True)
        db.add(row); users.append(row)
    db.flush()
    props = []
    for scope, name in ((org, "Assigned"), (org, "Unassigned"), (foreign_org, "Foreign")):
        row = Property(organization_id=scope.id, name=name,
                       address_line1="100 Main", city="Cleveland",
                       state="OH", zip_code="44113", is_active=True)
        db.add(row); props.append(row)
    db.flush()
    db.add(PropertyAssignment(
        property_id=props[0].id, user_id=users[2].id,
        role=UserRole.MANAGER, is_active=True,
    ))
    db.commit()
    association = hoa.create_association(
        HOAAssociationIn(name="Staff HOA", property_ids=[props[0].id, props[1].id]),
        db=db, current_user=users[0],
    )
    attached = []
    for scope, prop, label in (
        (org, props[0], "private.pdf"), (org, props[0], "shared.pdf"),
        (org, props[1], "elsewhere.pdf"), (foreign_org, props[2], "foreign.pdf"),
        (org, props[0], "not-document.csv"),
    ):
        row = EntityAttachment(
            organization_id=scope.id, entity_type="properties", entity_id=prop.id,
            storage_key="staff-"+label, original_name=label,
            content_type="application/pdf", size_bytes=10,
            share_with_tenants=label=="shared.pdf",
            share_with_owners=False, is_active=True,
        )
        db.add(row); attached.append(row)
    db.commit()
    return users, props, association, attached


def _payload(prop, attach, **change):
    data = {"property_id": prop.id, "attachment_id": attach.id, "evidence_type": "BYLAWS"}
    data.update(change)
    return HOAEvidenceLinkIn(**data)


def test_evidence_link_is_private_unverified_scoped_and_not_finance():
    db, engine = _db()
    try:
        (admin, owner, manager, crew, tenant, foreign), (assigned, unassigned, outside), assoc, docs = _seed(db)
        created = api.link_evidence(assoc.id, _payload(assigned, docs[0]), db=db, current_user=admin)
        assert created.status == "STAFF_SUPPLIED_UNVERIFIED"
        assert created.filename == "private.pdf"
        assert "approved" not in created.model_dump()
        response = Response()
        assert [v.id for v in api.list_evidence(assoc.id, response, assigned.id, db=db, current_user=manager)] == [created.id]
        assert response.headers["cache-control"] == "no-store"
        assert api.list_evidence(assoc.id, Response(), unassigned.id, db=db, current_user=owner) == []
        assert db.query(AuditLog).filter(AuditLog.entity_type=="hoa_governing_evidence").count()==1
        assert db.query(Charge).count() == db.query(GLTransaction).count() == db.query(Lease).count() == 0
        with pytest.raises(HTTPException) as e:
            api.link_evidence(assoc.id, _payload(assigned, docs[0]), db=db, current_user=owner)
        assert e.value.status_code == 409
        for candidate in (docs[1], docs[2], docs[3], docs[4]):
            with pytest.raises(HTTPException) as e:
                api.link_evidence(assoc.id, _payload(assigned, candidate), db=db, current_user=owner)
            assert e.value.status_code == 404
        for actor in (manager, crew, tenant, foreign):
            with pytest.raises(HTTPException):
                api.link_evidence(assoc.id, _payload(assigned, docs[0]), db=db, current_user=actor)
        for actor in (crew, tenant, foreign):
            with pytest.raises(HTTPException):
                api.list_evidence(assoc.id, Response(), assigned.id, db=db, current_user=actor)
        with pytest.raises(ValidationError):
            _payload(assigned, docs[0], approved=True)
        with pytest.raises(HTTPException):
            _model_for_table("hoa_governing_evidence")
    finally:
        db.close(); engine.dispose()


def test_evidence_gated_generic_attachment_access_and_sharing():
    db, engine = _db()
    try:
        (admin, owner, manager, crew, tenant, foreign), (assigned, _unused, _outside), assoc, docs = _seed(db)
        api.link_evidence(assoc.id, _payload(assigned, docs[0]), db=db, current_user=admin)
        view = attachments.list_entity_attachments(
            "properties", assigned.id, db=db, current_user=manager,
        )
        assert docs[0].id in [row.id for row in view.items]
        crew_items = attachments.list_entity_attachments(
            "properties", assigned.id, db=db, current_user=crew,
        )
        assert docs[0].id not in [row.id for row in crew_items.items]
        with pytest.raises(HTTPException):
            attachments.download_entity_attachment(docs[0].id, db=db, current_user=crew)
        with pytest.raises(HTTPException) as e:
            attachments.update_entity_attachment_sharing(
                docs[0].id, EntityAttachmentShareUpdate(share_with_owners=True),
                db=db, current_user=admin,
            )
        assert e.value.status_code == 403
        with pytest.raises(HTTPException):
            attachments.delete_entity_attachment(docs[0].id, db=db, current_user=manager)
        with pytest.raises(HTTPException):
            attachments.download_entity_attachment(docs[0].id, db=db, current_user=foreign)
        assert docs[0].share_with_owners is False
    finally:
        db.close(); engine.dispose()


def test_evidence_unlink_archive_and_permission_revocation(monkeypatch):
    db, engine = _db()
    try:
        (admin, owner, manager, crew, tenant, foreign), (assigned, unassigned, _other), assoc, docs = _seed(db)
        saved = api.link_evidence(assoc.id, _payload(assigned, docs[0]), db=db, current_user=admin)
        assoc_new = hoa.update_association(
            assoc.id, HOAAssociationIn(name="Staff HOA", property_ids=[unassigned.id]),
            db=db, current_user=owner,
        )
        assert api.list_evidence(assoc.id, Response(), unassigned.id, db=db, current_user=admin) == []
        row = db.query(HOAGoverningEvidence).filter_by(id=saved.id).one()
        assert row.is_active is False
        hoa.update_association(
            assoc_new.id, HOAAssociationIn(name="Staff HOA", property_ids=[assigned.id, unassigned.id]),
            db=db, current_user=owner,
        )
        assert api.list_evidence(assoc.id, Response(), assigned.id, db=db, current_user=admin) == []
        with pytest.raises(HTTPException) as e:
            api.link_evidence(assoc.id, _payload(assigned, docs[0]), db=db, current_user=admin)
        assert e.value.status_code == 409
        second = api.link_evidence(assoc.id, _payload(unassigned, docs[2]), db=db, current_user=owner)
        hoa.archive_association(assoc.id, db=db, current_user=admin)
        assert db.query(HOAGoverningEvidence).filter_by(id=second.id).one().is_active is False
    finally:
        db.close(); engine.dispose()


def test_attachment_feature_and_live_role_revocation(monkeypatch):
    db, engine = _db()
    try:
        (admin, owner, manager, crew, tenant, foreign), (assigned, unused, other), assoc, docs = _seed(db)
        api.link_evidence(assoc.id, _payload(assigned, docs[0]), db=db, current_user=admin)
        monkeypatch.setattr(api, "resolve_customer_features", lambda *a, **kw: [])
        with pytest.raises(HTTPException) as e:
            api.list_evidence(assoc.id, Response(), assigned.id, db=db, current_user=admin)
        assert e.value.status_code == 404
        monkeypatch.setattr(api, "resolve_customer_features", lambda *a, **kw: [
            SimpleNamespace(key=api.ATTACHMENT_FEATURE, allowed=True)
        ])
        manager.is_active = False; db.commit()
        with pytest.raises(HTTPException) as e:
            api.list_evidence(assoc.id, Response(), assigned.id, db=db, current_user=manager)
        assert e.value.status_code == 403
        assert db.query(GLTransaction).count() == db.query(Charge).count() == 0
    finally:
        db.close(); engine.dispose()
