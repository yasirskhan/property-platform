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

export default function VendorDirectoryPage() {
  const [preview, setPreview] = useState<Preview | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function load() {
    setBusy(true); setError(""); setPreview(null);
    try {
      const result = await apiGet("/api/reporting/vendor-directory/preview") as Preview;
      setPreview(result);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Vendor directory unavailable.");
    } finally { setBusy(false); }
  }

  return (
    <div className="space-y-5">
      <Link href="/dashboard/reporting" className="text-sm text-blue-700 hover:underline">← Reports</Link>
      <header>
        <h1 className="text-2xl font-bold text-slate-900">Vendor Directory</h1>
        <p className="mt-1 text-sm text-slate-600">
          Current registered vendor contact accounts only. Free-text bill
          payees and vendor crew are not automatically vendor accounts.
          Mailing addresses, tax identifiers and bank information are
          excluded. Existing user-management role restrictions apply.
        </p>
      </header>
      <button type="button" disabled={busy} onClick={() => void load()}
        className="rounded bg-slate-900 px-4 py-2 text-sm text-white disabled:opacity-50">
        {busy ? "Loading…" : "Load vendor directory"}
      </button>
      {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
      {preview && (
        <>
          <div className="flex flex-wrap items-center justify-between gap-3 text-sm">
            <span>{preview.total} recorded vendor account{preview.total === 1 ? "" : "s"}.</span>
            <ReportActions reportKey="vendor.directory" />
          </div>
          <div className="overflow-x-auto rounded-xl border bg-white">
            <table className="min-w-[680px] w-full text-sm">
              <thead className="bg-slate-50"><tr>
                {preview.headers.map((head) => (
                  <th key={head} scope="col" className="px-3 py-2 text-left font-semibold">{head}</th>
                ))}
              </tr></thead>
              <tbody>
                {preview.rows.map((row, index) => (
                  <tr key={index} className="border-t">
                    {row.map((value, col) => <td key={col} className="px-3 py-2">{String(value)}</td>)}
                  </tr>
                ))}
                {preview.total === 0 && (
                  <tr><td colSpan={preview.headers.length} className="p-5 text-center text-slate-500">
                    No active registered vendor contacts in your organization.
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
