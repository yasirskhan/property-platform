// ============================================================
// Trial Balance Page
// ------------------------------------------------------------
// Route: /dashboard/accounting/trial-balance
//
// Lists every active GL account with a nonzero balance and
// its debit / credit totals. The sum of all debits must equal
// the sum of all credits — if not, something is broken and we
// flag it visually.
//
// This is the accountant's "does it all add up?" check.
// ============================================================

"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  getTrialBalance,
  TrialBalance,
  TrialBalanceRow,
  formatBalance,
  formatMoney,
} from "@/lib/glTransactions";
import { ACCOUNT_TYPE_LABELS, ACCOUNT_TYPE_ORDER } from "@/lib/glAccounts";

export default function TrialBalancePage() {
  const [data, setData] = useState<TrialBalance | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const [asOf, setAsOf] = useState("");
  const [includeZero, setIncludeZero] = useState(false);

  async function load() {
    setLoading(true);
    setError("");
    try {
      const tb = await getTrialBalance(asOf || undefined, includeZero);
      setData(tb);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Load failed");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [asOf, includeZero]);

  if (loading && !data) return <div className="text-slate-500">Loading…</div>;
  if (error) return <div className="text-red-600">{error}</div>;
  if (!data) return null;

  // Group rows by account type
  const byType = new Map<string, TrialBalanceRow[]>();
  for (const row of data.rows) {
    const arr = byType.get(row.account_type) || [];
    arr.push(row);
    byType.set(row.account_type, arr);
  }

  return (
    <div>
      {/* Back link (smart: history if possible, dashboard otherwise) */}
      <div className="mb-4">
        <button
          type="button"
          onClick={() => {
            if (typeof window !== "undefined" && window.history.length > 1) {
              window.history.back();
            } else {
              window.location.href = "/dashboard";
            }
          }}
          className="text-sm text-slate-500 hover:text-slate-800"
        >
          ← Back
        </button>
      </div>

      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Trial Balance</h1>
          <p className="text-slate-500 mt-1 text-sm">
            As of {data.as_of} · {data.rows.length} account
            {data.rows.length === 1 ? "" : "s"}
          </p>
        </div>
        <div className="flex items-end gap-3">
          <div>
            <label className="block text-xs text-slate-500 mb-1">As of</label>
            <input
              type="date"
              value={asOf}
              onChange={(e) => setAsOf(e.target.value)}
              className="px-3 py-1.5 border border-slate-300 rounded text-sm"
            />
          </div>
          <label className="inline-flex items-center gap-2 text-sm text-slate-600 pb-2 cursor-pointer">
            <input
              type="checkbox"
              checked={includeZero}
              onChange={(e) => setIncludeZero(e.target.checked)}
              className="w-4 h-4 accent-blue-600"
            />
            Include zero balances
          </label>
        </div>
      </div>

      {/* Balance check banner */}
      {!data.is_balanced && (
        <div className="mb-6 p-4 bg-red-50 border border-red-200 text-red-700 text-sm rounded-lg">
          <strong>Out of balance.</strong> Total debits ({formatBalance(data.total_debits)})
          do not equal total credits ({formatBalance(data.total_credits)}).
          This should never happen. Please report it.
        </div>
      )}

      {/* Rows, grouped by account type */}
      {data.rows.length === 0 ? (
        <div className="bg-white border border-slate-200 rounded-lg p-12 text-center text-slate-500">
          No entries yet. Once transactions are posted, they'll show up here.
        </div>
      ) : (
        <div className="bg-white border border-slate-200 rounded-lg overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-slate-50">
              <tr>
                <th className="text-left px-4 py-2 font-medium text-slate-700 w-24">
                  GL #
                </th>
                <th className="text-left px-4 py-2 font-medium text-slate-700">
                  Account
                </th>
                <th className="text-right px-4 py-2 font-medium text-slate-700 w-40">
                  Debit
                </th>
                <th className="text-right px-4 py-2 font-medium text-slate-700 w-40">
                  Credit
                </th>
              </tr>
            </thead>
            <tbody>
              {ACCOUNT_TYPE_ORDER.map((type) => {
                const rows = byType.get(type) || [];
                if (rows.length === 0) return null;

                // Type subtotal
                const typeDebit = rows.reduce(
                  (s, r) => s + Number(r.debit || 0),
                  0
                );
                const typeCredit = rows.reduce(
                  (s, r) => s + Number(r.credit || 0),
                  0
                );

                return (
                  <TypeGroup
                    key={type}
                    type={type}
                    rows={rows}
                    typeDebit={typeDebit}
                    typeCredit={typeCredit}
                  />
                );
              })}
            </tbody>
            {/* Grand totals */}
            <tfoot className="bg-slate-100">
              <tr className="border-t-2 border-slate-300">
                <td colSpan={2} className="px-4 py-2 text-right font-medium text-slate-700">
                  Totals
                </td>
                <td className="px-4 py-2 text-right font-mono font-bold text-slate-900">
                  {formatBalance(data.total_debits)}
                </td>
                <td className="px-4 py-2 text-right font-mono font-bold text-slate-900">
                  {formatBalance(data.total_credits)}
                </td>
              </tr>
            </tfoot>
          </table>
        </div>
      )}
    </div>
  );
}

// ------------------------------------------------------------
// A group of accounts of the same type, with a subtotal row
// ------------------------------------------------------------
function TypeGroup({
  type,
  rows,
  typeDebit,
  typeCredit,
}: {
  type: string;
  rows: TrialBalanceRow[];
  typeDebit: number;
  typeCredit: number;
}) {
  return (
    <>
      <tr className="border-t-2 border-slate-200 bg-slate-50/40">
        <td colSpan={4} className="px-4 py-2 text-xs font-semibold text-slate-500 uppercase tracking-wide">
          {ACCOUNT_TYPE_LABELS[type] || type}
        </td>
      </tr>
      {rows.map((row) => (
        <tr
          key={row.gl_account_id}
          className="border-t border-slate-100 hover:bg-slate-50"
        >
          <td className="px-4 py-2 font-mono text-slate-500">
            {row.gl_number}
          </td>
          <td className="px-4 py-2 text-slate-800">
            <Link
              href={`/dashboard/accounting/gl-accounts/${row.gl_account_id}/ledger`}
              className="text-blue-600 hover:underline"
            >
              {row.name}
            </Link>
          </td>
          <td className="px-4 py-2 text-right font-mono text-slate-700">
            {formatMoney(row.debit)}
          </td>
          <td className="px-4 py-2 text-right font-mono text-slate-700">
            {formatMoney(row.credit)}
          </td>
        </tr>
      ))}
      <tr className="border-t border-slate-200 bg-slate-50">
        <td colSpan={2} className="px-4 py-2 text-right text-xs text-slate-600 font-medium">
          {ACCOUNT_TYPE_LABELS[type] || type} subtotal
        </td>
        <td className="px-4 py-2 text-right font-mono text-sm font-semibold text-slate-800">
          {formatBalance(typeDebit)}
        </td>
        <td className="px-4 py-2 text-right font-mono text-sm font-semibold text-slate-800">
          {formatBalance(typeCredit)}
        </td>
      </tr>
    </>
  );
}