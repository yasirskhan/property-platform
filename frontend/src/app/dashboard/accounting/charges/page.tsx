// ============================================================
// Charges list page
// ------------------------------------------------------------
// Lists all standalone tenant charges. "New Charge" opens the
// Enter Charge form. Click a row to view.
//
// See PROJECT_MASTER.md Section 19.
// ============================================================

"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { apiGet } from "@/lib/api";
import { formatMoney, formatDate } from "@/lib/money";

interface Charge {
  id: number;
  tenant_user_id: number;
  unit_id: number | null;
  property_id: number | null;
  gl_account_id: number;
  charge_date: string;
  description: string;
  amount: string;
  amount_paid: string;
  is_paid: boolean;
}

export default function ChargesPage() {
  const [rows, setRows] = useState<Charge[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [showPaid, setShowPaid] = useState<"all" | "unpaid" | "paid">("all");

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams();
      if (dateFrom) params.set("date_from", dateFrom);
      if (dateTo) params.set("date_to", dateTo);
      if (showPaid === "unpaid") params.set("is_paid", "false");
      if (showPaid === "paid") params.set("is_paid", "true");
      const qs = params.toString();
      const data = (await apiGet(
        `/api/accounting/charges${qs ? "?" + qs : ""}`
      )) as Charge[];
      setRows(data);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Could not load charges.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const total = useMemo(
    () => rows.reduce((acc, c) => acc + parseFloat(c.amount || "0"), 0),
    [rows]
  );
  const unpaidTotal = useMemo(
    () =>
      rows.reduce(
        (acc, c) =>
          acc +
          (c.is_paid
            ? 0
            : parseFloat(c.amount || "0") - parseFloat(c.amount_paid || "0")),
        0
      ),
    [rows]
  );

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-1">
        <h1 className="text-xl font-semibold text-slate-900">Charges</h1>
        <Link
          href="/dashboard/accounting/charges/new"
          className="px-3 py-1.5 rounded-md bg-blue-600 text-white text-sm font-medium hover:bg-blue-700"
        >
          + New Charge
        </Link>
      </div>
      <p className="text-sm text-slate-500 mb-6">
        One-off amounts owed by tenants: late fees, damages, utility
        re-bills, misc.
      </p>

      <div className="bg-white border border-slate-200 rounded-lg p-4 mb-5 flex flex-wrap items-end gap-3">
        <div>
          <label className="block text-xs text-slate-600 mb-1">From</label>
          <input
            type="date"
            value={dateFrom}
            onChange={(e) => setDateFrom(e.target.value)}
            className="border border-slate-300 rounded-md px-2 py-1.5 text-sm"
          />
        </div>
        <div>
          <label className="block text-xs text-slate-600 mb-1">To</label>
          <input
            type="date"
            value={dateTo}
            onChange={(e) => setDateTo(e.target.value)}
            className="border border-slate-300 rounded-md px-2 py-1.5 text-sm"
          />
        </div>
        <div>
          <label className="block text-xs text-slate-600 mb-1">Status</label>
          <select
            value={showPaid}
            onChange={(e) =>
              setShowPaid(e.target.value as "all" | "unpaid" | "paid")
            }
            className="border border-slate-300 rounded-md px-2 py-1.5 text-sm bg-white"
          >
            <option value="all">All</option>
            <option value="unpaid">Unpaid</option>
            <option value="paid">Paid</option>
          </select>
        </div>
        <button
          type="button"
          onClick={load}
          className="px-3 py-1.5 rounded-md bg-slate-700 text-white text-sm font-medium hover:bg-slate-800"
        >
          Show
        </button>
      </div>

      {error && (
        <div className="text-sm text-red-600 mb-3 bg-red-50 border border-red-200 rounded-md px-3 py-2">
          {error}
        </div>
      )}

      <div className="bg-white rounded-lg border border-slate-200 overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-slate-600">
            <tr>
              <th className="text-left px-4 py-2 font-medium">Date</th>
              <th className="text-left px-4 py-2 font-medium">Description</th>
              <th className="text-left px-4 py-2 font-medium">Tenant</th>
              <th className="text-left px-4 py-2 font-medium">Unit</th>
              <th className="text-right px-4 py-2 font-medium">Amount</th>
              <th className="text-right px-4 py-2 font-medium">Balance</th>
              <th className="text-left px-4 py-2 font-medium">Status</th>
            </tr>
          </thead>
          <tbody>
            {loading && (
              <tr>
                <td colSpan={7} className="px-4 py-6 text-center text-slate-500">
                  Loading...
                </td>
              </tr>
            )}
            {!loading && rows.length === 0 && (
              <tr>
                <td colSpan={7} className="px-4 py-6 text-center text-slate-500">
                  No charges yet.
                </td>
              </tr>
            )}
            {rows.map((c) => {
              const bal =
                parseFloat(c.amount || "0") - parseFloat(c.amount_paid || "0");
              return (
                <tr key={c.id} className="border-t border-slate-100">
                  <td className="px-4 py-2">{formatDate(c.charge_date)}</td>
                  <td className="px-4 py-2">{c.description}</td>
                  <td className="px-4 py-2 text-slate-500">
                    #{c.tenant_user_id}
                  </td>
                  <td className="px-4 py-2 text-slate-500">
                    {c.unit_id ? `#${c.unit_id}` : "\u2014"}
                  </td>
                  <td className="px-4 py-2 text-right font-mono">
                    {formatMoney(c.amount)}
                  </td>
                  <td className="px-4 py-2 text-right font-mono">
                    {formatMoney(bal.toFixed(2))}
                  </td>
                  <td className="px-4 py-2">
                    {c.is_paid ? (
                      <span className="text-xs px-2 py-0.5 rounded-full bg-green-100 text-green-700">
                        Paid
                      </span>
                    ) : (
                      <span className="text-xs px-2 py-0.5 rounded-full bg-yellow-100 text-yellow-700">
                        Unpaid
                      </span>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
          {rows.length > 0 && (
            <tfoot className="bg-slate-50 text-slate-700">
              <tr className="border-t border-slate-200">
                <td className="px-4 py-2 text-xs" colSpan={4}>
                  {rows.length} charges
                </td>
                <td className="px-4 py-2 text-right font-mono font-medium">
                  {formatMoney(total.toFixed(2))}
                </td>
                <td className="px-4 py-2 text-right font-mono font-medium">
                  {formatMoney(unpaidTotal.toFixed(2))}
                </td>
                <td />
              </tr>
            </tfoot>
          )}
        </table>
      </div>
    </div>
  );
}