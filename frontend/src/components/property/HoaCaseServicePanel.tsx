"use client";

import { useEffect, useRef, useState } from "react";
import { apiGet, apiPost } from "@/lib/api";

type Proof = { id: number; attachment_id: number; filename: string };
type Draft = {
  id: number; revision: number; policy_revision: number;
  recipient_user_id: number; recipient_reference_current: boolean;
  policy_revision_current: boolean;
};
type Service = {
  id: number; correspondence_revision: number; policy_revision: number;
  member_user_id: number; proof_attachment_id: number;
  delivery_method: string; served_on: string;
  cure_earliest_on: string; hearing_request_earliest_on: string;
  platform_certifies_service: false;
};

export default function HoaCaseServicePanel({
  associationId, propertyId, caseId, canEdit, onClose,
}: {
  associationId: number; propertyId: number; caseId: number;
  canEdit: boolean; onClose: () => void;
}) {
  const root = "/api/hoa/associations/" + associationId + "/staff-cases/" + caseId;
  const query = "?property_id=" + propertyId;
  const [record, setRecord] = useState<Service | null>(null);
  const [drafts, setDrafts] = useState<Draft[]>([]);
  const [proofs, setProofs] = useState<Proof[]>([]);
  const [proofId, setProofId] = useState("");
  const [servedOn, setServedOn] = useState("");
  const [method, setMethod] = useState("PERSONAL");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const requestKey = useRef("");

  useEffect(() => {
    let live = true;
    void Promise.all([
      apiGet(root + "/service-record" + query) as Promise<Service | null>,
      apiGet(root + "/correspondence" + query) as Promise<Draft[]>,
      apiGet(root + "/evidence" + query) as Promise<Proof[]>,
    ]).then(([service, messages, files]) => {
      if (!live) return;
      setRecord(service); setDrafts(messages); setProofs(files);
    }).catch((cause) => {
      if (live) setError(cause instanceof Error ? cause.message : "Service record unavailable.");
    });
    return () => { live = false; };
  }, [root, query]);

  async function recordService(event: React.FormEvent) {
    event.preventDefault();
    const latest = drafts[drafts.length - 1];
    if (!canEdit || busy || !latest || !proofId || !servedOn) return;
    if (!window.confirm(
      "Record the association's actual service with private proof? " +
      "This is not an automatic legal certification or a fine posting."
    )) return;
    if (!requestKey.current) requestKey.current = window.crypto.randomUUID();
    setBusy(true); setError(""); setMessage("");
    try {
      const entry = await apiPost(root + "/service-record", {
        property_id: propertyId, correspondence_id: latest.id,
        correspondence_revision: latest.revision,
        policy_revision: latest.policy_revision,
        member_user_id: latest.recipient_user_id,
        proof_attachment_id: Number(proofId),
        delivery_method: method, served_on: servedOn,
        request_key: requestKey.current,
      }) as Service;
      requestKey.current = "";
      setRecord(entry);
      setMessage("Association-reported service and supporting evidence recorded.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Service record rejected.");
      void apiGet(root + "/service-record" + query).then(
        result => setRecord(result as Service | null)
      ).catch(() => {});
    } finally { setBusy(false); }
  }

  const latest = drafts[drafts.length - 1];
  return <section className="space-y-2 rounded border border-teal-200 bg-teal-50 p-3 text-xs">
    <div className="flex items-center justify-between">
      <h4 className="font-semibold">Association notice-service record</h4>
      <button type="button" onClick={onClose} className="text-blue-700">Close service record</button>
    </div>
    <p>This records the association's statement of actual delivery with private
      supporting evidence, not an assumption based on SMTP acceptance.
      Service validity and jurisdiction-specific procedures remain the association's responsibility.
      This screen never assesses a fine or changes the general ledger.</p>
    {error && <p role="alert" className="text-red-700">{error}</p>}
    {message && <p role="status" className="text-green-800">{message}</p>}
    {record ? <div className="space-y-1 rounded border bg-white p-2">
      <p>Service record #{record.id} · {record.delivery_method} · {record.served_on}</p>
      <p>Correspondence revision {record.correspondence_revision}
        {" · "}Procedure revision {record.policy_revision}
        {" · "}Member #{record.member_user_id}</p>
      <p>Associated private proof attachment #{record.proof_attachment_id}</p>
      <p>Configured cure calculation: {record.cure_earliest_on}
        {" · "}Configured hearing-request calculation: {record.hearing_request_earliest_on}</p>
      <p className="text-amber-800">Evidence recorded by the association. The platform does not independently certify legal service.</p>
    </div> : <p>No actual service evidence has been recorded for this case.</p>}
    {canEdit && !record && latest && latest.recipient_reference_current &&
      latest.policy_revision_current && <form onSubmit={(e) => { void recordService(e); }}
        className="space-y-2 border-t pt-2">
        <p>Record service for correspondence revision {latest.revision}
          {" · "}Verified recipient #{latest.recipient_user_id}.</p>
        <label className="block">Actual delivery method
          <select aria-label="HOA service delivery method" className="mt-1 block rounded border p-2"
            value={method} onChange={e => setMethod(e.target.value)}>
            <option value="PERSONAL">Personally delivered</option>
            <option value="POSTAL">Postal service</option>
            <option value="EMAIL_CONFIRMED">Email with independent receipt proof</option>
            <option value="OTHER">Other permitted method</option>
          </select>
        </label>
        <label className="block">Actual date served
          <input type="date" required value={servedOn}
            onChange={e => setServedOn(e.target.value)}
            className="mt-1 block rounded border p-2" />
        </label>
        <label className="block">Private case-linked proof
          <select aria-label="HOA service proof" required value={proofId}
            onChange={e => setProofId(e.target.value)}
            className="mt-1 block w-full rounded border p-2">
            <option value="">Select existing private case evidence</option>
            {proofs.map(p => <option key={p.id} value={p.attachment_id}>
              {p.filename}</option>)}
          </select>
        </label>
        <button type="submit" disabled={busy || !proofId || !servedOn}
          className="rounded bg-teal-900 px-3 py-2 text-white disabled:opacity-50">
          Record evidenced service
        </button>
      </form>}
  </section>;
}
