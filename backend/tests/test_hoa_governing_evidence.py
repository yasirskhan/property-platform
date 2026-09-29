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
        SimpleNamespace(key=hoa.FEATURE_KEY, allowed=True),
        SimpleNamespace(key=hoa.HOA_FEATURE_KEY, allowed=True)
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
    db.add(PropertyAssignment(
        property_id=props[0].id, user_id=users[3].id,
        role=UserRole.CREW, is_active=True,
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


def test_meeting_minutes_are_private_staff_documents_not_board_approval():
    db, engine = _db()
    try:
        (admin, owner, manager, crew, tenant, foreign), (assigned, _, _), assoc, docs = _seed(db)
        saved = api.link_evidence(
            assoc.id, _payload(assigned, docs[0], evidence_type="MEETING_MINUTES"),
            db=db, current_user=admin,
        )
        assert saved.evidence_type == "MEETING_MINUTES"
        assert saved.status == "STAFF_SUPPLIED_UNVERIFIED"
        records = api.list_evidence(
            assoc.id, Response(), assigned.id, db=db, current_user=manager,
        )
        assert [x.id for x in records] == [saved.id]
        for actor in (crew, tenant, foreign):
            with pytest.raises(HTTPException):
                attachments.download_entity_attachment(
                    docs[0].id, db=db, current_user=actor,
                )
        with pytest.raises(ValidationError):
            _payload(assigned, docs[0], official_minutes=True)
        assert db.query(GLTransaction).count() == db.query(Charge).count() == 0
    finally:
        db.close()
        engine.dispose()



def _delivery_subject(db, *, admin, tenant, prop, association, document):
    from app.models.contact import Contact
    from app.schemas.hoa_association import HOAContactLinkIn

    tenant.is_verified = True
    contact = Contact(
        organization_id=admin.organization_id,
        display_name="Verified HOA recipient", contact_type="PERSON",
        email=tenant.email, is_active=True,
    )
    db.add(contact); db.flush()
    link = hoa.add_contact_link(
        association.id, HOAContactLinkIn(
            property_id=prop.id, contact_id=contact.id,
        ), db=db, current_user=admin,
    )
    evidence = api.link_evidence(
        association.id, _payload(prop, document),
        db=db, current_user=admin,
    )
    return contact, link, evidence


def test_governing_document_real_smtp_attachment_idempotency_and_audit(monkeypatch, tmp_path):
    import hashlib
    from app.routers import hoa_document_delivery as delivery
    from app.models.hoa_document_delivery import HOADocumentDelivery
    from app.schemas.hoa_document_delivery import HOADocumentSendIn
    from app.services.entity_notes import _model_for_table

    db, engine = _db()
    try:
        (admin, owner, manager, crew, tenant, foreign), (prop, _, _), assoc, docs = _seed(db)
        _contact, link, evidence = _delivery_subject(
            db, admin=admin, tenant=tenant, prop=prop,
            association=assoc, document=docs[0],
        )
        data = b"%PDF-1.4\nX"  # Ten bytes, matching the stored fixture metadata.
        assert len(data) == docs[0].size_bytes
        source = tmp_path / "document.pdf"
        source.write_bytes(data)
        monkeypatch.setattr(delivery, "attachment_path", lambda key: source)
        sent = []
        def capture(**kwargs):
            sent.append(kwargs)
        monkeypatch.setattr(
            delivery, "email_service",
            SimpleNamespace(settings=SimpleNamespace(EMAIL_MODE="smtp"), send_email=capture),
        )
        before = (db.query(Charge).count(), db.query(GLTransaction).count(), db.query(Lease).count())
        payload = HOADocumentSendIn(
            property_id=prop.id, contact_link_id=link.id,
            request_key="hoa-doc-delivery-001",
        )
        eligible = delivery.eligible_recipients(
            assoc.id, Response(), prop.id, db=db, current_user=owner,
        )
        assert [(x.contact_link_id, x.contact_name) for x in eligible] == [
            (link.id, "Verified HOA recipient"),
        ]
        issued = delivery.send_document(
            assoc.id, evidence.id, payload, db=db, current_user=admin,
        )
        assert issued.status == "SMTP_ACCEPTED" and issued.attempt_count == 1
        assert issued.email_attachment_included is True
        assert issued.recipient_delivery_confirmed is False and issued.legally_served is False
        assert issued.file_sha256 == hashlib.sha256(data).hexdigest()
        assert len(sent) == 1 and sent[0]["to"] == tenant.email
        assert sent[0]["attachments"][0] == ("private.pdf", data, "application/pdf")
        again = delivery.send_document(
            assoc.id, evidence.id, payload, db=db, current_user=owner,
        )
        assert again.id == issued.id and len(sent) == 1
        again = delivery.retry_document(
            assoc.id, issued.id, prop.id, db=db, current_user=owner,
        )
        assert again.status == "SMTP_ACCEPTED" and len(sent) == 1
        assert db.query(HOADocumentDelivery).count() == 1
        listing = delivery.delivery_history(
            assoc.id, Response(), prop.id, db=db, current_user=owner,
        )
        assert len(listing) == 1 and listing[0].id == issued.id
        for invalid in [
            dict(property_id=prop.id, contact_link_id=link.id, request_key="a"),
            dict(property_id=prop.id, contact_link_id=link.id,
                 request_key="hoa-doc-delivery-001", notify_tenant=True),
        ]:
            with pytest.raises(ValidationError):
                HOADocumentSendIn(**invalid)
        with pytest.raises(HTTPException) as reused:
            delivery.send_document(
                assoc.id, evidence.id,
                HOADocumentSendIn(
                    property_id=prop.id, contact_link_id=admin.id,
                    request_key="hoa-doc-delivery-001",
                ), db=db, current_user=owner,
            )
        assert reused.value.status_code == 409
        logs = db.query(AuditLog).filter(
            AuditLog.entity_type == "hoa_document_delivery",
        ).order_by(AuditLog.id).all()
        assert len(logs) == 3
        assert all(tenant.email not in (x.new_value or "") for x in logs)
        assert all("private.pdf" not in (x.new_value or "") for x in logs)
        with pytest.raises(HTTPException) as generic:
            _model_for_table("hoa_document_deliveries")
        assert generic.value.status_code == 404
        assert before == (db.query(Charge).count(), db.query(GLTransaction).count(), db.query(Lease).count())
    finally:
        db.rollback(); db.close(); engine.dispose()


def test_governing_document_delivery_failure_retry_identity_scope_and_bytes(monkeypatch, tmp_path):
    from app.models.hoa_document_delivery import HOADocumentDelivery
    from app.routers import hoa_document_delivery as delivery
    from app.schemas.hoa_document_delivery import HOADocumentSendIn

    db, engine = _db()
    try:
        (admin, owner, manager, crew, tenant, foreign), (prop, other, _), assoc, docs = _seed(db)
        _contact, link, evidence = _delivery_subject(
            db, admin=admin, tenant=tenant, prop=prop,
            association=assoc, document=docs[0],
        )
        path = tmp_path / "private.pdf"
        path.write_bytes(b"%PDF-1.4\nX")
        monkeypatch.setattr(delivery, "attachment_path", lambda key: path)
        attempted = []
        def flaky(**kwargs):
            attempted.append(kwargs)
            if len(attempted) == 1:
                raise RuntimeError("synthetic SMTP unavailable")
        monkeypatch.setattr(
            delivery, "email_service",
            SimpleNamespace(settings=SimpleNamespace(EMAIL_MODE="smtp"), send_email=flaky),
        )
        payload = HOADocumentSendIn(
            property_id=prop.id, contact_link_id=link.id,
            request_key="hoa-document-retry-01",
        )
        for actor in (manager, crew, tenant, foreign):
            with pytest.raises(HTTPException):
                delivery.send_document(
                    assoc.id, evidence.id, payload,
                    db=db, current_user=actor,
                )
        with pytest.raises(HTTPException) as wrong_prop:
            delivery.send_document(
                assoc.id, evidence.id,
                HOADocumentSendIn(
                    property_id=other.id, contact_link_id=link.id,
                    request_key="hoa-document-other-prop",
                ), db=db, current_user=admin,
            )
        assert wrong_prop.value.status_code == 404
        outcome = delivery.send_document(
            assoc.id, evidence.id, payload, db=db, current_user=admin,
        )
        assert outcome.status == "FAILED" and len(attempted) == 1
        again = delivery.send_document(
            assoc.id, evidence.id, payload, db=db, current_user=owner,
        )
        assert again.id == outcome.id and len(attempted) == 1
        tenant.is_verified = False; db.commit()
        with pytest.raises(HTTPException) as revoked:
            delivery.retry_document(
                assoc.id, outcome.id, prop.id,
                db=db, current_user=admin,
            )
        assert revoked.value.status_code == 409 and len(attempted) == 1
        tenant.is_verified = True; db.commit()
        path.write_bytes(b"modified??")
        with pytest.raises(HTTPException) as changed:
            delivery.retry_document(
                assoc.id, outcome.id, prop.id,
                db=db, current_user=admin,
            )
        assert changed.value.status_code == 409 and len(attempted) == 1
        path.write_bytes(b"%PDF-1.4\nX")
        accepted = delivery.retry_document(
            assoc.id, outcome.id, prop.id, db=db, current_user=admin,
        )
        assert accepted.status == "SMTP_ACCEPTED" and accepted.attempt_count == 2
        assert len(attempted) == 2 and db.query(HOADocumentDelivery).count() == 1
        assert db.query(Charge).count() == db.query(GLTransaction).count() == 0
    finally:
        db.rollback(); db.close(); engine.dispose()


def test_governing_document_console_transport_never_claims_attachment_delivery(monkeypatch, tmp_path):
    from app.routers import hoa_document_delivery as delivery
    from app.schemas.hoa_document_delivery import HOADocumentSendIn

    db, engine = _db()
    try:
        (admin, owner, manager, crew, tenant, foreign), (prop, _, _), assoc, docs = _seed(db)
        _contact, link, evidence = _delivery_subject(
            db, admin=admin, tenant=tenant, prop=prop,
            association=assoc, document=docs[0],
        )
        path = tmp_path / "private.pdf"
        path.write_bytes(b"%PDF-1.4\nX")
        monkeypatch.setattr(delivery, "attachment_path", lambda key: path)
        attempted = []
        monkeypatch.setattr(
            delivery, "email_service",
            SimpleNamespace(settings=SimpleNamespace(EMAIL_MODE="console"),
                            send_email=lambda **kw: attempted.append(kw)),
        )
        request = HOADocumentSendIn(
            property_id=prop.id, contact_link_id=link.id,
            request_key="hoa-doc-test-only-01",
        )
        result = delivery.send_document(
            assoc.id, evidence.id, request, db=db, current_user=admin,
        )
        assert result.status == "TEST_ONLY" and result.accepted_at is None
        assert result.email_attachment_included is False
        assert result.recipient_delivery_confirmed is False
        assert len(attempted) == 1
        monkeypatch.setattr(delivery.email_service.settings, "EMAIL_MODE", "smtp")
        sent = delivery.retry_document(
            assoc.id, result.id, prop.id, db=db, current_user=owner,
        )
        assert sent.status == "SMTP_ACCEPTED"
        assert sent.attempt_count == 2 and len(attempted) == 2
    finally:
        db.rollback(); db.close(); engine.dispose()
