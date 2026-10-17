"use client";

import { useState } from "react";
import Link from "next/link";

import ReportActions from "@/components/reporting/ReportActions";
import { apiGet } from "@/lib/api";

type Preview = {
  title: string; headers: string[]; rows: (string | number)[][]; total: number;
};

export default function PropertyBudgetDetailPage() {
  const [propertyId, setPropertyId] = useState("");
  const [year, setYear] = useState(String(new Date().getFullYear()));
  const [applied, setApplied] = useState<Record<string, string>>({});
  const [preview, setPreview] = useState<Preview | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function load(prop: string, period: string) {
    setBusy(true); setError(""); setPreview(null); setApplied({});
    const params = { property_id: prop.trim(), calendar_year: period.trim() };
    try {
      const result = await apiGet(
        `/api/reporting/budget-detail/preview?${new URLSearchParams(params)}`
      ) as Preview;
      setPreview(result); setApplied(params);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to load budget detail.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-5">
      <Link href="/dashboard/reporting" className="text-sm text-blue-700 hover:underline">← Reports</Link>
      <header>
        <h1 className="text-2xl font-bold text-slate-900">Property Budget Detail</h1>
        <p className="mt-1 text-sm text-slate-600">
          Explicit monthly income and expense targets from the existing budget schedule.
          A blank month means no target was entered; a recorded zero is shown as zero.
          Annual totals sum only configured months. This report does not include
          GL actuals and is available for either reporting basis.
        </p>
        <Link href="/dashboard/reporting/budget-comparison"
          className="mt-2 inline-block text-sm text-blue-700 underline">
          Enter or edit a monthly budget target
        </Link>
      </header>
      <form onSubmit={(event) => { event.preventDefault(); void load(propertyId, year); }}
        className="flex flex-wrap items-end gap-3 rounded-xl border border-slate-200 bg-white p-4">
        <label className="text-sm text-slate-700">Property ID
          <input required min={1} type="number" step={1} value={propertyId}
            onChange={(event) => setPropertyId(event.target.value)}
            className="mt-1 block w-48 rounded-lg border border-slate-300 p-2" />
        </label>
        <label className="text-sm text-slate-700">Calendar year
          <input required min={2000} max={2100} type="number" step={1} value={year}
            onChange={(event) => setYear(event.target.value)}
            className="mt-1 block w-40 rounded-lg border border-slate-300 p-2" />
        </label>
        <button type="submit" disabled={busy}
          className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50">
          {busy ? "Loading…" : "Load budget detail"}
        </button>
      </form>
      {error && <p role="alert" className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</p>}
      {preview && (
        <>
          <div className="flex flex-wrap items-center justify-between gap-3 text-sm">
            <span><strong>{preview.total}</strong> budgeted income/expense accounts.</span>
            <ReportActions reportKey="property.budget_detail" parameters={applied} />
          </div>
          <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white">
            <table className="min-w-[1450px] w-full text-sm">
              <thead className="bg-slate-50"><tr>
                {preview.headers.map((header) => (
                  <th key={header} scope="col" className="whitespace-nowrap px-3 py-2 text-left font-semibold">
                    {header}
                  </th>
                ))}
              </tr></thead>
              <tbody>
                {preview.rows.map((row, i) => (
                  <tr key={i} className="border-t border-slate-100">
                    {row.map((cell, n) => (
                      <td key={n} className="whitespace-nowrap px-3 py-2">
                        {cell === "" ? <span className="text-slate-400">—</span> : String(cell)}
                      </td>
                    ))}
                  </tr>
                ))}
                {preview.total === 0 && (
                  <tr><td colSpan={preview.headers.length} className="p-6 text-center text-slate-500">
                    No explicit budget targets entered for this property/year.
                  </td></tr>
                )}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
