"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

import ReportActions from "@/components/reporting/ReportActions";
import { apiGet } from "@/lib/api";
import { formatMoney } from "@/lib/money";

type DetailRow = [
  string, string, string, string, string, number, string,
  number | string, number | string, number | string, string, number | string,
];
type DetailPreview = { title: string; headers: string[]; rows: DetailRow[]; total: number };

export default function SecurityDepositFundsPage() {
  const [propertyId, setPropertyId] = useState("");
  const [asOf, setAsOf] = useState("");
  const [preview, setPreview] = useState<DetailPreview | null>(null);
  const [applied, setApplied] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function load(property: string, through: string) {
    setBusy(true);
    setError("");
    setPreview(null);
    setApplied({});
    const filters = new URLSearchParams();
    if (property.trim()) filters.set("property_id", property.trim());
    if (through.trim()) filters.set("as_of", through.trim());
    try {
      const data = await apiGet(
        `/api/reporting/security-deposits/preview${filters.size ? "?" + filters.toString() : ""}`
      ) as DetailPreview;
      setPreview(data);
      setApplied(Object.fromEntries(filters.entries()));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Cannot load deposit liability detail.");
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => { void load("", ""); }, []);

  const net = preview?.rows.reduce((total, row) => total + Number(row[9]), 0) ?? 0;
  const unallocated = preview?.rows.filter((row) => row[10] !== "Property tagged").length ?? 0;

  return (
    <div className="space-y-5">
      <Link href="/dashboard/reporting" className="text-sm text-blue-700 hover:underline">← Reports</Link>
      <header>
        <h1 className="text-2xl font-bold text-slate-900">Security Deposit Funds Detail</h1>
        <p className="mt-1 text-sm text-slate-600">
          Recorded security-deposit liability GL entries (account 2101 and configured
          owner-held deposit liability accounts). These are liability movements,
          not proof of tenant-level allocation or reconciled cash held in a bank.
          Lease contract deposits are not added to the booked balance.
        </p>
      </header>
      <form onSubmit={(event) => { event.preventDefault(); void load(propertyId, asOf); }}
        className="flex flex-wrap items-end gap-3 rounded-xl border border-slate-200 bg-white p-4">
        <label className="text-sm font-medium text-slate-800">
          Property ID (optional)
          <input type="number" min={1} step={1} value={propertyId}
            onChange={(event) => setPropertyId(event.target.value)}
            placeholder="All accessible properties"
            className="mt-1 block w-64 rounded-lg border border-slate-300 p-2 text-sm" />
        </label>
        <label className="text-sm font-medium text-slate-800">
          Posted through (optional)
          <input type="date" value={asOf}
            onChange={(event) => setAsOf(event.target.value)}
            className="mt-1 block rounded-lg border border-slate-300 p-2 text-sm" />
        </label>
        <button type="submit" disabled={busy}
          className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50">
          {busy ? "Loading…" : "Refresh report"}
        </button>
      </form>
      {error && <p role="alert" className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</p>}
      {preview && (
        <>
          <div className="flex flex-wrap items-center justify-between gap-3 text-sm text-slate-700">
            <p><strong>{preview.total}</strong> GL entries;{" "}
              <strong>{formatMoney(net)}</strong> net liability change in the selected scope.{" "}
              {unallocated > 0 && <span className="text-amber-700">{unallocated} unallocated entries require review.</span>}
            </p>
            <ReportActions reportKey="tenant.security_deposit_funds_detail" parameters={applied} />
          </div>
          <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white">
            <table className="w-full min-w-[1000px] text-sm">
              <thead className="bg-slate-50 text-slate-600"><tr>
                {preview.headers.map((header) => (
                  <th key={header} scope="col" className="whitespace-nowrap px-3 py-2 text-left font-semibold">{header}</th>
                ))}
              </tr></thead>
              <tbody>
                {preview.rows.map((row) => (
                  <tr key={row[5]} className="border-t border-slate-100">
                    {row.map((value, i) => (
                      <td key={i} className="whitespace-nowrap px-3 py-2">
                        {i >= 7 && i <= 9 ? formatMoney(value) : String(value)}
                      </td>
                    ))}
                  </tr>
                ))}
                {preview.rows.length === 0 && (
                  <tr><td colSpan={preview.headers.length} className="p-6 text-center text-slate-500">
                    No posted deposit-liability entries in the selected scope.
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
