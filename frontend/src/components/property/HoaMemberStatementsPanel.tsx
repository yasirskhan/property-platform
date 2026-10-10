"use client";

import { useEffect, useState } from "react";
import { apiGet } from "@/lib/api";

type Payment = {
  id: number; amount: string; received_on: string;
  status: "POSTED" | "REVERSED"; receipt_id: number;
  reversal_receipt_id: number | null;
};
type Charge = {
  id: number; proposal_id: number; amount: string; amount_paid: string;
  outstanding: string; due_on: string; status: "OPEN" | "PAID" | "REVERSED";
  gl_transaction_id: number; reversal_transaction_id: number | null;
  payments: Payment[];
};
type Statement = {
  member_user_id: number; total_assessed: string;
  total_paid: string; outstanding: string; charges: Charge[];
};

export default function HoaMemberStatementsPanel({
  associationId, propertyId, onClose,
}: {
  associationId: number; propertyId: number; onClose: () => void;
}) {
  const [accounts, setAccounts] = useState<Statement[]>([]);
  const [selected, setSelected] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const url = "/api/hoa/associations/" + associationId +
    "/member-statements?property_id=" + propertyId;

  async function reload() {
    setLoading(true); setError("");
    try {
      setAccounts(await apiGet(url) as Statement[]);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Member statements unavailable.");
    } finally { setLoading(false); }
  }

  useEffect(() => {
    let live = true;
    void apiGet(url).then((rows) => {
      if (live) setAccounts(rows as Statement[]);
    }).catch((cause) => {
      if (live) setError(cause instanceof Error ? cause.message : "Member statements unavailable.");
    }).finally(() => { if (live) setLoading(false); });
    return () => { live = false; };
  }, [url]);

  const visible = selected ? accounts.filter(a => String(a.member_user_id) === selected) : accounts;
  return <section className="w-full space-y-2 rounded border border-teal-200 bg-teal-50 p-3 text-xs">
    <div className="flex items-center justify-between gap-2">
      <h4 className="font-semibold">Posted HOA member statements</h4>
      <button type="button" onClick={onClose} className="text-blue-700">Close statements</button>
    </div>
    <p>Actual issued assessments and recorded offline receipts across all proposals
      for this association and property. This view does not collect funds, issue charges
      or certify statutory liability. Reversed entries remain visible for the audit trail.</p>
    <button type="button" disabled={loading} onClick={() => { void reload(); }}
      className="text-blue-700 disabled:opacity-50">Refresh member statements</button>
    {loading && <p>Loading posted balances…</p>}
    {error && <p role="alert" className="text-red-700">{error}</p>}
    {!loading && accounts.length === 0 && <p>No posted HOA member assessments.</p>}
    {accounts.length > 0 && <label className="block">Member account
      <select aria-label="HOA statement member" className="mt-1 block rounded border p-2"
        value={selected} onChange={event => setSelected(event.target.value)}>
        <option value="">All posted member accounts</option>
        {accounts.map(a => <option key={a.member_user_id} value={a.member_user_id}>
          Member #{a.member_user_id}</option>)}
      </select>
    </label>}
    {visible.map(account => <div key={account.member_user_id}
      className="space-y-2 rounded border bg-white p-2">
      <h5 className="font-semibold">Member #{account.member_user_id}</h5>
      <p>Assessed: ${account.total_assessed} · Paid: ${account.total_paid}
        {" · "}Outstanding: ${account.outstanding}</p>
      <ol className="space-y-2">
        {account.charges.map(charge => <li key={charge.id} className="rounded border p-2">
          <p>Assessment #{charge.id} · Proposal #{charge.proposal_id}
            {" · "}Due {charge.due_on} · {charge.status}</p>
          <p>Issued ${charge.amount} · Paid ${charge.amount_paid}
            {" · "}Outstanding ${charge.outstanding}</p>
          <p>Original GL #{charge.gl_transaction_id}
            {charge.reversal_transaction_id !== null &&
              " · Reversal GL #" + charge.reversal_transaction_id}</p>
          {charge.payments.length > 0 && <ol className="mt-1 space-y-1">
            {charge.payments.map(payment => <li key={payment.id}>
              Receipt #{payment.receipt_id} · {payment.received_on}
              {" · "}${payment.amount} · {payment.status}
              {payment.reversal_receipt_id !== null &&
                " · Reversal receipt #" + payment.reversal_receipt_id}
            </li>)}
          </ol>}
        </li>)}
      </ol>
    </div>)}
  </section>;
}
