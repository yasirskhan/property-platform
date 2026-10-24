"use client";
import { FormEvent, useEffect, useState } from "react";
import Link from "next/link";
import { apiGet, apiPost, apiPatch } from "@/lib/api";

type UnitChoice = { id: number; property_name: string; unit_number: string };
type Schedule = {
  id: number; organization_id: number; property_id: number; unit_id: number;
  title: string; description: string; interval_days: number;
  next_due_date: string; end_date?: string | null; active: boolean;
  executor_user_id?: number | null;
};
type Occurrence = { id: number; schedule_id: number; due_date: string; work_order_id: number };
type Generation = { work_order_id: number; newly_created: boolean; tenant_id: number | null };
type CatchUp = { schedule_id: number; as_of: string; created_work_order_ids: number[]; remaining_due: boolean };
type ExecutionStatus = { schedule_id: number; executor_user_id: number; status: string; due: boolean; block_reason?: string | null };
type Reconciliation = {
  schedule_id:number;verified_occurrences:number;latest_due_date:string|null;
  latest_work_order_id:number|null;next_due_date:string;integrity_status:"VERIFIED";
  read_only:true;work_orders_created:0;automatic_dispatch:false;financial_posted:false;
};
type DuePreview = { schedule_id: number; active: boolean; as_of: string; due_dates: string[]; has_more: boolean };
type RecoveryReceipt = {
  root_work_order_id:number;reason:string;operator_user_id:number|null;
  created_work_orders:{work_order_id:number;due_date:string}[];
};

export default function PreventiveMaintenancePage() {
  const [units, setUnits] = useState<UnitChoice[]>([]);
  const [unitSearch, setUnitSearch] = useState("");
  const [unitId, setUnitId] = useState("");
  const [unitsError, setUnitsError] = useState("");
  const [unitsLoading, setUnitsLoading] = useState(true);
  const [schedules, setSchedules] = useState<Schedule[]>([]);
  const [loading, setLoading] = useState(true);
  const [nextOffset, setNextOffset] = useState(0);
  const [scheduleSearch, setScheduleSearch] = useState("");
  const [appliedScheduleSearch, setAppliedScheduleSearch] = useState("");
  const [searchingSchedules, setSearchingSchedules] = useState(false);
  const [dueOnly, setDueOnly] = useState(false);
  const [appliedDueOnly, setAppliedDueOnly] = useState(false);
  const [hasMore, setHasMore] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [moreError, setMoreError] = useState("");
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [interval, setInterval] = useState("30");
  const [dueDate, setDueDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [saving, setSaving] = useState(false);
  const [busyId, setBusyId] = useState<number | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [historyId, setHistoryId] = useState<number | null>(null);
  const [reconciliation, setReconciliation] = useState<Reconciliation|null>(null);
  const [reconcileError, setReconcileError] = useState("");
  const [reconcileErrorId, setReconcileErrorId] = useState<number|null>(null);
  const [reconcileBusyId, setReconcileBusyId] = useState<number|null>(null);
  const [recoveryId, setRecoveryId] = useState<number|null>(null);
  const [recoveryReason, setRecoveryReason] = useState("");
  const [recoveryCursor, setRecoveryCursor] = useState("");
  const [receiptSchedule, setReceiptSchedule] = useState<number|null>(null);
  const [recoveryReceipts, setRecoveryReceipts] = useState<RecoveryReceipt[]>([]);
  const [receiptsError, setReceiptsError] = useState("");
  const [receiptsBusy, setReceiptsBusy] = useState(false);
  const [preview, setPreview] = useState<DuePreview | null>(null);
  const [previewError, setPreviewError] = useState("");
  const [previewErrorId, setPreviewErrorId] = useState<number | null>(null);
  const [previewLoadingId, setPreviewLoadingId] = useState<number | null>(null);
  const [occurrences, setOccurrences] = useState<Occurrence[]>([]);
  const [historyError, setHistoryError] = useState("");
  const [historyOffset, setHistoryOffset] = useState(0);
  const [historyHasMore, setHistoryHasMore] = useState(false);
  const [historyMoreError, setHistoryMoreError] = useState("");
  const [historyLoadingMore, setHistoryLoadingMore] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [takeoverId, setTakeoverId] = useState<number | null>(null);
  const [takeoverReason, setTakeoverReason] = useState("");
  const [executionStatus, setExecutionStatus] = useState<ExecutionStatus | null>(null);
  const [batchHealth, setBatchHealth] = useState<Record<number, ExecutionStatus>>({});
  const [batchHealthLoading, setBatchHealthLoading] = useState(false);
  const [batchHealthError, setBatchHealthError] = useState("");
  const [showBlockedOnly, setShowBlockedOnly] = useState(false);
  const [executionError, setExecutionError] = useState("");
  const [executionErrorId, setExecutionErrorId] = useState<number | null>(null);
  const [editTitle, setEditTitle] = useState("");
  const [editDescription, setEditDescription] = useState("");
  const [editInterval, setEditInterval] = useState("30");
  const [editEndDate, setEditEndDate] = useState("");

  async function loadMore() {
    if (loadingMore || !hasMore) return;
    setLoadingMore(true); setMoreError("");
    try {
      const rows = await apiGet(
        `/api/maintenance/preventive/schedules?limit=100&offset=${nextOffset}&search=${encodeURIComponent(appliedScheduleSearch)}&due_only=${appliedDueOnly}`
      ) as Schedule[];
      if (!Array.isArray(rows)) throw new Error("Unexpected schedule response.");
      setSchedules((previous) => {
        const known = new Set(previous.map((row) => row.id));
        return [...previous, ...rows.filter((row) => !known.has(row.id))];
      });
      setNextOffset((old) => old + rows.length);
      setHasMore(rows.length === 100);
      setShowBlockedOnly(false);
    } catch (cause) {
      setMoreError(cause instanceof Error ? cause.message : "Older schedules unavailable.");
    } finally { setLoadingMore(false); }
  }

  useEffect(() => {
    let active = true;
    apiGet("/api/maintenance/preventive/schedules?limit=100")
      .then((rows: Schedule[]) => {
        if (!Array.isArray(rows)) throw new Error("Unexpected schedule response.");
        if (active) {
          setSchedules(rows);
          setNextOffset(rows.length);
          setHasMore(rows.length === 100);
        }
      })
      .catch((cause) => {
        if (active) setError(cause instanceof Error ? cause.message : "Schedules unavailable.");
      })
      .finally(() => { if (active) setLoading(false); });
    apiGet("/work-orders/request-units?limit=100")
      .then((rows: UnitChoice[]) => {
        if (!Array.isArray(rows)) throw new Error("Unexpected units response.");
        if (active) setUnits(rows);
      })
      .catch((cause) => {
        if (active) setUnitsError(cause instanceof Error ? cause.message : "Units unavailable.");
      })
      .finally(() => { if (active) setUnitsLoading(false); });
    return () => { active = false; };
  }, []);

  async function searchSchedules(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const term = scheduleSearch.trim();
    setSearchingSchedules(true); setMoreError(""); setError("");
    try {
      const rows = await apiGet(`/api/maintenance/preventive/schedules?limit=100&search=${encodeURIComponent(term)}&due_only=${dueOnly}`) as Schedule[];
      if (!Array.isArray(rows)) throw new Error("Unexpected schedule search response.");
      setSchedules(rows); setNextOffset(rows.length); setHasMore(rows.length === 100);
      setBatchHealth({});
      setShowBlockedOnly(false);
      setAppliedScheduleSearch(term);
      setAppliedDueOnly(dueOnly);
    } catch (cause) {
      setMoreError(cause instanceof Error ? cause.message : "Schedule search failed.");
    } finally { setSearchingSchedules(false); }
  }

  async function searchUnits(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setUnitsLoading(true);
    setUnitsError("");
    setUnitId("");
    try {
      const query = new URLSearchParams({ limit: "100" });
      if (unitSearch.trim()) query.set("search", unitSearch.trim());
      const rows = await apiGet("/work-orders/request-units?" + query.toString()) as UnitChoice[];
      if (!Array.isArray(rows)) throw new Error("Unexpected units response.");
      setUnits(rows);
    } catch (cause) {
      setUnitsError(cause instanceof Error ? cause.message : "Unit search failed.");
      setUnits([]);
    } finally {
      setUnitsLoading(false);
    }
  }

  async function create(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!units.some((unit) => String(unit.id) === unitId)) {
      setError("Choose an authorized unit.");
      return;
    }
    setSaving(true); setError(""); setNotice("");
    try {
      const created = await apiPost("/api/maintenance/preventive/schedules", {
        unit_id: Number(unitId), title: title.trim(), description: description.trim(),
        interval_days: Number(interval), next_due_date: dueDate,
        ...(endDate ? { end_date: endDate } : {}),
      }) as Schedule;
      if (!Number.isSafeInteger(created?.id)) throw new Error("Invalid saved schedule.");
      setSchedules((previous) => [created, ...previous.filter((row) => row.id !== created.id)]);
      setBatchHealth({});
      setShowBlockedOnly(false);
      setNextOffset((previous) => previous + 1);
      setTitle(""); setDescription(""); setDueDate(""); setEndDate("");
      setNotice("Schedule saved. No work order was generated at creation; due dates are checked daily.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Schedule could not be saved.");
    } finally { setSaving(false); }
  }

  async function toggle(row: Schedule) {
    setBusyId(row.id); setError(""); setNotice("");
    try {
      const updated = await apiPatch(`/api/maintenance/preventive/schedules/${row.id}`,
        { active: !row.active }) as Schedule;
      setSchedules((previous) => previous.map((item) => item.id === row.id ? updated : item));
      setBatchHealth((previous) => { const next = { ...previous }; delete next[row.id]; return next; });
      setShowBlockedOnly(false);
      setPreview((prior) => prior?.schedule_id === row.id ? null : prior);
      setNotice(updated.active ? "Schedule resumed." : "Schedule paused.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Cannot change schedule.");
    } finally { setBusyId(null); }
  }

  function startEditing(row: Schedule) {
    if (row.active) {
      setError("Pause this schedule before changing its settings.");
      return;
    }
    setEditingId(row.id);
    setEditTitle(row.title);
    setEditDescription(row.description);
    setEditInterval(String(row.interval_days));
    setEditEndDate(row.end_date || "");
    setError(""); setNotice("");
  }

  async function saveSettings(event: FormEvent<HTMLFormElement>, row: Schedule) {
    event.preventDefault();
    if (row.active || editingId !== row.id) {
      setError("Pause this schedule before editing.");
      return;
    }
    setBusyId(row.id); setError(""); setNotice("");
    try {
      const updated = await apiPatch(
        `/api/maintenance/preventive/schedules/${row.id}/settings`, {
          title: editTitle.trim(), description: editDescription.trim(),
          interval_days: Number(editInterval),
          end_date: editEndDate || null,
        },
      ) as Schedule;
      if (updated.id !== row.id || updated.active)
        throw new Error("Unexpected schedule update response.");
      setSchedules((previous) => previous.map((item) => item.id === row.id ? updated : item));
      setBatchHealth((previous) => { const next = { ...previous }; delete next[row.id]; return next; });
      setShowBlockedOnly(false);
      setPreview((prior) => prior?.schedule_id === row.id ? null : prior);
      setEditingId(null);
      setNotice("Paused schedule settings updated and audited. Existing occurrences are unchanged.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Schedule edit failed.");
    } finally { setBusyId(null); }
  }

  async function generate(row: Schedule) {
    setBusyId(row.id); setError(""); setNotice("");
    try {
      const result = await apiPost(
        `/api/maintenance/preventive/schedules/${row.id}/generate`,
      ) as Generation;
      if (!Number.isSafeInteger(result.work_order_id) || result.tenant_id !== null)
        throw new Error("Unexpected preventive generation response.");
      const updated = await apiGet(
        `/api/maintenance/preventive/schedules/${row.id}`
      ) as Schedule;
      setSchedules((previous) => previous.map((item) => item.id === row.id ? updated : item));
      setBatchHealth((previous) => { const next = { ...previous }; delete next[row.id]; return next; });
      setShowBlockedOnly(false);
      setPreview((prior) => prior?.schedule_id === row.id ? null : prior);
      setNotice(result.newly_created
        ? `Work order #${result.work_order_id} generated without a tenant or automatic charge.`
        : `Due occurrence already exists as work order #${result.work_order_id}.`);
      if (historyId === row.id) await showHistory(row.id);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Cannot generate due occurrence.");
    } finally { setBusyId(null); }
  }

  async function showRecoveryReceipts(id:number) {
    setReceiptSchedule(id);setReceiptsBusy(true);setReceiptsError("");
    setRecoveryReceipts([]);
    try {
      const result = await apiGet(
        `/api/maintenance/preventive/schedules/${id}/recovery-receipts`,
      ) as RecoveryReceipt[];
      if (!Array.isArray(result) || result.some((entry)=>
        !Number.isSafeInteger(entry.root_work_order_id) ||
        !Array.isArray(entry.created_work_orders) ||
        entry.created_work_orders.some((work)=>!Number.isSafeInteger(work.work_order_id))))
        throw new Error("Invalid recovery evidence response.");
      setRecoveryReceipts(result);
    } catch (cause) {
      setReceiptsError(cause instanceof Error?cause.message:"Recovery receipts unavailable.");
    } finally {setReceiptsBusy(false);}
  }

  async function catchUp(event: FormEvent<HTMLFormElement>, row: Schedule) {
    event.preventDefault();
    if (recoveryId !== row.id || recoveryReason.trim().length < 10 || !recoveryCursor) {
      setError("Review original occurrence evidence and provide a recovery reason.");
      return;
    }
    setBusyId(row.id); setError(""); setNotice("");
    try {
      const result = await apiPost(
        `/api/maintenance/preventive/schedules/${row.id}/catch-up?limit=12`,
        { expected_next_due_date: recoveryCursor, reason: recoveryReason.trim() },
      ) as CatchUp;
      if (result.schedule_id !== row.id || !Array.isArray(result.created_work_order_ids) ||
          result.created_work_order_ids.length > 12 ||
          result.created_work_order_ids.some(id=>!Number.isSafeInteger(id)||id<1)) {
        throw new Error("Unexpected catch-up response.");
      }
      const updated = await apiGet(
        `/api/maintenance/preventive/schedules/${row.id}`
      ) as Schedule;
      setSchedules(old=>old.map(item=>item.id===row.id?updated:item));
      setBatchHealth(old=>{const next={...old};delete next[row.id];return next;});
      setShowBlockedOnly(false);
      setPreview(prior=>prior?.schedule_id===row.id?null:prior);
      setReconciliation(null);
      setRecoveryId(null); setRecoveryReason(""); setRecoveryCursor("");
      setNotice(result.created_work_order_ids.length
        ? `${result.created_work_order_ids.length} audited tenantless work orders created. ${result.remaining_due?"More backlog remains; review before repeating.":"No remaining due backlog."}`
        : "No further due work orders created. Existing occurrences remain unchanged.");
      if(historyId===row.id)await showHistory(row.id);
      if(result.created_work_order_ids.length) await showRecoveryReceipts(row.id);
    } catch (cause) {
      // A later occurrence may fail AFTER earlier work orders committed.
      // Never retain a reviewed cursor after any uncertain write result.
      setRecoveryId(null); setRecoveryReason(""); setRecoveryCursor("");
      setReconciliation(null);
      setPreview(null);
      setError((cause instanceof Error?cause.message:"Recovery failed.") +
        " Partial work may have been committed. Current history is refreshed below. Review original evidence again before retrying.");
      try {
        const current = await apiGet(
          `/api/maintenance/preventive/schedules/${row.id}`,
        ) as Schedule;
        if (current.id === row.id)
          setSchedules(old=>old.map(item=>item.id===row.id?current:item));
        await showHistory(row.id);
        await showRecoveryReceipts(row.id);
      } catch {
        // The primary error remains visible. We never guess a recovered cursor.
        setHistoryError("Could not refresh committed recovery evidence. Reload before retrying.");
      }
    } finally {setBusyId(null);}
  }

  async function inspectLoadedExecution() {
    if (!schedules.length || batchHealthLoading) return;
    setBatchHealthLoading(true); setBatchHealthError("");
    try {
      const combined: Record<number, ExecutionStatus> = {};
      for (let start = 0; start < schedules.length; start += 100) {
        const ids = schedules.slice(start, start + 100).map((row) => row.id);
        const rows = await apiPost("/api/maintenance/preventive/schedules/execution-health",
          { schedule_ids: ids }) as ExecutionStatus[];
        if (!Array.isArray(rows) || rows.length !== ids.length ||
            rows.some((row, index) => row.schedule_id !== ids[index])) {
          throw new Error("Unexpected schedule health response.");
        }
        for (const status of rows) combined[status.schedule_id] = status;
      }
      setBatchHealth(combined);
    } catch (cause) {
      setBatchHealth({});
      setShowBlockedOnly(false);
      setBatchHealthError(cause instanceof Error ? cause.message : "Execution health unavailable.");
    } finally { setBatchHealthLoading(false); }
  }

  async function inspectExecution(id: number) {
    setExecutionError(""); setExecutionErrorId(null);
    try {
      const result = await apiGet(
        `/api/maintenance/preventive/schedules/${id}/execution-status`,
      ) as ExecutionStatus;
      if (result.schedule_id !== id) throw new Error("Unexpected execution status.");
      setExecutionStatus(result);
    } catch (cause) {
      setExecutionStatus(null); setExecutionErrorId(id);
      setExecutionError(cause instanceof Error ? cause.message : "Execution status unavailable.");
    }
  }

  async function assumeExecution(event: FormEvent<HTMLFormElement>, row: Schedule) {
    event.preventDefault();
    if (takeoverId !== row.id || takeoverReason.trim().length < 10) {
      setError("Provide a reason with at least 10 characters.");
      return;
    }
    setBusyId(row.id); setError(""); setNotice("");
    try {
      const updated = await apiPost(
        `/api/maintenance/preventive/schedules/${row.id}/assume-execution`,
        { reason: takeoverReason.trim() },
      ) as Schedule;
      if (updated.id !== row.id) throw new Error("Unexpected transfer response.");
      setSchedules((old) => old.map((item) => item.id === row.id ? updated : item));
      setTakeoverId(null); setTakeoverReason("");
      setExecutionStatus(null);
      setBatchHealth((previous) => {
        const updated = { ...previous };
        delete updated[row.id];
        return updated;
      });
      setNotice("Schedule execution responsibility recorded. Original creator and past work orders are unchanged.");
      void inspectExecution(row.id);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not assume schedule execution.");
    } finally { setBusyId(null); }
  }

  async function showPreview(id: number) {
    setPreviewLoadingId(id); setPreviewError(""); setPreviewErrorId(null); setPreview(null);
    try {
      const result = await apiGet(
        `/api/maintenance/preventive/schedules/${id}/due-preview?limit=12`,
      ) as DuePreview;
      if (result.schedule_id !== id || !Array.isArray(result.due_dates)) {
        throw new Error("Unexpected due-preview response.");
      }
      setPreview(result);
    } catch (cause) {
      setPreviewErrorId(id);
      setPreviewError(cause instanceof Error ? cause.message : "Due preview unavailable.");
    } finally { setPreviewLoadingId(null); }
  }

  async function openRecovery(row: Schedule) {
    setBusyId(row.id); setError(""); setRecoveryId(null);
    try {
      const evidence = await apiGet(
        `/api/maintenance/preventive/schedules/${row.id}/reconciliation`,
      ) as Reconciliation;
      if (evidence.schedule_id !== row.id || evidence.integrity_status !== "VERIFIED" ||
          evidence.read_only !== true || evidence.financial_posted !== false ||
          evidence.automatic_dispatch !== false || !evidence.next_due_date) {
        throw new Error("Original occurrence evidence could not be verified.");
      }
      setReconciliation(evidence);
      setRecoveryCursor(evidence.next_due_date);
      setRecoveryReason("");
      setRecoveryId(row.id);
    } catch (cause) {
      setError((cause instanceof Error ? cause.message : "Original history is not verified.") +
        " No work orders were requested. Review the discrepancy before retrying.");
    } finally { setBusyId(null); }
  }

  async function reviewOccurrenceIntegrity(id: number) {
    setReconcileBusyId(id); setReconcileError(""); setReconcileErrorId(null);
    setReconciliation(null);
    try {
      const result=await apiGet(
        `/api/maintenance/preventive/schedules/${id}/reconciliation`
      ) as Reconciliation;
      if(result.schedule_id!==id||result.integrity_status!=="VERIFIED"||
        result.read_only!==true||result.work_orders_created!==0||
        result.automatic_dispatch!==false||result.financial_posted!==false||
        !Number.isSafeInteger(result.verified_occurrences))
        throw new Error("Schedule reconciliation response failed integrity checks.");
      setReconciliation(result);
    } catch(cause) {
      setReconcileErrorId(id);
      setReconcileError(cause instanceof Error?cause.message:
        "Occurrence reconciliation failed. Contact an administrator before recovery.");
    } finally {setReconcileBusyId(null);}
  }

  async function showHistory(id: number) {
    setHistoryId(id); setHistoryError(""); setHistoryMoreError("");
    try {
      const rows = await apiGet(`/api/maintenance/preventive/schedules/${id}/occurrences?limit=100`) as Occurrence[];
      if (!Array.isArray(rows)) throw new Error("Unexpected occurrence history.");
      setOccurrences(rows);
      setHistoryOffset(rows.length);
      setHistoryHasMore(rows.length === 100);
    } catch (cause) {
      setOccurrences([]);
      setHistoryHasMore(false);
      setHistoryError(cause instanceof Error ? cause.message : "Occurrence history unavailable.");
    }
  }

  async function loadOlderHistory(id: number) {
    if (historyLoadingMore || !historyHasMore || historyId !== id) return;
    setHistoryLoadingMore(true); setHistoryMoreError("");
    try {
      const rows = await apiGet(
        `/api/maintenance/preventive/schedules/${id}/occurrences?limit=100&offset=${historyOffset}`
      ) as Occurrence[];
      if (!Array.isArray(rows)) throw new Error("Unexpected occurrence response.");
      setOccurrences((old) => {
        const seen = new Set(old.map((row) => row.id));
        return [...old, ...rows.filter((row) => !seen.has(row.id))];
      });
      setHistoryOffset((previous) => previous + rows.length);
      setHistoryHasMore(rows.length === 100);
    } catch (cause) {
      setHistoryMoreError(cause instanceof Error ? cause.message : "Older occurrences unavailable.");
    } finally { setHistoryLoadingMore(false); }
  }

  const unitLabel = (unit: UnitChoice) => `${unit.property_name} · Unit ${unit.unit_number}`;
  return <main className="mx-auto max-w-5xl space-y-5">
    <Link href="/dashboard/maintenance/work-orders" className="text-sm text-blue-800 hover:underline">
      Back to maintenance work orders
    </Link>
    <header>
      <h1 className="text-2xl font-semibold">Preventive maintenance schedules</h1>
      <p className="mt-1 text-sm text-slate-600">
        Active schedules are checked daily for due work orders. Staff can also generate a due order
        manually. No automatic dispatch, entry authorization, or tenant charge occurs.
      </p>
    </header>
    {error && <p role="alert" className="rounded-lg border p-3 text-sm text-red-700">{error}</p>}
    {notice && <p role="status" className="rounded-lg border p-3 text-sm">{notice}</p>}
    <form onSubmit={(event) => void searchUnits(event)} className="rounded-xl border bg-white p-4">
      <label className="text-sm">Find an authorized unit
        <input value={unitSearch} maxLength={80} aria-label="Search preventive maintenance units"
          onChange={(event) => setUnitSearch(event.target.value)}
          className="mt-1 block w-full rounded-lg border p-2" />
      </label>
      <button disabled={unitsLoading} className="mt-2 rounded-lg border px-4 py-2 text-sm" type="submit">
        {unitsLoading ? "Searching…" : "Search units"}
      </button>
      {unitsError && <p role="alert" className="text-sm text-red-700">{unitsError}</p>}
    </form>
    <form onSubmit={(event) => void create(event)} className="space-y-3 rounded-xl border bg-white p-5">
      <h2 className="font-semibold">New preventive schedule</h2>
      <label className="block text-sm">Unit
        <select required value={unitId} aria-label="Preventive maintenance unit"
          disabled={unitsLoading || saving} onChange={(event) => setUnitId(event.target.value)}
          className="mt-1 w-full rounded-lg border p-2">
          <option value="">Choose an authorized unit</option>
          {units.map((unit) => <option key={unit.id} value={unit.id}>{unitLabel(unit)}</option>)}
        </select>
      </label>
      <label className="block text-sm">Task title
        <input required minLength={3} maxLength={255} value={title}
          aria-label="Preventive task title" onChange={(event) => setTitle(event.target.value)}
          className="mt-1 w-full rounded-lg border p-2" />
      </label>
      <label className="block text-sm">Instructions
        <textarea required minLength={10} maxLength={2000} rows={3} value={description}
          aria-label="Preventive task description"
          onChange={(event) => setDescription(event.target.value)}
          className="mt-1 w-full rounded-lg border p-2" />
      </label>
      <div className="grid gap-3 sm:grid-cols-2">
        <label className="block text-sm">Repeat every (days)
          <input type="number" min={1} max={3650} required value={interval}
            aria-label="Preventive schedule interval"
            onChange={(event) => setInterval(event.target.value)}
            className="mt-1 w-full rounded-lg border p-2" />
        </label>
        <label className="block text-sm">First due date
          <input type="date" required value={dueDate}
            aria-label="Preventive first due date"
            onChange={(event) => setDueDate(event.target.value)}
            className="mt-1 w-full rounded-lg border p-2" />
        </label>
        <label className="block text-sm">End date (optional)
          <input type="date" value={endDate} min={dueDate || undefined}
            aria-label="Preventive schedule end date"
            onChange={(event) => setEndDate(event.target.value)}
            className="mt-1 w-full rounded-lg border p-2" />
        </label>
      </div>
      <button type="submit" disabled={saving || unitsLoading}
        className="rounded-lg bg-slate-900 px-4 py-2 text-sm text-white disabled:opacity-50">
        {saving ? "Saving…" : "Save schedule"}
      </button>
    </form>
    <section className="space-y-3 rounded-xl border bg-white p-5">
      <h2 className="font-semibold">Authorized schedules</h2>
      <button type="button" disabled={batchHealthLoading || !schedules.length} onClick={() => void inspectLoadedExecution()}
        className="rounded-lg border px-4 py-2 text-sm disabled:opacity-50">
        {batchHealthLoading ? "Checking loaded schedule health…" : "Check all loaded schedule health"}
      </button>
      {batchHealthError && <p role="alert" className="text-sm text-red-700">{batchHealthError}</p>}
      {Object.keys(batchHealth).length > 0 && <div className="flex flex-wrap items-center gap-3 text-sm" role="status">
        <span>{Object.values(batchHealth).filter((state) => state.status === "blocked").length} blocked of {Object.keys(batchHealth).length} checked schedules</span>
        <label className="flex items-center gap-2">
          <input type="checkbox" aria-label="Show blocked schedules only" checked={showBlockedOnly}
            onChange={(event) => setShowBlockedOnly(event.target.checked)} /> Show blocked only
        </label>
      </div>}
      <form onSubmit={(event) => void searchSchedules(event)} className="flex flex-wrap items-end gap-2">
        <label className="min-w-48 flex-1 text-sm">Find a schedule by title
          <input aria-label="Search preventive schedules" value={scheduleSearch} maxLength={100}
            onChange={(event) => setScheduleSearch(event.target.value)}
            className="mt-1 w-full rounded-lg border p-2" />
        </label>
        <label className="flex items-center gap-2 text-sm"><input type="checkbox" aria-label="Due preventive schedules only"
            checked={dueOnly} onChange={(event) => setDueOnly(event.target.checked)} /> Due now only</label>
        <button type="submit" disabled={searchingSchedules || loadingMore} className="rounded-lg border px-4 py-2 text-sm disabled:opacity-50">
          {searchingSchedules ? "Searching…" : "Search schedules"}
        </button>
      </form>
      {loading && <p>Loading schedules…</p>}
      {!loading && schedules.length === 0 && <p>No preventive schedules yet.</p>}
      {schedules.filter((row) => !showBlockedOnly || batchHealth[row.id]?.status === "blocked").map((row) => <article key={row.id} className="space-y-2 rounded-lg border p-4">
        <h3 className="font-medium">{row.title} · Schedule #{row.id}</h3>
        <p className="text-sm text-slate-600">
          Unit #{row.unit_id} · Every {row.interval_days} days · Next due {row.next_due_date}
          {row.end_date ? ` · Ends ${row.end_date}` : ""}
          {" · "}{row.active ? "Active" : "Paused"}
          {row.executor_user_id ? ` · Execution staff #${row.executor_user_id}` : " · Original creator executes"}
        </p>
        <p className="whitespace-pre-wrap text-sm">{row.description}</p>
        <div className="flex flex-wrap gap-2">
          <button disabled={busyId !== null} onClick={() => void toggle(row)}
            className="rounded-lg border px-3 py-2 text-sm disabled:opacity-50">
            {row.active ? "Pause" : "Resume"}
          </button>
          <button disabled={busyId !== null || !row.active} onClick={() => void generate(row)}
            className="rounded-lg border px-3 py-2 text-sm disabled:opacity-50">
            Generate due work order
          </button>
          <button type="button" disabled={busyId !== null || !row.active}
            onClick={() => void openRecovery(row)}
            className="rounded-lg border px-3 py-2 text-sm disabled:opacity-50">
            Recover due backlog (up to 12)
          </button>
          <button type="button" disabled={busyId !== null || row.active}
            onClick={() => startEditing(row)}
            className="rounded-lg border px-3 py-2 text-sm disabled:opacity-50">
            Edit paused schedule
          </button>
          <button type="button" disabled={busyId !== null || previewLoadingId !== null}
            onClick={() => void showPreview(row.id)}
            className="rounded-lg border px-3 py-2 text-sm disabled:opacity-50">
            {previewLoadingId === row.id ? "Checking due backlog…" : "Preview due backlog"}
          </button>
          <button type="button" disabled={busyId !== null}
            onClick={() => void inspectExecution(row.id)}
            className="rounded-lg border px-3 py-2 text-sm disabled:opacity-50">
            Check execution status
          </button>
          <button type="button" disabled={busyId !== null}
            onClick={() => { setTakeoverId(row.id); setTakeoverReason(""); }}
            className="rounded-lg border px-3 py-2 text-sm disabled:opacity-50">
            Take over schedule execution
          </button>
          <button type="button" disabled={busyId !== null||reconcileBusyId!==null}
            onClick={() => void reviewOccurrenceIntegrity(row.id)}
            className="rounded-lg border px-3 py-2 text-sm disabled:opacity-50">
            {reconcileBusyId===row.id?"Checking original occurrence evidence…":"Reconcile original occurrence evidence"}
          </button>
          <button disabled={busyId !== null} onClick={() => void showHistory(row.id)}
            className="rounded-lg border px-3 py-2 text-sm disabled:opacity-50">
            Occurrence history
          </button>
          <button type="button" disabled={busyId !== null || receiptsBusy}
            onClick={() => void showRecoveryReceipts(row.id)}
            className="rounded-lg border px-3 py-2 text-sm disabled:opacity-50">
            {receiptsBusy && receiptSchedule===row.id?"Loading recovery receipts…":"Recovery receipts"}
          </button>
        </div>
        {receiptSchedule===row.id&&<section aria-label="Verified committed recovery receipts"
          className="space-y-2 rounded border p-3 text-sm">
          <h4 className="font-semibold">Committed recovery receipts</h4>
          {receiptsError&&<p role="alert">Recovery receipts not verified: {receiptsError}</p>}
          {!receiptsError&&recoveryReceipts.length===0&&<p>No reviewed recovery batches recorded.</p>}
          {recoveryReceipts.map(batch=><div key={batch.root_work_order_id} className="space-y-1">
            <p>Recovery root work order #{batch.root_work_order_id};
              operator #{batch.operator_user_id}; reason: {batch.reason}</p>
            <ul>{batch.created_work_orders.map(item=><li key={item.work_order_id}>
              <Link href={`/dashboard/maintenance/work-orders/${item.work_order_id}`}
                className="text-blue-800 underline">Work order #{item.work_order_id}</Link>
              {" · Original due "}{item.due_date}
            </li>)}</ul>
          </div>)}
          <p>No provider delivery, automatic dispatch or financial posting is certified.</p>
        </section>}
        {recoveryId===row.id&&<form onSubmit={(event)=>void catchUp(event,row)}
          className="space-y-2 rounded border bg-slate-50 p-3">
          <h4 className="font-semibold text-sm">Reviewed backlog recovery</h4>
          <p className="text-sm">Original occurrences verified. Expected next due: {recoveryCursor}.
            Server rechecks complete original history and this cursor under lock.
            Up to 12 tenantless work orders may be created. No dispatch, entry permission or charges.
          </p>
          <label className="block text-sm">Recovery reason
            <textarea required minLength={10} maxLength={500}
              aria-label={`Recovery reason ${row.id}`} value={recoveryReason}
              onChange={(event)=>setRecoveryReason(event.target.value)}
              className="mt-1 w-full rounded-lg border p-2" />
          </label>
          <button type="submit" disabled={busyId!==null||recoveryReason.trim().length<10}
            className="rounded-lg bg-slate-900 px-3 py-2 text-sm text-white disabled:opacity-50">
            Confirm reviewed recovery
          </button>
          <button type="button" disabled={busyId!==null}
            onClick={()=>{setRecoveryId(null);setRecoveryReason("");setRecoveryCursor("");}}
            className="ml-2 rounded-lg border px-3 py-2 text-sm">Cancel recovery</button>
        </form>}
        {reconciliation?.schedule_id===row.id&&<div role="status"
          aria-label="Verified preventive original occurrence reconciliation"
          className="rounded border p-3 text-sm">
          Verified {reconciliation.verified_occurrences} original occurrences for schedule #{row.id}.
          {reconciliation.latest_due_date?" Latest due "+reconciliation.latest_due_date+" · Work order #"+reconciliation.latest_work_order_id:" No original work orders yet."}
          {" "}Next due {reconciliation.next_due_date}. Read-only check; no work order, dispatch or finance action.
        </div>}
        {reconcileErrorId===row.id&&reconcileError&&<p role="alert" className="text-sm text-red-700">
          Reconciliation not verified: {reconcileError}. Do not rely on filtered history for recovery.
        </p>}
        {batchHealth[row.id] && <p className="text-sm" aria-label={`Batch execution health ${row.id}`}>
          Execution health: {batchHealth[row.id].status}{batchHealth[row.id].due ? " · Due now" : ""}{batchHealth[row.id].status === "blocked" && batchHealth[row.id].block_reason ? ` · ${batchHealth[row.id].block_reason?.replaceAll("_", " ").toLowerCase()}` : ""}
        </p>}
        {executionStatus?.schedule_id === row.id && <p className="text-sm" role="status">
          Execution: {executionStatus.status} · Staff #{executionStatus.executor_user_id}
          {executionStatus.due ? " · Due now" : ""}
          {executionStatus.status === "blocked" ? " · Ask authorized staff to assume execution." : ""}
        </p>}
        {executionErrorId === row.id && executionError &&
          <p role="alert" className="text-sm text-red-700">{executionError}</p>}
        {takeoverId === row.id && <form
          onSubmit={(event) => void assumeExecution(event, row)}
          className="space-y-2 rounded-lg border bg-slate-50 p-3">
          <label className="block text-sm">Reason for execution responsibility transfer
            <textarea required minLength={10} maxLength={500}
              aria-label={`Execution transfer reason ${row.id}`}
              value={takeoverReason} onChange={(event) => setTakeoverReason(event.target.value)}
              className="mt-1 w-full rounded-lg border p-2" />
          </label>
          <p className="text-xs text-slate-600">
            Managers may recover unavailable execution staff. Administrators can transfer proactively.
            This does not change tenant entry permission or issue charges.
          </p>
          <button type="submit" disabled={busyId !== null}
            className="rounded-lg bg-slate-900 px-3 py-2 text-sm text-white disabled:opacity-50">
            Confirm execution takeover
          </button>
          <button type="button" disabled={busyId !== null}
            onClick={() => setTakeoverId(null)} className="ml-2 rounded-lg border px-3 py-2 text-sm">
            Cancel takeover
          </button>
        </form>}
        {editingId === row.id && !row.active && <form
          onSubmit={(event) => void saveSettings(event, row)}
          className="space-y-3 rounded-lg border bg-slate-50 p-4">
          <p className="text-sm font-semibold">Edit paused schedule #{row.id}</p>
          <label className="block text-sm">Task title
            <input required minLength={3} maxLength={255} value={editTitle}
              aria-label={`Edit preventive title ${row.id}`}
              onChange={(event) => setEditTitle(event.target.value)}
              className="mt-1 w-full rounded-lg border p-2" />
          </label>
          <label className="block text-sm">Instructions
            <textarea required minLength={10} maxLength={2000} value={editDescription}
              aria-label={`Edit preventive instructions ${row.id}`}
              onChange={(event) => setEditDescription(event.target.value)}
              className="mt-1 w-full rounded-lg border p-2" />
          </label>
          <label className="block text-sm">Repeat every (days)
            <input type="number" min={1} max={3650} required value={editInterval}
              aria-label={`Edit preventive interval ${row.id}`}
              onChange={(event) => setEditInterval(event.target.value)}
              className="mt-1 w-full rounded-lg border p-2" />
          </label>
          <label className="block text-sm">Stop after date (optional)
            <input type="date" value={editEndDate}
              aria-label={`Edit preventive end date ${row.id}`}
              onChange={(event) => setEditEndDate(event.target.value)}
              className="mt-1 w-full rounded-lg border p-2" />
          </label>
          <p className="text-xs text-slate-600">Next due date remains {row.next_due_date}.
            Previously generated work orders are never rewritten.</p>
          <div className="flex flex-wrap gap-2">
            <button type="submit" disabled={busyId !== null}
              className="rounded-lg bg-slate-900 px-4 py-2 text-sm text-white disabled:opacity-50">
              Save schedule changes
            </button>
            <button type="button" disabled={busyId !== null}
              onClick={() => setEditingId(null)} className="rounded-lg border px-4 py-2 text-sm">
              Cancel editing
            </button>
          </div>
        </form>}
        {preview?.schedule_id === row.id && <section className="space-y-2 rounded-lg border p-3 text-sm">
          <h4 className="font-semibold">Due backlog preview — no work orders created</h4>
          {!preview.active && <p>Schedule is paused; no due work will be generated.</p>}
          {preview.active && preview.due_dates.length === 0 && <p>No work is due as of {preview.as_of}.</p>}
          {preview.due_dates.length > 0 && <p>{preview.due_dates.join(", ")}</p>}
          {preview.has_more && <p role="status">More due dates exist beyond this bounded preview.</p>}
        </section>}
        {previewErrorId === row.id && previewError && <p role="alert" className="text-sm text-red-700">{previewError}</p>}
        {historyId === row.id && <div className="space-y-2 border-t pt-3">
          {historyError && <p role="alert" className="text-sm text-red-700">{historyError}</p>}
          {!historyError && occurrences.length === 0 && <p className="text-sm">No work orders generated yet.</p>}
          {occurrences.map((item) => <p key={item.id} className="text-sm">
            {item.due_date}: <Link href={`/dashboard/maintenance/work-orders/${item.work_order_id}`}
              className="text-blue-800 underline">Work order #{item.work_order_id}</Link>
          </p>)}
          {historyHasMore && <button type="button" disabled={historyLoadingMore}
            onClick={() => void loadOlderHistory(row.id)}
            className="rounded-lg border px-3 py-2 text-sm disabled:opacity-50">
            {historyLoadingMore ? "Loading older occurrences…" : "Load older occurrences"}
          </button>}
          {historyMoreError && <p role="alert" className="text-sm text-red-700">{historyMoreError}</p>}
        </div>}
      </article>)}
      <p className="text-sm text-gray-600" aria-live="polite">Showing {schedules.length} authorized preventive maintenance schedules{hasMore ? ". More schedules available." : "."}</p>
      {hasMore && <button type="button" disabled={loadingMore}
        onClick={() => void loadMore()}
        className="rounded-lg border px-4 py-2 text-sm disabled:opacity-50">
        {loadingMore ? "Loading older schedules…" : "Load older schedules"}
      </button>}
      {moreError && <p role="alert" className="text-sm text-red-700">{moreError}</p>}
    </section>
  </main>;
}
