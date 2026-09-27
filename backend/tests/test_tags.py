"""Phase 4 universal tags: strict allowlist, live org/property permission, dedup and audit."""
from __future__ import annotations

from datetime import datetime

import pytest
from fastapi import HTTPException, Response
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import init_db  # noqa: F401
from app.core.database import Base
from app.models.audit_log import AuditLog
from app.models.contact import Contact
from app.models.property import Property, PropertyAssignment
from app.models.tag import Tag, EntityTag
from app.models.tax_profile import TaxProfile
from app.models.user import Organization, User, UserRole
from app.models.vendor import Vendor
from app.routers import tags as api
from app.schemas.tag import TagCreate, TagUpdate


def _session():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)(), engine


def _seed(db):
    org = Organization(name="Tag Org One", slug="tags-one")
    other = Organization(name="Tag Org Two", slug="tags-two")
    db.add_all([org, other]); db.flush()
    users = []
    for company, role, name in (
        (org, UserRole.ADMIN, "Admin"), (org, UserRole.OWNER, "Owner"),
        (org, UserRole.MANAGER, "Manager"), (org, UserRole.TENANT, "Tenant"),
        (other, UserRole.ADMIN, "Other"),
    ):
        user = User(
            organization_id=company.id, role=role, first_name=name, last_name="Tag",
            email=f"{name.lower()}@tags-test.example", hashed_password="x", is_active=True,
        )
        db.add(user); db.flush()
        users.append(user)
    admin, owner, manager, tenant, foreign_admin = users
    c1 = Contact(organization_id=org.id, display_name="Customer One")
    c2 = Contact(organization_id=other.id, display_name="Private Other")
    v1 = Vendor(organization_id=org.id, company_name="Approved Plumbing")
    v2 = Vendor(organization_id=other.id, company_name="Private Vendor")
    p1 = Property(organization_id=org.id, name="Assigned Property",
                  address_line1="100 Local Street", city="Cleveland", state="OH",
                  zip_code="44113", country="USA", is_active=True)
    p2 = Property(organization_id=org.id, name="Unassigned Property",
                  address_line1="200 Local Street", city="Cleveland", state="OH",
                  zip_code="44113", country="USA", is_active=True)
    db.add_all([c1,c2,v1,v2,p1,p2]); db.flush()
    db.add(PropertyAssignment(property_id=p1.id, user_id=manager.id,
                              role=UserRole.MANAGER, is_active=True))
    db.commit()
    return admin,owner,manager,tenant,foreign_admin,c1,c2,v1,v2,p1,p2


def test_tag_definition_dedup_archive_restore_and_audit(monkeypatch):
    db, engine = _session()
    try:
        admin,owner,manager,tenant,foreign_admin,c1,c2,v1,v2,p1,p2 = _seed(db)
        monkeypatch.setattr(api, "permission_allows_user", lambda *a, **kw: True)
        first = api.create_tag(TagCreate(name=" Priority "), db=db, current_user=admin)
        assert first.name == "Priority"
        with pytest.raises(HTTPException) as exc:
            api.create_tag(TagCreate(name="priority"), db=db, current_user=admin)
        assert exc.value.status_code == 409
        foreign = api.create_tag(TagCreate(name="priority"), db=db, current_user=foreign_admin)
        assert foreign.id != first.id
        assert api.list_tags(Response(), db=db, current_user=owner).total == 1
        renamed = api.update_tag(first.id, TagUpdate(name="Urgent"), db=db, current_user=admin)
        assert renamed.name == "Urgent"
        api.deactivate_tag(first.id, db=db, current_user=admin)
        assert api.list_tags(Response(), db=db, current_user=admin).total == 0
        assert api.list_tags(Response(), include_inactive=True, db=db, current_user=owner).total == 1
        api.restore_tag(first.id, db=db, current_user=admin)
        assert api.list_tags(Response(), db=db, current_user=admin).total == 1
        audit = db.query(AuditLog).filter_by(organization_id=admin.organization_id, entity_type="tag").all()
        assert [row.action for row in audit] == ["created","updated","deactivated","restored"]
        assert db.query(Tag).count() == 2
    finally:
        db.close(); engine.dispose()


def test_tag_assignment_scoping_archive_and_secret_target_denial(monkeypatch):
    db, engine = _session()
    try:
        admin,owner,manager,tenant,foreign_admin,c1,c2,v1,v2,p1,p2 = _seed(db)
        monkeypatch.setattr(api, "permission_allows_user", lambda *a, **kw: True)
        from app.services import entity_notes
        monkeypatch.setattr(entity_notes, "permission_allows_user", lambda *a, **kw: True)
        tag = api.create_tag(TagCreate(name="Follow up"), db=db, current_user=admin)
        api.assign_tag("contacts", c1.id, tag.id, db=db, current_user=admin)
        api.assign_tag("contacts", c1.id, tag.id, db=db, current_user=admin)
        assert db.query(EntityTag).count() == 1
        assert api.list_target_tags("contacts",c1.id,Response(),db=db,current_user=manager).total == 1
        for kind, entity_id in (
            ("contacts",c2.id), ("vendors",v2.id),
            ("audit_log",1), ("users",admin.id),
            ("tax_profiles",1), ("tax_w9_documents",1),
        ):
            with pytest.raises(HTTPException) as exc:
                api.assign_tag(kind,entity_id,tag.id,db=db,current_user=admin)
            assert exc.value.status_code in (403,404)
        api.assign_tag("vendors",v1.id,tag.id,db=db,current_user=owner)
        with pytest.raises(HTTPException) as exc:
            api.list_target_tags("vendors",v1.id,Response(),db=db,current_user=manager)
        assert exc.value.status_code == 403
        api.deactivate_tag(tag.id,db=db,current_user=admin)
        with pytest.raises(HTTPException) as exc:
            api.assign_tag("properties",p1.id,tag.id,db=db,current_user=manager)
        assert exc.value.status_code == 409
        assert api.list_target_tags("contacts",c1.id,Response(),db=db,current_user=admin).items[0].is_active is False
        api.unassign_tag("contacts",c1.id,tag.id,db=db,current_user=admin)
        assert db.query(EntityTag).count() == 1
        assert [row.action for row in db.query(AuditLog).filter_by(
            organization_id=admin.organization_id, entity_type="contacts").all()
        ] == ["tag_added","tag_removed"]
    finally:
        db.close(); engine.dispose()


def test_property_scope_and_live_permissions_no_cross_org_leak(monkeypatch):
    db, engine = _session()
    try:
        admin,owner,manager,tenant,foreign_admin,c1,c2,v1,v2,p1,p2 = _seed(db)
        monkeypatch.setattr(api, "permission_allows_user", lambda *a, **kw: True)
        from app.services import entity_notes
        monkeypatch.setattr(entity_notes, "permission_allows_user", lambda *a, **kw: True)
        tag = api.create_tag(TagCreate(name="On hold"), db=db, current_user=admin)
        api.assign_tag("properties",p1.id,tag.id,db=db,current_user=manager)
        with pytest.raises(HTTPException) as exc:
            api.assign_tag("properties",p2.id,tag.id,db=db,current_user=manager)
        assert exc.value.status_code == 403
        with pytest.raises(HTTPException) as exc:
            api.assign_tag("contacts",c2.id,tag.id,db=db,current_user=admin)
        assert exc.value.status_code == 403
        for actor in (tenant,):
            with pytest.raises(HTTPException) as exc:
                api.list_tags(Response(),db=db,current_user=actor)
            assert exc.value.status_code == 403
        for actor in (owner,manager):
            with pytest.raises(HTTPException) as exc:
                api.create_tag(TagCreate(name="Denied"),db=db,current_user=actor)
            assert exc.value.status_code == 403
        monkeypatch.setattr(api, "permission_allows_user", lambda *a,**kw: False)
        with pytest.raises(HTTPException) as exc:
            api.list_target_tags("properties",p1.id,Response(),db=db,current_user=admin)
        assert exc.value.status_code == 403
        admin.is_active = False
        db.commit()
        with pytest.raises(HTTPException) as exc:
            api.list_tags(Response(),db=db,current_user=admin)
        assert exc.value.status_code == 403
        assert db.query(EntityTag).count() == 1
    finally:
        db.close(); engine.dispose()
