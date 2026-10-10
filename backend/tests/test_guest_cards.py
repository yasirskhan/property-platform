"""Guest card org, staff and unit scope and no financial/identity mutation."""
from __future__ import annotations
from datetime import date
import pytest
from fastapi import HTTPException, Response
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import init_db  # noqa: F401
from app.core.database import Base
from app.models.user import Organization, User, UserRole
from app.models.property import Property, PropertyAssignment, Unit
from app.models.contact import Contact
from app.models.prospect import Prospect
from app.models.guest_card import GuestCard
from app.models.application import LeaseApplication
from app.models.lease import Lease
from app.models.audit_log import AuditLog
from app.routers import guest_cards as api
from app.routers import prospects
from app.schemas.guest_card import GuestCardIn, GuestCardUpdate
from app.schemas.prospect import ProspectIn


def _db():
    engine=create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine,expire_on_commit=False)(),engine


def _seed(db):
    a=Organization(name="Guest Org",slug="guest-org")
    b=Organization(name="Other Guests",slug="other-guests")
    db.add_all([a,b]);db.flush()
    staff=[]
    for org,role,name in [(a,UserRole.ADMIN,"Admin"),(a,UserRole.MANAGER,"Manager"),
                          (a,UserRole.OWNER,"Owner"),(a,UserRole.TENANT,"Tenant"),
                          (b,UserRole.ADMIN,"Foreign")]:
        u=User(organization_id=org.id,role=role,first_name=name,last_name="Guest",
               email=f"guest-{name.lower()}@example.com",hashed_password="x",is_active=True)
        db.add(u);staff.append(u)
    db.flush()
    props=[]
    for org,name in [(a,"Assigned"),(a,"Unassigned"),(b,"Foreign")]:
        p=Property(organization_id=org.id,name=name,address_line1="20 Guest Ave",
                   city="Cleveland",state="OH",zip_code="44113",is_active=True)
        db.add(p);props.append(p)
    db.flush()
    db.add(PropertyAssignment(property_id=props[0].id,user_id=staff[1].id,
                              role=UserRole.MANAGER,is_active=True))
    contact=Contact(organization_id=a.id,display_name="Guest Contact",contact_type="PERSON",is_active=True)
    db.add(contact);db.flush()
    p1=Prospect(organization_id=a.id,property_id=props[0].id,contact_id=contact.id,
                stage="NEW",source="Website",is_active=True)
    p2=Prospect(organization_id=a.id,property_id=props[1].id,contact_id=contact.id,
                stage="NEW",source="Referral",is_active=True)
    db.add_all([p1,p2]);db.flush()
    units=[]
    for prop in props:
        u=Unit(property_id=prop.id,unit_number="1",is_active=True)
        db.add(u);units.append(u)
    db.commit()
    return staff,props,(p1,p2),units


@pytest.fixture(autouse=True)
def grant(monkeypatch):
    monkeypatch.setattr(prospects,"permission_allows_user",lambda *a,**kw:True)


def test_guest_card_staff_scope_unit_validation_and_reversal_safe():
    db,engine=_db()
    try:
        (admin,manager,owner,tenant,foreign),(assigned,unassigned,other),(p1,p2),(u1,u2,u3)=_seed(db)
        card=api.create_guest_card(GuestCardIn(prospect_id=p1.id,visit_on=date(2026,9,27),
                 unit_id=u1.id,attended=True,next_step="FOLLOW_UP"),
                 Response(),db=db,current_user=manager)
        assert card.contact_name=="Guest Contact" and card.property_id==assigned.id
        assert card.attended and card.unit_id==u1.id
        assert api.list_guest_cards(Response(),db=db,current_user=owner).total==1
        assert api.list_guest_cards(Response(),db=db,current_user=foreign).total==0
        with pytest.raises(HTTPException) as exc:
            api.create_guest_card(GuestCardIn(prospect_id=p1.id,visit_on=date(2026,9,27)),
                                  Response(),db=db,current_user=admin)
        assert exc.value.status_code==409
        for bad_unit in (u2.id,u3.id):
            with pytest.raises(HTTPException) as exc:
                api.create_guest_card(GuestCardIn(prospect_id=p1.id,visit_on=date(2026,9,28),
                                  unit_id=bad_unit),Response(),db=db,current_user=admin)
            assert exc.value.status_code==404
        with pytest.raises(HTTPException) as exc:
            api.create_guest_card(GuestCardIn(prospect_id=p2.id,visit_on=date(2026,9,28)),
                                  Response(),db=db,current_user=manager)
        assert exc.value.status_code==404
        changed=api.update_guest_card(card.id,GuestCardUpdate(attended=False,next_step="TOUR_RESCHEDULE"),
                                      Response(),db=db,current_user=manager)
        assert changed.attended is False and changed.next_step=="TOUR_RESCHEDULE"
        api.archive_guest_card(card.id,db=db,current_user=manager)
        assert api.list_guest_cards(Response(),db=db,current_user=owner).total==0
        assert db.query(Lease).count()==0 and db.query(LeaseApplication).count()==0
        assert [x.action for x in db.query(AuditLog).filter_by(entity_type="leasing_guest_card").all()]==[
            "created","updated","archived",
        ]
    finally:
        db.close();engine.dispose()


def test_guest_cards_reject_foreign_staff_revoked_menu_and_sensitive_extra(monkeypatch):
    db,engine=_db()
    try:
        (admin,manager,owner,tenant,foreign),(assigned,unassigned,other),(p1,p2),(u1,u2,u3)=_seed(db)
        for actor in (owner,tenant,foreign):
            with pytest.raises(HTTPException) as exc:
                api.create_guest_card(GuestCardIn(prospect_id=p1.id,visit_on=date(2026,9,27)),
                                      Response(),db=db,current_user=actor)
            assert exc.value.status_code in {403,404}
        with pytest.raises(ValueError):
            GuestCardIn(prospect_id=p1.id,visit_on=date(2026,9,27),applicant_ssn="123456789")
        made=api.create_guest_card(GuestCardIn(prospect_id=p1.id,visit_on=date(2026,9,27)),
                                   Response(),db=db,current_user=admin)
        monkeypatch.setattr(prospects,"permission_allows_user",lambda *a,**kw:False)
        with pytest.raises(HTTPException) as exc:
            api.list_guest_cards(Response(),db=db,current_user=admin)
        assert exc.value.status_code==403
        monkeypatch.setattr(prospects,"permission_allows_user",lambda *a,**kw:True)
        manager.is_active=False;db.commit()
        with pytest.raises(HTTPException) as exc:
            api.archive_guest_card(made.id,db=db,current_user=manager)
        assert exc.value.status_code==403
    finally:
        db.close();engine.dispose()
