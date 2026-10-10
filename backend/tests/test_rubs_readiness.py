"""RUBs readiness must never bill, expose accounts or cross property scopes."""
from __future__ import annotations
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
import pytest
from fastapi import HTTPException, Response
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import init_db  # noqa: F401

from app.core.database import Base
from app.models.user import Organization, User, UserRole
from app.models.property import Property, PropertyAssignment, Unit
from app.models.utility import (
    PropertyUtility,
    UtilityBill,
    UtilityMeterReading,
    UtilityType,
    PaidBy,
)
from app.schemas.utility import MeterReadingCreate, MeterReadingCSVImport
from app.models.charge import Charge
from app.models.gl_transaction import GLTransaction
from app.routers import rubs_readiness as api


def _db():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, expire_on_commit=False)(), engine


def _seed(db):
    a=Organization(name="RUBs One",slug="rubs-one")
    b=Organization(name="RUBs Two",slug="rubs-two")
    db.add_all([a,b]);db.flush()
    users=[]
    for org,role,name in [(a,UserRole.ADMIN,"admin"),(a,UserRole.MANAGER,"manager"),
                          (a,UserRole.OWNER,"owner"),(a,UserRole.TENANT,"tenant"),
                          (b,UserRole.ADMIN,"foreign")]:
        u=User(organization_id=org.id,role=role,first_name=name,last_name="Utility",
               email=f"rubs-{name}@example.com",hashed_password="x",is_active=True)
        db.add(u);users.append(u)
    db.flush()
    props=[]
    for org,name in [(a,"Assigned"),(a,"Unassigned"),(b,"Foreign")]:
        p=Property(organization_id=org.id,name=name,address_line1="20 Utils Ave",
                   city="Cleveland",state="OH",zip_code="44113",is_active=True)
        db.add(p);props.append(p)
    db.flush()
    db.add(PropertyAssignment(property_id=props[0].id,user_id=users[1].id,
                              role=UserRole.MANAGER,is_active=True))
    shared=PropertyUtility(property_id=props[0].id,utility_type=UtilityType.WATER,
        company_name="Water Service",paid_by=PaidBy.SHARED,account_number="SECRET-12345",
        is_active=True)
    owned=PropertyUtility(property_id=props[0].id,utility_type=UtilityType.GAS,
        company_name="Gas",paid_by=PaidBy.OWNER,is_active=True)
    hidden=PropertyUtility(property_id=props[1].id,utility_type=UtilityType.WATER,
        company_name="Unassigned",paid_by=PaidBy.SHARED,is_active=True)
    external=PropertyUtility(property_id=props[2].id,utility_type=UtilityType.WATER,
        company_name="Foreign",paid_by=PaidBy.SHARED,is_active=True)
    db.add_all([shared,owned,hidden,external]);db.flush()
    db.add_all([
        UtilityBill(utility_id=shared.id,billing_period_start=date(2026,8,1),
                    billing_period_end=date(2026,8,31),amount=Decimal("120.00")),
        UtilityBill(utility_id=shared.id,amount=Decimal("99999.99")),
        UtilityBill(utility_id=owned.id,amount=Decimal("20.00")),
    ])
    db.commit()
    return users,props,shared


@pytest.fixture(autouse=True)
def gates(monkeypatch):
    monkeypatch.setattr(api,"permission_allows_user",lambda *a,**kw:True)
    monkeypatch.setattr(api,"resolve_customer_features",lambda *a,**kw:[
        SimpleNamespace(key=api.FEATURE_KEY,allowed=True),
    ])


def test_shared_utility_readiness_is_scoped_readonly_and_safe():
    db,engine=_db()
    try:
        (admin,manager,owner,tenant,foreign),(assigned,unassigned,other),shared=_seed(db)
        res=Response()
        data=api.rubs_readiness(assigned.id,res,db=db,current_user=manager)
        assert res.headers["cache-control"]=="no-store"
        assert data["allocation_available"] is False and data["billing_available"] is False
        assert data["utility_count"]==1
        assert data["items"]==[{
            "utility_id":shared.id,"utility_type":"water",
            "bill_count":2,"periods_complete":1,"periods_missing_or_invalid":1,
            "periods_overlapping":0,"periods_duplicate":0,
        }]
        assert "SECRET-12345" not in str(data) and "99999" not in str(data)
        assert api.rubs_readiness(assigned.id,Response(),db=db,current_user=owner)["utility_count"]==1
        for inaccessible in (unassigned.id,other.id):
            with pytest.raises(HTTPException) as exc:
                api.rubs_readiness(inaccessible,Response(),db=db,current_user=manager)
            assert exc.value.status_code==404
        for actor in (tenant,foreign):
            with pytest.raises(HTTPException) as exc:
                api.rubs_readiness(assigned.id,Response(),db=db,current_user=actor)
            assert exc.value.status_code in {403,404}
        assert db.query(Charge).count()==0 and db.query(GLTransaction).count()==0
    finally:
        db.close();engine.dispose()


def test_rubs_gate_menu_and_disabled_user_are_fail_closed(monkeypatch):
    db,engine=_db()
    try:
        (admin,manager,owner,tenant,foreign),(assigned,unassigned,other),shared=_seed(db)
        monkeypatch.setattr(api,"resolve_customer_features",lambda *a,**kw:[
            SimpleNamespace(key=api.FEATURE_KEY,allowed=False),
        ])
        with pytest.raises(HTTPException) as exc:
            api.rubs_readiness(assigned.id,Response(),db=db,current_user=admin)
        assert exc.value.status_code==404
        monkeypatch.setattr(api,"resolve_customer_features",lambda *a,**kw:[
            SimpleNamespace(key=api.FEATURE_KEY,allowed=True),
        ])
        monkeypatch.setattr(api,"permission_allows_user",lambda *a,**kw:False)
        with pytest.raises(HTTPException) as exc:
            api.rubs_readiness(assigned.id,Response(),db=db,current_user=admin)
        assert exc.value.status_code==403
        monkeypatch.setattr(api,"permission_allows_user",lambda *a,**kw:True)
        admin.is_active=False
        db.commit()
        with pytest.raises(HTTPException) as exc:
            api.rubs_readiness(assigned.id,Response(),db=db,current_user=admin)
        assert exc.value.status_code==403
        assert db.query(Charge).count()==0 and db.query(GLTransaction).count()==0
    finally:
        db.close();engine.dispose()


def test_rubs_period_flags_duplicate_and_inclusive_overlap_without_charges():
    db,engine=_db()
    try:
        (admin,manager,owner,tenant,foreign),(assigned,unassigned,other),shared=_seed(db)
        # Existing valid August interval and one undated bill.
        db.add_all([
            UtilityBill(utility_id=shared.id,billing_period_start=date(2026,8,1),
                        billing_period_end=date(2026,8,31),amount=Decimal("120.00")),
            UtilityBill(utility_id=shared.id,billing_period_start=date(2026,8,31),
                        billing_period_end=date(2026,9,30),amount=Decimal("80.00")),
            UtilityBill(utility_id=shared.id,billing_period_start=date(2026,10,1),
                        billing_period_end=date(2026,10,31),amount=Decimal("80.00")),
        ])
        db.commit()
        result=api.rubs_readiness(assigned.id,Response(),db=db,current_user=manager)
        item=result["items"][0]
        assert item["bill_count"]==5
        assert item["periods_complete"]==4
        assert item["periods_missing_or_invalid"]==1
        assert item["periods_duplicate"]==1
        assert item["periods_overlapping"]==2
        assert "120.00" not in str(result)
        assert db.query(Charge).count()==0 and db.query(GLTransaction).count()==0
    finally:
        db.close();engine.dispose()


def test_rubs_invalid_reversed_period_never_counts_as_overlap():
    db,engine=_db()
    try:
        (admin,manager,owner,tenant,foreign),(assigned,unassigned,other),shared=_seed(db)
        db.add(UtilityBill(utility_id=shared.id,billing_period_start=date(2026,9,5),
                           billing_period_end=date(2026,9,1),amount=Decimal("40.00")))
        db.commit()
        result=api.rubs_readiness(assigned.id,Response(),db=db,current_user=manager)
        item=result["items"][0]
        assert item["bill_count"]==3
        assert item["periods_complete"]==1
        assert item["periods_missing_or_invalid"]==2
        assert item["periods_duplicate"]==0 and item["periods_overlapping"]==0
        assert result["allocation_available"] is False
        assert result["billing_available"] is False
    finally:
        db.close();engine.dispose()



def test_rubs_manual_meter_reading_is_scoped_idempotent_and_finance_neutral():
    db,engine=_db()
    try:
        (admin,manager,owner,tenant,foreign),(assigned,unassigned,other),shared=_seed(db)
        unit=Unit(property_id=assigned.id,unit_number="1R",bedrooms=1,bathrooms=1,
                  monthly_rent=Decimal("1200.00"),is_active=True)
        db.add(unit);db.commit();db.refresh(unit)
        payload=MeterReadingCreate(
            meter_identifier="SUB-1R",
            reading_date=date(2026,9,30),
            reading_value=Decimal("1234.500000"),
            unit_of_measure="gallons",
            unit_id=unit.id,
            notes="End of month",
            request_key="manual-reading-001",
        )
        created=api.create_meter_reading(
            assigned.id,shared.id,payload,db=db,current_user=manager
        )
        assert created.source=="MANUAL" and created.unit_id==unit.id
        replay=api.create_meter_reading(
            assigned.id,shared.id,payload,db=db,current_user=manager
        )
        assert replay.id==created.id
        listed=api.list_meter_readings(
            assigned.id,shared.id,Response(),db=db,current_user=owner
        )
        assert [row.id for row in listed]==[created.id]
        conflicting=payload.model_copy(update={"reading_value":Decimal("1235.0")})
        with pytest.raises(HTTPException) as exc:
            api.create_meter_reading(
                assigned.id,shared.id,conflicting,db=db,current_user=manager
            )
        assert exc.value.status_code==409
        assert db.query(UtilityMeterReading).count()==1
        assert db.query(Charge).count()==0 and db.query(GLTransaction).count()==0
    finally:
        db.close();engine.dispose()


def test_rubs_csv_meter_import_is_atomic_replay_safe_and_validates_units():
    db,engine=_db()
    try:
        (admin,manager,owner,tenant,foreign),(assigned,unassigned,other),shared=_seed(db)
        unit=Unit(property_id=assigned.id,unit_number="2R",bedrooms=2,bathrooms=1,
                  monthly_rent=Decimal("1400.00"),is_active=True)
        db.add(unit);db.commit();db.refresh(unit)
        csv_text=(
            "meter_identifier,reading_date,reading_value,unit_of_measure,unit_id,notes\n"
            f"MASTER,2026-09-30,9000.25,gallons,,Property master\n"
            f"SUB-2R,2026-09-30,450.5,gallons,{unit.id},Unit submeter\n"
        )
        payload=MeterReadingCSVImport(
            request_key="import-reading-001",
            csv_text=csv_text,
        )
        first=api.import_meter_readings_csv(
            assigned.id,shared.id,payload,db=db,current_user=admin
        )
        assert first["created"]==2 and first["replayed"]==0 and first["total"]==2
        replay=api.import_meter_readings_csv(
            assigned.id,shared.id,payload,db=db,current_user=admin
        )
        assert replay["created"]==0 and replay["replayed"]==2
        assert db.query(UtilityMeterReading).count()==2

        bad=MeterReadingCSVImport(
            request_key="import-reading-002",
            csv_text=(
                "meter_identifier,reading_date,reading_value,unit_of_measure\n"
                "MASTER,2026-10-31,9100,gallons\n"
                "MASTER,not-a-date,9200,gallons\n"
            ),
        )
        with pytest.raises(HTTPException) as exc:
            api.import_meter_readings_csv(
                assigned.id,shared.id,bad,db=db,current_user=admin
            )
        assert exc.value.status_code==422
        assert db.query(UtilityMeterReading).count()==2

        foreign_unit=Unit(property_id=other.id,unit_number="X",bedrooms=1,bathrooms=1,
                          monthly_rent=Decimal("1000.00"),is_active=True)
        db.add(foreign_unit);db.commit();db.refresh(foreign_unit)
        cross_scope=MeterReadingCSVImport(
            request_key="import-reading-003",
            csv_text=(
                "meter_identifier,reading_date,reading_value,unit_of_measure,unit_id\n"
                f"FOREIGN,2026-10-31,10,kwh,{foreign_unit.id}\n"
            ),
        )
        with pytest.raises(HTTPException) as exc:
            api.import_meter_readings_csv(
                assigned.id,shared.id,cross_scope,db=db,current_user=manager
            )
        assert exc.value.status_code==422
        assert db.query(UtilityMeterReading).count()==2
        assert db.query(Charge).count()==0 and db.query(GLTransaction).count()==0
    finally:
        db.close();engine.dispose()
