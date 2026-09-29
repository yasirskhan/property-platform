"""Version-bound association decision on quorum and approval thresholds."""
from datetime import datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class HOABoardRuleAdoptIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    property_id: int = Field(ge=1)
    expected_proposal_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class HOABoardRuleAdoptionOut(BaseModel):
    id: int
    board_seat_id: int
    quorum_min: int
    approval_min: int
    proposal_sha256: str
    adopted_at: datetime
    status: Literal["BOARD_MEMBER_ADOPTED"] = "BOARD_MEMBER_ADOPTED"
    platform_legal_certification: Literal[False] = False


class HOABoardRuleRegisterOut(BaseModel):
    property_id: int
    proposed_quorum_min: int | None
    proposed_approval_min: int | None
    proposal_sha256: str | None
    active_adoption_id: int | None
    history: list[HOABoardRuleAdoptionOut]
    legal_quorum_certified: Literal[False] = False
