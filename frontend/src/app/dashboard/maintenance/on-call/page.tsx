"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { apiGet } from "@/lib/api";

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

export default function OnCallCalendarPage() {
  const [start, setStart] = useState(() => new Date().toISOString().slice(0, 10));
  const [showCancelled, setShowCancelled] = useState(false);
  const [shifts, setShifts] = useState<Shift[] | null>(null);
  const [error, setError] = useState("");
  const dates = Array.from({ length: 7 }, (_, i) => utcDayDelta(start, i));

  useEffect(() => {
    let active = true;
    setShifts(null); setError("");
    const query = new URLSearchParams({ start, days: "7", include_cancelled: String(showCancelled) });
    apiGet("/work-orders/on-call-calendar?" + query.toString())
      .then((result: Shift[]) => {
        if (!Array.isArray(result)) throw new Error("Unexpected calendar response.");
        if (active) setShifts(result);
      })
      .catch((cause) => {
        if (active) setError(cause instanceof Error ? cause.message : "Unable to load on-call coverage.");
      });
    return () => { active = false; };
  }, [start, showCancelled]);

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
        <Link href="/dashboard/maintenance/work-orders" className="rounded-lg border px-4 py-2 text-sm">Work orders</Link>
      </header>
      <section className="flex flex-wrap items-end gap-3 rounded-xl border bg-white p-4" aria-label="On-call calendar filters">
        <label className="text-sm">Week starting (UTC)
          <input type="date" aria-label="On-call calendar start" value={start}
            onChange={(event) => { if (event.target.value) setStart(event.target.value); }}
            className="mt-1 block rounded border p-2" />
        </label>
        <button type="button" onClick={() => setStart((value) => utcDayDelta(value, -7))}
          className="rounded border px-3 py-2 text-sm">Previous week</button>
        <button type="button" onClick={() => setStart((value) => utcDayDelta(value, 7))}
          className="rounded border px-3 py-2 text-sm">Next week</button>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={showCancelled} onChange={(event) => setShowCancelled(event.target.checked)}/>
          Include cancelled coverage
        </label>
      </section>
      {error && <p role="alert" className="rounded border border-red-300 bg-red-50 p-3 text-sm text-red-800">{error}</p>}
      <section aria-label="Seven-day on-call coverage" className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
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
                    </li>)}
                  </ul>}
          </article>;
        })}
      </section>
      <p className="text-xs text-slate-500">
        The date filters use UTC boundaries; displayed shift times use your local timezone.
        Creating or cancelling coverage requires an authorized property work order.
      </p>
    </div>
  );
}
