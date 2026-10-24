"use client";

import { useEffect, useRef, useState } from "react";
import { apiFetch, apiGet, apiPost } from "@/lib/api";

type Evidence = { attachment_id: number; filename: string };
type CaseRow = {
  association_id: number; property_id: number; case_id: number;
  proposed_fine: string; member_user_id: number; service_record_id: number;
  policy_revision: number; cure_earliest_on: string; hearing_request_earliest_on: string;
  hearing_record_id: number | null;
  hearing_disposition: "NO_REQUEST_RECORDED" | "HEARING_HELD" | null;
  hearing_held_on: string | null;
  private_evidence: Evidence[];
};
type Hearing = {
  id: number; disposition: "NO_REQUEST_RECORDED" | "HEARING_HELD";
  held_on: string | null; record_attachment_id: number | null;
};
type Fine = { id: number; decision: "APPROVED" | "DENIED"; status: string };

export default function HoaBoardViolationFineCasesPanel() {
  const [rows, setRows] = useState<CaseRow[]>([]);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [hearingChoice, setHearingChoice] = useState<Record<number, "NO_REQUEST_RECORDED" | "HEARING_HELD">>({});
  const [hearingOn, setHearingOn] = useState<Record<number, string>>({});
  const [hearingProof, setHearingProof] = useState<Record<number, string>>({});
  const [fineChoice, setFineChoice] = useState<Record<number, "APPROVED" | "DENIED">>({});
  const [fineAmount, setFineAmount] = useState<Record<number, string>>({});
  const [fineNote, setFineNote] = useState<Record<number, string>>({});
  const hearingKeys = useRef<Record<number, string>>({});
  const fineKeys = useRef<Record<number, string>>({});

  async function reload() {
    const result = await apiGet("/api/hoa/board/my-violation-fine-cases") as CaseRow[];
    setRows(result);
  }

  useEffect(() => {
    let live = true;
    void (apiGet("/api/hoa/board/my-violation-fine-cases") as Promise<CaseRow[]>)
      .then(result => { if (live) setRows(result); })
      .catch(cause => {
        if (live) setError(cause instanceof Error ? cause.message : "Board violation cases unavailable.");
      }).finally(() => { if (live) setLoading(false); });
    return () => { live = false; };
  }, []);

  async function downloadEvidence(row: CaseRow, evidence: Evidence) {
    if (busy) return;
    setBusy(true); setError(""); setMessage("");
    try {
      const response = await apiFetch(
        "/api/hoa/board/violation-cases/" + row.case_id + "/evidence/" + evidence.attachment_id,
        { method: "GET" },
      );
      if (!response.ok) throw new Error("Private case evidence unavailable or board access revoked.");
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url; link.download = evidence.filename || ("hoa-case-evidence-" + evidence.attachment_id);
      document.body.appendChild(link); link.click(); link.remove(); URL.revokeObjectURL(url);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Private case evidence unavailable.");
    } finally { setBusy(false); }
  }

  async function recordHearing(row: CaseRow) {
    if (busy || row.hearing_record_id) return;
    const disposition = hearingChoice[row.case_id] || "NO_REQUEST_RECORDED";
    const heldOn = hearingOn[row.case_id] || "";
    const proof = hearingProof[row.case_id] || "";
    if (disposition === "HEARING_HELD" && (!heldOn || !proof)) return;
    if (!window.confirm("Record this association hearing outcome? This does not create a fine or accounting entry.")) return;
    if (!hearingKeys.current[row.case_id]) hearingKeys.current[row.case_id] = window.crypto.randomUUID();
    setBusy(true); setError(""); setMessage("");
    try {
      await apiPost(
        "/api/hoa/associations/" + row.association_id + "/staff-cases/" + row.case_id + "/hearing-record",
        {
          property_id: row.property_id, disposition,
          held_on: disposition === "HEARING_HELD" ? heldOn : null,
          record_attachment_id: disposition === "HEARING_HELD" ? Number(proof) : null,
          request_key: hearingKeys.current[row.case_id],
        },
      ) as Hearing;
      delete hearingKeys.current[row.case_id];
      setMessage("Association hearing outcome recorded. No fine or GL entry was created.");
      await reload();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Hearing outcome rejected.");
    } finally { setBusy(false); }
  }

  async function recordFine(row: CaseRow) {
    if (busy || !row.hearing_record_id || !row.hearing_disposition) return;
    const decision = fineChoice[row.case_id] || "APPROVED";
    const amount = fineAmount[row.case_id] || row.proposed_fine;
    const note = (fineNote[row.case_id] || "").trim();
    if (!note || (decision === "APPROVED" && !amount)) return;
    if (!window.confirm("Record this final association board fine decision? No money posts until the separate accounting action.")) return;
    if (!fineKeys.current[row.case_id]) fineKeys.current[row.case_id] = window.crypto.randomUUID();
    setBusy(true); setError(""); setMessage("");
    try {
      await apiPost(
        "/api/hoa/associations/" + row.association_id + "/staff-cases/" + row.case_id + "/fine/board-decision",
        {
          property_id: row.property_id, decision,
          amount: decision === "APPROVED" ? amount : null,
          member_user_id: decision === "APPROVED" ? row.member_user_id : null,
          decision_note: note,
          hearing_record_id: row.hearing_record_id,
          hearing_disposition: row.hearing_disposition,
          hearing_held_on: row.hearing_held_on,
          request_key: fineKeys.current[row.case_id],
        },
      ) as Fine;
      delete fineKeys.current[row.case_id];
      setMessage("Final board fine decision recorded. No GL entry was posted.");
      await reload();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Final fine decision rejected.");
    } finally { setBusy(false); }
  }

  return <section className="space-y-3 rounded border bg-white p-4">
    <h2 className="font-semibold">Board violation hearings and fines</h2>
    <p className="text-xs text-slate-600">
      Only FINE PROPOSED cases for your current association board authority appear.
      Hearing and final fine decisions are separate recorded board actions. Neither action
      posts money; an authorized accounting user separately posts an approved fine.
    </p>
    {loading && <p className="text-xs">Loading delegated violation cases…</p>}
    {error && <p role="alert" className="text-red-700">{error}</p>}
    {message && <p role="status" className="text-green-800">{message}</p>}
    {!loading && rows.length === 0 && !error &&
      <p className="text-sm">No proposed fines require action for your authorized board seats.</p>}
    {rows.map(row => {
      const disposition = hearingChoice[row.case_id] || "NO_REQUEST_RECORDED";
      const decision = fineChoice[row.case_id] || "APPROVED";
      return <article key={row.case_id} className="space-y-2 rounded border bg-slate-50 p-3 text-sm">
        <h3 className="font-medium">Violation case #{row.case_id}</h3>
        <p className="text-xs">
          Association #{row.association_id} · Property #{row.property_id} · Member #{row.member_user_id}
          {" · "}Service #{row.service_record_id} · Procedure rev {row.policy_revision}
        </p>
        <p className="text-xs">
          Proposed fine {row.proposed_fine} · Cure date {row.cure_earliest_on}
          {" · "}Hearing-request date {row.hearing_request_earliest_on}
        </p>
        {row.private_evidence.length > 0 && <div className="space-y-1">
          <p className="text-xs font-medium">Private case evidence</p>
          {row.private_evidence.map(evidence =>
            <button key={evidence.attachment_id} type="button" disabled={busy}
              onClick={() => { void downloadEvidence(row, evidence); }}
              className="mr-3 text-blue-700 disabled:opacity-50">
              Download {evidence.filename}
            </button>
          )}
        </div>}
        {!row.hearing_record_id ? <div className="space-y-2 border-t pt-2">
          <label className="block">Association hearing outcome
            <select aria-label={"Board violation hearing outcome " + row.case_id}
              value={disposition}
              onChange={event => setHearingChoice(prior => ({
                ...prior, [row.case_id]: event.target.value as "NO_REQUEST_RECORDED" | "HEARING_HELD",
              }))} className="mt-1 block rounded border p-2">
              <option value="NO_REQUEST_RECORDED">No hearing request recorded after configured window</option>
              <option value="HEARING_HELD">Hearing held with private case record</option>
            </select>
          </label>
          {disposition === "HEARING_HELD" && <label className="block">Date hearing held
            <input type="date" aria-label={"Board hearing held date " + row.case_id}
              value={hearingOn[row.case_id] || ""}
              onChange={event => setHearingOn(prior => ({ ...prior, [row.case_id]: event.target.value }))}
              className="mt-1 block rounded border p-2"/>
          </label>}
          {disposition === "HEARING_HELD" && <label className="block">Private hearing record
            <select aria-label={"Board hearing evidence " + row.case_id}
              value={hearingProof[row.case_id] || ""}
              onChange={event => setHearingProof(prior => ({ ...prior, [row.case_id]: event.target.value }))}
              className="mt-1 block rounded border p-2">
              <option value="">Select private case evidence</option>
              {row.private_evidence.map(evidence =>
                <option key={evidence.attachment_id} value={evidence.attachment_id}>{evidence.filename}</option>
              )}
            </select>
          </label>}
          <button type="button" disabled={busy ||
              (disposition === "HEARING_HELD" && (!(hearingOn[row.case_id]) || !(hearingProof[row.case_id])))}
            onClick={() => { void recordHearing(row); }}
            className="rounded bg-slate-800 px-3 py-2 text-white disabled:opacity-50">
            Record board hearing outcome
          </button>
        </div> : <div className="space-y-2 border-t pt-2">
          <p className="text-xs">
            Hearing record #{row.hearing_record_id}: {row.hearing_disposition}
            {row.hearing_held_on ? " · " + row.hearing_held_on : ""}.
          </p>
          <label className="block">Final board fine decision
            <select aria-label={"Board violation fine decision " + row.case_id}
              value={decision}
              onChange={event => setFineChoice(prior => ({
                ...prior, [row.case_id]: event.target.value as "APPROVED" | "DENIED",
              }))} className="mt-1 block rounded border p-2">
              <option value="APPROVED">APPROVED</option><option value="DENIED">DENIED</option>
            </select>
          </label>
          {decision === "APPROVED" && <label className="block">Approved fine amount
            <input type="number" min="0.01" step="0.01"
              aria-label={"Board violation fine amount " + row.case_id}
              value={fineAmount[row.case_id] ?? row.proposed_fine}
              onChange={event => setFineAmount(prior => ({ ...prior, [row.case_id]: event.target.value }))}
              className="mt-1 block rounded border p-2"/>
          </label>}
          <label className="block">Board decision explanation
            <textarea maxLength={1500} aria-label={"Board violation fine explanation " + row.case_id}
              value={fineNote[row.case_id] || ""}
              onChange={event => setFineNote(prior => ({ ...prior, [row.case_id]: event.target.value }))}
              className="mt-1 block w-full rounded border p-2"/>
          </label>
          <button type="button" disabled={busy || !(fineNote[row.case_id] || "").trim()}
            onClick={() => { void recordFine(row); }}
            className="rounded bg-teal-900 px-3 py-2 text-white disabled:opacity-50">
            Record final board fine decision
          </button>
        </div>}
      </article>;
    })}
  </section>;
}
