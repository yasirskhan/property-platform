"use client";

import { useEffect, useRef, useState } from "react";
import { apiGet, apiPost } from "@/lib/api";

type Recipient = { contact_link_id: number; contact_name: string };
type Delivery = {
  id: number; evidence_id: number; contact_link_id: number;
  status: "PENDING" | "SENDING" | "FAILED" | "TEST_ONLY" | "SMTP_ACCEPTED";
  attempt_count: number; created_at: string; accepted_at: string | null;
  file_sha256: string; email_attachment_included: boolean;
  recipient_delivery_confirmed: false; legally_served: false;
};

export default function HoaDocumentDeliveryPanel({
  associationId, propertyId, evidenceId, onClose,
}: {
  associationId: number; propertyId: number; evidenceId: number;
  onClose: () => void;
}) {
  const [recipients, setRecipients] = useState<Recipient[]>([]);
  const [history, setHistory] = useState<Delivery[]>([]);
  const [contactLinkId, setContactLinkId] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const requestKey = useRef("");
  const base = "/api/hoa/associations/" + associationId + "/governing-evidence";
  const query = "?property_id=" + propertyId;

  async function refresh() {
    const [contacts, rows] = await Promise.all([
      apiGet(base + "/eligible-recipients" + query) as Promise<Recipient[]>,
      apiGet(base + "/deliveries" + query) as Promise<Delivery[]>,
    ]);
    setRecipients(contacts);
    setHistory(rows);
  }

  useEffect(() => {
    let live = true;
    void Promise.all([
      apiGet(base + "/eligible-recipients" + query) as Promise<Recipient[]>,
      apiGet(base + "/deliveries" + query) as Promise<Delivery[]>,
    ]).then(([contacts, rows]) => {
      if (!live) return;
      setRecipients(contacts); setHistory(rows);
    }).catch((cause) => {
      if (live) setError(cause instanceof Error ? cause.message : "Document delivery unavailable.");
    });
    return () => { live = false; };
  }, [base, query]);

  async function send() {
    if (busy || !contactLinkId) return;
    const recipient = recipients.find((row) => row.contact_link_id === Number(contactLinkId));
    if (!recipient || !window.confirm("Email a copy of this private document to " + recipient.contact_name + "? An emailed copy cannot be recalled.")) return;
    setBusy(true); setError(""); setMessage("");
    if (!requestKey.current) requestKey.current = crypto.randomUUID();
    try {
      const result = await apiPost(base + "/" + evidenceId + "/deliveries", {
        property_id: propertyId, contact_link_id: Number(contactLinkId),
        request_key: requestKey.current,
      }) as Delivery;
      requestKey.current = "";
      await refresh();
      setMessage(result.status === "SMTP_ACCEPTED"
        ? "Attachment accepted by SMTP. Recipient inbox delivery is not confirmed."
        : result.status === "TEST_ONLY"
          ? "Test mode: no document attachment was emailed."
          : "Delivery attempt recorded: " + result.status + ". Review history or retry.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to record document delivery.");
      await refresh().catch(() => {});
    } finally {
      setBusy(false);
    }
  }

  async function retry(delivery: Delivery) {
    if (busy || !window.confirm("Retry sending this same document version to its original verified recipient?")) return;
    setBusy(true); setError(""); setMessage("");
    try {
      const result = await apiPost(
        base + "/deliveries/" + delivery.id + "/retry" + query,
      ) as Delivery;
      await refresh();
      setMessage(result.status === "SMTP_ACCEPTED"
        ? "SMTP accepted the attachment. Actual recipient delivery remains unconfirmed."
        : result.status === "TEST_ONLY"
          ? "Test-only attempt: no attachment sent."
          : "Retry status: " + result.status);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Document retry unavailable.");
      await refresh().catch(() => {});
    } finally {
      setBusy(false);
    }
  }

  const rows = history.filter((row) => row.evidence_id === evidenceId);
  return (
    <section className="space-y-2 rounded border border-blue-200 bg-blue-50 p-3 text-xs">
      <div className="flex items-center justify-between gap-2">
        <h4 className="font-semibold">Email document copy</h4>
        <button type="button" onClick={onClose} className="text-blue-700">Close delivery</button>
      </div>
      <p className="text-slate-700">
        Emails a copy of the selected private document. Only a currently verified
        login linked to this association/property can receive it. SMTP acceptance
        does not prove inbox receipt or legal notice service. Console-mode testing
        does not transmit the attachment.
      </p>
      {error && <p role="alert" className="text-red-700">{error}</p>}
      {message && <p role="status" className="text-green-800">{message}</p>}
      <label className="block">Verified association contact
        <select aria-label="Verified association contact" required
          value={contactLinkId} onChange={(event) => {
            setContactLinkId(event.target.value); requestKey.current = "";
          }} className="mt-1 block w-full rounded border p-2">
          <option value="">Choose a verified contact</option>
          {recipients.map((recipient) => (
            <option key={recipient.contact_link_id} value={recipient.contact_link_id}>
              {recipient.contact_name}
            </option>
          ))}
        </select>
      </label>
      <button type="button" disabled={busy || !contactLinkId}
        onClick={() => { void send(); }}
        className="rounded bg-blue-900 px-3 py-2 text-white disabled:opacity-50">
        Email document copy
      </button>
      {recipients.length === 0 && <p>No currently verified contact is eligible for delivery.</p>}
      <h5 className="font-semibold">Document transmission history</h5>
      {rows.length === 0 && <p>No transmission attempts recorded for this document.</p>}
      <ol className="space-y-1">
        {rows.map((delivery) => (
          <li key={delivery.id} className="rounded border bg-white p-2">
            <p>
              Request #{delivery.id} · {delivery.status.replaceAll("_", " ")}
              {" · "}Attempts {delivery.attempt_count}
              {" · "}Contact reference #{delivery.contact_link_id}
            </p>
            <p>Stored document fingerprint: {delivery.file_sha256.slice(0, 16)}…</p>
            <p>Inbox delivery confirmed: NO · Legally served: NO</p>
            {["FAILED", "TEST_ONLY", "PENDING"].includes(delivery.status) && (
              <button type="button" disabled={busy}
                onClick={() => { void retry(delivery); }}
                className="text-blue-700 disabled:opacity-50">Retry this transmission</button>
            )}
          </li>
        ))}
      </ol>
    </section>
  );
}
