"use client";

import { useEffect, useRef, useState } from "react";
import { apiGet, apiPost } from "@/lib/api";

type Cash = { id: number; number: string; name: string };
type Payment = {
  id: number; amount: string; received_on: string; payment_reference: string;
  receipt_id: number; status: "POSTED" | "REVERSED";
  reversal_receipt_id: number | null; manually_recorded: true;
  bank_collection_executed: false;
};

export default function HoaMemberPaymentsPanel({
  associationId, propertyId, proposalId, chargeId, memberId,
  amount, amountPaid, status, canEdit, onChange,
}: {
  associationId: number; propertyId: number; proposalId: number;
  chargeId: number; memberId: number; amount: string; amountPaid: string;
  status: "OPEN" | "PAID" | "REVERSED";
  canEdit: boolean; onChange: () => void;
}) {
  const base = "/api/hoa/associations/" + associationId +
    "/draft-assessments/" + proposalId + "/member-ledger/" + chargeId;
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
    setPayments(await apiGet(base + "/payments" + query) as Payment[]);
  }

  useEffect(() => {
    let active = true;
    void Promise.all([
      apiGet(base + "/payments" + query) as Promise<Payment[]>,
      canEdit ? apiGet(base + "/cash-options" + query) as Promise<Cash[]> : Promise.resolve([]),
    ]).then(([rows, accounts]) => {
      if (!active) return;
      setPayments(rows);
      setCashOptions(accounts);
    }).catch((cause) => {
      if (active) setError(cause instanceof Error ? cause.message : "Member receipts unavailable.");
    });
    return () => { active = false; };
  }, [base, query, canEdit]);

  function change(setter: (value: string) => void, value: string) {
    requestKey.current = "";
    setter(value);
  }

  async function record(event: React.FormEvent) {
    event.preventDefault();
    if (!canEdit || busy || !cashId || !receivedOn || !receivedAmount || !reference.trim()) return;
    if (!window.confirm("Record an ALREADY RECEIVED offline member payment and post its balanced cash/receivable entry? This does not collect bank funds.")) return;
    if (!requestKey.current) requestKey.current = window.crypto.randomUUID();
    setBusy(true); setError(""); setMessage("");
    try {
      await apiPost(base + "/payments", {
        property_id: propertyId, member_user_id: memberId,
        cash_gl_account_id: Number(cashId), amount: receivedAmount,
        received_on: receivedOn, payment_reference: reference.trim(),
        idempotency_key: requestKey.current,
      });
      requestKey.current = "";
      setReceivedAmount(""); setReceivedOn(""); setReference("");
      await reload();
      onChange();
      setMessage("Received offline member payment recorded in the receipt register and central GL. No bank collection was initiated.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Member receipt could not be recorded.");
      await reload().catch(() => {});
    } finally { setBusy(false); }
  }

  async function reverse(payment: Payment) {
    if (!canEdit || busy || !reversalOn || reversalReason.trim().length < 3) return;
    if (!window.confirm("Reverse this member receipt and restore the outstanding HOA balance by an immutable GL entry?")) return;
    setBusy(true); setError(""); setMessage("");
    try {
      await apiPost(base + "/payments/" + payment.id + "/reverse", {
        property_id: propertyId, reversal_on: reversalOn,
        reason: reversalReason.trim(),
      });
      setReversalOn(""); setReversalReason("");
      await reload();
      onChange();
      setMessage("Member receipt reversed in the central GL. No bank transfer or processor refund was executed.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Member receipt reversal was rejected.");
      await reload().catch(() => {});
    } finally { setBusy(false); }
  }

  const remaining = Math.max(0, Number(amount) - Number(amountPaid));
  return <section className="mt-2 space-y-2 rounded border border-teal-200 p-2 text-xs">
    <h6 className="font-semibold">HOA member payments and receipt allocation</h6>
    <p>Outstanding ${remaining.toFixed(2)}. Record only money already received.
      This stores an actual receipt and central GL cash/receivable posting,
      not a bank collection or a tenant Charge.</p>
    {error && <p role="alert" className="text-red-700">{error}</p>}
    {message && <p role="status" className="text-green-700">{message}</p>}
    {payments.length === 0 && <p>No member payments recorded.</p>}
    {payments.map((payment) => <div className="space-y-1 rounded border bg-white p-2" key={payment.id}>
      <p>Receipt #{payment.receipt_id} · {payment.received_on} ·
        ${payment.amount} · {payment.payment_reference} · {payment.status}</p>
      {payment.reversal_receipt_id && <p>Reversal receipt #{payment.reversal_receipt_id}</p>}
      {canEdit && payment.status === "POSTED" && <>
        <label className="block">HOA receipt reversal date
          <input type="date" value={reversalOn} onChange={e => setReversalOn(e.target.value)}
            className="mt-1 block rounded border bg-white p-2" />
        </label>
        <label className="block">HOA receipt reversal reason
          <textarea maxLength={600} value={reversalReason}
            onChange={e => setReversalReason(e.target.value)}
            className="mt-1 block w-full rounded border bg-white p-2" />
        </label>
        <button type="button" disabled={busy || !reversalOn || reversalReason.trim().length < 3}
          onClick={() => { void reverse(payment); }}
          className="text-red-700 disabled:opacity-50">Reverse HOA payment</button>
      </>}
    </div>)}
    {canEdit && status !== "REVERSED" && remaining > 0 && <form onSubmit={event => { void record(event); }}
      className="space-y-2 border-t pt-2">
      <label className="block">HOA payment cash GL
        <select required value={cashId}
          onChange={event => change(setCashId, event.target.value)}
          className="mt-1 block w-full rounded border bg-white p-2">
          <option value="">Select existing cash GL</option>
          {cashOptions.map(a => <option key={a.id} value={a.id}>{a.number} · {a.name}</option>)}
        </select>
      </label>
      <label className="block">HOA received amount
        <input type="number" required min="0.01" step="0.01" max={remaining.toFixed(2)}
          value={receivedAmount} onChange={event => change(setReceivedAmount, event.target.value)}
          className="mt-1 block rounded border bg-white p-2" />
      </label>
      <label className="block">HOA received on
        <input type="date" required value={receivedOn}
          onChange={event => change(setReceivedOn, event.target.value)}
          className="mt-1 block rounded border bg-white p-2" />
      </label>
      <label className="block">HOA payment reference
        <input required maxLength={60} value={reference}
          onChange={event => change(setReference, event.target.value)}
          className="mt-1 block w-full rounded border bg-white p-2" />
      </label>
      <button type="submit" disabled={busy || !cashId || !receivedAmount || !receivedOn || reference.trim().length < 3}
        className="rounded bg-teal-900 px-2 py-1 text-white disabled:opacity-50">
        Record received HOA payment
      </button>
    </form>}
  </section>;
}
