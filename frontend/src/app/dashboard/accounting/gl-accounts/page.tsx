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
} from "@/lib/glAccounts";
import { apiGet } from "@/lib/api";
import GLAccountDrawer from "@/components/accounting/GLAccountDrawer";

type Me = { role: string };

const WRITE_ROLES = ["ADMIN", "OWNER", "MANAGER"];

export default function GLAccountsPage() {
  const [me, setMe] = useState<Me | null>(null);
  const [data, setData] = useState<GLAccountList | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [includeInactive, setIncludeInactive] = useState(false);

  // Drawer state
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [editing, setEditing] = useState<GLAccount | null>(null);

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

  async function handleDelete(account: GLAccount) {
    const ok = window.confirm(
      `Deactivate GL account ${account.gl_number} ${account.name}?\n\n` +
        `The account will be hidden from active lists but historical ` +
        `transactions will still reference it.`
    );
    if (!ok) return;
    try {
      await deleteGLAccount(account.id);
      await load();
    } catch (err) {
      alert(err instanceof Error ? err.message : "Delete failed");
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
        <div className="flex items-center gap-3">
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
                                onClick={() => handleDelete(a)}
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