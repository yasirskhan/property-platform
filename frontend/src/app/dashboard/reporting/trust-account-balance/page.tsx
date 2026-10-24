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
type Filters = { as_of: string; bank_id?: string };

export default function TrustAccountBalancePage() {
  const [asOf, setAsOf] = useState("");
  const [bankId, setBankId] = useState("");
  const [preview, setPreview] = useState<Preview | null>(null);
  const [applied, setApplied] = useState<Filters | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function load(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true); setError(""); setPreview(null); setApplied(null);
    const filters: Filters = {
      as_of: asOf, ...(bankId.trim() ? { bank_id: bankId.trim() } : {}),
    };
    try {
      const query = new URLSearchParams(filters);
      const data = await apiGet(
        `/api/reporting/trust-account-balance/preview?${query.toString()}`
      ) as Preview;
      setPreview(data); setApplied(filters);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Trust account balance unavailable.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-5">
      <Link href="/dashboard/reporting" className="text-sm text-blue-700 hover:underline">← Reports</Link>
      <header>
        <h1 className="text-2xl font-bold text-slate-900">Trust Account Balance</h1>
        <p className="mt-1 text-sm text-slate-600">
          Dated posted cash-book balances on explicitly configured bank-to-GL mappings,
          including archived historical accounts. This is not a cleared external bank
          statement, owner or tenant liability total, or verified three-way reconciliation.
        </p>
      </header>
      <form onSubmit={(event) => { void load(event); }}
        className="flex flex-wrap items-end gap-3 rounded-xl border bg-white p-4">
        <label className="block text-sm font-medium">Book balance as of
          <input required type="date" value={asOf}
            onChange={(event) => setAsOf(event.target.value)}
            className="mt-1 block rounded border px-3 py-2" />
        </label>
        <label className="block text-sm font-medium">Bank ID (optional)
          <input min={1} step={1} type="number" value={bankId}
            placeholder="All configured accounts"
            onChange={(event) => setBankId(event.target.value)}
            className="mt-1 block w-56 rounded border px-3 py-2" />
        </label>
        <button type="submit" disabled={busy}
          className="rounded bg-slate-900 px-4 py-2 text-sm text-white disabled:opacity-50">
          {busy ? "Loading…" : "Load trust book balance"}
        </button>
      </form>
      {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
      {preview && applied && (
        <>
          <div className="flex flex-wrap items-center justify-between gap-3 text-sm">
            <span>{preview.title}</span>
            <ReportActions reportKey="accounting.trust_account_balance" parameters={applied} />
          </div>
          <div className="overflow-x-auto rounded-xl border bg-white">
            <table className="min-w-full divide-y text-left text-sm">
              <thead className="bg-slate-50"><tr>
                {preview.headers.map((header) => (
                  <th key={header} scope="col" className="whitespace-nowrap px-3 py-2 font-medium">{header}</th>
                ))}
              </tr></thead>
              <tbody className="divide-y">
                {preview.rows.map((row, i) => (
                  <tr key={i} className={row[0] === "TOTAL" ? "bg-slate-50 font-semibold" : ""}>
                    {row.map((value, j) => (
                      <td key={j} className="whitespace-nowrap px-3 py-2">{String(value ?? "")}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
