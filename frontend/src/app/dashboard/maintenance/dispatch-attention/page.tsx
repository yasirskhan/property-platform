"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { apiGet } from "@/lib/api";

type Attention = {
  work_order_id: number; property_id: number; property_name: string; title: string;
  priority: string; status: string; attention_code: string; explanation: string;
  next_action: string; assigned_to_id: number | null; assignment_response: string | null;
  response_due_at: string | null; policy_group: string | null; policy_daypart: string | null;
  policy_configured: boolean; primary_target: string | null; backup_target: string | null;
};

const PAGE = 50;

export default function MaintenanceDispatchAttentionPage() {
  const [rows, setRows] = useState<Attention[] | null>(null);
  const [role, setRole] = useState("");
  const [error, setError] = useState("");
  const [offset, setOffset] = useState(0);
  const [revision, setRevision] = useState(0);

  useEffect(() => {
    let active = true;
    apiGet("/auth/me").then((person: { role: string }) => {
      if (!active) return;
      const authorizedRole = String(person.role).toUpperCase();
      setRole(authorizedRole);
      if (!["ADMIN", "OWNER", "MANAGER"].includes(authorizedRole)) {
        setError("Only authorized maintenance staff may review dispatch attention.");
      }
    }).catch(() => { if (active) setError("Sign in to review maintenance dispatch attention."); });
    return () => { active = false; };
  }, []);

  useEffect(() => {
    if (!["ADMIN", "OWNER", "MANAGER"].includes(role)) return;
    let active = true;
    setRows(null); setError("");
    apiGet("/api/maintenance/dispatch-attention?limit=" + PAGE + "&offset=" + offset)
      .then((result: Attention[]) => {
        if (!Array.isArray(result) || result.some((item) => !Number.isSafeInteger(item.work_order_id))) {
          throw new Error("Unexpected dispatch-attention response.");
        }
        if (active) setRows(result);
      })
      .catch((cause) => { if (active) setError(cause instanceof Error ? cause.message : "Unable to read dispatch attention."); })
      .finally(() => { if (active) setRows((current) => current ?? []); });
    return () => { active = false; };
  }, [role, offset, revision]);

  return <div className="space-y-5">
    <header className="flex flex-wrap items-start justify-between gap-3">
      <div>
        <h1 className="text-2xl font-bold">Maintenance dispatch attention</h1>
        <p className="mt-1 text-sm text-slate-600">
          Review unacknowledged requests, unassigned jobs, rejected offers and overdue crew responses.
          This is a read-only staff inbox. A timeout does not recall an assignment, send messages or approve spending.
        </p>
      </div>
      <div className="flex flex-wrap gap-2">
        <Link href="/dashboard/maintenance/work-orders" className="rounded-lg border px-3 py-2 text-sm">Work orders</Link>
        <Link href="/dashboard/maintenance/on-call" className="rounded-lg border px-3 py-2 text-sm">On-call calendar</Link>
        <Link href="/dashboard/maintenance/dispatch-reviews" className="rounded-lg border px-3 py-2 text-sm">Manual reviews</Link>
        {["ADMIN", "OWNER"].includes(role) && <Link href="/dashboard/maintenance/dispatch-settings"
          className="rounded-lg border px-3 py-2 text-sm">Dispatch settings</Link>}
      </div>
    </header>
    {error && <p role="alert" className="rounded-lg border border-red-300 p-3 text-sm text-red-800">{error}</p>}
    {["ADMIN", "OWNER", "MANAGER"].includes(role) && <>
      <div className="flex items-center justify-between">
        <p className="text-sm text-slate-600">Current, authorized property scope. Emergencies first; oldest requests first within priority.</p>
        <button type="button" className="rounded-lg border px-3 py-2 text-sm"
          onClick={() => setRevision((n) => n + 1)}>Refresh attention</button>
      </div>
      {rows === null ? <p className="text-sm">Loading dispatch attention...</p>
        : rows.length === 0 ? <p className="rounded-lg border p-4 text-sm">No open dispatch-attention items on this page.</p>
        : <section aria-label="Dispatch attention items" className="space-y-3">
          {rows.map((item) => <article key={item.work_order_id} className="rounded-xl border bg-white p-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h2 className="font-semibold">
                <Link className="text-blue-800 hover:underline" href={"/dashboard/maintenance/work-orders/" + item.work_order_id}>
                  #{item.work_order_id} · {item.title}
                </Link>
              </h2>
              <p className="text-xs font-semibold uppercase text-slate-700">{item.priority} · {item.attention_code.replaceAll("_", " ")}</p>
            </div>
            <p className="mt-1 text-sm">{item.property_name} · {item.status}</p>
            <p className="mt-2 text-sm">{item.explanation}</p>
            <p className="mt-1 text-sm font-medium">{item.next_action}</p>
            {item.response_due_at && <p className="mt-1 text-xs">Configured crew response window ended:
              {" " + new Date(item.response_due_at).toLocaleString()}</p>}
            <p className="mt-2 text-xs text-slate-600">
              Effective group: {item.policy_group ?? "Not configured"}
              {item.policy_daypart ? " · " + item.policy_daypart.replaceAll("_", " ") : ""}
              {item.policy_configured
                ? " · Primary: " + item.primary_target + " · Backup: " + item.backup_target
                : " · No active policy for this urgency/time"}
            </p>
          </article>)}
        </section>}
      <nav aria-label="Dispatch attention pagination" className="flex items-center gap-3">
        <button type="button" className="rounded border px-3 py-2 text-sm disabled:opacity-40"
          disabled={offset === 0 || rows === null} onClick={() => setOffset((n) => Math.max(0, n - PAGE))}>Previous</button>
        <span className="text-sm">Page {1 + offset / PAGE}</span>
        <button type="button" className="rounded border px-3 py-2 text-sm disabled:opacity-40"
          disabled={rows === null || rows.length < PAGE || offset >= 9950}
          onClick={() => setOffset((n) => n + PAGE)}>Next</button>
      </nav>
    </>}
  </div>;
}
