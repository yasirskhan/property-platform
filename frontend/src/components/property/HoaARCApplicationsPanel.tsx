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
type AppUser = { id: number; email: string; first_name: string; last_name: string; is_verified: boolean; is_active: boolean };
type BoardSeat = { id: number; contact_name: string; decision_authorized: boolean; can_record_offline: boolean };
type BoardDecision = {
  id: number; decision: "APPROVED" | "DENIED"; decision_note: string;
  decided_at: string; board_seat_id: number; decision_maker_seat_id: number;
  decided_on: string; record_method: "DIRECT" | "OFFLINE";
  supporting_attachment_id: number | null; notification_status: string;
  member_charge_id: number | null; member_charge_amount: string | null;
  member_charge_due_on: string | null; fee_gl_transaction_id: number | null;
  fee_reversal_transaction_id: number | null;
  follow_up_id: number | null; follow_up_kind: string | null;
  existing_work_order_id: number | null; work_order_id: number | null;
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
  const [memberUsers, setMemberUsers] = useState<AppUser[]>([]);
  const [memberUserId, setMemberUserId] = useState("");
  const [boardSeats, setBoardSeats] = useState<BoardSeat[]>([]);
  const [offlineDate, setOfflineDate] = useState("");
  const [decisionMakerSeatId, setDecisionMakerSeatId] = useState("");
  const [supportId, setSupportId] = useState("");
  const [followUpKind, setFollowUpKind] = useState("");
  const [followUpDescription, setFollowUpDescription] = useState("");
  const [reversalOn, setReversalOn] = useState("");
  const [reversalReason, setReversalReason] = useState("");
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
    void Promise.all([
      apiGet("/api/hoa/associations/" + associationId +
        "/arc-fee-gl-options" + query) as Promise<FeeOption[]>,
      apiGet("/api/hoa/associations/" + associationId +
        "/board-proposals" + query) as Promise<{ seats: BoardSeat[] }>,
      apiGet("/users") as Promise<AppUser[]>,
    ]).then(([options, board, members]) => {
      if (!alive) return;
      setFeeOptions(options);
      setBoardSeats(board.seats);
      setMemberUsers(members.filter(item => item.is_active && item.is_verified));
    }).catch(() => { if (alive) {
      setFeeOptions([]); setBoardSeats([]); setMemberUsers([]);
    } });
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
    if (feeAmount && (!memberUserId || !feeDueOn || !incomeGlId || !receivableGlId)) {
      setError("A verified member, fee amount, due date, receivables GL and income GL are required together.");
      return;
    }
    if (offlineDate && (!decisionMakerSeatId || !supportId)) {
      setError("Offline decisions require a decision-maker seat and private supporting record.");
      return;
    }
    if (followUpKind && followUpDescription.trim().length < 10) {
      setError("Describe the work-order or inspection follow-up.");
      return;
    }
    setBusy(true); setError(""); setMessage("");
    try {
      await apiPost(base + "/" + application.id + "/board-decision", {
        property_id: propertyId, decision, decision_note: note.trim(),
        offline_meeting_on: offlineDate || null,
        decision_maker_seat_id: offlineDate ? Number(decisionMakerSeatId) : null,
        supporting_attachment_id: offlineDate ? Number(supportId) : null,
        fee: feeAmount ? {
          member_user_id: Number(memberUserId),
          amount: feeAmount, due_on: feeDueOn,
          receivable_gl_account_id: Number(receivableGlId),
          income_gl_account_id: Number(incomeGlId),
        } : null,
        follow_up_kind: followUpKind || null,
        follow_up_description: followUpKind ? followUpDescription.trim() : null,
        follow_up_unit_id: followUpKind === "WORK_ORDER" && followupUnitId
          ? Number(followupUnitId) : null,
      });
      setNote(""); setFeeAmount(""); setFeeDueOn("");
      setIncomeGlId(""); setReceivableGlId(""); setMemberUserId("");
      setFollowupUnitId(""); setFollowUpKind(""); setFollowUpDescription("");
      setOfflineDate(""); setDecisionMakerSeatId(""); setSupportId("");
      await reload();
      setMessage("Board decision recorded. Any requested member fee and follow-up were processed atomically.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to record board decision.");
    } finally { setBusy(false); }
  }

  async function retryNotification() {
    if (!application || !canEdit || busy) return;
    setBusy(true); setError(""); setMessage("");
    try {
      await apiPost(base + "/" + application.id + "/notification/retry" + query, {});
      await reload();
      setMessage("Applicant notification delivery retried. Decision and charges are unchanged.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Applicant notice cannot be retried.");
    } finally { setBusy(false); }
  }

  async function reverseFee() {
    if (!application || !canEdit || busy || !reversalOn || !reversalReason.trim()) return;
    setBusy(true); setError(""); setMessage("");
    try {
      await apiPost(base + "/" + application.id + "/member-fee/reverse", {
        property_id: propertyId, reversal_on: reversalOn,
        reason: reversalReason.trim(),
      });
      await reload();
      setMessage("The fee was reversed with a new immutable GL entry. The board decision remains recorded.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Fee reversal rejected.");
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
                <p>Recorded by board seat #{application.board_decision.board_seat_id}
                  {application.board_decision.record_method === "OFFLINE"
                    ? " · Offline meeting " + application.board_decision.decided_on +
                      " · Decision maker seat #" + application.board_decision.decision_maker_seat_id
                    : " · Direct board record"}
                </p>
                {application.board_decision.supporting_attachment_id && (
                  <p>Private supporting record #{application.board_decision.supporting_attachment_id}</p>
                )}
                <p>Applicant notification: {application.board_decision.notification_status.replaceAll("_", " ")}</p>
                {canEdit && application.board_decision.notification_status !== "SENT" && (
                  <button type="button" disabled={busy} onClick={() => { void retryNotification(); }}
                    className="rounded border border-blue-600 px-2 py-1 text-blue-700 disabled:opacity-50">
                    Retry applicant notice
                  </button>
                )}
                {application.board_decision.member_charge_id && (
                  <p>Member fee #{application.board_decision.member_charge_id}: ${application.board_decision.member_charge_amount}
                    · Due {application.board_decision.member_charge_due_on}
                    · GL transaction #{application.board_decision.fee_gl_transaction_id}</p>
                )}
                {application.board_decision.fee_reversal_transaction_id && (
                  <p>Fee reversed by GL #{application.board_decision.fee_reversal_transaction_id}.</p>
                )}
                {application.board_decision.follow_up_id && (
                  <p>HOA {application.board_decision.follow_up_kind} follow-up #{application.board_decision.follow_up_id}
                    {application.board_decision.existing_work_order_id
                      ? " · Work order #" + application.board_decision.existing_work_order_id
                      : " · Association follow-up requested"}
                  </p>
                )}
                {canEdit && application.board_decision.member_charge_id &&
                  !application.board_decision.fee_reversal_transaction_id && (
                    <div className="mt-2 flex flex-wrap items-end gap-2">
                      <label>Fee reversal date
                        <input type="date" value={reversalOn}
                          onChange={(event) => setReversalOn(event.target.value)}
                          className="mt-1 block rounded border p-2" /></label>
                      <label>Reversal reason
                        <input maxLength={500} value={reversalReason}
                          onChange={(event) => setReversalReason(event.target.value)}
                          className="mt-1 block rounded border p-2" /></label>
                      <button type="button" disabled={busy || !reversalOn || !reversalReason.trim()}
                        onClick={() => { void reverseFee(); }}
                        className="rounded border border-red-500 px-3 py-2 text-red-700 disabled:opacity-50">
                        Reverse fee via GL
                      </button>
                    </div>
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
                        <label>Responsible verified member account
                          <select aria-label="ARC responsible member" value={memberUserId}
                            onChange={(event) => setMemberUserId(event.target.value)}
                            className="mt-1 block w-full rounded border p-2">
                            <option value="">Select verified member</option>
                            {memberUsers.map(item => (
                              <option key={item.id} value={item.id}>
                                {item.first_name} {item.last_name} · {item.email}
                              </option>
                            ))}
                          </select>
                        </label>
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
                    <label className="block">Optional follow-up
                      <select value={followUpKind} onChange={(event) => {
                        setFollowUpKind(event.target.value); setFollowupUnitId("");
                      }} className="mt-1 block w-full rounded border p-2">
                        <option value="">No follow-up</option>
                        <option value="WORK_ORDER">Work-order follow-up</option>
                        <option value="INSPECTION">Inspection request</option>
                      </select>
                    </label>
                    {followUpKind && <>
                      <label className="block">Follow-up instructions
                        <textarea minLength={10} maxLength={1000}
                          value={followUpDescription}
                          onChange={(event) => setFollowUpDescription(event.target.value)}
                          className="mt-1 block w-full rounded border p-2" />
                      </label>
                      {followUpKind === "WORK_ORDER" && (
                        <label className="block">Optional existing lease unit ID
                          <input type="number" min="1" step="1" value={followupUnitId}
                            onChange={(event) => setFollowupUnitId(event.target.value)}
                            className="mt-1 block w-full rounded border p-2" />
                          <span className="text-xs text-slate-500">
                            Creates an existing maintenance work order only for a verified
                            tenant applicant with an active lease on this unit. Otherwise
                            a separately scoped HOA work-order request is recorded.
                          </span>
                        </label>
                      )}
                    </>}
                    <label className="block">Offline board meeting date (optional)
                      <input aria-label="Offline ARC meeting date" type="date" value={offlineDate}
                        onChange={(event) => setOfflineDate(event.target.value)}
                        className="mt-1 block w-full rounded border p-2" />
                    </label>
                    {offlineDate && <>
                      <label className="block">Board decision maker
                        <select aria-label="Offline ARC decision maker" value={decisionMakerSeatId}
                          onChange={(event) => setDecisionMakerSeatId(event.target.value)}
                          className="mt-1 block w-full rounded border p-2">
                          <option value="">Choose authorized board seat</option>
                          {boardSeats.filter(seat => seat.decision_authorized).map(seat => (
                            <option key={seat.id} value={seat.id}>{seat.contact_name} · Seat #{seat.id}</option>
                          ))}
                        </select>
                      </label>
                      <label className="block">Private supporting meeting record
                        <select aria-label="Offline ARC support document" value={supportId}
                          onChange={(event) => setSupportId(event.target.value)}
                          className="mt-1 block w-full rounded border p-2">
                          <option value="">Choose private document</option>
                          {documents.map(item => (
                            <option key={item.id} value={item.id}>{item.original_name}</option>
                          ))}
                        </select>
                      </label>
                    </>}
                    <div className="flex flex-wrap gap-2">
                      <button type="button" disabled={busy || !note.trim() ||
                        (!!offlineDate && (!decisionMakerSeatId || !supportId))}
                        onClick={() => { void decide("APPROVED"); }}
                        className="rounded bg-emerald-700 px-3 py-2 text-white disabled:opacity-50">
                        Record board approval
                      </button>
                      <button type="button" disabled={busy || !note.trim() || !!feeAmount || !!followUpKind ||
                        (!!offlineDate && (!decisionMakerSeatId || !supportId))}
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
