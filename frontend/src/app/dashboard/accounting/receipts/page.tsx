// ============================================================
// Receipts list page
// ------------------------------------------------------------
// List receipts, filter, view detail, reverse.
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
import ConfirmModal from "@/components/ui/ConfirmModal";
import { useDisplay } from "@/contexts/DisplayContext";
import {
  listReceipts,
  getReceipt,
  reverseReceipt,
  RECEIPT_TYPE_LABELS,
  RECEIPT_TYPE_ORDER,
  type Receipt,
  type ReceiptDetail,
  type ReceiptListFilters,
} from "@/lib/receipts";

interface Me {
  id: number;
  role: string;
}

export default function ReceiptsPage() {
  const { prefs } = useDisplay();
  const [me, setMe] = useState<Me | null>(null);
  const [rows, setRows] = useState<Receipt[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [receiptType, setReceiptType] = useState<string>("");
  const [propertyId, setPropertyId] = useState<number | "">("");
  const [includeReversed, setIncludeReversed] = useState(true);

  const [openReceipt, setOpenReceipt] = useState<ReceiptDetail | null>(null);
  const [openLoading, setOpenLoading] = useState(false);
  const [reversing, setReversing] = useState(false);
  const [confirmReverseOpen, setConfirmReverseOpen] = useState(false);

  useEffect(() => {
    apiGet("/auth/me").then((u) => setMe(u as Me)).catch(() => setMe(null));
  }, []);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const filters: ReceiptListFilters = {};
      if (dateFrom) filters.date_from = dateFrom;
      if (dateTo) filters.date_to = dateTo;
      if (receiptType) filters.type = receiptType as ReceiptListFilters["type"];
      if (propertyId) filters.property_id = propertyId;
      filters.include_reversed = includeReversed;
      const data = await listReceipts(filters);
      setRows(data.items);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Could not load receipts.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function open(receiptId: number) {
    setOpenLoading(true);
    setError(null);
    try {
      const detail = await getReceipt(receiptId);
      setOpenReceipt(detail);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Could not load receipt.");
    } finally {
      setOpenLoading(false);
    }
  }

  async function submitReverse() {
    if (!openReceipt) return;
    setReversing(true);
    setError(null);
    try {
      const updated = await reverseReceipt(openReceipt.id, {
        reversal_date: new Date().toISOString().slice(0, 10),
      });
      setOpenReceipt(updated);
      setConfirmReverseOpen(false);
      await load();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Could not reverse receipt.");
    } finally {
      setReversing(false);
    }
  }

  const totalAmount = useMemo(
    () =>
      rows
        .filter((r) => !r.is_reversed)
        .reduce((acc, r) => acc + parseFloat(r.amount), 0),
    [rows]
  );

  return (
    <div
      className="p-6"
      data-layout-mode={(prefs?.layout_mode ?? "TABS").toLowerCase()}
      data-density={(prefs?.density ?? "COMFORTABLE").toLowerCase()}
    >
      <div className="flex items-center justify-between mb-1">
        <h1 className="text-xl font-semibold text-slate-900">Receipts</h1>
        <div className="flex items-center gap-2">
          <Flag name="release.reporting.export"><button type="button" disabled className="px-3 py-1.5 rounded-md border border-slate-300 text-slate-500 text-sm disabled:opacity-60">Export</button></Flag>
          <Flag name="release.accounting.receipts.list_print"><button type="button" disabled className="px-3 py-1.5 rounded-md border border-slate-300 text-slate-500 text-sm disabled:opacity-60">Print list</button></Flag>
          <Flag name="release.accounting.receipts.bulk"><button type="button" disabled className="px-3 py-1.5 rounded-md border border-slate-300 text-slate-500 text-sm disabled:opacity-60">Bulk actions</button></Flag>
          {me && me.role !== "TENANT" && (
            <Link href="/dashboard/accounting/receipts/new" className="px-3 py-1.5 rounded-md bg-blue-600 text-white text-sm font-medium hover:bg-blue-700">+ New Receipt</Link>
          )}
        </div>
      </div>
      <p className="text-sm text-slate-500 mb-6">
        All payments received: tenants, owners, and others.
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
        <div>
          <label className="block text-xs text-slate-600 mb-1">Type</label>
          <select
            value={receiptType}
            onChange={(e) => setReceiptType(e.target.value)}
            className="border border-slate-300 rounded-md px-2 py-1.5 text-sm bg-white"
          >
            <option value="">All</option>
            {RECEIPT_TYPE_ORDER.map((t) => (
              <option key={t} value={t}>
                {RECEIPT_TYPE_LABELS[t]}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-xs text-slate-600 mb-1">
            Property ID
          </label>
          <input
            type="number"
            value={propertyId}
            onChange={(e) =>
              setPropertyId(e.target.value ? Number(e.target.value) : "")
            }
            className="border border-slate-300 rounded-md px-2 py-1.5 text-sm w-24"
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
              <th className="text-left px-4 py-2 font-medium">Date</th>
              <th className="text-left px-4 py-2 font-medium">Type</th>
              <th className="text-left px-4 py-2 font-medium">From</th>
              <th className="text-left px-4 py-2 font-medium">Cash</th>
              <th className="text-right px-4 py-2 font-medium">Amount</th>
            </tr>
          </thead>
          <tbody>
            {loading && (
              <tr>
                <td colSpan={5} className="px-4 py-6 text-center text-slate-500">
                  Loading...
                </td>
              </tr>
            )}
            {!loading && rows.length === 0 && (
              <tr>
                <td colSpan={5} className="px-4 py-6 text-center text-slate-500">
                  No receipts yet.
                </td>
              </tr>
            )}
            {rows.map((r) => (
              <tr
                key={r.id}
                onClick={() => open(r.id)}
                className={`border-t border-slate-100 hover:bg-slate-50 cursor-pointer ${
                  r.is_reversed ? "line-through opacity-60" : ""
                }`}
              >
                <td className="px-4 py-2">{formatDate(r.receipt_date)}</td>
                <td className="px-4 py-2 text-xs text-slate-600">
                  {RECEIPT_TYPE_LABELS[r.type] || r.type}
                </td>
                <td className="px-4 py-2">
                  {r.type === "TENANT"
                    ? `Tenant #${r.tenant_user_id ?? "?"}`
                    : r.type === "OWNER"
                    ? r.payer_name || `Owner #${r.owner_user_id ?? "?"}`
                    : r.received_from || "—"}
                </td>
                <td className="px-4 py-2 text-slate-500 text-xs">
                  {r.cash_gl_account_number
                    ? `${r.cash_gl_account_number} ${r.cash_gl_account_name}`
                    : "—"}
                </td>
                <td className="px-4 py-2 text-right font-mono">
                  {formatMoney(r.amount)}
                </td>
              </tr>
            ))}
          </tbody>
          {rows.length > 0 && (
            <tfoot className="bg-slate-50 text-slate-700">
              <tr className="border-t border-slate-200">
                <td className="px-4 py-2 text-xs" colSpan={4}>
                  {rows.filter((r) => !r.is_reversed).length} receipts
                </td>
                <td className="px-4 py-2 text-right font-mono font-medium">
                  {formatMoney(totalAmount.toFixed(2))}
                </td>
              </tr>
            </tfoot>
          )}
        </table>
      </div>

      {/* Detail modal */}
      {(openReceipt || openLoading) && (
        <div
          className="fixed inset-0 bg-black/40 z-40 flex items-start justify-center p-6 overflow-auto"
          onClick={() => setOpenReceipt(null)}
        >
          <div
            className="bg-white rounded-lg shadow-xl max-w-2xl w-full my-8 max-h-[90vh] overflow-auto"
            onClick={(e) => e.stopPropagation()}
          >
            {openLoading && !openReceipt ? (
              <div className="p-8 text-center text-slate-500">Loading...</div>
            ) : openReceipt ? (
              <div className="p-6">
                <div className="flex items-start justify-between mb-4">
                  <div>
                    <h2 className="text-lg font-semibold text-slate-900">
                      Receipt #{openReceipt.id}
                    </h2>
                    <div className="text-sm text-slate-500">
                      {formatDate(openReceipt.receipt_date)} ·{" "}
                      {RECEIPT_TYPE_LABELS[openReceipt.type] || openReceipt.type}
                    </div>
                  </div>
                  <button
                    onClick={() => setOpenReceipt(null)}
                    className="text-slate-400 hover:text-slate-700 text-xl leading-none"
                  >
                    ✕
                  </button>
                </div>

                {openReceipt.is_reversed && (
                  <div className="text-sm text-red-600 mb-3 bg-red-50 border border-red-200 rounded-md px-3 py-2">
                    This receipt has been reversed.
                  </div>
                )}

                <div className="grid grid-cols-2 gap-3 mb-4 text-sm">
                  <div>
                    <div className="text-xs text-slate-500">Amount</div>
                    <div className="font-mono">
                      {formatMoney(openReceipt.amount)}
                    </div>
                  </div>
                  <div>
                    <div className="text-xs text-slate-500">Cash account</div>
                    <div className="font-mono text-xs">
                      {openReceipt.cash_gl_account_number
                        ? `${openReceipt.cash_gl_account_number} ${openReceipt.cash_gl_account_name}`
                        : "—"}
                    </div>
                  </div>
                </div>

                {openReceipt.remarks && (
                  <div className="text-sm text-slate-600 mb-4">
                    <span className="text-xs text-slate-500">Remarks: </span>
                    {openReceipt.remarks}
                  </div>
                )}

                {openReceipt.lines && openReceipt.lines.length > 0 && (
                  <div className="border border-slate-200 rounded-md overflow-hidden mb-4">
                    <table className="w-full text-sm">
                      <thead className="bg-slate-50 text-slate-600">
                        <tr>
                          <th className="text-left px-3 py-2 font-medium">
                            Account
                          </th>
                          <th className="text-left px-3 py-2 font-medium">
                            Description
                          </th>
                          <th className="text-right px-3 py-2 font-medium">
                            Amount
                          </th>
                        </tr>
                      </thead>
                      <tbody>
                        {openReceipt.lines.map((ln) => (
                          <tr key={ln.id} className="border-t border-slate-100">
                            <td className="px-3 py-2">
                              {ln.gl_account_number} {ln.gl_account_name}
                            </td>
                            <td className="px-3 py-2">
                              {ln.description || "—"}
                            </td>
                            <td className="px-3 py-2 text-right font-mono">
                              {formatMoney(ln.amount_to_pay)}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}

                {openReceipt.gl_transaction_id && (
                  <div className="text-xs text-slate-500 mb-4">
                    <Link
                      href={`/dashboard/accounting/journal-entries/${openReceipt.gl_transaction_id}`}
                      className="text-blue-600 hover:underline"
                    >
                      View GL transaction
                    </Link>
                  </div>
                )}

                <span hidden aria-hidden="true" data-compat-slot="receipts.edit-lock-after-deposit" />
                <div className="flex items-center justify-between gap-3">
                  <div className="flex flex-wrap items-center gap-2">
                    <Flag name="release.accounting.receipts.print"><button type="button" disabled className="px-3 py-1.5 rounded-md border border-slate-300 text-slate-500 text-sm disabled:opacity-60">Print receipt</button></Flag>
                    <Flag name="release.accounting.receipts.repeat"><button type="button" disabled className="px-3 py-1.5 rounded-md border border-slate-300 text-slate-500 text-sm disabled:opacity-60">Repeat receipt</button></Flag>
                    <Flag name="release.accounting.receipts.process_nsf"><button type="button" disabled className="px-3 py-1.5 rounded-md border border-slate-300 text-slate-500 text-sm disabled:opacity-60">Process NSF</button></Flag>
                    {!openReceipt.is_reversed && me && me.role !== "TENANT" && (
                      <button onClick={() => setConfirmReverseOpen(true)} disabled={reversing} className="px-3 py-1.5 rounded-md border border-red-300 text-red-700 text-sm font-medium hover:bg-red-50 disabled:opacity-50">
                        {reversing ? "Reversing..." : "Reverse receipt"}
                      </button>
                    )}
                  </div>
                  <button
                    onClick={() => setOpenReceipt(null)}
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
      <ConfirmModal
        open={confirmReverseOpen}
        title="Reverse receipt?"
        description={openReceipt ? `Receipt #${openReceipt.id} will be marked reversed and a reversing entry will be posted. This cannot be undone.` : ""}
        confirmLabel="Reverse receipt"
        busy={reversing}
        danger
        onCancel={() => setConfirmReverseOpen(false)}
        onConfirm={submitReverse}
      />
    </div>
  );
}