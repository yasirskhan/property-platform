"use client";

import { useEffect, useRef, useState } from "react";
import { apiGet, apiPost } from "@/lib/api";

type Cash = { id: number; number: string; name: string };
type Payment = {
  id: number; fine_id: number; amount: string; received_on: string;
  payment_reference: string; receipt_id: number; status: "POSTED" | "REVERSED";
  reversal_receipt_id: number | null; manually_recorded: true;
  bank_collection_executed: false;
};

export default function HoaCaseFinePaymentsPanel({
  associationId, propertyId, caseId, memberId, amount, amountPaid, onChange,
}: {
  associationId: number; propertyId: number; caseId: number;
  memberId: number; amount: string; amountPaid: string; onChange: () => void;
}) {
  const base = "/api/hoa/associations/" + associationId +
    "/staff-cases/" + caseId + "/fine/payments";
  const query = "?property_id=" + propertyId;
  const [payments, setPayments] = useState<Payment[]>([]);
  const [cashOptions, setCashOptions] = useState<Cash[]>([]);
  const [cashId, setCashId] = useState("");
  const [receivedOn, setReceivedOn] = useState("");
  const [receivedAmount, setReceivedAmount] = useState("");
  const [reference, setReference] = useState("");
  const [reversalOn, setReversalOn] = useState("");
  const [reversalReason, setReversalReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const requestKey = useRef("");

  async function reload() {
    setPayments(await apiGet(base + query) as Payment[]);
  }

  useEffect(() => {
    let live = true;
    void Promise.all([
      apiGet(base + query) as Promise<Payment[]>,
      apiGet(base + "/cash-options" + query) as Promise<Cash[]>,
    ]).then(([rows, accounts]) => {
      if (!live) return;
      setPayments(rows); setCashOptions(accounts);
    }).catch(cause => {
      if (live) setError(cause instanceof Error ? cause.message : "Fine payment history unavailable.");
    });
    return () => { live = false; };
  }, [base, query]);

  async function record(event: React.FormEvent) {
    event.preventDefault();
    if (busy || !cashId || !receivedOn || !receivedAmount || !reference.trim()) return;
    if (!window.confirm("Confirm the member funds were actually received offline? This posts a real receipt to the central GL.")) return;
    if (!requestKey.current) requestKey.current = window.crypto.randomUUID();
    setBusy(true); setError(""); setMessage("");
    try {
      await apiPost(base, {
        property_id: propertyId, member_user_id: memberId,
        cash_gl_account_id: Number(cashId), received_on: receivedOn,
        amount: receivedAmount, payment_reference: reference.trim(),
        idempotency_key: requestKey.current,
      });
      requestKey.current = "";
      await reload();
      onChange();
      setReceivedAmount(""); setReference("");
      setMessage("Fine payment posted as a receipt in the central GL. No bank collection initiated.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Cannot record fine receipt.");
    } finally { setBusy(false); }
  }

  async function reverse(payment: Payment) {
    if (busy || !reversalOn || !reversalReason.trim()) return;
    if (!window.confirm("Reverse this fine receipt and GL allocation? Deposited receipts must be reconciled first.")) return;
    setBusy(true); setError(""); setMessage("");
    try {
      await apiPost(base + "/" + payment.id + "/reverse", {
        property_id: propertyId, reversal_on: reversalOn,
        reason: reversalReason.trim(),
      });
      await reload(); onChange();
      setMessage("Fine receipt reversed in the central GL; historical records retained.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Fine receipt reversal rejected.");
    } finally { setBusy(false); }
  }

  const outstanding = Math.max(0, Number(amount) - Number(amountPaid));
  return <div className="space-y-2 border-t pt-2">
    <h5 className="font-semibold">Recorded fine payments</h5>
    <p>Member #{memberId} · Approved ${amount} · Received ${amountPaid}
      {" · "}Outstanding ${outstanding.toFixed(2)}</p>
    <p>Only record money already received. This does not charge a card or move bank funds.</p>
    {error && <p role="alert" className="text-red-700">{error}</p>}
    {message && <p role="status" className="text-green-800">{message}</p>}
    <form onSubmit={event => { void record(event); }} className="space-y-2">
      <label className="block">Fine payment cash GL
        <select aria-label="Fine payment cash GL" value={cashId} onChange={e => setCashId(e.target.value)}
          className="mt-1 block rounded border p-2">
          <option value="">Select cash GL</option>
          {cashOptions.map(a => <option key={a.id} value={a.id}>{a.number} · {a.name}</option>)}
        </select>
      </label>
      <label className="block">Fine received on
        <input aria-label="Fine received on" type="date" value={receivedOn}
          onChange={e => setReceivedOn(e.target.value)} className="mt-1 block rounded border p-2"/>
      </label>
      <label className="block">Fine received amount
        <input aria-label="Fine received amount" type="number" min="0.01" max={outstanding}
          step="0.01" value={receivedAmount} onChange={e => setReceivedAmount(e.target.value)}
          className="mt-1 block rounded border p-2"/>
      </label>
      <label className="block">Fine payment reference
        <input aria-label="Fine payment reference" maxLength={60} value={reference}
          onChange={e => setReference(e.target.value)} className="mt-1 block rounded border p-2"/>
      </label>
      <button type="submit" disabled={busy || outstanding <= 0 || !cashId ||
        !receivedOn || !Number(receivedAmount) || Number(receivedAmount) > outstanding ||
        reference.trim().length < 3}
        className="rounded bg-teal-900 px-3 py-2 text-white disabled:opacity-50">
        Record received fine payment</button>
    </form>
    <h6 className="font-semibold">Fine receipt history</h6>
    {payments.length === 0 && <p>No fine receipts yet.</p>}
    {payments.map(p => <div key={p.id} className="space-y-1 rounded border bg-white p-2">
      <p>Fine receipt #{p.receipt_id} · {p.received_on} · ${p.amount} · {p.status}
        {p.reversal_receipt_id !== null && " · Reversal receipt #" + p.reversal_receipt_id}</p>
      <p>Reference: {p.payment_reference}</p>
      {p.status === "POSTED" && <>
        <label className="block">Fine receipt reversal date
          <input aria-label="Fine receipt reversal date" type="date" value={reversalOn}
            onChange={e => setReversalOn(e.target.value)} className="mt-1 block rounded border p-2"/>
        </label>
        <label className="block">Fine receipt reversal reason
          <textarea aria-label="Fine receipt reversal reason" maxLength={600} value={reversalReason}
            onChange={e => setReversalReason(e.target.value)} className="mt-1 block rounded border p-2"/>
        </label>
        <button type="button" disabled={busy || !reversalOn || reversalReason.trim().length < 3}
          onClick={() => { void reverse(p); }} className="text-red-700 disabled:opacity-50">
          Reverse fine payment</button>
      </>}
    </div>)}
  </div>;
}
