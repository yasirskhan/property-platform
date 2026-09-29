"use client";

import { useEffect, useRef, useState } from "react";
import { apiGet, apiPost } from "@/lib/api";
import HoaCaseFinePaymentsPanel from "@/components/property/HoaCaseFinePaymentsPanel";
import HoaCaseFineAppealsPanel from "@/components/property/HoaCaseFineAppealsPanel";

type Fine = {
  id: number; decision: "APPROVED" | "DENIED";
  status: "APPROVED" | "DENIED" | "POSTED" | "REVERSED";
  amount: string | null; amount_paid: string; member_user_id: number | null;
  policy_revision: number; service_record_id: number;
  gl_transaction_id: number | null; reversal_transaction_id: number | null;
  hearing_disposition: string; decided_on: string; decision_note: string;
};
type Service = { id: number; member_user_id: number; cure_earliest_on: string;
  hearing_request_earliest_on: string };
type Proof = { attachment_id: number; filename: string };
type GL = { id: number; number: string; name: string; account_type: string };

export default function HoaCaseFinePanel({
  associationId, propertyId, caseId, stage, proposedFine, canEdit, onClose,
}: {
  associationId: number; propertyId: number; caseId: number;
  stage: string; proposedFine: string | null; canEdit: boolean; onClose: () => void;
}) {
  const root = "/api/hoa/associations/" + associationId;
  const base = root + "/staff-cases/" + caseId;
  const query = "?property_id=" + propertyId;
  const [fine, setFine] = useState<Fine | null>(null);
  const [appealsOpen, setAppealsOpen] = useState(false);
  const [service, setService] = useState<Service | null>(null);
  const [proofs, setProofs] = useState<Proof[]>([]);
  const [accounts, setAccounts] = useState<GL[]>([]);
  const [choice, setChoice] = useState<"APPROVED" | "DENIED">("APPROVED");
  const [hearing, setHearing] = useState<"NO_REQUEST_RECORDED" | "HEARING_HELD">("NO_REQUEST_RECORDED");
  const [hearingProof, setHearingProof] = useState("");
  const [hearingOn, setHearingOn] = useState("");
  const [amount, setAmount] = useState("");
  const [note, setNote] = useState("");
  const [arId, setArId] = useState("");
  const [incomeId, setIncomeId] = useState("");
  const [postingOn, setPostingOn] = useState("");
  const [reversalOn, setReversalOn] = useState("");
  const [reversalReason, setReversalReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const requestKey = useRef("");

  async function reload() {
    setFine(await apiGet(base + "/fine" + query) as Fine | null);
  }

  useEffect(() => {
    let active = true;
    void Promise.all([
      apiGet(base + "/fine" + query) as Promise<Fine | null>,
      apiGet(base + "/service-record" + query) as Promise<Service | null>,
      apiGet(base + "/evidence" + query) as Promise<Proof[]>,
      canEdit ? apiGet(root + "/arc-fee-gl-options" + query) as Promise<GL[]> : Promise.resolve([]),
    ]).then(([record, delivery, files, gl]) => {
      if (!active) return;
      setFine(record); setService(delivery); setProofs(files); setAccounts(gl);
    }).catch(cause => {
      if (active) setError(cause instanceof Error ? cause.message : "Fine record unavailable.");
    });
    return () => { active = false; };
  }, [base, root, query, canEdit]);

  async function decide(event: React.FormEvent) {
    event.preventDefault();
    if (busy || !canEdit || !service || !note.trim()) return;
    if (!window.confirm("Record this final association board fine decision? No money posts until a separately authorized action.")) return;
    if (!requestKey.current) requestKey.current = window.crypto.randomUUID();
    setBusy(true); setError(""); setMessage("");
    try {
      const result = await apiPost(base + "/fine/board-decision", {
        property_id: propertyId, decision: choice,
        amount: choice === "APPROVED" ? amount : null,
        member_user_id: choice === "APPROVED" ? service.member_user_id : null,
        decision_note: note.trim(),
        hearing_disposition: hearing,
        hearing_held_on: hearing === "HEARING_HELD" ? hearingOn : null,
        hearing_record_attachment_id: hearing === "HEARING_HELD" ? Number(hearingProof) : null,
        request_key: requestKey.current,
      }) as Fine;
      requestKey.current = ""; setFine(result);
      setMessage("Association board decision recorded. No GL entry posted.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Board fine decision rejected.");
      void reload().catch(() => {});
    } finally { setBusy(false); }
  }

  async function act(path: string, payload: unknown, success: string) {
    if (busy || !canEdit || !window.confirm(success + " Confirm the accounting action.")) return;
    setBusy(true); setError(""); setMessage("");
    try {
      setFine(await apiPost(base + "/fine/" + path, payload) as Fine);
      setMessage(success);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Fine accounting action rejected.");
    } finally { setBusy(false); }
  }

  return <section className="space-y-2 rounded border border-teal-200 bg-teal-50 p-3 text-xs">
    <div className="flex items-center justify-between gap-2">
      <h4 className="font-semibold">Association violation fine decision and ledger</h4>
      <button type="button" onClick={onClose} className="text-blue-700">Close fine</button>
    </div>
    <p>An authorized board records the outcome after the association reports actual
      notice service and satisfies its configured cure/hearing procedure. An accountant
      separately posts an approved fine through the central GL. This is not a tenant charge.
      The platform does not independently certify applicable law or delivery.</p>
    {error && <p role="alert" className="text-red-700">{error}</p>}
    {message && <p role="status" className="text-green-800">{message}</p>}
    {fine?.decision === "APPROVED" && <>
      <button type="button" className="text-blue-700"
        onClick={() => setAppealsOpen(v => !v)}>
        {appealsOpen ? "Hide fine appeals" : "Fine appeals"}
      </button>
      {appealsOpen && <HoaCaseFineAppealsPanel associationId={associationId}
        propertyId={propertyId} caseId={caseId} canEdit={canEdit}
        onClose={() => setAppealsOpen(false)}/>}
    </>}
    {fine ? <div className="space-y-1 rounded border bg-white p-2">
      <p>Board decision #{fine.id}: {fine.decision} · {fine.status} · {fine.decided_on}</p>
      <p>Member #{fine.member_user_id ?? "none"} · Amount {fine.amount ?? "not assessed"}
        {" · "}Service #{fine.service_record_id} · Procedure rev {fine.policy_revision}</p>
      <p>Hearing disposition: {fine.hearing_disposition}</p>
      <p>Decision note: {fine.decision_note}</p>
      {fine.status === "POSTED" && fine.amount !== null && <p>
        Paid ${fine.amount_paid} · Outstanding ${(Number(fine.amount) - Number(fine.amount_paid)).toFixed(2)}
      </p>}
      {fine.gl_transaction_id && <p>Central GL #{fine.gl_transaction_id}
        {fine.reversal_transaction_id && " · Reversal GL #" + fine.reversal_transaction_id}</p>}
    </div> : <p>No final association fine decision recorded.</p>}
    {canEdit && !fine && service && stage === "FINE_PROPOSED" && <form
      onSubmit={event => { void decide(event); }} className="space-y-2 border-t pt-2">
      <p>Recorded service #{service.id} · Member #{service.member_user_id}
        {" · "}Configured cure date {service.cure_earliest_on}
        {" · "}Hearing-request date {service.hearing_request_earliest_on}</p>
      <label className="block">Final board decision
        <select aria-label="Violation board decision" value={choice}
          onChange={event => setChoice(event.target.value as "APPROVED" | "DENIED")}
          className="mt-1 block rounded border p-2">
          <option value="APPROVED">APPROVED</option><option value="DENIED">DENIED</option>
        </select>
      </label>
      {choice === "APPROVED" && <label className="block">Approved fine amount
        <input type="number" min="0.01" step="0.01" aria-label="Approved violation fine"
          value={amount} onChange={event => setAmount(event.target.value)}
          placeholder={proposedFine ?? ""} className="mt-1 block rounded border p-2"/>
      </label>}
      <label className="block">Association hearing disposition
        <select aria-label="Violation hearing disposition" value={hearing}
          onChange={event => setHearing(event.target.value as "NO_REQUEST_RECORDED" | "HEARING_HELD")}
          className="mt-1 block rounded border p-2">
          <option value="NO_REQUEST_RECORDED">No hearing request recorded after configured window</option>
          <option value="HEARING_HELD">Hearing held; private case proof recorded</option>
        </select>
      </label>
      {hearing === "HEARING_HELD" && <label className="block">Date hearing held
        <input aria-label="Date hearing held" type="date" value={hearingOn}
          onChange={event => setHearingOn(event.target.value)}
          className="mt-1 block rounded border p-2"/>
      </label>}
      {hearing === "HEARING_HELD" && <label className="block">Private hearing record
        <select aria-label="Private hearing record" value={hearingProof}
          onChange={event => setHearingProof(event.target.value)}
          className="mt-1 block rounded border p-2">
          <option value="">Select private case evidence</option>
          {proofs.map(p => <option key={p.attachment_id} value={p.attachment_id}>{p.filename}</option>)}
        </select>
      </label>}
      <label className="block">Board decision explanation
        <textarea maxLength={1500} value={note} onChange={event => setNote(event.target.value)}
          className="mt-1 block w-full rounded border p-2"/>
      </label>
      <button type="submit" disabled={busy || !note.trim() || (choice === "APPROVED" && !amount) ||
        (hearing === "HEARING_HELD" && (!hearingProof || !hearingOn))}
        className="rounded bg-teal-900 px-3 py-2 text-white disabled:opacity-50">
        Record final association fine decision
      </button>
    </form>}
    {canEdit && fine?.status === "APPROVED" && <div className="space-y-2 border-t pt-2">
      <h5 className="font-semibold">Post board-approved member fine</h5>
      <label className="block">GL posting date<input type="date" value={postingOn}
        onChange={event => setPostingOn(event.target.value)}
        className="mt-1 block rounded border p-2"/></label>
      <label className="block">Member receivable GL
        <select aria-label="Fine receivable GL" value={arId}
          onChange={event => setArId(event.target.value)}
          className="mt-1 block rounded border p-2">
          <option value="">Select asset GL</option>
          {accounts.filter(x => x.account_type === "ASSET").map(x =>
            <option key={x.id} value={x.id}>{x.number} · {x.name}</option>)}
        </select>
      </label>
      <label className="block">Fine income GL
        <select aria-label="Fine income GL" value={incomeId}
          onChange={event => setIncomeId(event.target.value)}
          className="mt-1 block rounded border p-2">
          <option value="">Select income GL</option>
          {accounts.filter(x => x.account_type === "INCOME").map(x =>
            <option key={x.id} value={x.id}>{x.number} · {x.name}</option>)}
        </select>
      </label>
      <button type="button" disabled={busy || !postingOn || !arId || !incomeId}
        onClick={() => { void act("post", {
          property_id: propertyId, posting_on: postingOn,
          receivable_gl_account_id: Number(arId),
          income_gl_account_id: Number(incomeId),
        }, "Post one balanced member fine receivable."); }}
        className="rounded bg-teal-900 px-3 py-2 text-white disabled:opacity-50">
        Post approved fine to member GL
      </button>
    </div>}
    {canEdit && fine?.status === "POSTED" && fine.amount !== null && fine.member_user_id !== null &&
      <HoaCaseFinePaymentsPanel associationId={associationId} propertyId={propertyId}
        caseId={caseId} memberId={fine.member_user_id} amount={fine.amount}
        amountPaid={fine.amount_paid} onChange={() => { void reload(); }} />}
    {canEdit && fine?.status === "POSTED" && Number(fine.amount_paid) === 0 && <div className="space-y-2 border-t pt-2">
      <label className="block">Fine reversal date
        <input type="date" value={reversalOn} onChange={event => setReversalOn(event.target.value)}
          className="mt-1 block rounded border p-2"/></label>
      <label className="block">Fine reversal reason
        <textarea maxLength={500} value={reversalReason}
          onChange={event => setReversalReason(event.target.value)}
          className="mt-1 block w-full rounded border p-2"/></label>
      <button type="button" disabled={busy || !reversalOn || !reversalReason.trim()}
        onClick={() => { void act("reverse", {
          property_id: propertyId, reversal_on: reversalOn, reason: reversalReason.trim(),
        }, "Reverse member fine in the central GL."); }}
        className="text-red-700 disabled:opacity-50">
        Reverse posted fine
      </button>
    </div>}
  </section>;
}
