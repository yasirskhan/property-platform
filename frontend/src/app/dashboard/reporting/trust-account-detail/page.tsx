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
type Filters = { bank_id: string; date_from: string; date_to: string };

export default function TrustAccountDetailPage() {
  const [bankId, setBankId] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [preview, setPreview] = useState<Preview | null>(null);
  const [applied, setApplied] = useState<Filters | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function load(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true); setError(""); setPreview(null); setApplied(null);
    const filters: Filters = {
      bank_id: bankId, date_from: dateFrom, date_to: dateTo,
    };
    try {
      const query = new URLSearchParams(filters);
      const data = await apiGet(
        `/api/reporting/trust-account-detail/preview?${query.toString()}`
      ) as Preview;
      setPreview(data); setApplied(filters);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Trust detail unavailable.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-5">
      <Link href="/dashboard/reporting" className="text-sm text-blue-700 hover:underline">← Reports</Link>
      <header>
        <h1 className="text-2xl font-bold text-slate-900">Trust Account Detail</h1>
        <p className="mt-1 text-sm text-slate-600">
          Actual dated posted trust bank GL entries, opening and running book cash,
          and recorded owner/property tag IDs only when in your organization.
          Tags are not proof of beneficial ownership, bank settlement or
          three-way reconciliation. No external bank statement balance is shown.
        </p>
      </header>
      <form onSubmit={(event) => { void load(event); }}
        className="flex flex-wrap items-end gap-3 rounded-xl border bg-white p-4">
        <label className="block text-sm font-medium">Configured bank ID
          <input required min={1} step={1} type="number" value={bankId}
            onChange={(event) => setBankId(event.target.value)}
            className="mt-1 block w-48 rounded border px-3 py-2" />
        </label>
        <label className="block text-sm font-medium">Posted date from
          <input required type="date" value={dateFrom}
            onChange={(event) => setDateFrom(event.target.value)}
            className="mt-1 block rounded border px-3 py-2" />
        </label>
        <label className="block text-sm font-medium">Posted date to
          <input required type="date" value={dateTo}
            onChange={(event) => setDateTo(event.target.value)}
            className="mt-1 block rounded border px-3 py-2" />
        </label>
        <button type="submit" disabled={busy}
          className="rounded bg-slate-900 px-4 py-2 text-sm text-white disabled:opacity-50">
          {busy ? "Loading…" : "Load trust detail"}
        </button>
      </form>
      {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
      {preview && applied && (
        <>
          <div className="flex flex-wrap items-center justify-between gap-3 text-sm">
            <span>{preview.title}</span>
            <ReportActions reportKey="accounting.trust_account_detail" parameters={applied} />
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
                  <tr key={i} className={row[0] === "OPENING" || row[0] === "CLOSING" ? "bg-slate-50 font-semibold" : ""}>
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
