"use client";

import { useEffect, useMemo, useState } from "react";
import { apiDelete, apiGet, apiPost } from "@/lib/api";
import {
  listEntityAttachments, type EntityAttachment,
} from "@/lib/entityAttachments";

type ContactLink = {
  id: number;
  contact_id: number;
  contact_name: string;
};
type FeeOption = { id: number; number: string; name: string; account_type: "ASSET" | "INCOME" };
type BoardDecision = {
  id: number; decision: "APPROVED" | "DENIED"; decision_note: string;
  decided_at: string; board_seat_id: number; notification_status: string;
  member_charge_id: number | null; member_charge_amount: string | null;
  member_charge_due_on: string | null; fee_gl_transaction_id: number | null;
  work_order_id: number | null;
};
type Application = {
  id: number;
  intake_id: number;
  applicant_contact_link_id: number;
  applicant_contact_name: string;
  submitted_on: string;
  status: "SUBMITTED" | "UNDER_REVIEW" | "MORE_INFO_REQUESTED" |
    "INFO_RECEIVED" | "READY_FOR_DECISION" | "DECISION_PREPARED" | "APPROVED" | "DENIED";
  decision_preparation: "APPROVE" | "DENY" | null;
  board_decision: BoardDecision | null;
};
type Detail = Application & {
  events: { id: number; event_type: string; staff_note: string | null; created_at: string }[];
  attachments: { id: number; attachment_id: number; filename: string; recorded_at: string; private_only: true }[];
};

function privateDocument(row: EntityAttachment) {
  return !row.share_with_tenants && !row.share_with_owners
    && /\.(pdf|doc|docx)$/i.test(row.original_name);
}

const ACTIONS: Record<Application["status"], { key: string; label: string }[]> = {
  SUBMITTED: [{ key: "START_REVIEW", label: "Start staff review" }],
  UNDER_REVIEW: [
    { key: "REQUEST_MORE_INFO", label: "Request more information" },
    { key: "MARK_READY_FOR_DECISION", label: "Mark ready for decision" },
  ],
  MORE_INFO_REQUESTED: [{ key: "RECORD_INFO_RECEIVED", label: "Record information received" }],
  INFO_RECEIVED: [
    { key: "START_REVIEW", label: "Resume staff review" },
    { key: "MARK_READY_FOR_DECISION", label: "Mark ready for decision" },
  ],
  READY_FOR_DECISION: [
    { key: "PREPARE_APPROVAL", label: "Prepare approval" },
    { key: "PREPARE_DENIAL", label: "Prepare denial" },
    { key: "REQUEST_MORE_INFO", label: "Request more information" },
  ],
  DECISION_PREPARED: [
    { key: "START_REVIEW", label: "Return to review" },
    { key: "REQUEST_MORE_INFO", label: "Request more information" },
  ],
  APPROVED: [],
  DENIED: [],
};

export default function HoaARCApplicationsPanel({
  associationId, propertyId, intakeId, projectTitle, canEdit, onClose,
}: {
  associationId: number;
  propertyId: number;
  intakeId: number;
  projectTitle: string;
  canEdit: boolean;
  onClose: () => void;
}) {
  const [application, setApplication] = useState<Detail | null>(null);
  const [contacts, setContacts] = useState<ContactLink[]>([]);
  const [documents, setDocuments] = useState<EntityAttachment[]>([]);
  const [contactLinkId, setContactLinkId] = useState("");
  const [submittedOn, setSubmittedOn] = useState("");
  const [attachmentId, setAttachmentId] = useState("");
  const [note, setNote] = useState("");
  const [feeAmount, setFeeAmount] = useState("");
  const [feeDueOn, setFeeDueOn] = useState("");
  const [incomeGlId, setIncomeGlId] = useState("");
  const [receivableGlId, setReceivableGlId] = useState("");
  const [followupUnitId, setFollowupUnitId] = useState("");
  const [feeOptions, setFeeOptions] = useState<FeeOption[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const base = "/api/hoa/associations/" + associationId + "/arc-applications";
  const query = "?property_id=" + propertyId;

  async function reload() {
    const [apps, contactRows, stored] = await Promise.all([
      apiGet(base + query) as Promise<Application[]>,
      apiGet("/api/hoa/associations/" + associationId + "/contacts" + query) as Promise<ContactLink[]>,
      listEntityAttachments("properties", propertyId),
    ]);
    const found = apps.find((row) => row.intake_id === intakeId) || null;
    if (found) {
      setApplication(await apiGet(base + "/" + found.id + query) as Detail);
    } else {
      setApplication(null);
    }
    setContacts(contactRows);
    setDocuments(stored.items.filter(privateDocument));
  }

  useEffect(() => {
    let live = true;
    setLoading(true); setError(""); setMessage("");
    void Promise.all([
      apiGet(base + query) as Promise<Application[]>,
      apiGet("/api/hoa/associations/" + associationId + "/contacts" + query) as Promise<ContactLink[]>,
      listEntityAttachments("properties", propertyId),
    ]).then(async ([apps, contactRows, stored]) => {
      if (!live) return;
      const found = apps.find((row) => row.intake_id === intakeId) || null;
      let detail: Detail | null = null;
      if (found) detail = await apiGet(base + "/" + found.id + query) as Detail;
      if (!live) return;
      setApplication(detail);
      setContacts(contactRows);
      setDocuments(stored.items.filter(privateDocument));
    }).catch((cause) => {
      if (live) setError(cause instanceof Error ? cause.message : "ARC application workflow unavailable.");
    }).finally(() => { if (live) setLoading(false); });
    return () => { live = false; };
  }, [associationId, propertyId, intakeId, base, query]);

  const unusedDocuments = useMemo(() => documents.filter(
    (doc) => !application?.attachments.some((link) => link.attachment_id === doc.id)
  ), [documents, application]);

  useEffect(() => {
    let alive = true;
    if (!canEdit) return () => { alive = false; };
    void (apiGet("/api/hoa/associations/" + associationId +
      "/arc-fee-gl-options" + query) as Promise<FeeOption[]>)
      .then((options) => { if (alive) setFeeOptions(options); })
      .catch(() => { if (alive) setFeeOptions([]); });
    return () => { alive = false; };
  }, [associationId, canEdit, query]);

  async function create(event: React.FormEvent) {
    event.preventDefault();
    if (!canEdit || busy || !contactLinkId || !submittedOn) return;
    setBusy(true); setError(""); setMessage("");
    try {
      await apiPost(base, {
        property_id: propertyId,
        intake_id: intakeId,
        applicant_contact_link_id: Number(contactLinkId),
        submitted_on: submittedOn,
      });
      await reload();
      setMessage("ARC application recorded. Awaiting board decision.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to record ARC application.");
    } finally { setBusy(false); }
  }

  async function transition(eventType: string) {
    if (!application || !canEdit || busy) return;
    setBusy(true); setError(""); setMessage("");
    try {
      await apiPost(base + "/" + application.id + "/events" + query, {
        event_type: eventType, staff_note: note.trim() || null,
      });
      setNote("");
      await reload();
      setMessage(
        eventType.startsWith("PREPARE_")
          ? "Decision preparation recorded. It is not an effective approval or denial."
          : "Staff review history updated."
      );
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to update ARC review.");
    } finally { setBusy(false); }
  }

  async function decide(decision: "APPROVED" | "DENIED") {
    if (!application || !canEdit || busy || !note.trim()) return;
    if (feeAmount && (!feeDueOn || !incomeGlId || !receivableGlId)) {
      setError("Fee amount, due date, receivables GL, and income GL are required together.");
      return;
    }
    setBusy(true); setError(""); setMessage("");
    try {
      await apiPost(base + "/" + application.id + "/board-decision", {
        property_id: propertyId, decision, decision_note: note.trim(),
        fee: feeAmount ? {
          amount: feeAmount, due_on: feeDueOn,
          receivable_gl_account_id: Number(receivableGlId),
          income_gl_account_id: Number(incomeGlId),
        } : null,
        follow_up_unit_id: followupUnitId ? Number(followupUnitId) : null,
      });
      setNote(""); setFeeAmount(""); setFeeDueOn("");
      setIncomeGlId(""); setReceivableGlId(""); setFollowupUnitId("");
      await reload();
      setMessage("Board decision recorded. Any requested member fee and follow-up were processed atomically.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to record board decision.");
    } finally { setBusy(false); }
  }

  async function addAttachment() {
    if (!application || !canEdit || busy || !attachmentId) return;
    setBusy(true); setError(""); setMessage("");
    try {
      await apiPost(base + "/" + application.id + "/attachments" + query, {
        attachment_id: Number(attachmentId),
      });
      setAttachmentId("");
      await reload();
      setMessage("Private ARC document linked.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to link ARC document.");
    } finally { setBusy(false); }
  }

  async function removeAttachment(linkId: number) {
    if (!application || !canEdit || busy) return;
    setBusy(true); setError(""); setMessage("");
    try {
      await apiDelete(base + "/" + application.id + "/attachments/" + linkId + query);
      await reload();
      setMessage("ARC document reference archived; original property file retained.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to archive ARC document link.");
    } finally { setBusy(false); }
  }

  return (
    <section className="mt-3 w-full space-y-3 rounded border border-blue-200 bg-blue-50 p-3">
      <div className="flex items-center justify-between gap-2">
        <h4 className="text-sm font-semibold">ARC application and review · {projectTitle}</h4>
        <button type="button" onClick={onClose} className="text-sm text-blue-700">Close</button>
      </div>
      <p className="text-xs text-slate-700">
        Applicant identity uses the existing association contact and documents stay private.
        A verified, logged-in board member matching an eligible association seat may record
        an approved or denied decision. Financial fees and work-order follow-ups are optional
        and require valid member/accounting or tenant/unit associations.
      </p>
      {loading && <p className="text-sm text-slate-500">Loading ARC workflow…</p>}
      {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
      {message && <p role="status" className="text-sm text-green-700">{message}</p>}

      {!loading && !application && canEdit && (
        <form onSubmit={(event) => { void create(event); }} className="grid gap-3 sm:grid-cols-2">
          <label className="text-sm">Applicant contact
            <select required aria-label="Applicant contact" value={contactLinkId}
              onChange={(event) => setContactLinkId(event.target.value)}
              className="mt-1 block w-full rounded border bg-white p-2">
              <option value="">Select recorded HOA contact</option>
              {contacts.map((row) => <option key={row.id} value={row.id}>{row.contact_name}</option>)}
            </select>
          </label>
          <label className="text-sm">Application received date
            <input required type="date" value={submittedOn}
              onChange={(event) => setSubmittedOn(event.target.value)}
              className="mt-1 block w-full rounded border bg-white p-2" />
          </label>
          <button type="submit" disabled={busy || !contactLinkId || !submittedOn}
            className="rounded bg-slate-900 px-3 py-2 text-sm text-white disabled:opacity-50">
            Record ARC application
          </button>
        </form>
      )}
      {!loading && !application && !canEdit && (
        <p className="text-sm text-slate-500">No ARC application has been recorded for this intake.</p>
      )}

      {application && (
        <div className="space-y-3">
          <div className="rounded border bg-white p-3 text-sm">
            <p className="font-medium">{application.applicant_contact_name}</p>
            <p>Received {application.submitted_on} · {application.status.replaceAll("_", " ")}</p>
            {application.decision_preparation && (
              <p className="font-medium text-amber-700">
                {application.decision_preparation} PREPARED FOR BOARD REVIEW
              </p>
            )}
            {application.board_decision && (
              <div className="space-y-1 text-xs text-slate-700">
                <p className="font-semibold text-green-800">
                  Board decision: {application.board_decision.decision} · Recorded {application.board_decision.decided_at}
                </p>
                <p>{application.board_decision.decision_note}</p>
                <p>Applicant notification: {application.board_decision.notification_status.replaceAll("_", " ")}</p>
                {application.board_decision.member_charge_id && (
                  <p>Member fee #{application.board_decision.member_charge_id}: ${application.board_decision.member_charge_amount}
                    · Due {application.board_decision.member_charge_due_on}
                    · GL transaction #{application.board_decision.fee_gl_transaction_id}</p>
                )}
                {application.board_decision.work_order_id && (
                  <p>Work order #{application.board_decision.work_order_id} created.</p>
                )}
              </div>
            )}
          </div>

          <div className="space-y-2">
            <h5 className="text-sm font-semibold">Private application documents</h5>
            {application.attachments.length === 0 && <p className="text-xs text-slate-500">No private documents linked.</p>}
            {application.attachments.map((row) => (
              <div key={row.id} className="flex items-center justify-between rounded border bg-white p-2 text-sm">
                <span className="break-all">{row.filename}</span>
                {canEdit && <button type="button" disabled={busy}
                  onClick={() => { void removeAttachment(row.id); }}
                  className="text-red-700 disabled:opacity-50">Archive link</button>}
              </div>
            ))}
            {canEdit && (
              <div className="flex flex-wrap items-end gap-2">
                <label className="text-sm">Private property document
                  <select aria-label="Private ARC document" value={attachmentId}
                    onChange={(event) => setAttachmentId(event.target.value)}
                    className="mt-1 block rounded border bg-white p-2">
                    <option value="">Select document</option>
                    {unusedDocuments.map((row) => <option key={row.id} value={row.id}>{row.original_name}</option>)}
                  </select>
                </label>
                <button type="button" disabled={!attachmentId || busy}
                  onClick={() => { void addAttachment(); }}
                  className="rounded border bg-white px-3 py-2 disabled:opacity-50">Link document</button>
              </div>
            )}
          </div>

          <div className="space-y-2">
            <h5 className="text-sm font-semibold">Review history</h5>
            <ol className="space-y-1 text-xs text-slate-700">
              {application.events.map((row) => (
                <li key={row.id} className="rounded border bg-white p-2">
                  {row.event_type.replaceAll("_", " ")}
                  {row.staff_note ? " · " + row.staff_note : ""}
                  {" · "}{row.event_type.startsWith("BOARD_") ? "BOARD DECISION" : "STAFF REVIEW"}
                </li>
              ))}
            </ol>
            {canEdit && (
              <>
                <label className="block text-sm">Review note / board decision reason
                  <textarea maxLength={1500} rows={2} value={note}
                    onChange={(event) => setNote(event.target.value)}
                    className="mt-1 block w-full rounded border bg-white p-2" />
                </label>
                <div className="flex flex-wrap gap-2">
                  {ACTIONS[application.status].map((action) => (
                    <button key={action.key} type="button" disabled={busy}
                      onClick={() => { void transition(action.key); }}
                      className="rounded border bg-white px-3 py-2 text-sm disabled:opacity-50">
                      {action.label}
                    </button>
                  ))}
                </div>
                {["READY_FOR_DECISION", "DECISION_PREPARED"].includes(application.status) && (
                  <div className="mt-3 space-y-2 rounded border border-emerald-300 bg-white p-3 text-sm">
                    <p className="font-semibold">Record board decision</p>
                    <p className="text-xs text-slate-600">
                      Requires a verified board login matching an active eligible association seat.
                      A decision is final once recorded. Only an approved application may carry a fee
                      or work order. Applicant notification requires a matching verified account.
                    </p>
                    <label className="block">Optional ARC fee amount
                      <input type="number" min="0.01" step="0.01" value={feeAmount}
                        onChange={(event) => setFeeAmount(event.target.value)}
                        className="mt-1 block w-full rounded border p-2" />
                    </label>
                    {feeAmount && (
                      <div className="grid gap-2 sm:grid-cols-2">
                        <label>Fee due date<input type="date" required value={feeDueOn}
                          onChange={(event) => setFeeDueOn(event.target.value)}
                          className="mt-1 block w-full rounded border p-2" /></label>
                        <label>Receivables asset GL
                          <select value={receivableGlId}
                            onChange={(event) => setReceivableGlId(event.target.value)}
                            className="mt-1 block w-full rounded border p-2">
                            <option value="">Choose receivable GL</option>
                            {feeOptions.filter((item) => item.account_type === "ASSET").map((item) => (
                              <option key={item.id} value={item.id}>{item.number} · {item.name}</option>
                            ))}
                          </select>
                        </label>
                        <label>ARC fee income GL
                          <select value={incomeGlId}
                            onChange={(event) => setIncomeGlId(event.target.value)}
                            className="mt-1 block w-full rounded border p-2">
                            <option value="">Choose fee income GL</option>
                            {feeOptions.filter((item) => item.account_type === "INCOME").map((item) => (
                              <option key={item.id} value={item.id}>{item.number} · {item.name}</option>
                            ))}
                          </select>
                        </label>
                      </div>
                    )}
                    <label className="block">Optional follow-up work-order unit ID
                      <input type="number" min="1" step="1" value={followupUnitId}
                        onChange={(event) => setFollowupUnitId(event.target.value)}
                        className="mt-1 block w-full rounded border p-2" />
                      <span className="text-xs text-slate-500">
                        Requires a verified tenant applicant with an active lease on this unit.
                      </span>
                    </label>
                    <div className="flex flex-wrap gap-2">
                      <button type="button" disabled={busy || !note.trim()}
                        onClick={() => { void decide("APPROVED"); }}
                        className="rounded bg-emerald-700 px-3 py-2 text-white disabled:opacity-50">
                        Record board approval
                      </button>
                      <button type="button" disabled={busy || !note.trim() || !!feeAmount || !!followupUnitId}
                        onClick={() => { void decide("DENIED"); }}
                        className="rounded border border-red-500 px-3 py-2 text-red-700 disabled:opacity-50">
                        Record board denial
                      </button>
                    </div>
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      )}
    </section>
  );
}
