"use client";

import { FormEvent, useEffect, useState } from "react";
import Link from "next/link";
import { apiGet } from "@/lib/api";

const PAGE_SIZE = 50;
const STATUSES = ["submitted", "acknowledged", "assigned", "in_progress", "completed", "closed", "cancelled"];
const PRIORITIES = ["low", "medium", "high", "emergency"];
const CATEGORIES = ["plumbing", "electrical", "hvac", "appliance", "general", "pest", "cleaning", "landscaping", "other"];

type QueueSummary = { open: number; emergency_open: number; awaiting_assignment: number; pending_crew_response: number; declined_assignment: number; recalled_assignment: number; in_progress: number; ready_to_close: number };

type WorkOrder = {
  id: number;
  property_id: number;
  unit_id: number;
  property_name?: string | null;
  unit_number?: string | null;
  title: string;
  description: string;
  status: string;
  assignment_response?: string | null;
  priority: string;
  category: string;
  created_at: string;
};
type PendingCrewTimeReview = {
  id: number;
  work_order_id: number;
  work_order_title: string;
  property_id: number;
  property_name: string;
  original_minutes: number;
  proposed_minutes: number;
  reason: string;
  created_at: string;
};

type Filters = { status: string; priority: string; category: string; property: string; search: string; assignment_response: string };
const EMPTY: Filters = { status: "", priority: "", category: "", property: "", search: "", assignment_response: "" };

export default function WorkOrderQueuePage() {
  const [draft, setDraft] = useState<Filters>(EMPTY);
  const [applied, setApplied] = useState<Filters>(EMPTY);
  const [offset, setOffset] = useState(0);
  const [reload, setReload] = useState(0);
  const [rows, setRows] = useState<WorkOrder[]>([]);
  const [canCreate, setCanCreate] = useState(false);
  const [canInspect, setCanInspect] = useState(false);
  const [canViewOnCall, setCanViewOnCall] = useState(false);
  const [canReviewTime, setCanReviewTime] = useState(false);
  const [pendingTimeReviews, setPendingTimeReviews] = useState<PendingCrewTimeReview[] | null>(null);
  const [timeReviewOffset, setTimeReviewOffset] = useState(0);
  const [summary, setSummary] = useState<QueueSummary | null>(null);
  const [triage, setTriage] = useState<WorkOrder[] | null>(null);
  const [triageLoading, setTriageLoading] = useState(true);
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    const query = new URLSearchParams({
      limit: String(PAGE_SIZE),
      offset: String(offset),
    });
    if (applied.status) query.set("status", applied.status);
    if (applied.assignment_response) query.set("assignment_response", applied.assignment_response);
    if (applied.priority) query.set("priority", applied.priority);
    if (applied.category) query.set("category", applied.category);
    if (applied.property) query.set("property_id", applied.property);
    if (applied.search) query.set("search", applied.search);
    async function load() {
      setBusy(true);
      setError("");
      setRows([]);
      try {
        const result = await apiGet("/work-orders?" + query.toString()) as WorkOrder[];
        if (!Array.isArray(result)) throw new Error("Unexpected work order list response.");
        if (active) setRows(result);
      } catch (err) {
        if (active) setError(err instanceof Error ? err.message : "Unable to load work orders.");
      } finally {
        if (active) setBusy(false);
      }
    }
    void load();
    return () => { active = false; };
  }, [applied, offset, reload]);

  useEffect(() => {
    let active = true;
    setSummary(null);
    apiGet("/work-orders/summary")
      .then((result: QueueSummary) => { if (active) setSummary(result); })
      .catch(() => { if (active) setSummary(null); });
    return () => { active = false; };
  }, [reload]);

  useEffect(() => {
    let active = true;
    setTriage(null);
    setTriageLoading(true);
    apiGet("/work-orders/triage")
      .then((items: WorkOrder[]) => {
        if (!Array.isArray(items)) throw new Error("Unexpected triage response.");
        if (active) setTriage(items);
      })
      .catch(() => { if (active) setTriage(null); })
      .finally(() => { if (active) setTriageLoading(false); });
    return () => { active = false; };
  }, [reload]);

  useEffect(() => {
    let active = true;
    apiGet("/auth/me").then((viewer: { role: string }) => {
      if (active) setCanCreate(
        ["ADMIN", "OWNER", "MANAGER", "TENANT"].includes(String(viewer.role).toUpperCase())
      );
      if (active) setCanInspect(["ADMIN", "MANAGER"].includes(String(viewer.role).toUpperCase()));
      if (active) setCanViewOnCall(["ADMIN", "OWNER", "MANAGER", "CREW"].includes(String(viewer.role).toUpperCase()));
      if (active) setCanReviewTime(["ADMIN", "OWNER", "MANAGER"].includes(String(viewer.role).toUpperCase()));
    }).catch(() => { if (active) { setCanCreate(false); setCanReviewTime(false); setCanViewOnCall(false); } });
    return () => { active = false; };
  }, []);

  useEffect(() => {
    if (!canReviewTime) { setPendingTimeReviews(null); return; }
    let active = true;
    setPendingTimeReviews(null);
    apiGet("/work-orders/time-corrections/pending?limit=10&offset=" + timeReviewOffset)
      .then((rows: PendingCrewTimeReview[]) => {
        if (!Array.isArray(rows)) throw new Error("Unexpected pending review list");
        if (active) setPendingTimeReviews(rows);
      })
      .catch(() => { if (active) setPendingTimeReviews(null); });
    return () => { active = false; };
  }, [canReviewTime, timeReviewOffset, reload]);

  function apply(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const search = draft.search.trim();
    if (search && (search.length < 2 || search.length > 80)) {
      setError("Search must contain 2 to 80 characters.");
      return;
    }
    const propertyId = Number(draft.property);
    if (draft.property && (!Number.isSafeInteger(propertyId) || propertyId <= 0)) {
      setError("Enter a valid positive property ID.");
      return;
    }
    setApplied({ ...draft, search });
    setOffset(0);
    setReload((value) => value + 1);
  }

  function clear() {
    setDraft(EMPTY);
    setApplied(EMPTY);
    setOffset(0);
    setReload((value) => value + 1);
  }

  function showAllEmergencies() {
    const filters: Filters = { ...EMPTY, priority: "emergency" };
    setDraft(filters);
    setApplied(filters);
    setOffset(0);
    setReload((value) => value + 1);
  }

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Work Orders</h1>
          <p className="mt-1 text-sm text-slate-600">
            Search work orders you are authorized to see. Crew see their assignments,
            tenants see their own requests, and managers see assigned properties.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          {canCreate && (
            <Link href="/dashboard/maintenance/work-orders/new"
              className="rounded-lg bg-slate-900 px-4 py-2 text-sm text-white">
              New maintenance request
            </Link>
          )}
          {canInspect && (
            <Link href="/dashboard/maintenance/staff-inspection-records"
              className="rounded-lg border bg-white px-4 py-2 text-sm">
              Staff inspection records
            </Link>
          )}
          {canReviewTime && <Link href="/dashboard/maintenance/dispatch-attention"
            className="rounded-lg border bg-white px-4 py-2 text-sm">Dispatch attention</Link>}
          {canViewOnCall && (
            <Link href="/dashboard/maintenance/on-call"
              className="rounded-lg border bg-white px-4 py-2 text-sm">
              On-call calendar
            </Link>
          )}
          {canInspect && (
            <Link href="/dashboard/maintenance/preventive"
              className="rounded-lg border bg-white px-4 py-2 text-sm">
              Preventive schedules
            </Link>
          )}
          <Link href="/dashboard" className="rounded-lg border bg-white px-4 py-2 text-sm">Dashboard</Link>
        </div>
      </header>
      <section aria-label="Accessible work-order summary" className="space-y-2">
        <h2 className="text-sm font-semibold text-slate-800">Across all work orders you can access</h2>
        {summary ? (
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            {[
              ["Open", summary.open],
              ["Emergency open", summary.emergency_open],
              ["Awaiting assignment", summary.awaiting_assignment],
              ["Pending crew decision", summary.pending_crew_response],
              ["Declined assignments", summary.declined_assignment],
              ["Recalled assignments", summary.recalled_assignment],
              ["In progress", summary.in_progress],
              ["Ready to close", summary.ready_to_close],
            ].map(([label, value]) => (
              <div key={label} className="rounded-xl border bg-white p-4">
                <p className="text-xs text-slate-600">{label}</p>
                <p className="mt-1 text-2xl font-semibold tabular-nums">{value}</p>
              </div>
            ))}
          </div>
        ) : <p className="rounded-xl border bg-white p-4 text-sm text-slate-500">Summary unavailable</p>}
      </section>
      <section aria-label="Emergency maintenance triage" className="rounded-xl border bg-white p-5">
        <h2 className="font-semibold text-slate-900">Emergency work requiring attention</h2>
        <p className="mt-1 text-xs text-slate-500">
          Up to 20 open emergency requests you are authorized to view. Unacknowledged requests appear first,
          then oldest first. This view does not automatically dispatch staff or replace emergency services.
        </p>
        <button type="button" onClick={showAllEmergencies}
          className="mt-2 rounded-lg border bg-white px-3 py-2 text-sm hover:bg-slate-50">
          Show all emergencies in work-order queue
        </button>
        {triageLoading ? (
          <p className="mt-3 text-sm text-slate-500">Loading visible emergency requests…</p>
        ) : triage === null ? (
          <p className="mt-3 text-sm text-slate-500">Emergency triage unavailable.</p>
        ) : triage.length === 0 ? (
          <p className="mt-3 text-sm text-slate-500">No visible open emergency requests.</p>
        ) : (
          <ul className="mt-3 divide-y">
            {triage.map((item) => (
              <li key={item.id} className="flex flex-wrap items-start justify-between gap-2 py-2 text-sm">
                <div>
                  <Link href={`/dashboard/maintenance/work-orders/${item.id}`}
                    className="font-medium text-blue-800 hover:underline">
                    #{item.id} · {item.title}
                  </Link>
                  <p className="text-xs text-slate-500">
                    {item.property_name || `Property #${item.property_id}`} · {item.unit_number ? `Unit ${item.unit_number}` : `Unit #${item.unit_id}`}
                  </p>
                </div>
                <span className="rounded-full bg-slate-100 px-3 py-1 text-xs">
                  {item.status.replaceAll("_", " ")}
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>
      {canReviewTime && (
        <section aria-label="Pending crew time correction reviews" className="rounded-xl border bg-white p-5">
          <h2 className="font-semibold text-slate-900">Crew time corrections awaiting review</h2>
          <p className="mt-1 text-xs text-slate-500">
            Review the original and proposed hours in the linked work order.
            The original evidence is never overwritten and this is not payroll approval.
          </p>
          {pendingTimeReviews === null ? <p className="mt-3 text-sm text-slate-500">Review queue unavailable or loading.</p>
            : pendingTimeReviews.length === 0 ? <p className="mt-3 text-sm text-slate-500">No corrections pending in this page.</p>
            : <ul className="mt-3 divide-y">
              {pendingTimeReviews.map((item) => <li key={item.id} className="py-3 text-sm">
                <Link href={`/dashboard/maintenance/work-orders/${item.work_order_id}`}
                  className="font-medium text-blue-800 hover:underline">
                  #{item.work_order_id} · {item.work_order_title}
                </Link>
                <p className="mt-1 text-slate-600">{item.property_name} · Original {item.original_minutes} min → Proposed {item.proposed_minutes} min</p>
                <p className="mt-1 whitespace-pre-wrap text-slate-700">{item.reason}</p>
              </li>)}
            </ul>}
          <div className="mt-3 flex justify-between gap-3">
            <button type="button" disabled={timeReviewOffset === 0} onClick={() => setTimeReviewOffset((n) => Math.max(0, n - 10))}
              className="rounded border px-3 py-2 text-sm disabled:opacity-40">Previous reviews</button>
            <button type="button" disabled={!pendingTimeReviews || pendingTimeReviews.length < 10}
              onClick={() => setTimeReviewOffset((n) => n + 10)}
              className="rounded border px-3 py-2 text-sm disabled:opacity-40">Next reviews</button>
          </div>
        </section>
      )}
      <form onSubmit={apply} className="rounded-xl border bg-white p-5">
        <div className="grid gap-3 md:grid-cols-3 xl:grid-cols-6">
          <label className="text-sm">Search title, description, property or unit
            <input className="input mt-1" aria-label="Search work orders" maxLength={80}
              placeholder="At least 2 characters" value={draft.search}
              onChange={(event) => setDraft({ ...draft, search: event.target.value })} />
          </label>
          <label className="text-sm">Status
            <select aria-label="Work order status" className="input mt-1" value={draft.status}
              onChange={(event) => setDraft({ ...draft, status: event.target.value })}>
              <option value="">All statuses</option>
              {STATUSES.map((value) => <option key={value} value={value}>{value.replaceAll("_", " ")}</option>)}
            </select>
          </label>
          <label className="text-sm">Priority
            <select aria-label="Work order priority" className="input mt-1" value={draft.priority}
              onChange={(event) => setDraft({ ...draft, priority: event.target.value })}>
              <option value="">All priorities</option>
              {PRIORITIES.map((value) => <option key={value} value={value}>{value}</option>)}
            </select>
          </label>
          <label className="text-sm">Crew assignment response
            <select aria-label="Crew assignment response" className="input mt-1"
              value={draft.assignment_response}
              onChange={(event) => setDraft({ ...draft, assignment_response: event.target.value })}>
              <option value="">All crew responses</option>
              <option value="pending">Awaiting acceptance</option>
              <option value="accepted">Accepted</option>
              <option value="rejected">Rejected</option>
              <option value="recalled">Recalled by staff</option>
              <option value="legacy">Historical without response</option>
            </select>
          </label>
          <label className="text-sm">Category
            <select aria-label="Work order category" className="input mt-1" value={draft.category}
              onChange={(event) => setDraft({ ...draft, category: event.target.value })}>
              <option value="">All categories</option>
              {CATEGORIES.map((value) => <option key={value} value={value}>{value}</option>)}
            </select>
          </label>
          <label className="text-sm">Property ID
            <input type="number" min="1" step="1" className="input mt-1" aria-label="Work order property ID"
              placeholder="All accessible" value={draft.property}
              onChange={(event) => setDraft({ ...draft, property: event.target.value })} />
          </label>
        </div>
        <div className="mt-4 flex flex-wrap gap-2">
          <button type="submit" className="rounded-lg bg-slate-900 px-4 py-2 text-sm text-white">Apply filters</button>
          <button type="button" onClick={clear} className="rounded-lg border px-4 py-2 text-sm">Clear</button>
        </div>
      </form>
      {error && <p role="alert" className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-800">{error}</p>}
      <section className="rounded-xl border bg-white">
        <div className="border-b px-5 py-4">
          <h2 className="font-semibold">Visible work orders</h2>
          <p className="text-xs text-slate-500">
            Page {Math.floor(offset / PAGE_SIZE) + 1}, up to {PAGE_SIZE} per page.
            Access scope is enforced by the server.
          </p>
        </div>
        {busy ? <p className="p-5 text-sm text-slate-500">Loading work orders…</p> :
          error ? <p className="p-5 text-sm text-slate-500">Work orders could not be loaded.</p> :
          rows.length === 0 ? <p className="p-5 text-sm text-slate-500">No work orders match these filters.</p> :
          <div className="divide-y">
            {rows.map((row) => (
              <article key={row.id} className="px-5 py-4">
                <div className="flex flex-wrap justify-between gap-3">
                  <div>
                    <h3 className="font-semibold"><Link className="text-blue-800 hover:underline" href={`/dashboard/maintenance/work-orders/${row.id}`}>#{row.id} · {row.title}</Link></h3>
                    <p className="mt-1 text-sm text-slate-600">
                      {row.property_name || `Property #${row.property_id}`} · {row.unit_number ? `Unit ${row.unit_number}` : `Unit #${row.unit_id}`} · {row.category.replaceAll("_", " ")}
                    </p>
                  </div>
                  <div className="flex flex-wrap items-start gap-2 text-xs">
                    <span className="rounded-full bg-slate-100 px-3 py-1">{row.status.replaceAll("_", " ")}</span>
                    {row.assignment_response === "pending" && <span>Awaiting crew acceptance</span>}
                    {row.assignment_response === "rejected" && <span>Rejected, needs reassignment</span>}
                    <span className="rounded-full bg-slate-100 px-3 py-1">{row.priority} priority</span>
                  </div>
                </div>
                <p className="mt-2 line-clamp-2 text-sm text-slate-700">{row.description}</p>
                <p className="mt-2 text-xs text-slate-500">Created {new Date(row.created_at).toLocaleDateString()}</p>
              </article>
            ))}
          </div>}
        <div className="flex justify-between border-t p-4">
          <button disabled={busy || offset === 0} onClick={() => setOffset((n) => Math.max(0, n - PAGE_SIZE))}
            className="rounded-lg border px-4 py-2 text-sm disabled:opacity-40">Previous</button>
          <button disabled={busy || rows.length < PAGE_SIZE} onClick={() => setOffset((n) => n + PAGE_SIZE)}
            className="rounded-lg border px-4 py-2 text-sm disabled:opacity-40">Next</button>
        </div>
      </section>
    </div>
  );
}
