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

export default function DepositRegisterPage() {
  const [depositId, setDepositId] = useState("");
  const [glId, setGlId] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [preview, setPreview] = useState<Preview | null>(null);
  const [applied, setApplied] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function load() {
    setBusy(true); setError(""); setPreview(null);
    const params = new URLSearchParams();
    if (depositId.trim()) params.set("deposit_id", depositId.trim());
    if (glId.trim()) params.set("bank_gl_account_id", glId.trim());
    if (dateFrom) params.set("date_from", dateFrom);
    if (dateTo) params.set("date_to", dateTo);
    try {
      const data = await apiGet(`/api/reporting/deposit-register/preview?${params}`) as Preview;
      setPreview(data);
      setApplied(Object.fromEntries(params.entries()));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Deposit Register unavailable.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-5">
      <Link href="/dashboard/reporting" className="text-sm text-blue-700 hover:underline">← Reports</Link>
      <header>
        <h1 className="text-2xl font-bold text-slate-900">Deposit Register</h1>
        <p className="mt-1 text-sm text-slate-600">
          Recorded groupings of already-posted receipts. A deposit does not
          post new GL cash, prove a bank deposit cleared, or establish a reconciled balance.
          Reversed receipts are flagged. Bank routing and account numbers are excluded.
        </p>
      </header>
      <form onSubmit={(event) => { event.preventDefault(); void load(); }}
        className="flex flex-wrap items-end gap-3">
        <label className="text-sm text-slate-700">Deposit ID
          <input type="number" min={1} step={1} value={depositId}
            onChange={(event) => setDepositId(event.target.value)} placeholder="All deposits"
            className="ml-2 rounded border border-slate-300 px-3 py-2" />
        </label>
        <label className="text-sm text-slate-700">Cash GL account ID
          <input type="number" min={1} step={1} value={glId}
            onChange={(event) => setGlId(event.target.value)} placeholder="All accounts"
            className="ml-2 rounded border border-slate-300 px-3 py-2" />
        </label>
        <label className="text-sm text-slate-700">From
          <input type="date" value={dateFrom} onChange={(event) => setDateFrom(event.target.value)}
            className="ml-2 rounded border border-slate-300 px-3 py-2" />
        </label>
        <label className="text-sm text-slate-700">Through
          <input type="date" value={dateTo} onChange={(event) => setDateTo(event.target.value)}
            className="ml-2 rounded border border-slate-300 px-3 py-2" />
        </label>
        <button type="submit" disabled={busy}
          className="rounded bg-slate-900 px-4 py-2 text-sm text-white disabled:opacity-50">
          {busy ? "Loading…" : "Load Deposit Register"}
        </button>
      </form>
      {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
      {preview && (
        <>
          <div className="flex flex-wrap items-center justify-between gap-3 text-sm">
            <span>{preview.title}</span>
            <ReportActions reportKey="transaction.deposit_register" parameters={applied} />
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
                  <tr key={i}>
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
