"""An authenticated association board member adopts configured thresholds.

The record is an operative association configuration decision, not a legal
opinion or a motion outcome. No arbitrary quorum default or finance posting.
"""
from __future__ import annotations
from hashlib import sha256
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.hoa_board import HOABoardRuleDraft
from app.models.hoa_board_rule_adoption import HOABoardRuleAdoption
from app.models.user import User
from app.routers.auth import get_current_user
from app.routers.hoa_arc_board_decisions import _board_scope
from app.schemas.hoa_board_rule_adoption import (
    HOABoardRuleAdoptIn, HOABoardRuleAdoptionOut, HOABoardRuleRegisterOut,
)
from app.services.audit import append_audit_log

router = APIRouter(prefix="/api/hoa/associations", tags=["HOA adopted board thresholds"])


def _proposal(db: Session, org: int, assoc: int, prop: int, *, lock=False):
    query = db.query(HOABoardRuleDraft).filter(
        HOABoardRuleDraft.organization_id == org,
        HOABoardRuleDraft.association_id == assoc,
        HOABoardRuleDraft.property_id == prop,
        HOABoardRuleDraft.is_active.is_(True),
    )
    return (query.with_for_update() if lock else query).first()


def _digest(row: HOABoardRuleDraft | None) -> str | None:
    if row is None or row.proposed_quorum_min is None or row.proposed_approval_min is None:
        return None
    # Includes the source revision to prevent stale adoption after amendment.
    source = f"{row.id}:{row.proposed_quorum_min}:{row.proposed_approval_min}:{row.updated_at.isoformat()}"
    return sha256(source.encode("utf-8")).hexdigest()


def _out(row):
    return HOABoardRuleAdoptionOut(
        id=row.id, board_seat_id=row.board_seat_id,
        quorum_min=row.quorum_min, approval_min=row.approval_min,
        proposal_sha256=row.proposal_sha256, adopted_at=row.adopted_at,
    )


@router.get("/{association_id}/board-rule-adoptions",
            response_model=HOABoardRuleRegisterOut)
def get_board_rule_adoptions(
    association_id: int, response: Response,
    property_id: int = Query(ge=1),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org, assoc, seat = _board_scope(
        db, actor=current_user, association_id=association_id, property_id=property_id,
    )
    proposal = _proposal(db, org, assoc.id, property_id)
    digest = _digest(proposal)
    history = db.query(HOABoardRuleAdoption).filter(
        HOABoardRuleAdoption.organization_id == org,
        HOABoardRuleAdoption.association_id == assoc.id,
        HOABoardRuleAdoption.property_id == property_id,
    ).order_by(HOABoardRuleAdoption.id).limit(101).all()
    if len(history) > 100:
        raise HTTPException(status_code=422, detail="Board rule adoption history limit exceeded.")
    active = next((r for r in reversed(history)
                   if digest is not None and r.proposal_sha256 == digest), None)
    response.headers["Cache-Control"] = "no-store"
    return HOABoardRuleRegisterOut(
        property_id=property_id,
        proposed_quorum_min=proposal.proposed_quorum_min if proposal else None,
        proposed_approval_min=proposal.proposed_approval_min if proposal else None,
        proposal_sha256=digest,
        active_adoption_id=active.id if active else None,
        history=[_out(r) for r in history],
    )


@router.post("/{association_id}/board-rule-adoptions",
             response_model=HOABoardRuleAdoptionOut, status_code=201)
def adopt_board_rules(
    association_id: int, payload: HOABoardRuleAdoptIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org, assoc, seat = _board_scope(
        db, actor=current_user, association_id=association_id,
        property_id=payload.property_id,
    )
    proposal = _proposal(db, org, assoc.id, payload.property_id, lock=True)
    digest = _digest(proposal)
    if digest is None:
        raise HTTPException(status_code=409, detail="Explicit quorum and approval thresholds must first be configured.")
    if digest != payload.expected_proposal_sha256:
        raise HTTPException(status_code=409, detail="Configured rule revision changed. Review the current thresholds.")
    prior = db.query(HOABoardRuleAdoption).filter(
        HOABoardRuleAdoption.rule_draft_id == proposal.id,
        HOABoardRuleAdoption.proposal_sha256 == digest,
    ).first()
    if prior is not None:
        return _out(prior)
    row = HOABoardRuleAdoption(
        organization_id=org, association_id=assoc.id,
        property_id=payload.property_id, rule_draft_id=proposal.id,
        proposal_sha256=digest,
        quorum_min=proposal.proposed_quorum_min,
        approval_min=proposal.proposed_approval_min,
        board_seat_id=seat.id, adopted_by_user_id=current_user.id,
    )
    db.add(row)
    try:
        db.flush()
        append_audit_log(
            db, organization_id=org, user_id=current_user.id,
            entity_type="hoa_board_rule_adoption", entity_id=row.id,
            action="association_board_thresholds_adopted",
            new_value={
                "association_id": assoc.id, "property_id": payload.property_id,
                "board_seat_id": seat.id,
                "proposal_sha256": digest,
                "quorum_min": row.quorum_min, "approval_min": row.approval_min,
            },
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Concurrent board threshold adoption.") from exc
    db.refresh(row)
    return _out(row)
