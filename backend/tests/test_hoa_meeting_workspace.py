"""Staff meeting participation/motions never certify board authority or post money."""
from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import pytest
from fastapi import HTTPException, Response
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import init_db  # noqa: F401
from app.core.database import Base
from app.models.audit_log import AuditLog
from app.models.charge import Charge
from app.models.contact import Contact
from app.models.gl_entry import GLEntry
from app.models.gl_transaction import GLTransaction
from app.models.hoa_association import HOAContactLink
from app.models.hoa_meeting_workspace import HOAMeetingParticipation, HOAMotionDraft
from app.models.property import Property, PropertyAssignment
from app.models.user import Organization, User, UserRole
from app.routers import hoa_associations as hoa
from app.routers import hoa_meeting_drafts as meeting
from app.routers import hoa_meeting_workspace as api
from app.schemas.hoa_association import HOAAssociationIn, HOAContactLinkIn
from app.schemas.hoa_meeting_draft import HOAMeetingDraftIn
from app.schemas.hoa_meeting_workspace import HOAMeetingAttendanceIn, HOAMotionDraftIn
from app.services.entity_notes import _model_for_table


@pytest.fixture(autouse=True)
def access(monkeypatch):
    monkeypatch.setattr(hoa, "permission_allows_user", lambda *a, **k: True)
    monkeypatch.setattr(hoa, "resolve_customer_features", lambda *a, **k: [
        SimpleNamespace(key=hoa.FEATURE_KEY, allowed=True),
    ])


def _db():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, expire_on_commit=False)(), engine


def _seed(db):
    first = Organization(name="HOA Meeting Staff", slug="hoa-meeting-staff")
    other = Organization(name="HOA Foreign Meeting", slug="hoa-foreign-meeting")
    db.add_all([first, other]); db.flush()
    users = []
    for org, role, name in (
        (first, UserRole.ADMIN, "admin"),
        (first, UserRole.OWNER, "owner"),
        (first, UserRole.MANAGER, "manager"),
        (first, UserRole.CREW, "crew"),
        (first, UserRole.TENANT, "tenant"),
        (other, UserRole.ADMIN, "foreign"),
    ):
        row = User(organization_id=org.id, role=role,
                   email=f"hoa-workspace-{name}@example.test",
                   first_name=name, last_name="Meeting",
                   hashed_password="x", is_active=True)
        db.add(row); users.append(row)
    db.flush()
    props = []
    for org, name in ((first, "Assigned"), (first, "Unassigned"), (other, "Foreign")):
        row = Property(organization_id=org.id, name=name,
                       address_line1="100 Main", city="Cleveland",
                       state="OH", zip_code="44113", is_active=True)
        db.add(row); props.append(row)
    db.flush()
    db.add(PropertyAssignment(
        property_id=props[0].id, user_id=users[2].id,
        role=UserRole.MANAGER, is_active=True,
    ))
    contacts = []
    for org, name in ((first, "One"), (first, "Two"), (other, "Foreign")):
        row = Contact(organization_id=org.id, display_name=name,
                      contact_type="PERSON", is_active=True)
        db.add(row); contacts.append(row)
    db.commit()
    assoc = hoa.create_association(
        HOAAssociationIn(name="Meeting Planning", property_ids=[props[0].id, props[1].id]),
        db=db, current_user=users[0],
    )
    meeting_row = meeting.create_meeting_draft(
        assoc.id, HOAMeetingDraftIn(
            property_id=props[0].id, title="Synthetic planning meeting",
            proposed_on=date(2026, 10, 10),
        ), db=db, current_user=users[0],
    )
    primary = hoa.add_contact_link(
        assoc.id, HOAContactLinkIn(property_id=props[0].id, contact_id=contacts[0].id),
        db=db, current_user=users[0],
    )
    secondary = hoa.add_contact_link(
        assoc.id, HOAContactLinkIn(property_id=props[1].id, contact_id=contacts[1].id),
        db=db, current_user=users[0],
    )
    return users, props, assoc, meeting_row, primary, secondary


def _attendance(prop, link_id, **extra):
    return HOAMeetingAttendanceIn(
        property_id=prop.id, contact_link_id=link_id, staff_attendance="PRESENT",
        **extra,
    )


def _motion(prop, text="Staff proposes a landscaping review", **extra):
    return HOAMotionDraftIn(property_id=prop.id, proposed_motion=text, **extra)


def test_workspace_staff_attendance_motions_and_no_finance():
    db, engine = _db()
    try:
        (admin, owner, manager, crew, tenant, foreign), (prop, _, _), assoc, plan, contact, _ = _seed(db)
        before = (db.query(Charge).count(), db.query(GLTransaction).count(), db.query(GLEntry).count())
        attended = api.record_attendance(
            assoc.id, plan.id, _attendance(prop, contact.id),
            db=db, current_user=admin,
        )
        assert attended.contact_name == "One"
        assert attended.status == "STAFF_REPORTED_UNVERIFIED"
        assert attended.staff_attendance == "PRESENT"
        revised = api.record_attendance(
            assoc.id, plan.id, HOAMeetingAttendanceIn(
                property_id=prop.id, contact_link_id=contact.id,
                staff_attendance="UNCONFIRMED",
            ), db=db, current_user=owner,
        )
        assert revised.id == attended.id and revised.staff_attendance == "UNCONFIRMED"
        motion = api.propose_motion(
            assoc.id, plan.id, _motion(prop), db=db, current_user=admin,
        )
        assert motion.status == "PROPOSED_ONLY" and motion.vote_enabled is False
        result = api.get_workspace(
            assoc.id, plan.id, Response(), property_id=prop.id,
            db=db, current_user=manager,
        )
        assert result.board_authority_verified is False
        assert result.quorum_certified is False
        assert result.vote_enabled is False
        assert [x.id for x in result.attendance] == [attended.id]
        assert [x.id for x in result.motions] == [motion.id]
        response = Response()
        api.get_workspace(assoc.id, plan.id, response, prop.id, db=db, current_user=admin)
        assert response.headers["cache-control"] == "no-store"
        assert db.query(AuditLog).filter(
            AuditLog.entity_type.in_(("hoa_meeting_participation", "hoa_motion_draft")),
        ).count() == 3
        api.archive_motion(
            assoc.id, plan.id, motion.id, prop.id, db=db, current_user=owner,
        )
        api.archive_attendance(
            assoc.id, plan.id, attended.id, prop.id, db=db, current_user=admin,
        )
        assert api.get_workspace(
            assoc.id, plan.id, Response(), prop.id, db=db, current_user=manager,
        ).motions == []
        assert db.query(HOAMotionDraft).count() == 1
        assert db.query(HOAMeetingParticipation).count() == 1
        assert (db.query(Charge).count(), db.query(GLTransaction).count(),
                db.query(GLEntry).count()) == before
    finally:
        db.close(); engine.dispose()


def test_workspace_scope_contacts_restrictions_and_live_revocation(monkeypatch):
    db, engine = _db()
    try:
        (admin, owner, manager, crew, tenant, foreign), (prop, other, outsider), assoc, plan, primary, secondary = _seed(db)
        saved = api.record_attendance(
            assoc.id, plan.id, _attendance(prop, primary.id), db=db, current_user=admin,
        )
        for actor, property_id in (
            (manager, other.id), (manager, outsider.id), (foreign, prop.id),
            (tenant, prop.id), (crew, prop.id),
        ):
            with pytest.raises(HTTPException):
                api.get_workspace(
                    assoc.id, plan.id, Response(), property_id=property_id,
                    db=db, current_user=actor,
                )
        for actor in (manager, crew, tenant, foreign):
            with pytest.raises(HTTPException):
                api.propose_motion(
                    assoc.id, plan.id, _motion(prop),
                    db=db, current_user=actor,
                )
        with pytest.raises(HTTPException) as e:
            api.record_attendance(
                assoc.id, plan.id, _attendance(prop, secondary.id),
                db=db, current_user=admin,
            )
        assert e.value.status_code == 404
        with pytest.raises(HTTPException) as e:
            api.get_workspace(
                assoc.id, plan.id, Response(), property_id=other.id,
                db=db, current_user=admin,
            )
        assert e.value.status_code == 404
        link = db.query(HOAContactLink).filter_by(id=primary.id).one()
        link.is_active = False
        db.flush()
        result = api.get_workspace(
            assoc.id, plan.id, Response(), property_id=prop.id,
            db=db, current_user=admin,
        )
        assert result.attendance == []
        with pytest.raises(HTTPException) as e:
            api.record_attendance(
                assoc.id, plan.id, _attendance(prop, primary.id), db=db, current_user=admin,
            )
        assert e.value.status_code == 404
        monkeypatch.setattr(hoa, "permission_allows_user", lambda *a, **k: False)
        with pytest.raises(HTTPException) as e:
            api.get_workspace(
                assoc.id, plan.id, Response(), property_id=prop.id,
                db=db, current_user=admin,
            )
        assert e.value.status_code == 403
        monkeypatch.setattr(
            hoa, "permission_allows_user",
            lambda db, *, user, menu_key: menu_key != "PEOPLE.CONTACTS",
        )
        with pytest.raises(HTTPException) as exc:
            api.get_workspace(
                assoc.id, plan.id, Response(), property_id=prop.id,
                db=db, current_user=admin,
            )
        assert exc.value.status_code == 403
        with pytest.raises(HTTPException) as exc:
            api.record_attendance(
                assoc.id, plan.id,
                HOAMeetingAttendanceIn(
                    property_id=prop.id, contact_link_id=primary.id,
                    staff_attendance="ABSENT",
                ),
                db=db, current_user=admin,
            )
        assert exc.value.status_code == 403
        # Motion preparation has no reason to expose contact identities.
        assert api.propose_motion(
            assoc.id, plan.id, _motion(prop), db=db, current_user=admin,
        ).vote_enabled is False
        monkeypatch.setattr(hoa, "permission_allows_user", lambda *a, **k: True)
        monkeypatch.setattr(hoa, "resolve_customer_features", lambda *a, **k: [])
        with pytest.raises(HTTPException) as e:
            api.get_workspace(
                assoc.id, plan.id, Response(), property_id=prop.id,
                db=db, current_user=admin,
            )
        assert e.value.status_code == 404
        assert db.query(Charge).count() == db.query(GLTransaction).count() == 0
        with pytest.raises(HTTPException):
            _model_for_table("hoa_meeting_participation")
        with pytest.raises(HTTPException):
            _model_for_table("hoa_motion_drafts")
    finally:
        db.rollback(); db.close(); engine.dispose()


def test_workspace_schema_guards_archive_and_no_relink_resurrection():
    db, engine = _db()
    try:
        (admin, owner, manager, crew, tenant, foreign), (prop, other, outsider), assoc, plan, primary, secondary = _seed(db)
        for kwargs in ({"board_approved": True}, {"voting_eligible": True}, {"quorum_met": True}):
            with pytest.raises(ValidationError):
                _motion(prop, **kwargs)
        with pytest.raises(ValidationError):
            _attendance(prop, primary.id, official_board_attendee=True)
        with pytest.raises(ValidationError):
            _motion(prop, "   ")
        attended = api.record_attendance(
            assoc.id, plan.id, _attendance(prop, primary.id), db=db, current_user=admin,
        )
        motion = api.propose_motion(
            assoc.id, plan.id, _motion(prop), db=db, current_user=admin,
        )
        hoa.update_association(
            assoc.id, HOAAssociationIn(
                name="Meeting Planning", property_ids=[other.id],
            ), db=db, current_user=owner,
        )
        with pytest.raises(HTTPException):
            api.get_workspace(assoc.id, plan.id, Response(), prop.id,
                              db=db, current_user=admin)
        hoa.update_association(
            assoc.id, HOAAssociationIn(
                name="Meeting Planning", property_ids=[prop.id, other.id],
            ), db=db, current_user=owner,
        )
        with pytest.raises(HTTPException):
            api.get_workspace(assoc.id, plan.id, Response(), prop.id,
                              db=db, current_user=admin)
        # The parent meeting remains soft-archived even after relink.
        assert db.query(HOAMotionDraft).filter_by(id=motion.id).one().is_active is False
        assert db.query(HOAMeetingParticipation).filter_by(id=attended.id).one().is_active is False
        assert db.query(Charge).count() == db.query(GLTransaction).count() == 0
    finally:
        db.close(); engine.dispose()


def test_contact_unlink_does_not_resurrect_historical_staff_attendance():
    db, engine = _db()
    try:
        (admin, owner, manager, crew, tenant, foreign), (prop, other, outside), assoc, plan, primary, secondary = _seed(db)
        saved = api.record_attendance(
            assoc.id, plan.id, _attendance(prop, primary.id),
            db=db, current_user=admin,
        )
        hoa.remove_contact_link(
            assoc.id, primary.id, prop.id, db=db, current_user=owner,
        )
        restored = hoa.add_contact_link(
            assoc.id, HOAContactLinkIn(
                property_id=prop.id,
                contact_id=db.query(HOAContactLink).filter_by(id=primary.id).one().contact_id,
            ), db=db, current_user=admin,
        )
        assert restored.id == primary.id
        result = api.get_workspace(
            assoc.id, plan.id, Response(), prop.id, db=db, current_user=admin,
        )
        assert result.attendance == []
        assert db.query(HOAMeetingParticipation).filter_by(id=saved.id).one().is_active is False
        with pytest.raises(HTTPException) as exc:
            api.record_attendance(
                assoc.id, plan.id, _attendance(prop, primary.id),
                db=db, current_user=admin,
            )
        assert exc.value.status_code == 409
        assert db.query(GLTransaction).count() == db.query(Charge).count() == 0
    finally:
        db.close()
        engine.dispose()
