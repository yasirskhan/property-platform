"use client";

import { useEffect, useState } from "react";
import { apiGet, apiPost } from "@/lib/api";

type Decision = {
  id: number; decision: "APPROVED" | "DENIED";
  status: "APPROVED" | "DENIED" | "POSTED" | "REVERSED";
  amount: string | null; decided_on: string;
  gl_transaction_id: number | null; reversal_transaction_id: number | null;
  bank_transfer_executed: false;
};
type Action = "APPROVED" | "DENIED" | "POST" | "REVERSE";

export default function HoaReserveExecutionPanel({
  associationId, propertyId, draftId, canEdit, onChange,
}: {
  associationId: number; propertyId: number; draftId: number;
  canEdit: boolean; onChange: () => void;
}) {
  const base = "/api/hoa/associations/" + associationId +
    "/reserve-movement-drafts/" + draftId;
  const query = "?property_id=" + propertyId;
  const [decision, setDecision] = useState<Decision | null>(null);
  const [note, setNote] = useState("");
  const [recordOn, setRecordOn] = useState("");
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  async function reload() {
    setDecision(await apiGet(base + "/board-decision" + query) as Decision | null);
  }
  useEffect(() => {
    let live = true;
    void (apiGet(base + "/board-decision" + query) as Promise<Decision | null>)
      .then((row) => { if (live) setDecision(row); })
      .catch((cause) => {
        if (live) setError(cause instanceof Error ? cause.message : "Reserve decision unavailable.");
      });
    return () => { live = false; };
  }, [base, query]);

  async function perform(action: Action) {
    if (!canEdit || busy) return;
    if ((action === "APPROVED" || action === "DENIED") && note.trim().length < 3) {
      setError("Record the board decision note."); return;
    }
    if ((action === "POST" || action === "REVERSE") && !recordOn) {
      setError("Choose the transaction date."); return;
    }
    if (action === "REVERSE" && reason.trim().length < 3) {
      setError("Record a reversal reason."); return;
    }
    const confirmText = action === "POST"
      ? "Post a real, balanced reserve BOOK transfer to the general ledger? This does not move bank funds."
      : action === "REVERSE"
        ? "Post a real reversing GL transaction for this reserve BOOK transfer?"
        : "Record this final association board decision?";
    if (!window.confirm(confirmText)) return;
    setBusy(true); setError(""); setMessage("");
    try {
      if (action === "APPROVED" || action === "DENIED") {
        await apiPost(base + "/board-decision", {
          property_id: propertyId, decision: action, decision_note: note.trim(),
        });
      } else if (action === "POST") {
        await apiPost(base + "/post", {
          property_id: propertyId, transaction_on: recordOn,
        });
      } else {
        await apiPost(base + "/reverse", {
          property_id: propertyId, reversal_on: recordOn, reason: reason.trim(),
        });
      }
      await reload(); onChange();
      setNote(""); setReason("");
      setMessage(action === "POST"
        ? "Reserve book GL transfer posted. No bank transfer was executed."
        : action === "REVERSE"
          ? "Reserve book GL reversal posted. Bank transactions were not changed."
          : "Association board decision recorded.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Reserve action could not be recorded.");
      await reload().catch(() => {});
    } finally { setBusy(false); }
  }

  return <div className="mt-2 space-y-2 rounded border border-blue-200 bg-blue-50 p-2 text-xs">
    <p className="font-semibold">Board authorization and reserve book posting</p>
    {error && <p role="alert" className="text-red-700">{error}</p>}
    {message && <p role="status" className="text-green-700">{message}</p>}
    <p>Board decision: {decision ? decision.decision : "not recorded"}
      {decision && <> · Status: {decision.status} · Recorded: {decision.decided_on}</>}
    </p>
    {decision?.gl_transaction_id && <p>Posted GL transaction #{decision.gl_transaction_id}</p>}
    {decision?.reversal_transaction_id && <p>Reversing GL transaction #{decision.reversal_transaction_id}</p>}
    <p>Only general-ledger book entries are created here. Actual bank transfers, bank verification
      and statutory reserve certification are separate operations.</p>
    {canEdit && !decision && <>
      <label className="block">Board decision note
        <textarea value={note} maxLength={1500}
          onChange={(event) => setNote(event.target.value)}
          className="mt-1 block w-full rounded border bg-white p-2" />
      </label>
      <p>An active authenticated association board seat must authorize the decision.</p>
      <div className="flex flex-wrap gap-2">
        <button disabled={busy || note.trim().length < 3} type="button"
          onClick={() => { void perform("APPROVED"); }}
          className="rounded border bg-white px-2 py-1 disabled:opacity-50">
          Record board approval
        </button>
        <button disabled={busy || note.trim().length < 3} type="button"
          onClick={() => { void perform("DENIED"); }}
          className="rounded border bg-white px-2 py-1 disabled:opacity-50">
          Record board denial
        </button>
      </div>
    </>}
    {canEdit && (decision?.status === "APPROVED" || decision?.status === "POSTED") && <>
      <label className="block">GL transaction date
        <input required type="date" value={recordOn}
          onChange={(event) => setRecordOn(event.target.value)}
          className="mt-1 block rounded border bg-white p-2" />
      </label>
      {decision.status === "APPROVED" ? (
        <button type="button" disabled={busy || !recordOn}
          onClick={() => { void perform("POST"); }}
          className="rounded border bg-white px-2 py-1 disabled:opacity-50">
          Post approved reserve book transfer
        </button>
      ) : <>
        <label className="block">Reversal reason
          <textarea value={reason} maxLength={600}
            onChange={(event) => setReason(event.target.value)}
            className="mt-1 block w-full rounded border bg-white p-2" />
        </label>
        <button type="button" disabled={busy || !recordOn || reason.trim().length < 3}
          onClick={() => { void perform("REVERSE"); }}
          className="rounded border bg-white px-2 py-1 disabled:opacity-50">
          Reverse posted reserve book transfer
        </button>
      </>}
    </>}
  </div>;
}
