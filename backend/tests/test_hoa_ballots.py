"""Staff ballot observations do not certify eligibility, quorum or a legal vote."""
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
from app.models.gl_transaction import GLTransaction
from app.models.hoa_ballot import HOABallotRecord
from app.models.hoa_meeting_minutes import HOAMeetingMinutesDraft
from app.routers import hoa_meeting_minutes as minutes_api
from app.schemas.hoa_meeting_minutes import HOAMinutesDraftIn
from app.models.hoa_board import HOABoardSeat
from app.models.hoa_association import HOAContactLink
from app.models.contact import Contact
from app.models.property import Property, PropertyAssignment
from app.models.user import Organization, User, UserRole
from app.routers import (
    hoa_associations as hoa,
    hoa_board as board,
    hoa_ballots as api,
    hoa_meeting_drafts as meeting,
    hoa_meeting_workspace as workspace,
)
from app.schemas.hoa_association import HOAAssociationIn, HOAContactLinkIn
from app.schemas.hoa_board import HOABoardSeatIn
from app.schemas.hoa_ballot import HOABallotIn
from app.schemas.hoa_meeting_draft import HOAMeetingDraftIn
from app.schemas.hoa_meeting_workspace import HOAMotionDraftIn
from app.services.entity_notes import _model_for_table


@pytest.fixture(autouse=True)
def permissions(monkeypatch):
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
    org = Organization(name="Ballot Local", slug="ballot-local")
    foreign = Organization(name="Ballot Foreign", slug="ballot-foreign")
    db.add_all([org, foreign]); db.flush()
    actors = []
    for scope, role, name in (
        (org, UserRole.ADMIN, "admin"), (org, UserRole.OWNER, "owner"),
        (org, UserRole.MANAGER, "manager"), (org, UserRole.TENANT, "tenant"),
        (foreign, UserRole.ADMIN, "foreign"),
    ):
        row = User(organization_id=scope.id, role=role,
                   email=f"ballot-{name}@example.test", first_name=name,
                   last_name="Test", hashed_password="x", is_active=True)
        db.add(row); actors.append(row)
    db.flush()
    props = []
    for scope, label in ((org, "Linked"), (org, "Unassigned"), (foreign, "Outside")):
        prop = Property(organization_id=scope.id, name=label,
                        address_line1="1 Main", city="Cleveland", state="OH",
                        zip_code="44113", is_active=True)
        db.add(prop); props.append(prop)
    db.flush()
    db.add(PropertyAssignment(property_id=props[0].id,
                              user_id=actors[2].id, role=UserRole.MANAGER,
                              is_active=True))
    contact = Contact(organization_id=org.id, display_name="Staff ballot contact",
                      contact_type="PERSON", is_active=True)
    db.add(contact); db.commit()
    assoc = hoa.create_association(
        HOAAssociationIn(name="Synthetic Board", property_ids=[
            props[0].id, props[1].id,
        ]), db=db, current_user=actors[0],
    )
    link = hoa.add_contact_link(
        assoc.id, HOAContactLinkIn(property_id=props[0].id, contact_id=contact.id),
        db=db, current_user=actors[0],
    )
    plan = meeting.create_meeting_draft(
        assoc.id, HOAMeetingDraftIn(
            property_id=props[0].id, title="Synthetic meeting",
            proposed_on=date(2026, 11, 1),
        ), db=db, current_user=actors[0],
    )
    motion = workspace.propose_motion(
        assoc.id, plan.id, HOAMotionDraftIn(
            property_id=props[0].id, proposed_motion="Synthetic motion",
        ), db=db, current_user=actors[0],
    )
    seat = board.record_board_seat(
        assoc.id, HOABoardSeatIn(
            property_id=props[0].id, contact_link_id=link.id,
            proposed_role="DIRECTOR", staff_voting_eligible=True,
        ), db=db, current_user=actors[0],
    )
    return actors, props, assoc, link, plan, motion, seat


def _payload(prop, seat, **extra):
    return HOABallotIn(
        property_id=prop.id, board_seat_id=seat.id,
        staff_reported_choice="FOR", **extra,
    )


def test_ballot_reporting_is_not_legal_vote_and_never_posts_finance():
    db, engine = _db()
    try:
        (admin, owner, manager, tenant, foreign), (prop, other, outside), assoc, link, plan, motion, seat = _seed(db)
        before = (db.query(Charge).count(), db.query(GLTransaction).count())
        recorded = api.record_ballot(
            assoc.id, plan.id, motion.id, _payload(prop, seat),
            db=db, current_user=admin,
        )
        assert recorded.staff_reported_choice == "FOR"
        assert recorded.status == "STAFF_REPORTED_UNVERIFIED"
        assert recorded.vote_effective is False
        assert recorded.board_authority_verified is False
        response = Response()
        result = api.list_ballot_records(
            assoc.id, plan.id, motion.id, response, property_id=prop.id,
            db=db, current_user=manager,
        )
        assert result.quorum_certified is False and result.approval_certified is False
        assert result.vote_effective is False
        assert [r.id for r in result.ballots] == [recorded.id]
        assert response.headers["cache-control"] == "no-store"
        assert (db.query(Charge).count(), db.query(GLTransaction).count()) == before
        assert db.query(AuditLog).filter(AuditLog.entity_type == "hoa_ballot_record").count() == 1
        with pytest.raises(HTTPException) as exc:
            api.record_ballot(
                assoc.id, plan.id, motion.id, _payload(prop, seat),
                db=db, current_user=owner,
            )
        assert exc.value.status_code == 409
        api.archive_ballot_record(
            assoc.id, plan.id, motion.id, recorded.id, prop.id,
            db=db, current_user=admin,
        )
        assert api.list_ballot_records(
            assoc.id, plan.id, motion.id, Response(), prop.id,
            db=db, current_user=manager,
        ).ballots == []
        with pytest.raises(HTTPException) as exc:
            api.record_ballot(
                assoc.id, plan.id, motion.id, _payload(prop, seat),
                db=db, current_user=owner,
            )
        assert exc.value.status_code == 409
        assert db.query(HOABallotRecord).count() == 1
        assert db.query(GLTransaction).count() == db.query(Charge).count() == 0
    finally:
        db.close(); engine.dispose()


def test_ballot_scope_live_eligibility_and_revocation(monkeypatch):
    db, engine = _db()
    try:
        (admin, owner, manager, tenant, foreign), (prop, other, outside), assoc, link, plan, motion, seat = _seed(db)
        for actor, property_id in (
            (manager, other.id), (foreign, prop.id), (tenant, prop.id),
            (manager, outside.id),
        ):
            with pytest.raises(HTTPException):
                api.list_ballot_records(
                    assoc.id, plan.id, motion.id, Response(), property_id,
                    db=db, current_user=actor,
                )
        for actor in (manager, tenant, foreign):
            with pytest.raises(HTTPException):
                api.record_ballot(
                    assoc.id, plan.id, motion.id, _payload(prop, seat),
                    db=db, current_user=actor,
                )
        with pytest.raises(HTTPException):
            api.record_ballot(
                assoc.id, plan.id, motion.id, _payload(other, seat),
                db=db, current_user=admin,
            )
        db.get(HOABoardSeat, seat.id).staff_voting_eligible = False
        db.flush()
        with pytest.raises(HTTPException) as exc:
            api.record_ballot(
                assoc.id, plan.id, motion.id, _payload(prop, seat),
                db=db, current_user=admin,
            )
        assert exc.value.status_code == 422
        db.get(HOABoardSeat, seat.id).staff_voting_eligible = True
        db.flush()
        saved = api.record_ballot(
            assoc.id, plan.id, motion.id, _payload(prop, seat),
            db=db, current_user=admin,
        )
        db.get(HOABoardSeat, seat.id).is_active = False
        db.flush()
        assert api.list_ballot_records(
            assoc.id, plan.id, motion.id, Response(), prop.id,
            db=db, current_user=admin,
        ).ballots == []
        monkeypatch.setattr(hoa, "permission_allows_user", lambda *a, **k: False)
        with pytest.raises(HTTPException) as exc:
            api.list_ballot_records(
                assoc.id, plan.id, motion.id, Response(), prop.id,
                db=db, current_user=admin,
            )
        assert exc.value.status_code == 403
        monkeypatch.setattr(hoa, "permission_allows_user", lambda *a, **k: True)
        monkeypatch.setattr(hoa, "resolve_customer_features", lambda *a, **k: [])
        with pytest.raises(HTTPException) as exc:
            api.list_ballot_records(
                assoc.id, plan.id, motion.id, Response(), prop.id,
                db=db, current_user=admin,
            )
        assert exc.value.status_code == 404
        assert db.get(HOABallotRecord, saved.id).is_active is True
    finally:
        db.rollback(); db.close(); engine.dispose()


def test_ballot_motion_archive_contact_revocation_and_schema_fail_closed():
    db, engine = _db()
    try:
        (admin, owner, manager, tenant, foreign), (prop, other, outside), assoc, link, plan, motion, seat = _seed(db)
        for field in ("legal_vote", "quorum_met", "board_approved", "signed_by_member"):
            with pytest.raises(ValidationError):
                HOABallotIn(property_id=prop.id, board_seat_id=seat.id,
                            staff_reported_choice="FOR", **{field: True})
        with pytest.raises(ValidationError):
            HOABallotIn(property_id=prop.id, board_seat_id=seat.id,
                        staff_reported_choice="APPROVED")
        with pytest.raises(HTTPException):
            _model_for_table("hoa_ballot_records")
        saved = api.record_ballot(
            assoc.id, plan.id, motion.id, _payload(prop, seat),
            db=db, current_user=admin,
        )
        workspace.archive_motion(
            assoc.id, plan.id, motion.id, prop.id,
            db=db, current_user=owner,
        )
        with pytest.raises(HTTPException) as exc:
            api.list_ballot_records(
                assoc.id, plan.id, motion.id, Response(), prop.id,
                db=db, current_user=admin,
            )
        assert exc.value.status_code == 404
        assert db.query(GLTransaction).count() == db.query(Charge).count() == 0
        assert db.get(HOABallotRecord, saved.id).is_active is False
    finally:
        db.close(); engine.dispose()


def test_minutes_recorded_revised_archived_are_not_certified_governance():
    db, engine = _db()
    try:
        (admin, owner, manager, tenant, foreign), (prop, other, outside), assoc, link, plan, motion, seat = _seed(db)
        payload = HOAMinutesDraftIn(property_id=prop.id, staff_minutes="  Staff noted agenda items  ")
        first = minutes_api.save_minutes_draft(
            assoc.id, plan.id, payload, db=db, current_user=admin,
        )
        assert first.staff_minutes == "Staff noted agenda items"
        assert first.status == "STAFF_DRAFT_UNVERIFIED"
        assert first.legal_minutes_effective is False
        assert first.quorum_certified is False
        assert first.board_approval_certified is False
        assert "adopted" not in first.model_dump()
        response = Response()
        selected = minutes_api.get_minutes_draft(
            assoc.id, plan.id, response, prop.id, db=db, current_user=manager,
        )
        assert selected.id == first.id
        assert response.headers["cache-control"] == "no-store"
        changed = minutes_api.save_minutes_draft(
            assoc.id, plan.id, HOAMinutesDraftIn(
                property_id=prop.id, staff_minutes="Second staff draft"
            ), db=db, current_user=owner,
        )
        assert changed.id == first.id and changed.staff_minutes == "Second staff draft"
        assert db.query(HOAMeetingMinutesDraft).count() == 1
        minutes_api.archive_minutes_draft(
            assoc.id, plan.id, prop.id, db=db, current_user=admin,
        )
        assert minutes_api.get_minutes_draft(
            assoc.id, plan.id, Response(), prop.id, db=db, current_user=admin,
        ) is None
        with pytest.raises(HTTPException) as exc:
            minutes_api.save_minutes_draft(
                assoc.id, plan.id, payload, db=db, current_user=admin,
            )
        assert exc.value.status_code == 409
        assert db.query(AuditLog).filter(
            AuditLog.entity_type == "hoa_meeting_minutes_draft",
        ).count() == 3
        assert db.query(Charge).count() == db.query(GLTransaction).count() == 0
    finally:
        db.close(); engine.dispose()


def test_minutes_scope_permissions_schema_and_meeting_archive(monkeypatch):
    db, engine = _db()
    try:
        (admin, owner, manager, tenant, foreign), (prop, other, outside), assoc, link, plan, motion, seat = _seed(db)
        payload = HOAMinutesDraftIn(property_id=prop.id, staff_minutes="Staff only")
        for bad in ({'legal_minutes_effective': True}, {'approved': True},
                    {'official_notice': True}, {'gl_account_id': 1}):
            with pytest.raises(ValidationError):
                HOAMinutesDraftIn(property_id=prop.id, staff_minutes="Test", **bad)
        with pytest.raises(ValidationError):
            HOAMinutesDraftIn(property_id=prop.id, staff_minutes=" ")
        for actor, pid in ((manager, other.id), (foreign, prop.id),
                           (tenant, prop.id), (manager, outside.id)):
            with pytest.raises(HTTPException):
                minutes_api.get_minutes_draft(
                    assoc.id, plan.id, Response(), pid,
                    db=db, current_user=actor,
                )
        for actor in (manager, tenant, foreign):
            with pytest.raises(HTTPException):
                minutes_api.save_minutes_draft(
                    assoc.id, plan.id, payload, db=db, current_user=actor,
                )
        with pytest.raises(HTTPException):
            minutes_api.save_minutes_draft(
                assoc.id, plan.id, HOAMinutesDraftIn(
                    property_id=other.id, staff_minutes="Out of scope"
                ), db=db, current_user=admin,
            )
        first = minutes_api.save_minutes_draft(
            assoc.id, plan.id, payload, db=db, current_user=admin,
        )
        with pytest.raises(HTTPException):
            _model_for_table("hoa_meeting_minutes_drafts")
        monkeypatch.setattr(hoa, "permission_allows_user", lambda *a, **k: False)
        with pytest.raises(HTTPException) as exc:
            minutes_api.get_minutes_draft(
                assoc.id, plan.id, Response(), prop.id,
                db=db, current_user=admin,
            )
        assert exc.value.status_code == 403
        monkeypatch.setattr(hoa, "permission_allows_user", lambda *a, **k: True)
        monkeypatch.setattr(hoa, "resolve_customer_features", lambda *a, **k: [])
        with pytest.raises(HTTPException) as exc:
            minutes_api.get_minutes_draft(
                assoc.id, plan.id, Response(), prop.id,
                db=db, current_user=admin,
            )
        assert exc.value.status_code == 404
        monkeypatch.setattr(hoa, "resolve_customer_features", lambda *a, **k: [
            SimpleNamespace(key=hoa.FEATURE_KEY, allowed=True),
        SimpleNamespace(key=hoa.HOA_FEATURE_KEY, allowed=True)
        ])
        meeting.archive_meeting_draft(
            assoc.id, plan.id, prop.id, db=db, current_user=owner,
        )
        assert db.get(HOAMeetingMinutesDraft, first.id).is_active is False
        with pytest.raises(HTTPException):
            minutes_api.get_minutes_draft(
                assoc.id, plan.id, Response(), prop.id,
                db=db, current_user=admin,
            )
        assert db.query(Charge).count() == db.query(GLTransaction).count() == 0
    finally:
        db.close(); engine.dispose()
