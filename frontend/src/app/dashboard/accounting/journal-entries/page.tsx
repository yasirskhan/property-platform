// ============================================================
// Journal Entries list page
// ------------------------------------------------------------
// Route: /dashboard/accounting/journal-entries
//
// Lists every manual JE (transaction_type = JOURNAL_ENTRY) in
// the org. Filters by date. + New Journal Entry button goes
// to the creation form.
// ============================================================

"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  listJournalEntries,
  JournalEntry,
  JournalEntryList,
} from "@/lib/journalEntries";
import { apiGet } from "@/lib/api";
import { formatDate } from "@/lib/money";
import Flag from "@/components/features/Flag";
import { useDisplay } from "@/contexts/DisplayContext";

type Me = { role: string };

const WRITE_ROLES = ["ADMIN", "OWNER", "MANAGER"];

export default function JournalEntriesPage() {
  const { prefs } = useDisplay();
  const [me, setMe] = useState<Me | null>(null);
  const [data, setData] = useState<JournalEntryList | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [includeReversed, setIncludeReversed] = useState(true);

  async function load() {
    setLoading(true);
    setError("");
    try {
      const meData = await apiGet("/auth/me");
      setMe(meData);
      const list = await listJournalEntries({
        date_from: dateFrom || undefined,
        date_to: dateTo || undefined,
        include_reversed: includeReversed,
      });
      setData(list);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Load failed");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dateFrom, dateTo, includeReversed]);

  if (loading && !data) return <div className="text-slate-500">Loading…</div>;
  if (error) return <div className="text-red-600">{error}</div>;
  if (!data) return null;

  const canWrite = me ? WRITE_ROLES.includes(me.role) : false;

  return (
    <div>
      {/* Back link */}
      <div className="mb-4">
        <Link
          href="/dashboard"
          className="text-sm text-slate-500 hover:text-slate-800"
        >
          ← Back to Dashboard
        </Link>
      </div>

      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">
            Journal Entries
          </h1>
          <p className="text-slate-500 mt-1">
            {data.total} {data.total === 1 ? "entry" : "entries"}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <Flag name="release.accounting.journal_entries.recurring">
            <button type="button" disabled className="text-sm px-3 py-2 border border-slate-300 rounded-lg text-slate-500 disabled:opacity-60">Recurring Journal Entries</button>
          </Flag>
          <Flag name="release.accounting.journal_entries.post_gpr">
            <button type="button" disabled className="text-sm px-3 py-2 border border-slate-300 rounded-lg text-slate-500 disabled:opacity-60">Post GPR</button>
          </Flag>
          <Link
            href="/dashboard/accounting/gl-accounts"
            className="text-sm px-3 py-2 text-slate-600 hover:text-slate-900"
          >
            Chart of Accounts
          </Link>
          <Link
            href="/dashboard/accounting/trial-balance"
            className="text-sm px-3 py-2 text-slate-600 hover:text-slate-900"
          >
            Trial Balance
          </Link>
          {canWrite && (
            <Link
              href="/dashboard/accounting/journal-entries/new"
              className="text-sm px-4 py-2 bg-slate-900 text-white rounded-lg hover:bg-slate-700"
            >
              + New Journal Entry
            </Link>
          )}
        </div>
      </div>

      {/* Filters */}
      <div className="bg-white border border-slate-200 rounded-xl p-4 mb-6 flex flex-wrap items-end gap-4">
        <div>
          <label className="block text-xs text-slate-500 mb-1">
            Date from
          </label>
          <input
            type="date"
            value={dateFrom}
            onChange={(e) => setDateFrom(e.target.value)}
            className="border border-slate-300 rounded px-2 py-1.5 text-sm"
          />
        </div>
        <div>
          <label className="block text-xs text-slate-500 mb-1">Date to</label>
          <input
            type="date"
            value={dateTo}
            onChange={(e) => setDateTo(e.target.value)}
            className="border border-slate-300 rounded px-2 py-1.5 text-sm"
          />
        </div>
        <label className="flex items-center gap-2 text-sm text-slate-600 pb-1.5">
          <input
            type="checkbox"
            checked={includeReversed}
            onChange={(e) => setIncludeReversed(e.target.checked)}
          />
          Show reversed
        </label>
      </div>

      {/* Table */}
      <div className="bg-white border border-slate-200 rounded-xl overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-slate-50">
            <tr>
              <th className="text-left px-4 py-2 font-medium text-slate-700 w-24">
                ID
              </th>
              <th className="text-left px-4 py-2 font-medium text-slate-700 w-28">
                Date
              </th>
              <th className="text-left px-4 py-2 font-medium text-slate-700 w-28">
                Reference
              </th>
              <th className="text-left px-4 py-2 font-medium text-slate-700">
                Memo
              </th>
              <th className="text-left px-4 py-2 font-medium text-slate-700 w-28">
                Source
              </th>
            </tr>
          </thead>
          <tbody>
            {data.items.length === 0 && (
              <tr>
                <td
                  colSpan={5}
                  className="px-4 py-8 text-center text-slate-500"
                >
                  No journal entries yet.
                </td>
              </tr>
            )}
            {data.items.map((je) => (
              <tr
                key={je.id}
                className={`border-t border-slate-100 hover:bg-slate-50 ${
                  je.is_reversed ? "opacity-60" : ""
                }`}
              >
                <td className="px-4 py-2 text-slate-500 font-mono">
                  #{je.id}
                </td>
                <td className="px-4 py-2 text-slate-700">
                  {formatDate(je.transaction_date)}
                </td>
                <td className="px-4 py-2 text-slate-600 text-xs font-mono">
                  {je.reference_number || "—"}
                </td>
                <td
                  className={`px-4 py-2 ${
                    je.is_reversed
                      ? "line-through text-slate-400"
                      : "text-slate-800"
                  }`}
                >
                  <Link
                    href={`/dashboard/accounting/journal-entries/${je.id}`}
                    className="text-blue-600 hover:underline"
                  >
                    {je.memo || "(no memo)"}
                  </Link>
                  {je.is_reversed && (
                    <span className="ml-2 text-xs text-red-600">
                      reversed
                    </span>
                  )}
                </td>
                <td className="px-4 py-2 text-slate-500 text-xs">
                  {je.source_type || "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}