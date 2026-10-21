"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { apiGet, apiPost } from "@/lib/api";

type OnCallRoster = {
  property_id: number;
  property_name: string;
  crew: { id: number; name: string }[];
};

type Shift = {
  id: number;
  property_id: number;
  property_name: string;
  crew_user_id: number;
  crew_name: string;
  starts_at: string;
  ends_at: string;
  cancelled_at: string | null;
  cancellation_reason: string | null;
};

function utcDayDelta(iso: string, days: number): string {
  const date = new Date(iso + "T00:00:00Z");
  date.setUTCDate(date.getUTCDate() + days);
  return date.toISOString().slice(0, 10);
}

function monthStart(iso: string): string {
  return iso.slice(0, 7) + "-01";
}

function monthOffset(iso: string, delta: number): string {
  const [year, month] = monthStart(iso).split("-").map(Number);
  return new Date(Date.UTC(year, month - 1 + delta, 1)).toISOString().slice(0, 10);
}

function daysInMonth(iso: string): number {
  const [year, month] = monthStart(iso).split("-").map(Number);
  return new Date(Date.UTC(year, month, 0)).getUTCDate();
}

export default function OnCallCalendarPage() {
  const [start, setStart] = useState(() => new Date().toISOString().slice(0, 10));
  const [showCancelled, setShowCancelled] = useState(false);
  const [calendarView, setCalendarView] = useState<"week" | "month">("week");
  const [shifts, setShifts] = useState<Shift[] | null>(null);
  const [error, setError] = useState("");
  const [viewerRole, setViewerRole] = useState("");
  const [notice, setNotice] = useState("");
  const [revision, setRevision] = useState(0);
  const [roster, setRoster] = useState<OnCallRoster[] | null>(null);
  const [propertyId, setPropertyId] = useState("");
  const [crewId, setCrewId] = useState("");
  const [shiftStart, setShiftStart] = useState("");
  const [shiftEnd, setShiftEnd] = useState("");
  const [saving, setSaving] = useState(false);
  const [cancelId, setCancelId] = useState<number | null>(null);
  const [cancelReason, setCancelReason] = useState("");
  const dateCount = calendarView === "month" ? daysInMonth(start) : 7;
  const viewStart = calendarView === "month" ? monthStart(start) : start;
  const dates = Array.from({ length: dateCount }, (_, i) => utcDayDelta(viewStart, i));
  const chosenProperty = roster?.find((item) => String(item.property_id) === propertyId);

  useEffect(() => {
    let active = true;
    apiGet("/auth/me").then((viewer: {role: string}) => {
      if (!active) return;
      setViewerRole(String(viewer.role).toUpperCase());
      if (!active || !["ADMIN", "OWNER", "MANAGER"].includes(String(viewer.role).toUpperCase())) return;
      apiGet("/work-orders/on-call-property-roster").then((rows: OnCallRoster[]) => {
        if (!Array.isArray(rows)) throw new Error("Invalid on-call property roster.");
        if (active) setRoster(rows);
      }).catch(() => { if (active) setRoster(null); });
    }).catch(() => { if (active) setRoster(null); });
    return () => { active = false; };
  }, []);

  async function scheduleFromCalendar() {
    if (saving || !chosenProperty) return;
    const selectedCrew = Number(crewId);
    const a = new Date(shiftStart), b = new Date(shiftEnd);
    if (!chosenProperty.crew.some((person) => person.id === selectedCrew) ||
        !shiftStart || !shiftEnd || Number.isNaN(a.getTime()) || Number.isNaN(b.getTime()) ||
        a <= new Date() || b <= a) {
      setError("Choose assigned property crew and a valid future schedule."); return;
    }
    setSaving(true); setError(""); setNotice("");
    try {
      const saved = await apiPost(
        "/work-orders/on-call-property/" + chosenProperty.property_id + "/shifts", {
          crew_user_id: selectedCrew, starts_at: a.toISOString(), ends_at: b.toISOString(),
        }) as Shift;
      if (!saved || !Number.isSafeInteger(saved.id) || saved.crew_user_id !== selectedCrew)
        throw new Error("Unexpected on-call scheduling response.");
      setCrewId(""); setShiftStart(""); setShiftEnd("");
      setNotice("On-call shift scheduled for the selected property. No automatic dispatch was performed.");
      setRevision((value) => value + 1);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Could not schedule shift."); }
    finally { setSaving(false); }
  }

  async function cancelFromCalendar(item: Shift) {
    if (saving || cancelReason.trim().length < 5) {
      setError("Cancellation reason must contain at least five characters."); return;
    }
    setSaving(true); setError(""); setNotice("");
    try {
      const saved = await apiPost(
        "/work-orders/on-call-property/" + item.property_id + "/shifts/" + item.id + "/cancel",
        {reason: cancelReason.trim()},
      ) as Shift;
      if (!saved || saved.id !== item.id || !saved.cancelled_at)
        throw new Error("Unexpected on-call cancellation response.");
      setCancelId(null); setCancelReason("");
      setNotice("On-call shift cancelled with reason and audit history preserved.");
      setRevision((value) => value + 1);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Could not cancel on-call shift."); }
    finally { setSaving(false); }
  }

  useEffect(() => {
    let active = true;
    setShifts(null); setError("");
    const query = new URLSearchParams({ start: viewStart, days: String(dateCount), include_cancelled: String(showCancelled) });
    apiGet("/work-orders/on-call-calendar?" + query.toString())
      .then((result: Shift[]) => {
        if (!Array.isArray(result)) throw new Error("Unexpected calendar response.");
        if (active) setShifts(result);
      })
      .catch((cause) => {
        if (active) setError(cause instanceof Error ? cause.message : "Unable to load on-call coverage.");
      });
    return () => { active = false; };
  }, [viewStart, dateCount, showCancelled, revision]);

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold">Maintenance on-call calendar</h1>
          <p className="mt-1 text-sm text-slate-600">
            Primary crew coverage, scoped to properties you manage or shifts assigned to you.
            These are schedules only, not automatic dispatch orders.
          </p>
        </div>
        <div className="flex flex-wrap gap-2"><Link href="/dashboard/maintenance/work-orders" className="rounded-lg border px-4 py-2 text-sm">Work orders</Link>
          <Link href="/dashboard/maintenance/dispatch-attention" className="rounded-lg border px-4 py-2 text-sm">Dispatch attention</Link>
        {["ADMIN", "OWNER"].includes(viewerRole) && <Link href="/dashboard/maintenance/dispatch-settings" className="rounded-lg border px-4 py-2 text-sm">Dispatch settings</Link>}
      </div>
      </header>
      {roster && (
        <section aria-label="Schedule on-call crew from calendar" className="rounded-xl border bg-white p-5">
          <h2 className="font-semibold">Schedule primary crew coverage</h2>
          <p className="mt-1 text-xs text-slate-500">Choose your property, its active assigned crew and a future shift of up to 72 hours.</p>
          <div className="mt-3 grid gap-3 md:grid-cols-4">
            <label className="text-sm">Property
              <select aria-label="On-call calendar property" className="mt-1 block w-full rounded border p-2"
                value={propertyId} disabled={saving} onChange={(event) => {
                  setPropertyId(event.target.value); setCrewId("");
                }}>
                <option value="">Choose property</option>
                {roster.map((item) => <option key={item.property_id} value={item.property_id}>
                  {item.property_name}
                </option>)}
              </select>
            </label>
            <label className="text-sm">Assigned crew
              <select aria-label="On-call calendar crew" className="mt-1 block w-full rounded border p-2"
                value={crewId} disabled={saving || !chosenProperty}
                onChange={(event) => setCrewId(event.target.value)}>
                <option value="">Choose crew</option>
                {(chosenProperty?.crew || []).map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
              </select>
            </label>
            <label className="text-sm">Start time
              <input aria-label="On-call calendar shift start" type="datetime-local" value={shiftStart}
                onChange={(event) => setShiftStart(event.target.value)} disabled={saving}
                className="mt-1 block w-full rounded border p-2" />
            </label>
            <label className="text-sm">End time
              <input aria-label="On-call calendar shift end" type="datetime-local" value={shiftEnd}
                onChange={(event) => setShiftEnd(event.target.value)} disabled={saving}
                className="mt-1 block w-full rounded border p-2" />
            </label>
          </div>
          <button type="button" onClick={() => void scheduleFromCalendar()}
            disabled={saving || !propertyId || !crewId || !shiftStart || !shiftEnd}
            className="mt-3 rounded bg-slate-900 px-4 py-2 text-sm text-white disabled:opacity-40">
            Schedule coverage
          </button>
        </section>
      )}
      <section className="flex flex-wrap items-end gap-3 rounded-xl border bg-white p-4" aria-label="On-call calendar filters">
        <label className="text-sm">Calendar view
          <select aria-label="On-call calendar view" value={calendarView}
            onChange={(event) => {
              const chosen = event.target.value === "month" ? "month" : "week";
              setCalendarView(chosen);
              if (chosen === "month") setStart(monthStart(start));
            }}
            className="mt-1 block rounded border p-2">
            <option value="week">Seven-day view</option>
            <option value="month">Month view</option>
          </select>
        </label>
        <label className="text-sm">{calendarView === "month" ? "Month starting (UTC)" : "Week starting (UTC)"}
          <input type="date" aria-label="On-call calendar start" value={start}
            onChange={(event) => { if (event.target.value) setStart(calendarView === "month" ? monthStart(event.target.value) : event.target.value); }}
            className="mt-1 block rounded border p-2" />
        </label>
        <button type="button" onClick={() => setStart((value) =>
          calendarView === "month" ? monthOffset(value, -1) : utcDayDelta(value, -7))}
          className="rounded border px-3 py-2 text-sm">
          {calendarView === "month" ? "Previous month" : "Previous week"}
        </button>
        <button type="button" onClick={() => setStart((value) =>
          calendarView === "month" ? monthOffset(value, 1) : utcDayDelta(value, 7))}
          className="rounded border px-3 py-2 text-sm">
          {calendarView === "month" ? "Next month" : "Next week"}
        </button>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={showCancelled} onChange={(event) => setShowCancelled(event.target.checked)}/>
          Include cancelled coverage
        </label>
      </section>
      {error && <p role="alert" className="rounded border border-red-300 bg-red-50 p-3 text-sm text-red-800">{error}</p>}
      {notice && <p role="status" className="rounded border bg-white p-3 text-sm text-slate-700">{notice}</p>}
      <section aria-label={calendarView === "month" ? "Monthly on-call coverage" : "Seven-day on-call coverage"}
        className={calendarView === "month" ? "grid gap-3 sm:grid-cols-2 lg:grid-cols-7" : "grid gap-3 md:grid-cols-2 xl:grid-cols-4"}>
        {dates.map((day) => {
          const first = Date.parse(day + "T00:00:00Z");
          const end = first + 24 * 60 * 60 * 1000;
          const entries = (shifts || []).filter((row) => {
            const begin = Date.parse(row.starts_at + "Z");
            const finish = Date.parse(row.ends_at + "Z");
            return begin < end && finish > first;
          });
          return <article key={day} className="rounded-xl border bg-white p-4">
            <h2 className="font-semibold">{new Date(day + "T00:00:00Z").toLocaleDateString(undefined, {
              weekday: "short", month: "short", day: "numeric", timeZone: "UTC",
            })}</h2>
            {shifts === null
              ? <p className="mt-2 text-sm text-slate-500">Loading coverage…</p>
              : entries.length === 0
                ? <p className="mt-2 text-sm text-slate-500">No scheduled coverage</p>
                : <ul className="mt-2 space-y-3">
                    {entries.map((item) => <li key={item.id} className="rounded border p-2 text-sm">
                      <p className="font-medium">{item.crew_name}</p>
                      <p className="text-slate-600">{item.property_name}</p>
                      <p className="text-xs text-slate-600">
                        {new Date(item.starts_at + "Z").toLocaleString()} – {new Date(item.ends_at + "Z").toLocaleString()}
                      </p>
                      {item.cancelled_at && <p className="text-xs text-amber-700">Cancelled: {item.cancellation_reason}</p>}
                      {!item.cancelled_at && roster && (
                        cancelId === item.id ?
                          <div className="mt-2 space-y-2">
                            <textarea aria-label={"On-call calendar cancellation reason " + item.id}
                              className="w-full rounded border p-2" maxLength={1000} value={cancelReason}
                              onChange={(event) => setCancelReason(event.target.value)} disabled={saving} />
                            <button type="button" disabled={saving || cancelReason.trim().length < 5}
                              onClick={() => void cancelFromCalendar(item)}
                              className="rounded bg-slate-900 px-2 py-1 text-xs text-white">Confirm cancellation</button>
                            <button type="button" disabled={saving} onClick={() => { setCancelId(null); setCancelReason(""); }}
                              className="ml-2 rounded border px-2 py-1 text-xs">Keep coverage</button>
                          </div> :
                          <button type="button" disabled={saving} onClick={() => { setCancelId(item.id); setCancelReason(""); }}
                            className="mt-2 rounded border px-2 py-1 text-xs">Cancel coverage</button>
                      )}
                    </li>)}
                  </ul>}
          </article>;
        })}
      </section>
      <p className="text-xs text-slate-500">
        Seven-day and month views use UTC day boundaries; displayed shift times use your local timezone.
        Authorized managers can schedule and cancel directly above; crew have a read-only view.
      </p>
    </div>
  );
}
