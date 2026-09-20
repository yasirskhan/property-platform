// ============================================================
// Receipts list page
// ------------------------------------------------------------
// Route: /dashboard/accounting/receipts
//
// Shows every receipt in the current org. Filters: date range,
// type, include reversed. Clicking a row opens a CENTERED modal
// with the receipt detail.
// ============================================================

"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  listReceipts,
  Receipt,
  ReceiptList,
  RECEIPT_TYPE_LABELS,
} from "@/lib/receipts";
import { apiGet } from "@/lib/api";

type Me = { role: string };

const WRITE_ROLES = ["ADMIN", "OWNER", "MANAGER"];

export default function ReceiptsPage() {
  const [me, setMe] = useState<Me | null>(null);
  const [data, setData] = useState<ReceiptList | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  // Filters
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [type, setType] = useState<"" | "TENANT" | "OWNER" | "OTHER">("");
  const [includeReversed, setIncludeReversed] = useState(true);

  // Selected receipt for the modal
  const [selected, setSelected] = useState<Receipt | null>(null);

  async function load() {
    setLoading(true);
    setError("");
    try {
      const meData = await apiGet("/auth/me");
      setMe(meData);
      const list = await listReceipts({
        date_from: dateFrom || undefined,
        date_to: dateTo || undefined,
        type: type || undefined,
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
  }, [dateFrom, dateTo, type, includeReversed]);

  if (loading && !data) return <div className="text-slate-500">Loading…</div>;
  if (error) return <div className="text-red-600">{error}</div>;
  if (!data) return null;

  const canWrite = me ? WRITE_ROLES.includes(me.role) : false;

  const totalAmount = data.items
    .filter((r) => !r.is_reversed)
    .reduce((sum, r) => sum + Number(r.amount || 0), 0);

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Receipts</h1>
          <p className="text-slate-500 mt-1">
            {data.total} {data.total === 1 ? "receipt" : "receipts"}
            {" · "}
            Total:{" "}
            {totalAmount.toLocaleString("en-US", {
              style: "currency",
              currency: "USD",
            })}
          </p>
        </div>
        <div className="flex items-center gap-3">
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
              href="/dashboard/accounting/receipts/new"
              className="text-sm px-4 py-2 bg-slate-900 text-white rounded-lg hover:bg-slate-700"
            >
              + New Receipt
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
        <div>
          <label className="block text-xs text-slate-500 mb-1">Type</label>
          <select
            value={type}
            onChange={(e) =>
              setType(e.target.value as "" | "TENANT" | "OWNER" | "OTHER")
            }
            className="border border-slate-300 rounded px-2 py-1.5 text-sm"
          >
            <option value="">All types</option>
            <option value="TENANT">Tenant</option>
            <option value="OWNER">Owner</option>
            <option value="OTHER">Other</option>
          </select>
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
              <th className="text-left px-4 py-2 font-medium text-slate-700 w-24">
                Type
              </th>
              <th className="text-left px-4 py-2 font-medium text-slate-700">
                From
              </th>
              <th className="text-left px-4 py-2 font-medium text-slate-700 w-40">
                Cash Account
              </th>
              <th className="text-left px-4 py-2 font-medium text-slate-700 w-28">
                Reference
              </th>
              <th className="text-right px-4 py-2 font-medium text-slate-700 w-32">
                Amount
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
                  No receipts yet.
                </td>
              </tr>
            )}
            {data.items.map((r) => {
              const from =
                r.type === "TENANT"
                  ? `Tenant #${r.tenant_user_id ?? "?"}`
                  : r.type === "OWNER"
                  ? r.payer_name || `Owner #${r.owner_user_id ?? "?"}`
                  : r.received_from || "—";
              return (
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
                  <td className="px-4 py-2 text-slate-700">
                    {r.receipt_date}
                  </td>
                  <td className="px-4 py-2 text-slate-700">
                    <span className="text-xs px-2 py-0.5 bg-slate-100 rounded">
                      {RECEIPT_TYPE_LABELS[r.type] || r.type}
                    </span>
                  </td>
                  <td
                    className={`px-4 py-2 ${
                      r.is_reversed
                        ? "line-through text-slate-400"
                        : "text-slate-800"
                    }`}
                  >
                    {from}
                    {r.is_reversed && (
                      <span className="ml-2 text-xs text-red-600">
                        reversed
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-2 text-slate-600 text-xs">
                    {r.cash_gl_account_number
                      ? `${r.cash_gl_account_number} ${r.cash_gl_account_name}`
                      : "—"}
                  </td>
                  <td className="px-4 py-2 text-slate-600 text-xs">
                    {r.reference_number || "—"}
                  </td>
                  <td
                    className={`px-4 py-2 text-right font-mono ${
                      r.is_reversed ? "line-through text-slate-400" : ""
                    }`}
                  >
                    {Number(r.amount).toLocaleString("en-US", {
                      style: "currency",
                      currency: "USD",
                    })}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Centered modal */}
      {selected && (
        <ReceiptDetailModal
          receipt={selected}
          onClose={() => setSelected(null)}
        />
      )}
    </div>
  );
}

// ------------------------------------------------------------
// Centered modal: receipt detail
// ------------------------------------------------------------
function ReceiptDetailModal({
  receipt,
  onClose,
}: {
  receipt: Receipt;
  onClose: () => void;
}) {
  const [lines, setLines] = useState<
    Array<{
      id: number;
      gl_account_number: string | null;
      gl_account_name: string | null;
      description: string | null;
      amount_to_pay: string;
    }>
  >([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      try {
        const { getReceipt } = await import("@/lib/receipts");
        const detail = await getReceipt(receipt.id);
        if (!cancelled) setLines(detail.lines);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [receipt.id]);

  return (
    <>
      {/* Dark backdrop — click to close */}
      <div className="fixed inset-0 bg-black/40 z-40" onClick={onClose} />

      {/* Centered modal */}
      <div className="fixed inset-0 z-50 flex items-center justify-center p-4 pointer-events-none">
        <div className="w-full max-w-2xl max-h-[90vh] bg-white rounded-xl shadow-2xl flex flex-col pointer-events-auto">
          {/* Header */}
          <div className="flex items-center justify-between px-6 py-4 border-b border-slate-200">
            <div>
              <div className="text-xs text-slate-500">Receipt</div>
              <div className="font-semibold text-slate-900 text-lg">
                #{receipt.id}
                <span className="ml-2 text-xs px-2 py-0.5 bg-slate-100 rounded">
                  {RECEIPT_TYPE_LABELS[receipt.type]}
                </span>
              </div>
            </div>
            <button
              onClick={onClose}
              className="text-slate-400 hover:text-slate-700 text-2xl leading-none"
            >
              ×
            </button>
          </div>

          {/* Body */}
          <div className="flex-1 overflow-y-auto p-6 space-y-4 text-sm">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <div className="text-xs text-slate-500">Date</div>
                <div className="text-slate-800">{receipt.receipt_date}</div>
              </div>
              <div>
                <div className="text-xs text-slate-500">Amount</div>
                <div className="text-slate-800 font-mono text-lg">
                  {Number(receipt.amount).toLocaleString("en-US", {
                    style: "currency",
                    currency: "USD",
                  })}
                </div>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <div className="text-xs text-slate-500">Cash Account</div>
                <div className="text-slate-800">
                  {receipt.cash_gl_account_number}{" "}
                  {receipt.cash_gl_account_name}
                </div>
              </div>
              <div>
                <div className="text-xs text-slate-500">Reference</div>
                <div className="text-slate-800">
                  {receipt.reference_number || "—"}
                </div>
              </div>
            </div>

            {receipt.remarks && (
              <div>
                <div className="text-xs text-slate-500">Remarks</div>
                <div className="text-slate-800 whitespace-pre-wrap">
                  {receipt.remarks}
                </div>
              </div>
            )}

            {receipt.gl_transaction_id && (
              <div>
                <div className="text-xs text-slate-500">GL Transaction</div>
                <Link
                  href={`/dashboard/accounting/journal-entries/${receipt.gl_transaction_id}`}
                  className="text-blue-600 hover:underline"
                >
                  #{receipt.gl_transaction_id}
                </Link>
              </div>
            )}

            <div className="pt-4 border-t border-slate-200">
              <div className="text-xs font-semibold text-slate-500 uppercase mb-2">
                Lines
              </div>
              {loading ? (
                <div className="text-slate-500 text-xs">Loading…</div>
              ) : lines.length === 0 ? (
                <div className="text-slate-500 text-xs">No lines.</div>
              ) : (
                <ul className="space-y-2">
                  {lines.map((ln) => (
                    <li
                      key={ln.id}
                      className="flex items-start justify-between text-xs border-b border-slate-100 pb-2"
                    >
                      <div>
                        <div className="text-slate-700">
                          {ln.gl_account_number} {ln.gl_account_name}
                        </div>
                        {ln.description && (
                          <div className="text-slate-500">
                            {ln.description}
                          </div>
                        )}
                      </div>
                      <div className="font-mono text-slate-800">
                        {Number(ln.amount_to_pay).toLocaleString("en-US", {
                          style: "currency",
                          currency: "USD",
                        })}
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        </div>
      </div>
    </>
  );
}