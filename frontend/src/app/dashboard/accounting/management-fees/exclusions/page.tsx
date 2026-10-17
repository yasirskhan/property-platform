"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import {
  listManagementFeeExclusions,
  type ManagementFeeExclusion,
} from "@/lib/managementFees";
import { formatDate, formatMoney } from "@/lib/money";
import { useDisplay } from "@/contexts/DisplayContext";

export default function ManagementFeeExclusionsPage() {
  const { prefs } = useDisplay();
  const [items, setItems] = useState<ManagementFeeExclusion[]>([]);
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [includeReversed, setIncludeReversed] = useState(true);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  async function load() {
    setLoading(true);
    setError("");
    try {
      const result = await listManagementFeeExclusions({
        date_from: dateFrom || undefined,
        date_to: dateTo || undefined,
        include_reversed: includeReversed,
      });
      setItems(result.items);
    } catch (err) {
      setItems([]);
      setError(
        err instanceof Error ? err.message : "Management fee exclusions failed to load"
      );
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const activeTotal = useMemo(
    () =>
      items
        .filter((item) => !item.is_reversed)
        .reduce((sum, item) => sum + Number(item.amount), 0),
    [items]
  );

  return (
    <div
      data-layout-mode={(prefs?.layout_mode ?? "TABS").toLowerCase()}
      data-density={(prefs?.density ?? "COMFORTABLE").toLowerCase()}
      className="max-w-6xl p-6"
    >
      <Link
        href="/dashboard/accounting/management-fees"
        className="text-sm text-slate-500 hover:text-slate-800"
      >
        ← Back to Management Fees
      </Link>

      <div className="mt-4 mb-6">
        <h1 className="text-2xl font-bold text-slate-900">
          Management Fee Exclusions
        </h1>
        <p className="text-slate-500 mt-1">
          Receipts explicitly marked to be excluded from management-fee calculations.
          Posted receipts remain immutable; this page is an audit view of that existing flag.
        </p>
      </div>

      <div className="bg-white border border-slate-200 rounded-xl p-4 mb-5 flex flex-wrap items-end gap-4">
        <div>
          <label className="block text-xs text-slate-500 mb-1">From</label>
          <input
            type="date"
            value={dateFrom}
            onChange={(event) => setDateFrom(event.target.value)}
            className="border border-slate-300 rounded-lg px-3 py-2 text-sm"
          />
        </div>
        <div>
          <label className="block text-xs text-slate-500 mb-1">To</label>
          <input
            type="date"
            value={dateTo}
            onChange={(event) => setDateTo(event.target.value)}
            className="border border-slate-300 rounded-lg px-3 py-2 text-sm"
          />
        </div>
        <label className="flex items-center gap-2 text-sm text-slate-600">
          <input
            type="checkbox"
            checked={includeReversed}
            onChange={(event) => setIncludeReversed(event.target.checked)}
          />
          Include reversed source receipts
        </label>
        <button
          type="button"
          onClick={() => void load()}
          className="px-4 py-2 rounded-lg bg-slate-800 text-white text-sm font-medium"
        >
          Show
        </button>
      </div>

      {error && (
        <div className="text-sm text-red-700 bg-red-50 border border-red-200 rounded-lg px-4 py-3 mb-5">
          {error}
        </div>
      )}

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-5">
        <div className="bg-white border border-slate-200 rounded-xl p-4">
          <div className="text-xs text-slate-500">Excluded source receipts shown</div>
          <div className="text-xl font-semibold text-slate-900">{items.length}</div>
        </div>
        <div className="bg-white border border-slate-200 rounded-xl p-4">
          <div className="text-xs text-slate-500">Active excluded receipt total</div>
          <div className="text-xl font-semibold text-slate-900">
            {formatMoney(activeTotal)}
          </div>
        </div>
      </div>

      <div className="bg-white border border-slate-200 rounded-xl overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-slate-50">
            <tr>
              <th className="px-4 py-3 text-left font-medium text-slate-700">Receipt</th>
              <th className="px-4 py-3 text-left font-medium text-slate-700">Date</th>
              <th className="px-4 py-3 text-left font-medium text-slate-700">Property / Source</th>
              <th className="px-4 py-3 text-left font-medium text-slate-700">Reference</th>
              <th className="px-4 py-3 text-right font-medium text-slate-700">Amount</th>
              <th className="px-4 py-3 text-left font-medium text-slate-700">Status</th>
            </tr>
          </thead>
          <tbody>
            {loading && (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-slate-500">
                  Loading exclusions…
                </td>
              </tr>
            )}
            {!loading && items.length === 0 && (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-slate-500">
                  No explicitly excluded receipts match these filters.
                </td>
              </tr>
            )}
            {!loading &&
              items.map((item) => (
                <tr
                  key={item.receipt_id}
                  className={`border-t border-slate-100 ${item.is_reversed ? "opacity-60" : ""}`}
                >
                  <td className="px-4 py-3">
                    <div className="font-medium text-slate-900">#{item.receipt_id}</div>
                    <div className="text-xs text-slate-500">{item.receipt_type}</div>
                  </td>
                  <td className="px-4 py-3 text-slate-700">{formatDate(item.receipt_date)}</td>
                  <td className="px-4 py-3">
                    <div className="text-slate-800">{item.property_name || "No property"}</div>
                    <div className="text-xs text-slate-500">{item.source_name || item.remarks || "—"}</div>
                  </td>
                  <td className="px-4 py-3 text-slate-600">{item.reference_number || "—"}</td>
                  <td className="px-4 py-3 text-right font-mono">{formatMoney(item.amount)}</td>
                  <td className="px-4 py-3">
                    {item.is_reversed ? (
                      <span className="text-xs text-slate-600 bg-slate-100 px-2 py-1 rounded-full">
                        Reversed
                      </span>
                    ) : (
                      <span className="text-xs text-amber-700 bg-amber-50 px-2 py-1 rounded-full">
                        Excluded
                      </span>
                    )}
                  </td>
                </tr>
              ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
