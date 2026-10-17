"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";

import {
  importBankFeed,
  listBankFeed,
  rematchBankFeed,
  type BankFeedStatus,
  type BankFeedTransaction,
} from "@/lib/bankFeed";
import { getBankAccount, type BankAccount } from "@/lib/bankAccounts";
import { formatDate, formatMoney } from "@/lib/money";
import { useDisplay } from "@/contexts/DisplayContext";

type Filter = "ALL" | BankFeedStatus;

export default function BankFeedPage() {
  const params = useParams<{ id: string }>();
  const bankId = Number(params.id);
  const { prefs } = useDisplay();

  const [bank, setBank] = useState<BankAccount | null>(null);
  const [rows, setRows] = useState<BankFeedTransaction[]>([]);
  const [filter, setFilter] = useState<Filter>("ALL");
  const [loading, setLoading] = useState(true);
  const [working, setWorking] = useState(false);
  const [error, setError] = useState("");
  const [info, setInfo] = useState("");

  const [fileName, setFileName] = useState("");
  const [csvContent, setCsvContent] = useState("");

  async function load() {
    setLoading(true);
    setError("");
    try {
      const [bankRow, feed] = await Promise.all([
        getBankAccount(bankId),
        listBankFeed(bankId),
      ]);
      setBank(bankRow);
      setRows(feed.items);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load bank feed.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, [bankId]);

  const visibleRows = useMemo(
    () => (filter === "ALL" ? rows : rows.filter((row) => row.status === filter)),
    [filter, rows]
  );

  async function chooseFile(file: File | null) {
    setError("");
    setInfo("");
    setFileName("");
    setCsvContent("");
    if (!file) return;
    if (file.size > 5_000_000) {
      setError("CSV file must be 5 MB or smaller.");
      return;
    }
    try {
      const content = await file.text();
      setFileName(file.name);
      setCsvContent(content);
    } catch {
      setError("Could not read the selected CSV file.");
    }
  }

  async function importFile() {
    if (!csvContent) {
      setError("Choose a CSV file first.");
      return;
    }
    setWorking(true);
    setError("");
    setInfo("");
    try {
      const result = await importBankFeed(bankId, csvContent);
      const feed = await listBankFeed(bankId);
      setRows(feed.items);
      setCsvContent("");
      setFileName("");
      setInfo(
        `Imported ${result.imported}; duplicates ignored ${result.duplicates}; matched ${result.matched}.`
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Bank feed import failed.");
    } finally {
      setWorking(false);
    }
  }

  async function rematch() {
    setWorking(true);
    setError("");
    setInfo("");
    try {
      const result = await rematchBankFeed(bankId);
      const feed = await listBankFeed(bankId);
      setRows(feed.items);
      setInfo(
        `Matched ${result.matched}; ${result.remaining_unmatched} remain unmatched.`
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Bank feed rematch failed.");
    } finally {
      setWorking(false);
    }
  }

  if (loading && !bank) {
    return <div className="p-6 text-slate-500">Loading…</div>;
  }

  if (!bank) {
    return (
      <div className="p-6">
        <Link
          href="/dashboard/accounting/bank-accounts"
          className="text-sm text-blue-600 hover:text-blue-800"
        >
          ← Bank Accounts
        </Link>
        <p className="mt-4 text-red-600">{error || "Bank account not found."}</p>
      </div>
    );
  }

  const matchedCount = rows.filter((row) => row.status === "MATCHED").length;
  const unmatchedCount = rows.length - matchedCount;

  return (
    <div
      className="p-6 max-w-7xl"
      data-layout-mode={(prefs?.layout_mode ?? "TABS").toLowerCase()}
      data-density={(prefs?.density ?? "COMFORTABLE").toLowerCase()}
    >
      <div className="mb-4">
        <Link
          href="/dashboard/accounting/bank-accounts"
          className="text-sm text-slate-500 hover:text-slate-800"
        >
          ← Bank Accounts
        </Link>
      </div>

      <div className="flex flex-wrap items-start justify-between gap-4 mb-6">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Bank Feed</h1>
          <p className="text-sm text-slate-500 mt-1">
            {bank.name} · {bank.gl_account_number} {bank.gl_account_name}
          </p>
        </div>
        <button
          type="button"
          onClick={() => void rematch()}
          disabled={working || unmatchedCount === 0}
          className="rounded border border-slate-300 px-3 py-2 text-sm text-slate-700 hover:bg-slate-50 disabled:opacity-50"
        >
          Rematch Unmatched
        </button>
      </div>

      {error && (
        <div className="mb-4 rounded border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
          {error}
        </div>
      )}
      {info && (
        <div className="mb-4 rounded border border-green-200 bg-green-50 px-3 py-2 text-sm text-green-700">
          {info}
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5 mb-6">
        <div className="lg:col-span-2 bg-white border border-slate-200 rounded-xl p-5">
          <h2 className="font-semibold text-slate-900">Import CSV</h2>
          <p className="text-xs text-slate-500 mt-1">
            Required columns: date and amount. Optional columns: payee,
            description, memo, reference, external_id.
          </p>
          <p className="text-xs text-slate-500 mt-1">
            Positive amounts increase the bank balance. Negative amounts decrease it.
            Importing and matching do not create accounting entries.
          </p>

          <div className="mt-4 flex flex-wrap items-center gap-3">
            <label className="rounded border border-slate-300 px-3 py-2 text-sm text-slate-700 hover:bg-slate-50 cursor-pointer">
              Choose CSV
              <input
                type="file"
                accept=".csv,text/csv"
                className="hidden"
                onChange={(event) => void chooseFile(event.target.files?.[0] ?? null)}
              />
            </label>
            <span className="text-sm text-slate-500">
              {fileName || "No file selected"}
            </span>
            <button
              type="button"
              onClick={() => void importFile()}
              disabled={working || !csvContent}
              className="rounded bg-slate-900 px-4 py-2 text-sm text-white hover:bg-slate-700 disabled:opacity-50"
            >
              {working ? "Working…" : "Import"}
            </button>
          </div>
        </div>

        <div className="bg-white border border-slate-200 rounded-xl p-5">
          <h2 className="font-semibold text-slate-900">Feed Status</h2>
          <dl className="mt-3 space-y-2 text-sm">
            <div className="flex justify-between gap-4">
              <dt className="text-slate-500">Total rows</dt>
              <dd className="font-medium text-slate-900">{rows.length}</dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt className="text-slate-500">Matched</dt>
              <dd className="font-medium text-green-700">{matchedCount}</dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt className="text-slate-500">Unmatched</dt>
              <dd className="font-medium text-amber-700">{unmatchedCount}</dd>
            </div>
          </dl>
        </div>
      </div>

      <div className="bg-white border border-slate-200 rounded-xl overflow-hidden">
        <div className="px-4 py-3 border-b border-slate-200 flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="font-semibold text-slate-900">Imported Transactions</h2>
            <p className="text-xs text-slate-500 mt-0.5">
              Exact unique date-and-amount matches are linked automatically.
            </p>
          </div>
          <select
            value={filter}
            onChange={(event) => setFilter(event.target.value as Filter)}
            className="border border-slate-300 rounded px-2 py-1.5 text-sm text-slate-700"
          >
            <option value="ALL">All</option>
            <option value="MATCHED">Matched</option>
            <option value="UNMATCHED">Unmatched</option>
          </select>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-slate-50">
              <tr>
                <th className="text-left px-4 py-2 font-medium text-slate-700">Date</th>
                <th className="text-left px-4 py-2 font-medium text-slate-700">Payee / Description</th>
                <th className="text-left px-4 py-2 font-medium text-slate-700">Reference</th>
                <th className="text-right px-4 py-2 font-medium text-slate-700">Amount</th>
                <th className="text-left px-4 py-2 font-medium text-slate-700">Match</th>
              </tr>
            </thead>
            <tbody>
              {visibleRows.length === 0 && (
                <tr>
                  <td colSpan={5} className="px-4 py-8 text-center text-slate-500">
                    No bank feed rows in this view.
                  </td>
                </tr>
              )}
              {visibleRows.map((row) => (
                <tr key={row.id} className="border-t border-slate-100">
                  <td className="px-4 py-2 whitespace-nowrap">
                    {formatDate(row.posted_date)}
                  </td>
                  <td className="px-4 py-2">
                    <div className="text-slate-800">
                      {row.payee || row.description || "—"}
                    </div>
                    {row.memo && (
                      <div className="text-xs text-slate-500 mt-0.5">{row.memo}</div>
                    )}
                  </td>
                  <td className="px-4 py-2 text-slate-600">
                    {row.reference_number || "—"}
                  </td>
                  <td
                    className={
                      "px-4 py-2 text-right font-medium " +
                      (Number(row.amount) < 0 ? "text-red-700" : "text-green-700")
                    }
                  >
                    {formatMoney(row.amount)}
                  </td>
                  <td className="px-4 py-2">
                    {row.status === "MATCHED" ? (
                      <span className="text-xs text-green-700">
                        {row.matched_source_type} #{row.matched_source_id}
                      </span>
                    ) : (
                      <span className="text-xs text-amber-700">Unmatched</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
