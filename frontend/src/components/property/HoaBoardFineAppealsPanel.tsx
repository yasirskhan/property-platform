"use client";

import { useEffect, useRef, useState } from "react";
import { apiFetch, apiGet, apiPost } from "@/lib/api";
import HoaAppealNotificationPanel from "./HoaAppealNotificationPanel";

type Appeal = {
  association_id: number; property_id: number; case_id: number;
  fine_id: number; appeal_id: number; received_on: string;
  member_user_id: number; appeal_reason: string; has_private_evidence: boolean;
  status: "OPEN";
};
type FinalAppeal = {
  association_id: number; property_id: number; case_id: number;
  fine_id: number; appeal_id: number; outcome: "UPHELD" | "VACATED";
  decided_on: string; notification_status: string | null;
  has_private_evidence: boolean;
};

export default function HoaBoardFineAppealsPanel() {
  const [appeals, setAppeals] = useState<Appeal[]>([]);
  const [finalAppeals, setFinalAppeals] = useState<FinalAppeal[]>([]);
  const [notificationOpen, setNotificationOpen] = useState<number | null>(null);
  const [choices, setChoices] = useState<Record<number, "UPHELD" | "VACATED">>({});
  const [notes, setNotes] = useState<Record<number, string>>({});
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const requestKeys = useRef<Record<number, string>>({});

  async function reload() {
    const [open, decided] = await Promise.all([
      apiGet("/api/hoa/board/my-fine-appeals") as Promise<Appeal[]>,
      apiGet("/api/hoa/board/my-final-fine-appeals") as Promise<FinalAppeal[]>,
    ]);
    setAppeals(open); setFinalAppeals(decided);
  }

  useEffect(() => {
    let live = true;
    void Promise.all([
      apiGet("/api/hoa/board/my-fine-appeals") as Promise<Appeal[]>,
      apiGet("/api/hoa/board/my-final-fine-appeals") as Promise<FinalAppeal[]>,
    ]).then(([open, decided]) => {
      if (live) { setAppeals(open); setFinalAppeals(decided); }
    }).catch(cause => {
      if (live) setError(cause instanceof Error ? cause.message : "Board appeals unavailable.");
    }).finally(() => { if (live) setLoading(false); });
    return () => { live = false; };
  }, []);

  async function downloadEvidence(appeal: Appeal | FinalAppeal) {
    if (busy || !appeal.has_private_evidence) return;
    setBusy(true); setError("");
    try {
      const response = await apiFetch(
        "/api/hoa/board/fine-appeals/" + appeal.appeal_id + "/supporting-evidence",
        { method: "GET" },
      );
      if (!response.ok) throw new Error("Private board evidence is unavailable or access has been revoked.");
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = "hoa-appeal-evidence-" + appeal.appeal_id;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Private appeal evidence unavailable.");
    } finally { setBusy(false); }
  }

  async function decide(appeal: Appeal) {
    if (busy || !(notes[appeal.appeal_id] || "").trim()) return;
    const choice = choices[appeal.appeal_id] || "UPHELD";
    if (!window.confirm("Record your association board " + choice +
      " appeal disposition? Existing member payments and GL entries are not automatically reversed.")) return;
    if (!requestKeys.current[appeal.appeal_id]) {
      requestKeys.current[appeal.appeal_id] = window.crypto.randomUUID();
    }
    setBusy(true); setError(""); setMessage("");
    try {
      await apiPost("/api/hoa/associations/" + appeal.association_id +
        "/staff-cases/" + appeal.case_id + "/fine/appeals/" +
        appeal.appeal_id + "/decision", {
        property_id: appeal.property_id, result: choice,
        decision_note: notes[appeal.appeal_id].trim(),
        request_key: requestKeys.current[appeal.appeal_id],
      });
      delete requestKeys.current[appeal.appeal_id];
      await reload();
      setMessage("Your direct board appeal disposition was recorded; separate accounting correction is required if vacated.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Board disposition rejected.");
    } finally { setBusy(false); }
  }

  return <section className="space-y-3 rounded border bg-white p-4">
    <h2 className="font-semibold">Board fine appeals</h2>
    <p className="text-xs text-slate-600">
      Open and final appeals remain scoped to your currently verified
      association-specific board authority. UPHELD/VACATED records a decision,
      not a refund, mailed notice or automatic general-ledger correction.
    </p>
    {loading && <p className="text-xs">Loading board appeals…</p>}
    {error && <p role="alert" className="text-red-700">{error}</p>}
    {message && <p role="status" className="text-green-800">{message}</p>}
    {!loading && appeals.length === 0 && !error &&
      <p className="text-sm">No open appeals for your currently authorized board seats.</p>}
    {appeals.map(appeal => <article key={appeal.appeal_id}
      className="space-y-2 rounded border bg-slate-50 p-3 text-sm">
      <h3 className="font-medium">Fine appeal #{appeal.appeal_id}</h3>
      <p className="text-xs">Association #{appeal.association_id}
        {" · "}Property #{appeal.property_id} · Case #{appeal.case_id}
        {" · "}Member #{appeal.member_user_id}</p>
      <p>Received {appeal.received_on} · {appeal.status}</p>
      <p className="whitespace-pre-wrap break-words">Member appeal reason: {appeal.appeal_reason}</p>
      {appeal.has_private_evidence && <button type="button" disabled={busy}
        onClick={() => { void downloadEvidence(appeal); }}
        className="text-blue-700 disabled:opacity-50">
        Download private appeal evidence
      </button>}
      <label className="block text-sm">Board appeal disposition
        <select aria-label={"Board portal appeal outcome " + appeal.appeal_id}
          value={choices[appeal.appeal_id] || "UPHELD"}
          onChange={event => setChoices(prev => ({
            ...prev, [appeal.appeal_id]: event.target.value as "UPHELD" | "VACATED",
          }))}
          className="mt-1 block rounded border p-2">
          <option value="UPHELD">UPHELD</option>
          <option value="VACATED">VACATED</option>
        </select>
      </label>
      <label className="block text-sm">Board disposition explanation
        <textarea aria-label={"Board portal appeal explanation " + appeal.appeal_id}
          maxLength={2000} value={notes[appeal.appeal_id] || ""}
          onChange={event => setNotes(prev => ({
            ...prev, [appeal.appeal_id]: event.target.value,
          }))}
          className="mt-1 block w-full rounded border p-2"/>
      </label>
      <button type="button" disabled={busy || (notes[appeal.appeal_id] || "").trim().length < 3}
        onClick={() => { void decide(appeal); }}
        className="rounded bg-teal-900 px-3 py-2 text-white disabled:opacity-50">
        Record my board appeal decision
      </button>
    </article>)}
    <h3 className="font-semibold">Final board appeal outcomes</h3>
    <p className="text-xs text-slate-600">
      Final decision history remains available only while the board seat is
      authorized. Email delivery is separate from the decision and does not
      complete legal service or alter member receipts or general-ledger entries.
    </p>
    {finalAppeals.length === 0 && !loading && !error &&
      <p className="text-xs">No final board appeals for this authorized seat.</p>}
    {finalAppeals.map(appeal => <article key={appeal.appeal_id}
      className="space-y-2 rounded border bg-slate-50 p-3 text-sm">
      <h4 className="font-medium">Final fine appeal #{appeal.appeal_id} · {appeal.outcome}</h4>
      <p className="text-xs">Association #{appeal.association_id}
        {" · "}Property #{appeal.property_id} · Case #{appeal.case_id}
        {" · "}Board decision date {appeal.decided_on}</p>
      <p className="text-xs">Outcome email: {appeal.notification_status
        ? appeal.notification_status.replaceAll("_", " ")
        : "NOT REQUESTED"}. SMTP acceptance does not prove inbox delivery.</p>
      {appeal.has_private_evidence && <button type="button" disabled={busy}
        onClick={() => { void downloadEvidence(appeal); }}
        className="text-blue-700 disabled:opacity-50">
        Download private appeal evidence
      </button>}
      <button type="button" className="text-blue-700"
        onClick={() => setNotificationOpen(
          notificationOpen === appeal.appeal_id ? null : appeal.appeal_id
        )}>
        {notificationOpen === appeal.appeal_id
          ? "Hide final outcome email" : "Open final outcome email"}
      </button>
      {notificationOpen === appeal.appeal_id && <HoaAppealNotificationPanel
        associationId={appeal.association_id} propertyId={appeal.property_id}
        caseId={appeal.case_id} appealId={appeal.appeal_id} canEdit
        onClose={() => { setNotificationOpen(null); void reload().catch(cause => {
          setError(cause instanceof Error ? cause.message : "Final appeal history unavailable.");
        }); }}/>}
    </article>)}
  </section>;
}
