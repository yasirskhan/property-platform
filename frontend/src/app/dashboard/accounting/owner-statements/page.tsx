// ============================================================
// Owner Statements list page
// ------------------------------------------------------------
// Route: /dashboard/accounting/owner-statements
//
// Lists generated statements. Click a row → view the frozen
// snapshot in a centered modal, with a link to the printable
// detail page.
// ============================================================

"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  listOwnerStatements,
  OwnerStatement,
  OwnerStatementList,
} from "@/lib/ownerStatements";
import { apiGet } from "@/lib/api";

type Me = { role: string };

const WRITE_ROLES = ["ADMIN", "OWNER", "MANAGER"];

export default function OwnerStatementsPage() {
  const [me, setMe] = useState<Me | null>(null);
  const [data, setData] = useState<OwnerStatementList | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  async function load() {
    setLoading(true);
    setError("");
    try {
      const meData = await apiGet("/auth/me");
      setMe(meData);
      const list = await listOwnerStatements({});
      setData(list);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Load failed");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

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
            Owner Statements
          </h1>
          <p className="text-slate-500 mt-1">
            {data.total} {data.total === 1 ? "statement" : "statements"}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Link
            href="/dashboard/accounting/management-fees"
            className="text-sm px-3 py-2 text-slate-600 hover:text-slate-900"
          >
            Management Fees
          </Link>
          {canWrite && (
            <Link
              href="/dashboard/accounting/owner-statements/new"
              className="text-sm px-4 py-2 bg-slate-900 text-white rounded-lg hover:bg-slate-700"
            >
              + Generate Statement
            </Link>
          )}
        </div>
      </div>

      {/* Table */}
      <div className="bg-white border border-slate-200 rounded-xl overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-slate-50">
            <tr>
              <th className="text-left px-4 py-2 font-medium text-slate-700 w-20">
                #
              </th>
              <th className="text-left px-4 py-2 font-medium text-slate-700">
                Owner
              </th>
              <th className="text-left px-4 py-2 font-medium text-slate-700 w-48">
                Period
              </th>
              <th className="text-left px-4 py-2 font-medium text-slate-700 w-40">
                Generated
              </th>
              <th className="text-right px-4 py-2 font-medium text-slate-700 w-32">
                Income
              </th>
              <th className="text-right px-4 py-2 font-medium text-slate-700 w-32">
                Expense
              </th>
              <th className="text-right px-4 py-2 font-medium text-slate-700 w-32">
                Net
              </th>
            </tr>
          </thead>
          <tbody>
            {data.items.length === 0 && (
              <tr>
                <td
                  colSpan={7}
                  className="px-4 py-8 text-center text-slate-500"
                >
                  No statements yet.
                </td>
              </tr>
            )}
            {data.items.map((s) => (
              <tr
                key={s.id}
                className="border-t border-slate-100 hover:bg-slate-50"
              >
                <td className="px-4 py-2 text-slate-500 font-mono">
                  #{s.id}
                </td>
                <td className="px-4 py-2 text-slate-800">
                  <Link
                    href={`/dashboard/accounting/owner-statements/${s.id}`}
                    className="text-blue-600 hover:underline"
                  >
                    {s.owner_name || s.owner_email || `Owner #${s.owner_id}`}
                  </Link>
                </td>
                <td className="px-4 py-2 text-slate-600 text-xs">
                  {s.period_start} → {s.period_end}
                </td>
                <td className="px-4 py-2 text-slate-500 text-xs">
                  {s.generated_at
                    ? new Date(s.generated_at).toLocaleString()
                    : "—"}
                </td>
                <td className="px-4 py-2 text-right font-mono text-slate-600">
                  {Number(s.total_income).toLocaleString("en-US", {
                    style: "currency",
                    currency: "USD",
                  })}
                </td>
                <td className="px-4 py-2 text-right font-mono text-slate-600">
                  {Number(s.total_expense).toLocaleString("en-US", {
                    style: "currency",
                    currency: "USD",
                  })}
                </td>
                <td className="px-4 py-2 text-right font-mono font-semibold">
                  {Number(s.total_net).toLocaleString("en-US", {
                    style: "currency",
                    currency: "USD",
                  })}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}