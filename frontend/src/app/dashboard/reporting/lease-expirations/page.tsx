"use client";

import { useState } from "react";
import Link from "next/link";

import ReportActions from "@/components/reporting/ReportActions";
import { apiGet } from "@/lib/api";

type ReportMode = "detail" | "summary";
type Preview = {
  title: string; headers: string[];
  rows: (string | number)[][]; total: number;
};

const REPORT_KEYS = {
  detail: "property.lease_expiration_detail",
  summary: "property.lease_expiration_summary",
} as const;

export default function LeaseExpirationsPage() {
  const [mode, setMode] = useState<ReportMode>("detail");
  const [from, setFrom] = useState(() => new Date().toISOString().slice(0, 10));
  const [through, setThrough] = useState(() => {
    const next = new Date();
    next.setFullYear(next.getFullYear() + 1);
    return next.toISOString().slice(0, 10);
  });
  const [propertyId, setPropertyId] = useState("");
  const [preview, setPreview] = useState<Preview | null>(null);
  const [applied, setApplied] = useState<Record<string, string>>({});
  const [appliedMode, setAppliedMode] = useState<ReportMode>("detail");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function load(selected: ReportMode) {
    setBusy(true); setError(""); setPreview(null); setApplied({});
    const params = {
      date_from: from, date_to: through,
      ...(propertyId.trim() ? { property_id: propertyId.trim() } : {}),
    };
    try {
      const q = new URLSearchParams({ ...params, report_key: REPORT_KEYS[selected] });
      const result = await apiGet(`/api/reporting/lease-expirations/preview?${q}`) as Preview;
      setPreview(result); setApplied(params); setAppliedMode(selected);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Lease expiration report unavailable.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-5">
      <Link href="/dashboard/reporting" className="text-sm text-blue-700 hover:underline">← Reports</Link>
      <header>
        <h1 className="text-2xl font-bold text-slate-900">Lease Expirations</h1>
        <p className="mt-1 text-sm text-slate-600">
          Dates come from recorded lease contracts with ACTIVE or EXPIRED status.
          Scheduled contract endings do not prove a tenant moved out, a notice
          was served, or that a renewal has or has not been signed. Rent shown
          is the recorded monthly contract amount, not cash receipts.
        </p>
      </header>
      <form onSubmit={(event) => { event.preventDefault(); void load(mode); }}
        className="flex flex-wrap items-end gap-3 rounded-xl border border-slate-200 bg-white p-4">
        <label className="text-sm text-slate-700">Report
          <select value={mode} onChange={(event) => { setMode(event.target.value as ReportMode); setPreview(null); setApplied({}); }}
            className="mt-1 block rounded-lg border border-slate-300 p-2">
            <option value="detail">Lease expiration detail</option>
            <option value="summary">Summary by month</option>
          </select>
        </label>
        <label className="text-sm text-slate-700">From
          <input required type="date" value={from} onChange={(event) => setFrom(event.target.value)}
            className="mt-1 block rounded-lg border border-slate-300 p-2" />
        </label>
        <label className="text-sm text-slate-700">Through
          <input required type="date" value={through} onChange={(event) => setThrough(event.target.value)}
            className="mt-1 block rounded-lg border border-slate-300 p-2" />
        </label>
        <label className="text-sm text-slate-700">Property ID (optional)
          <input type="number" min={1} step={1} value={propertyId}
            onChange={(event) => setPropertyId(event.target.value)}
            className="mt-1 block w-40 rounded-lg border border-slate-300 p-2" />
        </label>
        <button type="submit" disabled={busy}
          className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50">
          {busy ? "Loading…" : "Load lease expirations"}
        </button>
      </form>
      {error && <p role="alert" className="rounded-lg border border-red-200 p-3 text-sm text-red-700">{error}</p>}
      {preview && (
        <>
          <div className="flex flex-wrap items-center justify-between gap-3 text-sm">
            <span><strong>{preview.total}</strong> {appliedMode === "detail" ? "recorded lease endings" : "property-month groups"}.</span>
            <ReportActions reportKey={REPORT_KEYS[appliedMode]} parameters={applied} />
          </div>
          <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white">
            <table className="min-w-[1050px] w-full text-sm">
              <thead className="bg-slate-50"><tr>
                {preview.headers.map((header) => <th key={header} scope="col"
                  className="whitespace-nowrap px-3 py-2 text-left font-semibold">{header}</th>)}
              </tr></thead>
              <tbody>
                {preview.rows.map((row, i) => (
                  <tr key={i} className="border-t border-slate-100">
                    {row.map((cell, j) => <td key={j} className="whitespace-nowrap px-3 py-2">
                      {String(cell)}
                    </td>)}
                  </tr>
                ))}
                {preview.total === 0 && (
                  <tr><td colSpan={preview.headers.length} className="p-6 text-center text-slate-500">
                    No eligible recorded lease endings in the selected range.
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
