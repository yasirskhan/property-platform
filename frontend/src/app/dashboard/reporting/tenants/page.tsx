"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

import ReportActions from "@/components/reporting/ReportActions";
import { apiGet } from "@/lib/api";

type TenantRow = [
  number, string, string, string, string, string,
  number | string, string, string, string, number | string,
];
type TenantDirectoryPreview = { title: string; headers: string[]; rows: TenantRow[]; total: number };

export default function TenantDirectoryPage() {
  const [propertyId, setPropertyId] = useState("");
  const [appliedPropertyId, setAppliedPropertyId] = useState("");
  const [preview, setPreview] = useState<TenantDirectoryPreview | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function load(nextPropertyId: string) {
    setBusy(true);
    setError("");
    setPreview(null);
    setAppliedPropertyId("");
    const suffix = nextPropertyId.trim()
      ? `?property_id=${encodeURIComponent(nextPropertyId.trim())}` : "";
    try {
      const data = await apiGet(`/api/reporting/tenants/preview${suffix}`) as TenantDirectoryPreview;
      setPreview(data);
      setAppliedPropertyId(nextPropertyId.trim());
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Cannot load tenant directory.");
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => { void load(""); }, []);

  return (
    <div className="space-y-5">
      <Link href="/dashboard/reporting" className="text-sm text-blue-700 hover:underline">← Reports</Link>
      <header>
        <h1 className="text-2xl font-bold text-slate-900">Tenant Directory</h1>
        <p className="mt-1 text-sm text-slate-600">
          Active tenant contacts and eligible current lease associations.
          Administrators also see tenants without an eligible current lease;
          managers see only tenants on assigned properties. Historical
          leases are not included.
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
          {busy ? "Loading…" : "Refresh directory"}
        </button>
      </form>
      {error && <p role="alert" className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</p>}
      {preview && (
        <>
          <div className="flex flex-wrap items-center justify-between gap-3 text-sm text-slate-700">
            <p><strong>{preview.total}</strong> tenant-directory entries.</p>
            <ReportActions reportKey="tenant.directory"
              parameters={appliedPropertyId ? { property_id: appliedPropertyId } : {}} />
          </div>
          <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white">
            <table className="w-full min-w-[1000px] text-sm">
              <thead className="bg-slate-50 text-slate-600"><tr>
                {preview.headers.map((header) => (
                  <th key={header} scope="col" className="whitespace-nowrap px-3 py-2 text-left font-semibold">{header}</th>
                ))}
              </tr></thead>
              <tbody>
                {preview.rows.map((row, index) => (
                  <tr key={`${row[0]}-${row[6]}-${index}`} className="border-t border-slate-100">
                    {row.map((value, i) => (
                      <td key={i} className="whitespace-nowrap px-3 py-2">{String(value)}</td>
                    ))}
                  </tr>
                ))}
                {preview.rows.length === 0 && (
                  <tr><td colSpan={preview.headers.length} className="p-6 text-center text-slate-500">
                    No tenants in the selected scope.
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
