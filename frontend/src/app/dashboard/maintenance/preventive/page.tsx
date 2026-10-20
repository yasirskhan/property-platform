"use client";
import { FormEvent, useEffect, useState } from "react";
import Link from "next/link";
import { apiGet, apiPost, apiPatch } from "@/lib/api";

type UnitChoice = { id: number; property_name: string; unit_number: string };
type Schedule = {
  id: number; organization_id: number; property_id: number; unit_id: number;
  title: string; description: string; interval_days: number;
  next_due_date: string; active: boolean;
};
type Occurrence = { id: number; schedule_id: number; due_date: string; work_order_id: number };
type Generation = { work_order_id: number; newly_created: boolean; tenant_id: number | null };

export default function PreventiveMaintenancePage() {
  const [units, setUnits] = useState<UnitChoice[]>([]);
  const [unitSearch, setUnitSearch] = useState("");
  const [unitId, setUnitId] = useState("");
  const [unitsError, setUnitsError] = useState("");
  const [unitsLoading, setUnitsLoading] = useState(true);
  const [schedules, setSchedules] = useState<Schedule[]>([]);
  const [loading, setLoading] = useState(true);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [interval, setInterval] = useState("30");
  const [dueDate, setDueDate] = useState("");
  const [saving, setSaving] = useState(false);
  const [busyId, setBusyId] = useState<number | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [historyId, setHistoryId] = useState<number | null>(null);
  const [occurrences, setOccurrences] = useState<Occurrence[]>([]);
  const [historyError, setHistoryError] = useState("");

  async function refreshSchedules() {
    const rows = await apiGet("/api/maintenance/preventive/schedules") as Schedule[];
    if (!Array.isArray(rows)) throw new Error("Unexpected schedule response.");
    setSchedules(rows);
  }

  useEffect(() => {
    let active = true;
    apiGet("/api/maintenance/preventive/schedules")
      .then((rows: Schedule[]) => {
        if (!Array.isArray(rows)) throw new Error("Unexpected schedule response.");
        if (active) setSchedules(rows);
      })
      .catch((cause) => {
        if (active) setError(cause instanceof Error ? cause.message : "Schedules unavailable.");
      })
      .finally(() => { if (active) setLoading(false); });
    apiGet("/work-orders/request-units?limit=100")
      .then((rows: UnitChoice[]) => {
        if (!Array.isArray(rows)) throw new Error("Unexpected units response.");
        if (active) setUnits(rows);
      })
      .catch((cause) => {
        if (active) setUnitsError(cause instanceof Error ? cause.message : "Units unavailable.");
      })
      .finally(() => { if (active) setUnitsLoading(false); });
    return () => { active = false; };
  }, []);

  async function searchUnits(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setUnitsLoading(true);
    setUnitsError("");
    setUnitId("");
    try {
      const query = new URLSearchParams({ limit: "100" });
      if (unitSearch.trim()) query.set("search", unitSearch.trim());
      const rows = await apiGet("/work-orders/request-units?" + query.toString()) as UnitChoice[];
      if (!Array.isArray(rows)) throw new Error("Unexpected units response.");
      setUnits(rows);
    } catch (cause) {
      setUnitsError(cause instanceof Error ? cause.message : "Unit search failed.");
      setUnits([]);
    } finally {
      setUnitsLoading(false);
    }
  }

  async function create(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!units.some((unit) => String(unit.id) === unitId)) {
      setError("Choose an authorized unit.");
      return;
    }
    setSaving(true); setError(""); setNotice("");
    try {
      const created = await apiPost("/api/maintenance/preventive/schedules", {
        unit_id: Number(unitId), title: title.trim(), description: description.trim(),
        interval_days: Number(interval), next_due_date: dueDate,
      }) as Schedule;
      if (!Number.isSafeInteger(created?.id)) throw new Error("Invalid saved schedule.");
      setSchedules((previous) => [created, ...previous.filter((row) => row.id !== created.id)]);
      setTitle(""); setDescription(""); setDueDate("");
      setNotice("Schedule saved. No work order was generated at creation; due dates are checked daily.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Schedule could not be saved.");
    } finally { setSaving(false); }
  }

  async function toggle(row: Schedule) {
    setBusyId(row.id); setError(""); setNotice("");
    try {
      const updated = await apiPatch(`/api/maintenance/preventive/schedules/${row.id}`,
        { active: !row.active }) as Schedule;
      setSchedules((previous) => previous.map((item) => item.id === row.id ? updated : item));
      setNotice(updated.active ? "Schedule resumed." : "Schedule paused.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Cannot change schedule.");
    } finally { setBusyId(null); }
  }

  async function generate(row: Schedule) {
    setBusyId(row.id); setError(""); setNotice("");
    try {
      const result = await apiPost(
        `/api/maintenance/preventive/schedules/${row.id}/generate`,
      ) as Generation;
      if (!Number.isSafeInteger(result.work_order_id) || result.tenant_id !== null)
        throw new Error("Unexpected preventive generation response.");
      await refreshSchedules();
      setNotice(result.newly_created
        ? `Work order #${result.work_order_id} generated without a tenant or automatic charge.`
        : `Due occurrence already exists as work order #${result.work_order_id}.`);
      if (historyId === row.id) await showHistory(row.id);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Cannot generate due occurrence.");
    } finally { setBusyId(null); }
  }

  async function showHistory(id: number) {
    setHistoryId(id); setHistoryError("");
    try {
      const rows = await apiGet(`/api/maintenance/preventive/schedules/${id}/occurrences?limit=100`) as Occurrence[];
      if (!Array.isArray(rows)) throw new Error("Unexpected occurrence history.");
      setOccurrences(rows);
    } catch (cause) {
      setOccurrences([]);
      setHistoryError(cause instanceof Error ? cause.message : "Occurrence history unavailable.");
    }
  }

  const unitLabel = (unit: UnitChoice) => `${unit.property_name} · Unit ${unit.unit_number}`;
  return <main className="mx-auto max-w-5xl space-y-5">
    <Link href="/dashboard/maintenance/work-orders" className="text-sm text-blue-800 hover:underline">
      Back to maintenance work orders
    </Link>
    <header>
      <h1 className="text-2xl font-semibold">Preventive maintenance schedules</h1>
      <p className="mt-1 text-sm text-slate-600">
        Active schedules are checked daily for due work orders. Staff can also generate a due order
        manually. No automatic dispatch, entry authorization, or tenant charge occurs.
      </p>
    </header>
    {error && <p role="alert" className="rounded-lg border p-3 text-sm text-red-700">{error}</p>}
    {notice && <p role="status" className="rounded-lg border p-3 text-sm">{notice}</p>}
    <form onSubmit={(event) => void searchUnits(event)} className="rounded-xl border bg-white p-4">
      <label className="text-sm">Find an authorized unit
        <input value={unitSearch} maxLength={80} aria-label="Search preventive maintenance units"
          onChange={(event) => setUnitSearch(event.target.value)}
          className="mt-1 block w-full rounded-lg border p-2" />
      </label>
      <button disabled={unitsLoading} className="mt-2 rounded-lg border px-4 py-2 text-sm" type="submit">
        {unitsLoading ? "Searching…" : "Search units"}
      </button>
      {unitsError && <p role="alert" className="text-sm text-red-700">{unitsError}</p>}
    </form>
    <form onSubmit={(event) => void create(event)} className="space-y-3 rounded-xl border bg-white p-5">
      <h2 className="font-semibold">New preventive schedule</h2>
      <label className="block text-sm">Unit
        <select required value={unitId} aria-label="Preventive maintenance unit"
          disabled={unitsLoading || saving} onChange={(event) => setUnitId(event.target.value)}
          className="mt-1 w-full rounded-lg border p-2">
          <option value="">Choose an authorized unit</option>
          {units.map((unit) => <option key={unit.id} value={unit.id}>{unitLabel(unit)}</option>)}
        </select>
      </label>
      <label className="block text-sm">Task title
        <input required minLength={3} maxLength={255} value={title}
          aria-label="Preventive task title" onChange={(event) => setTitle(event.target.value)}
          className="mt-1 w-full rounded-lg border p-2" />
      </label>
      <label className="block text-sm">Instructions
        <textarea required minLength={10} maxLength={2000} rows={3} value={description}
          aria-label="Preventive task description"
          onChange={(event) => setDescription(event.target.value)}
          className="mt-1 w-full rounded-lg border p-2" />
      </label>
      <div className="grid gap-3 sm:grid-cols-2">
        <label className="block text-sm">Repeat every (days)
          <input type="number" min={1} max={3650} required value={interval}
            aria-label="Preventive schedule interval"
            onChange={(event) => setInterval(event.target.value)}
            className="mt-1 w-full rounded-lg border p-2" />
        </label>
        <label className="block text-sm">First due date
          <input type="date" required value={dueDate}
            aria-label="Preventive first due date"
            onChange={(event) => setDueDate(event.target.value)}
            className="mt-1 w-full rounded-lg border p-2" />
        </label>
      </div>
      <button type="submit" disabled={saving || unitsLoading}
        className="rounded-lg bg-slate-900 px-4 py-2 text-sm text-white disabled:opacity-50">
        {saving ? "Saving…" : "Save schedule"}
      </button>
    </form>
    <section className="space-y-3 rounded-xl border bg-white p-5">
      <h2 className="font-semibold">Authorized schedules</h2>
      {loading && <p>Loading schedules…</p>}
      {!loading && schedules.length === 0 && <p>No preventive schedules yet.</p>}
      {schedules.map((row) => <article key={row.id} className="space-y-2 rounded-lg border p-4">
        <h3 className="font-medium">{row.title} · Schedule #{row.id}</h3>
        <p className="text-sm text-slate-600">
          Unit #{row.unit_id} · Every {row.interval_days} days · Next due {row.next_due_date}
          {" · "}{row.active ? "Active" : "Paused"}
        </p>
        <p className="whitespace-pre-wrap text-sm">{row.description}</p>
        <div className="flex flex-wrap gap-2">
          <button disabled={busyId !== null} onClick={() => void toggle(row)}
            className="rounded-lg border px-3 py-2 text-sm disabled:opacity-50">
            {row.active ? "Pause" : "Resume"}
          </button>
          <button disabled={busyId !== null || !row.active} onClick={() => void generate(row)}
            className="rounded-lg border px-3 py-2 text-sm disabled:opacity-50">
            Generate due work order
          </button>
          <button disabled={busyId !== null} onClick={() => void showHistory(row.id)}
            className="rounded-lg border px-3 py-2 text-sm disabled:opacity-50">
            Occurrence history
          </button>
        </div>
        {historyId === row.id && <div className="space-y-2 border-t pt-3">
          {historyError && <p role="alert" className="text-sm text-red-700">{historyError}</p>}
          {!historyError && occurrences.length === 0 && <p className="text-sm">No work orders generated yet.</p>}
          {occurrences.map((item) => <p key={item.id} className="text-sm">
            {item.due_date}: <Link href={`/dashboard/maintenance/work-orders/${item.work_order_id}`}
              className="text-blue-800 underline">Work order #{item.work_order_id}</Link>
          </p>)}
        </div>}
      </article>)}
    </section>
  </main>;
}
