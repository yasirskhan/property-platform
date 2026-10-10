"""Only staff observations of a proposed ballot. No certified vote or tally."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

BallotChoice = Literal["FOR", "AGAINST", "ABSTAIN"]


class HOABallotIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    property_id: int = Field(ge=1)
    board_seat_id: int = Field(ge=1)
    staff_reported_choice: BallotChoice


class HOABallotOut(BaseModel):
    id: int
    motion_draft_id: int
    board_seat_id: int
    contact_name: str
    staff_reported_choice: BallotChoice
    status: Literal["STAFF_REPORTED_UNVERIFIED"] = "STAFF_REPORTED_UNVERIFIED"
    vote_effective: Literal[False] = False
    board_authority_verified: Literal[False] = False
    quorum_certified: Literal[False] = False


class HOABallotListOut(BaseModel):
    meeting_draft_id: int
    motion_draft_id: int
    ballots: list[HOABallotOut]
    vote_effective: Literal[False] = False
    quorum_certified: Literal[False] = False
    approval_certified: Literal[False] = False
