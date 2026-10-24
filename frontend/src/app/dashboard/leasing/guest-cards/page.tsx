"use client";

import { useEffect, useState, type FormEvent } from "react";
import Link from "next/link";
import { apiDelete, apiGet, apiPatch, apiPost } from "@/lib/api";

type Viewer = { role: string };
type Prospect = { id: number; contact_name: string; property_id: number; stage: string };
type LeadList = { items: Prospect[] };
type Unit = { id: number; unit_number: string; is_active: boolean };
type Card = {
  id: number; prospect_id: number; contact_name: string; property_id: number;
  visit_on: string; unit_id: number | null; attended: boolean;
  next_step: NextStep;
};
type CardList = { items: Card[] };
type NextStep = "NONE" | "FOLLOW_UP" | "APPLICATION_INVITED" | "NOT_INTERESTED" | "TOUR_RESCHEDULE";
const STEPS: { value: NextStep; label: string }[] = [
  {value:"NONE",label:"No next step"},
  {value:"FOLLOW_UP",label:"Follow up"},
  {value:"APPLICATION_INVITED",label:"Application suggested (no application created)"},
  {value:"NOT_INTERESTED",label:"Not interested"},
  {value:"TOUR_RESCHEDULE",label:"Reschedule tour"},
];

export default function GuestCardsPage() {
  const [viewer, setViewer] = useState<Viewer | null>(null);
  const [prospects, setProspects] = useState<Prospect[]>([]);
  const [rows, setRows] = useState<Card[]>([]);
  const [units, setUnits] = useState<Unit[]>([]);
  const [prospectId, setProspectId] = useState("");
  const [visitOn, setVisitOn] = useState("");
  const [unitId, setUnitId] = useState("");
  const [attended, setAttended] = useState(false);
  const [nextStep, setNextStep] = useState<NextStep>("NONE");
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const canWrite = viewer?.role === "ADMIN" || viewer?.role === "MANAGER";
  const selected = prospects.find(p=>p.id===Number(prospectId));

  async function refresh() {
    const list = await apiGet("/api/leasing/guest-cards") as CardList;
    setRows(list.items);
  }

  useEffect(() => {
    let active = true;
    async function load() {
      try {
        const me = await apiGet("/auth/me") as Viewer;
        const [leadList, cardList] = await Promise.all([
          apiGet("/api/leasing/prospects") as Promise<LeadList>,
          apiGet("/api/leasing/guest-cards") as Promise<CardList>,
        ]);
        if (!active) return;
        setViewer(me); setProspects(leadList.items); setRows(cardList.items);
      } catch (cause) {
        if (active) setError(cause instanceof Error ? cause.message : "Guest cards unavailable.");
      } finally {
        if (active) setLoading(false);
      }
    }
    void load();
    return () => { active = false; };
  }, []);

  useEffect(() => {
    let active = true;
    if (!selected || !canWrite) return;
    void (async () => {
      try {
        const result = await apiGet(`/properties/${selected.property_id}/units`) as Unit[];
        if (active) setUnits(result.filter(u=>u.is_active));
      } catch {
        if (active) setUnits([]);
      }
    })();
    return () => { active = false; };
  }, [selected?.property_id, canWrite]);

  async function save(event: FormEvent) {
    event.preventDefault();
    if (!canWrite || !prospectId || !visitOn) return;
    setBusy(true); setError(""); setMessage("");
    try {
      await apiPost("/api/leasing/guest-cards", {
        prospect_id:Number(prospectId), visit_on:visitOn,
        unit_id:unitId ? Number(unitId) : null, attended, next_step:nextStep,
      });
      await refresh();
      setVisitOn(""); setUnitId(""); setAttended(false); setNextStep("NONE");
      setMessage("Staff guest card recorded. No application or lease was created.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Guest card could not be saved.");
    } finally { setBusy(false); }
  }

  async function change(card: Card, updates: {attended?:boolean;next_step?:NextStep}) {
    if (!canWrite) return;
    setBusy(true); setError(""); setMessage("");
    try {
      await apiPatch(`/api/leasing/guest-cards/${card.id}`,updates);
      await refresh(); setMessage("Guest card updated.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Guest card could not be updated.");
    } finally { setBusy(false); }
  }

  async function archive(card: Card) {
    if (!canWrite || !window.confirm("Archive this guest card?")) return;
    setBusy(true); setError(""); setMessage("");
    try {
      await apiDelete(`/api/leasing/guest-cards/${card.id}`);
      await refresh(); setMessage("Guest card archived.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to archive guest card.");
    } finally { setBusy(false); }
  }

  return <div className="space-y-5">
    <Link href="/dashboard/leasing/crm" className="text-sm text-slate-600 underline">← Leasing CRM</Link>
    <header><h1 className="text-2xl font-semibold text-slate-900">Guest cards</h1>
      <p className="mt-1 text-sm text-slate-600">Staff-recorded property visits for existing prospects.
        No public check-in, tenant signature or application is created here.</p></header>
    {loading && <p className="text-sm text-slate-500">Loading guest cards…</p>}
    {error && <p role="alert" className="rounded-lg border border-red-200 p-3 text-sm text-red-700">{error}</p>}
    {message && <p role="status" className="rounded-lg border border-green-200 p-3 text-sm text-green-700">{message}</p>}
    {!loading && canWrite && <form onSubmit={event=>{void save(event);}} className="space-y-3 rounded-xl border bg-white p-4">
      <h2 className="font-semibold">Record a visit</h2>
      <div className="grid gap-3 md:grid-cols-3">
        <label className="text-sm font-medium">Prospect
          <select required value={prospectId}
            onChange={event=>{setProspectId(event.target.value);setUnitId("");setUnits([]);}}
            className="mt-1 block w-full rounded-lg border p-2">
            <option value="">Choose prospect</option>
            {prospects.map(p=><option value={p.id} key={p.id}>{p.contact_name} · Property #{p.property_id}</option>)}
          </select>
        </label>
        <label className="text-sm font-medium">Visit date
          <input required type="date" value={visitOn} onChange={event=>setVisitOn(event.target.value)}
            className="mt-1 block w-full rounded-lg border p-2" />
        </label>
        <label className="text-sm font-medium">Unit (optional)
          <select value={unitId} onChange={event=>setUnitId(event.target.value)}
            className="mt-1 block w-full rounded-lg border p-2" disabled={!selected}>
            <option value="">Property only</option>
            {units.map(u=><option value={u.id} key={u.id}>Unit {u.unit_number}</option>)}
          </select>
        </label>
      </div>
      <div className="flex flex-wrap gap-4">
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={attended} onChange={event=>setAttended(event.target.checked)} />
          Guest attended
        </label>
        <label className="text-sm">Next step
          <select value={nextStep} onChange={event=>setNextStep(event.target.value as NextStep)}
            className="ml-2 rounded-lg border p-2">
            {STEPS.map(s=><option key={s.value} value={s.value}>{s.label}</option>)}
          </select>
        </label>
      </div>
      <button type="submit" disabled={busy || !prospectId || !visitOn}
        className="rounded-lg bg-slate-900 px-4 py-2 text-sm text-white disabled:opacity-50">
        {busy ? "Saving…" : "Record guest card"}
      </button>
    </form>}
    {!loading && <section className="rounded-xl border bg-white p-4">
      <h2 className="font-semibold">Recorded visits ({rows.length})</h2>
      {rows.length===0 && <p className="mt-2 text-sm text-slate-500">No guest cards recorded.</p>}
      <div className="mt-3 space-y-3">
        {rows.map(card=><article key={card.id} className="flex flex-wrap items-center justify-between gap-3 rounded-lg border p-3 text-sm">
          <div><p className="font-medium">{card.contact_name}</p>
            <p className="text-slate-600">Visit {card.visit_on} · Property #{card.property_id}{card.unit_id ? ` · Unit #${card.unit_id}` : ""}</p></div>
          <div className="flex flex-wrap items-center gap-2">
            <label className="flex items-center gap-2">
              <input type="checkbox" disabled={!canWrite || busy} checked={card.attended}
                onChange={event=>{void change(card,{attended:event.target.checked});}} />
              Attended
            </label>
            <select aria-label="Guest card next step" disabled={!canWrite || busy}
              value={card.next_step} onChange={event=>{void change(card,{next_step:event.target.value as NextStep});}}
              className="rounded-lg border p-2">
              {STEPS.map(s=><option value={s.value} key={s.value}>{s.label}</option>)}
            </select>
            {canWrite && <button type="button" disabled={busy} onClick={()=>{void archive(card);}}
              className="rounded-lg border border-red-200 p-2 text-red-700 disabled:opacity-50">Archive</button>}
          </div>
        </article>)}
      </div>
    </section>}
  </div>;
}
