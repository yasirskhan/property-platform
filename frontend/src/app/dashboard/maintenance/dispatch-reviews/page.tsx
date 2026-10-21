"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { apiGet, apiPost } from "@/lib/api";

type Attention = {
  work_order_id: number; title: string; property_name: string;
  priority: string; attention_code: string;
};
type DispatchReview = {
  id: number; work_order_id: number; status: "open" | "closed";
  reason: string; resolution_note: string | null;
  opened_by_user_id: number; closed_by_user_id: number | null;
  created_at: string; closed_at: string | null; externally_notified: boolean;
};
const PAGE_SIZE = 50;

export default function DispatchManualReviewsPage() {
  const [role, setRole] = useState("");
  const [items, setItems] = useState<Attention[]>([]);
  const [reviews, setReviews] = useState<DispatchReview[] | null>(null);
  const [selectedOrder, setSelectedOrder] = useState("");
  const [reason, setReason] = useState("");
  const [resolutions, setResolutions] = useState<Record<number, string>>({});
  const [showClosed, setShowClosed] = useState(false);
  const [offset, setOffset] = useState(0);
  const [revision, setRevision] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const refresh = useCallback(async () => {
    const [cases, attention] = await Promise.all([
      apiGet("/api/maintenance/dispatch-reviews?include_closed=" + (showClosed ? "true" : "false")
        + "&limit=" + PAGE_SIZE + "&offset=" + offset) as Promise<DispatchReview[]>,
      apiGet("/api/maintenance/dispatch-attention?limit=100") as Promise<Attention[]>,
    ]);
    if (!Array.isArray(cases) || !Array.isArray(attention)
        || cases.some((item) => !Number.isSafeInteger(item.id) || !Number.isSafeInteger(item.work_order_id))) {
      throw new Error("Unexpected dispatch review response");
    }
    setReviews(cases);
    setItems(attention);
  }, [offset, showClosed]);

  useEffect(() => {
    let active = true;
    apiGet("/auth/me").then((person: {role: string}) => {
      if (active) setRole(String(person.role).toUpperCase());
    }).catch(() => { if (active) setRole("DENIED"); });
    return () => { active = false; };
  }, []);

  useEffect(() => {
    if (!["ADMIN", "OWNER", "MANAGER"].includes(role)) return;
    let active = true;
    setError("");
    setReviews(null);
    refresh().catch((cause) => {
      if (active) setError(cause instanceof Error ? cause.message : "Cannot load dispatch review history");
    });
    return () => { active = false; };
  }, [role, refresh, revision]);

  async function openReview() {
    if (busy || !selectedOrder || reason.trim().length < 12) return;
    setBusy(true); setError(""); setNotice("");
    try {
      const saved = await apiPost(
        "/api/maintenance/dispatch-reviews/work-orders/" + selectedOrder,
        {reason: reason.trim()},
      ) as DispatchReview;
      if (!saved.id || saved.status !== "open" || saved.externally_notified) {
        throw new Error("Dispatch review was not recorded safely");
      }
      setReason(""); setSelectedOrder("");
      setOffset(0); setShowClosed(false); setRevision((n) => n + 1);
      setNotice("Manual review recorded. No crew, vendor, or manager was automatically contacted.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not record review");
    } finally { setBusy(false); }
  }

  async function closeReview(id: number) {
    const resolution = resolutions[id]?.trim() ?? "";
    if (busy || resolution.length < 12) return;
    setBusy(true); setError(""); setNotice("");
    try {
      const saved = await apiPost("/api/maintenance/dispatch-reviews/" + id + "/close",
        {resolution_note: resolution}) as DispatchReview;
      if (saved.id !== id || saved.status !== "closed" || saved.externally_notified) {
        throw new Error("Dispatch review close response was invalid");
      }
      setResolutions((current) => ({...current, [id]: ""}));
      setNotice("Review closure and reason were recorded in immutable audit history.");
      setRevision((n) => n + 1);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not close review");
    } finally { setBusy(false); }
  }

  if (role && !["ADMIN", "OWNER", "MANAGER"].includes(role)) {
    return <p role="alert" className="rounded-lg border p-4">Only authorized maintenance staff may review dispatch.</p>;
  }
  const openOrders = items.filter((item) =>
    !reviews?.some((record) => record.status === "open" && record.work_order_id === item.work_order_id));

  return <main className="space-y-5">
    <header className="flex flex-wrap items-start justify-between gap-3">
      <div>
        <h1 className="text-2xl font-bold">Manual dispatch reviews</h1>
        <p className="mt-1 text-sm text-slate-600">
          Record and resolve operator follow-up with an audit trail. These are internal case records,
          not SMS, email, phone calls, dispatch acknowledgements or financial approvals.
        </p>
      </div>
      <div className="flex gap-2">
        <Link href="/dashboard/maintenance/dispatch-attention" className="rounded border px-3 py-2 text-sm">Attention inbox</Link>
        <Link href="/dashboard/maintenance/work-orders" className="rounded border px-3 py-2 text-sm">Work orders</Link>
      </div>
    </header>
    {error && <p role="alert" className="rounded border border-red-300 p-3 text-sm text-red-800">{error}</p>}
    {notice && <p role="status" className="rounded border p-3 text-sm">{notice}</p>}
    <section aria-label="Record manual dispatch review" className="rounded-xl border bg-white p-4 space-y-3">
      <h2 className="font-semibold">Record a follow-up</h2>
      <p className="text-xs text-slate-600">Select an authorized, unresolved work order. One case may be open at a time for each work order.</p>
      <label className="block text-sm">Work order needing review
        <select aria-label="Manual review work order" value={selectedOrder}
          onChange={(e) => setSelectedOrder(e.target.value)}
          className="mt-1 block w-full rounded border p-2">
          <option value="">Select unresolved work order</option>
          {openOrders.map((item) => <option key={item.work_order_id} value={item.work_order_id}>
            #{item.work_order_id} · {item.property_name} · {item.title} · {item.attention_code.replaceAll("_", " ")}
          </option>)}
        </select>
      </label>
      <label className="block text-sm">Review reason
        <textarea aria-label="Manual dispatch review reason" rows={3} minLength={12} maxLength={1000}
          value={reason} onChange={(e) => setReason(e.target.value)}
          className="mt-1 block w-full rounded border p-2"
          placeholder="Describe the unmet dispatch need and expected human follow-up"/>
      </label>
      <button type="button" disabled={busy || !selectedOrder || reason.trim().length < 12}
        onClick={() => void openReview()} className="rounded bg-slate-900 px-4 py-2 text-sm text-white disabled:opacity-40">
        Record manual review (no notification)
      </button>
    </section>
    <section aria-label="Manual dispatch review history" className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="font-semibold">Review cases</h2>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={showClosed}
            onChange={(e) => { setShowClosed(e.target.checked); setOffset(0); }}/>
          Include closed cases
        </label>
      </div>
      {reviews === null ? <p>Loading authorized dispatch reviews...</p>
        : reviews.length === 0 ? <p className="rounded border p-4 text-sm">No reviews on this page.</p>
        : reviews.map((item) => <article key={item.id} className="rounded-xl border bg-white p-4 space-y-2">
          <div className="flex flex-wrap justify-between gap-3">
            <h3 className="font-semibold">Case #{item.id} · Work order #{item.work_order_id}</h3>
            <span className="text-sm">{item.status.toUpperCase()}</span>
          </div>
          <p className="text-sm">{item.reason}</p>
          <p className="text-xs text-slate-600">Opened by staff #{item.opened_by_user_id} · {new Date(item.created_at).toLocaleString()}</p>
          <Link href={"/dashboard/maintenance/work-orders/" + item.work_order_id}
            className="block text-sm text-blue-800 underline">View work order and assignment history</Link>
          {item.status === "closed" ?
            <p className="text-sm">Outcome: {item.resolution_note} · Closed by staff #{item.closed_by_user_id}</p> :
            <div className="space-y-2">
              <label className="block text-sm">Resolution and actions taken
                <textarea aria-label={"Manual review resolution case " + item.id}
                  value={resolutions[item.id] ?? ""}
                  onChange={(e) => setResolutions((current) => ({...current, [item.id]: e.target.value}))}
                  rows={2} minLength={12} maxLength={1000} className="mt-1 block w-full rounded border p-2"/>
              </label>
              <button type="button" disabled={busy || (resolutions[item.id]?.trim().length ?? 0) < 12}
                onClick={() => void closeReview(item.id)}
                className="rounded bg-slate-900 px-4 py-2 text-sm text-white disabled:opacity-40">
                Close case with recorded outcome
              </button>
            </div>}
          <p className="text-xs text-slate-600">External delivery confirmed: No</p>
        </article>)}
      <nav aria-label="Manual review pagination" className="flex items-center gap-3">
        <button type="button" disabled={offset === 0 || reviews === null}
          onClick={() => setOffset((current) => Math.max(0, current - PAGE_SIZE))}
          className="rounded border px-3 py-2 text-sm disabled:opacity-40">Previous</button>
        <span className="text-sm">Page {1 + offset / PAGE_SIZE}</span>
        <button type="button" disabled={!reviews || reviews.length < PAGE_SIZE || offset >= 9950}
          onClick={() => setOffset((current) => current + PAGE_SIZE)}
          className="rounded border px-3 py-2 text-sm disabled:opacity-40">Next</button>
      </nav>
    </section>
  </main>;
}
