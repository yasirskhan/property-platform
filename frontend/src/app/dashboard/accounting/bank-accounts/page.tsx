// ============================================================
// Bank Accounts list page
// ------------------------------------------------------------
// Route: /dashboard/accounting/bank-accounts
//
// Lists the org's physical bank accounts (Client Trust,
// Security Deposit Trust). Each maps to a GL cash account.
// Managers can edit bank details inline via a centered modal.
// ============================================================

"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  listBankAccounts,
  updateBankAccount,
  BankAccount,
  BankAccountList,
} from "@/lib/bankAccounts";
import { apiGet } from "@/lib/api";

type Me = { role: string };

const WRITE_ROLES = ["ADMIN", "OWNER", "MANAGER"];

export default function BankAccountsPage() {
  const [me, setMe] = useState<Me | null>(null);
  const [data, setData] = useState<BankAccountList | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const [selected, setSelected] = useState<BankAccount | null>(null);

  async function load() {
    setLoading(true);
    setError("");
    try {
      const meData = await apiGet("/auth/me");
      setMe(meData);
      const list = await listBankAccounts(false);
      setData(list);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Load failed");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  if (loading && !data) return <div className="text-slate-500">Loading…</div>;
  if (error) return <div className="text-red-600">{error}</div>;
  if (!data) return null;

  const canWrite = me ? WRITE_ROLES.includes(me.role) : false;

  return (
    <div>
      <div className="mb-4">
        <Link
          href="/dashboard"
          className="text-sm text-slate-500 hover:text-slate-800"
        >
          ← Back to Dashboard
        </Link>
      </div>

      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Bank Accounts</h1>
          <p className="text-slate-500 mt-1">
            {data.total} {data.total === 1 ? "account" : "accounts"}
          </p>
        </div>
      </div>

      <div className="bg-white border border-slate-200 rounded-xl overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-slate-50">
            <tr>
              <th className="text-left px-4 py-2 font-medium text-slate-700 w-32">
                Type
              </th>
              <th className="text-left px-4 py-2 font-medium text-slate-700">
                Name
              </th>
              <th className="text-left px-4 py-2 font-medium text-slate-700 w-40">
                GL Account
              </th>
              <th className="text-left px-4 py-2 font-medium text-slate-700 w-40">
                Bank
              </th>
              <th className="text-left px-4 py-2 font-medium text-slate-700 w-40">
                Account #
              </th>
              <th className="text-left px-4 py-2 font-medium text-slate-700 w-28">
                ACH
              </th>
              <th className="w-16"></th>
            </tr>
          </thead>
          <tbody>
            {data.items.length === 0 && (
              <tr>
                <td colSpan={7} className="px-4 py-8 text-center text-slate-500">
                  No bank accounts configured.
                </td>
              </tr>
            )}
            {data.items.map((b) => (
              <tr
                key={b.id}
                className="border-t border-slate-100 hover:bg-slate-50"
              >
                <td className="px-4 py-2">
                  <span
                    className={`text-xs px-2 py-0.5 rounded ${
                      b.account_type === "ESCROW"
                        ? "bg-purple-50 text-purple-700"
                        : "bg-blue-50 text-blue-700"
                    }`}
                  >
                    {b.account_type}
                  </span>
                </td>
                <td className="px-4 py-2 text-slate-800">{b.name}</td>
                <td className="px-4 py-2 text-slate-600 text-xs font-mono">
                  {b.gl_account_number} {b.gl_account_name}
                </td>
                <td className="px-4 py-2 text-slate-600 text-xs">
                  {b.bank_name || "—"}
                </td>
                <td className="px-4 py-2 text-slate-600 text-xs font-mono">
                  {b.account_number
                    ? `••••${b.account_number.slice(-4)}`
                    : "—"}
                </td>
                <td className="px-4 py-2 text-slate-600 text-xs">
                  {b.ach_format || "—"}
                </td>
                <td className="px-4 py-2 text-right">
                  {canWrite && (
                    <button
                      onClick={() => setSelected(b)}
                      className="text-blue-600 hover:text-blue-800 text-xs"
                    >
                      Edit
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {selected && (
        <EditModal
          account={selected}
          onClose={() => setSelected(null)}
          onSaved={async () => {
            setSelected(null);
            await load();
          }}
        />
      )}
    </div>
  );
}

// ------------------------------------------------------------
// Centered edit modal
// ------------------------------------------------------------
function EditModal({
  account,
  onClose,
  onSaved,
}: {
  account: BankAccount;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [name, setName] = useState(account.name);
  const [bankName, setBankName] = useState(account.bank_name || "");
  const [routing, setRouting] = useState(account.routing_number || "");
  const [accountNum, setAccountNum] = useState(account.account_number || "");
  const [accountType, setAccountType] = useState<"OPERATING" | "ESCROW">(
    account.account_type
  );
  const [achFormat, setAchFormat] = useState<"" | "CSV" | "NACHA">(
    (account.ach_format as "" | "CSV" | "NACHA") || ""
  );
  const [notes, setNotes] = useState(account.notes || "");

  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState("");

  async function handleSave() {
    setErr("");
    if (!name.trim()) {
      setErr("Name is required.");
      return;
    }
    setSaving(true);
    try {
      await updateBankAccount(account.id, {
        name: name.trim(),
        bank_name: bankName || null,
        routing_number: routing || null,
        account_number: accountNum || null,
        account_type: accountType,
        ach_format: achFormat || null,
        notes: notes || null,
      });
      onSaved();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Save failed");
    } finally {
      setSaving(false);
    }
  }

  return (
    <>
      <div className="fixed inset-0 bg-black/40 z-40" onClick={onClose} />
      <div className="fixed inset-0 z-50 flex items-center justify-center p-4 pointer-events-none">
        <div className="w-full max-w-xl max-h-[90vh] bg-white rounded-xl shadow-2xl flex flex-col pointer-events-auto">
          <div className="flex items-center justify-between px-6 py-4 border-b border-slate-200">
            <div>
              <div className="text-xs text-slate-500">Bank Account</div>
              <div className="font-semibold text-slate-900 text-lg">
                {account.name}
              </div>
            </div>
            <button
              onClick={onClose}
              className="text-slate-400 hover:text-slate-700 text-2xl leading-none"
            >
              ×
            </button>
          </div>

          <div className="flex-1 overflow-y-auto p-6 space-y-4 text-sm">
            {err && (
              <div className="px-3 py-2 bg-red-50 border border-red-200 text-red-700 rounded text-xs">
                {err}
              </div>
            )}

            <div>
              <div className="text-xs text-slate-500 mb-1">
                GL Account (read-only)
              </div>
              <div className="text-slate-800 font-mono text-xs bg-slate-50 px-3 py-2 rounded">
                {account.gl_account_number} {account.gl_account_name}
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs text-slate-500 mb-1">
                  Name *
                </label>
                <input
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  className="w-full border border-slate-300 rounded px-3 py-2 text-sm"
                />
              </div>
              <div>
                <label className="block text-xs text-slate-500 mb-1">
                  Type *
                </label>
                <select
                  value={accountType}
                  onChange={(e) =>
                    setAccountType(e.target.value as "OPERATING" | "ESCROW")
                  }
                  className="w-full border border-slate-300 rounded px-3 py-2 text-sm"
                >
                  <option value="OPERATING">Operating</option>
                  <option value="ESCROW">Escrow</option>
                </select>
              </div>
              <div className="col-span-2">
                <label className="block text-xs text-slate-500 mb-1">
                  Bank Name
                </label>
                <input
                  type="text"
                  value={bankName}
                  onChange={(e) => setBankName(e.target.value)}
                  className="w-full border border-slate-300 rounded px-3 py-2 text-sm"
                />
              </div>
              <div>
                <label className="block text-xs text-slate-500 mb-1">
                  Routing #
                </label>
                <input
                  type="text"
                  value={routing}
                  onChange={(e) => setRouting(e.target.value)}
                  className="w-full border border-slate-300 rounded px-3 py-2 text-sm font-mono"
                />
              </div>
              <div>
                <label className="block text-xs text-slate-500 mb-1">
                  Account #
                </label>
                <input
                  type="text"
                  value={accountNum}
                  onChange={(e) => setAccountNum(e.target.value)}
                  className="w-full border border-slate-300 rounded px-3 py-2 text-sm font-mono"
                />
              </div>
              <div className="col-span-2">
                <label className="block text-xs text-slate-500 mb-1">
                  ACH Format
                </label>
                <select
                  value={achFormat}
                  onChange={(e) =>
                    setAchFormat(e.target.value as "" | "CSV" | "NACHA")
                  }
                  className="w-full border border-slate-300 rounded px-3 py-2 text-sm"
                >
                  <option value="">— Not configured —</option>
                  <option value="CSV">CSV</option>
                  <option value="NACHA">NACHA</option>
                </select>
              </div>
              <div className="col-span-2">
                <label className="block text-xs text-slate-500 mb-1">
                  Notes
                </label>
                <textarea
                  rows={2}
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  className="w-full border border-slate-300 rounded px-3 py-2 text-sm"
                />
              </div>
            </div>
          </div>

          <div className="border-t border-slate-200 p-4 flex items-center gap-3">
            <button
              onClick={handleSave}
              disabled={saving}
              className="text-sm px-4 py-2 bg-slate-900 text-white rounded-lg hover:bg-slate-700 disabled:opacity-50"
            >
              {saving ? "Saving…" : "Save"}
            </button>
            <button
              onClick={onClose}
              disabled={saving}
              className="text-sm px-3 py-2 text-slate-600 hover:text-slate-900"
            >
              Cancel
            </button>
          </div>
        </div>
      </div>
    </>
  );
}