// ============================================================
// UserOverrides.tsx
// ------------------------------------------------------------
// The Users tab in Settings -> Permissions.
//
// Left: list of users the current editor is allowed to edit.
// Right: drawer with every menu item and a 3-state control:
//          Inherit    — use the role default (override = null)
//          Force allow — override = true  (cannot grant what
//                         the role denied; see backend)
//          Force hide  — override = false (always hides)
//
// Save is a batch: one PUT with the full set of changed values.
// ============================================================

"use client";

import { useEffect, useState } from "react";
import { X, Save, RotateCcw, Loader2 } from "lucide-react";
import {
  listEditableUsers,
  getUserOverrides,
  updateUserOverrides,
  clearUserOverrides,
  EditableUserSummary,
  UserOverrides as UserOverridesType,
  UserOverrideRow,
} from "@/lib/menuPermissions";
import { getMenuEntry, ROLE_LABELS } from "@/lib/menuConfig";

type Props = {
  onSaved: () => void;
};

type OverrideState = "inherit" | "allow" | "hide";

function rowToState(row: UserOverrideRow): OverrideState {
  if (row.override === null) return "inherit";
  return row.override ? "allow" : "hide";
}

export default function UserOverrides({ onSaved }: Props) {
  const [users, setUsers] = useState<EditableUserSummary[] | null>(null);
  const [loadingUsers, setLoadingUsers] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [selected, setSelected] = useState<EditableUserSummary | null>(null);
  const [detail, setDetail] = useState<UserOverridesType | null>(null);
  const [draft, setDraft] = useState<Record<string, OverrideState>>({});
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [saving, setSaving] = useState(false);

  // ----------------------------------------------------------
  // Load the user list
  // ----------------------------------------------------------
  useEffect(() => {
    setLoadingUsers(true);
    listEditableUsers()
      .then(setUsers)
      .catch((e) =>
        setError(e instanceof Error ? e.message : "Failed to load users")
      )
      .finally(() => setLoadingUsers(false));
  }, []);

  // ----------------------------------------------------------
  // Load overrides when a user is selected
  // ----------------------------------------------------------
  async function openUser(u: EditableUserSummary) {
    setSelected(u);
    setDetail(null);
    setDraft({});
    setLoadingDetail(true);
    setError(null);
    try {
      const d = await getUserOverrides(u.id);
      setDetail(d);
      const next: Record<string, OverrideState> = {};
      for (const row of d.rows) next[row.menu_key] = rowToState(row);
      setDraft(next);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load overrides");
    } finally {
      setLoadingDetail(false);
    }
  }

  function closeDrawer() {
    setSelected(null);
    setDetail(null);
    setDraft({});
  }

  function setState(key: string, value: OverrideState) {
    setDraft((prev) => ({ ...prev, [key]: value }));
  }

  // ----------------------------------------------------------
  // Save — send only values that differ from the current server state
  // ----------------------------------------------------------
  async function save() {
    if (!detail) return;
    setSaving(true);
    setError(null);
    try {
      const payload: Record<string, boolean | null> = {};
      for (const row of detail.rows) {
        const serverState = rowToState(row);
        const draftState = draft[row.menu_key] ?? serverState;
        if (draftState === serverState) continue;
        if (draftState === "inherit") payload[row.menu_key] = null;
        else if (draftState === "allow") payload[row.menu_key] = true;
        else payload[row.menu_key] = false;
      }

      if (Object.keys(payload).length === 0) {
        closeDrawer();
        return;
      }

      const updated = await updateUserOverrides(selected!.id, payload);
      setDetail(updated);
      const next: Record<string, OverrideState> = {};
      for (const row of updated.rows) next[row.menu_key] = rowToState(row);
      setDraft(next);
      onSaved();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to save");
    } finally {
      setSaving(false);
    }
  }

  // ----------------------------------------------------------
  // Clear all overrides
  // ----------------------------------------------------------
  async function clearAll() {
    if (!selected) return;
    const ok = window.confirm(
      `Clear all overrides for ${selected.email}? ` +
        `They will revert to their role's defaults.`
    );
    if (!ok) return;
    setSaving(true);
    setError(null);
    try {
      await clearUserOverrides(selected.id);
      await openUser(selected);
      onSaved();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to clear");
    } finally {
      setSaving(false);
    }
  }

  // ----------------------------------------------------------
  // Render
  // ----------------------------------------------------------
  if (loadingUsers) {
    return <div className="p-4 text-slate-500">Loading users…</div>;
  }

  const hasChanges =
    detail !== null &&
    detail.rows.some(
      (row) => rowToState(row) !== draft[row.menu_key]
    );

  return (
    <div>
      {error && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 text-red-700 text-sm rounded">
          {error}
        </div>
      )}

      <div className="text-sm text-slate-600 mb-4">
        Click a user to set personal overrides. Overrides can only
        subtract visibility — they cannot grant what the role
        doesn't already allow.
      </div>

      {users && users.length === 0 && (
        <div className="p-4 bg-slate-50 border border-slate-200 rounded text-slate-500 text-sm">
          You don't have permission to edit any users.
        </div>
      )}

      {users && users.length > 0 && (
        <div className="border border-slate-200 rounded overflow-hidden bg-white">
          <table className="w-full text-sm">
            <thead className="bg-slate-50">
              <tr>
                <th className="text-left px-4 py-2 font-medium text-slate-700">
                  Name
                </th>
                <th className="text-left px-4 py-2 font-medium text-slate-700">
                  Email
                </th>
                <th className="text-left px-4 py-2 font-medium text-slate-700">
                  Role
                </th>
                <th className="w-20"></th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => (
                <tr key={u.id} className="border-t border-slate-100">
                  <td className="px-4 py-2 text-slate-800">
                    {u.first_name} {u.last_name}
                  </td>
                  <td className="px-4 py-2 text-slate-600">{u.email}</td>
                  <td className="px-4 py-2 text-slate-600">
                    {ROLE_LABELS[u.role] || u.role}
                  </td>
                  <td className="px-4 py-2 text-right">
                    <button
                      onClick={() => openUser(u)}
                      className="text-blue-600 hover:text-blue-800 text-sm"
                    >
                      Edit
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* ---------- Drawer ---------- */}
      {selected && (
        <div className="fixed inset-0 bg-black/30 z-40 flex justify-end">
          <div className="w-[520px] bg-white h-full shadow-xl flex flex-col">
            <div className="px-5 py-4 border-b border-slate-200 flex items-center justify-between">
              <div>
                <div className="text-sm text-slate-500">
                  Overrides for
                </div>
                <div className="font-medium text-slate-900">
                  {selected.first_name} {selected.last_name}{" "}
                  <span className="text-slate-400 font-normal">
                    ({selected.email})
                  </span>
                </div>
              </div>
              <button
                onClick={closeDrawer}
                className="p-1.5 rounded hover:bg-slate-100"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="flex-1 overflow-y-auto px-5 py-4">
              {loadingDetail && (
                <div className="text-slate-500 text-sm">Loading…</div>
              )}

              {detail && (
                <>
                  {detail.rows.map((row) => (
                    <OverrideRow
                      key={row.menu_key}
                      row={row}
                      state={draft[row.menu_key] ?? rowToState(row)}
                      onChange={(v) => setState(row.menu_key, v)}
                    />
                  ))}
                </>
              )}
            </div>

            <div className="px-5 py-4 border-t border-slate-200 flex items-center gap-3">
              <button
                onClick={save}
                disabled={saving || !hasChanges}
                className="inline-flex items-center gap-2 px-4 py-2 bg-blue-600 text-white text-sm rounded hover:bg-blue-700 disabled:opacity-50"
              >
                {saving ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <Save className="w-4 h-4" />
                )}
                Save
              </button>

              <button
                onClick={clearAll}
                disabled={saving}
                className="inline-flex items-center gap-2 px-4 py-2 text-slate-600 text-sm hover:text-slate-900 disabled:opacity-50"
              >
                <RotateCcw className="w-4 h-4" />
                Clear all overrides
              </button>

              <div className="flex-1" />

              {hasChanges && (
                <span className="text-xs text-amber-600">
                  Unsaved changes
                </span>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ------------------------------------------------------------
// One menu item row in the drawer
// ------------------------------------------------------------
function OverrideRow({
  row,
  state,
  onChange,
}: {
  row: UserOverrideRow;
  state: OverrideState;
  onChange: (v: OverrideState) => void;
}) {
  const entry = getMenuEntry(row.menu_key);
  const label = entry?.label || row.menu_key;
  const isChild = row.parent !== null;

  // Role-default label: what the role currently allows
  const roleDefault = row.role_default ? "visible" : "hidden";

  return (
    <div
      className={`flex items-center justify-between py-2 border-b border-slate-100 ${
        isChild ? "pl-6" : ""
      }`}
    >
      <div className="flex-1 min-w-0">
        <div className="text-sm text-slate-800 truncate">{label}</div>
        <div className="text-xs text-slate-400">
          Role default: {roleDefault}
        </div>
      </div>

      <div className="flex gap-1">
        <StateButton
          label="Inherit"
          active={state === "inherit"}
          onClick={() => onChange("inherit")}
        />
        <StateButton
          label="Allow"
          active={state === "allow"}
          disabled={!row.role_default}
          title={
            !row.role_default
              ? "The role doesn't allow this — an override can't grant it"
              : "Force-allow for this user"
          }
          onClick={() => onChange("allow")}
        />
        <StateButton
          label="Hide"
          active={state === "hide"}
          onClick={() => onChange("hide")}
        />
      </div>
    </div>
  );
}

function StateButton({
  label,
  active,
  disabled,
  title,
  onClick,
}: {
  label: string;
  active: boolean;
  disabled?: boolean;
  title?: string;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      title={title}
      className={`px-2 py-1 text-xs rounded border transition-colors ${
        active
          ? "bg-blue-600 text-white border-blue-600"
          : "bg-white text-slate-600 border-slate-200 hover:border-slate-400"
      } ${disabled ? "opacity-40 cursor-not-allowed" : ""}`}
    >
      {label}
    </button>
  );
}