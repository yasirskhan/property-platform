"use client";

import { useEffect, useRef, useState } from "react";
import { apiGet, apiPost } from "@/lib/api";

type Task = {
  id: number; case_id: number; kind: string; title: string;
  details: string | null; assigned_user_id: number; due_on: string;
  status: "OPEN" | "IN_PROGRESS" | "DONE" | "CANCELLED";
  version: number; completed_at: string | null; result_note: string | null;
  internal_only: true; notice_issued: false; fine_assessed: false;
};
type Staff = { id: number; name: string; role: "ADMIN" | "OWNER" | "MANAGER" };
type Viewer = { id: number; role: string };

export default function HoaCaseTasksPanel({
  associationId, propertyId, caseId, stage, canEdit, onClose,
}: {
  associationId: number; propertyId: number; caseId: number;
  stage: string; canEdit: boolean; onClose: () => void;
}) {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [assignees, setAssignees] = useState<Staff[]>([]);
  const [viewer, setViewer] = useState<Viewer | null>(null);
  const [title, setTitle] = useState("");
  const [details, setDetails] = useState("");
  const [kind, setKind] = useState("INSPECTION");
  const [assigneeId, setAssigneeId] = useState("");
  const [dueOn, setDueOn] = useState("");
  const [finishing, setFinishing] = useState<number | null>(null);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const requestKey = useRef("");
  const base = "/api/hoa/associations/" + associationId +
    "/staff-cases/" + caseId;
  const query = "?property_id=" + propertyId;

  async function reload() {
    const rows = await apiGet(base + "/tasks" + query) as Task[];
    setTasks(rows);
  }

  useEffect(() => {
    let live = true;
    void Promise.all([
      apiGet(base + "/tasks" + query) as Promise<Task[]>,
      apiGet(base + "/task-assignees" + query) as Promise<Staff[]>,
      apiGet("/auth/me") as Promise<Viewer>,
    ]).then(([rows, staff, me]) => {
      if (!live) return;
      setTasks(rows); setAssignees(staff); setViewer(me);
    }).catch((cause) => {
      if (live) setError(cause instanceof Error ? cause.message : "Case follow-ups unavailable.");
    });
    return () => { live = false; };
  }, [base, query]);

  function changed(clear: () => void) {
    requestKey.current = "";
    clear();
  }

  async function add(event: React.FormEvent) {
    event.preventDefault();
    if (!canEdit || busy || !assigneeId || !title.trim() || !dueOn) return;
    setBusy(true); setError(""); setMessage("");
    if (!requestKey.current) requestKey.current = crypto.randomUUID();
    try {
      await apiPost(base + "/tasks", {
        property_id: propertyId, request_key: requestKey.current,
        title: title.trim(), details: details.trim() || null,
        kind, assigned_user_id: Number(assigneeId), due_on: dueOn,
      });
      requestKey.current = "";
      setTitle(""); setDetails(""); setDueOn(""); setAssigneeId("");
      await reload();
      setMessage("Assigned an internal follow-up. No notice or fine was issued.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to create staff follow-up.");
    } finally { setBusy(false); }
  }

  async function transition(task: Task, nextStatus: "IN_PROGRESS" | "DONE" | "CANCELLED") {
    const assignedManager = viewer?.role === "MANAGER" && viewer.id === task.assigned_user_id;
    if ((!canEdit && !assignedManager) || (nextStatus === "CANCELLED" && !canEdit) || busy) return;
    if (nextStatus === "DONE" && !note.trim()) {
      setError("Record the completion note.");
      return;
    }
    setBusy(true); setError(""); setMessage("");
    try {
      await apiPost(base + "/tasks/" + task.id + "/transition", {
        property_id: propertyId, expected_version: task.version,
        next_status: nextStatus, action_note: nextStatus === "DONE" ? note.trim() : null,
      });
      setFinishing(null); setNote("");
      await reload();
      setMessage("Internal follow-up updated. No legal notice or financial posting.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to change follow-up status.");
      await reload().catch(() => {});
    } finally { setBusy(false); }
  }

  const editable = canEdit && !["RESOLVED", "CLOSED"].includes(stage);
  const closable = stage !== "CLOSED";

  return (
    <section className="space-y-3 rounded border border-blue-200 bg-blue-50 p-3 text-sm">
      <div className="flex justify-between gap-2">
        <h4 className="font-semibold">Case follow-ups · #{caseId}</h4>
        <button type="button" className="text-blue-700" onClick={onClose}>Close follow-ups</button>
      </div>
      <p className="text-xs text-slate-700">
        Internal inspection or remediation tasks assigned to verified staff.
        A task is not an issued legal notice, a legal finding, a fee, or a work order.
        All open tasks must be completed or cancelled before closing this case.
      </p>
      {error && <p role="alert" className="text-xs text-red-700">{error}</p>}
      {message && <p role="status" className="text-xs text-green-700">{message}</p>}
      {tasks.length === 0 && <p className="text-xs">No internal follow-ups.</p>}
      <ol className="space-y-2">
        {tasks.map((task) => (
          <li key={task.id} className="space-y-1 rounded border bg-white p-2 text-xs">
            <p className="font-semibold">{task.kind} · {task.title} · {task.status.replaceAll("_", " ")}</p>
            <p>Assigned: {assignees.find((x) => x.id === task.assigned_user_id)?.name || "User #" + task.assigned_user_id}
              {" · "}Due: {task.due_on} · Revision {task.version}</p>
            {task.details && <p className="whitespace-pre-wrap">{task.details}</p>}
            {task.result_note && <p className="whitespace-pre-wrap">Result: {task.result_note}</p>}
            {closable && (canEdit || (viewer?.role === "MANAGER" && viewer.id === task.assigned_user_id)) && task.status === "OPEN" && (
              <div className="flex flex-wrap gap-2">
                <button type="button" disabled={busy}
                  onClick={() => { void transition(task, "IN_PROGRESS"); }}
                  className="text-blue-700 disabled:opacity-50">Start follow-up</button>
                {canEdit && <button type="button" disabled={busy}
                  onClick={() => { void transition(task, "CANCELLED"); }}
                  className="text-red-700 disabled:opacity-50">Cancel follow-up</button>}
              </div>
            )}
            {closable && (canEdit || (viewer?.role === "MANAGER" && viewer.id === task.assigned_user_id)) && task.status === "IN_PROGRESS" && (
              <div className="space-y-1">
                <button type="button" disabled={busy}
                  onClick={() => setFinishing((id) => id === task.id ? null : task.id)}
                  className="text-blue-700 disabled:opacity-50">Complete follow-up</button>
                {canEdit && <button type="button" disabled={busy}
                  onClick={() => { void transition(task, "CANCELLED"); }}
                  className="ml-3 text-red-700 disabled:opacity-50">Cancel follow-up</button>}
                {finishing === task.id && (
                  <div className="space-y-1">
                    <label className="block">Completion note
                      <textarea required maxLength={600} value={note}
                        onChange={(event) => setNote(event.target.value)}
                        className="mt-1 block w-full rounded border p-2" />
                    </label>
                    <button type="button" disabled={busy || !note.trim()}
                      onClick={() => { void transition(task, "DONE"); }}
                      className="rounded bg-slate-900 px-3 py-1 text-white disabled:opacity-50">
                      Save completion
                    </button>
                  </div>
                )}
              </div>
            )}
          </li>
        ))}
      </ol>

      {editable && (
        <form onSubmit={(event) => { void add(event); }} className="space-y-2 border-t pt-3">
          <p className="font-medium">Assign internal follow-up</p>
          <label className="block text-xs">Task title
            <input required maxLength={160} minLength={3} value={title}
              onChange={(event) => changed(() => setTitle(event.target.value))}
              className="mt-1 block w-full rounded border p-2" />
          </label>
          <label className="block text-xs">Task type
            <select value={kind} onChange={(event) => changed(() => setKind(event.target.value))}
              className="mt-1 block rounded border p-2">
              <option value="INSPECTION">Internal inspection</option>
              <option value="REMEDIATION">Remediation follow-up</option>
              <option value="REVIEW">Staff review</option>
              <option value="OTHER">Other internal task</option>
            </select>
          </label>
          <label className="block text-xs">Assigned staff
            <select required aria-label="Assigned staff" value={assigneeId}
              onChange={(event) => changed(() => setAssigneeId(event.target.value))}
              className="mt-1 block w-full rounded border p-2">
              <option value="">Choose verified staff</option>
              {assignees.map((staff) => (
                <option key={staff.id} value={staff.id}>{staff.name} · {staff.role}</option>
              ))}
            </select>
          </label>
          <label className="block text-xs">Internal target date
            <input required type="date" value={dueOn}
              onChange={(event) => changed(() => setDueOn(event.target.value))}
              className="mt-1 block rounded border p-2" />
          </label>
          <label className="block text-xs">Private details (optional)
            <textarea maxLength={1500} value={details}
              onChange={(event) => changed(() => setDetails(event.target.value))}
              className="mt-1 block w-full rounded border p-2" />
          </label>
          <button type="submit" disabled={busy || !title.trim() || !assigneeId || !dueOn}
            className="rounded bg-slate-900 px-3 py-2 text-white disabled:opacity-50">
            Assign follow-up
          </button>
        </form>
      )}
    </section>
  );
}
