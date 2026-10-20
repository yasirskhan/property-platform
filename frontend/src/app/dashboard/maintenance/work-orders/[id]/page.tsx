"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { apiGet, apiPost } from "@/lib/api";

type WorkOrderUpdate = {
  id: number;
  user_id: number;
  actor_name?: string | null;
  from_status: string | null;
  to_status: string | null;
  message: string | null;
  created_at: string;
};
type WorkOrder = {
  id: number;
  property_id: number;
  unit_id: number;
  property_name?: string | null;
  request_origin?: "staff" | "tenant" | "unknown_legacy";
  requested_by_user_id?: number | null;
  source_inspection_id?: number | null;
  unit_number?: string | null;
  title: string;
  description: string;
  category: string;
  priority: string;
  status: string;
  permission_to_enter: boolean;
  entry_notes: string | null;
  assigned_to_id: number | null;
  assignment_response?: "pending" | "accepted" | "rejected" | "recalled" | null;
  crew_eta_at?: string | null;
  resolution_notes: string | null;
  created_at: string;
  updated_at: string;
  updates: WorkOrderUpdate[];
};

type CrewTimeEntry = {
  id: number;
  started_at: string;
  ended_at: string;
  duration_minutes: number;
  notes?: string | null;
};

export default function WorkOrderDetailPage() {
  const params = useParams<{ id: string }>();
  const orderId = Number(params.id);
  const [order, setOrder] = useState<WorkOrder | null>(null);
  const [viewer, setViewer] = useState<{ id: number; role: string } | null>(null);
  const [completionNotes, setCompletionNotes] = useState("");
  const [etaDraft, setEtaDraft] = useState("");
  const [timeStart, setTimeStart] = useState("");
  const [timeEnd, setTimeEnd] = useState("");
  const [timeNotes, setTimeNotes] = useState("");
  const [timeEntries, setTimeEntries] = useState<CrewTimeEntry[] | null>(null);
  const [crew, setCrew] = useState<{ id: number; name: string }[]>([]);
  const [crewId, setCrewId] = useState("");
  const [crewLoading, setCrewLoading] = useState(false);
  const [crewError, setCrewError] = useState("");
  const [comment, setComment] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [rejectRequested, setRejectRequested] = useState(false);
  const [rejectReason, setRejectReason] = useState("");
  const [recallRequested, setRecallRequested] = useState(false);
  const [recallReason, setRecallReason] = useState("");
  const [cancelRequested, setCancelRequested] = useState(false);
  const [cancelReason, setCancelReason] = useState("");

  const reload = useCallback(async () => {
    if (!Number.isSafeInteger(orderId) || orderId <= 0) {
      setError("Enter a valid work order ID.");
      setOrder(null);
      setLoading(false);
      return;
    }
    setLoading(true);
    try {
      const result = await apiGet("/work-orders/" + orderId) as WorkOrder;
      if (result.id !== orderId || !Array.isArray(result.updates))
        throw new Error("Unexpected work order response.");
      setOrder(result);
      setError("");
    } catch (cause) {
      setOrder(null);
      setError(cause instanceof Error ? cause.message : "Unable to load the work order.");
    } finally {
      setLoading(false);
    }
  }, [orderId]);

  useEffect(() => { void reload(); }, [reload]);

  useEffect(() => {
    let active = true;
    apiGet("/auth/me").then((value: { id: number; role: string }) => {
      if (active) setViewer(value);
    }).catch(() => { if (active) setViewer(null); });
    return () => { active = false; };
  }, []);

  useEffect(() => {
    const role = String(viewer?.role || "").toUpperCase();
    const propertyId = order?.property_id;
    if (!["ADMIN", "OWNER", "MANAGER"].includes(role) || !propertyId) {
      setCrew([]);
      setCrewId("");
      setCrewError("");
      return;
    }
    // The property roster is the existing server-authorized source of crew
    // assigned to THIS property. Organization-wide /users included invalid choices.
    let active = true;
    setCrew([]);
    setCrewId("");
    setCrewLoading(true);
    setCrewError("");
    apiGet(`/properties/${propertyId}/assignments`)
      .then((rows: { user_id: number; name: string; role: string }[]) => {
        if (!Array.isArray(rows)) throw new Error("Unexpected property staff response.");
        if (active) setCrew(rows
          .filter((row) => row.role === "CREW" && Number.isSafeInteger(row.user_id) && row.user_id > 0)
          .map((row) => ({ id: row.user_id, name: row.name })));
      })
      .catch((cause) => {
        if (active) {
          setCrew([]);
          setCrewError(cause instanceof Error ? cause.message : "Property crew unavailable.");
        }
      })
      .finally(() => { if (active) setCrewLoading(false); });
    return () => { active = false; };
  }, [viewer?.role, order?.property_id]);

  useEffect(() => {
    if (!order || !viewer || !["ADMIN", "OWNER", "MANAGER", "CREW"].includes(String(viewer.role).toUpperCase())) {
      setTimeEntries(null);
      return;
    }
    let active = true;
    apiGet("/work-orders/" + order.id + "/time-entries")
      .then((result: CrewTimeEntry[]) => {
        if (active) setTimeEntries(Array.isArray(result) ? result : null);
      })
      .catch(() => { if (active) setTimeEntries(null); });
    return () => { active = false; };
  }, [order?.id, viewer?.id, viewer?.role]);

  async function assignCrew() {
    if (!order || saving) return;
    const selected = Number(crewId);
    if (!Number.isSafeInteger(selected) || selected < 1 || !crew.some((row) => row.id === selected)) {
      setError("Choose an available crew member.");
      return;
    }
    setSaving(true);
    setError("");
    setNotice("");
    try {
      const persisted = await apiPost("/work-orders/" + order.id + "/assign", { crew_user_id: selected }) as WorkOrder;
      if (!persisted || persisted.id !== order.id || persisted.assigned_to_id !== selected
          || persisted.status !== "assigned") {
        throw new Error("Unexpected crew assignment response.");
      }
      setOrder((previous) => previous ? {
        ...previous, status: persisted.status, assigned_to_id: persisted.assigned_to_id,
        assignment_response: persisted.assignment_response, updated_at: persisted.updated_at,
      } : previous);
      setCrewId("");
      setNotice("Crew assignment recorded. Property assignment is verified by the backend.");
      try {
        const fresh = await apiGet("/work-orders/" + order.id) as WorkOrder;
        if (fresh.id === order.id && Array.isArray(fresh.updates)) setOrder(fresh);
      } catch {
        // The assignment POST was already committed; never claim it failed.
      }
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Crew assignment failed.");
    } finally {
      setSaving(false);
    }
  }

  async function advanceStatus(action: "acknowledge" | "accept" | "reject" | "recall" | "start" | "complete" | "close" | "cancel") {
    if (!order || saving) return;
    setSaving(true);
    setError("");
    setNotice("");
    try {
      const data = action === "complete"
        ? { resolution_notes: completionNotes.trim() || null }
        : action === "cancel" ? { reason: cancelReason.trim() }
        : action === "recall" ? { reason: recallReason.trim() }
        : action === "reject" ? { reason: rejectReason.trim() } : undefined;
      const persisted = await apiPost("/work-orders/" + order.id + "/" + action, data) as WorkOrder;
      const expected = {
        acknowledge: "acknowledged",
        accept: "assigned",
        reject: "acknowledged",
        recall: "acknowledged",
        start: "in_progress",
        complete: "completed",
        close: "closed",
        cancel: "cancelled",
      }[action];
      if (!persisted || persisted.id !== order.id || persisted.status !== expected)
        throw new Error("Unexpected saved work order response.");
      // The successful POST is authoritative. A later GET outage cannot
      // reverse that status or incorrectly suggest the transition failed.
      setOrder((previous) => previous ? {
        ...previous, status: persisted.status,
        assigned_to_id: persisted.assigned_to_id,
        assignment_response: persisted.assignment_response,
        resolution_notes: persisted.resolution_notes,
        updated_at: persisted.updated_at,
      } : previous);
      if (action === "complete") setCompletionNotes("");
      if (action === "reject") { setRejectRequested(false); setRejectReason(""); }
      if (action === "recall") { setRecallRequested(false); setRecallReason(""); }
      if (action === "cancel") {
        setCancelRequested(false);
        setCancelReason("");
      }
      setNotice("Work order " + (action === "acknowledge" ? "acknowledged" :
        action === "accept" ? "assignment accepted" : action === "reject" ? "assignment rejected for reassignment" :
        action === "recall" ? "crew assignment recalled for reassignment" :
        action === "start" ? "started" : action === "complete" ? "completed" :
        action === "cancel" ? "cancelled" : "closed") + ".");
      // Fetch the authoritative activity log opportunistically, never as a
      // prerequisite for reporting that the status change was persisted.
      try {
        const fresh = await apiGet("/work-orders/" + order.id) as WorkOrder;
        if (fresh.id === order.id && Array.isArray(fresh.updates)) setOrder(fresh);
      } catch {
        // The latest known status and success notice remain visible.
      }
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to update the work order.");
    } finally {
      setSaving(false);
    }
  }

  async function saveArrivalEta() {
    if (!order || saving) return;
    const local = new Date(etaDraft);
    if (!etaDraft || Number.isNaN(local.getTime()) || local.getTime() <= Date.now()) {
      setError("Choose a future arrival date and time.");
      return;
    }
    setSaving(true);
    setError("");
    setNotice("");
    try {
      const updated = await apiPost("/work-orders/" + order.id + "/eta", {
        eta_at: local.toISOString(),
      }) as WorkOrder;
      if (!updated || updated.id !== order.id || !updated.crew_eta_at)
        throw new Error("Unexpected crew arrival ETA response.");
      setOrder((previous) => previous ? { ...previous, crew_eta_at: updated.crew_eta_at } : previous);
      setEtaDraft("");
      setNotice("Crew arrival ETA saved.");
      try {
        const fresh = await apiGet("/work-orders/" + order.id) as WorkOrder;
        if (fresh.id === order.id && Array.isArray(fresh.updates)) setOrder(fresh);
      } catch {
        // The successful ETA POST is authoritative even if activity reload fails.
      }
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to record arrival ETA.");
    } finally {
      setSaving(false);
    }
  }

  async function saveCrewTime() {
    if (!order || saving || !timeStart || !timeEnd) return;
    const start = new Date(timeStart), end = new Date(timeEnd);
    if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime()) || start >= end
        || end.getTime() > Date.now()) {
      setError("Choose a completed, valid start and end time.");
      return;
    }
    setSaving(true);
    setError("");
    setNotice("");
    try {
      const row = await apiPost("/work-orders/" + order.id + "/time-entries", {
        started_at: start.toISOString(), ended_at: end.toISOString(),
        notes: timeNotes.trim() || null,
      }) as CrewTimeEntry;
      if (!row || !Number.isSafeInteger(row.id) || row.duration_minutes < 1)
        throw new Error("Unexpected crew time response.");
      setTimeEntries((previous) => {
        if (previous === null) return [row];
        if (previous.some((item) => item.id === row.id)) return previous;
        return [...previous, row].sort((a, b) => a.started_at.localeCompare(b.started_at));
      });
      setTimeStart("");
      setTimeEnd("");
      setTimeNotes("");
      setNotice("Time entry saved.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to record crew time.");
    } finally {
      setSaving(false);
    }
  }

  async function submitComment(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!order || saving) return;
    const message = comment.trim();
    if (!message || message.length > 2000) {
      setError("Enter a comment between 1 and 2,000 characters.");
      return;
    }
    setSaving(true);
    setError("");
    setNotice("");
    try {
      const created = await apiPost("/work-orders/" + order.id + "/comments", { message }) as WorkOrderUpdate;
      if (!created || typeof created.id !== "number" || created.message !== message) {
        throw new Error("Unexpected saved activity response.");
      }
      // The POST response is authoritative; an unavailable detail-refresh GET
      // must not hide a successfully recorded audit/activity entry.
      setOrder((previous) => previous
        ? { ...previous, updates: [...previous.updates, created] }
        : previous);
      setComment("");
      setNotice("Comment recorded in the work order activity history.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to save the comment.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="space-y-5">
      <Link href="/dashboard/maintenance/work-orders"
        className="inline-flex rounded-lg border bg-white px-4 py-2 text-sm text-slate-800 hover:bg-slate-50">
        Back to work orders
      </Link>
      {error && <p role="alert" className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-800">{error}</p>}
      {notice && <p role="status" className="rounded-lg border border-slate-200 bg-white p-3 text-sm">{notice}</p>}
      {loading ? <p className="rounded-lg border bg-white p-5 text-sm text-slate-600">Loading work order…</p> : null}
      {order && !loading ? (
        <>
          <header className="rounded-xl border bg-white p-5">
            <h1 className="text-2xl font-semibold text-slate-900">Work order #{order.id}: {order.title}</h1>
            <div className="mt-3 flex flex-wrap gap-2 text-xs text-slate-700">
              <span className="rounded-full bg-slate-100 px-3 py-1">{order.status.replaceAll("_", " ")}</span>
              <span className="rounded-full bg-slate-100 px-3 py-1">{order.priority} priority</span>
              <span className="rounded-full bg-slate-100 px-3 py-1">{order.category}</span>
              <span className="rounded-full bg-slate-100 px-3 py-1">
                {order.property_name || `Property #${order.property_id}`} · {order.unit_number ? `Unit ${order.unit_number}` : `Unit #${order.unit_id}`}
              </span>
            </div>
            <p className="mt-4 whitespace-pre-wrap text-sm text-slate-800">{order.description}</p>
            {order.crew_eta_at && <p className="mt-2 text-sm font-semibold">Crew arrival estimate: {new Date(order.crew_eta_at + "Z").toLocaleString()}</p>}
            <p className="mt-4 text-xs text-slate-500">Submitted {new Date(order.created_at).toLocaleString()}</p>
            <p className="mt-2 text-xs text-slate-600">
              Request source: {order.request_origin === "staff" ? "Staff request" : order.request_origin === "tenant" ? "Tenant request" : "Historical source not verified"}
              {order.request_origin !== "unknown_legacy" && order.requested_by_user_id != null
                ? ` · Recorded requester #${order.requested_by_user_id}`
                : ""}
            </p>
            {order.source_inspection_id != null
              && ["ADMIN", "MANAGER"].includes(String(viewer?.role || "").toUpperCase())
              && <p className="mt-2 text-sm">
                Based on <Link className="text-blue-800 underline"
                  href={`/dashboard/maintenance/staff-inspection-records/${order.source_inspection_id}`}>
                  staff inspection #{order.source_inspection_id}
                </Link>
              </p>}
            {order.resolution_notes && (
              <div className="mt-4 rounded-lg bg-slate-50 p-3 text-sm">
                <strong>Resolution notes</strong>
                <p className="mt-1 whitespace-pre-wrap">{order.resolution_notes}</p>
              </div>
            )}
          </header>
          <section className="rounded-xl border bg-white p-5">
            <h2 className="font-semibold">Available next step</h2>
            <p className="mt-1 text-xs text-slate-500">
              Actions are role-specific. Every transition is validated again by the backend and recorded in work-order history.
            </p>
            <div className="mt-3 flex flex-wrap items-end gap-3">
              {["ADMIN", "OWNER", "MANAGER"].includes(String(viewer?.role || "").toUpperCase())
                && order.status === "submitted" && (
                  <button disabled={saving} onClick={() => void advanceStatus("acknowledge")}
                    className="rounded-lg bg-slate-900 px-4 py-2 text-sm text-white disabled:opacity-50">Acknowledge</button>
                )}
              {["ADMIN", "OWNER", "MANAGER"].includes(String(viewer?.role || "").toUpperCase())
                && ["acknowledged", "assigned"].includes(order.status) && (
                  <>
                    <label className="text-sm">Choose crew assigned to this property
                      <select aria-label="Assigned crew member" disabled={saving || crewLoading || Boolean(crewError)}
                        className="mt-1 block rounded-lg border p-2" value={crewId}
                        onChange={(event) => setCrewId(event.target.value)}>
                        <option value="">Select crew</option>
                        {crew.map((person) => <option key={person.id} value={person.id}>
                          {person.name} (#{person.id})
                        </option>)}
                      </select>
                    </label>
                    {crewError && <p role="alert" className="text-sm text-red-700">Crew roster unavailable: {crewError}</p>}
                    {!crewLoading && !crewError && crew.length === 0 &&
                      <p className="text-sm text-slate-600">No active crew are assigned to this property.</p>}
                    <button disabled={saving || crewLoading || Boolean(crewError) || !crewId} onClick={() => void assignCrew()}
                      className="rounded-lg border bg-white px-4 py-2 text-sm disabled:opacity-50">
                      Assign crew
                    </button>
                  </>
                )}
              {viewer?.role?.toUpperCase() === "CREW" && order.assigned_to_id === viewer.id
                && order.status === "assigned" && order.assignment_response === "pending" && (
                  <>
                    <p className="text-sm">Assignment offered. Accept before starting or reject with a reason.</p>
                    <button disabled={saving} onClick={() => void advanceStatus("accept")}
                      className="rounded-lg bg-slate-900 px-4 py-2 text-sm text-white disabled:opacity-50">
                      Accept assignment
                    </button>
                    {!rejectRequested ? (
                      <button disabled={saving} onClick={() => setRejectRequested(true)}
                        className="rounded-lg border px-4 py-2 text-sm disabled:opacity-50">
                        Reject assignment
                      </button>
                    ) : (
                      <div className="w-full space-y-2 rounded-lg border p-3">
                        <label className="block text-sm">Reason for rejecting this assignment
                          <textarea aria-label="Crew rejection reason" required minLength={5} maxLength={1000}
                            rows={2} value={rejectReason} disabled={saving}
                            onChange={(event) => setRejectReason(event.target.value)}
                            className="mt-1 block w-full rounded-lg border p-2" />
                        </label>
                        <button disabled={saving || rejectReason.trim().length < 5}
                          onClick={() => void advanceStatus("reject")}
                          className="rounded-lg border px-3 py-2 text-sm disabled:opacity-50">
                          Confirm assignment rejection
                        </button>
                        <button disabled={saving} onClick={() => { setRejectRequested(false); setRejectReason(""); }}
                          className="ml-2 rounded-lg border px-3 py-2 text-sm">Keep assignment offer</button>
                      </div>
                    )}
                  </>
                )}
              {order.status === "assigned" && order.assignment_response === "pending"
                && ["ADMIN", "OWNER", "MANAGER"].includes(String(viewer?.role || "").toUpperCase())
                && <p className="text-sm">Awaiting crew acceptance. Reassignment is available before work starts.</p>}
              {order.status === "assigned" && ["ADMIN", "OWNER", "MANAGER"].includes(String(viewer?.role || "").toUpperCase())
                && (
                  recallRequested ? (
                    <div className="w-full space-y-2 rounded-lg border p-3">
                      <p className="text-sm">Recall the unstarted crew assignment; the work order stays open for reassignment.</p>
                      <label className="block text-sm">Reason for recalling assignment
                        <textarea aria-label="Reason for recalling assignment" required minLength={5} maxLength={1000}
                          value={recallReason} disabled={saving} rows={2}
                          onChange={(event) => setRecallReason(event.target.value)}
                          className="mt-1 block w-full rounded-lg border p-2" />
                      </label>
                      <button disabled={saving || recallReason.trim().length < 5}
                        onClick={() => void advanceStatus("recall")}
                        className="rounded-lg border px-3 py-2 text-sm disabled:opacity-50">
                        Confirm assignment recall
                      </button>
                      <button disabled={saving} onClick={() => { setRecallRequested(false); setRecallReason(""); }}
                        className="ml-2 rounded-lg border px-3 py-2 text-sm">Keep crew assignment</button>
                    </div>
                  ) : (
                    <button disabled={saving} onClick={() => setRecallRequested(true)}
                      className="rounded-lg border px-4 py-2 text-sm disabled:opacity-50">
                      Recall assignment
                    </button>
                  )
                )}
              {viewer?.role?.toUpperCase() === "CREW" && order.assigned_to_id === viewer.id
                && order.status === "assigned" && order.assignment_response !== "pending" && (
                  <button disabled={saving} onClick={() => void advanceStatus("start")}
                    className="rounded-lg bg-slate-900 px-4 py-2 text-sm text-white disabled:opacity-50">Start work</button>
                )}
              {viewer?.role?.toUpperCase() === "CREW" && order.assigned_to_id === viewer.id
                && order.status === "assigned" && order.assignment_response === "accepted" && (
                  <div className="w-full space-y-2 rounded-lg border p-3">
                    <label className="block text-sm">Crew arrival ETA
                      <input type="datetime-local" aria-label="Crew arrival ETA" value={etaDraft}
                        onChange={(event) => setEtaDraft(event.target.value)}
                        disabled={saving} className="mt-1 block rounded-lg border p-2" />
                    </label>
                    <button disabled={saving || !etaDraft} onClick={() => void saveArrivalEta()}
                      className="rounded-lg border px-3 py-2 text-sm disabled:opacity-50">
                      Save arrival ETA
                    </button>
                  </div>
                )}
              {viewer?.role?.toUpperCase() === "CREW" && order.assigned_to_id === viewer.id
                && order.status === "in_progress" && (
                  <>
                    <label className="text-sm">Resolution notes (optional)
                      <textarea rows={2} maxLength={2000} value={completionNotes}
                        disabled={saving} onChange={(event) => setCompletionNotes(event.target.value)}
                        className="mt-1 w-full rounded-lg border p-2" />
                    </label>
                    <button disabled={saving} onClick={() => void advanceStatus("complete")}
                      className="rounded-lg bg-slate-900 px-4 py-2 text-sm text-white disabled:opacity-50">Mark completed</button>
                  </>
                )}
              {["ADMIN", "OWNER", "MANAGER"].includes(String(viewer?.role || "").toUpperCase())
                && order.status === "completed" && (
                  <button disabled={saving} onClick={() => void advanceStatus("close")}
                    className="rounded-lg bg-slate-900 px-4 py-2 text-sm text-white disabled:opacity-50">Approve and close</button>
                )}
              {["ADMIN", "OWNER", "MANAGER"].includes(String(viewer?.role || "").toUpperCase())
                && !["closed", "cancelled"].includes(order.status) && (
                  cancelRequested ? (
                    <div className="rounded-lg border border-amber-300 bg-amber-50 p-3 text-sm">
                      <p>Cancel this work order? The cancellation and its reason will be recorded in its audit history.</p>
                      <label className="mt-2 block">Reason for cancellation (required)
                        <textarea aria-label="Cancellation reason" maxLength={1000} rows={2}
                          value={cancelReason} disabled={saving}
                          onChange={(event) => setCancelReason(event.target.value)}
                          className="mt-1 block w-full rounded-lg border p-2"
                          placeholder="Explain why this work order must be cancelled" />
                      </label>
                      <div className="mt-2 flex gap-2">
                        <button disabled={saving || cancelReason.trim().length < 5} onClick={() => void advanceStatus("cancel")}
                          className="rounded-lg bg-slate-900 px-3 py-2 text-white disabled:opacity-50">
                          Confirm cancellation
                        </button>
                        <button disabled={saving} onClick={() => { setCancelRequested(false); setCancelReason(""); }}
                          className="rounded-lg border bg-white px-3 py-2 disabled:opacity-50">
                          Keep work order
                        </button>
                      </div>
                    </div>
                  ) : (
                    <button disabled={saving} onClick={() => setCancelRequested(true)}
                      className="rounded-lg border border-red-300 bg-white px-3 py-2 text-sm text-red-800 disabled:opacity-50">
                      Cancel work order
                    </button>
                  )
                )}
              {!(["ADMIN", "OWNER", "MANAGER"].includes(String(viewer?.role || "").toUpperCase())
                && (order.status === "submitted" || order.status === "completed"))
                && !(viewer?.role?.toUpperCase() === "CREW" && order.assigned_to_id === viewer.id
                  && ["assigned", "in_progress"].includes(order.status)) && (
                  <p className="text-sm text-slate-600">No status transition is available for this role.</p>
                )}
            </div>
          </section>
          {viewer && ["ADMIN", "OWNER", "MANAGER", "CREW"].includes(String(viewer.role).toUpperCase()) && (
            <section aria-label="Crew time records" className="rounded-xl border bg-white p-5">
              <h2 className="font-semibold">Crew time tracking</h2>
              <p className="mt-1 text-xs text-slate-500">Hours are historical evidence only, not approved payroll or tenant charges.</p>
              {timeEntries === null ? <p className="mt-2 text-sm text-slate-500">Crew hours unavailable.</p>
                : timeEntries.length === 0 ? <p className="mt-2 text-sm text-slate-500">No time entries recorded.</p>
                : <ul className="mt-3 space-y-2">
                    {timeEntries.map((entry) => <li key={entry.id} className="rounded-lg border p-3 text-sm">
                      {new Date(entry.started_at + "Z").toLocaleString()} to {new Date(entry.ended_at + "Z").toLocaleString()}
                      · {entry.duration_minutes} minutes
                      {entry.notes && <p className="mt-1 whitespace-pre-wrap">{entry.notes}</p>}
                    </li>)}
                  </ul>}
              {viewer.role?.toUpperCase() === "CREW" && order.assigned_to_id === viewer.id
                && order.status === "in_progress" && (
                  <div className="mt-4 grid gap-3 md:grid-cols-2">
                    <label className="text-sm">Work start time
                      <input type="datetime-local" aria-label="Work start time" value={timeStart}
                        onChange={(event) => setTimeStart(event.target.value)}
                        disabled={saving} className="mt-1 block w-full rounded-lg border p-2" />
                    </label>
                    <label className="text-sm">Work end time
                      <input type="datetime-local" aria-label="Work end time" value={timeEnd}
                        onChange={(event) => setTimeEnd(event.target.value)}
                        disabled={saving} className="mt-1 block w-full rounded-lg border p-2" />
                    </label>
                    <label className="text-sm md:col-span-2">Work description (optional)
                      <textarea aria-label="Time entry notes" value={timeNotes} maxLength={500}
                        rows={2} disabled={saving} onChange={(event) => setTimeNotes(event.target.value)}
                        className="mt-1 block w-full rounded-lg border p-2" />
                    </label>
                    <button type="button" disabled={saving || !timeStart || !timeEnd}
                      onClick={() => void saveCrewTime()}
                      className="rounded-lg bg-slate-900 px-4 py-2 text-sm text-white disabled:opacity-50">
                      Save work time
                    </button>
                  </div>
                )}
            </section>
          )}
          <section className="rounded-xl border bg-white p-5">
            <h2 className="font-semibold">Recorded activity</h2>
            <p className="mt-1 text-xs text-slate-500">Only activity for this authorized work order is shown.</p>
            {order.updates.length === 0 ? (
              <p className="mt-4 text-sm text-slate-600">No recorded activity yet.</p>
            ) : (
              <ol className="mt-4 space-y-3">
                {order.updates.map((update) => (
                  <li key={update.id} className="rounded-lg border p-3">
                    <div className="flex flex-wrap justify-between gap-2 text-xs text-slate-500">
                      <span>{update.actor_name || `Staff/resident user #${update.user_id}`}</span>
                      <time>{new Date(update.created_at).toLocaleString()}</time>
                    </div>
                    {(update.from_status || update.to_status) && (
                      <p className="mt-1 text-xs text-slate-600">
                        {update.from_status?.replaceAll("_", " ") || "New"} → {update.to_status?.replaceAll("_", " ") || "Unchanged"}
                      </p>
                    )}
                    {update.message && <p className="mt-2 whitespace-pre-wrap text-sm text-slate-800">{update.message}</p>}
                  </li>
                ))}
              </ol>
            )}
          </section>
          <form onSubmit={(event) => void submitComment(event)} className="rounded-xl border bg-white p-5">
            <h2 className="font-semibold">Add an activity note</h2>
            <p className="mt-1 text-xs text-slate-500">The backend checks your access to this work order before recording the note.</p>
            <textarea aria-label="Work order activity note" required maxLength={2000}
              disabled={saving || loading} value={comment} rows={3}
              className="mt-3 w-full rounded-lg border p-3 text-sm"
              placeholder="Record an update for this work order"
              onChange={(event) => setComment(event.target.value)} />
            <button type="submit" disabled={saving || !comment.trim()} className="mt-3 rounded-lg bg-slate-900 px-4 py-2 text-sm text-white disabled:opacity-50">
              {saving ? "Saving…" : "Save activity note"}
            </button>
          </form>
        </>
      ) : null}
    </div>
  );
}
