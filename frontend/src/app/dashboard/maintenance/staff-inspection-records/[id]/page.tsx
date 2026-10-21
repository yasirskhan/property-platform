"use client";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { apiGet, apiPost } from "@/lib/api";

type ChecklistItem = { area: string; condition: string; notes: string };
type FollowUp = { id: number; title: string; status: string; priority: string };
type Review = {
  id: number; inspection_id: number; reviewer_id: number; reviewer_name?: string | null;
  decision: "CONFIRMED" | "FOLLOW_UP_REQUIRED"; notes: string; reviewed_at: string;
};
type Inspection = {
  id: number; property_id: number; unit_id: number;
  property_name?: string | null; unit_number?: string | null;
  inspection_date: string; recorded_condition: string;
  findings: string; checklist_items: ChecklistItem[];
  recorded_by_id: number | null; recorded_by_name?: string | null; recorded_at: string;
};

export default function StaffInspectionDetailPage() {
  const params = useParams();
  const id = String(params.id ?? "");
  const [record, setRecord] = useState<Inspection | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [followUps, setFollowUps] = useState<FollowUp[]>([]);
  const [followUpsLoading, setFollowUpsLoading] = useState(false);
  const [followUpsError, setFollowUpsError] = useState("");
  const [review, setReview] = useState<Review | null>(null);
  const [reviewLoading, setReviewLoading] = useState(true);
  const [reviewError, setReviewError] = useState("");
  const [reviewMessage, setReviewMessage] = useState("");
  const [reviewDecision, setReviewDecision] = useState<Review["decision"]>("CONFIRMED");
  const [reviewNotes, setReviewNotes] = useState("");
  const [reviewSaving, setReviewSaving] = useState(false);
  const [actor, setActor] = useState<{ id: number; role: string } | null>(null);

  useEffect(() => {
    let active = true;
    if (!/^[1-9]\d*$/.test(id)) {
      setError("Invalid inspection record."); setLoading(false);
      return;
    }
    apiGet(`/api/unit-inspections/${id}`)
      .then((data: Inspection) => {
        if (!data || data.id !== Number(id)) throw new Error("Inspection record unavailable.");
        if (active) setRecord(data);
      })
      .catch((cause) => {
        if (active) setError(cause instanceof Error ? cause.message : "Inspection record unavailable.");
      })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [id]);

  useEffect(() => {
    if (!record) return;
    let active = true;
    setFollowUpsLoading(true);
    setFollowUpsError("");
    apiGet(`/api/unit-inspections/${record.id}/work-orders?limit=100`)
      .then((rows: FollowUp[]) => {
        if (!Array.isArray(rows)) throw new Error("Invalid linked maintenance response.");
        if (active) setFollowUps(rows);
      })
      .catch((cause) => {
        if (active) setFollowUpsError(cause instanceof Error ? cause.message : "Linked work orders unavailable.");
      })
      .finally(() => { if (active) setFollowUpsLoading(false); });
    return () => { active = false; };
  }, [record]);


  useEffect(() => {
    let active = true;
    apiGet("/auth/me")
      .then((user: { id: number; role: string }) => { if (active) setActor(user); })
      .catch(() => { if (active) setReviewError("Unable to verify reviewer identity."); });
    return () => { active = false; };
  }, []);

  useEffect(() => {
    if (!record) return;
    let active = true;
    setReviewLoading(true);
    apiGet(`/api/unit-inspections/${record.id}/review`)
      .then((result: Review | null) => { if (active) setReview(result); })
      .catch((cause) => { if (active) setReviewError(cause instanceof Error ? cause.message : "Unable to load inspection review."); })
      .finally(() => { if (active) setReviewLoading(false); });
    return () => { active = false; };
  }, [record]);

  async function saveReview() {
    if (!record || reviewSaving || review || reviewNotes.trim().length < 10) return;
    setReviewSaving(true); setReviewError(""); setReviewMessage("");
    try {
      const result: Review = await apiPost(`/api/unit-inspections/${record.id}/review`, {
        decision: reviewDecision, notes: reviewNotes.trim(),
      });
      setReview(result);
      setReviewMessage("Independent inspection review recorded and audited.");
    } catch (cause) {
      setReviewError(cause instanceof Error ? cause.message : "Unable to save review.");
    } finally {
      setReviewSaving(false);
    }
  }

  const mayReview = actor && record && !reviewLoading && !review
    && actor.id !== record.recorded_by_id
    && record.recorded_by_id !== null
    && ["ADMIN", "OWNER", "MANAGER"].includes(String(actor.role).toUpperCase());

  return <main className="space-y-5">
    <Link href="/dashboard/maintenance/staff-inspection-records" className="text-sm text-blue-800 hover:underline">Back to inspection records</Link>
    <h1 className="text-2xl font-semibold">Inspection #{id}</h1>
    {loading && <p role="status">Loading inspection evidence…</p>}
    {error && <p role="alert" className="rounded-lg border p-3 text-red-700">{error}</p>}
    {!loading && record && <article className="space-y-3 rounded-xl border bg-white p-5">
      <h2 className="text-lg font-medium">{record.property_name || `Property #${record.property_id}`} · Unit {record.unit_number || record.unit_id}</h2>
      <p>Inspection date: {record.inspection_date}</p>
      <p>Condition: {record.recorded_condition.replaceAll("_", " ")}</p>
      <p className="whitespace-pre-wrap">Findings: {record.findings || "No findings noted."}</p>
      <Link href={`/dashboard/maintenance/work-orders/new?source_inspection_id=${record.id}`}
        className="inline-block rounded-lg border px-4 py-2 text-sm text-blue-800 hover:underline">
        Create follow-up work order
      </Link>
      <section className="space-y-2 rounded-lg border p-3">
        <h3 className="font-semibold">Linked maintenance work orders</h3>
        {followUpsLoading && <p role="status">Loading follow-up work orders…</p>}
        {followUpsError && <p role="alert" className="text-sm text-red-700">{followUpsError}</p>}
        {!followUpsLoading && !followUpsError && followUps.length === 0 &&
          <p className="text-sm text-slate-600">No maintenance work orders linked to this inspection.</p>}
        {followUps.length > 0 && <ul className="space-y-2">
          {followUps.map((order) => <li key={order.id} className="text-sm">
            <Link href={`/dashboard/maintenance/work-orders/${order.id}`} className="text-blue-800 underline">
              Work order #{order.id}: {order.title}
            </Link>
            {" · "}{order.status.replaceAll("_", " ")}
          </li>)}
        </ul>}
        {followUps.length === 100 && <p className="text-xs text-slate-500">Showing the most recent 100 linked work orders.</p>}
      </section>
      <section className="space-y-3 rounded-lg border p-3">
        <h3 className="font-semibold">Independent inspection review</h3>
        <p className="text-xs text-slate-600">
          An authorized person other than the inspector records this decision. It does not
          create a work order, notify anyone, authorize spending or change the original inspection.
        </p>
        {reviewLoading && <p role="status">Loading independent review…</p>}
        {reviewError && <p role="alert" className="text-sm text-red-700">{reviewError}</p>}
        {reviewMessage && <p role="status" className="text-sm text-green-700">{reviewMessage}</p>}
        {!reviewLoading && review && <div className="rounded-lg border p-3 text-sm">
          <p className="font-medium">Decision: {review.decision.replaceAll("_", " ")}</p>
          <p className="whitespace-pre-wrap">Reason: {review.notes}</p>
          <p>Reviewed by {review.reviewer_name ? `${review.reviewer_name} (user #${review.reviewer_id})` : `user #${review.reviewer_id}`} on {review.reviewed_at}</p>
          <p className="text-xs">This decision is immutable. Subsequent changes require separate audited follow-up.</p>
        </div>}
        {mayReview && <div className="space-y-3">
          <label className="block text-sm">Independent review decision
            <select value={reviewDecision} onChange={(e) => setReviewDecision(e.target.value as Review["decision"])}
              className="mt-1 block w-full rounded border p-2">
              <option value="CONFIRMED">Confirm inspection record</option>
              <option value="FOLLOW_UP_REQUIRED">Follow-up required</option>
            </select>
          </label>
          <label className="block text-sm">Review explanation
            <textarea value={reviewNotes} onChange={(e) => setReviewNotes(e.target.value)}
              maxLength={1000} rows={3} className="mt-1 block w-full rounded border p-2"
              placeholder="Describe the independent review findings (at least 10 characters)." />
          </label>
          <button type="button" onClick={saveReview}
            disabled={reviewSaving || reviewNotes.trim().length < 10}
            className="rounded-lg border px-4 py-2 text-sm disabled:opacity-50">
            {reviewSaving ? "Saving…" : "Record independent review"}
          </button>
        </div>}
        {!reviewLoading && !review && !mayReview && !reviewError &&
          <p className="text-sm text-slate-600">Review requires a different authorized Owner, Admin, or property Manager.</p>}
      </section>
      <h3 className="font-semibold">Recorded checklist</h3>
      {record.checklist_items?.length ? <ul className="space-y-2">
        {record.checklist_items.map((item) => <li className="rounded-lg border p-3" key={item.area}>
          <p className="font-medium">{item.area.replaceAll("_", " ")}: {item.condition.replaceAll("_", " ")}</p>
          {item.notes && <p className="whitespace-pre-wrap">{item.notes}</p>}
        </li>)}
      </ul> : <p>No checklist was recorded.</p>}
      <p className="text-sm text-slate-600">Recorded by {record.recorded_by_name || `user #${record.recorded_by_id ?? "unknown"}`} · {record.recorded_at}</p>
      <p className="text-xs text-slate-600">This is immutable staff-recorded evidence, not an approval or an automated inspection.</p>
    </article>}
  </main>;
}
