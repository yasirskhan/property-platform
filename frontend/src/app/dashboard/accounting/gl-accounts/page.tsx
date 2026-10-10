// ============================================================
// GL Accounts Page (Chart of Accounts)
// ------------------------------------------------------------
// Route: /dashboard/accounting/gl-accounts
//
// Shows every GL account in the current org, grouped by
// account type. Admin/Owner/Manager can add, edit, and
// deactivate accounts. Clicking an account name opens its
// ledger.
// ============================================================

"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  listGLAccounts,
  deleteGLAccount,
  GLAccount,
  GLAccountList,
  ACCOUNT_TYPE_LABELS,
  ACCOUNT_TYPE_ORDER,
  GLAccountPostingPermissionMatrix,
  getGLAccountPostingPermissions,
  updateGLAccountPostingPermissions,
  GLBalanceRecalculation,
  recalculateGLBalances,
} from "@/lib/glAccounts";
import { apiGet } from "@/lib/api";
import GLAccountDrawer from "@/components/accounting/GLAccountDrawer";
import Flag from "@/components/features/Flag";
import ConfirmModal from "@/components/ui/ConfirmModal";
import { useDisplay } from "@/contexts/DisplayContext";
import ReportActions from "@/components/reporting/ReportActions";

type Me = { role: string };

const WRITE_ROLES = ["ADMIN", "OWNER", "MANAGER"];

export default function GLAccountsPage() {
  const { prefs } = useDisplay();
  const [me, setMe] = useState<Me | null>(null);
  const [data, setData] = useState<GLAccountList | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [includeInactive, setIncludeInactive] = useState(false);

  // Drawer state
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [editing, setEditing] = useState<GLAccount | null>(null);
  const [deactivateTarget, setDeactivateTarget] = useState<GLAccount | null>(null);
  const [deactivateBusy, setDeactivateBusy] = useState(false);
  const [permissionsOpen, setPermissionsOpen] = useState(false);
  const [permissionsLoading, setPermissionsLoading] = useState(false);
  const [permissionsSaving, setPermissionsSaving] = useState(false);
  const [permissionMatrix, setPermissionMatrix] = useState<GLAccountPostingPermissionMatrix | null>(null);
  const [recalculateBusy, setRecalculateBusy] = useState(false);
  const [recalculateResult, setRecalculateResult] = useState<GLBalanceRecalculation | null>(null);

  async function load() {
    setLoading(true);
    setError("");
    try {
      const meData = await apiGet("/auth/me");
      setMe(meData);
      const list = await listGLAccounts(includeInactive);
      setData(list);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Load failed");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [includeInactive]);

  function openCreate() {
    setEditing(null);
    setDrawerOpen(true);
  }

  function openEdit(account: GLAccount) {
    setEditing(account);
    setDrawerOpen(true);
  }

  function closeDrawer() {
    setDrawerOpen(false);
    setEditing(null);
  }

  async function openPermissions() {
    setPermissionsOpen(true);
    setPermissionsLoading(true);
    setError("");
    try { setPermissionMatrix(await getGLAccountPostingPermissions()); }
    catch (err) {
      setPermissionsOpen(false);
      setError(err instanceof Error ? err.message : "Permission load failed");
    } finally { setPermissionsLoading(false); }
  }

  function setPostingPermission(accountId: number, role: string, allowed: boolean) {
    setPermissionMatrix((current) => current ? ({
      ...current,
      rows: current.rows.map((row) => row.gl_account_id === accountId
        ? {...row, permissions: {...row.permissions, [role]: allowed}}
        : row),
    }) : current);
  }

  async function savePostingPermissions() {
    if (!permissionMatrix) return;
    setPermissionsSaving(true);
    setError("");
    try {
      const values: Record<number, Record<string, boolean>> = {};
      for (const row of permissionMatrix.rows) values[row.gl_account_id] = row.permissions;
      setPermissionMatrix(await updateGLAccountPostingPermissions(values));
      setPermissionsOpen(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Permission save failed");
    } finally { setPermissionsSaving(false); }
  }

  async function handleRecalculate() {
    setRecalculateBusy(true);
    setRecalculateResult(null);
    setError("");
    try {
      setRecalculateResult(await recalculateGLBalances());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Balance recalculation failed");
    } finally {
      setRecalculateBusy(false);
    }
  }

  async function handleDelete() {
    if (!deactivateTarget) return;
    setDeactivateBusy(true);
    try {
      await deleteGLAccount(deactivateTarget.id);
      setDeactivateTarget(null);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Deactivate failed");
    } finally {
      setDeactivateBusy(false);
    }
  }

  if (loading && !data) return <div className="text-slate-500">Loading…</div>;
  if (error) return <div className="text-red-600">{error}</div>;
  if (!data) return null;

  const canWrite = me ? WRITE_ROLES.includes(me.role) : false;

  // Build a lookup for "sub-account of" labels
  const byId = new Map<number, GLAccount>();
  for (const g of data.groups) {
    for (const a of g.accounts) byId.set(a.id, a);
  }

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">
            Chart of Accounts
          </h1>
          <p className="text-slate-500 mt-1">
            {data.total} {data.total === 1 ? "account" : "accounts"}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <ReportActions
            reportKey="accounting.chart_of_accounts"
            parameters={{ include_inactive: includeInactive }}
          />
          <Flag name="release.accounting.owner_held_security_deposits">
            <Link
              href="/dashboard/accounting/owner-held-security-deposits"
              className="text-sm px-3 py-2 border border-slate-300 rounded-lg text-slate-700 hover:bg-slate-50"
            >
              Owner Held Deposits
            </Link>
          </Flag>
          <Flag name="release.accounting.gl_account_permissions">
            <button type="button" onClick={openPermissions} className="text-sm px-3 py-2 border border-slate-300 rounded-lg text-slate-700 hover:bg-slate-50">
              GL Account Permissions
            </button>
          </Flag>
          <Flag name="release.accounting.gl_accounts.recalculate">
            <button
              type="button"
              onClick={handleRecalculate}
              disabled={recalculateBusy}
              className="text-sm px-3 py-2 border border-slate-300 rounded-lg text-slate-700 hover:bg-slate-50 disabled:opacity-60"
            >
              {recalculateBusy ? "Recalculating…" : "Recalculate Balances"}
            </button>
          </Flag>
          <Link
            href="/dashboard/accounting/trial-balance"
            className="text-sm px-3 py-2 text-slate-600 hover:text-slate-900"
          >
            Trial Balance
          </Link>
          <button
            onClick={() => setIncludeInactive((v) => !v)}
            className="text-sm px-3 py-2 text-slate-600 hover:text-slate-900"
          >
            {includeInactive ? "Hide inactive" : "Show inactive"}
          </button>
          {canWrite && (
            <button
              onClick={openCreate}
              className="text-sm px-4 py-2 bg-slate-900 text-white rounded-lg hover:bg-slate-700"
            >
              + Add Account
            </button>
          )}
        </div>
      </div>

      {recalculateResult && (
        <div
          className={`mb-6 rounded-lg border px-4 py-3 text-sm ${
            recalculateResult.is_balanced
              ? "border-green-200 bg-green-50 text-green-800"
              : "border-red-200 bg-red-50 text-red-800"
          }`}
        >
          Recomputed {recalculateResult.account_count} accounts from{" "}
          {recalculateResult.entry_count} ledger entries. Debits and credits{" "}
          {recalculateResult.is_balanced ? "are balanced." : "do not balance."}
          {" "}No cached balances were written.
        </div>
      )}

      {/* Groups */}
      {ACCOUNT_TYPE_ORDER.map((type) => {
        const group = data.groups.find((g) => g.account_type === type);
        if (!group || group.accounts.length === 0) return null;
        return (
          <div key={type} className="mb-8">
            <h2 className="text-sm font-semibold text-slate-500 uppercase tracking-wide mb-3">
              {ACCOUNT_TYPE_LABELS[type] || type}
            </h2>

            <div className="bg-white border border-slate-200 rounded-xl overflow-hidden">
              <table className="w-full text-sm">
                <thead className="bg-slate-50">
                  <tr>
                    <th className="text-left px-4 py-2 font-medium text-slate-700 w-24">
                      GL #
                    </th>
                    <th className="text-left px-4 py-2 font-medium text-slate-700">
                      Account Name
                    </th>
                    <th className="text-left px-4 py-2 font-medium text-slate-700 w-40">
                      Sub-account of
                    </th>
                    <th className="text-center px-4 py-2 font-medium text-slate-700 w-28">
                      Mgmt Fees
                    </th>
                    <th className="text-center px-4 py-2 font-medium text-slate-700 w-28">
                      Cash Flow
                    </th>
                    <th className="text-center px-4 py-2 font-medium text-slate-700 w-28">
                      Must Clear
                    </th>
                    {canWrite && <th className="w-48"></th>}
                  </tr>
                </thead>
                <tbody>
                  {group.accounts.map((a) => {
                    const parent = a.sub_account_of
                      ? byId.get(a.sub_account_of)
                      : null;
                    return (
                      <tr
                        key={a.id}
                        className={`border-t border-slate-100 hover:bg-slate-50 ${
                          !a.is_active ? "opacity-50" : ""
                        }`}
                      >
                        <td className="px-4 py-2 text-slate-500 font-mono">
                          {a.gl_number}
                        </td>
                        <td className="px-4 py-2 text-slate-800">
                          <Link
                            href={`/dashboard/accounting/gl-accounts/${a.id}/ledger`}
                            className="text-blue-600 hover:underline"
                          >
                            {a.name}
                          </Link>
                          {!a.is_active && (
                            <span className="ml-2 text-xs px-1.5 py-0.5 bg-red-50 text-red-700 rounded">
                              inactive
                            </span>
                          )}
                        </td>
                        <td className="px-4 py-2 text-slate-500 text-xs">
                          {parent
                            ? `${parent.gl_number} ${parent.name}`
                            : "—"}
                        </td>
                        <td className="px-4 py-2 text-center text-slate-600">
                          {a.subject_to_mgmt_fees ? "Yes" : "—"}
                        </td>
                        <td className="px-4 py-2 text-center text-slate-600">
                          {a.include_on_cash_flow ? "Yes" : "—"}
                        </td>
                        <td className="px-4 py-2 text-center text-slate-600">
                          {a.must_clear ? "Yes" : "—"}
                        </td>
                        {canWrite && (
                          <td className="px-4 py-2 text-right whitespace-nowrap">
                            <button
                              onClick={() => openEdit(a)}
                              className="text-blue-600 hover:text-blue-800 text-xs"
                            >
                              Edit
                            </button>
                            {a.is_active && (
                              <button
                                onClick={() => setDeactivateTarget(a)}
                                className="text-red-600 hover:text-red-800 text-xs ml-4"
                              >
                                Deactivate
                              </button>
                            )}
                          </td>
                        )}
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        );
      })}

      <span hidden aria-hidden="true" data-compat-slot="gl-accounts.hide-semantics" />

      <ConfirmModal
        open={deactivateTarget !== null}
        title="Deactivate GL account?"
        description={deactivateTarget ? `${deactivateTarget.gl_number} ${deactivateTarget.name} will be hidden from active lists while historical transactions remain intact.` : ""}
        confirmLabel="Deactivate account"
        busy={deactivateBusy}
        danger
        onCancel={() => {
          if (!deactivateBusy) setDeactivateTarget(null);
        }}
        onConfirm={handleDelete}
      />

      {permissionsOpen && (
        <div className="fixed inset-0 z-50 bg-black/30 flex items-center justify-center p-6">
          <div className="bg-white rounded-xl shadow-xl w-full max-w-6xl max-h-[85vh] flex flex-col">
            <div className="px-6 py-4 border-b border-slate-200">
              <h2 className="text-lg font-semibold">GL Account Permissions</h2>
              <p className="text-sm text-slate-500 mt-1">Uncheck a role to deny posting. This layer can only subtract access.</p>
            </div>
            <div className="flex-1 overflow-auto px-6 py-4">
              {permissionsLoading || !permissionMatrix ? <div>Loading permissions…</div> : (
                <table className="w-full text-sm">
                  <thead><tr><th className="text-left py-2">GL Account</th>{permissionMatrix.roles.map((role)=><th key={role} className="px-2">{role.replace("_"," ")}</th>)}</tr></thead>
                  <tbody>{permissionMatrix.rows.map((row)=><tr key={row.gl_account_id} className="border-t">
                    <td className="py-2"><span className="font-mono">{row.gl_number}</span> {row.name}</td>
                    {permissionMatrix.roles.map((role)=><td key={role} className="text-center">
                      <input type="checkbox" aria-label={`${row.gl_number} ${role} posting`} checked={row.permissions[role] !== false}
                        onChange={(e)=>setPostingPermission(row.gl_account_id, role, e.target.checked)} />
                    </td>)}
                  </tr>)}</tbody>
                </table>
              )}
            </div>
            <div className="px-6 py-4 border-t flex justify-end gap-3">
              <button type="button" onClick={()=>setPermissionsOpen(false)} disabled={permissionsSaving}>Cancel</button>
              <button type="button" onClick={savePostingPermissions} disabled={permissionsSaving || permissionsLoading || !permissionMatrix}
                className="px-4 py-2 bg-slate-900 text-white rounded-lg disabled:opacity-50">
                {permissionsSaving ? "Saving…" : "Save permissions"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Drawer */}
      {drawerOpen && (
        <GLAccountDrawer
          account={editing}
          allAccounts={data.groups.flatMap((g) => g.accounts)}
          onClose={closeDrawer}
          onSaved={async () => {
            setDrawerOpen(false);
            setEditing(null);
            await load();
          }}
        />
      )}
    </div>
  );
}