"""HOA observation intake never creates legal notices, fines, or finance."""
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
from app.models.gl_transaction import GLTransaction
from app.models.hoa_observation import HOAObservation
from app.models.lease import Lease
from app.models.property import Property, PropertyAssignment
from app.models.user import Organization, User, UserRole
from app.routers import hoa_associations as hoa
from app.routers import hoa_observations as api
from app.schemas.hoa_association import HOAAssociationIn
from app.schemas.hoa_observation import HOAObservationIn
from app.services.entity_notes import _model_for_table


@pytest.fixture(autouse=True)
def access(monkeypatch):
    # The shared _scope helper delegates to the source association module.
    monkeypatch.setattr(hoa, "permission_allows_user", lambda *a, **kw: True)
    monkeypatch.setattr(hoa, "resolve_customer_features", lambda *a, **kw: [
        SimpleNamespace(key=hoa.FEATURE_KEY, allowed=True),
    ])


def _db():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, expire_on_commit=False)(), engine


def _seed(db):
    org = Organization(name="HOA Observations", slug="hoa-observations")
    other = Organization(name="HOA Observations Other", slug="hoa-observations-other")
    db.add_all([org, other])
    db.flush()
    users = []
    for o, role, email in (
        (org, UserRole.ADMIN, "admin"), (org, UserRole.OWNER, "owner"),
        (org, UserRole.MANAGER, "manager"), (org, UserRole.TENANT, "tenant"),
        (other, UserRole.ADMIN, "foreign"),
    ):
        person = User(
            organization_id=o.id, role=role, email=f"hoa-obs-{email}@example.test",
            first_name=email, last_name="Observer", hashed_password="x", is_active=True,
        )
        db.add(person)
        users.append(person)
    db.flush()
    props = []
    for o, name in ((org, "Assigned"), (org, "Unassigned"), (other, "Foreign")):
        prop = Property(
            organization_id=o.id, name=name, address_line1="100 Test",
            city="Cleveland", state="OH", zip_code="44113", is_active=True,
        )
        db.add(prop)
        props.append(prop)
    db.flush()
    db.add(PropertyAssignment(
        property_id=props[0].id, user_id=users[2].id,
        role=UserRole.MANAGER, is_active=True,
    ))
    db.commit()
    assoc = hoa.create_association(HOAAssociationIn(
        name="Recorded HOA", property_ids=[props[0].id, props[1].id]),
        db=db, current_user=users[0],
    )
    return users, props, assoc


def _payload(property_id, **changes):
    values = dict(
        property_id=property_id, summary="Roof debris seen at walk-through",
        observed_on=date(2026, 9, 1), details="Staff note, not a ruling.",
    )
    values.update(changes)
    return HOAObservationIn(**values)


def test_staff_observation_crud_scope_audit_and_zero_finance():
    db, engine = _db()
    try:
        (admin, owner, manager, tenant, foreign), (assigned, unassigned, other), assoc = _seed(db)
        first = api.create_observation(assoc.id, _payload(assigned.id),
                                       db=db, current_user=admin)
        second = api.create_observation(assoc.id, _payload(unassigned.id),
                                        db=db, current_user=owner)
        assert first.status == second.status == "STAFF_RECORDED"
        res = Response()
        items = api.list_observations(assoc.id, res, assigned.id,
                                      db=db, current_user=manager)
        assert res.headers["cache-control"] == "no-store"
        assert [item.id for item in items] == [first.id]
        edited = api.update_observation(
            assoc.id, first.id, _payload(assigned.id, details="Reinspection noted."),
            db=db, current_user=owner,
        )
        assert edited.details == "Reinspection noted."
        api.archive_observation(assoc.id, first.id, assigned.id,
                                db=db, current_user=admin)
        assert api.list_observations(assoc.id, Response(), assigned.id,
                                      db=db, current_user=admin) == []
        assert db.query(HOAObservation).count() == 2
        assert db.query(AuditLog).filter(
            AuditLog.entity_type == "hoa_observation",
        ).count() == 4
        assert db.query(GLTransaction).count() == db.query(Charge).count() == db.query(Lease).count() == 0
        assert "notice" not in edited.model_dump()
        assert "fine_amount" not in edited.model_dump()
    finally:
        db.close(); engine.dispose()


def test_manager_cross_org_and_permission_revocation(monkeypatch):
    db, engine = _db()
    try:
        (admin, owner, manager, tenant, foreign), (assigned, unassigned, other), assoc = _seed(db)
        first = api.create_observation(assoc.id, _payload(assigned.id), db=db, current_user=admin)
        for actor, prop in ((foreign, assigned), (manager, unassigned), (manager, other)):
            with pytest.raises(HTTPException) as exc:
                api.list_observations(assoc.id, Response(), prop.id, db=db, current_user=actor)
            assert exc.value.status_code == 404
        for actor in (manager, tenant):
            with pytest.raises(HTTPException) as exc:
                api.create_observation(assoc.id, _payload(assigned.id),
                                       db=db, current_user=actor)
            assert exc.value.status_code == 403
        with pytest.raises(HTTPException) as exc:
            api.update_observation(assoc.id, first.id, _payload(other.id),
                                   db=db, current_user=admin)
        assert exc.value.status_code == 404
        monkeypatch.setattr(hoa, "permission_allows_user", lambda *a, **kw: False)
        with pytest.raises(HTTPException) as exc:
            api.list_observations(assoc.id, Response(), assigned.id, db=db, current_user=admin)
        assert exc.value.status_code == 403
        assert db.query(GLTransaction).count() == db.query(Charge).count() == 0
    finally:
        db.rollback(); db.close(); engine.dispose()


def test_observation_excludes_legal_and_payer_fields():
    for values in (
        {"summary": " "}, {"observed_on": date.today() + timedelta(days=1)},
        {"fine_amount": "500"}, {"notice_sent_on": date(2026, 9, 1)},
        {"cure_deadline": date(2026, 9, 5)}, {"tenant_id": 10},
        {"hearing_on": date(2026, 9, 20)}, {"legal_status": "CONFIRMED"},
        {"details": "x" * 1001},
    ):
        with pytest.raises(ValidationError):
            _payload(1, **values)


def test_unlink_archive_and_relink_never_restore_observations():
    db, engine = _db()
    try:
        (admin, owner, manager, tenant, foreign), (assigned, unassigned, other), assoc = _seed(db)
        first = api.create_observation(assoc.id, _payload(assigned.id), db=db, current_user=admin)
        second = api.create_observation(assoc.id, _payload(unassigned.id), db=db, current_user=admin)
        hoa.update_association(assoc.id, HOAAssociationIn(
            name="Recorded HOA", property_ids=[unassigned.id]),
            db=db, current_user=admin)
        with pytest.raises(HTTPException) as exc:
            api.list_observations(assoc.id, Response(), assigned.id, db=db, current_user=admin)
        assert exc.value.status_code == 404
        hoa.update_association(assoc.id, HOAAssociationIn(
            name="Recorded HOA", property_ids=[assigned.id, unassigned.id]),
            db=db, current_user=admin)
        assert api.list_observations(assoc.id, Response(), assigned.id,
                                     db=db, current_user=admin) == []
        assert db.query(HOAObservation).filter_by(id=first.id).one().is_active is False
        hoa.archive_association(assoc.id, db=db, current_user=admin)
        assert db.query(HOAObservation).filter_by(id=second.id).one().is_active is False
        with pytest.raises(HTTPException) as exc:
            api.list_observations(assoc.id, Response(), unassigned.id,
                                  db=db, current_user=admin)
        assert exc.value.status_code == 404
        with pytest.raises(HTTPException) as exc:
            _model_for_table("hoa_observations")
        assert exc.value.status_code == 404
        assert db.query(GLTransaction).count() == db.query(Charge).count() == db.query(Lease).count() == 0
    finally:
        db.rollback(); db.close(); engine.dispose()


def test_staff_observation_ui_payload_keeps_manager_read_only():
    db, engine = _db()
    try:
        (admin, owner, manager, tenant, foreign), (assigned, unassigned, other), assoc = _seed(db)
        row = api.create_observation(assoc.id, _payload(assigned.id), db=db, current_user=admin)
        visible = api.list_observations(assoc.id, Response(), assigned.id, db=db, current_user=manager)
        assert len(visible) == 1
        assert visible[0].id == row.id
        assert visible[0].status == "STAFF_RECORDED"
        assert set(visible[0].model_dump()) == {
            "property_id", "summary", "observed_on", "details",
            "id", "association_id", "status", "updated_at",
        }
        with pytest.raises(HTTPException) as exc:
            api.archive_observation(assoc.id, row.id, assigned.id, db=db, current_user=manager)
        assert exc.value.status_code == 403
        assert db.query(HOAObservation).filter_by(id=row.id).one().is_active
        assert db.query(GLTransaction).count() == db.query(Charge).count() == 0
    finally:
        db.rollback()
        db.close()
        engine.dispose()


def test_staff_meeting_drafts_crud_scope_audit_and_no_governance_or_finance():
    from app.models.hoa_meeting_draft import HOAMeetingDraft
    from app.routers import hoa_meeting_drafts as planning
    from app.schemas.hoa_meeting_draft import HOAMeetingDraftIn

    db, engine = _db()
    try:
        (admin, owner, manager, tenant, foreign), (assigned, unassigned, other), assoc = _seed(db)
        payload = HOAMeetingDraftIn(
            property_id=assigned.id, title=" Budget discussion ",
            proposed_on=date(2026, 11, 1), staff_agenda="Tentative agenda only.",
        )
        created = planning.create_meeting_draft(assoc.id, payload, db=db, current_user=admin)
        assert created.status == "STAFF_DRAFT"
        assert created.title == "Budget discussion"
        out = planning.list_meeting_drafts(assoc.id, Response(), assigned.id, db=db, current_user=manager)
        assert [x.id for x in out] == [created.id]
        assert not ({"vote", "quorum", "notice", "minutes", "fine", "approved"} & set(out[0].model_dump()))
        revised = planning.update_meeting_draft(
            assoc.id, created.id, HOAMeetingDraftIn(
                property_id=assigned.id, title="New agenda", proposed_on=date(2026, 11, 3),
            ), db=db, current_user=owner,
        )
        assert revised.title == "New agenda"
        planning.archive_meeting_draft(assoc.id, created.id, assigned.id, db=db, current_user=admin)
        assert planning.list_meeting_drafts(assoc.id, Response(), assigned.id,
                                            db=db, current_user=admin) == []
        assert db.query(HOAMeetingDraft).count() == 1
        assert db.query(AuditLog).filter(AuditLog.entity_type == "hoa_meeting_draft").count() == 3
        assert db.query(GLTransaction).count() == db.query(Charge).count() == db.query(Lease).count() == 0
    finally:
        db.rollback()
        db.close()
        engine.dispose()


def test_staff_meeting_drafts_access_revocation_and_input_contract(monkeypatch):
    from app.routers import hoa_meeting_drafts as planning
    from app.schemas.hoa_meeting_draft import HOAMeetingDraftIn

    db, engine = _db()
    try:
        (admin, owner, manager, tenant, foreign), (assigned, unassigned, other), assoc = _seed(db)
        payload = HOAMeetingDraftIn(
            property_id=assigned.id, title="Planning only", proposed_on=date(2026, 11, 1),
        )
        created = planning.create_meeting_draft(assoc.id, payload, db=db, current_user=admin)
        for actor, prop in ((foreign, assigned), (manager, unassigned), (manager, other)):
            with pytest.raises(HTTPException) as exc:
                planning.list_meeting_drafts(assoc.id, Response(), prop.id, db=db, current_user=actor)
            assert exc.value.status_code == 404
        for actor in (manager, tenant):
            with pytest.raises(HTTPException) as exc:
                planning.update_meeting_draft(
                    assoc.id, created.id, payload, db=db, current_user=actor,
                )
            assert exc.value.status_code == 403
        with pytest.raises(HTTPException) as exc:
            planning.archive_meeting_draft(
                assoc.id, created.id, other.id, db=db, current_user=admin,
            )
        assert exc.value.status_code == 404
        monkeypatch.setattr(hoa, "permission_allows_user", lambda *a, **kw: False)
        with pytest.raises(HTTPException) as exc:
            planning.list_meeting_drafts(
                assoc.id, Response(), assigned.id, db=db, current_user=admin,
            )
        assert exc.value.status_code == 403
        for field in ("vote", "quorum", "minutes", "notice_sent_on", "tenant_id", "fine_amount"):
            with pytest.raises(ValidationError):
                HOAMeetingDraftIn(
                    property_id=assigned.id, title="Staff", proposed_on=date(2026, 11, 1),
                    **{field: "never"},
                )
        assert db.query(Charge).count() == db.query(GLTransaction).count() == 0
    finally:
        db.rollback()
        db.close()
        engine.dispose()


def test_meeting_plan_unlink_relink_and_association_archive_do_not_resurrect():
    from app.models.hoa_meeting_draft import HOAMeetingDraft
    from app.routers import hoa_meeting_drafts as planning
    from app.schemas.hoa_meeting_draft import HOAMeetingDraftIn

    db, engine = _db()
    try:
        (admin, owner, manager, tenant, foreign), (assigned, unassigned, other), assoc = _seed(db)
        def draft(prop_id):
            return HOAMeetingDraftIn(
                property_id=prop_id, title="Staff proposed meeting", proposed_on=date(2026, 11, 1),
            )
        first = planning.create_meeting_draft(assoc.id, draft(assigned.id), db=db, current_user=admin)
        second = planning.create_meeting_draft(assoc.id, draft(unassigned.id), db=db, current_user=admin)
        hoa.update_association(assoc.id, HOAAssociationIn(
            name="Recorded HOA", property_ids=[unassigned.id],
        ), db=db, current_user=admin)
        hoa.update_association(assoc.id, HOAAssociationIn(
            name="Recorded HOA", property_ids=[assigned.id, unassigned.id],
        ), db=db, current_user=admin)
        assert planning.list_meeting_drafts(
            assoc.id, Response(), assigned.id, db=db, current_user=admin,
        ) == []
        assert db.query(HOAMeetingDraft).filter_by(id=first.id).one().is_active is False
        hoa.archive_association(assoc.id, db=db, current_user=admin)
        assert db.query(HOAMeetingDraft).filter_by(id=second.id).one().is_active is False
        with pytest.raises(HTTPException) as exc:
            _model_for_table("hoa_meeting_drafts")
        assert exc.value.status_code == 404
        assert db.query(Charge).count() == db.query(GLTransaction).count() == db.query(Lease).count() == 0
    finally:
        db.rollback()
        db.close()
        engine.dispose()


def test_arc_staff_intake_crud_and_zero_official_or_financial_effects():
    from app.models.hoa_arc_intake import HOAARCIntake
    from app.routers import hoa_arc_intake as arc
    from app.schemas.hoa_arc_intake import HOAARCIntakeIn

    db, engine = _db()
    try:
        (admin, owner, manager, tenant, foreign), (assigned, unassigned, other), assoc = _seed(db)
        payload = HOAARCIntakeIn(
            property_id=assigned.id, project_title=" Patio extension ",
            staff_noted_on=date(2026, 9, 20),
            staff_description="Staff summary only.",
        )
        recorded = arc.create_arc_intake(assoc.id, payload, db=db, current_user=admin)
        assert recorded.status == "STAFF_INTAKE"
        assert recorded.project_title == "Patio extension"
        read = arc.list_arc_intakes(assoc.id, Response(), assigned.id,
                                    db=db, current_user=manager)
        assert [row.id for row in read] == [recorded.id]
        assert not ({"applicant_id", "approval", "denial", "permit", "fee", "deadline"} & set(read[0].model_dump()))
        changed = arc.update_arc_intake(
            assoc.id, recorded.id, HOAARCIntakeIn(
                property_id=assigned.id, project_title="Revised staff note",
                staff_noted_on=date(2026, 9, 21),
            ), db=db, current_user=owner,
        )
        assert changed.project_title == "Revised staff note"
        arc.archive_arc_intake(assoc.id, recorded.id, assigned.id, db=db, current_user=admin)
        assert arc.list_arc_intakes(assoc.id, Response(), assigned.id,
                                    db=db, current_user=admin) == []
        assert db.query(HOAARCIntake).count() == 1
        assert db.query(AuditLog).filter(AuditLog.entity_type == "hoa_arc_intake").count() == 3
        assert db.query(GLTransaction).count() == db.query(Charge).count() == db.query(Lease).count() == 0
    finally:
        db.rollback(); db.close(); engine.dispose()


def test_arc_staff_intake_scopes_revocation_and_refuses_decision_fields(monkeypatch):
    from app.routers import hoa_arc_intake as arc
    from app.schemas.hoa_arc_intake import HOAARCIntakeIn

    db, engine = _db()
    try:
        (admin, owner, manager, tenant, foreign), (assigned, unassigned, other), assoc = _seed(db)
        payload = HOAARCIntakeIn(
            property_id=assigned.id, project_title="Staff only", staff_noted_on=date(2026, 9, 20),
        )
        first = arc.create_arc_intake(assoc.id, payload, db=db, current_user=admin)
        for actor, prop in ((foreign, assigned), (manager, unassigned), (manager, other)):
            with pytest.raises(HTTPException) as exc:
                arc.list_arc_intakes(assoc.id, Response(), prop.id, db=db, current_user=actor)
            assert exc.value.status_code == 404
        for actor in (manager, tenant):
            with pytest.raises(HTTPException) as exc:
                arc.update_arc_intake(assoc.id, first.id, payload, db=db, current_user=actor)
            assert exc.value.status_code == 403
        with pytest.raises(HTTPException) as exc:
            arc.archive_arc_intake(assoc.id, first.id, other.id, db=db, current_user=admin)
        assert exc.value.status_code == 404
        monkeypatch.setattr(hoa, "permission_allows_user", lambda *a, **kw: False)
        with pytest.raises(HTTPException) as exc:
            arc.list_arc_intakes(assoc.id, Response(), assigned.id, db=db, current_user=admin)
        assert exc.value.status_code == 403
        for field in ("approved", "decision", "permit", "fee", "applicant_id", "deadline"):
            with pytest.raises(ValidationError):
                HOAARCIntakeIn(
                    property_id=assigned.id, project_title="Staff",
                    staff_noted_on=date(2026, 9, 20), **{field: "never"},
                )
        assert db.query(GLTransaction).count() == db.query(Charge).count() == 0
    finally:
        db.rollback(); db.close(); engine.dispose()


def test_arc_intake_unlink_and_archive_do_not_restore_old_records():
    from app.models.hoa_arc_intake import HOAARCIntake
    from app.routers import hoa_arc_intake as arc
    from app.schemas.hoa_arc_intake import HOAARCIntakeIn

    db, engine = _db()
    try:
        (admin, owner, manager, tenant, foreign), (assigned, unassigned, other), assoc = _seed(db)
        def payload(p):
            return HOAARCIntakeIn(
                property_id=p, project_title="Project note",
                staff_noted_on=date(2026, 9, 20),
            )
        first = arc.create_arc_intake(assoc.id, payload(assigned.id), db=db, current_user=admin)
        second = arc.create_arc_intake(assoc.id, payload(unassigned.id), db=db, current_user=admin)
        hoa.update_association(assoc.id, HOAAssociationIn(
            name="Recorded HOA", property_ids=[unassigned.id],
        ), db=db, current_user=admin)
        hoa.update_association(assoc.id, HOAAssociationIn(
            name="Recorded HOA", property_ids=[assigned.id, unassigned.id],
        ), db=db, current_user=admin)
        assert arc.list_arc_intakes(assoc.id, Response(), assigned.id, db=db, current_user=admin) == []
        assert db.query(HOAARCIntake).filter_by(id=first.id).one().is_active is False
        hoa.archive_association(assoc.id, db=db, current_user=admin)
        assert db.query(HOAARCIntake).filter_by(id=second.id).one().is_active is False
        with pytest.raises(HTTPException) as exc:
            _model_for_table("hoa_arc_intakes")
        assert exc.value.status_code == 404
        assert db.query(GLTransaction).count() == db.query(Charge).count() == db.query(Lease).count() == 0
    finally:
        db.rollback(); db.close(); engine.dispose()
