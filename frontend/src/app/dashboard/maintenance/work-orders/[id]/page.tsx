"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { apiGet, apiPost } from "@/lib/api";

type WorkOrderUpdate = {
  id: number;
  user_id: number;
  from_status: string | null;
  to_status: string | null;
  message: string | null;
  created_at: string;
};
type WorkOrder = {
  id: number;
  property_id: number;
  unit_id: number;
  title: string;
  description: string;
  category: string;
  priority: string;
  status: string;
  permission_to_enter: boolean;
  entry_notes: string | null;
  assigned_to_id: number | null;
  resolution_notes: string | null;
  created_at: string;
  updated_at: string;
  updates: WorkOrderUpdate[];
};

export default function WorkOrderDetailPage() {
  const params = useParams<{ id: string }>();
  const orderId = Number(params.id);
  const [order, setOrder] = useState<WorkOrder | null>(null);
  const [viewer, setViewer] = useState<{ id: number; role: string } | null>(null);
  const [completionNotes, setCompletionNotes] = useState("");
  const [crew, setCrew] = useState<{ id: number; first_name: string; last_name: string; is_active: boolean }[]>([]);
  const [crewId, setCrewId] = useState("");
  const [comment, setComment] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

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
    if (!["ADMIN", "OWNER", "MANAGER"].includes(role)) {
      setCrew([]);
      return;
    }
    let active = true;
    apiGet("/users?role=crew")
      .then((rows: { id: number; first_name: string; last_name: string; is_active: boolean }[]) => {
        if (active) setCrew(Array.isArray(rows) ? rows.filter((row) => row.is_active) : []);
      }).catch(() => { if (active) setCrew([]); });
    return () => { active = false; };
  }, [viewer?.role]);

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
      await apiPost("/work-orders/" + order.id + "/assign", { crew_user_id: selected });
      await reload();
      setNotice("Crew assignment recorded. Property assignment is verified by the backend.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Crew assignment failed.");
    } finally {
      setSaving(false);
    }
  }

  async function advanceStatus(action: "acknowledge" | "start" | "complete" | "close") {
    if (!order || saving) return;
    setSaving(true);
    setError("");
    setNotice("");
    try {
      const data = action === "complete"
        ? { resolution_notes: completionNotes.trim() || null }
        : undefined;
      await apiPost("/work-orders/" + order.id + "/" + action, data);
      if (action === "complete") setCompletionNotes("");
      await reload();
      setNotice("Work order " + (action === "acknowledge" ? "acknowledged" :
        action === "start" ? "started" : action === "complete" ? "completed" : "closed") + ".");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to update the work order.");
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
      await apiPost("/work-orders/" + order.id + "/comments", { message });
      setComment("");
      await reload();
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
              <span className="rounded-full bg-slate-100 px-3 py-1">Property #{order.property_id} · Unit #{order.unit_id}</span>
            </div>
            <p className="mt-4 whitespace-pre-wrap text-sm text-slate-800">{order.description}</p>
            <p className="mt-4 text-xs text-slate-500">Submitted {new Date(order.created_at).toLocaleString()}</p>
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
                      <select aria-label="Assigned crew member" disabled={saving}
                        className="mt-1 block rounded-lg border p-2" value={crewId}
                        onChange={(event) => setCrewId(event.target.value)}>
                        <option value="">Select crew</option>
                        {crew.map((person) => <option key={person.id} value={person.id}>
                          {person.first_name} {person.last_name} (#{person.id})
                        </option>)}
                      </select>
                    </label>
                    <button disabled={saving || !crewId} onClick={() => void assignCrew()}
                      className="rounded-lg border bg-white px-4 py-2 text-sm disabled:opacity-50">
                      Assign crew
                    </button>
                  </>
                )}
              {viewer?.role?.toUpperCase() === "CREW" && order.assigned_to_id === viewer.id
                && order.status === "assigned" && (
                  <button disabled={saving} onClick={() => void advanceStatus("start")}
                    className="rounded-lg bg-slate-900 px-4 py-2 text-sm text-white disabled:opacity-50">Start work</button>
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
              {!(["ADMIN", "OWNER", "MANAGER"].includes(String(viewer?.role || "").toUpperCase())
                && (order.status === "submitted" || order.status === "completed"))
                && !(viewer?.role?.toUpperCase() === "CREW" && order.assigned_to_id === viewer.id
                  && ["assigned", "in_progress"].includes(order.status)) && (
                  <p className="text-sm text-slate-600">No status transition is available for this role.</p>
                )}
            </div>
          </section>
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
                      <span>Staff/resident user #{update.user_id}</span>
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
