"use client";

import { useState } from "react";
import Link from "next/link";
import ReportActions from "@/components/reporting/ReportActions";
import { apiGet } from "@/lib/api";

type Preview = { title: string; headers: string[]; rows: (string | number)[][]; total: number };

export default function BillDetailPage() {
  const [preview, setPreview] = useState<Preview | null>(null);
  const [billId, setBillId] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [applied, setApplied] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function load() {
    setBusy(true); setError(""); setPreview(null);
    const params = new URLSearchParams();
    if (billId.trim()) params.set("bill_id", billId.trim());
    if (dateFrom) params.set("date_from", dateFrom);
    if (dateTo) params.set("date_to", dateTo);
    try {
      const data = await apiGet(`/api/reporting/bill-detail/preview?${params}`) as Preview;
      setPreview(data);
      setApplied(Object.fromEntries(params.entries()));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Bill Detail unavailable.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-5">
      <Link href="/dashboard/reporting" className="text-sm text-blue-700 hover:underline">← Reports</Link>
      <header>
        <h1 className="text-2xl font-bold text-slate-900">Bill Detail</h1>
        <p className="mt-1 text-sm text-slate-600">
          Recorded posted bill headers and their verified GL-account lines.
          Parent amounts appear once per bill, never on each line.
          Payment amounts are current recorded metadata, not historical or cleared check activity.
          Reversed, void, deleted and unposted bills are excluded.
        </p>
      </header>
      <form onSubmit={(event) => { event.preventDefault(); void load(); }}
        className="flex flex-wrap items-end gap-3">
        <label className="text-sm text-slate-700">Bill ID
          <input type="number" min={1} step={1} value={billId}
            onChange={(event) => setBillId(event.target.value)}
            placeholder="All posted bills"
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
          {busy ? "Loading…" : "Load Bill Detail"}
        </button>
      </form>
      {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
      {preview && (
        <>
          <div className="flex flex-wrap items-center justify-between gap-3 text-sm">
            <span>{preview.title}</span>
            <ReportActions reportKey="transaction.bill_detail" parameters={applied} />
          </div>
          {preview.total === 0 ? <p className="text-sm text-slate-500">No matching posted bills.</p> : (
            <div className="overflow-x-auto rounded-xl border bg-white">
              <table className="min-w-full divide-y text-left text-sm">
                <thead className="bg-slate-50"><tr>
                  {preview.headers.map((header) => (
                    <th key={header} scope="col" className="whitespace-nowrap px-3 py-2 font-medium">{header}</th>
                  ))}
                </tr></thead>
                <tbody className="divide-y">
                  {preview.rows.map((row, i) => (
                    <tr key={i} className={row[0] === "BILL" ? "bg-slate-50 font-semibold" : ""}>
                      {row.map((value, j) => (
                        <td key={j} className="whitespace-nowrap px-3 py-2">{String(value ?? "")}</td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </div>
  );
}
