"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

import ReportActions from "@/components/reporting/ReportActions";
import { apiGet } from "@/lib/api";

type TicklerRow = [
  number, string, string, string, string, string,
  number | string, string, string, string, string,
  string, number | string,
];
type TicklerPreview = { title: string; headers: string[]; rows: TicklerRow[]; total: number };

export default function TenantTicklerPage() {
  const [propertyId, setPropertyId] = useState("");
  const [applied, setApplied] = useState("");
  const [preview, setPreview] = useState<TicklerPreview | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function load(property: string) {
    setBusy(true);
    setError("");
    setPreview(null);
    setApplied("");
    const suffix = property.trim()
      ? `?property_id=${encodeURIComponent(property.trim())}` : "";
    try {
      const result = await apiGet(`/api/reporting/tickler/preview${suffix}`) as TicklerPreview;
      setPreview(result);
      setApplied(property.trim());
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to load tenant tickler.");
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => { void load(""); }, []);

  return (
    <div className="space-y-5">
      <Link href="/dashboard/reporting" className="text-sm text-blue-700 hover:underline">← Reports</Link>
      <header>
        <h1 className="text-2xl font-bold text-slate-900">Tenant Tickler</h1>
        <p className="mt-1 text-sm text-slate-600">
          Tenant contacts and the most recent recorded lease activity in your authorized properties.
          Event sources are lease creation, updates, signatures and dated lease notes.
          Contractual start/end dates are displayed for context only: they do not prove
          an actual move-in, move-out or delivered notice. Note contents are not exported.
        </p>
      </header>
      <form onSubmit={(event) => { event.preventDefault(); void load(propertyId); }}
        className="flex flex-wrap items-end gap-3 rounded-xl border border-slate-200 bg-white p-4">
        <label className="text-sm font-medium text-slate-800">
          Property ID (optional)
          <input type="number" min={1} step={1} value={propertyId}
            onChange={(event) => setPropertyId(event.target.value)}
            placeholder="All accessible properties"
            className="mt-1 block w-64 rounded-lg border border-slate-300 p-2 text-sm" />
        </label>
        <button type="submit" disabled={busy}
          className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50">
          {busy ? "Loading…" : "Refresh tickler"}
        </button>
      </form>
      {error && <p role="alert" className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</p>}
      {preview && (
        <>
          <div className="flex flex-wrap items-center justify-between gap-3 text-sm text-slate-700">
            <p><strong>{preview.total}</strong> tenant contact records.</p>
            <ReportActions reportKey="tenant.tickler"
              parameters={applied ? { property_id: applied } : {}} />
          </div>
          <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white">
            <table className="w-full min-w-[1100px] text-sm">
              <thead className="bg-slate-50 text-slate-600"><tr>
                {preview.headers.map((header) => (
                  <th key={header} scope="col" className="whitespace-nowrap px-3 py-2 text-left font-semibold">{header}</th>
                ))}
              </tr></thead>
              <tbody>
                {preview.rows.map((row) => (
                  <tr key={row[0]} className="border-t border-slate-100">
                    {row.map((value, i) => (
                      <td key={i} className="whitespace-nowrap px-3 py-2">{String(value)}</td>
                    ))}
                  </tr>
                ))}
                {preview.rows.length === 0 && (
                  <tr><td colSpan={preview.headers.length} className="p-6 text-center text-slate-500">
                    No tenant events in your current scope.
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
