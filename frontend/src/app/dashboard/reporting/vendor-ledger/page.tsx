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
type Filter = { vendor_id?: string; date_from?: string; date_to?: string };

export default function VendorLedgerPage() {
  const [vendorId, setVendorId] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [applied, setApplied] = useState<Filter | null>(null);
  const [preview, setPreview] = useState<Preview | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function load(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true); setError(""); setPreview(null); setApplied(null);
    const filters: Filter = {
      ...(vendorId.trim() ? { vendor_id: vendorId.trim() } : {}),
      ...(dateFrom ? { date_from: dateFrom } : {}),
      ...(dateTo ? { date_to: dateTo } : {}),
    };
    try {
      const query = new URLSearchParams(filters);
      const data = await apiGet(`/api/reporting/vendor-ledger/preview?${query.toString()}`) as Preview;
      setPreview(data); setApplied(filters);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Vendor payable report unavailable.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-5">
      <Link href="/dashboard/reporting" className="text-sm text-blue-700 hover:underline">← Reports</Link>
      <header>
        <h1 className="text-2xl font-bold text-slate-900">Vendor Ledger</h1>
        <p className="mt-1 text-sm text-slate-600">
          Recorded bills explicitly linked to active registered vendor accounts.
          Shows bill amount, recorded payments, and unpaid amount. Unlinked free-text
          payees, reversed or void bills and deleted records are excluded.
          This is a payable-bill register, not a complete GL cash history or tax register.
        </p>
      </header>
      <form onSubmit={(event) => { void load(event); }}
        className="flex flex-wrap items-end gap-3 rounded-xl border bg-white p-4">
        <label className="block text-sm font-medium">
          Vendor user ID (optional)
          <input type="number" min={1} step={1} value={vendorId}
            onChange={(event) => setVendorId(event.target.value)}
            className="mt-1 block rounded border px-3 py-2" />
        </label>
        <label className="block text-sm font-medium">
          Bill date from
          <input type="date" value={dateFrom} onChange={(event) => setDateFrom(event.target.value)}
            className="mt-1 block rounded border px-3 py-2" />
        </label>
        <label className="block text-sm font-medium">
          Bill date to
          <input type="date" value={dateTo} onChange={(event) => setDateTo(event.target.value)}
            className="mt-1 block rounded border px-3 py-2" />
        </label>
        <button disabled={busy} type="submit"
          className="rounded bg-slate-900 px-4 py-2 text-sm text-white disabled:opacity-50">
          {busy ? "Loading…" : "Load recorded vendor bills"}
        </button>
      </form>
      {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
      {preview && applied && (
        <>
          <div className="flex flex-wrap items-center justify-between gap-3 text-sm">
            <span>{preview.total} recorded bill{preview.total === 1 ? "" : "s"}.</span>
            <ReportActions reportKey="vendor.ledger" parameters={applied} />
          </div>
          <div className="overflow-x-auto rounded-xl border bg-white">
            <table className="min-w-[1000px] w-full text-sm">
              <thead className="bg-slate-50">
                <tr>{preview.headers.map((header) =>
                  <th key={header} scope="col" className="px-3 py-2 text-left font-semibold">{header}</th>)}</tr>
              </thead>
              <tbody>
                {preview.rows.map((row, idx) =>
                  <tr key={idx} className="border-t">
                    {row.map((value, col) => <td key={col} className="px-3 py-2">{String(value)}</td>)}
                  </tr>)}
                {preview.total === 0 &&
                  <tr><td colSpan={preview.headers.length} className="p-5 text-center text-slate-500">
                    No linked vendor bills match these filters.
                  </td></tr>}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
