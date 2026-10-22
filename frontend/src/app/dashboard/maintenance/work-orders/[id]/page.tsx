"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { apiGet, apiPost, apiPut } from "@/lib/api";

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

type OnCallShift = {
  id: number;
  crew_user_id: number;
  starts_at: string;
  ends_at: string;
  cancelled_at?: string | null;
  cancellation_reason?: string | null;
};
type DispatchPolicy = {
  group_id: number | null;
  group_name: string | null;
  urgency: string; daypart: string | null;
  configured: boolean; status: string;
  first_target?: string | null;
  backup_target?: string | null;
  timeout_minutes?: number | null;
  escalate: boolean;
};
type DispatchReadiness = {
  work_order_id: number;
  can_offer: boolean;
  crew_user_id: number | null;
  crew_name: string | null;
  on_call_shift_id: number | null;
  shift_ends_at: string | null;
  message: string;
  preferred_vendors: PreferredVendor[];
  effective_policy?: DispatchPolicy | null;
};
type VendorCandidate = { vendor_id: number; company_name: string; trade: string | null; insurance_status: string };
type PreferredVendor = { vendor_id: number; rank: number; company_name: string; trade: string; insurance_status: string };

type CrewTimeEntry = {
  id: number;
  started_at: string;
  ended_at: string;
  duration_minutes: number;
  notes?: string | null;
};

type CrewTimeSummary = {
  recorded_entries: number;
  recorded_minutes: number;
  reviewed_minutes: number;
  approved_entries: number;
  pending_corrections: number;
  payroll_approved: boolean;
};

type CrewTimeCorrection = {
  id: number;
  time_entry_id: number;
  proposed_started_at: string;
  proposed_ended_at: string;
  duration_minutes: number;
  reason: string;
  status: "pending" | "approved" | "denied";
  review_reason?: string | null;
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
  const [timeCorrections, setTimeCorrections] = useState<CrewTimeCorrection[]>([]);
  const [timeSummary, setTimeSummary] = useState<CrewTimeSummary | null>(null);
  const [correctionEntry, setCorrectionEntry] = useState<number | null>(null);
  const [correctionStart, setCorrectionStart] = useState("");
  const [correctionEnd, setCorrectionEnd] = useState("");
  const [correctionReason, setCorrectionReason] = useState("");
  const [reviewReasons, setReviewReasons] = useState<Record<number, string>>({});
  const [crew, setCrew] = useState<{ id: number; name: string }[]>([]);
  const [onCallShifts, setOnCallShifts] = useState<OnCallShift[] | null>(null);
  const [dispatchReadiness, setDispatchReadiness] = useState<DispatchReadiness | null>(null);
  const [onCallCrewId, setOnCallCrewId] = useState("");
  const [onCallStart, setOnCallStart] = useState("");
  const [onCallEnd, setOnCallEnd] = useState("");
  const [onCallCancelId, setOnCallCancelId] = useState<number | null>(null);
  const [onCallCancelReason, setOnCallCancelReason] = useState("");
  const [vendorCandidates, setVendorCandidates] = useState<VendorCandidate[] | null>(null);
  const [preferredVendors, setPreferredVendors] = useState<PreferredVendor[] | null>(null);
  const [preferredVendorDraft, setPreferredVendorDraft] = useState(["", "", ""]);
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
    setTimeCorrections([]);
    setTimeSummary(null);
    apiGet("/work-orders/" + order.id + "/time-ledger")
      .then((result: CrewTimeSummary) => {
        if (active) setTimeSummary(result);
      }).catch(() => { if (active) setTimeSummary(null); });
    apiGet("/work-orders/" + order.id + "/time-corrections")
      .then((result: CrewTimeCorrection[]) => {
        if (active) setTimeCorrections(Array.isArray(result) ? result : []);
      }).catch(() => { if (active) setTimeCorrections([]); });
    apiGet("/work-orders/" + order.id + "/time-entries")
      .then((result: CrewTimeEntry[]) => {
        if (active) setTimeEntries(Array.isArray(result) ? result : null);
      })
      .catch(() => { if (active) setTimeEntries(null); });
    return () => { active = false; };
  }, [order?.id, viewer?.id, viewer?.role]);

  useEffect(() => {
    const role = String(viewer?.role || "").toUpperCase();
    if (!order || !["ADMIN", "OWNER", "MANAGER"].includes(role)) {
      setVendorCandidates(null);
      setPreferredVendors(null);
      return;
    }
    let active = true;
    setVendorCandidates(null); setPreferredVendors(null);
    Promise.all([
      apiGet("/work-orders/" + order.id + "/vendor-candidates") as Promise<VendorCandidate[]>,
      apiGet("/work-orders/" + order.id + "/preferred-vendors") as Promise<PreferredVendor[]>,
    ]).then(([candidates, ranked]) => {
      if (!Array.isArray(candidates) || !Array.isArray(ranked))
        throw new Error("Invalid preferred vendor response.");
      if (active) {
        setVendorCandidates(candidates); setPreferredVendors(ranked);
        setPreferredVendorDraft([0, 1, 2].map((i) => String(ranked[i]?.vendor_id || "")));
      }
    }).catch(() => { if (active) { setVendorCandidates(null); setPreferredVendors(null); } });
    return () => { active = false; };
  }, [order?.id, order?.category, viewer?.role]);

  useEffect(() => {
    if (!order || !viewer || !["ADMIN", "OWNER", "MANAGER"].includes(String(viewer.role).toUpperCase())) {
      setOnCallShifts(null); return;
    }
    let active = true;
    setOnCallShifts(null);
    apiGet("/work-orders/" + order.id + "/on-call-shifts?limit=100&offset=0")
      .then((rows: OnCallShift[]) => {
        if (!Array.isArray(rows)) throw new Error("Unexpected on-call shifts.");
        if (active) setOnCallShifts(rows);
      }).catch(() => { if (active) setOnCallShifts(null); });
    return () => { active = false; };
  }, [order?.id, viewer?.id, viewer?.role]);

  useEffect(() => {
    if (!order || !viewer || !["ADMIN", "OWNER", "MANAGER"].includes(String(viewer.role).toUpperCase())) {
      setDispatchReadiness(null); return;
    }
    let active = true;
    setDispatchReadiness(null);
    apiGet("/work-orders/" + order.id + "/dispatch-readiness")
      .then((row: DispatchReadiness) => {
        if (!row || row.work_order_id !== order.id || typeof row.message !== "string")
          throw new Error("Invalid dispatch readiness response.");
        if (active) setDispatchReadiness(row);
      }).catch(() => { if (active) setDispatchReadiness(null); });
    return () => { active = false; };
  }, [order?.id, order?.status, order?.assigned_to_id, viewer?.role, onCallShifts]);

  async function offerOnCallCrew() {
    if (!order || !dispatchReadiness?.can_offer || saving) return;
    setSaving(true); setError(""); setNotice("");
    try {
      const result = await apiPost("/work-orders/" + order.id + "/offer-on-call") as WorkOrder;
      if (result.id !== order.id || result.assigned_to_id !== dispatchReadiness.crew_user_id
          || result.assignment_response !== "pending")
        throw new Error("Unexpected on-call offer response.");
      setNotice("On-call crew offer recorded in-app. No external SMS, email or call delivery is confirmed.");
      await reload();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to offer to current on-call crew.");
      await reload();
    } finally { setSaving(false); }
  }

  async function offerConfiguredPolicyCrew() {
    if (!order || saving || !dispatchReadiness?.can_offer
        || !dispatchReadiness.effective_policy?.configured
        || dispatchReadiness.effective_policy.first_target !== "crew") return;
    setSaving(true); setError(""); setNotice("");
    try {
      const row = await apiPost(
        "/api/maintenance/policy-offers/work-orders/" + order.id, {},
      ) as WorkOrder;
      if (row.id !== order.id || row.assigned_to_id !== dispatchReadiness.crew_user_id
          || row.assignment_response !== "pending")
        throw new Error("Configured policy offer did not return a pending crew assignment.");
      setNotice("Configured crew policy applied and in-app offer recorded. No external delivery or escalation has occurred.");
      await reload();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Cannot offer under this dispatch policy.");
      await reload();
    } finally { setSaving(false); }
  }

  async function scheduleOnCall() {
    if (!order || saving) return;
    const selected = Number(onCallCrewId);
    const starts = new Date(onCallStart), ends = new Date(onCallEnd);
    if (!Number.isSafeInteger(selected) || !crew.some((person) => person.id === selected)
        || !onCallStart || !onCallEnd || Number.isNaN(starts.getTime()) || Number.isNaN(ends.getTime())
        || starts <= new Date() || ends <= starts) {
      setError("Choose an available property crew member and a valid future shift.");
      return;
    }
    setSaving(true); setError(""); setNotice("");
    try {
      const shift = await apiPost("/work-orders/" + order.id + "/on-call-shifts", {
        crew_user_id: selected, starts_at: starts.toISOString(), ends_at: ends.toISOString(),
      }) as OnCallShift;
      if (!shift || !Number.isSafeInteger(shift.id) || shift.crew_user_id !== selected)
        throw new Error("Unexpected on-call schedule response.");
      setOnCallShifts((old) => old ? [shift, ...old.filter((row) => row.id !== shift.id)] : [shift]);
      setOnCallStart(""); setOnCallEnd(""); setOnCallCrewId("");
      setNotice("Property on-call shift scheduled. No automatic dispatch was performed.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not schedule on-call crew.");
    } finally { setSaving(false); }
  }

  async function cancelOnCall(shiftId: number) {
    if (!order || saving || onCallCancelReason.trim().length < 5) {
      setError("An on-call cancellation reason of at least five characters is required."); return;
    }
    setSaving(true); setError(""); setNotice("");
    try {
      const row = await apiPost("/work-orders/" + order.id + "/on-call-shifts/" + shiftId + "/cancel", {
        reason: onCallCancelReason.trim(),
      }) as OnCallShift;
      if (!row || row.id !== shiftId || !row.cancelled_at)
        throw new Error("Unexpected on-call cancellation response.");
      setOnCallShifts((old) => old?.map((shift) => shift.id === row.id ? row : shift) || []);
      setOnCallCancelId(null); setOnCallCancelReason("");
      setNotice("On-call shift cancelled with audit history retained.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to cancel on-call shift.");
    } finally { setSaving(false); }
  }

  async function savePreferredVendors() {
    if (!order || saving || vendorCandidates === null) return;
    const ids = preferredVendorDraft.filter(Boolean).map(Number);
    if (ids.some((id) => !Number.isSafeInteger(id) || !vendorCandidates.some((vendor) => vendor.vendor_id === id))
        || new Set(ids).size !== ids.length) {
      setError("Select up to three different eligible vendor companies."); return;
    }
    setSaving(true); setError(""); setNotice("");
    try {
      const ranked = await apiPut("/work-orders/" + order.id + "/preferred-vendors", { vendor_ids: ids }) as PreferredVendor[];
      if (!Array.isArray(ranked) || ranked.length !== ids.length)
        throw new Error("Unexpected saved vendor preferences.");
      setPreferredVendors(ranked);
      setPreferredVendorDraft([0, 1, 2].map((i) => String(ranked[i]?.vendor_id || "")));
      setNotice("Preferred vendor ranks saved for this property and maintenance trade.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to save preferred vendors.");
    } finally { setSaving(false); }
  }

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
      apiGet("/work-orders/" + order.id + "/time-ledger")
        .then((result: CrewTimeSummary) => setTimeSummary(result)).catch(() => {});
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to record crew time.");
    } finally {
      setSaving(false);
    }
  }


  async function requestTimeCorrection() {
    if (!order || saving || correctionEntry === null) return;
    const start = new Date(correctionStart), end = new Date(correctionEnd);
    if (!correctionStart || !correctionEnd || Number.isNaN(start.getTime()) ||
        Number.isNaN(end.getTime()) || start >= end || end.getTime() > Date.now()
        || correctionReason.trim().length < 5) {
      setError("Provide valid past times and a correction reason of at least 5 characters.");
      return;
    }
    setSaving(true); setError(""); setNotice("");
    try {
      const result = await apiPost(
        "/work-orders/" + order.id + "/time-entries/" + correctionEntry + "/corrections",
        { started_at: start.toISOString(), ended_at: end.toISOString(), reason: correctionReason.trim() },
      ) as CrewTimeCorrection;
      if (!result || !Number.isSafeInteger(result.id) || result.status !== "pending")
        throw new Error("Unexpected time correction response.");
      setTimeCorrections((items) => items.some((item) => item.id === result.id) ? items : [...items, result]);
      setCorrectionEntry(null); setCorrectionStart(""); setCorrectionEnd(""); setCorrectionReason("");
      setNotice("Correction requested for independent review. Original evidence remains unchanged.");
      apiGet("/work-orders/" + order.id + "/time-ledger")
        .then((result: CrewTimeSummary) => setTimeSummary(result)).catch(() => {});
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Time correction failed."); }
    finally { setSaving(false); }
  }

  async function reviewTimeCorrection(id: number, approve: boolean) {
    if (!order || saving) return;
    const reason = (reviewReasons[id] || "").trim();
    if (reason.length < 5) { setError("Review reason must be at least 5 characters."); return; }
    setSaving(true); setError(""); setNotice("");
    try {
      const result = await apiPost("/work-orders/" + order.id + "/time-corrections/" + id + "/decision", {
        approve, reason,
      }) as CrewTimeCorrection;
      if (!result || result.id !== id || result.status !== (approve ? "approved" : "denied"))
        throw new Error("Unexpected correction review response.");
      setTimeCorrections((items) => items.map((item) => item.id === id ? result : item));
      setReviewReasons((items) => { const next = { ...items }; delete next[id]; return next; });
      setNotice("Time correction " + result.status + ". Original time evidence remains intact.");
      apiGet("/work-orders/" + order.id + "/time-ledger")
        .then((data: CrewTimeSummary) => setTimeSummary(data)).catch(() => {});
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Unable to review time correction."); }
    finally { setSaving(false); }
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
          {["ADMIN","OWNER","MANAGER"].includes(String(viewer?.role||"").toUpperCase()) && (
            <Link href={"/dashboard/maintenance/material-orders?work_order_id="+order.id}
              className="inline-flex rounded-lg border bg-white px-4 py-2 text-sm text-blue-800 underline">
              Request materials and view purchase approvals
            </Link>
          )}
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
          {viewer && ["ADMIN", "OWNER", "MANAGER"].includes(String(viewer.role).toUpperCase()) && (
            <section aria-label="Property on-call crew shifts" className="rounded-xl border bg-white p-5">
              <h2 className="font-semibold">Property on-call crew shifts</h2>
              <p className="mt-1 text-xs text-slate-500">
                Set a primary on-call crew shift for this property, with no overlapping active shifts.
                A schedule does not dispatch anyone or approve a payment.
              </p>

              <div role="region" className="mt-3 rounded-lg border p-3" aria-label="Current on-call dispatch readiness">
                <h3 className="text-sm font-semibold">Current dispatch readiness</h3>
                {dispatchReadiness ? (
                  <>
                    <p className="mt-1 text-sm">{dispatchReadiness.message}</p>
                    {dispatchReadiness.effective_policy && (
                      <div className="mt-2 border-t pt-2 text-xs text-slate-600">
                        <p className="font-medium">Effective group: {dispatchReadiness.effective_policy.group_name || "Not configured"}</p>
                        <p>Policy: {dispatchReadiness.effective_policy.urgency}
                          {dispatchReadiness.effective_policy.daypart
                            ? " · " + dispatchReadiness.effective_policy.daypart.replaceAll("_", " ") : ""}
                        </p>
                        {dispatchReadiness.effective_policy.configured
                          ? <p>Primary target: {dispatchReadiness.effective_policy.first_target},
                            backup: {dispatchReadiness.effective_policy.backup_target},
                            timeout: {dispatchReadiness.effective_policy.timeout_minutes} minutes,
                            escalation setting: {dispatchReadiness.effective_policy.escalate ? "enabled" : "disabled"}.
                            Advisory only, no automatic contact or timer is active.
                          </p>
                          : <p>No active policy configured for this urgency and time window. Manual management action required.</p>}
                      </div>
                    )}
                    {dispatchReadiness.crew_name && <p className="mt-1 text-xs text-slate-600">
                      Current on-call: {dispatchReadiness.crew_name}
                      {dispatchReadiness.shift_ends_at ? " (until " + new Date(dispatchReadiness.shift_ends_at + "Z").toLocaleString() + ")" : ""}
                    </p>}
                    {dispatchReadiness.can_offer && order.status === "acknowledged" && (
                      <button type="button" disabled={saving} onClick={() => void offerOnCallCrew()}
                        className="mt-3 rounded bg-slate-900 px-3 py-2 text-sm text-white disabled:opacity-50">
                        Offer to current on-call crew (in-app only)
                      </button>
                    )}
                    {dispatchReadiness.can_offer && order.status === "acknowledged"
                      && dispatchReadiness.effective_policy?.configured
                      && dispatchReadiness.effective_policy.first_target === "crew" && (
                        <div className="mt-3 rounded border bg-slate-50 p-3">
                          <p className="text-xs text-slate-600">
                            Configured primary route: on-call crew. This requires your explicit confirmation;
                            the policy timeout is guidance only and external delivery is not enabled.
                          </p>
                          <button type="button" disabled={saving}
                            onClick={() => void offerConfiguredPolicyCrew()}
                            className="mt-2 rounded bg-slate-900 px-3 py-2 text-sm text-white disabled:opacity-50">
                            Confirm policy-guided crew offer (in-app)
                          </button>
                        </div>
                      )}
                    {!dispatchReadiness.crew_user_id && dispatchReadiness.preferred_vendors.length > 0 && (
                      <p className="mt-2 text-xs text-slate-600">
                        Review ranked preferred vendors below for manual follow-up. No vendor has been contacted.
                      </p>
                    )}
                  </>
                ) : <p className="mt-1 text-sm text-slate-500">Dispatch readiness unavailable. Refresh before assigning.</p>}
              </div>
              {onCallShifts === null ? <p className="mt-2 text-sm text-slate-500">On-call schedule unavailable.</p> : (
                <>
                  <div className="mt-3 grid gap-3 sm:grid-cols-3">
                    <label className="text-sm">On-call crew
                      <select aria-label="On-call crew member" className="mt-1 block w-full rounded border p-2"
                        value={onCallCrewId} onChange={(e) => setOnCallCrewId(e.target.value)} disabled={saving}>
                        <option value="">Select eligible crew</option>
                        {crew.map((person) => <option key={person.id} value={person.id}>{person.name}</option>)}
                      </select>
                    </label>
                    <label className="text-sm">Shift start
                      <input aria-label="On-call shift start" type="datetime-local"
                        className="mt-1 block w-full rounded border p-2"
                        value={onCallStart} onChange={(e) => setOnCallStart(e.target.value)} disabled={saving}/>
                    </label>
                    <label className="text-sm">Shift end
                      <input aria-label="On-call shift end" type="datetime-local"
                        className="mt-1 block w-full rounded border p-2"
                        value={onCallEnd} onChange={(e) => setOnCallEnd(e.target.value)} disabled={saving}/>
                    </label>
                  </div>
                  <button type="button" className="mt-3 rounded bg-slate-900 px-4 py-2 text-sm text-white"
                    disabled={saving || !onCallCrewId || !onCallStart || !onCallEnd}
                    onClick={() => void scheduleOnCall()}>Schedule on-call crew</button>
                  {onCallShifts.length === 0
                    ? <p className="mt-3 text-sm text-slate-500">No on-call shifts scheduled for this property.</p>
                    : <ul className="mt-3 divide-y">{onCallShifts.map((shift) => (
                      <li key={shift.id} className="py-3 text-sm">
                        <p>Shift #{shift.id} · {crew.find((person) => person.id === shift.crew_user_id)?.name || `Crew #${shift.crew_user_id}`}
                          {" · "}{new Date(shift.starts_at + "Z").toLocaleString()} – {new Date(shift.ends_at + "Z").toLocaleString()}
                        </p>
                        {shift.cancelled_at ? <p className="text-slate-500">Cancelled: {shift.cancellation_reason}</p>
                        : <div className="mt-2">
                            {onCallCancelId === shift.id ? (
                              <div className="space-y-2">
                                <textarea aria-label="On-call cancellation reason" className="w-full rounded border p-2"
                                  maxLength={1000} value={onCallCancelReason} disabled={saving}
                                  onChange={(e) => setOnCallCancelReason(e.target.value)} />
                                <button type="button" onClick={() => void cancelOnCall(shift.id)}
                                  disabled={saving || onCallCancelReason.trim().length < 5}
                                  className="rounded bg-slate-900 px-3 py-2 text-white">Confirm shift cancellation</button>
                                <button type="button" className="ml-2 rounded border px-3 py-2"
                                  disabled={saving} onClick={() => {setOnCallCancelId(null);setOnCallCancelReason("");}}>Keep shift</button>
                              </div>
                            ) : <button type="button" className="rounded border px-3 py-2"
                                  disabled={saving} onClick={() => {setOnCallCancelId(shift.id);setOnCallCancelReason("");}}>
                                  Cancel shift
                                </button>}
                          </div>}
                      </li>
                    ))}</ul>}
                </>
              )}
            </section>
          )}
          {viewer && ["ADMIN", "OWNER", "MANAGER"].includes(String(viewer.role).toUpperCase()) && (
            <section aria-label="Property preferred maintenance vendors" className="rounded-xl border bg-white p-5">
              <h2 className="font-semibold">Preferred maintenance vendors</h2>
              <p className="mt-1 text-xs text-slate-500">
                Ranking is shared across this property for the {order.category} trade. Preferences are planning only:
                they do not dispatch a vendor, grant access, approve an invoice, or post a resident charge.
                Confirm insurance, compliance, availability, and contracts before any real assignment.
              </p>
              {vendorCandidates === null || preferredVendors === null
                ? <p className="mt-3 text-sm text-slate-500">Vendor preferences unavailable.</p>
                : <>
                    <p className="mt-3 text-xs text-slate-600">
                      {preferredVendors.length === 0 ? "No preferred vendors configured." :
                        preferredVendors.map((v) => `#${v.rank} ${v.company_name} (insurance ${v.insurance_status.replaceAll("_", " ").toLowerCase()})`).join(" · ")}
                    </p>
                    <div className="mt-3 grid gap-3 sm:grid-cols-3">
                      {preferredVendorDraft.map((selected, index) => <label key={index} className="text-sm">
                        Preference rank {index + 1}
                        <select aria-label={`Preferred vendor rank ${index + 1}`} className="mt-1 block w-full rounded border p-2"
                          value={selected} disabled={saving}
                          onChange={(event) => setPreferredVendorDraft((before) =>
                            before.map((value, i) => i === index ? event.target.value : value))}>
                          <option value="">No vendor</option>
                          {vendorCandidates.map((vendor) => <option key={vendor.vendor_id} value={vendor.vendor_id}>
                            {vendor.company_name} · Insurance {vendor.insurance_status.replaceAll("_", " ")}
                          </option>)}
                        </select>
                      </label>)}
                    </div>
                    <button type="button" disabled={saving} onClick={() => void savePreferredVendors()}
                      className="mt-3 rounded bg-slate-900 px-4 py-2 text-sm text-white disabled:opacity-50">
                      Save preferred vendor ranking
                    </button>
                  </>}
            </section>
          )}
          {viewer && ["ADMIN", "OWNER", "MANAGER", "CREW"].includes(String(viewer.role).toUpperCase()) && (
            <section aria-label="Crew time records" className="rounded-xl border bg-white p-5">
              <h2 className="font-semibold">Crew time tracking</h2>
              <p className="mt-1 text-xs text-slate-500">Hours are historical evidence only, not approved payroll or tenant charges.</p>
              {timeSummary && (
                <div className="mt-3 rounded-lg border p-3 text-sm" aria-label="Crew work time summary">
                  <p>Original work evidence: {timeSummary.recorded_entries} entries, {timeSummary.recorded_minutes} minutes</p>
                  <p>Reviewed work evidence: {timeSummary.reviewed_minutes} minutes ({timeSummary.approved_entries} approved corrections)</p>
                  <p>Corrections awaiting review: {timeSummary.pending_corrections}</p>
                  <p className="mt-1 text-xs text-slate-500">Informational only — no payable time or tenant charge approved.</p>
                </div>
              )}
              {timeEntries === null ? <p className="mt-2 text-sm text-slate-500">Crew hours unavailable.</p>
                : timeEntries.length === 0 ? <p className="mt-2 text-sm text-slate-500">No time entries recorded.</p>
                : <ul className="mt-3 space-y-2">
                    {timeEntries.map((entry) => <li key={entry.id} className="rounded-lg border p-3 text-sm">
                      {new Date(entry.started_at + "Z").toLocaleString()} to {new Date(entry.ended_at + "Z").toLocaleString()}
                      · {entry.duration_minutes} minutes
                      {entry.notes && <p className="mt-1 whitespace-pre-wrap">{entry.notes}</p>}
                      {(() => {
                        const approved = timeCorrections.filter((item) =>
                          item.time_entry_id === entry.id && item.status === "approved").at(-1);
                        return approved ? <p className="mt-1 font-medium text-emerald-800">
                          Reviewed correction: {approved.duration_minutes} minutes
                        </p> : null;
                      })()}
                      {viewer.role?.toUpperCase() === "CREW" && order.assigned_to_id === viewer.id && (
                        <button type="button" disabled={saving} onClick={() => {
                          setCorrectionEntry(entry.id); setCorrectionStart(""); setCorrectionEnd(""); setCorrectionReason("");
                        }} className="mt-2 rounded border px-2 py-1 text-xs">Request time correction</button>
                      )}
                    </li>)}
                  </ul>}
              {correctionEntry !== null && viewer.role?.toUpperCase() === "CREW" && (
                <div className="mt-4 space-y-2 rounded-lg border p-3">
                  <h3 className="font-medium">Correct time entry #{correctionEntry}</h3>
                  <label className="block text-sm">Corrected start
                    <input aria-label="Corrected start" type="datetime-local" value={correctionStart}
                      onChange={(event) => setCorrectionStart(event.target.value)}
                      className="mt-1 block rounded border p-2" disabled={saving} />
                  </label>
                  <label className="block text-sm">Corrected end
                    <input aria-label="Corrected end" type="datetime-local" value={correctionEnd}
                      onChange={(event) => setCorrectionEnd(event.target.value)}
                      className="mt-1 block rounded border p-2" disabled={saving} />
                  </label>
                  <label className="block text-sm">Correction reason
                    <textarea aria-label="Time correction reason" maxLength={1000}
                      value={correctionReason} onChange={(event) => setCorrectionReason(event.target.value)}
                      className="mt-1 w-full rounded border p-2" disabled={saving} />
                  </label>
                  <button type="button" disabled={saving || correctionReason.trim().length < 5}
                    onClick={() => void requestTimeCorrection()}
                    className="rounded bg-slate-900 px-3 py-2 text-sm text-white">Submit correction request</button>
                  <button type="button" disabled={saving} onClick={() => setCorrectionEntry(null)}
                    className="ml-2 rounded border px-3 py-2 text-sm">Cancel</button>
                </div>
              )}
              {timeCorrections.length > 0 && (
                <div className="mt-4 space-y-3" aria-label="Time correction reviews">
                  <h3 className="font-semibold">Correction review history</h3>
                  {timeCorrections.map((item) => <div key={item.id} className="rounded-lg border p-3 text-sm">
                    <p>Entry #{item.time_entry_id} — {item.status} — proposed {item.duration_minutes} minutes</p>
                    <p className="mt-1 whitespace-pre-wrap">Reason: {item.reason}</p>
                    {item.review_reason && <p className="mt-1">Decision: {item.review_reason}</p>}
                    {item.status === "pending" && ["ADMIN", "OWNER", "MANAGER"].includes(viewer.role?.toUpperCase() || "") && (
                      <div className="mt-2 space-y-2">
                        <textarea aria-label={"Review reason for correction " + item.id}
                          maxLength={1000} value={reviewReasons[item.id] || ""}
                          onChange={(event) => setReviewReasons((items) => ({ ...items, [item.id]: event.target.value }))}
                          className="w-full rounded border p-2" placeholder="Required approval or denial reason"
                          disabled={saving} />
                        <button type="button" disabled={saving || (reviewReasons[item.id] || "").trim().length < 5}
                          onClick={() => void reviewTimeCorrection(item.id, true)}
                          className="rounded bg-slate-900 px-3 py-2 text-white">Approve correction</button>
                        <button type="button" disabled={saving || (reviewReasons[item.id] || "").trim().length < 5}
                          onClick={() => void reviewTimeCorrection(item.id, false)}
                          className="ml-2 rounded border px-3 py-2">Deny correction</button>
                      </div>
                    )}
                  </div>)}
                </div>
              )}
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
