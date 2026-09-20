// ============================================================
// RoleMatrix.tsx
// ------------------------------------------------------------
// The Roles tab in Settings -> Permissions.
//
// Grid: rows = menu keys (grouped by parent), columns = roles
// the current user is allowed to edit. Each cell is a checkbox.
//
// Saving is per-cell: toggling a checkbox fires a PUT that sends
// only that one changed value. The backend returns the full
// fresh matrix, so we just replace local state with the response.
//
// The parent row (e.g. ACCOUNTING) is rendered as a header and
// is also toggleable — unchecking it visually unchecks children
// on the client but does NOT auto-save them (the backend's
// parent-hidden rule handles the effective behavior).
// ============================================================

"use client";

import { useEffect, useState } from "react";
import { RotateCcw, Loader2 } from "lucide-react";
import {
  getRoleMatrix,
  updateRoleMatrix,
  resetRoleMatrix,
  RoleMatrix as RoleMatrixType,
  RoleMatrixRow,
} from "@/lib/menuPermissions";
import { getMenuEntry, ROLE_LABELS } from "@/lib/menuConfig";

type Props = {
  onSaved: () => void;
};

export default function RoleMatrix({ onSaved }: Props) {
  const [data, setData] = useState<RoleMatrixType | null>(null);
  const [loading, setLoading] = useState(true);
  const [busyKey, setBusyKey] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const m = await getRoleMatrix();
      setData(m);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load matrix");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function toggle(
    role: string,
    row: RoleMatrixRow,
    next: boolean
  ) {
    if (!data) return;
    setBusyKey(`${role}:${row.menu_key}`);
    try {
      const updated = await updateRoleMatrix(role, {
        [row.menu_key]: next,
      });
      setData(updated);
      onSaved();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to save");
    } finally {
      setBusyKey(null);
    }
  }

  async function reset(role: string) {
    const ok = window.confirm(
      `Reset the ${ROLE_LABELS[role] || role} role to defaults? ` +
        `All custom permissions for this role will be lost.`
    );
    if (!ok) return;
    setBusyKey(`reset:${role}`);
    try {
      const updated = await resetRoleMatrix(role);
      setData(updated);
      onSaved();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to reset");
    } finally {
      setBusyKey(null);
    }
  }

  if (loading || !data) {
    return <div className="p-4 text-slate-500">Loading matrix…</div>;
  }

  // ----------------------------------------------------------
  // Group rows: parents first, then their children below
  // ----------------------------------------------------------
  const parentRows = data.rows.filter((r) => r.parent === null);
  const childrenOf = new Map<string, RoleMatrixRow[]>();
  for (const r of data.rows) {
    if (r.parent !== null) {
      const arr = childrenOf.get(r.parent) || [];
      arr.push(r);
      childrenOf.set(r.parent, arr);
    }
  }

  return (
    <div>
      {error && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 text-red-700 text-sm rounded">
          {error}
        </div>
      )}

      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div className="text-sm text-slate-600">
          Unchecking a menu item hides it from that role. Children are
          hidden automatically when their parent is hidden.
        </div>
        <div className="flex gap-2">
          {data.editable_roles.map((role) => (
            <button
              key={role}
              onClick={() => reset(role)}
              disabled={busyKey === `reset:${role}`}
              className="inline-flex items-center gap-1 px-2 py-1 text-xs text-slate-600 hover:text-slate-900 disabled:opacity-50"
              title={`Reset ${ROLE_LABELS[role] || role} to defaults`}
            >
              <RotateCcw className="w-3 h-3" />
              Reset {ROLE_LABELS[role] || role}
            </button>
          ))}
        </div>
      </div>

      {/* Matrix table */}
      <div className="border border-slate-200 rounded overflow-hidden bg-white">
        <table className="w-full text-sm">
          <thead className="bg-slate-50">
            <tr>
              <th className="text-left px-4 py-2 font-medium text-slate-700">
                Menu item
              </th>
              {data.editable_roles.map((role) => (
                <th
                  key={role}
                  className="text-center px-4 py-2 font-medium text-slate-700 whitespace-nowrap"
                >
                  {ROLE_LABELS[role] || role}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {parentRows.map((parent) => {
              const children = childrenOf.get(parent.menu_key) || [];
              const parentEntry = getMenuEntry(parent.menu_key);
              return (
                <ParentWithChildren
                  key={parent.menu_key}
                  parent={parent}
                  parentLabel={parentEntry?.label || parent.menu_key}
                  children={children}
                  roles={data.editable_roles}
                  busyKey={busyKey}
                  onToggle={toggle}
                />
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ------------------------------------------------------------
// A parent row plus all its children.
// Children are indented under the parent.
// ------------------------------------------------------------
function ParentWithChildren({
  parent,
  parentLabel,
  children,
  roles,
  busyKey,
  onToggle,
}: {
  parent: RoleMatrixRow;
  parentLabel: string;
  children: RoleMatrixRow[];
  roles: string[];
  busyKey: string | null;
  onToggle: (role: string, row: RoleMatrixRow, next: boolean) => void;
}) {
  return (
    <>
      <tr className="border-t border-slate-200 bg-slate-50/40">
        <td className="px-4 py-2 font-medium text-slate-800">
          {parentLabel}
        </td>
        {roles.map((role) => {
          const cellKey = `${role}:${parent.menu_key}`;
          const busy = busyKey === cellKey;
          return (
            <td key={role} className="px-4 py-2 text-center">
              <CellCheckbox
                checked={parent.values[role] ?? false}
                busy={busy}
                onChange={(next) => onToggle(role, parent, next)}
              />
            </td>
          );
        })}
      </tr>

      {children.map((child) => {
        const childEntry = getMenuEntry(child.menu_key);
        return (
          <tr key={child.menu_key} className="border-t border-slate-100">
            <td className="px-4 py-2 text-slate-600 pl-10">
              {childEntry?.label || child.menu_key}
            </td>
            {roles.map((role) => {
              const cellKey = `${role}:${child.menu_key}`;
              const busy = busyKey === cellKey;
              return (
                <td key={role} className="px-4 py-2 text-center">
                  <CellCheckbox
                    checked={child.values[role] ?? false}
                    busy={busy}
                    onChange={(next) => onToggle(role, child, next)}
                  />
                </td>
              );
            })}
          </tr>
        );
      })}
    </>
  );
}

// ------------------------------------------------------------
// One checkbox with a busy spinner
// ------------------------------------------------------------
function CellCheckbox({
  checked,
  busy,
  onChange,
}: {
  checked: boolean;
  busy: boolean;
  onChange: (next: boolean) => void;
}) {
  if (busy) {
    return <Loader2 className="w-4 h-4 animate-spin text-slate-400 mx-auto" />;
  }
  return (
    <input
      type="checkbox"
      checked={checked}
      onChange={(e) => onChange(e.target.checked)}
      className="w-4 h-4 accent-blue-600 cursor-pointer"
    />
  );
}