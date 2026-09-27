"use client";

import { useState } from "react";
import Link from "next/link";
import ReportActions from "@/components/reporting/ReportActions";
import { apiGet } from "@/lib/api";

type Preview = {
  title: string;
  headers: string[];
  rows: (string | number | null)[][];
  total: number;
};
type Filter = {
  property_id?: string;
  status?: string;
  date_from?: string;
  date_to?: string;
};
const STATUSES = [
  "submitted", "acknowledged", "assigned", "in_progress",
  "completed", "closed", "cancelled",
];

export default function WorkOrderReportPage() {
  const [propertyId, setPropertyId] = useState("");
  const [status, setStatus] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [preview, setPreview] = useState<Preview | null>(null);
  const [applied, setApplied] = useState<Filter | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function load(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true); setError(""); setPreview(null); setApplied(null);
    const params: Filter = {
      ...(propertyId.trim() ? { property_id: propertyId.trim() } : {}),
      ...(status ? { status } : {}),
      ...(dateFrom ? { date_from: dateFrom } : {}),
      ...(dateTo ? { date_to: dateTo } : {}),
    };
    try {
      const qs = new URLSearchParams(params);
      const data = await apiGet(`/api/reporting/work-orders/preview?${qs.toString()}`) as Preview;
      setPreview(data); setApplied(params);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Work order report unavailable.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-5">
      <Link href="/dashboard/reporting" className="text-sm text-blue-700 hover:underline">← Reports</Link>
      <header>
        <h1 className="text-2xl font-bold text-slate-900">Work Order Report</h1>
        <p className="mt-1 text-sm text-slate-600">
          Current recorded work orders in your permitted properties.
          Private entry instructions, tenant contact details and photographs are excluded.
          Costs appear only when explicitly recorded, not as actual posted GL expenses.
        </p>
      </header>
      <form onSubmit={(event) => { void load(event); }}
        className="flex flex-wrap items-end gap-3 rounded-xl border bg-white p-4">
        <label className="block text-sm font-medium">
          Property ID (optional)
          <input type="number" min={1} step={1} value={propertyId}
            onChange={(event) => setPropertyId(event.target.value)}
            className="mt-1 block rounded border px-3 py-2" />
        </label>
        <label className="block text-sm font-medium">
          Status
          <select value={status} onChange={(event) => setStatus(event.target.value)}
            className="mt-1 block rounded border px-3 py-2">
            <option value="">All statuses</option>
            {STATUSES.map((item) =>
              <option key={item} value={item}>{item.replaceAll("_", " ")}</option>)}
          </select>
        </label>
        <label className="block text-sm font-medium">
          Created from
          <input type="date" value={dateFrom} onChange={(event) => setDateFrom(event.target.value)}
            className="mt-1 block rounded border px-3 py-2" />
        </label>
        <label className="block text-sm font-medium">
          Created to
          <input type="date" value={dateTo} onChange={(event) => setDateTo(event.target.value)}
            className="mt-1 block rounded border px-3 py-2" />
        </label>
        <button disabled={busy} type="submit"
          className="rounded bg-slate-900 px-4 py-2 text-sm text-white disabled:opacity-50">
          {busy ? "Loading…" : "Load work orders"}
        </button>
      </form>
      {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
      {preview && applied && (
        <>
          <div className="flex flex-wrap items-center justify-between gap-3 text-sm">
            <span>{preview.total} recorded work order{preview.total === 1 ? "" : "s"}.</span>
            <ReportActions reportKey="maintenance.work_order" parameters={applied} />
          </div>
          <div className="overflow-x-auto rounded-xl border bg-white">
            <table className="min-w-[1150px] w-full text-sm">
              <thead className="bg-slate-50"><tr>
                {preview.headers.map((header) =>
                  <th key={header} scope="col" className="px-3 py-2 text-left font-semibold">{header}</th>)}
              </tr></thead>
              <tbody>
                {preview.rows.map((row, idx) =>
                  <tr key={idx} className="border-t">
                    {row.map((value, col) =>
                      <td key={col} className="px-3 py-2">{String(value ?? "")}</td>)}
                  </tr>)}
                {preview.total === 0 &&
                  <tr><td colSpan={preview.headers.length} className="p-5 text-center text-slate-500">
                    No recorded work orders match these filters.
                  </td></tr>}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
