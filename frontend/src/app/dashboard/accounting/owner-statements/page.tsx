// ============================================================
// Owner Statements list page
// ------------------------------------------------------------
// Frozen snapshot documents. List + drill to detail.
//
// Uses formatMoney() / formatDate() from lib/money.ts so the
// org's currency / date settings are respected (Section 59).
// ============================================================

"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { formatMoney, formatDate } from "@/lib/money";
import { apiGet } from "@/lib/api";
import Flag from "@/components/features/Flag";
import { useDisplay } from "@/contexts/DisplayContext";
import {
  listOwnerStatements,
  type OwnerStatement,
  type OwnerStatementList,
} from "@/lib/ownerStatements";

interface Me {
  id: number;
  role: string;
}

const WRITE_ROLES = ["ADMIN", "OWNER", "MANAGER"];

export default function OwnerStatementsPage() {
  const { prefs } = useDisplay();
  const [me, setMe] = useState<Me | null>(null);
  const [statements, setStatements] = useState<OwnerStatement[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");

  useEffect(() => {
    apiGet("/auth/me").then((u) => setMe(u as Me)).catch(() => setMe(null));
  }, []);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const data: OwnerStatementList = await listOwnerStatements({
        date_from: dateFrom || undefined,
        date_to: dateTo || undefined,
      });
      setStatements(data.items);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Could not load statements.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const canWrite = Boolean(
    me && WRITE_ROLES.includes(String(me.role).toUpperCase())
  );

  return (
    <div
      className="p-6"
      data-layout-mode={(prefs?.layout_mode ?? "TABS").toLowerCase()}
      data-density={(prefs?.density ?? "COMFORTABLE").toLowerCase()}
    >
      <div className="flex items-center justify-between mb-1">
        <h1 className="text-xl font-semibold text-slate-900">
          Owner Statements
        </h1>
<div className="flex flex-wrap justify-end gap-2">
          <Flag name="release.accounting.owner_statements.cash_summary">
            <button type="button" disabled className="px-3 py-1.5 rounded-md border border-slate-300 text-slate-500 text-sm disabled:opacity-60">Property Cash Summary</button>
          </Flag>
          <Flag name="release.owner_portal.packet_customizer">
            <button type="button" disabled className="px-3 py-1.5 rounded-md border border-slate-300 text-slate-500 text-sm disabled:opacity-60">Owner Packet</button>
          </Flag>
          <Flag name="release.owner_statements.email">
            <button type="button" disabled className="px-3 py-1.5 rounded-md border border-slate-300 text-slate-500 text-sm disabled:opacity-60">Email Statement</button>
          </Flag>
          {canWrite && (
            <Link
              href="/dashboard/accounting/owner-statements/new"
              className="px-3 py-1.5 rounded-md bg-blue-600 text-white text-sm font-medium hover:bg-blue-700"
            >
              + New Statement
            </Link>
          )}
        </div>
      </div>
      <p className="text-sm text-slate-500 mb-6">
        Frozen snapshot documents. Once generated, they never change.
      </p>

      <div className="bg-white border border-slate-200 rounded-lg p-4 mb-5 flex flex-wrap items-end gap-3">
        <div>
          <label className="block text-xs text-slate-600 mb-1">From</label>
          <input
            type="date"
            value={dateFrom}
            onChange={(e) => setDateFrom(e.target.value)}
            className="border border-slate-300 rounded-md px-2 py-1.5 text-sm"
          />
        </div>
        <div>
          <label className="block text-xs text-slate-600 mb-1">To</label>
          <input
            type="date"
            value={dateTo}
            onChange={(e) => setDateTo(e.target.value)}
            className="border border-slate-300 rounded-md px-2 py-1.5 text-sm"
          />
        </div>
        <button
          type="button"
          onClick={load}
          className="px-3 py-1.5 rounded-md bg-slate-700 text-white text-sm font-medium hover:bg-slate-800"
        >
          Show
        </button>
      </div>

      {error && (
        <div className="text-sm text-red-600 mb-3 bg-red-50 border border-red-200 rounded-md px-3 py-2">
          {error}
        </div>
      )}

      <div className="bg-white rounded-lg border border-slate-200 overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-slate-600">
            <tr>
              <th className="text-left px-4 py-2 font-medium">Owner</th>
              <th className="text-left px-4 py-2 font-medium">Period</th>
              <th className="text-left px-4 py-2 font-medium">Generated</th>
              <th className="text-right px-4 py-2 font-medium">Income</th>
              <th className="text-right px-4 py-2 font-medium">Expense</th>
              <th className="text-right px-4 py-2 font-medium">Net</th>
            </tr>
          </thead>
          <tbody>
            {loading && (
              <tr>
                <td colSpan={6} className="px-4 py-6 text-center text-slate-500">
                  Loading...
                </td>
              </tr>
            )}
            {!loading && statements.length === 0 && (
              <tr>
                <td colSpan={6} className="px-4 py-6 text-center text-slate-500">
                  No statements yet.
                </td>
              </tr>
            )}
            {statements.map((s) => (
              <tr
                key={s.id}
                className="border-t border-slate-100 hover:bg-slate-50"
              >
                <td className="px-4 py-2">
                  <Link
                    href={`/dashboard/accounting/owner-statements/${s.id}`}
                    className="text-blue-600 hover:underline"
                  >
                    {s.owner_name || s.owner_email || `Owner #${s.owner_id}`}
                  </Link>
                </td>
                <td className="px-4 py-2 text-slate-500 text-xs">
                  {formatDate(s.period_start)} → {formatDate(s.period_end)}
                </td>
                <td className="px-4 py-2 text-slate-500 text-xs">
                  {s.generated_at ? formatDate(s.generated_at) : "—"}
                </td>
                <td className="px-4 py-2 text-right font-mono">
                  {formatMoney(s.total_income)}
                </td>
                <td className="px-4 py-2 text-right font-mono">
                  {formatMoney(s.total_expense)}
                </td>
                <td className="px-4 py-2 text-right font-mono font-semibold">
                  {formatMoney(s.total_net)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}