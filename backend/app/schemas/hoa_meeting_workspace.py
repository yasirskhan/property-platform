"""Unverified staff meeting workspace. Neither attendance nor a motion is an official board action."""
from __future__ import annotations
from datetime import datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator

StaffAttendance = Literal["PRESENT", "ABSENT", "UNCONFIRMED"]


class HOAMeetingAttendanceIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    property_id: int = Field(ge=1)
    contact_link_id: int = Field(ge=1)
    staff_attendance: StaffAttendance


class HOAMotionDraftIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    property_id: int = Field(ge=1)
    proposed_motion: str = Field(min_length=1, max_length=1000)

    @field_validator("proposed_motion")
    @classmethod
    def clean_motion(cls, value: str) -> str:
        cleaned = " ".join(value.split())
        if not cleaned:
            raise ValueError("A proposed motion is required.")
        return cleaned


class HOAMeetingAttendanceOut(BaseModel):
    id: int
    contact_link_id: int
    contact_name: str
    staff_attendance: StaffAttendance
    status: Literal["STAFF_REPORTED_UNVERIFIED"] = "STAFF_REPORTED_UNVERIFIED"


class HOAMotionDraftOut(BaseModel):
    id: int
    proposed_motion: str
    updated_at: datetime
    status: Literal["PROPOSED_ONLY"] = "PROPOSED_ONLY"
    vote_enabled: Literal[False] = False


class HOAMeetingWorkspaceOut(BaseModel):
    meeting_draft_id: int
    association_id: int
    property_id: int
    attendance: list[HOAMeetingAttendanceOut]
    motions: list[HOAMotionDraftOut]
    board_authority_verified: Literal[False] = False
    quorum_certified: Literal[False] = False
    vote_enabled: Literal[False] = False
