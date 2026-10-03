"""HOA reserve mappings are read-only book references, not reserve transfers."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi import HTTPException, Response
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import init_db  # noqa: F401
from app.core.database import Base
from app.models.audit_log import AuditLog
from app.models.bank_account import BankAccount
from app.models.charge import Charge
from app.models.gl_account import GLAccount
from app.models.gl_entry import GLEntry
from app.models.gl_transaction import GLTransaction
from app.models.hoa_reserve_account import HOAReserveAccount
from app.models.hoa_reserve_movement_draft import HOAReserveMovementDraft
from app.routers import hoa_reserve_movements as movement_api
from app.schemas.hoa_reserve_movement import HOAReserveMovementIn
from app.models.lease import Lease, RentInvoice
from app.models.property import Property, PropertyAssignment
from app.models.user import Organization, User, UserRole
from app.routers import hoa_associations as hoa
from app.routers import hoa_reserve_accounts as api
from app.schemas.hoa_association import HOAAssociationIn
from app.schemas.hoa_reserve_account import HOAReserveIn
from app.models.contact import Contact
from app.models.hoa_association import HOAContactLink
from app.models.hoa_reserve_movement_decision import HOAReserveMovementDecision
from app.routers import hoa_board as board_api
from app.routers import hoa_arc_board_decisions as arc_board
from app.routers import hoa_reserve_execution as execution
from app.schemas.hoa_association import HOAContactLinkIn
from app.schemas.hoa_board import HOABoardSeatIn, HOABoardAuthorizationIn
from app.schemas.hoa_reserve_execution import HOAReserveDecisionIn, HOAReservePostIn, HOAReserveReverseIn
from app.services.entity_notes import _model_for_table


@pytest.fixture(autouse=True)
def grants(monkeypatch):
    monkeypatch.setattr(hoa, "permission_allows_user", lambda *a, **kw: True)
    monkeypatch.setattr(hoa, "resolve_customer_features", lambda *a, **kw: [
        SimpleNamespace(key=hoa.FEATURE_KEY, allowed=True),
        SimpleNamespace(key=hoa.HOA_FEATURE_KEY, allowed=True)
    ])
    monkeypatch.setattr(api, "permission_allows_user", lambda *a, **kw: True)
    monkeypatch.setattr(arc_board, "resolve_customer_features", lambda *a, **kw: [
        SimpleNamespace(key=key, release_allowed=True,
                        entitlement_allowed=True, org_config_allowed=True)
        for key in arc_board.HOA_GATES
    ])


def _db():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, expire_on_commit=False)(), engine


def _seed(db):
    org = Organization(name="HOA Reserve A", slug="hoa-reserve-a")
    other = Organization(name="HOA Reserve B", slug="hoa-reserve-b")
    db.add_all([org, other]); db.flush()
    users = []
    for o, role, label in (
        (org, UserRole.ADMIN, "admin"), (org, UserRole.OWNER, "owner"),
        (org, UserRole.MANAGER, "manager"), (org, UserRole.TENANT, "tenant"),
        (other, UserRole.ADMIN, "foreign"),
    ):
        user = User(
            organization_id=o.id, role=role, first_name=label,
            last_name="Reserve", email=f"hoa-reserve-{label}@example.test",
            hashed_password="x", is_active=True,
        )
        db.add(user); users.append(user)
    db.flush()
    props = []
    for scope, label in (
        (org, "Assigned"), (org, "Other property"), (other, "Foreign"),
    ):
        prop = Property(
            organization_id=scope.id, name=label, address_line1="1 Main",
            city="Cleveland", state="OH", zip_code="44113", is_active=True,
        )
        db.add(prop); props.append(prop)
    db.flush()
    db.add(PropertyAssignment(
        property_id=props[0].id, user_id=users[2].id,
        role=UserRole.MANAGER, is_active=True,
    ))
    cash = GLAccount(
        organization_id=org.id, gl_number="1188",
        name="Recorded reserve cash GL", account_type="ASSET",
        include_on_cash_flow=True, is_active=True,
    )
    offset = GLAccount(
        organization_id=org.id, gl_number="3900",
        name="Offset for test", account_type="EQUITY", is_active=True,
    )
    another = GLAccount(
        organization_id=org.id, gl_number="1199",
        name="Other reserve cash GL", account_type="ASSET",
        include_on_cash_flow=True, is_active=True,
    )
    foreign_gl = GLAccount(
        organization_id=other.id, gl_number="1188",
        name="Other org cash", account_type="ASSET",
        include_on_cash_flow=True, is_active=True,
    )
    db.add_all([cash, offset, another, foreign_gl]); db.flush()
    bank = BankAccount(
        organization_id=org.id, name="Staff reserve bank",
        gl_account_id=cash.id, account_type="ESCROW",
        bank_name="Sensitive bank provider", routing_number="123456789",
        account_number="12345678901234", is_active=True,
    )
    wrong = BankAccount(
        organization_id=org.id, name="Different cash bank",
        gl_account_id=another.id, account_type="OPERATING",
        routing_number="00001111", account_number="SECRETACCOUNT",
        is_active=True,
    )
    db.add_all([bank, wrong])
    db.commit()
    assoc = hoa.create_association(
        HOAAssociationIn(name="Recorded HOA", property_ids=[props[0].id, props[1].id]),
        db=db, current_user=users[0],
    )
    return users, props, assoc, cash, offset, another, foreign_gl, bank, wrong


def _post_fixture(db, *, org_id, cash, offset, prop_id, debit, credit, d=date(2026, 9, 1), reversal=False):
    """Create representative already-posted balanced GL for READ tests only."""
    tr = GLTransaction(
        organization_id=org_id, transaction_date=d,
        transaction_type="REVERSAL" if reversal else "JOURNAL_ENTRY",
        is_reversed=False,
    )
    db.add(tr); db.flush()
    amount = Decimal(str(debit or credit))
    db.add_all([
        GLEntry(
            organization_id=org_id, transaction_id=tr.id,
            gl_account_id=cash.id, property_id=prop_id,
            debit=Decimal(str(debit)), credit=Decimal(str(credit)),
        ),
        GLEntry(
            organization_id=org_id, transaction_id=tr.id,
            gl_account_id=offset.id, property_id=prop_id,
            debit=Decimal(str(credit)), credit=Decimal(str(debit)),
        ),
    ])
    db.commit()


def _payload(prop, cash, bank=None):
    return HOAReserveIn(
        property_id=prop.id, gl_account_id=cash.id,
        bank_account_id=bank.id if bank is not None else None,
    )


def _finances(db):
    return (
        db.query(Charge).count(), db.query(Lease).count(),
        db.query(RentInvoice).count(), db.query(GLTransaction).count(),
        db.query(GLEntry).count(),
    )


def test_reserve_mapping_and_actual_book_balances_are_not_legal_reserves():
    db, engine = _db()
    try:
        (admin, owner, manager, tenant, foreign), (assigned, other_prop, outside), assoc, cash, offset, another, foreign_gl, bank, wrong = _seed(db)
        _post_fixture(db, org_id=admin.organization_id, cash=cash, offset=offset,
                      prop_id=assigned.id, debit="1000.00", credit="0.00")
        _post_fixture(db, org_id=admin.organization_id, cash=cash, offset=offset,
                      prop_id=None, debit="75.00", credit="0.00")
        _post_fixture(db, org_id=admin.organization_id, cash=cash, offset=offset,
                      prop_id=other_prop.id, debit="40.00", credit="0.00")
        _post_fixture(db, org_id=admin.organization_id, cash=cash, offset=offset,
                      prop_id=assigned.id, debit="0.00", credit="20.00",
                      d=date(2026, 9, 2), reversal=True)
        before = _finances(db)
        settings = api.put_reserve(
            assoc.id, _payload(assigned, cash, bank),
            db=db, current_user=admin,
        )
        assert settings.status == "STAFF_MAPPED_UNVERIFIED"
        assert settings.posting_enabled is False
        assert settings.gl_number == "1188"
        assert settings.bank_display_name == bank.name
        assert bank.routing_number not in str(settings.model_dump())
        assert bank.account_number not in str(settings.model_dump())
        read = api.get_reserve(
            assoc.id, Response(), assigned.id, db=db, current_user=manager,
        )
        assert read.id == settings.id
        options = api.reserve_options(
            assoc.id, Response(), assigned.id, db=db, current_user=owner,
        )
        assert [v.gl_account_id for v in options] == [cash.id]
        assert bank.account_number not in str([x.model_dump() for x in options])
        response = Response()
        result = api.reserve_book(
            assoc.id, response, assigned.id, date(2026, 9, 2),
            db=db, current_user=owner,
        )
        assert response.headers["cache-control"] == "no-store"
        assert result.account_wide_book_balance == Decimal("1095.00")
        assert result.property_tagged_book_balance == Decimal("980.00")
        assert result.unallocated_or_other_property_balance == Decimal("115.00")
        assert result.attribution_status == "OTHER_OR_UNTAGGED_POSTINGS_PRESENT"
        assert result.bank_statement_reconciled is False
        assert result.legal_reserve_ownership_verified is False
        early = api.reserve_book(
            assoc.id, Response(), assigned.id, date(2026, 8, 31),
            db=db, current_user=admin,
        )
        assert early.account_wide_book_balance == Decimal("0")
        with pytest.raises(HTTPException) as denied:
            api.reserve_book(
                assoc.id, Response(), assigned.id, date(2026, 9, 2),
                db=db, current_user=manager,
            )
        assert denied.value.status_code == 403
        assert _finances(db) == before
        assert "123456789" not in str(result.model_dump())
        assert "SECRETACCOUNT" not in str(result.model_dump())
        assert db.query(AuditLog).filter(AuditLog.entity_type=="hoa_reserve_account").count() == 1
    finally:
        db.close(); engine.dispose()


def test_reserve_mismatch_scope_duplicate_and_actor_revocation(monkeypatch):
    db, engine = _db()
    try:
        (admin, owner, manager, tenant, foreign), (assigned, other_prop, outside), assoc, cash, offset, another, foreign_gl, bank, wrong = _seed(db)
        for prop, gl, b in (
            (outside, cash, bank), (assigned, foreign_gl, None),
            (assigned, offset, None), (assigned, cash, wrong),
        ):
            with pytest.raises(HTTPException):
                api.put_reserve(assoc.id, _payload(prop, gl, b),
                                db=db, current_user=admin)
        for actor in (manager, tenant, foreign):
            with pytest.raises(HTTPException):
                api.put_reserve(assoc.id, _payload(assigned, cash, bank),
                                db=db, current_user=actor)
        first = api.put_reserve(
            assoc.id, _payload(assigned, cash, bank), db=db, current_user=admin,
        )
        with pytest.raises(HTTPException) as e:
            api.put_reserve(assoc.id, _payload(other_prop, cash),
                            db=db, current_user=owner)
        assert e.value.status_code == 409
        with pytest.raises(HTTPException) as e:
            api.put_reserve(assoc.id, _payload(assigned, another),
                            db=db, current_user=owner)
        assert e.value.status_code == 409
        for actor, prop in ((manager, other_prop), (foreign, assigned)):
            with pytest.raises(HTTPException):
                api.get_reserve(assoc.id, Response(), prop.id,
                                db=db, current_user=actor)
        monkeypatch.setattr(api, "permission_allows_user",
                            lambda db, *, user, menu_key: menu_key != "ACCOUNTING.GL_ACCOUNTS")
        with pytest.raises(HTTPException) as e:
            api.get_reserve(assoc.id, Response(), assigned.id,
                            db=db, current_user=admin)
        assert e.value.status_code == 403
        monkeypatch.setattr(api, "permission_allows_user", lambda *a, **k: True)
        monkeypatch.setattr(hoa, "resolve_customer_features", lambda *a, **k: [])
        with pytest.raises(HTTPException) as e:
            api.get_reserve(assoc.id, Response(), assigned.id,
                            db=db, current_user=admin)
        assert e.value.status_code == 404
        assert db.get(HOAReserveAccount, first.id).is_active
        assert db.query(Charge).count() == db.query(GLTransaction).count() == 0
        with pytest.raises(HTTPException) as e:
            _model_for_table("hoa_reserve_accounts")
        assert e.value.status_code == 404
    finally:
        db.rollback(); db.close(); engine.dispose()


def test_reserve_unlink_archives_mapping_and_relink_requires_revalidation():
    db, engine = _db()
    try:
        (admin, owner, manager, tenant, foreign), (assigned, other_prop, outside), assoc, cash, offset, another, foreign_gl, bank, wrong = _seed(db)
        saved = api.put_reserve(
            assoc.id, _payload(assigned, cash, bank), db=db, current_user=admin,
        )
        hoa.update_association(
            assoc.id, HOAAssociationIn(
                name="Recorded HOA", property_ids=[other_prop.id],
            ), db=db, current_user=owner,
        )
        assert db.get(HOAReserveAccount, saved.id).is_active is False
        hoa.update_association(
            assoc.id, HOAAssociationIn(
                name="Recorded HOA", property_ids=[assigned.id, other_prop.id],
            ), db=db, current_user=owner,
        )
        assert api.get_reserve(
            assoc.id, Response(), assigned.id, db=db, current_user=admin,
        ) is None
        restored = api.put_reserve(
            assoc.id, _payload(assigned, cash, bank), db=db, current_user=owner,
        )
        assert restored.id == saved.id and restored.posting_enabled is False
        bank.is_active = False
        db.flush()
        old = api.get_reserve(
            assoc.id, Response(), assigned.id, db=db, current_user=owner,
        )
        assert old.mapping_status == "ARCHIVED_MAPPING_NEEDS_REVIEW"
        with pytest.raises(HTTPException):
            api.put_reserve(
                assoc.id, _payload(assigned, cash, bank),
                db=db, current_user=admin,
            )
        assert db.query(Charge).count() == db.query(GLTransaction).count() == 0
    finally:
        db.rollback(); db.close(); engine.dispose()


def _movement(prop, gl_id, key="reserve-test-request-001", **kw):
    args = dict(
        property_id=prop.id, counterparty_gl_account_id=gl_id,
        direction="TO_RESERVE", planned_on=date(2026, 11, 1),
        amount=Decimal("105.25"), memo="Synthetic reserve planning only",
        idempotency_key=key,
    )
    args.update(kw)
    return HOAReserveMovementIn(**args)


def test_reserve_movement_plans_use_dedicated_mapping_with_no_funds_moved():
    db, engine = _db()
    try:
        (admin, owner, manager, tenant, foreign), (assigned, _, _), assoc, cash, _, other_gl, _, bank, wrong = _seed(db)
        mapped = api.put_reserve(assoc.id, _payload(assigned, cash, bank),
                                 db=db, current_user=admin)
        before = _finances(db)
        row = movement_api.create_movement_draft(
            assoc.id, _movement(assigned, other_gl.id), db=db, current_user=admin,
        )
        candidates_response = Response()
        candidates = movement_api.reserve_counterpart_options(
            assoc.id, candidates_response, property_id=assigned.id,
            db=db, current_user=owner,
        )
        assert candidates_response.headers["cache-control"] == "no-store"
        assert [candidate.gl_account_id for candidate in candidates] == [other_gl.id]
        assert "123456789" not in str([candidate.model_dump() for candidate in candidates])
        with pytest.raises(HTTPException):
            movement_api.reserve_counterpart_options(
                assoc.id, Response(), property_id=assigned.id,
                db=db, current_user=manager,
            )
        assert row.reserve_gl_account_id == mapped.gl_account_id
        assert row.posting_enabled is False and row.funds_moved is False
        assert row.legally_restricted_funds_verified is False
        assert row.amount == Decimal("105.25")
        assert row.status == "DRAFT"
        again = movement_api.create_movement_draft(
            assoc.id, _movement(assigned, other_gl.id), db=db, current_user=owner,
        )
        assert again.id == row.id
        assert db.query(HOAReserveMovementDraft).count() == 1
        response = Response()
        history = movement_api.list_movement_drafts(
            assoc.id, response, assigned.id, db=db, current_user=admin,
        )
        assert response.headers["cache-control"] == "no-store"
        assert len(history) == 1
        with pytest.raises(HTTPException) as error:
            movement_api.create_movement_draft(
                assoc.id, _movement(assigned, other_gl.id, amount=Decimal("111.00")),
                db=db, current_user=admin,
            )
        assert error.value.status_code == 409
        cancelled = movement_api.cancel_movement_draft(
            assoc.id, row.id, property_id=assigned.id,
            db=db, current_user=owner,
        )
        assert cancelled.status == "CANCELLED" and cancelled.cancelled_at is not None
        with pytest.raises(HTTPException) as error:
            movement_api.cancel_movement_draft(
                assoc.id, row.id, property_id=assigned.id,
                db=db, current_user=owner,
            )
        assert error.value.status_code == 409
        assert movement_api.create_movement_draft(
            assoc.id, _movement(assigned, other_gl.id),
            db=db, current_user=admin,
        ).status == "CANCELLED"  # idempotent replay cannot resurrect
        assert _finances(db) == before
        assert db.query(AuditLog).filter(AuditLog.entity_type == "hoa_reserve_movement_draft").count() == 2
        with pytest.raises(HTTPException):
            _model_for_table("hoa_reserve_movement_drafts")
    finally:
        db.close()
        engine.dispose()


def test_reserve_movement_plans_deny_cross_scope_and_stale_mappings(monkeypatch):
    db, engine = _db()
    try:
        (admin, owner, manager, tenant, foreign), (assigned, second, outside), assoc, cash, offset, other_gl, foreign_gl, bank, wrong = _seed(db)
        with pytest.raises(HTTPException):
            movement_api.create_movement_draft(
                assoc.id, _movement(assigned, other_gl.id),
                db=db, current_user=admin,
            )
        api.put_reserve(assoc.id, _payload(assigned, cash, bank),
                        db=db, current_user=admin)
        for actor in (manager, tenant, foreign):
            with pytest.raises(HTTPException):
                movement_api.create_movement_draft(
                    assoc.id, _movement(assigned, other_gl.id),
                    db=db, current_user=actor,
                )
        for candidate in (
            _movement(assigned, foreign_gl.id, key="reserve-test-request-foreign"),
            _movement(assigned, cash.id, key="reserve-test-request-self"),
            _movement(assigned, offset.id, key="reserve-test-request-equity"),
        ):
            with pytest.raises(HTTPException):
                movement_api.create_movement_draft(
                    assoc.id, candidate, db=db, current_user=owner,
                )
        with pytest.raises(HTTPException):
            movement_api.create_movement_draft(
                assoc.id, _movement(outside, other_gl.id),
                db=db, current_user=admin,
            )
        with pytest.raises(ValidationError):
            _movement(assigned, other_gl.id, gl_transaction_id=10)
        with pytest.raises(ValidationError):
            _movement(assigned, other_gl.id, amount=Decimal("0"))
        saved = movement_api.create_movement_draft(
            assoc.id, _movement(assigned, other_gl.id),
            db=db, current_user=admin,
        )
        monkeypatch.setattr(api, "permission_allows_user", lambda *a, **kw: False)
        with pytest.raises(HTTPException):
            movement_api.list_movement_drafts(
                assoc.id, Response(), assigned.id, db=db, current_user=admin,
            )
        monkeypatch.setattr(api, "permission_allows_user", lambda *a, **kw: True)
        bank.is_active = False
        db.flush()
        with pytest.raises(HTTPException):
            movement_api.list_movement_drafts(
                assoc.id, Response(), assigned.id, db=db, current_user=admin,
            )
        bank.is_active = True
        db.flush()
        hoa.update_association(
            assoc.id, HOAAssociationIn(
                name="Recorded HOA", property_ids=[second.id],
            ), db=db, current_user=admin,
        )
        assert db.get(HOAReserveMovementDraft, saved.id).status == "CANCELLED"
        hoa.update_association(
            assoc.id, HOAAssociationIn(
                name="Recorded HOA", property_ids=[assigned.id, second.id],
            ), db=db, current_user=admin,
        )
        api.put_reserve(assoc.id, _payload(assigned, cash, bank),
                        db=db, current_user=admin)
        history = movement_api.list_movement_drafts(
            assoc.id, Response(), assigned.id, db=db, current_user=admin,
        )
        assert len(history) == 1 and history[0].status == "CANCELLED"
        assert _finances(db) == (0, 0, 0, 0, 0)
    finally:
        db.rollback()
        db.close()
        engine.dispose()


def _authorize_reserve_board(db, *, admin, assoc, prop):
    admin.is_verified = True
    db.flush()
    contact = Contact(
        organization_id=admin.organization_id,
        display_name="Reserve board member", email=admin.email,
        contact_type="PERSON", is_active=True,
    )
    db.add(contact); db.flush()
    link = hoa.add_contact_link(
        assoc.id, HOAContactLinkIn(
            property_id=prop.id, contact_id=contact.id,
        ), db=db, current_user=admin,
    )
    seat = board_api.record_board_seat(
        assoc.id, HOABoardSeatIn(
            property_id=prop.id, contact_link_id=link.id,
            proposed_role="CHAIR", staff_voting_eligible=True,
        ), db=db, current_user=admin,
    )
    board_api.authorize_board_seat(
        assoc.id, seat.id, HOABoardAuthorizationIn(
            property_id=prop.id, user_id=admin.id, can_record_offline=True,
        ), db=db, current_user=admin,
    )
    return seat


def test_board_approved_reserve_book_posts_reverses_without_bank_transfer():
    db, engine = _db()
    try:
        (admin, owner, manager, tenant, foreign), (prop, _, _), assoc, cash, _, other_gl, _, bank, _ = _seed(db)
        api.put_reserve(assoc.id, _payload(prop, cash, bank), db=db, current_user=admin)
        seat = _authorize_reserve_board(db, admin=admin, assoc=assoc, prop=prop)
        draft = movement_api.create_movement_draft(
            assoc.id, _movement(prop, other_gl.id, planned_on=date.today()),
            db=db, current_user=admin,
        )
        before = _finances(db)
        with pytest.raises(HTTPException):
            execution.record_reserve_decision(
                assoc.id, draft.id, HOAReserveDecisionIn(
                    property_id=prop.id, decision="APPROVED", decision_note="Approved",
                ), db=db, current_user=manager,
            )
        approved = execution.record_reserve_decision(
            assoc.id, draft.id, HOAReserveDecisionIn(
                property_id=prop.id, decision="APPROVED",
                decision_note="Board approved the reserve book movement",
            ), db=db, current_user=admin,
        )
        assert approved.status == "APPROVED" and approved.board_seat_id == seat.id
        assert approved.amount == Decimal("105.25") and approved.bank_transfer_executed is False
        assert _finances(db) == before
        with pytest.raises(HTTPException) as duplicate:
            execution.record_reserve_decision(
                assoc.id, draft.id, HOAReserveDecisionIn(
                    property_id=prop.id, decision="APPROVED", decision_note="Duplicate",
                ), db=db, current_user=admin,
            )
        assert duplicate.value.status_code == 409
        with pytest.raises(HTTPException) as cannot_cancel:
            movement_api.cancel_movement_draft(
                assoc.id, draft.id, property_id=prop.id, db=db, current_user=owner,
            )
        assert cannot_cancel.value.status_code == 409
        posted = execution.post_reserve_book_movement(
            assoc.id, draft.id, HOAReservePostIn(
                property_id=prop.id, transaction_on=date.today(),
            ), db=db, current_user=owner,
        )
        assert posted.status == "POSTED" and posted.gl_transaction_id is not None
        assert posted.bank_transfer_executed is False
        assert execution.post_reserve_book_movement(
            assoc.id, draft.id, HOAReservePostIn(
                property_id=prop.id, transaction_on=date.today(),
            ), db=db, current_user=owner,
        ).gl_transaction_id == posted.gl_transaction_id
        tx = db.get(GLTransaction, posted.gl_transaction_id)
        assert tx.transaction_type == "TRANSFER"
        assert tx.source_type == "hoa_reserve_book_movement"
        lines = db.query(GLEntry).filter(GLEntry.transaction_id == tx.id).all()
        assert len(lines) == 2
        assert {x.gl_account_id for x in lines} == {cash.id, other_gl.id}
        assert sum((x.debit for x in lines), Decimal("0")) == Decimal("105.25")
        assert sum((x.credit for x in lines), Decimal("0")) == Decimal("105.25")
        assert any(x.gl_account_id == cash.id and x.debit == Decimal("105.25") for x in lines)
        reversed_book = execution.reverse_reserve_book_movement(
            assoc.id, draft.id, HOAReserveReverseIn(
                property_id=prop.id, reversal_on=date.today(),
                reason="Corrected approved reserve instruction",
            ), db=db, current_user=owner,
        )
        assert reversed_book.status == "REVERSED"
        assert reversed_book.reversal_transaction_id != posted.gl_transaction_id
        assert db.get(GLTransaction, tx.id).is_reversed
        assert db.query(GLTransaction).count() == before[3] + 2
        assert db.query(GLEntry).count() == before[4] + 4
        assert db.query(Charge).count() == db.query(Lease).count() == db.query(RentInvoice).count() == 0
        with pytest.raises(HTTPException):
            execution.reverse_reserve_book_movement(
                assoc.id, draft.id, HOAReserveReverseIn(
                    property_id=prop.id, reversal_on=date.today(),
                    reason="Repeat reversal",
                ), db=db, current_user=owner,
            )
        assert db.query(AuditLog).filter(
            AuditLog.entity_type == "hoa_reserve_movement_decision",
        ).count() == 3
        assert db.query(HOAReserveMovementDecision).count() == 1
        with pytest.raises(HTTPException):
            _model_for_table("hoa_reserve_movement_decisions")
    finally:
        db.rollback(); db.close(); engine.dispose()


def test_reserve_posting_scope_and_denied_board_decision_fail_closed(monkeypatch):
    db, engine = _db()
    try:
        (admin, owner, manager, tenant, foreign), (prop, other, outside), assoc, cash, _, other_gl, foreign_gl, bank, _ = _seed(db)
        api.put_reserve(assoc.id, _payload(prop, cash, bank), db=db, current_user=admin)
        _authorize_reserve_board(db, admin=admin, assoc=assoc, prop=prop)
        draft = movement_api.create_movement_draft(
            assoc.id, _movement(prop, other_gl.id, planned_on=date.today()),
            db=db, current_user=admin,
        )
        with pytest.raises(HTTPException):
            execution.record_reserve_decision(
                assoc.id, draft.id, HOAReserveDecisionIn(
                    property_id=other.id, decision="APPROVED", decision_note="Wrong property",
                ), db=db, current_user=admin,
            )
        with pytest.raises(HTTPException):
            execution.record_reserve_decision(
                assoc.id, draft.id, HOAReserveDecisionIn(
                    property_id=prop.id, decision="APPROVED", decision_note="Foreign board",
                ), db=db, current_user=foreign,
            )
        denied = execution.record_reserve_decision(
            assoc.id, draft.id, HOAReserveDecisionIn(
                property_id=prop.id, decision="DENIED", decision_note="Board denied",
            ), db=db, current_user=admin,
        )
        assert denied.status == "DENIED"
        with pytest.raises(HTTPException) as denied_post:
            execution.post_reserve_book_movement(
                assoc.id, draft.id, HOAReservePostIn(
                    property_id=prop.id, transaction_on=date.today(),
                ), db=db, current_user=owner,
            )
        assert denied_post.value.status_code == 409
        assert db.query(GLTransaction).count() == 0
        assert db.query(Charge).count() == 0
    finally:
        db.rollback(); db.close(); engine.dispose()
