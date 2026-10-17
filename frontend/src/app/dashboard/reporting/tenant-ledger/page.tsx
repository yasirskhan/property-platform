"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

import { apiGet } from "@/lib/api";
import { formatMoney } from "@/lib/money";
import ReportActions from "@/components/reporting/ReportActions";

type LedgerRow = [
  string, string, string, string, string, number, string,
  string | number, string | number, string | number,
  number, number | string,
];
type LedgerPreview = { title: string; headers: string[]; rows: LedgerRow[]; total: number };

export default function TenantLedgerPage() {
  const [tenantId, setTenantId] = useState("");
  const [propertyId, setPropertyId] = useState("");
  const [applied, setApplied] = useState<Record<string, string>>({});
  const [preview, setPreview] = useState<LedgerPreview | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function load(tenant: string, property: string) {
    setBusy(true);
    setError("");
    setPreview(null);
    setApplied({});
    const params = new URLSearchParams();
    if (tenant.trim()) params.set("tenant_id", tenant.trim());
    if (property.trim()) params.set("property_id", property.trim());
    try {
      const data = await apiGet(
        `/api/reporting/tenant-ledger/preview${params.size ? "?" + params.toString() : ""}`,
      ) as LedgerPreview;
      setPreview(data);
      setApplied(Object.fromEntries(params.entries()));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Cannot load tenant balance schedule.");
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => { void load("", ""); }, []);
  const net = preview?.rows.reduce((sum, row) => sum + Number(row[9]), 0) ?? 0;

  return (
    <div className="space-y-5">
      <Link href="/dashboard/reporting" className="text-sm text-blue-700 hover:underline">← Reports</Link>
      <header>
        <h1 className="text-2xl font-bold text-slate-900">Tenant Ledger</h1>
        <p className="mt-1 text-sm text-slate-600">
          Current recorded rent-invoice and standalone-charge balances.
          Rent includes recorded late fees; void invoices and deleted
          charges are excluded.
        </p>
      </header>
      <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-950">
        This is a current balance schedule, not a historical posted transaction
        ledger. Legacy invoice payments, accounting receipts and GL records
        are independent sources; recorded paid totals are shown ONCE, rather
        than double-counting those sources. Charge paid amounts have no
        dated payment history here. Dates are document/due dates, not a
        reconstructed transaction chronology.
      </div>
      <form onSubmit={(e) => { e.preventDefault(); void load(tenantId, propertyId); }}
        className="flex flex-wrap items-end gap-3 rounded-xl border border-slate-200 bg-white p-4">
        <label className="block text-sm font-medium text-slate-800">
          Tenant ID (optional)
          <input type="number" min={1} step={1} value={tenantId}
            onChange={(e) => setTenantId(e.target.value)}
            className="mt-1 block w-52 rounded-lg border border-slate-300 p-2 text-sm" />
        </label>
        <label className="block text-sm font-medium text-slate-800">
          Property ID (optional)
          <input type="number" min={1} step={1} value={propertyId}
            onChange={(e) => setPropertyId(e.target.value)}
            className="mt-1 block w-52 rounded-lg border border-slate-300 p-2 text-sm" />
        </label>
        <button type="submit" disabled={busy}
          className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50">
          {busy ? "Loading…" : "Refresh ledger"}
        </button>
      </form>
      {error && <p role="alert" className="rounded border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</p>}
      {preview && (
        <>
          <div className="flex flex-wrap items-center justify-between gap-3 text-sm">
            <p><strong>{preview.total}</strong> current balance row(s);{" "}
              <strong>{formatMoney(net)}</strong> net outstanding (negative indicates recorded overpayment).
            </p>
            <ReportActions reportKey="tenant.ledger" parameters={applied} />
          </div>
          <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white">
            <table className="w-full min-w-[1150px] text-sm">
              <thead className="bg-slate-50 text-slate-700">
                <tr>{preview.headers.map((header) => (
                  <th scope="col" key={header} className="px-3 py-2 text-left font-semibold">{header}</th>
                ))}</tr>
              </thead>
              <tbody>
                {preview.rows.map((row, i) => (
                  <tr key={i} className="border-t border-slate-100">
                    {row.map((cell, j) => (
                      <td key={j} className="whitespace-nowrap px-3 py-2">
                        {j >= 7 && j <= 9 ? formatMoney(cell) : String(cell)}
                      </td>
                    ))}
                  </tr>
                ))}
                {preview.rows.length === 0 && (
                  <tr><td colSpan={preview.headers.length} className="p-6 text-center text-slate-500">
                    No tenant invoice or standalone charge balances in this scope.
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
