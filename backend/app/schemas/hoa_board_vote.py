"""Authenticated, immutable individual association board motion votes."""
from datetime import datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

BoardChoice = Literal["FOR", "AGAINST", "ABSTAIN"]


class HOABoardVoteIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    property_id: int = Field(ge=1)
    motion_sha256: str = Field(min_length=64, max_length=64, pattern="^[0-9a-f]{64}$")
    choice: BoardChoice


class HOABoardVoteOut(BaseModel):
    id: int
    motion_draft_id: int
    board_seat_id: int
    choice: BoardChoice
    motion_sha256: str
    voted_at: datetime
    authenticated_member_vote: Literal[True] = True
    quorum_certified: Literal[False] = False
    resolution_effective: Literal[False] = False


class HOABoardMotionOut(BaseModel):
    id: int
    meeting_draft_id: int
    proposed_motion: str
    motion_sha256: str
    recorded_votes: int
    votes_for: int
    votes_against: int
    votes_abstain: int
    vote_register: list[HOABoardVoteOut]
    my_vote: HOABoardVoteOut | None
    quorum_certified: Literal[False] = False
    resolution_effective: Literal[False] = False
