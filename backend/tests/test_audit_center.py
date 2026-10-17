from __future__ import annotations
from datetime import datetime, timedelta
import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import init_db  # noqa: F401
import app.routers.audit_center as audit_router
from app.core.database import Base
from app.models.audit_log import AuditLog
from app.models.user import Organization, User, UserRole
from app.services.audit import append_audit_log

def _session():
    engine=create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, expire_on_commit=False)(), engine

def _seed(db):
    org=Organization(name="Audit Org", slug="audit-org")
    other_org=Organization(name="Other Audit Org", slug="other-audit-org")
    db.add_all([org,other_org]); db.flush()
    admin=User(email="audit-admin@example.com",hashed_password="x",first_name="Audit",last_name="Admin",role=UserRole.ADMIN,organization_id=org.id,is_active=True)
    tenant=User(email="audit-tenant@example.com",hashed_password="x",first_name="Audit",last_name="Tenant",role=UserRole.TENANT,organization_id=org.id,is_active=True)
    other=User(email="other-audit@example.com",hashed_password="x",first_name="Other",last_name="Admin",role=UserRole.ADMIN,organization_id=other_org.id,is_active=True)
    db.add_all([admin,tenant,other]); db.flush()
    append_audit_log(db,user_id=admin.id,organization_id=org.id,entity_type="property",entity_id=10,action="updated",field_name="name",old_value="Old",new_value="New")
    append_audit_log(db,user_id=other.id,organization_id=other_org.id,entity_type="property",entity_id=20,action="updated")
    db.commit()
    return org,admin,tenant,other

def _allow(monkeypatch):
    class D: key=audit_router.FEATURE_KEY; allowed=True
    monkeypatch.setattr(audit_router,"resolve_customer_features",lambda db,user:[D()])
    monkeypatch.setattr(audit_router,"permission_allows_user",lambda *a,**k:True)

def test_audit_center_org_scope_filters_and_export(monkeypatch):
    db,engine=_session()
    try:
        _,admin,_,_=_seed(db); _allow(monkeypatch)
        result=audit_router.list_audit_events(entity_type="property",action="updated",actor_user_id=admin.id,date_from=datetime.utcnow()-timedelta(days=1),date_to=datetime.utcnow()+timedelta(days=1),search="name",limit=100,offset=0,db=db,current_user=admin)
        assert result.total==1 and result.items[0].entity_id==10
        response=audit_router.export_audit_events(entity_type="property",action="updated",actor_user_id=admin.id,date_from=None,date_to=None,search=None,db=db,current_user=admin)
        body=response.body.decode()
        assert "Audit Admin" in body and ",10,updated," in body and "Other Admin" not in body
    finally:
        db.close(); engine.dispose()

def test_audit_center_requires_permission_and_feature(monkeypatch):
    db,engine=_session()
    try:
        _,admin,tenant,_=_seed(db)
        class D: key=audit_router.FEATURE_KEY; allowed=True
        monkeypatch.setattr(audit_router,"resolve_customer_features",lambda db,user:[D()])
        monkeypatch.setattr(audit_router,"permission_allows_user",lambda *a,**k:False)
        with pytest.raises(HTTPException) as exc: audit_router.list_audit_events(limit=100,offset=0,db=db,current_user=tenant)
        assert exc.value.status_code==403
        monkeypatch.setattr(audit_router,"permission_allows_user",lambda *a,**k:True)
        class X: key=audit_router.FEATURE_KEY; allowed=False
        monkeypatch.setattr(audit_router,"resolve_customer_features",lambda db,user:[X()])
        with pytest.raises(HTTPException) as exc: audit_router.list_audit_events(limit=100,offset=0,db=db,current_user=admin)
        assert exc.value.status_code==404
    finally:
        db.close(); engine.dispose()

def test_audit_center_read_does_not_mutate_history(monkeypatch):
    db,engine=_session()
    try:
        _,admin,_,_=_seed(db); _allow(monkeypatch)
        before=db.query(AuditLog).count()
        audit_router.list_audit_events(limit=100,offset=0,db=db,current_user=admin)
        assert db.query(AuditLog).count()==before
    finally:
        db.close(); engine.dispose()
