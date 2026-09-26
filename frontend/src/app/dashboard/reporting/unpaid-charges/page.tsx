"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

import ReportActions from "@/components/reporting/ReportActions";
import { apiGet } from "@/lib/api";

type Row = [
  string, string, string, string, number, string, string, string, string,
  number, number | string,
];
type Preview = { title: string; headers: string[]; rows: Row[]; total: number };

export default function UnpaidChargesPage() {
  const [propertyId, setPropertyId] = useState("");
  const [tenantId, setTenantId] = useState("");
  const [applied, setApplied] = useState<Record<string, string>>({});
  const [preview, setPreview] = useState<Preview | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function load(property: string, tenant: string) {
    setBusy(true);
    setError("");
    setPreview(null);
    setApplied({});
    const filters: Record<string, string> = {};
    if (property.trim()) filters.property_id = property.trim();
    if (tenant.trim()) filters.tenant_id = tenant.trim();
    const qs = new URLSearchParams(filters).toString();
    try {
      const data = await apiGet(`/api/reporting/unpaid-charges/preview${qs ? `?${qs}` : ""}`) as Preview;
      setPreview(data);
      setApplied(filters);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to load unpaid charges.");
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => { void load("", ""); }, []);

  return (
    <div className="space-y-5">
      <Link href="/dashboard/reporting" className="text-sm text-blue-700 hover:underline">← Reports</Link>
      <header>
        <h1 className="text-2xl font-bold text-slate-900">Tenant Unpaid Charges</h1>
        <p className="mt-1 text-sm text-slate-600">
          Current positive balances for separately recorded tenant Charges.
          Rent invoices and invoice late fees are not included.
          Amounts reflect current recorded payments, not a historical ledger or bank reconciliation.
          Organization administrators may see explicitly unallocated charges.
        </p>
      </header>
      <form onSubmit={(event) => { event.preventDefault(); void load(propertyId, tenantId); }}
        className="flex flex-wrap items-end gap-3 rounded-xl border border-slate-200 bg-white p-4">
        <label className="text-sm font-medium text-slate-800">
          Property ID (optional)
          <input type="number" min={1} step={1} value={propertyId}
            onChange={(event) => setPropertyId(event.target.value)}
            className="mt-1 block w-56 rounded-lg border border-slate-300 p-2 text-sm" />
        </label>
        <label className="text-sm font-medium text-slate-800">
          Tenant ID (optional)
          <input type="number" min={1} step={1} value={tenantId}
            onChange={(event) => setTenantId(event.target.value)}
            className="mt-1 block w-56 rounded-lg border border-slate-300 p-2 text-sm" />
        </label>
        <button disabled={busy} type="submit"
          className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50">
          {busy ? "Loading…" : "Refresh charges"}
        </button>
      </form>
      {error && <p role="alert" className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</p>}
      {preview && (
        <>
          <div className="flex flex-wrap items-center justify-between gap-3 text-sm">
            <span><strong>{preview.total}</strong> outstanding standalone charges.</span>
            <ReportActions reportKey="tenant.unpaid_charges" parameters={applied} />
          </div>
          <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white">
            <table className="min-w-[1100px] w-full text-sm">
              <thead className="bg-slate-50">
                <tr>{preview.headers.map((header) => (
                  <th key={header} className="px-3 py-2 text-left font-semibold text-slate-700">{header}</th>
                ))}</tr>
              </thead>
              <tbody>
                {preview.rows.map((row) => (
                  <tr key={row[4]} className="border-t border-slate-100">
                    {row.map((value, i) => <td key={i} className="whitespace-nowrap px-3 py-2">{String(value)}</td>)}
                  </tr>
                ))}
                {preview.rows.length === 0 && (
                  <tr><td colSpan={preview.headers.length} className="p-6 text-center text-slate-500">
                    No positive outstanding standalone charges in this scope.
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
