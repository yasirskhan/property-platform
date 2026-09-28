"""Only link a privately stored property document; do not assert authority."""
from datetime import datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

class HOAEvidenceLinkIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    property_id: int = Field(ge=1)
    attachment_id: int = Field(ge=1)
    evidence_type: Literal[
        "DECLARATION", "BYLAWS", "COVENANTS", "RULES",
        "ARC_GUIDELINES", "RESERVE_STUDY", "MEETING_MINUTES", "OTHER",
    ]

class HOAEvidenceOut(BaseModel):
    id: int
    association_id: int
    property_id: int
    attachment_id: int
    evidence_type: str
    filename: str
    recorded_at: datetime
    status: Literal["STAFF_SUPPLIED_UNVERIFIED"] = "STAFF_SUPPLIED_UNVERIFIED"
