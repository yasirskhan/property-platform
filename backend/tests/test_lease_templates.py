"""Lease template organization isolation, scope, authoring, addenda and attachments."""
from __future__ import annotations

from fastapi import HTTPException, Response
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import date
import pytest

import init_db  # noqa: F401
from app.core.database import Base
from app.models.audit_log import AuditLog
from app.models.lease_template import LeaseTemplate, LeaseTemplateAddendum
from app.models.entity_attachment import EntityAttachment
from app.models.property import Property, PropertyAssignment
from app.models.user import Organization, User, UserRole
from app.routers import lease_templates as api
from app.schemas.lease_template import TemplateIn, AddendumIn
from app.services import entity_notes


def _db():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, expire_on_commit=False)(), engine


def _seed(db):
    a = Organization(name="Templates One", slug="lease-templates-one")
    b = Organization(name="Templates Two", slug="lease-templates-two")
    db.add_all([a, b]); db.flush()
    staff=[]
    for org, role, label in (
        (a, UserRole.ADMIN, "admin"), (a, UserRole.MANAGER, "manager"),
        (a, UserRole.TENANT, "tenant"), (b, UserRole.ADMIN, "foreign"),
        (a, UserRole.OWNER, "owner"), (a, UserRole.CREW, "crew"),
    ):
        user=User(organization_id=org.id, role=role, first_name=label,
                  last_name="Staff", email=f"lease-template-{label}@example.com",
                  hashed_password="x", is_active=True)
        db.add(user);staff.append(user)
    db.flush()
    props=[]
    for org, name in ((a,"Assigned"),(a,"Unassigned"),(b,"Foreign")):
        prop=Property(organization_id=org.id,name=name,address_line1="20 Template Ave",
                      city="Cleveland",state="OH",zip_code="44113",is_active=True)
        db.add(prop);props.append(prop)
    db.flush()
    db.add(PropertyAssignment(property_id=props[0].id,user_id=staff[1].id,
                              role=UserRole.MANAGER,is_active=True))
    db.commit()
    return (*staff,*props)


@pytest.fixture(autouse=True)
def allow(monkeypatch):
    monkeypatch.setattr(api,"permission_allows_user",lambda *a,**kw:True)
    monkeypatch.setattr(entity_notes,"permission_allows_user",lambda *a,**kw:True)


def _create(db,admin,pid=None):
    return api.create_lease_template(
        TemplateIn(title="Lease",body="Plain {{tenant_name}} lease",property_id=pid),
        Response(),db=db,current_user=admin,
    )


def test_scope_and_three_levels_and_attachment_target():
    db, engine=_db()
    try:
        admin,manager,tenant,foreign,owner,crew,assigned,unassigned,other=_seed(db)
        global_template=_create(db,admin)
        local=_create(db,admin,assigned.id)
        blocked=_create(db,admin,unassigned.id)
        with pytest.raises(HTTPException) as exc:
            _create(db,admin,other.id)
        assert exc.value.status_code==404
        assert [row.id for row in api.list_lease_templates(
            Response(),db=db,current_user=manager)]==[global_template.id,local.id]
        assert len(api.list_lease_templates(Response(),db=db,current_user=owner))==3
        assert api.list_lease_templates(Response(),db=db,current_user=foreign)==[]
        for uid in (local.id,blocked.id):
            with pytest.raises(HTTPException) as exc:
                api.get_lease_template(uid,Response(),db=db,current_user=foreign)
            assert exc.value.status_code==404
        with pytest.raises(HTTPException) as exc:
            api.get_lease_template(blocked.id,Response(),db=db,current_user=manager)
        assert exc.value.status_code==404
        first=api.create_lease_addendum(local.id,AddendumIn(title="Pets",body="Pets",position=2),
                                       Response(),db=db,current_user=admin)
        second=api.create_lease_addendum(local.id,AddendumIn(title="Parking",body="Parking",position=1),
                                        Response(),db=db,current_user=admin)
        listed=api.get_lease_template(local.id,Response(),db=db,current_user=manager)
        assert [x.id for x in listed.addenda]==[second.id,first.id]
        assert db.query(LeaseTemplateAddendum).filter_by(organization_id=admin.organization_id).count()==2
        clean,obj,org=entity_notes.resolve_note_target(
            db,current_user=manager,entity_type="lease_template_addenda",entity_id=first.id)
        assert clean=="lease_template_addenda" and org==admin.organization_id
        with pytest.raises(HTTPException) as exc:
            entity_notes.resolve_note_target(db,current_user=manager,
                                             entity_type="lease_templates",entity_id=blocked.id)
        assert exc.value.status_code==403
        for actor in (tenant,crew):
            with pytest.raises(HTTPException) as exc:
                entity_notes.resolve_note_target(db,current_user=actor,
                                                 entity_type="lease_templates",entity_id=global_template.id)
            assert exc.value.status_code==403
        with pytest.raises(HTTPException):
            api.edit_lease_template(local.id,
                TemplateIn(title="Moved",body="Contents",property_id=unassigned.id),
                Response(),db=db,current_user=admin)
        assert db.query(AuditLog).filter_by(entity_type="lease_template_addendum").count()==2
        assert db.query(EntityAttachment).count()==0
    finally:
        db.close();engine.dispose()


def test_write_roles_validation_and_soft_deletion():
    db, engine=_db()
    try:
        admin,manager,tenant,foreign,owner,crew,assigned,unassigned,other=_seed(db)
        item=_create(db,admin,assigned.id)
        for actor in (manager,tenant,owner,foreign):
            with pytest.raises(HTTPException) as exc:
                api.edit_lease_template(item.id,
                    TemplateIn(title="Alter",body="text",property_id=assigned.id),
                    Response(),db=db,current_user=actor)
            assert exc.value.status_code in {403,404}
        for invalid in ("<script>danger</script>","{{applicant_ssn}}","{{tenant_name|safe}}"):
            with pytest.raises(HTTPException) as exc:
                api.edit_lease_template(item.id,
                    TemplateIn(title="Lease",body=invalid,property_id=assigned.id),
                    Response(),db=db,current_user=admin)
            assert exc.value.status_code==422
        add=api.create_lease_addendum(item.id,AddendumIn(title="Rules",body="Plain"),
                                     Response(),db=db,current_user=admin)
        updated=api.edit_lease_addendum(item.id,add.id,AddendumIn(title="Changed",body="Updated",position=5),
                                        Response(),db=db,current_user=admin)
        assert updated.title=="Changed"
        api.delete_lease_addendum(item.id,add.id,db=db,current_user=admin)
        assert api.get_lease_template(item.id,Response(),db=db,current_user=admin).addenda==[]
        api.deactivate_lease_template(item.id,db=db,current_user=admin)
        with pytest.raises(HTTPException) as exc:
            api.get_lease_template(item.id,Response(),db=db,current_user=admin)
        assert exc.value.status_code==404
        assert db.query(LeaseTemplate).one().is_active is False
        assert db.query(LeaseTemplateAddendum).one().is_active is False
    finally:
        db.close();engine.dispose()


def test_permission_revocation_and_inactive_role_guard(monkeypatch):
    db,engine=_db()
    try:
        admin,manager,tenant,foreign,owner,crew,assigned,unassigned,other=_seed(db)
        item=_create(db,admin,assigned.id)
        monkeypatch.setattr(api,"permission_allows_user",lambda *a,**kw:False)
        with pytest.raises(HTTPException) as exc:
            api.list_lease_templates(Response(),db=db,current_user=admin)
        assert exc.value.status_code==403
        monkeypatch.setattr(api,"permission_allows_user",lambda *a,**kw:True)
        admin.is_active=False; db.commit()
        with pytest.raises(HTTPException) as exc:
            api.create_lease_addendum(item.id,AddendumIn(title="No",body="No"),
                                      Response(),db=db,current_user=admin)
        assert exc.value.status_code==403
    finally:
        db.close();engine.dispose()
