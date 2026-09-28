"use client";

import { useEffect, useState } from "react";
import { apiDelete, apiGet, apiPost } from "@/lib/api";

type AssociationContact = {
  id: number; association_id: number; property_id: number;
  contact_id: number; contact_name: string;
};
type Contact = { id: number; display_name: string; is_active: boolean };
type ContactPage = { items: Contact[]; total: number };

export default function HoaContactsPanel({ associationId, propertyId, canEdit, onClose }: {
  associationId: number; propertyId: number; canEdit: boolean; onClose: () => void;
}) {
  const [items, setItems] = useState<AssociationContact[]>([]);
  const [available, setAvailable] = useState<Contact[]>([]);
  const [chosen, setChosen] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  useEffect(() => {
    let live = true;
    void (async () => {
      try {
        const [links, contacts] = await Promise.all([
          apiGet("/api/hoa/associations/" + associationId + "/contacts?property_id=" + propertyId),
          canEdit ? apiGet("/api/contacts") : Promise.resolve({ items: [], total: 0 }),
        ]);
        if (!live) return;
        setItems(links as AssociationContact[]);
        setAvailable((contacts as ContactPage).items.filter((contact) => contact.is_active));
      } catch (cause) {
        if (live) setError(cause instanceof Error ? cause.message : "Contacts permission required.");
      } finally {
        if (live) setLoading(false);
      }
    })();
    return () => { live = false; };
  }, [associationId, propertyId, canEdit]);

  async function add(event: React.FormEvent) {
    event.preventDefault();
    if (!chosen) return;
    setBusy(true); setError(""); setMessage("");
    try {
      const link = await apiPost("/api/hoa/associations/" + associationId + "/contacts", {
        property_id: propertyId, contact_id: Number(chosen),
      }) as AssociationContact;
      setItems((prior) => [...prior, link]);
      setChosen("");
      setMessage("Staff contact reference saved. No legal membership or dues payer was established.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Cannot link contact.");
    } finally {
      setBusy(false);
    }
  }

  async function remove(link: AssociationContact) {
    setBusy(true); setError(""); setMessage("");
    try {
      await apiDelete("/api/hoa/associations/" + associationId +
                      "/contacts/" + link.id + "?property_id=" + propertyId);
      setItems((prior) => prior.filter((row) => row.id !== link.id));
      setMessage("Contact reference removed; no legal obligations changed.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Cannot unlink contact.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="space-y-3 rounded-lg border bg-slate-50 p-4">
      <div className="flex items-center justify-between gap-2">
        <h3 className="text-sm font-semibold">Recorded association contacts</h3>
        <button type="button" onClick={onClose} className="text-sm text-blue-700">Close</button>
      </div>
      <p className="text-xs text-slate-600">
        This is a reference to an existing organization Contact only. It is
        not proof of property ownership, association voting eligibility,
        legal membership or a person responsible for HOA assessments.
      </p>
      {loading && <p className="text-sm text-slate-500">Loading…</p>}
      {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
      {message && <p role="status" className="text-sm text-green-700">{message}</p>}
      {!loading && items.length === 0 && <p className="text-sm text-slate-500">No contacts recorded for this property.</p>}
      {items.map((item) => (
        <div key={item.id} className="flex flex-wrap items-center justify-between gap-2 rounded border bg-white p-2 text-sm">
          <span>{item.contact_name}</span>
          {canEdit && <button type="button" disabled={busy} onClick={() => { void remove(item); }}
            className="text-red-700 disabled:opacity-50">Unlink contact</button>}
        </div>
      ))}
      {canEdit && !loading && (
        <form onSubmit={(event) => { void add(event); }} className="flex flex-wrap items-end gap-2">
          <label className="block text-sm">Existing organization contact
            <select required value={chosen} onChange={(event) => setChosen(event.target.value)}
              className="mt-1 block rounded border p-2">
              <option value="">Select a contact</option>
              {available.filter((contact) => !items.some((row) => row.contact_id === contact.id))
                .map((contact) => <option key={contact.id} value={contact.id}>{contact.display_name}</option>)}
            </select>
          </label>
          <button type="submit" disabled={busy || !chosen}
            className="rounded bg-slate-900 px-3 py-2 text-sm text-white disabled:opacity-50">Link contact</button>
        </form>
      )}
    </section>
  );
}
