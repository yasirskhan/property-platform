"use client";

import { useEffect, useState } from "react";
import { apiGet, apiPost } from "@/lib/api";

type Evidence = {
  id: number; filename: string; target_type: "properties" | "leases";
};
type Summary = {
  allowance_total: string; used_active: string; remaining: string; terms_id: number;
};
type Row = {
  id: number; incurred_on: string; amount: string; allowance_total: string;
  remaining_after: string; note: string; status: "ACTIVE" | "VOIDED";
  voided_on: string | null; void_reason: string | null;
};

export default function CommercialTIAllowancePanel({
  propertyId, abstractId, canEdit,
}: {
  propertyId: number; abstractId: number; canEdit: boolean;
}) {
  const base = `/api/properties/${propertyId}/commercial-lease-abstracts/${abstractId}/ti-allowance`;
  const [rows, setRows] = useState<Row[]>([]);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [evidence, setEvidence] = useState<Evidence[]>([]);
  const [evidenceId, setEvidenceId] = useState("");
  const [incurredOn, setIncurredOn] = useState("");
  const [amount, setAmount] = useState("");
  const [note, setNote] = useState("");
  const [requestKey, setRequestKey] = useState("");
  const [voidDates, setVoidDates] = useState<Record<number, string>>({});
  const [voidReasons, setVoidReasons] = useState<Record<number, string>>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  async function reload() {
    const [saved, totals, docs] = await Promise.all([
      apiGet(base) as Promise<Row[]>,
      apiGet(base + "/summary") as Promise<Summary>,
      apiGet(base + "/evidence-candidates") as Promise<Evidence[]>,
    ]);
    setRows(saved); setSummary(totals); setEvidence(docs);
  }

  useEffect(() => {
    let live = true;
    void Promise.all([
      apiGet(base) as Promise<Row[]>,
      apiGet(base + "/summary") as Promise<Summary>,
      apiGet(base + "/evidence-candidates") as Promise<Evidence[]>,
    ]).then(([saved, totals, docs]) => {
      if (!live) return;
      setRows(saved); setSummary(totals); setEvidence(docs);
    }).catch((cause) => {
      if (live) setError(cause instanceof Error ? cause.message : "TI allowance unavailable.");
    });
    return () => { live = false; };
  }, [base]);

  async function save(event: React.FormEvent) {
    event.preventDefault();
    if (!canEdit || busy) return;
    setBusy(true); setError(""); setMessage("");
    try {
      await apiPost(base, {
        evidence_attachment_id: Number(evidenceId),
        incurred_on: incurredOn,
        amount,
        note: note.trim(),
        request_key: requestKey.trim(),
      });
      await reload();
      setRequestKey("");
      setMessage("TI allowance utilization recorded. No payout, bank movement, or GL entry was created.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to record TI utilization.");
    } finally { setBusy(false); }
  }

  async function voidRow(row: Row) {
    const voidedOn = voidDates[row.id] || "";
    const reason = (voidReasons[row.id] || "").trim();
    if (!canEdit || !voidedOn || reason.length < 5 || busy) return;
    setBusy(true); setError(""); setMessage("");
    try {
      await apiPost(base + "/" + row.id + "/void", { voided_on: voidedOn, reason });
      await reload();
      setMessage("TI utilization record voided. No financial posting was reversed because none was created.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to void TI utilization.");
    } finally { setBusy(false); }
  }

  return (
    <section className="space-y-3 rounded border bg-slate-50 p-3">
      <h4 className="font-medium text-slate-900">TI allowance tracking</h4>
      <p className="text-xs text-slate-600">
        Tracks private-evidence utilization against the current internally authorized TI allowance.
        This is not a reimbursement, payment instruction, bank movement, or GL posting.
      </p>
      {summary && <p className="text-sm">
        Allowance {summary.allowance_total} · Active utilization {summary.used_active} · Remaining {summary.remaining}
      </p>}
      {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
      {message && <p role="status" className="text-sm text-green-700">{message}</p>}
      {rows.map((row) => (
        <div key={row.id} className="space-y-1 rounded border bg-white p-2 text-xs">
          <div className="font-medium">{row.incurred_on} · {row.status}</div>
          <div>Amount {row.amount} · Remaining after record {row.remaining_after}</div>
          <div>{row.note}</div>
          {canEdit && row.status === "ACTIVE" && <div className="flex flex-wrap gap-2">
            <label>TI void date {row.id}
              <input aria-label={`TI void date ${row.id}`} type="date"
                value={voidDates[row.id] || ""}
                onChange={(e) => setVoidDates((prior) => ({ ...prior, [row.id]: e.target.value }))}
                className="ml-2 rounded border p-1" />
            </label>
            <label>TI void reason {row.id}
              <input aria-label={`TI void reason ${row.id}`}
                value={voidReasons[row.id] || ""}
                onChange={(e) => setVoidReasons((prior) => ({ ...prior, [row.id]: e.target.value }))}
                className="ml-2 rounded border p-1" />
            </label>
            <button type="button" disabled={busy}
              onClick={() => { void voidRow(row); }}
              className="text-red-700 disabled:opacity-50">Void TI utilization</button>
          </div>}
        </div>
      ))}
      {canEdit && <form onSubmit={(event) => { void save(event); }} className="grid gap-2 md:grid-cols-2">
        <label className="text-xs">TI incurred date
          <input required type="date" value={incurredOn}
            onChange={(e) => setIncurredOn(e.target.value)} className="mt-1 block w-full rounded border p-2" />
        </label>
        <label className="text-xs">TI utilization amount
          <input required type="number" min="0.01" step="0.01" value={amount}
            onChange={(e) => setAmount(e.target.value)} className="mt-1 block w-full rounded border p-2" />
        </label>
        <label className="text-xs">Private TI evidence
          <select required value={evidenceId} onChange={(e) => setEvidenceId(e.target.value)}
            className="mt-1 block w-full rounded border p-2">
            <option value="">Select private evidence</option>
            {evidence.map((row) =>
              <option key={row.id} value={row.id}>{row.filename} · {row.target_type}</option>)}
          </select>
        </label>
        <label className="text-xs">TI request key
          <input required minLength={8} value={requestKey}
            onChange={(e) => setRequestKey(e.target.value)} className="mt-1 block w-full rounded border p-2" />
        </label>
        <label className="text-xs md:col-span-2">TI utilization note
          <textarea required minLength={5} value={note}
            onChange={(e) => setNote(e.target.value)} className="mt-1 block w-full rounded border p-2" rows={2} />
        </label>
        <button type="submit" disabled={busy}
          className="rounded bg-slate-900 px-3 py-2 text-sm text-white disabled:opacity-50">
          Record TI utilization
        </button>
      </form>}
    </section>
  );
}
