# ============================================================
# sidebar_preference.py (schemas)
# ------------------------------------------------------------
# Pydantic models for the sidebar layout API.
# ============================================================

from datetime import datetime
from typing import List
from pydantic import BaseModel, Field


class SidebarPreferenceIn(BaseModel):
    """Payload sent from the frontend when saving the layout."""
    order: List[str] = Field(default_factory=list)
    hidden: List[str] = Field(default_factory=list)


class SidebarPreferenceOut(BaseModel):
    """Response when the frontend reads the saved layout."""
    order: List[str]
    hidden: List[str]
    updated_at: datetime | None = None

    class Config:
        from_attributes = True