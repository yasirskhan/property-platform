# ============================================================
# menu_permission.py (schemas)
# ------------------------------------------------------------
# Pydantic models for the menu permissions API.
#
# Every response is a full picture of what the frontend should
# render — the frontend does NOT re-implement the 4-layer
# resolution logic. If a menu item is hidden, it is simply not
# present in the `items` list.
# ============================================================

from datetime import datetime
from typing import List, Dict, Optional
from pydantic import BaseModel, Field


# ------------------------------------------------------------
# /api/menu/me  — the resolved sidebar for the current user
# ------------------------------------------------------------

class ResolvedMenuItem(BaseModel):
    """One menu item, already resolved through all 4 layers."""
    key: str                # e.g. "ACCOUNTING.RECEIVABLES"
    parent: Optional[str]   # e.g. "ACCOUNTING"  (None for top-level)
    visible: bool = True    # always True in this payload (hidden items are dropped)


class ResolvedMenuOut(BaseModel):
    """Everything the sidebar needs to render, in order."""
    items: List[ResolvedMenuItem]
    role: str
    organization_id: Optional[int] = None


# ------------------------------------------------------------
# /api/menu/roles  — the role permission matrix
# ------------------------------------------------------------

class RoleMatrixRow(BaseModel):
    """One menu key and its visibility per role."""
    menu_key: str
    parent: Optional[str] = None
    # role -> visible bool. Roles the editor can't edit are omitted.
    values: Dict[str, bool]


class RoleMatrixOut(BaseModel):
    """The whole matrix for the roles this editor is allowed to edit."""
    editable_roles: List[str]
    rows: List[RoleMatrixRow]


class RoleMatrixUpdateIn(BaseModel):
    """Bulk-update one role's matrix. Sends the complete new set."""
    # menu_key -> visible
    values: Dict[str, bool] = Field(default_factory=dict)


# ------------------------------------------------------------
# /api/menu/users  — user overrides (Layer 3)
# ------------------------------------------------------------

class UserOverrideRow(BaseModel):
    """One user, one menu key, one override state."""
    menu_key: str
    parent: Optional[str] = None
    role_default: bool          # what the role currently allows
    override: Optional[bool]    # None = inherit, True/False = explicit
    effective: bool             # final resolved visibility


class UserOverridesOut(BaseModel):
    user_id: int
    role: str
    rows: List[UserOverrideRow]


class UserOverridesUpdateIn(BaseModel):
    """Batch-save user overrides.
    Any menu_key present with a bool sets an override.
    Any menu_key present with null clears the override (back to inherit).
    Any menu_key absent is left untouched.
    """
    values: Dict[str, Optional[bool]] = Field(default_factory=dict)


# ------------------------------------------------------------
# /api/menu/me/preferences  — Layer 4 (personal)
# ------------------------------------------------------------

class MyPreferencesOut(BaseModel):
    order: List[str] = Field(default_factory=list)
    hidden: List[str] = Field(default_factory=list)
    updated_at: Optional[datetime] = None


class MyPreferencesIn(BaseModel):
    order: List[str] = Field(default_factory=list)
    hidden: List[str] = Field(default_factory=list)


# ------------------------------------------------------------
# Editor scoping helper response
# ------------------------------------------------------------

class EditableUserSummary(BaseModel):
    """A user this editor is allowed to modify overrides for."""
    id: int
    email: str
    first_name: str
    last_name: str
    role: str
    organization_id: Optional[int] = None