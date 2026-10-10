"""Annual LIHTC 8609-A references are not IRS filings or credit calculations."""
from __future__ import annotations
from types import SimpleNamespace
import pytest
from fastapi import HTTPException, Response
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import init_db  # noqa: F401
from app.core.database import Base
from app.models.affordable_program import AffordableProgram
from app.models.affordable_building import AffordableBuilding
from app.models.affordable_8609_annual import Affordable8609Annual
from app.models.audit_log import AuditLog
from app.models.charge import Charge
from app.models.gl_transaction import GLTransaction
from app.models.lease import Lease
from app.models.property import Property, PropertyAssignment
from app.models.user import Organization, User, UserRole
from app.routers import affordable_programs as programs, affordable_8609_annual as api
from app.schemas.affordable_8609_annual import Affordable8609AnnualIn
from app.services.entity_notes import _model_for_table


@pytest.fixture(autouse=True)
def permissions(monkeypatch):
    monkeypatch.setattr(programs,"permission_allows_user",lambda *a,**k:True)
    monkeypatch.setattr(programs,"resolve_customer_features",lambda *a,**k:[
        SimpleNamespace(key=programs.FEATURE_KEY,allowed=True)])


def _db():
    engine=create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine,expire_on_commit=False)(),engine


def _seed(db):
    orgs=[Organization(name="Annual One",slug="annual-one"),
          Organization(name="Annual Two",slug="annual-two")]
    db.add_all(orgs);db.flush()
    users=[]
    for org,role,label in (
        (orgs[0],UserRole.ADMIN,"admin"), (orgs[0],UserRole.OWNER,"owner"),
        (orgs[0],UserRole.MANAGER,"manager"), (orgs[0],UserRole.TENANT,"tenant"),
        (orgs[1],UserRole.ADMIN,"foreign"),
    ):
        row=User(organization_id=org.id,role=role,first_name=label,last_name="Annual",
                 email=f"annual-{label}@example.com",hashed_password="x",is_active=True)
        db.add(row);users.append(row)
    db.flush()
    props=[];programs_list=[];buildings=[]
    for org,label in ((orgs[0],"Assigned"),(orgs[0],"Unassigned"),(orgs[1],"Foreign")):
        p=Property(organization_id=org.id,name=label,address_line1="10 Main",
                   city="Cleveland",state="OH",zip_code="44113",is_active=True)
        db.add(p);db.flush()
        pr=AffordableProgram(organization_id=org.id,property_id=p.id,
                             program_type="LIHTC",label="LIHTC",is_active=True)
        db.add(pr);db.flush()
        b=AffordableBuilding(organization_id=org.id,property_id=p.id,program_id=pr.id,
                              building_label="Building A",agency_bin="OH-20-12345",is_active=True)
        db.add(b);db.flush()
        props.append(p);programs_list.append(pr);buildings.append(b)
    db.add(PropertyAssignment(property_id=props[0].id,user_id=users[2].id,
                              role=UserRole.MANAGER,is_active=True))
    db.commit()
    return users,props,programs_list,buildings


def _input(year=2026, category="BUILDING_OR_ACQUISITION", status="REFERENCE_IDENTIFIED"):
    return Affordable8609AnnualIn(
        tax_year=year, allocation_category=category, status=status)


def test_annual_by_year_category_and_scope_audit_nonmutation():
    db,engine=_db()
    try:
        (admin,owner,manager,*_), (prop,*_), (pr,*_), (b,*_) = _seed(db)
        response=Response()
        initial=api.list_annual(prop.id,pr.id,b.id,response,tax_year=2026,db=db,current_user=manager)
        assert response.headers["cache-control"]=="no-store"
        assert len(initial)==2 and {x.status for x in initial}=={"NOT_RECORDED"}
        assert db.query(Affordable8609Annual).count()==0
        base=api.save_annual(prop.id,pr.id,b.id,_input(),db=db,current_user=admin)
        rehab=api.save_annual(prop.id,pr.id,b.id,
                              _input(category="REHABILITATION"),db=db,current_user=owner)
        prior=api.save_annual(prop.id,pr.id,b.id,
                              _input(year=2025),db=db,current_user=admin)
        updated=api.save_annual(prop.id,pr.id,b.id,
                                 _input(status="FOLLOW_UP_NEEDED"),db=db,current_user=admin)
        assert base.tax_year==2026 and rehab.allocation_category=="REHABILITATION"
        assert prior.tax_year==2025 and updated.status=="FOLLOW_UP_NEEDED"
        assert db.query(Affordable8609Annual).count()==3
        assert {x.status for x in api.list_annual(prop.id,pr.id,b.id,Response(),
                tax_year=2026,db=db,current_user=manager)}=={"FOLLOW_UP_NEEDED","REFERENCE_IDENTIFIED"}
        assert db.query(AuditLog).filter_by(entity_type="affordable_8609_annual").count()==4
        for klass in (Lease,Charge,GLTransaction):
            assert db.query(klass).count()==0
        assert not hasattr(base,"tax_credit") and not hasattr(base,"filed")
    finally:db.close();engine.dispose()


def test_annual_isolation_role_revocation_and_archived_building(monkeypatch):
    db,engine=_db()
    try:
        (admin,owner,manager,tenant,foreign),props,pr,buildings=_seed(db)
        for actor,ix in ((manager,1),(manager,2),(foreign,0),(admin,2)):
            with pytest.raises(HTTPException) as exc:
                api.list_annual(props[ix].id,pr[ix].id,buildings[ix].id,
                                Response(),tax_year=2026,db=db,current_user=actor)
            assert exc.value.status_code==404
        # Admin remains authorized for another property in same organization.
        assert len(api.list_annual(props[1].id,pr[1].id,buildings[1].id,
                                  Response(),tax_year=2026,db=db,current_user=admin))==2
        for actor in (manager,tenant):
            with pytest.raises(HTTPException) as exc:
                api.save_annual(props[0].id,pr[0].id,buildings[0].id,
                                _input(),db=db,current_user=actor)
            assert exc.value.status_code==403
        with pytest.raises(HTTPException) as exc:
            api.list_annual(props[0].id,pr[0].id,buildings[1].id,Response(),
                            tax_year=2026,db=db,current_user=admin)
        assert exc.value.status_code==404
        buildings[0].is_active=False;db.flush()
        with pytest.raises(HTTPException) as exc:
            api.list_annual(props[0].id,pr[0].id,buildings[0].id,
                            Response(),tax_year=2026,db=db,current_user=admin)
        assert exc.value.status_code==404
        buildings[0].is_active=True;db.flush()
        monkeypatch.setattr(programs,"permission_allows_user",lambda *a,**k:False)
        with pytest.raises(HTTPException) as exc:
            api.list_annual(props[0].id,pr[0].id,buildings[0].id,
                            Response(),tax_year=2026,db=db,current_user=admin)
        assert exc.value.status_code==403
        monkeypatch.setattr(programs,"permission_allows_user",lambda *a,**k:True)
        monkeypatch.setattr(programs,"resolve_customer_features",lambda *a,**k:[
            SimpleNamespace(key=programs.FEATURE_KEY,allowed=False)])
        with pytest.raises(HTTPException) as exc:
            api.list_annual(props[0].id,pr[0].id,buildings[0].id,
                            Response(),tax_year=2026,db=db,current_user=admin)
        assert exc.value.status_code==404
    finally:db.rollback();db.close();engine.dispose()


def test_annual_validation_and_generic_attachment_denial():
    db,engine=_db()
    try:
        (admin,*_), (prop,*_), (pr,*_), (b,*_) = _seed(db)
        for year in (0,1986,2101):
            with pytest.raises(ValueError):_input(year=year)
        for category in ("NOT_AN_ALLOCATION","CREDIT_9_PERCENT"):
            with pytest.raises(ValueError):_input(category=category)
        for status in ("FILED","CERTIFIED","CLAIMED"):
            with pytest.raises(ValueError):_input(status=status)
        with pytest.raises(HTTPException) as exc:
            _model_for_table("affordable_lihtc_8609_annual")
        assert exc.value.status_code==404
        assert api.list_annual(prop.id,pr.id,b.id,Response(),tax_year=1987,
                               db=db,current_user=admin)[0].tax_year==1987
        assert db.query(Affordable8609Annual).count()==0
    finally:db.close();engine.dispose()
