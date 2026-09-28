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
