"""Staff meeting participation/motions never certify board authority or post money."""
from __future__ import annotations

from datetime import date, timedelta
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
from app.models.hoa_meeting_draft import HOAMeetingDraft
from app.models.hoa_meeting_minutes import HOAMeetingMinutesApproval, HOAMeetingMinutesDraft
from app.routers import hoa_meeting_minutes as minutes
from app.routers import hoa_meeting_minutes_board as minutes_board
from app.routers import hoa_board as board_api
from app.routers import hoa_arc_board_decisions as arc_board
from app.schemas.hoa_board import HOABoardSeatIn, HOABoardAuthorizationIn
from app.schemas.hoa_meeting_minutes import HOAMinutesDraftIn
from app.schemas.hoa_meeting_minutes_approval import HOAMinutesBoardApprovalIn
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
        SimpleNamespace(key=hoa.HOA_FEATURE_KEY, allowed=True),
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


def _minutes_board_setup(db, monkeypatch):
    actors, props, assoc, plan, link, other_link = _seed(db)
    admin = actors[0]
    admin.is_verified = True
    db.query(Contact).filter(Contact.id == db.query(
        HOAContactLink.contact_id,
    ).filter(HOAContactLink.id == link.id).scalar()).one().email = admin.email
    db.query(HOAMeetingDraft).filter(HOAMeetingDraft.id == plan.id).one().proposed_on = date.today()
    db.flush()
    monkeypatch.setattr(arc_board, "resolve_customer_features", lambda *args, **kwargs: [
        SimpleNamespace(key=key, release_allowed=True, entitlement_allowed=True,
                        org_config_allowed=True)
        for key in arc_board.HOA_GATES
    ])
    seat = board_api.record_board_seat(
        assoc.id, HOABoardSeatIn(
            property_id=props[0].id, contact_link_id=link.id,
            proposed_role="CHAIR", staff_voting_eligible=True,
        ), db=db, current_user=admin,
    )
    board_api.authorize_board_seat(
        assoc.id, seat.id, HOABoardAuthorizationIn(
            property_id=props[0].id, user_id=admin.id, can_record_offline=True,
        ), db=db, current_user=admin,
    )
    return actors, props, assoc, plan, seat


def test_authorized_board_minutes_approval_is_immutable_scoped_and_zero_finance(monkeypatch):
    db, engine = _db()
    try:
        (admin, owner, manager, crew, tenant, foreign), (prop, other, outside), assoc, plan, seat = _minutes_board_setup(db, monkeypatch)
        prior = (db.query(Charge).count(), db.query(GLTransaction).count(),
                 db.query(GLEntry).count())
        draft = minutes.save_minutes_draft(
            assoc.id, plan.id, HOAMinutesDraftIn(
                property_id=prop.id, staff_minutes="Internal initial record",
            ), db=db, current_user=admin,
        )
        assert draft.revision == 1 and len(draft.content_sha256) == 64
        modified = minutes.save_minutes_draft(
            assoc.id, plan.id, HOAMinutesDraftIn(
                property_id=prop.id, staff_minutes="Board-reviewed final meeting minutes",
            ), db=db, current_user=owner,
        )
        assert modified.revision == 2 and modified.content_sha256 != draft.content_sha256
        response = Response()
        preview = minutes_board.board_minutes_preview(
            assoc.id, plan.id, response, property_id=prop.id,
            db=db, current_user=admin,
        )
        assert response.headers["cache-control"] == "no-store"
        assert preview.content_sha256 == modified.content_sha256
        stale = HOAMinutesBoardApprovalIn(
            property_id=prop.id, minutes_revision=1,
            content_sha256=draft.content_sha256, approval_note="Approve older revision",
        )
        with pytest.raises(HTTPException) as err:
            minutes_board.record_minutes_approval(
                assoc.id, plan.id, stale, db=db, current_user=admin,
            )
        assert err.value.status_code == 409
        payload = HOAMinutesBoardApprovalIn(
            property_id=prop.id, minutes_revision=preview.revision,
            content_sha256=preview.content_sha256,
            approval_note="The designated board member adopts this exact text.",
        )
        for actor in (owner, manager, tenant, foreign):
            with pytest.raises(HTTPException):
                minutes_board.record_minutes_approval(
                    assoc.id, plan.id, payload, db=db, current_user=actor,
                )
        for actor, property_id in ((admin, other.id), (admin, outside.id)):
            with pytest.raises(HTTPException):
                minutes_board.board_minutes_preview(
                    assoc.id, plan.id, Response(), property_id=property_id,
                    db=db, current_user=actor,
                )
        approved = minutes_board.record_minutes_approval(
            assoc.id, plan.id, payload, db=db, current_user=admin,
        )
        assert approved.status == "BOARD_MEMBER_APPROVED"
        assert approved.minutes_revision == 2
        assert approved.board_seat_id == seat.id
        assert approved.quorum_certified is False
        assert approved.full_board_vote_certified is False
        assert approved.financial_posting is False
        assert db.query(HOAMeetingMinutesApproval).count() == 1
        with pytest.raises(HTTPException) as duplicate:
            minutes_board.record_minutes_approval(
                assoc.id, plan.id, payload, db=db, current_user=admin,
            )
        assert duplicate.value.status_code == 409
        with pytest.raises(HTTPException) as edit:
            minutes.save_minutes_draft(
                assoc.id, plan.id, HOAMinutesDraftIn(
                    property_id=prop.id, staff_minutes="Changed after board approval",
                ), db=db, current_user=owner,
            )
        assert edit.value.status_code == 409
        with pytest.raises(HTTPException) as archive:
            minutes.archive_minutes_draft(
                assoc.id, plan.id, prop.id, db=db, current_user=owner,
            )
        assert archive.value.status_code == 409
        with pytest.raises(HTTPException) as archive_meeting:
            meeting.archive_meeting_draft(
                assoc.id, plan.id, prop.id, db=db, current_user=owner,
            )
        assert archive_meeting.value.status_code == 409
        assert db.get(HOAMeetingMinutesDraft, draft.id).staff_minutes == modified.staff_minutes
        assert (db.query(Charge).count(), db.query(GLTransaction).count(),
                db.query(GLEntry).count()) == prior
        events = db.query(AuditLog).filter(
            AuditLog.entity_type == "hoa_meeting_minutes_approval",
        ).all()
        assert len(events) == 1
        assert "Board-reviewed final meeting minutes" not in str(events[0].new_value)
        assert "designated board member adopts" not in str(events[0].new_value)
        with pytest.raises(HTTPException):
            _model_for_table("hoa_meeting_minutes_approvals")
    finally:
        db.rollback(); db.close(); engine.dispose()


def test_minutes_board_approval_requires_live_board_entitlement_and_meeting_date(monkeypatch):
    db, engine = _db()
    try:
        (admin, owner, manager, crew, tenant, foreign), (prop, other, outside), assoc, plan, seat = _minutes_board_setup(db, monkeypatch)
        draft = minutes.save_minutes_draft(
            assoc.id, plan.id, HOAMinutesDraftIn(
                property_id=prop.id, staff_minutes="Second meeting's initial minutes",
            ), db=db, current_user=admin,
        )
        payload = HOAMinutesBoardApprovalIn(
            property_id=prop.id, minutes_revision=draft.revision,
            content_sha256=draft.content_sha256, approval_note="Approval pending checks",
        )
        meeting_model = db.get(HOAMeetingDraft, plan.id)
        meeting_model.proposed_on = date.today() + timedelta(days=1)
        db.flush()
        with pytest.raises(HTTPException) as early:
            minutes_board.record_minutes_approval(
                assoc.id, plan.id, payload, db=db, current_user=admin,
            )
        assert early.value.status_code == 409
        meeting_model.proposed_on = date.today()
        db.flush()
        from app.models.hoa_board import HOABoardSeat
        board_seat = db.get(HOABoardSeat, seat.id)
        board_seat.decision_authorized = False
        db.flush()
        with pytest.raises(HTTPException):
            minutes_board.record_minutes_approval(
                assoc.id, plan.id, payload, db=db, current_user=admin,
            )
        board_seat.decision_authorized = True
        db.flush()
        monkeypatch.setattr(arc_board, "resolve_customer_features", lambda *args, **kwargs: [])
        with pytest.raises(HTTPException) as disabled:
            minutes_board.record_minutes_approval(
                assoc.id, plan.id, payload, db=db, current_user=admin,
            )
        assert disabled.value.status_code == 404
        assert db.query(HOAMeetingMinutesApproval).count() == 0
        with pytest.raises(ValidationError):
            HOAMinutesBoardApprovalIn(
                property_id=prop.id, minutes_revision=1,
                content_sha256="invalid", approval_note="Bad hash",
            )
        assert db.query(GLTransaction).count() == 0
    finally:
        db.rollback(); db.close(); engine.dispose()
