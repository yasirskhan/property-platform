"use client";

import { useState } from "react";
import Link from "next/link";

import ReportActions from "@/components/reporting/ReportActions";
import { apiGet } from "@/lib/api";

type Preview = { title: string; headers: string[]; rows: (string | number)[][]; total: number };

export default function GrossPotentialRentPage() {
  const [propertyId, setPropertyId] = useState("");
  const [month, setMonth] = useState(() => new Date().toISOString().slice(0, 7));
  const [preview, setPreview] = useState<Preview | null>(null);
  const [applied, setApplied] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function load() {
    setBusy(true); setError(""); setPreview(null); setApplied({});
    const params = { property_id: propertyId.trim(), month: month + "-01" };
    try {
      const data = await apiGet(
        `/api/reporting/gross-potential-rent/preview?${new URLSearchParams(params)}`
      ) as Preview;
      setPreview(data); setApplied(params);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Gross potential rent unavailable.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-5">
      <Link href="/dashboard/reporting" className="text-sm text-blue-700 hover:underline">← Reports</Link>
      <header>
        <h1 className="text-2xl font-bold text-slate-900">Gross Potential Rent</h1>
        <p className="mt-1 text-sm text-slate-600">
          Monthly projected market rent, scheduled rent and loss/gain are calculated from
          CURRENT unit and active-lease settings. Selecting an older month does not reconstruct
          historically frozen rents. Journal markers are separate and do not imply the current
          projections were the amounts originally posted. No accounting transactions are created.
        </p>
      </header>
      <form onSubmit={(event) => { event.preventDefault(); void load(); }}
        className="flex flex-wrap items-end gap-3 rounded-xl border border-slate-200 bg-white p-4">
        <label className="text-sm text-slate-700">Property ID
          <input required min={1} type="number" step={1} value={propertyId}
            onChange={(event) => setPropertyId(event.target.value)}
            className="mt-1 block w-44 rounded-lg border border-slate-300 p-2" />
        </label>
        <label className="text-sm text-slate-700">Month
          <input required type="month" min="2000-01" max="2100-12" value={month}
            onChange={(event) => setMonth(event.target.value)}
            className="mt-1 block w-44 rounded-lg border border-slate-300 p-2" />
        </label>
        <button type="submit" disabled={busy}
          className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50">
          {busy ? "Loading…" : "Load GPR projection"}
        </button>
      </form>
      {error && <p role="alert" className="rounded-lg border border-red-200 p-3 text-sm text-red-700">{error}</p>}
      {preview && (
        <>
          <div className="flex flex-wrap items-center justify-between gap-3 text-sm">
            <span><strong>{preview.total}</strong> active market-rent units.</span>
            <ReportActions reportKey="property.gross_potential_rent" parameters={applied} />
          </div>
          <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white">
            <table className="min-w-[1600px] w-full text-sm">
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
                    {row.map((cell, j) => (
                      <td key={j} className="whitespace-nowrap px-3 py-2">{String(cell)}</td>
                    ))}
                  </tr>
                ))}
                {preview.total === 0 && (
                  <tr><td colSpan={preview.headers.length} className="p-6 text-center text-slate-500">
                    No active units with positive market rent for this property.
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
