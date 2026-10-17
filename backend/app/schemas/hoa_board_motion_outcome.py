"""Exact-tally board motion outcome, recorded by an authorized association member."""
from datetime import datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

class HOAMotionOutcomeIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    property_id: int = Field(ge=1)
    motion_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    rule_adoption_id: int = Field(ge=1)
    expected_vote_register_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

class HOAMotionOutcomeOut(BaseModel):
    id: int
    motion_draft_id: int
    motion_sha256: str
    rule_adoption_id: int
    vote_register_sha256: str
    quorum_min: int
    approval_min: int
    votes_for: int
    votes_against: int
    votes_abstain: int
    outcome: Literal["PASSED", "NOT_PASSED"]
    recorded_by_seat_id: int
    recorded_at: datetime
    statutory_compliance_certified: Literal[False] = False

class HOAMotionOutcomePreviewOut(BaseModel):
    motion_draft_id: int
    motion_sha256: str
    rule_adoption_id: int | None
    vote_register_sha256: str
    quorum_min: int | None
    approval_min: int | None
    votes_for: int
    votes_against: int
    votes_abstain: int
    quorum_met: bool
    predicted_outcome: Literal["PASSED", "NOT_PASSED"] | None
    recorded: HOAMotionOutcomeOut | None
    statutory_compliance_certified: Literal[False] = False
