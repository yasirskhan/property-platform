// ============================================================
// Management Fees list page
// ------------------------------------------------------------
// List historical management fee runs. Detail modal shows the
// breakdown. Reverse available if not already reversed.
//
// Uses formatMoney() from lib/money.ts for every amount so the
// org's currency setting is respected (Section 59).
// ============================================================

"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { apiGet } from "@/lib/api";
import { formatMoney, formatDate } from "@/lib/money";
import Flag from "@/components/features/Flag";
import { useDisplay } from "@/contexts/DisplayContext";
import {
  listManagementFees,
  getManagementFee,
  reverseManagementFee,
  type ManagementFeeRun,
  type ManagementFeeRunList,
} from "@/lib/managementFees";

interface Me {
  id: number;
  role: string;
}

const WRITE_ROLES = ["ADMIN", "OWNER", "MANAGER"];

export default function ManagementFeesPage() {
  const { prefs } = useDisplay();
  const [me, setMe] = useState<Me | null>(null);
  const [runs, setRuns] = useState<ManagementFeeRun[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [includeReversed, setIncludeReversed] = useState(true);

  const [openRun, setOpenRun] = useState<ManagementFeeRun | null>(null);
  const [openLoading, setOpenLoading] = useState(false);
  const [reversing, setReversing] = useState(false);

  useEffect(() => {
    apiGet("/auth/me").then((u) => setMe(u as Me)).catch(() => setMe(null));
  }, []);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const data: ManagementFeeRunList = await listManagementFees({
        date_from: dateFrom || undefined,
        date_to: dateTo || undefined,
        include_reversed: includeReversed,
      });
      setRuns(data.items);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Could not load fees.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function open(runId: number) {
    setOpenLoading(true);
    setError(null);
    try {
      const detail = await getManagementFee(runId);
      setOpenRun(detail);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Could not load run.");
    } finally {
      setOpenLoading(false);
    }
  }

  async function submitReverse() {
    if (!openRun) return;
    if (
      !confirm(
        `Reverse management fee run for ${openRun.property_name || `Property #${openRun.property_id}`}?`
      )
    )
      return;
    setReversing(true);
    setError(null);
    try {
      const updated = await reverseManagementFee(openRun.id, {
        reversal_date: new Date().toISOString().slice(0, 10),
      });
      setOpenRun(updated);
      await load();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Could not reverse.");
    } finally {
      setReversing(false);
    }
  }

  const canWrite = Boolean(me && WRITE_ROLES.includes(String(me.role).toUpperCase()));

  const totalFees = useMemo(
    () =>
      runs
        .filter((r) => !r.is_reversed)
        .reduce((acc, r) => acc + parseFloat(r.total_fee), 0),
    [runs]
  );

  return (
    <div className="p-6" data-layout-mode={(prefs?.layout_mode ?? "TABS").toLowerCase()} data-density={(prefs?.density ?? "COMFORTABLE").toLowerCase()}>
      <div className="flex items-center justify-between mb-1">
        <h1 className="text-xl font-semibold text-slate-900">
          Management Fees
        </h1>
        <div className="flex flex-wrap justify-end gap-2">
          <Flag name="release.accounting.pay_owners">
            <button type="button" disabled className="px-3 py-1.5 rounded-md border border-slate-300 text-slate-500 text-sm disabled:opacity-60">Pay Owners</button>
          </Flag>
          <Flag name="release.accounting.management_fees.overcollection">
            <button type="button" disabled className="px-3 py-1.5 rounded-md border border-slate-300 text-slate-500 text-sm disabled:opacity-60">Overcollection Strategy</button>
          </Flag>
          <Flag name="release.accounting.management_fees.exclusions">
            <button type="button" disabled className="px-3 py-1.5 rounded-md border border-slate-300 text-slate-500 text-sm disabled:opacity-60">Management Fee Exclusions</button>
          </Flag>
          <Flag name="release.accounting.management_fees.post_gpr">
            <button type="button" disabled className="px-3 py-1.5 rounded-md border border-slate-300 text-slate-500 text-sm disabled:opacity-60">Post GPR</button>
          </Flag>
          {canWrite && (
            <Link
              href="/dashboard/accounting/management-fees/new"
              className="px-3 py-1.5 rounded-md bg-blue-600 text-white text-sm font-medium hover:bg-blue-700"
            >
              + Pay Fees
            </Link>
          )}
        </div>
      </div>
      <p className="text-sm text-slate-500 mb-6">
        Two-tier: 9% of rent income + 100% of other eligible fees.
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
        <label className="flex items-center gap-2 text-xs text-slate-600">
          <input
            type="checkbox"
            checked={includeReversed}
            onChange={(e) => setIncludeReversed(e.target.checked)}
          />
          Include reversed
        </label>
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
              <th className="text-left px-4 py-2 font-medium">Property</th>
              <th className="text-left px-4 py-2 font-medium">Period</th>
              <th className="text-right px-4 py-2 font-medium">
                Rent income
              </th>
              <th className="text-right px-4 py-2 font-medium">Rent fee</th>
              <th className="text-right px-4 py-2 font-medium">Other fee</th>
              <th className="text-right px-4 py-2 font-medium">Total</th>
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
            {!loading && runs.length === 0 && (
              <tr>
                <td colSpan={6} className="px-4 py-6 text-center text-slate-500">
                  No management fee runs yet.
                </td>
              </tr>
            )}
            {runs.map((r) => (
              <tr
                key={r.id}
                onClick={() => open(r.id)}
                className={`border-t border-slate-100 hover:bg-slate-50 cursor-pointer ${
                  r.is_reversed ? "line-through opacity-60" : ""
                }`}
              >
                <td className="px-4 py-2">
                  {r.property_name || `Property #${r.property_id}`}
                </td>
                <td className="px-4 py-2 text-slate-500 text-xs">
                  {formatDate(r.period_start)} → {formatDate(r.period_end)}
                </td>
                <td className="px-4 py-2 text-right font-mono">
                  {formatMoney(r.rent_income_total)}
                </td>
                <td className="px-4 py-2 text-right font-mono">
                  {formatMoney(r.rent_fee_amount)}
                </td>
                <td className="px-4 py-2 text-right font-mono">
                  {formatMoney(r.other_fee_amount)}
                </td>
                <td className="px-4 py-2 text-right font-mono font-semibold">
                  {formatMoney(r.total_fee)}
                </td>
              </tr>
            ))}
          </tbody>
          {runs.length > 0 && (
            <tfoot className="bg-slate-50 text-slate-700">
              <tr className="border-t border-slate-200">
                <td className="px-4 py-2 text-xs" colSpan={5}>
                  {runs.filter((r) => !r.is_reversed).length} active runs
                </td>
                <td className="px-4 py-2 text-right font-mono font-medium">
                  {formatMoney(totalFees.toFixed(2))}
                </td>
              </tr>
            </tfoot>
          )}
        </table>
      </div>

      {/* Detail modal */}
      {(openRun || openLoading) && (
        <div
          className="fixed inset-0 bg-black/40 z-40 flex items-start justify-center p-6 overflow-auto"
          onClick={() => setOpenRun(null)}
        >
          <div
            className="bg-white rounded-lg shadow-xl max-w-2xl w-full my-8 max-h-[90vh] overflow-auto"
            onClick={(e) => e.stopPropagation()}
          >
            {openLoading && !openRun ? (
              <div className="p-8 text-center text-slate-500">Loading...</div>
            ) : openRun ? (
              <div className="p-6">
                <div className="flex items-start justify-between mb-4">
                  <div>
                    <h2 className="text-lg font-semibold text-slate-900">
                      {openRun.property_name || `Property #${openRun.property_id}`}
                    </h2>
                    <div className="text-sm text-slate-500">
                      {formatDate(openRun.period_start)} → {formatDate(openRun.period_end)}
                    </div>
                  </div>
                  <button
                    onClick={() => setOpenRun(null)}
                    className="text-slate-400 hover:text-slate-700 text-xl leading-none"
                  >
                    ✕
                  </button>
                </div>

                {openRun.is_reversed && (
                  <div className="text-sm text-red-600 mb-3 bg-red-50 border border-red-200 rounded-md px-3 py-2">
                    This run has been reversed.
                  </div>
                )}

                <div className="grid grid-cols-2 gap-3 mb-4 text-sm">
                  <div>
                    <div className="text-xs text-slate-500">Rent income</div>
                    <div className="font-mono">
                      {formatMoney(openRun.rent_income_total)}
                    </div>
                  </div>
                  <div>
                    <div className="text-xs text-slate-500">
                      Other fee income
                    </div>
                    <div className="font-mono">
                      {formatMoney(openRun.other_fee_income_total)}
                    </div>
                  </div>
                  <div>
                    <div className="text-xs text-slate-500">
                      Rent fee ({openRun.rent_fee_pct}%)
                    </div>
                    <div className="font-mono">
                      {formatMoney(openRun.rent_fee_amount)}
                    </div>
                  </div>
                  <div>
                    <div className="text-xs text-slate-500">
                      Other fee ({openRun.other_fee_pct}%)
                    </div>
                    <div className="font-mono">
                      {formatMoney(openRun.other_fee_amount)}
                    </div>
                  </div>
                  <div className="col-span-2 border-t border-slate-200 pt-3">
                    <div className="text-xs text-slate-500">Total fee</div>
                    <div className="text-lg font-semibold font-mono">
                      {formatMoney(openRun.total_fee)}
                    </div>
                  </div>
                </div>

                {openRun.gl_transaction_id && (
                  <div className="text-xs text-slate-500 mb-4">
                    <Link
                      href={`/dashboard/accounting/journal-entries/${openRun.gl_transaction_id}`}
                      className="text-blue-600 hover:underline"
                    >
                      View GL transaction
                    </Link>
                  </div>
                )}

                <div className="flex items-center justify-between">
                  <div>
                    {!openRun.is_reversed && canWrite && (
                      <button
                        onClick={submitReverse}
                        disabled={reversing}
                        className="px-3 py-1.5 rounded-md border border-red-300 text-red-700 text-sm font-medium hover:bg-red-50 disabled:opacity-50"
                      >
                        {reversing ? "Reversing..." : "Reverse"}
                      </button>
                    )}
                  </div>
                  <button
                    onClick={() => setOpenRun(null)}
                    className="text-sm text-slate-500 hover:text-slate-700"
                  >
                    Close
                  </button>
                </div>
              </div>
            ) : null}
          </div>
        </div>
      )}
    </div>
  );
}