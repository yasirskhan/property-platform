"""Phase 5 dispatch-group configuration, DEFAULT inheritance, policies, isolation."""
from datetime import datetime
from types import SimpleNamespace

import pytest
from fastapi import HTTPException, Response
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import init_db  # noqa: F401
from app.core.database import Base
from app.models.audit_log import AuditLog
from app.models.maintenance_dispatch import MaintenanceDispatchGroup, MaintenanceDispatchProperty, MaintenanceDispatchRule
from app.models.property import Property
from app.models.user import Organization, User, UserRole
from app.routers.maintenance_dispatch_groups import (
    list_dispatch_groups, create_dispatch_group, edit_dispatch_group,
    dispatch_group_properties, dispatch_group_contacts, save_dispatch_rule,
)
from app.schemas.maintenance_dispatch import MaintenanceGroupInput, MaintenanceRuleInput


def _fixture():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine, expire_on_commit=False)()
    first = Organization(name="Dispatch One", slug="dispatch-one", is_active=True)
    other = Organization(name="Dispatch Two", slug="dispatch-two", is_active=True)
    db.add_all([first,other]); db.flush()
    def user(org, role, name):
        row = User(organization_id=org.id, role=role, first_name=name, last_name="Tester",
                   email=name.lower()+"@dispatch.test", hashed_password="x", is_active=True)
        db.add(row); db.flush()
        return row
    admin = user(first, UserRole.ADMIN, "Admin")
    owner = user(first, UserRole.OWNER, "Owner")
    manager = user(first, UserRole.MANAGER, "Manager")
    crew = user(first, UserRole.CREW, "Crew")
    tenant = user(first, UserRole.TENANT, "Tenant")
    outsider = user(other, UserRole.ADMIN, "Outsider")
    def property(org,name):
        p=Property(organization_id=org.id, name=name, address_line1="123 Example St",
                   city="Cleveland", state="OH", zip_code="44113", is_active=True)
        db.add(p);db.flush();return p
    first_prop=property(first, "East")
    second_prop=property(first, "West")
    foreign_prop=property(other, "Foreign")
    db.commit()
    return db, engine, (admin,owner,manager,crew,tenant,outsider), (first_prop,second_prop,foreign_prop)


def _input(name, ids=(), tz="UTC", start=9, end=17):
    return MaintenanceGroupInput(name=name, property_ids=list(ids),
        timezone_name=tz,business_start_hour=start,business_end_hour=end)


def _groups(db,actor):
    return list_dispatch_groups(response=Response(),db=db,current_user=actor)


def test_default_group_inherits_active_properties_once_with_read_isolation():
    db,engine,people,properties=_fixture()
    try:
        admin,owner,manager,crew,tenant,outsider=people
        p1,p2,foreign=properties
        for user in (manager,crew,tenant):
            with pytest.raises(HTTPException) as denied:
                _groups(db,user)
            assert denied.value.status_code==403
        result=_groups(db,admin)
        assert len(result)==1 and result[0].name=="DEFAULT"
        assert result[0].is_default and result[0].property_ids==[p1.id,p2.id]
        assert len(result[0].rules)==6
        assert all(not r.configured for r in result[0].rules)
        assert _groups(db,owner)[0].id==result[0].id
        assert db.query(AuditLog).filter_by(
            entity_type="maintenance_dispatch_group",entity_id=result[0].id,
            action="default_initialized").count()==1
        assert [p.id for p in dispatch_group_properties(db=db,current_user=admin)]==[p1.id,p2.id]
        assert {u.id for u in dispatch_group_contacts(db=db,current_user=owner)}=={admin.id,owner.id}
        assert [g.property_ids for g in _groups(db,outsider)]==[[foreign.id]]
        assert db.query(MaintenanceDispatchGroup).count()==2
    finally:
        db.close();engine.dispose()


def test_exclusive_property_groups_transfer_and_return_to_default_with_audit():
    db,engine,people,properties=_fixture()
    try:
        admin,owner,manager,crew,tenant,outsider=people
        p1,p2,foreign=properties
        default=_groups(db,admin)[0]
        with pytest.raises(HTTPException) as denied:
            create_dispatch_group(_input("Forbidden", [p1.id]),db=db,current_user=manager)
        assert denied.value.status_code==403
        with pytest.raises(HTTPException) as foreign_p:
            create_dispatch_group(_input("Unsafe", [foreign.id]),db=db,current_user=admin)
        assert foreign_p.value.status_code==404
        assert db.query(MaintenanceDispatchGroup).count()==1
        a=create_dispatch_group(_input("East repairs", [p1.id]), db=db,current_user=admin)
        assert a.property_ids==[p1.id]
        assert next(g for g in _groups(db,admin) if g.is_default).property_ids==[p2.id]
        b=create_dispatch_group(_input("After Hours", [p2.id]),db=db,current_user=owner)
        moved=edit_dispatch_group(b.id,_input("After Hours", [p1.id,p2.id],tz="America/New_York",start=8,end=18),
                                  db=db,current_user=admin)
        assert moved.property_ids==[p1.id,p2.id] and moved.timezone_name=="America/New_York"
        assert len(next(g for g in _groups(db,admin) if g.is_default).property_ids)==0
        assert next(group for group in _groups(db,admin) if group.id==a.id).property_ids==[]
        assert db.query(MaintenanceDispatchProperty).count()==2
        updated=edit_dispatch_group(b.id,_input("After Hours", [p2.id],tz="America/New_York",start=8,end=18),
                                    db=db,current_user=admin)
        assert updated.property_ids==[p2.id]
        assert next(g for g in _groups(db,owner) if g.is_default).property_ids==[p1.id]
        assert db.query(MaintenanceDispatchProperty).count()==1
        assert db.query(AuditLog).filter_by(entity_type="maintenance_dispatch_property",
                                          entity_id=p1.id,action="group_changed").count()==3
        # No-op saves must not append misleading audit.
        before=db.query(AuditLog).count()
        edit_dispatch_group(b.id,_input("After Hours", [p2.id],tz="America/New_York",start=8,end=18),
                            db=db,current_user=admin)
        assert db.query(AuditLog).count()==before
        with pytest.raises(HTTPException) as reserved:
            edit_dispatch_group(default.id,_input("Rename DEFAULT",[]),db=db,current_user=admin)
        assert reserved.value.status_code==409
        with pytest.raises(HTTPException) as duplicate:
            create_dispatch_group(_input("AFTER HOURS",[]),db=db,current_user=admin)
        assert duplicate.value.status_code==409
    finally:
        db.close();engine.dispose()


def test_dispatch_policy_six_slots_contacts_validation_and_idempotent_review():
    db,engine,people,properties=_fixture()
    try:
        admin,owner,manager,crew,tenant,outsider=people
        default=_groups(db,admin)[0]
        policy=MaintenanceRuleInput(first_target="crew",backup_target="vendor",
                                    timeout_minutes=7,escalate=True,
                                    primary_contact_user_id=admin.id,
                                    backup_contact_user_id=owner.id)
        for user in (manager,crew,tenant,outsider):
            with pytest.raises(HTTPException):
                save_dispatch_rule(default.id,"emergency","after_hours",policy,
                                   db=db,current_user=user)
        saved=save_dispatch_rule(default.id,"emergency","after_hours",policy,db=db,current_user=admin)
        assert saved.configured and saved.escalate and saved.timeout_minutes==7
        assert len(_groups(db,admin)[0].rules)==6
        assert sum(1 for row in _groups(db,admin)[0].rules if row.configured)==1
        again=save_dispatch_rule(default.id,"emergency","after_hours",policy,db=db,current_user=owner)
        assert again.configured
        assert db.query(AuditLog).filter_by(entity_type="maintenance_dispatch_rule",action="created").count()==1
        assert db.query(MaintenanceDispatchRule).count()==1
        bad=MaintenanceRuleInput(first_target="crew",backup_target="vendor",
                                 timeout_minutes=10,escalate=True,primary_contact_user_id=crew.id)
        with pytest.raises(HTTPException) as wrong_contact:
            save_dispatch_rule(default.id,"normal","business_hours",bad,db=db,current_user=admin)
        assert wrong_contact.value.status_code==404
        for bad_ids in ((outsider.id,None),(owner.id,owner.id)):
            with pytest.raises(HTTPException):
                save_dispatch_rule(default.id,"normal","business_hours",
                                   MaintenanceRuleInput(first_target="crew",backup_target="vendor",
                                                        timeout_minutes=10,escalate=True,
                                                        primary_contact_user_id=bad_ids[0],
                                                        backup_contact_user_id=bad_ids[1]),
                                   db=db,current_user=admin)
        with pytest.raises(HTTPException) as unsupported:
            save_dispatch_rule(default.id,"immediate","after_hours",policy,db=db,current_user=admin)
        assert unsupported.value.status_code==422
        assert db.query(MaintenanceDispatchRule).count()==1
        assert db.query(AuditLog).filter_by(entity_type="maintenance_dispatch_rule",action="created").count()==1
    finally:
        db.close();engine.dispose()


def test_dispatch_group_requires_valid_timezone_hours_and_active_property():
    db,engine,people,properties=_fixture()
    try:
        admin,*_=people
        p1,p2,foreign=properties
        _groups(db,admin)
        for payload in (_input("Bad TZ",tz="Mars/Unknown"),
                        _input("Bad Hours",start=19,end=8),
                        _input("Bad org",ids=[foreign.id])):
            with pytest.raises(HTTPException):
                create_dispatch_group(payload,db=db,current_user=admin)
        p2.is_active=False
        db.commit()
        with pytest.raises(HTTPException):
            create_dispatch_group(_input("Retired",[p2.id]),db=db,current_user=admin)
        assert db.query(MaintenanceDispatchGroup).count()==1
        assert len(_groups(db,admin)[0].property_ids)==1
    finally:
        db.close();engine.dispose()


from datetime import timezone
from app.models.work_order import WorkOrderPriority
from app.services.maintenance_dispatch_policy import resolve_maintenance_dispatch_policy


def test_effective_dispatch_policy_requires_configuration_and_uses_real_local_hours():
    db,engine,people,properties=_fixture()
    try:
        admin,owner,manager,crew,tenant,outsider=people
        p1,p2,foreign=properties
        monday=datetime(2026,10,19,13,15,tzinfo=timezone.utc)
        uninitialized=resolve_maintenance_dispatch_policy(
            db,prop=p1,priority=WorkOrderPriority.EMERGENCY,now_utc=monday)
        assert uninitialized.status=="NO_GROUP_CONFIGURED"
        assert not uninitialized.configured and uninitialized.group_id is None

        default=_groups(db,admin)[0]
        preview=resolve_maintenance_dispatch_policy(
            db,prop=p2,priority=WorkOrderPriority.EMERGENCY,now_utc=monday)
        assert preview.group_id==default.id
        assert preview.status=="RULE_NOT_CONFIGURED"
        assert preview.daypart=="business_hours"
        assert preview.first_target is None

        group=create_dispatch_group(_input("New York response", [p1.id],tz="America/New_York",start=9,end=17),
                                    db=db,current_user=admin)
        policy=MaintenanceRuleInput(first_target="crew",backup_target="manager",
                                    timeout_minutes=12,escalate=True,
                                    primary_contact_user_id=admin.id)
        save_dispatch_rule(group.id,"emergency","business_hours",policy,db=db,current_user=owner)
        business=resolve_maintenance_dispatch_policy(
            db,prop=p1,priority=WorkOrderPriority.EMERGENCY,now_utc=monday)
        assert business.group_name=="New York response"
        assert business.daypart=="business_hours"
        assert business.configured and business.first_target=="crew"
        assert business.backup_target=="manager" and business.timeout_minutes==12
        # New York 9:15am in daylight saving time, but Saturday is after hours.
        weekend=datetime(2026,10,24,13,15,tzinfo=timezone.utc)
        after=resolve_maintenance_dispatch_policy(
            db,prop=p1,priority=WorkOrderPriority.EMERGENCY,now_utc=weekend)
        assert after.daypart=="after_hours" and not after.configured
        assert after.first_target is None
        assert resolve_maintenance_dispatch_policy(
            db,prop=p1,priority=WorkOrderPriority.LOW,now_utc=monday).urgency=="low"
    finally:
        db.close();engine.dispose()


def test_policy_resolver_fails_closed_on_cross_org_or_malformed_binding():
    db,engine,people,properties=_fixture()
    try:
        admin,owner,manager,crew,tenant,outsider=people
        p1,p2,foreign=properties
        local=create_dispatch_group(_input("Local", [p1.id]),db=db,current_user=admin)
        external_default=_groups(db,outsider)[0]
        bound=db.query(MaintenanceDispatchProperty).filter_by(property_id=p1.id).one()
        bound.group_id=external_default.id
        db.commit()
        with pytest.raises(HTTPException) as invalid:
            resolve_maintenance_dispatch_policy(db,prop=p1,priority="emergency")
        assert invalid.value.status_code==409
        # This legacy/corrupted organization value must never grant visibility.
        bound.group_id=local.id
        bound.organization_id=outsider.organization_id
        db.commit()
        with pytest.raises(HTTPException) as invalid:
            resolve_maintenance_dispatch_policy(db,prop=p1,priority="emergency")
        assert invalid.value.status_code==409
    finally:
        db.close();engine.dispose()


def test_automation_opt_in_is_owner_only_persisted_audited_and_never_executes_dispatch():
    db,engine,people,properties=_fixture()
    try:
        admin,owner,manager,crew,tenant,outsider=people
        default=next(g for g in _groups(db,admin) if g.is_default)
        assert default.automation_requested is False
        payload=MaintenanceGroupInput(name="DEFAULT",property_ids=[],automation_requested=True)
        with pytest.raises(HTTPException) as denied:
            edit_dispatch_group(default.id,payload,db=db,current_user=manager)
        assert denied.value.status_code==403
        changed=edit_dispatch_group(default.id,payload,db=db,current_user=owner)
        assert changed.automation_requested is True
        assert _groups(db,admin)[0].automation_requested is True
        log=db.query(AuditLog).filter_by(entity_type="maintenance_dispatch_group",entity_id=default.id,action="updated").one()
        assert __import__("json").loads(log.new_value)["automation_requested"] is True
        assert db.query(MaintenanceDispatchRule).count()==0
        before=db.query(AuditLog).count()
        edit_dispatch_group(default.id,payload,db=db,current_user=owner)
        assert db.query(AuditLog).count()==before
        turned_off=edit_dispatch_group(default.id,MaintenanceGroupInput(name="DEFAULT",property_ids=[],automation_requested=False),db=db,current_user=admin)
        assert turned_off.automation_requested is False
    finally:
        db.close();engine.dispose()
