"use client";

import { useState } from "react";
import Link from "next/link";

import { apiGet } from "@/lib/api";
import ReportActions from "@/components/reporting/ReportActions";

type Preview = {
  title: string;
  headers: string[];
  rows: (string | number)[][];
  total: number;
};

export default function CommercialLeaseReferencesPage() {
  const [propertyId, setPropertyId] = useState("");
  const [preview, setPreview] = useState<Preview | null>(null);
  const [applied, setApplied] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function load() {
    setBusy(true); setError(""); setPreview(null); setApplied({});
    const parameters = propertyId.trim() ? { property_id: propertyId.trim() } : {};
    try {
      const query = new URLSearchParams(parameters);
      const suffix = query.size ? `?${query.toString()}` : "";
      const report = await apiGet(
        `/api/reporting/commercial-lease-references/preview${suffix}`,
      ) as Preview;
      setPreview(report);
      setApplied(parameters);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Commercial references unavailable.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-5">
      <Link href="/dashboard/reporting" className="text-sm text-blue-700 hover:underline">← Reports</Link>
      <header className="space-y-2">
        <h1 className="text-2xl font-bold text-slate-900">Commercial lease references</h1>
        <p className="text-sm text-slate-600">
          Read-only staff-reference report. Lease start, end, and status come
          from current recorded leases, while rent commencement is a separate
          unverified staff entry. Neither is proof of executed contract terms.
          No rent, CAM, NNN, percentage rent, notices, invoices, or ledger
          entries are calculated or issued here.
        </p>
      </header>
      <form onSubmit={(event) => { event.preventDefault(); void load(); }}
        className="flex flex-wrap items-end gap-3 rounded-xl border bg-white p-4">
        <label className="text-sm text-slate-700">Commercial property ID (optional)
          <input type="number" min={1} step={1} value={propertyId}
            onChange={(event) => setPropertyId(event.target.value)}
            className="mt-1 block w-44 rounded-lg border p-2" />
        </label>
        <button type="submit" disabled={busy}
          className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50">
          {busy ? "Loading…" : "Load staff references"}
        </button>
      </form>
      {error && <p role="alert" className="rounded-lg border border-red-200 p-3 text-sm text-red-700">{error}</p>}
      {preview && (
        <>
          <div className="flex flex-wrap items-center justify-between gap-3 text-sm">
            <span><strong>{preview.total}</strong> authorized staff references.</span>
            <ReportActions reportKey="commercial.lease_references" parameters={applied} />
          </div>
          <div className="overflow-x-auto rounded-xl border bg-white">
            <table className="min-w-[1080px] w-full text-sm">
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
                    {row.map((value, j) => (
                      <td key={j} className="whitespace-nowrap px-3 py-2">{String(value)}</td>
                    ))}
                  </tr>
                ))}
                {preview.total === 0 && (
                  <tr><td colSpan={preview.headers.length} className="p-6 text-center text-slate-500">
                    No authorized staff references are recorded.
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
