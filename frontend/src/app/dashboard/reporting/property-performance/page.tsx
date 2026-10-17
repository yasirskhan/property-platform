"use client";

import { useState } from "react";
import Link from "next/link";
import ReportActions from "@/components/reporting/ReportActions";
import { apiGet } from "@/lib/api";

type Preview = {
  title: string;
  headers: string[];
  rows: (string | number)[][];
  total: number;
};

export default function PropertyPerformancePage() {
  const [propertyId, setPropertyId] = useState("");
  const [year, setYear] = useState(String(new Date().getFullYear()));
  const [preview, setPreview] = useState<Preview | null>(null);
  const [applied, setApplied] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function load() {
    setBusy(true);
    setError("");
    setPreview(null);
    setApplied({});
    const parameters = { property_id: propertyId.trim(), calendar_year: year.trim() };
    const query = new URLSearchParams(parameters).toString();
    try {
      const result = await apiGet(`/api/reporting/property-performance/preview?${query}`) as Preview;
      setPreview(result);
      setApplied(parameters);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Property performance is unavailable.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-5">
      <Link href="/dashboard/reporting" className="text-sm text-blue-700 hover:underline">← Reports</Link>
      <header>
        <h1 className="text-2xl font-bold text-slate-900">Property Performance</h1>
        <p className="mt-1 text-sm text-slate-600">
          Posted income and expense journal lines tagged to a property, including
          reversals. This is an accrual-basis GL snapshot, not cash flow,
          net operating income, investment return or a historical rent roll.
          Organization-wide entries without a property tag are excluded.
        </p>
      </header>
      <form onSubmit={(event) => { event.preventDefault(); void load(); }}
        className="flex flex-wrap items-end gap-3 rounded-xl border bg-white p-4">
        <label className="text-sm">Property ID
          <input required type="number" min={1} step={1} value={propertyId}
            onChange={(event) => setPropertyId(event.target.value)}
            className="mt-1 block w-40 rounded border p-2" />
        </label>
        <label className="text-sm">Calendar year
          <input required type="number" min={2000} max={2099} step={1} value={year}
            onChange={(event) => setYear(event.target.value)}
            className="mt-1 block w-36 rounded border p-2" />
        </label>
        <button type="submit" disabled={busy}
          className="rounded bg-slate-900 px-4 py-2 text-sm text-white disabled:opacity-50">
          {busy ? "Loading…" : "Load performance"}
        </button>
      </form>
      {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
      {preview && (
        <>
          <div className="flex flex-wrap items-center justify-between gap-3 text-sm">
            <span>{preview.total > 0 ? preview.total - 1 : 0} GL accounts with recorded activity.</span>
            <ReportActions reportKey="property.performance" parameters={applied} />
          </div>
          <div className="overflow-x-auto rounded-xl border bg-white">
            <table className="min-w-[900px] w-full text-sm">
              <thead className="bg-slate-50"><tr>
                {preview.headers.map((head) => (
                  <th key={head} scope="col" className="px-3 py-2 text-left font-semibold">{head}</th>
                ))}
              </tr></thead>
              <tbody>
                {preview.rows.map((row, index) => (
                  <tr key={index} className="border-t">
                    {row.map((value, col) => <td key={col} className="px-3 py-2">{String(value)}</td>)}
                  </tr>
                ))}
                {preview.total === 0 && (
                  <tr><td colSpan={preview.headers.length} className="p-5 text-center text-slate-500">
                    No property-tagged income or expense GL entries in this calendar year.
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
