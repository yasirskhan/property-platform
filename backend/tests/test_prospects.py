"""Scoped leasing CRM: never create login identities or alter accounting."""
from __future__ import annotations
from datetime import date
import pytest
from fastapi import HTTPException, Response
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import init_db  # noqa: F401
from app.core.database import Base
from app.models.user import Organization, User, UserRole
from app.models.property import Property, PropertyAssignment
from app.models.contact import Contact
from app.models.prospect import Prospect
from app.models.audit_log import AuditLog
from app.models.application import LeaseApplication
from app.models.lease import Lease
from app.routers import prospects as api
from app.schemas.prospect import ProspectIn, ProspectUpdate


def _db():
    engine=create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)(),engine


def _seed(db):
    a=Organization(name="CRM one", slug="crm-one")
    b=Organization(name="CRM two", slug="crm-two")
    db.add_all([a,b]);db.flush()
    users=[]
    for org,role,name in [(a,UserRole.ADMIN,"Admin"),(a,UserRole.MANAGER,"Manager"),
                          (a,UserRole.OWNER,"Owner"),(a,UserRole.TENANT,"Tenant"),
                          (b,UserRole.ADMIN,"Foreign")]:
        u=User(organization_id=org.id,role=role,first_name=name,last_name="CRM",
               email=f"crm-{name.lower()}@example.com",hashed_password="x",is_active=True)
        db.add(u);users.append(u)
    db.flush()
    props=[]
    for org,name in [(a,"Assigned"),(a,"Unassigned"),(b,"Foreign")]:
        p=Property(organization_id=org.id,name=name,address_line1="20 CRM Ave",
                   city="Cleveland",state="OH",zip_code="44113",is_active=True)
        db.add(p);props.append(p)
    db.flush()
    db.add(PropertyAssignment(property_id=props[0].id,user_id=users[1].id,
                              role=UserRole.MANAGER,is_active=True))
    contacts=[]
    for org,name in [(a,"Local lead"),(b,"Foreign lead")]:
        c=Contact(organization_id=org.id,display_name=name,contact_type="PERSON",is_active=True)
        db.add(c);contacts.append(c)
    db.commit()
    return users,props,contacts


@pytest.fixture(autouse=True)
def allow(monkeypatch):
    monkeypatch.setattr(api,"permission_allows_user",lambda *a,**kw:True)


def test_crm_scope_dedupe_stage_marketing_and_identity_integrity():
    db,engine=_db()
    try:
        (admin,manager,owner,tenant,foreign),(assigned,unassigned,other),(contact,other_contact)=_seed(db)
        before_users=db.query(User).count()
        payload=ProspectIn(property_id=assigned.id,contact_id=contact.id,source="Website")
        created=api.create_prospect(payload,Response(),db=db,current_user=manager)
        assert created.contact_name=="Local lead" and created.stage=="NEW"
        assert created.organization_id==admin.organization_id
        assert len(api.list_prospects(Response(),db=db,current_user=manager).items)==1
        assert len(api.list_prospects(Response(),db=db,current_user=owner).items)==1
        assert api.list_prospects(Response(),db=db,current_user=foreign).total==0
        with pytest.raises(HTTPException) as exc:
            api.create_prospect(payload,Response(),db=db,current_user=admin)
        assert exc.value.status_code==409
        changed=api.update_prospect(created.id,ProspectUpdate(stage="TOUR_SCHEDULED",
            next_follow_up=date(2026,10,1)),Response(),db=db,current_user=manager)
        assert changed.stage=="TOUR_SCHEDULED" and changed.next_follow_up==date(2026,10,1)
        assert api.list_prospects(Response(),stage="NEW",db=db,current_user=admin).total==0
        assert api.list_prospects(Response(),stage="TOUR_SCHEDULED",db=db,current_user=admin).total==1
        for actor in (tenant,foreign):
            with pytest.raises(HTTPException) as exc:
                api.update_prospect(created.id,ProspectUpdate(stage="CLOSED"),Response(),
                                    db=db,current_user=actor)
            assert exc.value.status_code in {403,404}
        for target in (unassigned.id,other.id):
            with pytest.raises(HTTPException) as exc:
                api.create_prospect(ProspectIn(property_id=target,contact_id=contact.id),
                                    Response(),db=db,current_user=manager)
            assert exc.value.status_code==404
        with pytest.raises(HTTPException) as exc:
            api.create_prospect(ProspectIn(property_id=assigned.id,contact_id=other_contact.id),
                                Response(),db=db,current_user=admin)
        assert exc.value.status_code==404
        api.archive_prospect(created.id,db=db,current_user=manager)
        assert api.list_prospects(Response(),db=db,current_user=admin).total==0
        assert db.query(User).count()==before_users
        assert db.query(Lease).count()==0 and db.query(LeaseApplication).count()==0
        assert [r.action for r in db.query(AuditLog).filter_by(entity_type="leasing_prospect").all()]==[
            "created","updated","archived",
        ]
    finally:
        db.close();engine.dispose()


def test_crm_authorization_revocation_and_invalid_input(monkeypatch):
    db,engine=_db()
    try:
        (admin,manager,owner,tenant,foreign),(assigned,unassigned,other),(contact,other_contact)=_seed(db)
        made=api.create_prospect(ProspectIn(property_id=assigned.id,contact_id=contact.id),
                                 Response(),db=db,current_user=admin)
        for actor in (owner,tenant):
            with pytest.raises(HTTPException) as exc:
                api.create_prospect(ProspectIn(property_id=assigned.id,contact_id=contact.id),
                                    Response(),db=db,current_user=actor)
            assert exc.value.status_code==403
        monkeypatch.setattr(api,"permission_allows_user",lambda *a,**kw:False)
        with pytest.raises(HTTPException) as exc:
            api.list_prospects(Response(),db=db,current_user=admin)
        assert exc.value.status_code==403
        monkeypatch.setattr(api,"permission_allows_user",lambda *a,**kw:True)
        manager.is_active=False;db.commit()
        with pytest.raises(HTTPException) as exc:
            api.archive_prospect(made.id,db=db,current_user=manager)
        assert exc.value.status_code==403
        with pytest.raises(ValueError):
            ProspectIn(property_id=assigned.id,contact_id=contact.id,stage="PAID")
        with pytest.raises(ValueError):
            ProspectUpdate(source="x"*61)
        assert db.query(Prospect).count()==1
    finally:
        db.close();engine.dispose()



def test_source_summary_counts_only_visible_active_leads_and_preserves_org_scope():
    db, engine = _db()
    try:
        (admin, manager, owner, tenant, foreign), (assigned, unassigned, other), (contact, other_contact) = _seed(db)
        first = api.create_prospect(
            ProspectIn(property_id=assigned.id, contact_id=contact.id,
                       source="Website", stage="TOUR_SCHEDULED"),
            Response(), db=db, current_user=admin,
        )
        api.create_prospect(
            ProspectIn(property_id=unassigned.id, contact_id=contact.id,
                       source="Referral", stage="APPLIED"),
            Response(), db=db, current_user=admin,
        )
        api.create_prospect(
            ProspectIn(property_id=other.id, contact_id=other_contact.id,
                       source="Private foreign source"),
            Response(), db=db, current_user=foreign,
        )
        manager_response = Response()
        manager_summary = api.source_summary(manager_response, db=db, current_user=manager)
        assert manager_response.headers["cache-control"] == "no-store"
        assert manager_summary["total"] == 1
        assert manager_summary["items"] == [{
            "source": "Website", "total": 1, "new": 0, "contacted": 0,
            "tour_scheduled": 1, "applied": 0, "closed": 0,
        }]
        owner_summary = api.source_summary(Response(), db=db, current_user=owner)
        assert owner_summary["total"] == 2
        assert {row["source"] for row in owner_summary["items"]} == {"Website", "Referral"}
        assert "not verified applications" in owner_summary["meaning"].lower()
        foreign_summary = api.source_summary(Response(), db=db, current_user=foreign)
        assert foreign_summary["total"] == 1
        assert foreign_summary["items"][0]["source"] == "Private foreign source"
        api.archive_prospect(first.id, db=db, current_user=admin)
        assert api.source_summary(Response(), db=db, current_user=manager)["total"] == 0
        unassigned.is_active = False
        db.commit()
        assert api.source_summary(Response(), db=db, current_user=owner)["total"] == 0
        assert db.query(Lease).count() == 0 and db.query(LeaseApplication).count() == 0
    finally:
        db.close()
        engine.dispose()


def test_source_summary_enforces_live_permission(monkeypatch):
    db, engine = _db()
    try:
        (admin, manager, owner, tenant, foreign), props, contacts = _seed(db)
        for actor in (tenant,):
            with pytest.raises(HTTPException) as exc:
                api.source_summary(Response(), db=db, current_user=actor)
            assert exc.value.status_code == 403
        monkeypatch.setattr(api, "permission_allows_user", lambda *a, **kw: False)
        with pytest.raises(HTTPException) as exc:
            api.source_summary(Response(), db=db, current_user=admin)
        assert exc.value.status_code == 403
    finally:
        db.close()
        engine.dispose()
