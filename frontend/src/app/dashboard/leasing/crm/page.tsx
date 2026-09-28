"use client";

import { useEffect, useState, type FormEvent } from "react";
import Link from "next/link";
import ProspectMarketingSummary from "@/components/leasing/ProspectMarketingSummary";
import { apiDelete, apiGet, apiPatch, apiPost } from "@/lib/api";

type Viewer = { role: string };
type Contact = { id: number; display_name: string; is_active: boolean };
type Property = { id: number; name: string; is_active: boolean };
type Lead = {
  id: number; property_id: number; contact_id: number;
  contact_name: string; contact_email: string | null;
  source: string; stage: Stage; next_follow_up: string | null;
};
type Stage = "NEW" | "CONTACTED" | "TOUR_SCHEDULED" | "APPLIED" | "CLOSED";
type LeadList = { items: Lead[]; total: number };
type ContactList = { items: Contact[]; total: number };
const STAGES: { value: Stage; title: string }[] = [
  { value: "NEW", title: "New" },
  { value: "CONTACTED", title: "Contacted" },
  { value: "TOUR_SCHEDULED", title: "Tour scheduled" },
  { value: "APPLIED", title: "Applied" },
  { value: "CLOSED", title: "Closed" },
];

export default function LeasingCrmPage() {
  const [viewer, setViewer] = useState<Viewer | null>(null);
  const [leads, setLeads] = useState<Lead[]>([]);
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [properties, setProperties] = useState<Property[]>([]);
  const [contactId, setContactId] = useState("");
  const [propertyId, setPropertyId] = useState("");
  const [source, setSource] = useState("OTHER");
  const [filter, setFilter] = useState<Stage | "ALL">("ALL");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [sourceVersion, setSourceVersion] = useState(0);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const canWrite = viewer?.role === "ADMIN" || viewer?.role === "MANAGER";

  async function refresh() {
    const list = await apiGet("/api/leasing/prospects") as LeadList;
    setLeads(list.items);
    setSourceVersion(v => v + 1);
  }

  useEffect(() => {
    let active = true;
    async function load() {
      try {
        const user = await apiGet("/auth/me") as Viewer;
        if (!active) return;
        setViewer(user);
        const list = await apiGet("/api/leasing/prospects") as LeadList;
        if (!active) return;
        setLeads(list.items);
        if (user.role === "ADMIN" || user.role === "MANAGER") {
          const [contactResult, propertyResult] = await Promise.allSettled([
            apiGet("/api/contacts") as Promise<ContactList>,
            apiGet("/properties") as Promise<Property[]>,
          ]);
          if (!active) return;
          if (contactResult.status === "fulfilled") setContacts(contactResult.value.items.filter(c => c.is_active));
          if (propertyResult.status === "fulfilled") setProperties(propertyResult.value.filter(p => p.is_active));
        }
      } catch (cause) {
        if (active) setError(cause instanceof Error ? cause.message : "CRM unavailable.");
      } finally {
        if (active) setLoading(false);
      }
    }
    void load();
    return () => { active = false; };
  }, []);

  async function create(event: FormEvent) {
    event.preventDefault();
    if (!canWrite) return;
    setBusy(true); setError(""); setMessage("");
    try {
      await apiPost("/api/leasing/prospects", {
        contact_id: Number(contactId), property_id: Number(propertyId),
        source: source.trim(), stage: "NEW",
      });
      await refresh();
      setContactId(""); setPropertyId(""); setSource("OTHER");
      setMessage("Prospect recorded. No application, guest card, or lease was created.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to create prospect.");
    } finally {
      setBusy(false);
    }
  }

  async function change(lead: Lead, changes: { stage?: Stage; next_follow_up?: string | null }) {
    if (!canWrite) return;
    setBusy(true); setError(""); setMessage("");
    try {
      await apiPatch(`/api/leasing/prospects/${lead.id}`, changes);
      await refresh();
      setMessage("Prospect stage or follow-up updated.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to update prospect.");
    } finally {
      setBusy(false);
    }
  }

  async function archive(lead: Lead) {
    if (!canWrite || !window.confirm("Archive this prospect?")) return;
    setBusy(true); setError(""); setMessage("");
    try {
      await apiDelete(`/api/leasing/prospects/${lead.id}`);
      await refresh();
      setMessage("Prospect archived.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to archive prospect.");
    } finally {
      setBusy(false);
    }
  }

  const visible = filter === "ALL" ? leads : leads.filter((lead) => lead.stage === filter);
  return (
    <div className="space-y-5">
      <div className="text-sm"><Link href="/dashboard/leasing/guest-cards" className="underline text-slate-700">Guest cards →</Link></div>
      <header>
        <h1 className="text-2xl font-semibold text-slate-900">Leasing CRM</h1>
        <p className="mt-1 text-sm text-slate-600">
          Track existing contacts through property-specific leasing follow-ups and marketing sources.
          This does not submit applications, send messages, or activate leases.
        </p>
      </header>
      {loading && <p className="text-sm text-slate-500">Loading prospects…</p>}
      {error && <p role="alert" className="rounded-lg border border-red-200 p-3 text-sm text-red-700">{error}</p>}
      {message && <p role="status" className="rounded-lg border border-green-200 p-3 text-sm text-green-700">{message}</p>}
      {!loading && <ProspectMarketingSummary version={sourceVersion} />}
      {!loading && canWrite && (
        <form onSubmit={(event) => { void create(event); }} className="space-y-3 rounded-xl border bg-white p-4">
          <h2 className="font-semibold">Add property prospect</h2>
          <p className="text-xs text-slate-500">Choose an existing organization contact; create new contacts in <Link href="/dashboard/contacts" className="underline">Contacts</Link> first. Nothing here creates a login identity.</p>
          <div className="grid gap-3 md:grid-cols-3">
            <label className="block text-sm font-medium">Contact
              <select required value={contactId} onChange={e=>setContactId(e.target.value)}
                className="mt-1 block w-full rounded-lg border p-2">
                <option value="">Select a contact</option>
                {contacts.map(c=><option key={c.id} value={c.id}>{c.display_name} (#{c.id})</option>)}
              </select>
            </label>
            <label className="block text-sm font-medium">Property
              <select required value={propertyId} onChange={e=>setPropertyId(e.target.value)}
                className="mt-1 block w-full rounded-lg border p-2">
                <option value="">Select property</option>
                {properties.map(p=><option key={p.id} value={p.id}>{p.name} (#{p.id})</option>)}
              </select>
            </label>
            <label className="block text-sm font-medium">Marketing source
              <input required maxLength={60} value={source} onChange={e=>setSource(e.target.value)}
                className="mt-1 block w-full rounded-lg border p-2" />
            </label>
          </div>
          <button type="submit" disabled={busy || !contactId || !propertyId}
            className="rounded-lg bg-slate-900 px-4 py-2 text-sm text-white disabled:opacity-50">
            {busy ? "Saving…" : "Add prospect"}
          </button>
        </form>
      )}
      {!loading && <section className="rounded-xl border bg-white p-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 className="font-semibold">Prospect pipeline ({visible.length})</h2>
          <label className="text-sm">Stage
            <select value={filter} onChange={e=>setFilter(e.target.value as Stage | "ALL")}
              className="ml-2 rounded-lg border px-2 py-1">
              <option value="ALL">All stages</option>
              {STAGES.map(s=><option key={s.value} value={s.value}>{s.title}</option>)}
            </select>
          </label>
        </div>
        {visible.length === 0 && <p className="mt-4 text-sm text-slate-500">No matching prospects.</p>}
        <div className="mt-4 space-y-3">
          {visible.map(lead=><article key={lead.id} className="flex flex-wrap items-center justify-between gap-4 rounded-lg border p-3">
            <div className="min-w-0">
              <h3 className="font-medium">{lead.contact_name}</h3>
              <p className="text-sm text-slate-600">{lead.contact_email || "No contact email"} · Property #{lead.property_id}</p>
              <p className="text-xs text-slate-500">Source: {lead.source}</p>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <label className="text-xs">Stage
                <select value={lead.stage} disabled={!canWrite || busy}
                  onChange={e=>{void change(lead,{stage:e.target.value as Stage});}}
                  className="ml-2 rounded-md border p-2 text-sm">
                  {STAGES.map(s=><option key={s.value} value={s.value}>{s.title}</option>)}
                </select>
              </label>
              <label className="text-xs">Follow-up
                <input type="date" disabled={!canWrite || busy}
                  value={lead.next_follow_up || ""}
                  onChange={e=>{void change(lead,{next_follow_up:e.target.value || null});}}
                  className="ml-2 rounded-md border p-2 text-sm" />
              </label>
              {canWrite && <button type="button" disabled={busy}
                onClick={()=>{void archive(lead);}}
                className="rounded-md border border-red-200 px-3 py-2 text-xs text-red-700 disabled:opacity-50">Archive</button>}
            </div>
          </article>)}
        </div>
      </section>}
    </div>
  );
}
