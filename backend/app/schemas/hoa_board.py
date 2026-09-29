"""Staff proposal of board roles and quorum rules, never legal certification."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

Role = Literal["CHAIR", "VICE_CHAIR", "SECRETARY", "TREASURER", "DIRECTOR", "ALTERNATE"]


class HOABoardSeatIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    property_id: int = Field(ge=1)
    contact_link_id: int = Field(ge=1)
    proposed_role: Role
    staff_voting_eligible: bool = False


class HOABoardAuthorizationIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    property_id: int = Field(ge=1)
    user_id: int = Field(ge=1)
    can_record_offline: bool = False


class HOABoardSeatOut(HOABoardSeatIn):
    id: int
    contact_name: str
    authority_verified: Literal[False] = False
    vote_enabled: Literal[False] = False
    authorized_user_id: int | None = None
    decision_authorized: bool = False
    can_record_offline: bool = False
    status: Literal["STAFF_PROPOSED_UNVERIFIED", "AUTHORIZED_BOARD_LOGIN"] = "STAFF_PROPOSED_UNVERIFIED"


class HOABoardRulesIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    property_id: int = Field(ge=1)
    proposed_quorum_min: int | None = Field(default=None, ge=1, le=500)
    proposed_approval_min: int | None = Field(default=None, ge=1, le=500)


class HOABoardRulesOut(HOABoardRulesIn):
    id: int
    authority_verified: Literal[False] = False
    quorum_certified: Literal[False] = False
    vote_enabled: Literal[False] = False


class HOABoardRosterOut(BaseModel):
    association_id: int
    property_id: int
    seats: list[HOABoardSeatOut]
    rules: HOABoardRulesOut | None
    authority_verified: Literal[False] = False
    vote_enabled: Literal[False] = False
