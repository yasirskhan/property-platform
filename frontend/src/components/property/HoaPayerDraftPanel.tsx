"use client";

import { useEffect, useState } from "react";
import { apiDelete, apiGet, apiPut } from "@/lib/api";

type Contact = { id: number; contact_name: string };
type Payer = {
  id: number; contact_link_id: number; contact_name: string;
  status: "STAFF_SUGGESTED_UNVERIFIED";
  legal_payer_verified: false; issue_charge_enabled: false;
};

export default function HoaPayerDraftPanel({
  associationId, propertyId, proposalId, canEdit,
}: {
  associationId: number; propertyId: number; proposalId: number; canEdit: boolean;
}) {
  const base = "/api/hoa/associations/" + associationId +
    "/draft-assessments/" + proposalId + "/payer-draft";
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [record, setRecord] = useState<Payer | null>(null);
  const [linkId, setLinkId] = useState("");
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let active = true;
    setError(""); setMessage(""); setRecord(null); setContacts([]);
    void Promise.all([
      apiGet(base + "?property_id=" + propertyId) as Promise<Payer | null>,
      apiGet("/api/hoa/associations/" + associationId +
        "/contacts?property_id=" + propertyId) as Promise<Contact[]>,
    ]).then(([saved, available]) => {
      if (!active) return;
      setRecord(saved);
      setLinkId(saved ? String(saved.contact_link_id) : "");
      setContacts(available);
    }).catch((cause) => {
      if (active) setError(cause instanceof Error ? cause.message : "Suggested payer unavailable.");
    });
    return () => { active = false; };
  }, [base, associationId, propertyId]);

  async function save(event: React.FormEvent) {
    event.preventDefault();
    if (!canEdit || !linkId || busy) return;
    setBusy(true); setError(""); setMessage("");
    try {
      const updated = await apiPut(base, {
        property_id: propertyId, contact_link_id: Number(linkId),
      }) as Payer;
      setRecord(updated);
      setMessage("Staff payer reference saved; no debt, bill, or charge created.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to save payer reference.");
    } finally { setBusy(false); }
  }

  async function archive() {
    if (!canEdit || !record || busy || !window.confirm(
      "Archive the suggested payer? This cannot issue or reverse a charge."
    )) return;
    setBusy(true); setError(""); setMessage("");
    try {
      await apiDelete(base + "?property_id=" + propertyId);
      setRecord(null); setLinkId("");
      setMessage("Suggested payer archived; no legal or accounting effect.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to archive payer reference.");
    } finally { setBusy(false); }
  }

  return (
    <section className="w-full space-y-2 rounded border border-amber-200 bg-amber-50 p-3 text-sm">
      <h5 className="font-semibold">Suggested assessment contact</h5>
      <p className="text-xs text-amber-900">
        Staff planning only. A contact link does not establish ownership,
        dues liability, a legal payer, or permission to issue charges.
      </p>
      {error && <p role="alert" className="text-red-700">{error}</p>}
      {message && <p role="status" className="text-green-700">{message}</p>}
      {record && <p className="text-xs">
        {record.contact_name} · {record.status.replaceAll("_", " ")}
        {" · "}Legal payer verified: NO · Issue charge: DISABLED
      </p>}
      {canEdit ? (
        <form onSubmit={(event) => { void save(event); }} className="flex flex-wrap items-end gap-2">
          <label className="text-xs">Staff-suggested contact
            <select required value={linkId} onChange={(event) => setLinkId(event.target.value)}
              className="mt-1 block rounded border bg-white p-2">
              <option value="">Choose an active HOA contact</option>
              {contacts.map((item) => (
                <option key={item.id} value={item.id}>{item.contact_name}</option>
              ))}
            </select>
          </label>
          <button disabled={busy || !linkId} type="submit"
            className="rounded bg-slate-900 px-3 py-2 text-white disabled:opacity-50">
            Save staff reference
          </button>
          {record && <button type="button" disabled={busy}
            onClick={() => { void archive(); }}
            className="rounded border bg-white px-3 py-2 text-red-700 disabled:opacity-50">
            Archive reference
          </button>}
        </form>
      ) : <p className="text-xs">{record ? "Read-only staff reference." : "No payer contact suggested."}</p>}
    </section>
  );
}
