"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

import ReportActions from "@/components/reporting/ReportActions";
import { apiGet } from "@/lib/api";
import { formatMoney } from "@/lib/money";

type DelinquencyRow = [
  string, string, string, number, string, number,
  number | string, number | string, number | string, number | string, number
];
type DelinquencyPreview = {
  title: string;
  headers: string[];
  rows: DelinquencyRow[];
  total: number;
};

export default function TenantDelinquencyPage() {
  const [propertyId, setPropertyId] = useState("");
  const [appliedPropertyId, setAppliedPropertyId] = useState("");
  const [preview, setPreview] = useState<DelinquencyPreview | null>(null);
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
      const data = await apiGet(`/api/reporting/delinquency/preview${suffix}`) as DelinquencyPreview;
      setPreview(data);
      setAppliedPropertyId(nextPropertyId.trim());
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Cannot load overdue rent invoices.");
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => { void load(""); }, []);

  const outstandingTotal = preview?.rows.reduce(
    (sum, row) => sum + Number(row[9]), 0,
  ) ?? 0;

  return (
    <div className="space-y-5">
      <Link href="/dashboard/reporting" className="text-sm text-blue-700 hover:underline">
        ← Reports
      </Link>
      <header>
        <h1 className="text-2xl font-bold text-slate-900">Tenant Delinquency</h1>
        <p className="mt-1 text-sm text-slate-600">
          Current overdue rent invoices. Amounts use recorded rent, late fees
          and payments; separate tenant charges are not included. This is not a historical
          accounts-receivable snapshot.
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
          {busy ? "Loading…" : "Refresh report"}
        </button>
      </form>
      {error && <p role="alert" className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</p>}
      {preview && (
        <>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <p className="text-sm text-slate-700">
              <strong>{preview.total}</strong> overdue invoice(s),{" "}
              <strong>{formatMoney(outstandingTotal)}</strong> outstanding.
            </p>
            <ReportActions reportKey="tenant.delinquency"
              parameters={appliedPropertyId ? { property_id: appliedPropertyId } : {}} />
          </div>
          <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white">
            <table className="w-full min-w-[900px] text-sm">
              <thead className="bg-slate-50 text-slate-600">
                <tr>
                  {preview.headers.map((header) => (
                    <th key={header} scope="col" className="px-3 py-2 text-left font-semibold">
                      {header}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {preview.rows.map((row) => (
                  <tr key={row[3]} className="border-t border-slate-100">
                    {row.map((value, index) => (
                      <td key={index} className="whitespace-nowrap px-3 py-2">
                        {index >= 6 && index <= 9 ? formatMoney(value) : String(value)}
                      </td>
                    ))}
                  </tr>
                ))}
                {preview.rows.length === 0 && (
                  <tr><td colSpan={preview.headers.length}
                    className="p-6 text-center text-slate-500">No overdue rent invoices in the current scope.</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
