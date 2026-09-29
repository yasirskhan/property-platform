"use client";

import { useEffect, useRef, useState } from "react";
import { apiGet, apiPost } from "@/lib/api";

type Appeal = {
  id: number; fine_id: number; received_on: string;
  appeal_reason: string; supporting_attachment_id: number | null;
  status: "OPEN" | "UPHELD" | "VACATED"; decided_on: string | null;
  decision_note: string | null; decision_board_seat_id: number | null;
  accounting_reversal_pending: boolean;
};

export default function HoaCaseFineAppealsPanel({
  associationId, propertyId, caseId, canEdit, onClose,
}: {
  associationId: number; propertyId: number; caseId: number;
  canEdit: boolean; onClose: () => void;
}) {
  const base = "/api/hoa/associations/" + associationId +
    "/staff-cases/" + caseId + "/fine/appeals";
  const query = "?property_id=" + propertyId;
  const [records, setRecords] = useState<Appeal[]>([]);
  const [receivedOn, setReceivedOn] = useState("");
  const [reason, setReason] = useState("");
  const [choice, setChoice] = useState<"UPHELD" | "VACATED">("UPHELD");
  const [decisionNote, setDecisionNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const requestKey = useRef("");
  const decisionKey = useRef("");

  async function reload() {
    setRecords(await apiGet(base + query) as Appeal[]);
  }

  useEffect(() => {
    let live = true;
    void apiGet(base + query).then(rows => {
      if (live) setRecords(rows as Appeal[]);
    }).catch(cause => {
      if (live) setError(cause instanceof Error ? cause.message : "Appeal history unavailable.");
    });
    return () => { live = false; };
  }, [base, query]);

  async function record(event: React.FormEvent) {
    event.preventDefault();
    if (!canEdit || busy || !receivedOn || !reason.trim()) return;
    if (!window.confirm("Record an appeal received by the association? This does not reverse any financial entry.")) return;
    if (!requestKey.current) requestKey.current = window.crypto.randomUUID();
    setBusy(true); setError(""); setMessage("");
    try {
      await apiPost(base, {
        property_id: propertyId, received_on: receivedOn,
        appeal_reason: reason.trim(), request_key: requestKey.current,
      });
      requestKey.current = "";
      await reload();
      setReason(""); setReceivedOn("");
      setMessage("Appeal received and recorded. No fine was reversed or notice sent.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not record fine appeal.");
    } finally { setBusy(false); }
  }

  async function decide(row: Appeal) {
    if (!canEdit || busy || !decisionNote.trim()) return;
    if (!window.confirm("Record the association board appeal decision? Any payment/refund and GL reversal remain separate authorized actions.")) return;
    if (!decisionKey.current) decisionKey.current = window.crypto.randomUUID();
    setBusy(true); setError(""); setMessage("");
    try {
      await apiPost(base + "/" + row.id + "/decision", {
        property_id: propertyId, result: choice,
        decision_note: decisionNote.trim(), request_key: decisionKey.current,
      });
      decisionKey.current = "";
      await reload();
      setDecisionNote("");
      setMessage("Board appeal disposition recorded. Accounting changes require a separate action.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Board appeal disposition rejected.");
    } finally { setBusy(false); }
  }

  const open = records.some(r => r.status === "OPEN");
  const vacated = records.some(r => r.status === "VACATED");
  return <section className="space-y-2 rounded border border-amber-200 bg-amber-50 p-3 text-xs">
    <div className="flex items-center justify-between">
      <h4 className="font-semibold">Fine appeal and correction history</h4>
      <button type="button" onClick={onClose} className="text-blue-700">Close appeals</button>
    </div>
    <p>Staff records receipt of an appeal. An authorized association board directly
      records UPHELD or VACATED. No automatic penalty adjustment, refund, member
      notice or GL transaction is created. Open/vacated appeals hold new posting
      and receipt allocations; any existing payments need separately approved corrections.</p>
    {error && <p role="alert" className="text-red-700">{error}</p>}
    {message && <p role="status" className="text-green-800">{message}</p>}
    {records.length === 0 && <p>No association appeal recorded.</p>}
    {records.map(row => <div key={row.id} className="space-y-1 rounded border bg-white p-2">
      <p className="font-semibold">Appeal #{row.id} · {row.status} · Received {row.received_on}</p>
      <p>Recorded reason: {row.appeal_reason}</p>
      {row.decision_note && <p>Board disposition: {row.decision_note}
        {" · "}Seat #{row.decision_board_seat_id} · {row.decided_on}</p>}
      {row.accounting_reversal_pending && <p className="font-semibold text-amber-800">
        Board vacated the fine, but its posted GL still requires an authorized
        reversal. Reverse allocated receipts first. Do not infer a cash refund.</p>}
      {row.status === "OPEN" && canEdit && <div className="space-y-1 border-t pt-2">
        <label className="block">Board appeal outcome
          <select aria-label="Fine appeal board outcome" value={choice}
            onChange={event => setChoice(event.target.value as "UPHELD" | "VACATED")}
            className="mt-1 block border p-2">
            <option value="UPHELD">UPHELD</option><option value="VACATED">VACATED</option>
          </select>
        </label>
        <label className="block">Board appeal explanation
          <textarea maxLength={2000} value={decisionNote}
            onChange={event => setDecisionNote(event.target.value)}
            className="mt-1 block w-full border p-2"/>
        </label>
        <button type="button" disabled={busy || !decisionNote.trim()}
          onClick={() => { void decide(row); }} className="text-blue-700 disabled:opacity-50">
          Record final board appeal decision</button>
      </div>}
    </div>)}
    {canEdit && !open && !vacated && <form onSubmit={event => { void record(event); }}
      className="space-y-2 border-t pt-2">
      <label className="block">Appeal received on
        <input type="date" aria-label="Fine appeal received date" value={receivedOn}
          onChange={event => setReceivedOn(event.target.value)}
          className="mt-1 block border p-2"/>
      </label>
      <label className="block">Received appeal reason
        <textarea maxLength={2000} value={reason} onChange={event => setReason(event.target.value)}
          className="mt-1 block w-full border p-2"/>
      </label>
      <button type="submit" disabled={busy || !receivedOn || !reason.trim()}
        className="text-blue-700 disabled:opacity-50">Record appeal received</button>
    </form>}
  </section>;
}
