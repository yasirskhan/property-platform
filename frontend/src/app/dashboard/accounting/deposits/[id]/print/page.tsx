"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { getPrintableDeposit, type DepositDetail } from "@/lib/deposits";
import { formatDate, formatMoney } from "@/lib/money";

export default function PrintDepositPage() {
  const id = Number(useParams().id);
  const [deposit, setDeposit] = useState<DepositDetail | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    getPrintableDeposit(id)
      .then(setDeposit)
      .catch((e) => setError(e instanceof Error ? e.message : "Could not load deposit."));
  }, [id]);

  if (!deposit) return <div className="p-8">{error || "Loading..."}</div>;

  return (
    <div className="max-w-4xl mx-auto p-8 print:p-0">
      <div className="mb-5 print:hidden">
        <button className="border rounded px-4 py-2" onClick={() => window.print()}>
          Print
        </button>
      </div>
      <div className="border rounded p-8">
        <div className="flex justify-between gap-4">
          <div>
            <h1 className="text-xl font-semibold">Bank Deposit</h1>
            <p>{deposit.bank_gl_account_number} {deposit.bank_gl_account_name}</p>
          </div>
          <div className="text-right">
            <strong>{deposit.deposit_number}</strong>
            <p>{formatDate(deposit.deposit_date)}</p>
          </div>
        </div>
        {deposit.description && <p className="mt-4">{deposit.description}</p>}
        <table className="w-full mt-6 text-sm">
          <thead><tr className="border-b"><th className="py-2 text-left">Receipt</th><th className="py-2 text-left">Payer</th><th className="py-2 text-left">Reference</th><th className="py-2 text-right">Amount</th></tr></thead>
          <tbody>{deposit.lines.map((line) => <tr className="border-b" key={line.id}><td className="py-2">{line.receipt_date ? formatDate(line.receipt_date) : "—"}</td><td className="py-2">{line.receipt_payer || line.receipt_type || "—"}</td><td className="py-2">{line.receipt_reference || "—"}</td><td className="py-2 text-right">{line.receipt_amount ? formatMoney(line.receipt_amount) : "—"}</td></tr>)}</tbody>
        </table>
        <div className="mt-5 text-right text-lg font-semibold">Total {formatMoney(deposit.total)}</div>
        {deposit.notes && <p className="mt-6 text-sm">Notes: {deposit.notes}</p>}
      </div>
    </div>
  );
}
