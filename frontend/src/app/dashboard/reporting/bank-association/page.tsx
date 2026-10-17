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
type Filter = { bank_id?: string; include_inactive?: boolean };

export default function BankAssociationPage() {
  const [bankId, setBankId] = useState("");
  const [includeInactive, setIncludeInactive] = useState(false);
  const [preview, setPreview] = useState<Preview | null>(null);
  const [applied, setApplied] = useState<Filter | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function load(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setPreview(null);
    setApplied(null);
    const parameters: Filter = {
      ...(bankId.trim() ? { bank_id: bankId.trim() } : {}),
      ...(includeInactive ? { include_inactive: true } : {}),
    };
    try {
      const query = new URLSearchParams();
      for (const [key, value] of Object.entries(parameters)) query.set(key, String(value));
      const data = await apiGet(
        `/api/reporting/bank-association/preview?${query.toString()}`
      ) as Preview;
      setPreview(data);
      setApplied(parameters);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Bank association report unavailable.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-5">
      <Link href="/dashboard/reporting" className="text-sm text-blue-700 hover:underline">← Reports</Link>
      <header>
        <h1 className="text-2xl font-bold text-slate-900">Bank Account Association</h1>
        <p className="mt-1 text-sm text-slate-600">
          Recorded bank account to general ledger account mappings.
          This does not establish property-to-bank associations, clearing, balances,
          or transaction activity. Routing and account numbers are excluded.
        </p>
      </header>
      <form onSubmit={(event) => { void load(event); }}
        className="flex flex-wrap items-end gap-3 rounded-xl border bg-white p-4">
        <label className="block text-sm font-medium">Bank ID (optional)
          <input type="number" min={1} step={1} value={bankId}
            onChange={(event) => setBankId(event.target.value)}
            placeholder="All accessible accounts"
            className="mt-1 block rounded border px-3 py-2" />
        </label>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={includeInactive}
            onChange={(event) => setIncludeInactive(event.target.checked)} />
          Include inactive bank records
        </label>
        <button type="submit" disabled={busy}
          className="rounded bg-slate-900 px-4 py-2 text-sm text-white disabled:opacity-50">
          {busy ? "Loading…" : "Load associations"}
        </button>
      </form>
      {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
      {preview && applied && (
        <>
          <div className="flex flex-wrap items-center justify-between gap-3 text-sm">
            <span>{preview.title} · {preview.total} record{preview.total === 1 ? "" : "s"}</span>
            <ReportActions reportKey="accounting.bank_association" parameters={applied} />
          </div>
          <div className="overflow-x-auto rounded-xl border bg-white">
            <table className="min-w-full divide-y text-left text-sm">
              <thead className="bg-slate-50"><tr>
                {preview.headers.map((header) => (
                  <th scope="col" key={header} className="whitespace-nowrap px-3 py-2 font-medium">{header}</th>
                ))}
              </tr></thead>
              <tbody className="divide-y">
                {preview.rows.map((row, index) => (
                  <tr key={index}>
                    {row.map((cell, j) => (
                      <td key={j} className="whitespace-nowrap px-3 py-2">{String(cell ?? "")}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {preview.total === 0 && <p className="text-sm text-slate-500">No recorded associations match.</p>}
        </>
      )}
    </div>
  );
}
