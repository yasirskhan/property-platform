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

export default function UnitDirectoryPage() {
  const [propertyId, setPropertyId] = useState("");
  const [preview, setPreview] = useState<Preview | null>(null);
  const [applied, setApplied] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function load() {
    setBusy(true); setError(""); setPreview(null); setApplied({});
    const parameters: Record<string, string> = propertyId.trim()
      ? { property_id: propertyId.trim() } : {};
    const query = new URLSearchParams(parameters).toString();
    try {
      const result = await apiGet(`/api/reporting/unit-directory/preview${query ? "?" + query : ""}`) as Preview;
      setPreview(result); setApplied(parameters);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unit directory unavailable.");
    } finally { setBusy(false); }
  }

  return (
    <div className="space-y-5">
      <Link href="/dashboard/reporting" className="text-sm text-blue-700 hover:underline">← Reports</Link>
      <header>
        <h1 className="text-2xl font-bold text-slate-900">Unit Directory</h1>
        <p className="mt-1 text-sm text-slate-600">
          Current recorded unit layout, rent and fee configuration.
          Availability and listing flags are editable inventory settings,
          not proof of physical vacancy or a current tenant lease.
          No payment or ledger amounts are included.
        </p>
      </header>
      <form onSubmit={(event) => { event.preventDefault(); void load(); }}
        className="flex flex-wrap items-end gap-3 rounded-xl border bg-white p-4">
        <label className="text-sm">Property ID (optional)
          <input type="number" min={1} step={1} value={propertyId}
            onChange={(event) => setPropertyId(event.target.value)}
            placeholder="All visible properties"
            className="mt-1 block w-56 rounded border p-2" />
        </label>
        <button type="submit" disabled={busy}
          className="rounded bg-slate-900 px-4 py-2 text-sm text-white disabled:opacity-50">
          {busy ? "Loading…" : "Load unit directory"}
        </button>
      </form>
      {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
      {preview && (
        <>
          <div className="flex flex-wrap items-center justify-between gap-3 text-sm">
            <span>{preview.total} active unit records.</span>
            <ReportActions reportKey="property.unit_directory" parameters={applied} />
          </div>
          <div className="overflow-x-auto rounded-xl border bg-white">
            <table className="min-w-[1250px] w-full text-sm">
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
                    No active unit records in the selected scope.
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
