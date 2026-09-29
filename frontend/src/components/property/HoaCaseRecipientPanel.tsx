"use client";

import { useEffect, useState } from "react";
import { apiDelete, apiGet, apiPut } from "@/lib/api";

type ContactLink = { id: number; contact_name: string };
type Recipient = {
  id: number; contact_link_id: number; contact_name: string;
  matched_user_id: number; status: "STAFF_LINKED_VERIFIED_LOGIN";
  notice_delivery_enabled: false; member_liability_verified: false;
};

export default function HoaCaseRecipientPanel({
  associationId, propertyId, caseId, canEdit, onClose,
}: {
  associationId: number; propertyId: number; caseId: number;
  canEdit: boolean; onClose: () => void;
}) {
  const [contacts, setContacts] = useState<ContactLink[]>([]);
  const [record, setRecord] = useState<Recipient | null>(null);
  const [selected, setSelected] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const base = "/api/hoa/associations/" + associationId + "/staff-cases/" + caseId + "/recipient";
  const query = "?property_id=" + propertyId;

  useEffect(() => {
    let alive = true;
    void Promise.all([
      apiGet(base + query) as Promise<Recipient | null>,
      apiGet("/api/hoa/associations/" + associationId + "/contacts" + query) as Promise<ContactLink[]>,
    ]).then(([recipient, links]) => {
      if (!alive) return;
      setRecord(recipient); setContacts(links);
      setSelected(recipient ? String(recipient.contact_link_id) : "");
    }).catch((cause) => {
      if (alive) setError(cause instanceof Error ? cause.message : "Recipient reference unavailable.");
    });
    return () => { alive = false; };
  }, [associationId, base, query]);

  async function save() {
    if (!canEdit || busy || !selected) return;
    setBusy(true); setError(""); setMessage("");
    try {
      const saved = await apiPut(base, {
        property_id: propertyId, contact_link_id: Number(selected),
      }) as Recipient;
      setRecord(saved);
      setMessage("Potential recipient linked to an existing verified login. No notice or fine issued.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Cannot link potential recipient.");
    } finally { setBusy(false); }
  }

  async function clear() {
    if (!canEdit || busy || !record) return;
    setBusy(true); setError(""); setMessage("");
    try {
      await apiDelete(base + query);
      setRecord(null); setSelected("");
      setMessage("Potential recipient reference cleared. History retained.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Cannot clear reference.");
    } finally { setBusy(false); }
  }

  return (
    <section className="space-y-2 rounded border border-amber-200 bg-amber-50 p-3 text-sm">
      <div className="flex justify-between gap-2">
        <h4 className="font-semibold">Potential violation recipient · case #{caseId}</h4>
        <button type="button" className="text-blue-700" onClick={onClose}>Close recipient</button>
      </div>
      <p className="text-xs text-amber-900">
        Only a staff reference to an active, same-association contact matching a verified customer login.
        A match does NOT prove this person is the liable member, or establish service of notice,
        statutory deadlines, legal enforcement or an assessed fine. No messages are sent here.
      </p>
      {error && <p role="alert" className="text-red-700">{error}</p>}
      {message && <p role="status" className="text-emerald-700">{message}</p>}
      {record && (
        <p className="text-xs text-slate-700">
          Staff-selected: {record.contact_name} · Verified login #{record.matched_user_id} ·
          Notice delivery DISABLED
        </p>
      )}
      {!record && <p className="text-xs text-slate-500">No verified-login recipient has been linked.</p>}
      {canEdit && (
        <div className="flex flex-wrap items-end gap-2">
          <label className="text-xs">Potential recipient contact
            <select aria-label="Potential recipient contact" value={selected}
              onChange={(event) => setSelected(event.target.value)}
              className="mt-1 block rounded border bg-white p-2 text-sm">
              <option value="">Choose association contact</option>
              {contacts.map((item) => (
                <option key={item.id} value={item.id}>{item.contact_name}</option>
              ))}
            </select>
          </label>
          <button type="button" disabled={busy || !selected}
            onClick={() => { void save(); }}
            className="rounded border bg-white px-3 py-2 text-blue-700 disabled:opacity-50">
            Record potential recipient
          </button>
          {record && <button type="button" disabled={busy}
            onClick={() => { void clear(); }}
            className="rounded border bg-white px-3 py-2 text-red-700 disabled:opacity-50">
            Clear reference
          </button>}
        </div>
      )}
    </section>
  );
}
