// ============================================================
// Management Fees list page
// ------------------------------------------------------------
// Route: /dashboard/accounting/management-fees
//
// Shows past fee runs. Click a row → centered modal with the
// full breakdown (rent portion, other portion, GL refs).
// ============================================================

"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  listManagementFees,
  ManagementFeeRun,
  ManagementFeeRunList,
} from "@/lib/managementFees";
import { apiGet } from "@/lib/api";

type Me = { role: string };

const WRITE_ROLES = ["ADMIN", "OWNER", "MANAGER"];

export default function ManagementFeesPage() {
  const [me, setMe] = useState<Me | null>(null);
  const [data, setData] = useState<ManagementFeeRunList | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [selected, setSelected] = useState<ManagementFeeRun | null>(null);

  async function load() {
    setLoading(true);
    setError("");
    try {
      const meData = await apiGet("/auth/me");
      setMe(meData);
      const list = await listManagementFees({});
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

  const totalFees = data.items
    .filter((r) => !r.is_reversed)
    .reduce((sum, r) => sum + Number(r.total_fee || 0), 0);

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
            Management Fees
          </h1>
          <p className="text-slate-500 mt-1">
            {data.total} {data.total === 1 ? "run" : "runs"}
            {" · "}
            Total billed:{" "}
            {totalFees.toLocaleString("en-US", {
              style: "currency",
              currency: "USD",
            })}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Link
            href="/dashboard/accounting/receipts"
            className="text-sm px-3 py-2 text-slate-600 hover:text-slate-900"
          >
            Receipts
          </Link>
          <Link
            href="/dashboard/accounting/bills"
            className="text-sm px-3 py-2 text-slate-600 hover:text-slate-900"
          >
            Bills
          </Link>
          {canWrite && (
            <Link
              href="/dashboard/accounting/management-fees/new"
              className="text-sm px-4 py-2 bg-slate-900 text-white rounded-lg hover:bg-slate-700"
            >
              + Pay Management Fees
            </Link>
          )}
        </div>
      </div>

      {/* Table */}
      <div className="bg-white border border-slate-200 rounded-xl overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-slate-50">
            <tr>
              <th className="text-left px-4 py-2 font-medium text-slate-700 w-24">
                #
              </th>
              <th className="text-left px-4 py-2 font-medium text-slate-700">
                Property
              </th>
              <th className="text-left px-4 py-2 font-medium text-slate-700 w-44">
                Period
              </th>
              <th className="text-right px-4 py-2 font-medium text-slate-700 w-32">
                Rent Income
              </th>
              <th className="text-right px-4 py-2 font-medium text-slate-700 w-28">
                Rent Fee
              </th>
              <th className="text-right px-4 py-2 font-medium text-slate-700 w-28">
                Other Fee
              </th>
              <th className="text-right px-4 py-2 font-medium text-slate-700 w-32">
                Total
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
                  No management fee runs yet.
                </td>
              </tr>
            )}
            {data.items.map((r) => (
              <tr
                key={r.id}
                onClick={() => setSelected(r)}
                className={`border-t border-slate-100 hover:bg-slate-50 cursor-pointer ${
                  r.is_reversed ? "opacity-60" : ""
                }`}
              >
                <td className="px-4 py-2 text-slate-500 font-mono">
                  #{r.id}
                </td>
                <td
                  className={`px-4 py-2 ${
                    r.is_reversed
                      ? "line-through text-slate-400"
                      : "text-slate-800"
                  }`}
                >
                  {r.property_name || `Property #${r.property_id}`}
                  {r.is_reversed && (
                    <span className="ml-2 text-xs text-red-600">
                      reversed
                    </span>
                  )}
                </td>
                <td className="px-4 py-2 text-slate-600 text-xs">
                  {r.period_start} → {r.period_end}
                </td>
                <td className="px-4 py-2 text-right font-mono text-slate-600">
                  {Number(r.rent_income_total).toLocaleString("en-US", {
                    style: "currency",
                    currency: "USD",
                  })}
                </td>
                <td className="px-4 py-2 text-right font-mono text-slate-600">
                  {Number(r.rent_fee_amount).toLocaleString("en-US", {
                    style: "currency",
                    currency: "USD",
                  })}
                </td>
                <td className="px-4 py-2 text-right font-mono text-slate-600">
                  {Number(r.other_fee_amount).toLocaleString("en-US", {
                    style: "currency",
                    currency: "USD",
                  })}
                </td>
                <td
                  className={`px-4 py-2 text-right font-mono font-semibold ${
                    r.is_reversed ? "line-through text-slate-400" : ""
                  }`}
                >
                  {Number(r.total_fee).toLocaleString("en-US", {
                    style: "currency",
                    currency: "USD",
                  })}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Centered modal */}
      {selected && (
        <DetailModal
          run={selected}
          onClose={() => setSelected(null)}
        />
      )}
    </div>
  );
}

// ------------------------------------------------------------
// Centered detail modal
// ------------------------------------------------------------
function DetailModal({
  run,
  onClose,
}: {
  run: ManagementFeeRun;
  onClose: () => void;
}) {
  return (
    <>
      <div className="fixed inset-0 bg-black/40 z-40" onClick={onClose} />
      <div className="fixed inset-0 z-50 flex items-center justify-center p-4 pointer-events-none">
        <div className="w-full max-w-2xl max-h-[90vh] bg-white rounded-xl shadow-2xl flex flex-col pointer-events-auto">
          <div className="flex items-center justify-between px-6 py-4 border-b border-slate-200">
            <div>
              <div className="text-xs text-slate-500">Management Fee Run</div>
              <div className="font-semibold text-slate-900 text-lg">
                #{run.id}
                {run.is_reversed && (
                  <span className="ml-2 text-xs px-2 py-0.5 bg-red-50 text-red-700 rounded">
                    reversed
                  </span>
                )}
              </div>
            </div>
            <button
              onClick={onClose}
              className="text-slate-400 hover:text-slate-700 text-2xl leading-none"
            >
              ×
            </button>
          </div>

          <div className="flex-1 overflow-y-auto p-6 space-y-4 text-sm">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <div className="text-xs text-slate-500">Property</div>
                <div className="text-slate-800">
                  {run.property_name || `Property #${run.property_id}`}
                </div>
              </div>
              <div>
                <div className="text-xs text-slate-500">Period</div>
                <div className="text-slate-800">
                  {run.period_start} → {run.period_end}
                </div>
              </div>
            </div>

            <div className="pt-4 border-t border-slate-200">
              <div className="text-xs font-semibold text-slate-500 uppercase mb-3">
                Fee breakdown
              </div>
              <div className="space-y-2">
                <div className="flex justify-between">
                  <span className="text-slate-600">
                    Rent income × {run.rent_fee_pct}%
                  </span>
                  <span className="font-mono">
                    {Number(run.rent_fee_amount).toLocaleString("en-US", {
                      style: "currency",
                      currency: "USD",
                    })}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-600">
                    Other fees × {run.other_fee_pct}%
                  </span>
                  <span className="font-mono">
                    {Number(run.other_fee_amount).toLocaleString("en-US", {
                      style: "currency",
                      currency: "USD",
                    })}
                  </span>
                </div>
                <div className="flex justify-between border-t border-slate-200 pt-2 mt-2 font-semibold">
                  <span>Total Fee</span>
                  <span className="font-mono">
                    {Number(run.total_fee).toLocaleString("en-US", {
                      style: "currency",
                      currency: "USD",
                    })}
                  </span>
                </div>
              </div>
            </div>

            <div className="pt-4 border-t border-slate-200">
              <div className="text-xs font-semibold text-slate-500 uppercase mb-2">
                Eligible income
              </div>
              <div className="space-y-1 text-xs">
                <div className="flex justify-between">
                  <span className="text-slate-500">Rent income total</span>
                  <span className="font-mono text-slate-700">
                    {Number(run.rent_income_total).toLocaleString("en-US", {
                      style: "currency",
                      currency: "USD",
                    })}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">Other fee income total</span>
                  <span className="font-mono text-slate-700">
                    {Number(run.other_fee_income_total).toLocaleString("en-US", {
                      style: "currency",
                      currency: "USD",
                    })}
                  </span>
                </div>
              </div>
            </div>

            <div className="pt-4 border-t border-slate-200">
              <div className="text-xs font-semibold text-slate-500 uppercase mb-2">
                GL Posting
              </div>
              <div className="text-xs space-y-1">
                <div>
                  <span className="text-slate-500">Debit:</span>{" "}
                  <span className="text-slate-700 font-mono">
                    {run.expense_gl_account_number}{" "}
                    {run.expense_gl_account_name}
                  </span>
                </div>
                <div>
                  <span className="text-slate-500">Credit (Payable):</span>{" "}
                  <span className="text-slate-700 font-mono">
                    {run.cash_gl_account_number} {run.cash_gl_account_name}
                  </span>
                </div>
                {run.gl_transaction_id && (
                  <div>
                    <span className="text-slate-500">GL txn:</span>{" "}
                    <Link
                      href={`/dashboard/accounting/journal-entries/${run.gl_transaction_id}`}
                      className="text-blue-600 hover:underline"
                    >
                      #{run.gl_transaction_id}
                    </Link>
                  </div>
                )}
              </div>
            </div>

            {run.notes && (
              <div className="pt-4 border-t border-slate-200">
                <div className="text-xs text-slate-500">Notes</div>
                <div className="text-slate-800 whitespace-pre-wrap">
                  {run.notes}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </>
  );
}