// ============================================================
// menuPermissions.ts
// ------------------------------------------------------------
// Typed API client for the menu permission system.
//
// Wraps the 10 endpoints under /api/menu so callers don't have
// to remember paths or shapes.
//
// Everything goes through apiGet/apiPut/apiPost/apiDelete in
// lib/api.ts so auth, error handling, and base URL are shared.
// ============================================================

import { apiGet, apiPost, apiPut, apiDelete } from "@/lib/api";

// ------------------------------------------------------------
// Shapes returned from the backend
// ------------------------------------------------------------

export type ResolvedMenuItem = {
  key: string;
  parent: string | null;
  visible: boolean;
};

export type ResolvedMenu = {
  items: ResolvedMenuItem[];
  role: string;
  organization_id: number | null;
};

export type RoleMatrixRow = {
  menu_key: string;
  parent: string | null;
  values: Record<string, boolean>;   // role -> visible
};

export type RoleMatrix = {
  editable_roles: string[];
  rows: RoleMatrixRow[];
};

export type UserOverrideRow = {
  menu_key: string;
  parent: string | null;
  role_default: boolean;
  override: boolean | null;   // null = inherit
  effective: boolean;
};

export type UserOverrides = {
  user_id: number;
  role: string;
  rows: UserOverrideRow[];
};

export type MyPreferences = {
  order: string[];
  hidden: string[];
  updated_at: string | null;
};

export type EditableUserSummary = {
  id: number;
  email: string;
  first_name: string;
  last_name: string;
  role: string;
  organization_id: number | null;
};

// ------------------------------------------------------------
// Endpoints
// ------------------------------------------------------------

// GET /api/menu/me
export function getMyMenu(): Promise<ResolvedMenu> {
  return apiGet("/api/menu/me");
}

// GET /api/menu/roles
export function getRoleMatrix(): Promise<RoleMatrix> {
  return apiGet("/api/menu/roles");
}

// PUT /api/menu/roles/{role}  — send the full new value set for one role
export function updateRoleMatrix(
  role: string,
  values: Record<string, boolean>
): Promise<RoleMatrix> {
  return apiPut(`/api/menu/roles/${role}`, { values });
}

// POST /api/menu/roles/{role}/reset
export function resetRoleMatrix(role: string): Promise<RoleMatrix> {
  return apiPost(`/api/menu/roles/${role}/reset`);
}

// GET /api/menu/users
export function listEditableUsers(): Promise<EditableUserSummary[]> {
  return apiGet("/api/menu/users");
}

// GET /api/menu/users/{user_id}
export function getUserOverrides(userId: number): Promise<UserOverrides> {
  return apiGet(`/api/menu/users/${userId}`);
}

// PUT /api/menu/users/{user_id}
// values: menu_key -> true | false | null (null clears the override)
export function updateUserOverrides(
  userId: number,
  values: Record<string, boolean | null>
): Promise<UserOverrides> {
  return apiPut(`/api/menu/users/${userId}`, { values });
}

// DELETE /api/menu/users/{user_id}/overrides
export function clearUserOverrides(userId: number): Promise<null> {
  return apiDelete(`/api/menu/users/${userId}/overrides`);
}

// GET /api/menu/me/preferences
export function getMyPreferences(): Promise<MyPreferences> {
  return apiGet("/api/menu/me/preferences");
}

// PUT /api/menu/me/preferences
export function updateMyPreferences(
  order: string[],
  hidden: string[]
): Promise<MyPreferences> {
  return apiPut("/api/menu/me/preferences", { order, hidden });
}