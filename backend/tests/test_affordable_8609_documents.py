"""Signed-form scan archive is ciphertext-only and not agency verification."""
from __future__ import annotations
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
from app.models.affordable_building import AffordableBuilding
from app.models.affordable_8609_document import Affordable8609Document
from app.models.affordable_program import AffordableProgram
from app.models.audit_log import AuditLog
from app.models.charge import Charge
from app.models.gl_transaction import GLTransaction
from app.models.lease import Lease
from app.models.property import Property, PropertyAssignment
from app.models.user import Organization, User, UserRole
from app.routers import affordable_programs as programs
from app.routers import affordable_8609_documents as routes
from app.services import affordable_8609_documents as service
from app.services.entity_notes import _model_for_table

PDF = b"%PDF-1.4\n" + b"Private agency form 8609 record; 123-45-6789 " + b"x"*60 + b"\n%%EOF"

@pytest.fixture(autouse=True)
def access(monkeypatch):
    monkeypatch.setattr(programs, "permission_allows_user", lambda *a, **k: True)
    monkeypatch.setattr(programs, "resolve_customer_features", lambda *a, **k: [
        SimpleNamespace(key=programs.FEATURE_KEY, allowed=True),
    ])
    monkeypatch.setattr(settings, "COMPLIANCE_DOCUMENT_ENCRYPTION_KEY",
                        Fernet.generate_key().decode("utf-8"))


def _db():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, expire_on_commit=False)(), engine


def _seed(db):
    a, b = Organization(name="8609 Archive One", slug="8609-archive-one"), Organization(name="8609 Archive Other", slug="8609-archive-other")
    db.add_all([a,b]); db.flush()
    users = []
    for org, role, label in ((a,UserRole.ADMIN,"admin"), (a,UserRole.OWNER,"owner"),
                             (a,UserRole.MANAGER,"manager"), (a,UserRole.TENANT,"tenant"),
                             (b,UserRole.ADMIN,"other")):
        u=User(organization_id=org.id,role=role,first_name=label,last_name="Archive",
               email=f"8609-archive-{label}@example.com",hashed_password="x",is_active=True)
        db.add(u);users.append(u)
    db.flush()
    props=[]; programs_list=[]; buildings=[]
    for org,label in ((a,"Assigned"),(a,"Unassigned"),(b,"Foreign")):
        prop=Property(organization_id=org.id,name=label,address_line1="10 Main",
                      city="Cleveland",state="OH",zip_code="44113",is_active=True)
        db.add(prop);db.flush()
        program=AffordableProgram(organization_id=org.id,property_id=prop.id,
                                  program_type="LIHTC",label="LIHTC",is_active=True)
        db.add(program);db.flush()
        building=AffordableBuilding(organization_id=org.id,property_id=prop.id,
                                     program_id=program.id,building_label="A",
                                     agency_bin="OH-20-12345",is_active=True)
        db.add(building);db.flush()
        props.append(prop); programs_list.append(program); buildings.append(building)
    db.add(PropertyAssignment(property_id=props[0].id,user_id=users[2].id,
                              role=UserRole.MANAGER,is_active=True))
    db.commit()
    return users,props,programs_list,buildings


def test_encrypted_8609_archive_multiple_scans_and_audit():
    db, engine=_db()
    try:
        (admin, owner, *_), (prop, *_), (program, *_), (building, *_) = _seed(db)
        def upload(actor, pdf):
            return service.archive_8609(
                db, current_user=actor, property_id=prop.id,
                program_id=program.id, building_id=building.id,
                contents=pdf, received_on=date(2026,9,26), signed_copy_reviewed=True)
        first=upload(admin,PDF)
        second=upload(owner,PDF+b"\n")
        assert first.id!=second.id
        raw=db.query(Affordable8609Document).first()
        assert raw.encrypted_pdf!=PDF
        assert b"123-45-6789" not in raw.encrypted_pdf
        assert b"Private agency form" not in raw.encrypted_pdf
        listed=routes.list_documents(prop.id,program.id,building.id,Response(),
                                      db=db,current_user=admin)
        assert len(listed)==2 and "encrypted_pdf" not in listed[0].model_dump()
        restored=service.download_8609(
            db,current_user=admin,property_id=prop.id,
            program_id=program.id,building_id=building.id,document_id=first.id)
        assert restored==PDF
        assert db.query(AuditLog).filter_by(entity_type="affordable_8609_document").count()==4
        assert not hasattr(first,"signed_by_agency") and not hasattr(first,"credit")
        for klass in (Lease,Charge,GLTransaction):
            assert db.query(klass).count()==0
    finally:db.close();engine.dispose()


def test_org_property_role_and_building_archive_denials():
    db,engine=_db()
    try:
        (admin,owner,manager,tenant,foreign),props,progs,buildings=_seed(db)
        saved=service.archive_8609(
            db,current_user=admin,property_id=props[0].id,
            program_id=progs[0].id,building_id=buildings[0].id,
            contents=PDF,received_on=date(2026,9,26),signed_copy_reviewed=True)
        for actor,ix in ((foreign,0),(admin,2),(manager,1),(manager,0),
                         (tenant,0)):
            with pytest.raises(HTTPException):
                service.list_8609(db,current_user=actor,property_id=props[ix].id,
                                  program_id=progs[ix].id,building_id=buildings[ix].id)
        with pytest.raises(HTTPException) as exc:
            service.download_8609(db,current_user=admin,property_id=props[1].id,
                                  program_id=progs[1].id,building_id=buildings[1].id,
                                  document_id=saved.id)
        assert exc.value.status_code==404
        with pytest.raises(HTTPException) as exc:
            service.list_8609(db,current_user=admin,property_id=props[0].id,
                              program_id=progs[0].id,building_id=buildings[1].id)
        assert exc.value.status_code==404
        buildings[0].is_active=False;db.flush()
        with pytest.raises(HTTPException) as exc:
            service.download_8609(db,current_user=owner,property_id=props[0].id,
                                  program_id=progs[0].id,building_id=buildings[0].id,
                                  document_id=saved.id)
        assert exc.value.status_code==404
    finally:db.rollback();db.close();engine.dispose()


def test_pdf_validation_crypto_configuration_tamper_and_generic_target(monkeypatch):
    db,engine=_db()
    try:
        (admin,*_), (prop,*_), (program,*_), (building,*_) = _seed(db)
        def upload(contents=PDF,approved=True,day=date(2026,9,26)):
            return service.archive_8609(db,current_user=admin,
                property_id=prop.id,program_id=program.id,building_id=building.id,
                contents=contents,received_on=day,signed_copy_reviewed=approved)
        for contents,status in ((b"not a pdf",422),(PDF+b"x"*(service.MAX_8609_BYTES+1),413)):
            with pytest.raises(HTTPException) as exc: upload(contents=contents)
            assert exc.value.status_code==status
        with pytest.raises(HTTPException) as exc: upload(approved=False)
        assert exc.value.status_code==422
        with pytest.raises(HTTPException) as exc: upload(day=date(2099,1,1))
        assert exc.value.status_code==422
        assert db.query(Affordable8609Document).count()==0
        monkeypatch.setattr(settings,"COMPLIANCE_DOCUMENT_ENCRYPTION_KEY","")
        with pytest.raises(HTTPException) as exc: upload()
        assert exc.value.status_code==503
        monkeypatch.setattr(settings,"COMPLIANCE_DOCUMENT_ENCRYPTION_KEY",settings.ENCRYPTION_KEY)
        with pytest.raises(HTTPException) as exc: upload()
        assert exc.value.status_code==503
        monkeypatch.setattr(settings,"COMPLIANCE_DOCUMENT_ENCRYPTION_KEY",Fernet.generate_key().decode())
        doc=upload()
        row=db.query(Affordable8609Document).one()
        row.encrypted_pdf=b"tampered";db.commit()
        with pytest.raises(HTTPException) as exc:
            service.download_8609(db,current_user=admin,property_id=prop.id,
                program_id=program.id,building_id=building.id,document_id=doc.id)
        assert exc.value.status_code==503
        with pytest.raises(HTTPException) as exc:
            _model_for_table("affordable_lihtc_8609_documents")
        assert exc.value.status_code==404
    finally:db.close();engine.dispose()


def test_revocation_and_no_store_response(monkeypatch):
    db,engine=_db()
    try:
        (admin,*_), (prop,*_), (program,*_), (building,*_) = _seed(db)
        response=Response()
        assert routes.list_documents(prop.id,program.id,building.id,response,
                                     db=db,current_user=admin)==[]
        assert response.headers.get("Cache-Control")=="no-store"
        monkeypatch.setattr(programs,"permission_allows_user",lambda *a,**k:False)
        with pytest.raises(HTTPException) as exc:
            service.list_8609(db,current_user=admin,property_id=prop.id,
                              program_id=program.id,building_id=building.id)
        assert exc.value.status_code==403
        monkeypatch.setattr(programs,"permission_allows_user",lambda *a,**k:True)
        monkeypatch.setattr(programs,"resolve_customer_features",lambda *a,**k:[
            SimpleNamespace(key=programs.FEATURE_KEY,allowed=False)])
        with pytest.raises(HTTPException) as exc:
            service.list_8609(db,current_user=admin,property_id=prop.id,
                              program_id=program.id,building_id=building.id)
        assert exc.value.status_code==404
    finally:db.close();engine.dispose()


def test_compliance_key_rotation_bounded_and_no_payload_or_secrets(monkeypatch):
    import json
    from cryptography.fernet import InvalidToken
    db, engine = _db()
    try:
        (admin, owner, manager, tenant, foreign), props, progs, buildings = _seed(db)
        previous = settings.COMPLIANCE_DOCUMENT_ENCRYPTION_KEY
        one = service.archive_8609(
            db, current_user=admin, property_id=props[0].id,
            program_id=progs[0].id, building_id=buildings[0].id,
            contents=PDF, received_on=date(2026,9,26), signed_copy_reviewed=True)
        two = service.archive_8609(
            db, current_user=owner, property_id=props[0].id,
            program_id=progs[0].id, building_id=buildings[0].id,
            contents=PDF+b"\\n", received_on=date(2026,9,26), signed_copy_reviewed=True)
        third = service.archive_8609(
            db, current_user=admin, property_id=props[1].id,
            program_id=progs[1].id, building_id=buildings[1].id,
            contents=PDF, received_on=date(2026,9,26), signed_copy_reviewed=True)
        monkeypatch.setattr(settings, "COMPLIANCE_DOCUMENT_PREVIOUS_KEYS_JSON",
                            json.dumps([previous]))
        current = Fernet.generate_key().decode()
        monkeypatch.setattr(settings, "COMPLIANCE_DOCUMENT_ENCRYPTION_KEY", current)
        first = service.rotate_building_scans(
            db, current_user=admin, property_id=props[0].id,
            program_id=progs[0].id, building_id=buildings[0].id, limit=1)
        assert first == {"rewrapped":1, "next_document_id":one.id, "has_more":True}
        second = service.rotate_building_scans(
            db, current_user=admin, property_id=props[0].id,
            program_id=progs[0].id, building_id=buildings[0].id,
            after_document_id=first["next_document_id"], limit=1)
        assert second == {"rewrapped":1, "next_document_id":two.id, "has_more":False}
        again = service.rotate_building_scans(
            db, current_user=admin, property_id=props[0].id,
            program_id=progs[0].id, building_id=buildings[0].id)
        assert again["rewrapped"] == 0
        for doc_id in (one.id, two.id):
            raw = db.query(Affordable8609Document).filter_by(id=doc_id).one()
            assert Fernet(current.encode()).decrypt(raw.encrypted_pdf).startswith(b"%PDF-")
            with pytest.raises(InvalidToken):
                Fernet(previous.encode()).decrypt(raw.encrypted_pdf)
        assert Fernet(previous.encode()).decrypt(
            db.query(Affordable8609Document).filter_by(id=third.id).one().encrypted_pdf
        ) == PDF
        monkeypatch.setattr(settings, "COMPLIANCE_DOCUMENT_PREVIOUS_KEYS_JSON", "[]")
        assert service.download_8609(
            db, current_user=admin, property_id=props[0].id,
            program_id=progs[0].id, building_id=buildings[0].id,
            document_id=one.id) == PDF
        with pytest.raises(HTTPException) as exc:
            service.download_8609(
                db, current_user=admin, property_id=props[1].id,
                program_id=progs[1].id, building_id=buildings[1].id,
                document_id=third.id)
        assert exc.value.status_code == 503
        audit = db.query(AuditLog).filter_by(action="encryption_key_rotated").all()
        assert len(audit) == 2
        for event in audit:
            assert event.organization_id == admin.organization_id
            assert "123-45-6789" not in (event.new_value or "")
            assert current not in (event.new_value or "")
            assert previous not in (event.new_value or "")
    finally:
        db.close(); engine.dispose()


def test_compliance_rotation_role_scope_config_and_atomic_failure(monkeypatch):
    import json
    db, engine = _db()
    try:
        (admin, owner, manager, tenant, foreign), props, progs, buildings = _seed(db)
        original = settings.COMPLIANCE_DOCUMENT_ENCRYPTION_KEY
        docs = [service.archive_8609(
            db, current_user=admin, property_id=props[0].id,
            program_id=progs[0].id, building_id=buildings[0].id,
            contents=PDF, received_on=date(2026,9,26), signed_copy_reviewed=True
        ) for _ in range(2)]
        original_ciphertext = [
            db.query(Affordable8609Document).filter_by(id=doc.id).one().encrypted_pdf
            for doc in docs
        ]
        for actor in (owner, manager, tenant, foreign):
            with pytest.raises(HTTPException):
                service.rotate_building_scans(
                    db, current_user=actor, property_id=props[0].id,
                    program_id=progs[0].id, building_id=buildings[0].id)
        with pytest.raises(HTTPException) as exc:
            service.rotate_building_scans(
                db, current_user=admin, property_id=props[1].id,
                program_id=progs[1].id, building_id=buildings[0].id)
        assert exc.value.status_code == 404
        monkeypatch.setattr(settings, "COMPLIANCE_DOCUMENT_ENCRYPTION_KEY",
                            Fernet.generate_key().decode())
        monkeypatch.setattr(settings, "COMPLIANCE_DOCUMENT_PREVIOUS_KEYS_JSON", "[]")
        with pytest.raises(HTTPException) as exc:
            service.rotate_building_scans(
                db, current_user=admin, property_id=props[0].id,
                program_id=progs[0].id, building_id=buildings[0].id)
        assert exc.value.status_code == 503
        for ix, doc in enumerate(docs):
            assert db.query(Affordable8609Document).filter_by(id=doc.id).one().encrypted_pdf == original_ciphertext[ix]
        # A corrupted SECOND ciphertext must roll back the first document's rewrap.
        monkeypatch.setattr(settings, "COMPLIANCE_DOCUMENT_PREVIOUS_KEYS_JSON",
                            json.dumps([original]))
        row = db.query(Affordable8609Document).filter_by(id=docs[1].id).one()
        row.encrypted_pdf = b"corrupted"
        db.commit()
        with pytest.raises(HTTPException) as exc:
            service.rotate_building_scans(
                db, current_user=admin, property_id=props[0].id,
                program_id=progs[0].id, building_id=buildings[0].id)
        assert exc.value.status_code == 503
        assert db.query(Affordable8609Document).filter_by(id=docs[0].id).one().encrypted_pdf == original_ciphertext[0]
        monkeypatch.setattr(settings, "COMPLIANCE_DOCUMENT_PREVIOUS_KEYS_JSON",
                            json.dumps([settings.ENCRYPTION_KEY]))
        with pytest.raises(HTTPException) as exc:
            service.rotate_building_scans(
                db, current_user=admin, property_id=props[0].id,
                program_id=progs[0].id, building_id=buildings[0].id)
        assert exc.value.status_code == 503
    finally:
        db.close(); engine.dispose()


def test_compliance_rotation_readiness_scoped_paginated_and_redacted(monkeypatch):
    import json
    db, engine = _db()
    try:
        (admin, owner, manager, tenant, foreign), props, progs, buildings = _seed(db)
        old_key = settings.COMPLIANCE_DOCUMENT_ENCRYPTION_KEY
        original = service.archive_8609(
            db, current_user=admin, property_id=props[0].id,
            program_id=progs[0].id, building_id=buildings[0].id,
            contents=PDF, received_on=date(2026,9,26), signed_copy_reviewed=True,
        )
        foreign_scan = service.archive_8609(
            db, current_user=admin, property_id=props[1].id,
            program_id=progs[1].id, building_id=buildings[1].id,
            contents=PDF, received_on=date(2026,9,26), signed_copy_reviewed=True,
        )
        saved = db.query(Affordable8609Document).filter_by(id=original.id).one().encrypted_pdf
        monkeypatch.setattr(settings, "COMPLIANCE_DOCUMENT_PREVIOUS_KEYS_JSON",
                            json.dumps([old_key]))
        monkeypatch.setattr(settings, "COMPLIANCE_DOCUMENT_ENCRYPTION_KEY",
                            Fernet.generate_key().decode())
        current_scan = service.archive_8609(
            db, current_user=admin, property_id=props[0].id,
            program_id=progs[0].id, building_id=buildings[0].id,
            contents=PDF, received_on=date(2026,9,26), signed_copy_reviewed=True,
        )
        response = Response()
        first = routes.rotation_readiness(
            props[0].id, progs[0].id, buildings[0].id, response,
            limit=1, db=db, current_user=admin,
        )
        assert response.headers["cache-control"] == "no-store"
        assert first == {"checked":1, "pending_rewrap":1, "current_key":0,
                         "next_document_id":original.id, "has_more":True}
        second = service.inspect_building_rotation(
            db, current_user=admin, property_id=props[0].id,
            program_id=progs[0].id, building_id=buildings[0].id,
            after_document_id=first["next_document_id"], limit=1,
        )
        assert second == {"checked":1, "pending_rewrap":0, "current_key":1,
                          "next_document_id":current_scan.id, "has_more":False}
        assert db.query(Affordable8609Document).filter_by(id=original.id).one().encrypted_pdf == saved
        assert db.query(Affordable8609Document).filter_by(id=foreign_scan.id).one().encrypted_pdf
        reviews = db.query(AuditLog).filter_by(action="encryption_rotation_reviewed").all()
        assert len(reviews) == 2
        for event in reviews:
            assert event.organization_id == admin.organization_id
            for sensitive in ("123-45-6789", old_key,
                              settings.COMPLIANCE_DOCUMENT_ENCRYPTION_KEY):
                assert sensitive not in (event.new_value or "")
        for actor in (owner, manager, tenant, foreign):
            with pytest.raises(HTTPException):
                service.inspect_building_rotation(
                    db, current_user=actor, property_id=props[0].id,
                    program_id=progs[0].id, building_id=buildings[0].id,
                )
        with pytest.raises(HTTPException) as exc:
            service.inspect_building_rotation(
                db, current_user=admin, property_id=props[1].id,
                program_id=progs[1].id, building_id=buildings[0].id,
            )
        assert exc.value.status_code == 404
        assert db.query(GLTransaction).count() == db.query(Lease).count() == db.query(Charge).count() == 0
    finally:
        db.close();engine.dispose()


def test_rotation_readiness_fails_closed_for_missing_keys_and_corruption(monkeypatch):
    import json
    db, engine = _db()
    try:
        (admin, *_), (prop, *_), (program, *_), (building, *_) = _seed(db)
        old = settings.COMPLIANCE_DOCUMENT_ENCRYPTION_KEY
        saved = service.archive_8609(
            db, current_user=admin, property_id=prop.id,
            program_id=program.id, building_id=building.id,
            contents=PDF, received_on=date(2026,9,26), signed_copy_reviewed=True,
        )
        monkeypatch.setattr(settings, "COMPLIANCE_DOCUMENT_ENCRYPTION_KEY",
                            Fernet.generate_key().decode())
        for history in ("[]", "not-json"):
            monkeypatch.setattr(settings, "COMPLIANCE_DOCUMENT_PREVIOUS_KEYS_JSON", history)
            with pytest.raises(HTTPException) as exc:
                service.inspect_building_rotation(
                    db, current_user=admin, property_id=prop.id,
                    program_id=program.id, building_id=building.id,
                )
            assert exc.value.status_code == 503
        monkeypatch.setattr(settings, "COMPLIANCE_DOCUMENT_PREVIOUS_KEYS_JSON",
                            json.dumps([old]))
        row = db.query(Affordable8609Document).filter_by(id=saved.id).one()
        row.encrypted_pdf = b"tampered"
        db.commit()
        with pytest.raises(HTTPException) as exc:
            service.inspect_building_rotation(
                db, current_user=admin, property_id=prop.id,
                program_id=program.id, building_id=building.id,
            )
        assert exc.value.status_code == 503
        assert db.query(AuditLog).filter_by(action="encryption_rotation_reviewed").count() == 0
    finally:
        db.close();engine.dispose()
