"use client";

import { useEffect, useRef, useState } from "react";
import { apiGet, apiPost } from "@/lib/api";

type Draft = {
  id: number; revision: number; subject: string; body: string;
  policy_revision: number; recipient_user_id: number;
  stage_snapshot: string; draft_notice_on: string | null;
  tentative_cure_on: string | null; prepared_at: string;
  recipient_reference_current: boolean;
  policy_revision_current: boolean; case_stage_current: boolean;
  status: "STAFF_DRAFT_NOT_SENT";
};

type Policy = { draft_notice_text: string | null; revision: number } | null;
type Delivery = {
  id: number; correspondence_id: number; correspondence_revision: number;
  status: "PENDING" | "SENDING" | "TEST_ONLY" | "SMTP_ACCEPTED" | "FAILED";
  attempt_count: number; smtp_accepted_at: string | null;
};

export default function HoaCaseCorrespondencePanel({
  associationId, propertyId, caseId, stage, canEdit, onClose,
}: {
  associationId: number; propertyId: number; caseId: number;
  stage: string; canEdit: boolean; onClose: () => void;
}) {
  const [drafts, setDrafts] = useState<Draft[]>([]);
  const [deliveries, setDeliveries] = useState<Delivery[]>([]);
  const requestKey = useRef("");
  const [subject, setSubject] = useState("");
  const [body, setBody] = useState("");
  const [policy, setPolicy] = useState<Policy>(null);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const root = "/api/hoa/associations/" + associationId;
  const base = root + "/staff-cases/" + caseId + "/correspondence";
  const query = "?property_id=" + propertyId;
  useEffect(() => {
    let alive = true;
    void Promise.all([
      apiGet(base + query) as Promise<Draft[]>,
      apiGet(root + "/procedure-policy" + query) as Promise<Policy>,
      apiGet(root + "/staff-cases/" + caseId + "/notice-emails" + query) as Promise<Delivery[]>,
    ]).then(([records, settings, sent]) => {
      if (!alive) return;
      setDrafts(records); setPolicy(settings); setDeliveries(sent);
    }).catch((cause) => {
      if (alive) setError(cause instanceof Error ? cause.message : "Private staff correspondence unavailable.");
    });
    return () => { alive = false; };
  }, [base, query, root]);

  async function record(event: React.FormEvent) {
    event.preventDefault();
    if (!canEdit || busy || !subject.trim() || !body.trim()) return;
    setBusy(true); setError(""); setMessage("");
    try {
      await apiPost(base, {
        property_id: propertyId, subject: subject.trim(), body: body.trim(),
      });
      const next = await apiGet(base + query) as Draft[];
      setDrafts(next); setSubject(""); setBody("");
      setMessage("Private correspondence draft recorded. Nothing sent or charged.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Cannot prepare staff correspondence.");
    } finally { setBusy(false); }
  }

  async function send(draft: Draft) {
    if (!canEdit || busy) return;
    if (!window.confirm("As an authorized association board member, send this exact current correspondence by email? SMTP acceptance does not prove legal service.")) return;
    if (!requestKey.current) requestKey.current = window.crypto.randomUUID();
    setBusy(true); setError(""); setMessage("");
    try {
      const result = await apiPost(base + "/" + draft.id + "/email", {
        property_id: propertyId, correspondence_revision: draft.revision,
        policy_revision: draft.policy_revision, request_key: requestKey.current,
      }) as Delivery;
      requestKey.current = "";
      setDeliveries(await apiGet(root + "/staff-cases/" + caseId + "/notice-emails" + query) as Delivery[]);
      setMessage(result.status === "SMTP_ACCEPTED"
        ? "Email accepted by SMTP. This does not prove receipt or statutory service."
        : result.status === "TEST_ONLY" ? "Console test only; no email delivered."
        : "Email request recorded. Check transport status before retrying.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Email request not recorded.");
      void apiGet(root + "/staff-cases/" + caseId + "/notice-emails" + query)
        .then(rows => setDeliveries(rows as Delivery[])).catch(() => {});
    } finally { setBusy(false); }
  }

  async function retry(delivery: Delivery) {
    if (!canEdit || busy || delivery.status === "SMTP_ACCEPTED") return;
    if (!window.confirm("Retry this same approved email? Prior SMTP delivery may be uncertain.")) return;
    setBusy(true); setError(""); setMessage("");
    try {
      const result = await apiPost(root + "/staff-cases/" + caseId + "/notice-emails/" + delivery.id + "/retry" + query) as Delivery;
      setDeliveries(await apiGet(root + "/staff-cases/" + caseId + "/notice-emails" + query) as Delivery[]);
      setMessage(result.status === "SMTP_ACCEPTED" ? "SMTP accepted this email, not proof of statutory service."
        : "Email attempt recorded: " + result.status);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Cannot retry email."); }
    finally { setBusy(false); }
  }

  const openStage = ["NOTICE_DRAFT", "CURE_TRACKING", "HEARING_PLANNED", "FINE_PROPOSED"].includes(stage);
  return (
    <section className="space-y-3 rounded border border-amber-200 bg-amber-50 p-3 text-sm">
      <div className="flex items-center justify-between gap-2">
        <h4 className="font-semibold">Private case correspondence · #{caseId}</h4>
        <button type="button" className="text-blue-700" onClick={onClose}>Close correspondence</button>
      </div>
      <p className="text-xs text-amber-900">
        Internal record only. A draft is not a delivered statutory notice and
        creates no enforceable cure deadline, fine, charge or ledger posting.
        Preparing a draft requires a live verified-login potential recipient,
        but that login alone does not establish legal recipient liability.
      </p>
      {error && <p role="alert" className="text-red-700">{error}</p>}
      {message && <p role="status" className="text-emerald-700">{message}</p>}
      {drafts.length === 0 && <p className="text-xs">No recorded correspondence drafts.</p>}
      <ol className="space-y-2">
        {drafts.map((draft) => (
          <li key={draft.id} className="space-y-1 rounded border bg-white p-2">
            <p className="font-medium">Draft #{draft.revision}: {draft.subject}</p>
            <p className="text-xs text-slate-600">
              Procedure revision {draft.policy_revision} · Stage {draft.stage_snapshot.replaceAll("_", " ")} ·
              Potential recipient user #{draft.recipient_user_id}
            </p>
            <p className="whitespace-pre-wrap text-xs">{draft.body}</p>
            <p className="text-xs text-amber-800">STAFF DRAFT · NOT SENT AS STATUTORY NOTICE. Email transport is tracked separately.</p>
            {deliveries.filter(d => d.correspondence_id === draft.id).map(delivery => (
              <div key={delivery.id} className="space-y-1 rounded border border-teal-200 p-2 text-xs">
                <p>Email attempt #{delivery.id}: {delivery.status} · Attempts {delivery.attempt_count}.
                  SMTP acceptance does not establish statutory service.</p>
                {canEdit && delivery.status !== "SMTP_ACCEPTED" && (
                  <button type="button" disabled={busy} onClick={() => { void retry(delivery); }}
                    className="text-blue-700 disabled:opacity-50">Retry authorized email</button>
                )}
              </div>
            ))}
            {canEdit && draft.id === drafts[drafts.length - 1]?.id &&
              draft.recipient_reference_current && draft.policy_revision_current &&
              draft.case_stage_current && stage !== "FINE_PROPOSED" &&
              !deliveries.some(d => d.correspondence_id === draft.id) && (
                <button type="button" disabled={busy} onClick={() => { void send(draft); }}
                  className="text-blue-700 disabled:opacity-50">
                  Board-authorize and email this correspondence
                </button>
              )}
            {(!draft.recipient_reference_current || !draft.policy_revision_current || !draft.case_stage_current) && (
              <p className="text-xs text-red-700">Historical draft is stale: recipient, procedure or case stage changed. Review before preparing a new version.</p>
            )}
          </li>
        ))}
      </ol>
      {canEdit && openStage && (
        <form onSubmit={(event) => { void record(event); }} className="space-y-2 border-t pt-3">
          <label className="block text-xs">Internal correspondence subject
            <input required maxLength={200} value={subject}
              onChange={(event) => setSubject(event.target.value)}
              className="mt-1 block w-full rounded border bg-white p-2" />
          </label>
          <label className="block text-xs">Internal correspondence body (never sent)
            <textarea required maxLength={4000} value={body} rows={4}
              onChange={(event) => setBody(event.target.value)}
              className="mt-1 block w-full rounded border bg-white p-2" />
          </label>
          {policy?.draft_notice_text && (
            <button type="button" disabled={busy}
              onClick={() => setBody(policy.draft_notice_text || "")}
              className="text-xs text-blue-700">
              Use configured staff draft text (revision {policy.revision})
            </button>
          )}
          <button type="submit" disabled={busy || !subject.trim() || !body.trim()}
            className="block rounded bg-slate-900 px-3 py-2 text-white disabled:opacity-50">
            Record private draft only
          </button>
        </form>
      )}
    </section>
  );
}
