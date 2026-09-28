"use client";

import { useEffect, useState } from "react";
import { apiDelete, apiGet, apiPost, apiPut } from "@/lib/api";
import HoaContactsPanel from "@/components/property/HoaContactsPanel";
import HoaDraftAssessmentsPanel from "@/components/property/HoaDraftAssessmentsPanel";
import HoaObservationsPanel from "@/components/property/HoaObservationsPanel";
import HoaMeetingDraftsPanel from "@/components/property/HoaMeetingDraftsPanel";
import HoaARCIntakePanel from "@/components/property/HoaARCIntakePanel";
import HoaGoverningEvidencePanel from "@/components/property/HoaGoverningEvidencePanel";

type Association = { id: number; name: string; property_ids: number[]; updated_at: string };
type PropertyOption = { id: number; name: string; is_active: boolean };

export default function HoaAssociationsPanel({ propertyId, canEdit }: {
  propertyId: number; canEdit: boolean;
}) {
  const [items, setItems] = useState<Association[]>([]);
  const [properties, setProperties] = useState<PropertyOption[]>([]);
  const [name, setName] = useState("");
  const [contactsAssociation, setContactsAssociation] = useState<number | null>(null);
  const [draftAssociation, setDraftAssociation] = useState<number | null>(null);
  const [observationAssociation, setObservationAssociation] = useState<number | null>(null);
  const [meetingAssociation, setMeetingAssociation] = useState<number | null>(null);
  const [arcAssociation, setArcAssociation] = useState<number | null>(null);
  const [evidenceAssociation, setEvidenceAssociation] = useState<number | null>(null);
  const [others, setOthers] = useState<number[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  useEffect(() => {
    let live = true;
    setLoading(true); setError(""); setItems([]);
    void (async () => {
      try {
        const [associations, available] = await Promise.all([
          apiGet("/api/hoa/associations") as Promise<Association[]>,
          canEdit ? apiGet("/properties") as Promise<PropertyOption[]> : Promise.resolve([]),
        ]);
        if (live) {
          setItems(associations);
          setProperties(available.filter((p) => p.is_active));
        }
      } catch (cause) {
        if (live) setError(cause instanceof Error ? cause.message : "HOA inventory unavailable.");
      } finally {
        if (live) setLoading(false);
      }
    })();
    return () => { live = false; };
  }, [propertyId, canEdit]);

  async function create(event: React.FormEvent) {
    event.preventDefault();
    if (!name.trim()) return;
    setBusy(true); setError(""); setMessage("");
    try {
      const saved = await apiPost("/api/hoa/associations", {
        name: name.trim(), property_ids: Array.from(new Set([propertyId, ...others])),
      }) as Association;
      setItems((prior) => [...prior, saved]);
      setName(""); setOthers([]);
      setMessage("Staff-recorded association saved; no dues or legal status established.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Cannot record association.");
    } finally {
      setBusy(false);
    }
  }

  async function changeMembership(row: Association, include: boolean) {
    setBusy(true); setError(""); setMessage("");
    try {
      const property_ids = include
        ? Array.from(new Set([...row.property_ids, propertyId]))
        : row.property_ids.filter((id) => id !== propertyId);
      const saved = await apiPut("/api/hoa/associations/" + row.id, {
        name: row.name, property_ids,
      }) as Association;
      setItems((prior) => prior.map((item) => item.id === saved.id ? saved : item));
      setMessage(include ? "Property linked." : "Property unlinked.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Cannot update association.");
    } finally {
      setBusy(false);
    }
  }

  async function archive(row: Association) {
    if (!window.confirm("Archive this inventory entry? This does not dissolve a legal HOA.")) return;
    setBusy(true); setError(""); setMessage("");
    try {
      await apiDelete("/api/hoa/associations/" + row.id);
      setItems((prior) => prior.filter((item) => item.id !== row.id));
      if (contactsAssociation === row.id) setContactsAssociation(null);
      if (draftAssociation === row.id) setDraftAssociation(null);
      if (observationAssociation === row.id) setObservationAssociation(null);
      if (meetingAssociation === row.id) setMeetingAssociation(null);
      if (arcAssociation === row.id) setArcAssociation(null);
      if (evidenceAssociation === row.id) setEvidenceAssociation(null);
      setMessage("Inventory archived. No charges or legal obligations were changed.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Cannot archive association.");
    } finally {
      setBusy(false);
    }
  }

  const linked = items.filter((item) => item.property_ids.includes(propertyId));
  const notLinked = items.filter((item) => !item.property_ids.includes(propertyId));
  const availableOthers = properties.filter((p) => p.id !== propertyId);

  return (
    <section className="space-y-3 rounded-xl border bg-white p-5">
      <h2 className="text-lg font-semibold text-slate-900">HOA — recorded associations</h2>
      <p className="text-sm text-slate-600">
        A staff-recorded property/association inventory, not proof of legal HOA
        membership, governance, assessments, fines or board authority.
        This panel never posts charges or general ledger entries.
      </p>
      {loading && <p className="text-sm text-slate-500">Loading associations…</p>}
      {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
      {message && <p role="status" className="text-sm text-green-700">{message}</p>}
      {!loading && (
        <>
          {linked.length === 0 && <p className="text-sm text-slate-500">
            No association recorded for this property; that does not establish an absence of HOA obligations.
          </p>}
          {linked.map((row) => (
            <div key={row.id} className="flex flex-wrap items-center justify-between gap-3 rounded-lg border p-3">
              <div className="text-sm">
                <div className="font-medium text-slate-900">{row.name}</div>
                <div className="text-xs text-slate-500">{row.property_ids.length} visible linked properties</div>
              </div>
              <div className="flex gap-3 text-sm">
                <button type="button" onClick={() => setContactsAssociation((old) => old === row.id ? null : row.id)}
                  className="text-blue-700">Contacts</button>
                <button type="button" onClick={() => setDraftAssociation((old) => old === row.id ? null : row.id)}
                  className="text-blue-700">Draft assessments</button>
                <button type="button" onClick={() => setObservationAssociation((old) => old === row.id ? null : row.id)}
                  className="text-blue-700">Staff observations</button>
                <button type="button" onClick={() => setMeetingAssociation((old) => old === row.id ? null : row.id)}
                  className="text-blue-700">Meeting plans</button>
                <button type="button" onClick={() => setArcAssociation((old) => old === row.id ? null : row.id)}
                  className="text-blue-700">ARC staff intake</button>
                <button type="button" onClick={() => setEvidenceAssociation((old) => old === row.id ? null : row.id)}
                  className="text-blue-700">Governing evidence</button>
              {canEdit && <>
                <button type="button" disabled={busy} onClick={() => { void changeMembership(row, false); }}
                  className="text-blue-700 disabled:opacity-50">Unlink</button>
                <button type="button" disabled={busy} onClick={() => { void archive(row); }}
                  className="text-red-700 disabled:opacity-50">Archive</button>
              </>}
              </div>
              {contactsAssociation === row.id && (
                <HoaContactsPanel associationId={row.id} propertyId={propertyId} canEdit={canEdit}
                  onClose={() => setContactsAssociation(null)} />
              )}
              {draftAssociation === row.id && (
                <HoaDraftAssessmentsPanel associationId={row.id} propertyId={propertyId}
                  canEdit={canEdit} onClose={() => setDraftAssociation(null)} />
              )}
              {observationAssociation === row.id && (
                <HoaObservationsPanel associationId={row.id} propertyId={propertyId}
                  canEdit={canEdit} onClose={() => setObservationAssociation(null)} />
              )}
              {meetingAssociation === row.id && (
                <HoaMeetingDraftsPanel associationId={row.id} propertyId={propertyId}
                  canEdit={canEdit} onClose={() => setMeetingAssociation(null)} />
              )}
              {arcAssociation === row.id && (
                <HoaARCIntakePanel associationId={row.id} propertyId={propertyId}
                  canEdit={canEdit} onClose={() => setArcAssociation(null)} />
              )}
              {evidenceAssociation === row.id && (
                <HoaGoverningEvidencePanel associationId={row.id} propertyId={propertyId}
                  canEdit={canEdit} onClose={() => setEvidenceAssociation(null)} />
              )}
            </div>
          ))}
          {canEdit && (
            <div className="space-y-3 border-t pt-3">
              {notLinked.length > 0 && (
                <div className="space-y-2">
                  <h3 className="text-sm font-semibold">Link an existing association</h3>
                  <div className="flex flex-wrap gap-2">
                    {notLinked.map((row) => <button key={row.id} type="button"
                      disabled={busy} onClick={() => { void changeMembership(row, true); }}
                      className="rounded border px-3 py-2 text-sm text-blue-700 disabled:opacity-50">
                      + {row.name}
                    </button>)}
                  </div>
                </div>
              )}
              <form onSubmit={(event) => { void create(event); }} className="space-y-3">
                <h3 className="text-sm font-semibold">Record a new association</h3>
                <label className="block text-sm">
                  Association name
                  <input required maxLength={160} value={name}
                    onChange={(event) => setName(event.target.value)}
                    className="mt-1 block w-full rounded border p-2"
                    placeholder="Staff-recorded association name" />
                </label>
                {availableOthers.length > 0 && (
                  <fieldset className="space-y-2 rounded border p-3">
                    <legend className="px-1 text-sm font-semibold">Additional properties (optional)</legend>
                    <p className="text-xs text-slate-500">
                      This property is included automatically. Select only confirmed links to other properties.
                    </p>
                    {availableOthers.map((p) => <label key={p.id} className="flex items-center gap-2 text-sm">
                      <input type="checkbox" checked={others.includes(p.id)}
                        onChange={(event) => setOthers((prior) => event.target.checked
                          ? [...prior, p.id] : prior.filter((id) => id !== p.id))} />
                      {p.name}
                    </label>)}
                  </fieldset>
                )}
                <button type="submit" disabled={busy || !name.trim()}
                  className="rounded bg-slate-900 px-4 py-2 text-sm text-white disabled:opacity-50">
                  {busy ? "Saving…" : "Record association"}
                </button>
              </form>
            </div>
          )}
        </>
      )}
    </section>
  );
}
