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
type Application = {
  id: number;
  intake_id: number;
  applicant_contact_link_id: number;
  applicant_contact_name: string;
  submitted_on: string;
  status: "SUBMITTED" | "UNDER_REVIEW" | "MORE_INFO_REQUESTED" |
    "INFO_RECEIVED" | "READY_FOR_DECISION" | "DECISION_PREPARED";
  decision_preparation: "APPROVE" | "DENY" | null;
  legal_decision_effective: false;
  governing_authority_verified: false;
};
type Detail = Application & {
  events: { id: number; event_type: string; staff_note: string | null; created_at: string; legal_effect: false }[];
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
      setMessage("ARC application recorded for staff review. No legal decision has been issued.");
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
        Generic application workflow only. Applicant identity is an existing scoped HOA contact.
        Documents stay private property attachments. Approval or denial can be prepared for review,
        but remains legally ineffective until governing authority and decision-maker prerequisites are verified.
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
                {application.decision_preparation} PREPARED ONLY · NOT LEGALLY EFFECTIVE
              </p>
            )}
            <p className="text-xs text-slate-600">
              Governing authority verified: NO · Effective legal decision: NO
            </p>
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
                  {" · "}NO LEGAL EFFECT
                </li>
              ))}
            </ol>
            {canEdit && (
              <>
                <label className="block text-sm">Staff review note (optional)
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
              </>
            )}
          </div>
        </div>
      )}
    </section>
  );
}
