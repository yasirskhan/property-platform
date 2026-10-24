"use client";

import { useEffect, useState } from "react";
import { apiGet, apiPost } from "@/lib/api";
import HoaCaseRecipientPanel from "@/components/property/HoaCaseRecipientPanel";
import HoaCaseCorrespondencePanel from "@/components/property/HoaCaseCorrespondencePanel";
import HoaCaseEvidencePanel from "@/components/property/HoaCaseEvidencePanel";
import HoaCaseServicePanel from "@/components/property/HoaCaseServicePanel";
import HoaCaseFinePanel from "@/components/property/HoaCaseFinePanel";
import HoaCaseTasksPanel from "@/components/property/HoaCaseTasksPanel";

type Observation = { id: number; summary: string; observed_on: string };
type HistoryEvent = {
  id: number;
  case_id: number;
  from_stage: string | null;
  to_stage: string;
  policy_revision: number | null;
  staff_action_on: string | null;
  tentative_cure_on: string | null;
  tentative_hearing_on: string | null;
  proposed_fine: string | null;
  staff_resolution: string | null;
  recorded_at: string;
  notice_delivered: false;
  fine_posted: false;
};
type Stage = "OPEN" | "NOTICE_DRAFT" | "CURE_TRACKING" |
  "HEARING_PLANNED" | "FINE_PROPOSED" | "RESOLVED" | "CLOSED";
type Case = {
  id: number; observation_id: number; stage: Stage;
  draft_notice_on: string | null; tentative_cure_on: string | null;
  tentative_hearing_on: string | null; proposed_fine: string | null;
  staff_resolution: string | null; policy_revision: number | null;
  notice_sent: false; fine_assessed: false; legally_adjudicated: false;
};
const NEXT: Record<Stage, Stage[]> = {
  OPEN: ["NOTICE_DRAFT", "RESOLVED"],
  NOTICE_DRAFT: ["CURE_TRACKING", "HEARING_PLANNED", "RESOLVED"],
  CURE_TRACKING: ["HEARING_PLANNED", "FINE_PROPOSED", "RESOLVED"],
  HEARING_PLANNED: ["FINE_PROPOSED", "RESOLVED"],
  FINE_PROPOSED: ["HEARING_PLANNED", "RESOLVED"],
  RESOLVED: ["CLOSED"],
  CLOSED: [],
};
const LABEL: Record<Stage, string> = {
  OPEN: "Open staff review", NOTICE_DRAFT: "Notice draft prepared (not sent)",
  CURE_TRACKING: "Tentative cure tracking", HEARING_PLANNED: "Hearing plan",
  FINE_PROPOSED: "Fine proposal (unassessed)",
  RESOLVED: "Staff-recorded resolution", CLOSED: "Staff case closed",
};

export default function HoaCaseWorkflowPanel({
  associationId, propertyId, canEdit, onClose,
}: {
  associationId: number; propertyId: number;
  canEdit: boolean; onClose: () => void;
}) {
  const [items, setItems] = useState<Case[]>([]);
  const [historyCase, setHistoryCase] = useState<number | null>(null);
  const [recipientCase, setRecipientCase] = useState<number | null>(null);
  const [correspondenceCase, setCorrespondenceCase] = useState<number | null>(null);
  const [evidenceCase, setEvidenceCase] = useState<number | null>(null);
  const [serviceCase, setServiceCase] = useState<number | null>(null);
  const [fineCase, setFineCase] = useState<number | null>(null);
  const [tasksCase, setTasksCase] = useState<number | null>(null);
  const [history, setHistory] = useState<HistoryEvent[]>([]);
  const [observations, setObservations] = useState<Observation[]>([]);
  const [selectedObservation, setSelectedObservation] = useState("");
  const [editing, setEditing] = useState<number | null>(null);
  const [next, setNext] = useState<Stage>("NOTICE_DRAFT");
  const [actionOn, setActionOn] = useState("");
  const [proposedFine, setProposedFine] = useState("");
  const [resolution, setResolution] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const root = "/api/hoa/associations/" + associationId;
  const base = root + "/staff-cases";
  const query = "?property_id=" + propertyId;

  async function reload() {
    const [cases, source] = await Promise.all([
      apiGet(base + query) as Promise<Case[]>,
      apiGet(root + "/observations" + query) as Promise<Observation[]>,
    ]);
    setItems(cases); setObservations(source);
    if (historyCase !== null) {
      setHistory(await apiGet(base + "/" + historyCase + "/history" + query) as HistoryEvent[]);
    }
  }

  useEffect(() => {
    let live = true;
    setLoading(true); setError("");
    void Promise.all([
      apiGet(base + query) as Promise<Case[]>,
      apiGet(root + "/observations" + query) as Promise<Observation[]>,
    ]).then(([records, source]) => {
      if (!live) return;
      setItems(records); setObservations(source);
    }).catch((cause) => {
      if (live) setError(cause instanceof Error ? cause.message : "HOA staff cases unavailable.");
    }).finally(() => { if (live) setLoading(false); });
    return () => { live = false; };
  }, [base, root, query]);

  async function create(event: React.FormEvent) {
    event.preventDefault();
    if (!canEdit || busy || !selectedObservation) return;
    setBusy(true); setError(""); setMessage("");
    try {
      await apiPost(base, {
        property_id: propertyId, observation_id: Number(selectedObservation),
      });
      setSelectedObservation("");
      await reload();
      setMessage("Internal staff case opened. No legal notice was issued.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to open staff case.");
    } finally { setBusy(false); }
  }

  async function toggleHistory(row: Case) {
    if (historyCase === row.id) {
      setHistoryCase(null); setHistory([]);
      return;
    }
    setBusy(true); setError("");
    try {
      setHistory(await apiGet(base + "/" + row.id + "/history" + query) as HistoryEvent[]);
      setHistoryCase(row.id);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Case history unavailable.");
    } finally { setBusy(false); }
  }

  function begin(row: Case) {
    setEditing(row.id); setNext(NEXT[row.stage][0] || "CLOSED");
    setActionOn(""); setProposedFine(""); setResolution("");
  }

  async function advance(event: React.FormEvent, row: Case) {
    event.preventDefault();
    if (!canEdit || busy || !NEXT[row.stage].includes(next)) return;
    setBusy(true); setError(""); setMessage("");
    try {
      await apiPost(base + "/" + row.id + "/advance", {
        property_id: propertyId, next_stage: next,
        action_on: next === "NOTICE_DRAFT" || next === "HEARING_PLANNED"
          ? actionOn || null : null,
        proposed_fine: next === "FINE_PROPOSED" ? proposedFine || null : null,
        staff_resolution: next === "RESOLVED" ? resolution.trim() || null : null,
      });
      await reload();
      setEditing(null);
      setMessage("Internal case stage recorded. No notice sent, fine assessed, or money posted.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Cannot change staff case stage.");
    } finally { setBusy(false); }
  }

  const unlinked = observations.filter((o) => !items.some((r) => r.observation_id === o.id));

  return (
    <section className="w-full space-y-3 rounded border bg-slate-50 p-4">
      <div className="flex items-center justify-between gap-2">
        <h3 className="text-sm font-semibold">HOA internal review cases</h3>
        <button type="button" onClick={onClose} className="text-blue-700">Close</button>
      </div>
      <p className="text-xs text-amber-800">
        Internal case stage only. A notice draft is not delivered;
        a cure target is a tentative planning date; hearing is only
        planned; a staff fine proposal is not an assessed or collectible fine.
        Staff resolution is not a legal board determination. State
        rules, recipient identity and governing authority must be
        independently reviewed before any official enforcement.
      </p>
      {loading && <p className="text-xs">Loading cases…</p>}
      {error && <p role="alert" className="text-xs text-red-700">{error}</p>}
      {message && <p role="status" className="text-xs text-green-700">{message}</p>}
      {!loading && items.length === 0 && <p className="text-xs text-slate-500">No staff cases recorded.</p>}
      {!loading && items.map((row) => (
        <div key={row.id} className="space-y-2 rounded border bg-white p-3 text-sm">
          <div className="font-medium">Case #{row.id} · {LABEL[row.stage]}</div>
          <p className="text-xs text-slate-600">
            Observation #{row.observation_id}
            {row.policy_revision !== null ? " · Staff procedure rev " + row.policy_revision : " · No rule revision"}
          </p>
          <p className="text-xs text-slate-600">
            Draft prepared: {row.draft_notice_on || "not recorded"}
            {" · "}Tentative cure: {row.tentative_cure_on || "not calculated"}
            {" · "}Hearing plan: {row.tentative_hearing_on || "not planned"}
          </p>
          {row.proposed_fine && <p className="text-xs">Unassessed fine proposal: ${row.proposed_fine}</p>}
          {row.staff_resolution && <p className="text-xs">Staff resolution: {row.staff_resolution}</p>}
          <button type="button" disabled={busy}
            onClick={() => setRecipientCase((prior) => prior === row.id ? null : row.id)}
            className="text-sm text-blue-700 disabled:opacity-50">
            {recipientCase === row.id ? "Hide potential recipient" : "Potential recipient"}
          </button>
          {recipientCase === row.id && (
            <HoaCaseRecipientPanel associationId={associationId} propertyId={propertyId}
              caseId={row.id} canEdit={canEdit && row.stage !== "CLOSED"}
              onClose={() => setRecipientCase(null)} />
          )}
          <button type="button" disabled={busy}
            onClick={() => setTasksCase((prior) => prior === row.id ? null : row.id)}
            className="text-sm text-blue-700 disabled:opacity-50">
            {tasksCase === row.id ? "Hide case follow-ups" : "Case follow-ups"}
          </button>
          {tasksCase === row.id && (
            <HoaCaseTasksPanel associationId={associationId} propertyId={propertyId}
              caseId={row.id} stage={row.stage} canEdit={canEdit}
              onClose={() => setTasksCase(null)} />
          )}
          <button type="button" disabled={busy}
            onClick={() => setFineCase((prior) => prior === row.id ? null : row.id)}
            className="text-sm text-blue-700 disabled:opacity-50">
            {fineCase === row.id ? "Hide association fine" : "Association fine"}
          </button>
          {fineCase === row.id && (
            <HoaCaseFinePanel associationId={associationId} propertyId={propertyId}
              caseId={row.id} stage={row.stage} proposedFine={row.proposed_fine}
              canEdit={canEdit} onClose={() => setFineCase(null)} />
          )}
          <button type="button" disabled={busy}
            onClick={() => setServiceCase((prior) => prior === row.id ? null : row.id)}
            className="text-sm text-blue-700 disabled:opacity-50">
            {serviceCase === row.id ? "Hide notice service" : "Notice service"}
          </button>
          {serviceCase === row.id && (
            <HoaCaseServicePanel associationId={associationId} propertyId={propertyId}
              caseId={row.id} canEdit={canEdit && row.stage !== "CLOSED"}
              onClose={() => setServiceCase(null)} />
          )}
          <button type="button" disabled={busy}
            onClick={() => setEvidenceCase((prior) => prior === row.id ? null : row.id)}
            className="text-sm text-blue-700 disabled:opacity-50">
            {evidenceCase === row.id ? "Hide private evidence" : "Private case evidence"}
          </button>
          {evidenceCase === row.id && (
            <HoaCaseEvidencePanel associationId={associationId} propertyId={propertyId}
              caseId={row.id} canEdit={canEdit && row.stage !== "CLOSED"}
              onClose={() => setEvidenceCase(null)} />
          )}
          <button type="button" disabled={busy}
            onClick={() => setCorrespondenceCase((prior) => prior === row.id ? null : row.id)}
            className="text-sm text-blue-700 disabled:opacity-50">
            {correspondenceCase === row.id ? "Hide correspondence" : "Private correspondence"}
          </button>
          {correspondenceCase === row.id && (
            <HoaCaseCorrespondencePanel associationId={associationId} propertyId={propertyId}
              caseId={row.id} stage={row.stage} canEdit={canEdit}
              onClose={() => setCorrespondenceCase(null)} />
          )}
          <button type="button" disabled={busy}
            onClick={() => { void toggleHistory(row); }}
            className="text-sm text-blue-700 disabled:opacity-50">
            {historyCase === row.id ? "Hide case history" : "Case history"}
          </button>
          {historyCase === row.id && (
            <div className="space-y-1 rounded border bg-slate-50 p-2 text-xs">
              <h4 className="font-semibold">Internal case history</h4>
              {history.length === 0 && <p>No recorded transition history for this case.</p>}
              <ol className="space-y-1">
                {history.map((item) => (
                  <li key={item.id} className="rounded border bg-white p-2">
                    <p>{(item.from_stage || "NEW").replaceAll("_", " ")} → {item.to_stage.replaceAll("_", " ")}
                      {" · "}Recorded {item.recorded_at}</p>
                    {item.policy_revision !== null &&
                      <p>Procedure revision {item.policy_revision}</p>}
                    {item.staff_action_on && <p>Staff-planned date: {item.staff_action_on}</p>}
                    {item.tentative_cure_on && <p>Tentative cure: {item.tentative_cure_on}</p>}
                    {item.tentative_hearing_on && <p>Tentative hearing: {item.tentative_hearing_on}</p>}
                    {item.proposed_fine && <p>Unassessed proposal: ${item.proposed_fine}</p>}
                    {item.staff_resolution && <p>Staff resolution: {item.staff_resolution}</p>}
                  </li>
                ))}
              </ol>
              <p className="text-amber-900">
                Recorded history does not deliver a legal notice, assess a fine
                or create a member receivable.
              </p>
            </div>
          )}
          {canEdit && NEXT[row.stage].length > 0 && (
            <button type="button" onClick={() => begin(row)}
              className="text-sm text-blue-700">Advance internal case</button>
          )}
          {canEdit && editing === row.id && NEXT[row.stage].length > 0 && (
            <form onSubmit={(event) => { void advance(event, row); }} className="space-y-2 rounded border p-3">
              <label className="block text-xs">Next staff stage
                <select value={next} onChange={(event) => setNext(event.target.value as Stage)}
                  className="mt-1 block w-full rounded border p-2">
                  {NEXT[row.stage].map((stage) => (
                    <option key={stage} value={stage}>{LABEL[stage]}</option>
                  ))}
                </select>
              </label>
              {(next === "NOTICE_DRAFT" || next === "HEARING_PLANNED") && (
                <label className="block text-xs">Staff-planned date
                  <input required type="date" value={actionOn}
                    onChange={(event) => setActionOn(event.target.value)}
                    className="mt-1 block rounded border p-2" />
                </label>
              )}
              {next === "FINE_PROPOSED" && (
                <label className="block text-xs">Proposed amount (not assessed)
                  <input required type="number" min="0.01" step="0.01" value={proposedFine}
                    onChange={(event) => setProposedFine(event.target.value)}
                    className="mt-1 block rounded border p-2" />
                </label>
              )}
              {next === "RESOLVED" && (
                <label className="block text-xs">Internal resolution note
                  <textarea required maxLength={1000} value={resolution}
                    onChange={(event) => setResolution(event.target.value)}
                    className="mt-1 block w-full rounded border p-2" />
                </label>
              )}
              <div className="flex gap-3">
                <button type="submit" disabled={busy}
                  className="rounded bg-slate-900 px-3 py-2 text-white disabled:opacity-50">
                  {busy ? "Saving…" : "Record staff stage"}
                </button>
                <button type="button" onClick={() => setEditing(null)}
                  className="text-slate-600">Cancel</button>
              </div>
            </form>
          )}
        </div>
      ))}
      {canEdit && !loading && unlinked.length > 0 && (
        <form onSubmit={(event) => { void create(event); }} className="space-y-2 border-t pt-3">
          <h4 className="text-sm font-semibold">Open a staff case from an existing observation</h4>
          <select required value={selectedObservation}
            onChange={(event) => setSelectedObservation(event.target.value)}
            className="block w-full rounded border bg-white p-2">
            <option value="">Select a staff observation</option>
            {unlinked.map((item) => (
              <option key={item.id} value={item.id}>#{item.id} · {item.summary}</option>
            ))}
          </select>
          <button type="submit" disabled={busy || !selectedObservation}
            className="rounded bg-slate-900 px-3 py-2 text-sm text-white disabled:opacity-50">
            Open internal case
          </button>
        </form>
      )}
    </section>
  );
}
