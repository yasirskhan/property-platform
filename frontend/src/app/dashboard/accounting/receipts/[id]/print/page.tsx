"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import {
  getReceiptPrintData,
  RECEIPT_TYPE_LABELS,
  type ReceiptDetail,
} from "@/lib/receipts";
import { formatDate, formatMoney } from "@/lib/money";

export default function ReceiptPrintPage() {
  const params = useParams();
  const receiptId = Number(params.id);
  const [receipt, setReceipt] = useState<ReceiptDetail | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!receiptId) return;
    getReceiptPrintData(receiptId)
      .then(setReceipt)
      .catch((err) =>
        setError(err instanceof Error ? err.message : "Could not load receipt")
      );
  }, [receiptId]);

  if (error) {
    return <div className="p-8 text-red-700">{error}</div>;
  }
  if (!receipt) {
    return <div className="p-8 text-slate-500">Loading receipt…</div>;
  }

  return (
    <div className="max-w-3xl mx-auto p-8 bg-white text-slate-900">
      <div className="print:hidden flex items-center justify-between mb-8">
        <Link
          href="/dashboard/accounting/receipts"
          className="text-sm text-slate-500 hover:text-slate-800"
        >
          ← Back to Receipts
        </Link>
        <button
          type="button"
          onClick={() => window.print()}
          className="px-4 py-2 rounded-lg bg-slate-900 text-white text-sm font-medium"
        >
          Print
        </button>
      </div>

      <header className="border-b border-slate-300 pb-5 mb-6">
        <h1 className="text-2xl font-bold">Receipt #{receipt.id}</h1>
        <p className="text-sm text-slate-500 mt-1">
          {formatDate(receipt.receipt_date)} ·{" "}
          {RECEIPT_TYPE_LABELS[receipt.type] || receipt.type}
        </p>
      </header>

      <div className="grid grid-cols-2 gap-5 text-sm mb-6">
        <div>
          <div className="text-xs uppercase tracking-wide text-slate-500">
            Amount
          </div>
          <div className="text-xl font-semibold font-mono">
            {formatMoney(receipt.amount)}
          </div>
        </div>
        <div>
          <div className="text-xs uppercase tracking-wide text-slate-500">
            Cash account
          </div>
          <div>
            {receipt.cash_gl_account_number
              ? `${receipt.cash_gl_account_number} ${receipt.cash_gl_account_name ?? ""}`
              : "—"}
          </div>
        </div>
        <div>
          <div className="text-xs uppercase tracking-wide text-slate-500">
            Received from
          </div>
          <div>
            {receipt.type === "TENANT"
              ? `Tenant #${receipt.tenant_user_id ?? "—"}`
              : receipt.type === "OWNER"
              ? receipt.payer_name || `Owner #${receipt.owner_user_id ?? "—"}`
              : receipt.received_from || "—"}
          </div>
        </div>
        <div>
          <div className="text-xs uppercase tracking-wide text-slate-500">
            Reference
          </div>
          <div>{receipt.reference_number || "—"}</div>
        </div>
      </div>

      {receipt.remarks && (
        <div className="mb-6 text-sm">
          <div className="text-xs uppercase tracking-wide text-slate-500">
            Remarks
          </div>
          <div>{receipt.remarks}</div>
        </div>
      )}

      <table className="w-full text-sm border border-slate-300">
        <thead className="bg-slate-50">
          <tr>
            <th className="text-left px-3 py-2 border-b border-slate-300">
              Account
            </th>
            <th className="text-left px-3 py-2 border-b border-slate-300">
              Description
            </th>
            <th className="text-right px-3 py-2 border-b border-slate-300">
              Amount
            </th>
          </tr>
        </thead>
        <tbody>
          {receipt.lines.map((line) => (
            <tr key={line.id} className="border-t border-slate-200">
              <td className="px-3 py-2">
                {line.gl_account_number} {line.gl_account_name}
              </td>
              <td className="px-3 py-2">{line.description || "—"}</td>
              <td className="px-3 py-2 text-right font-mono">
                {formatMoney(line.amount_to_pay)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {receipt.is_deposited && (
        <p className="mt-5 text-xs text-slate-500">
          Included in bank deposit #{receipt.deposit_id}.
        </p>
      )}
      {receipt.is_reversed && (
        <p className="mt-2 text-sm font-semibold text-red-700">REVERSED</p>
      )}
    </div>
  );
}
