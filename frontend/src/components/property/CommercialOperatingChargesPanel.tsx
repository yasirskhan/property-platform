"use client";

import { useEffect, useState } from "react";
import { apiGet, apiPost } from "@/lib/api";

type GlOption = {
  id: number; gl_number: string; name: string; account_type: "ASSET" | "INCOME";
};
type OperatingCharge = {
  id: number; kind: "CAM" | "NNN"; period_start: string; period_end: string;
  posting_on: string; due_on: string; cam_amount: string; tax_amount: string;
  insurance_amount: string; total_amount: string; charge_id: number;
  gl_transaction_id: number; reversal_transaction_id: number | null;
  status: "POSTED" | "REVERSED"; reversal_on: string | null;
  reversal_reason: string | null;
};

export default function CommercialOperatingChargesPanel({
  propertyId, abstractId, canEdit,
}: {
  propertyId: number; abstractId: number; canEdit: boolean;
}) {
  const base = `/api/properties/${propertyId}/commercial-lease-abstracts/${abstractId}/operating-charges`;
  const [rows, setRows] = useState<OperatingCharge[]>([]);
  const [accounts, setAccounts] = useState<GlOption[]>([]);
  const [kind, setKind] = useState<"CAM" | "NNN">("CAM");
  const [periodStart, setPeriodStart] = useState("");
  const [periodEnd, setPeriodEnd] = useState("");
  const [postingOn, setPostingOn] = useState("");
  const [dueOn, setDueOn] = useState("");
  const [receivable, setReceivable] = useState("");
  const [income, setIncome] = useState("");
  const [requestKey, setRequestKey] = useState("");
  const [reverseDates, setReverseDates] = useState<Record<number, string>>({});
  const [reverseReasons, setReverseReasons] = useState<Record<number, string>>({});
  const [busy, setBusy] = useState(false);
  const [available, setAvailable] = useState(true);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  async function reload() {
    try {
      const [saved, gl] = await Promise.all([
        apiGet(base) as Promise<OperatingCharge[]>,
        apiGet(base + "/gl-options") as Promise<GlOption[]>,
      ]);
      setRows(saved); setAccounts(gl); setAvailable(true);
    } catch (cause) {
      const text = cause instanceof Error ? cause.message : "Commercial operating charges unavailable.";
      if (/not authorized for billing|must be active/i.test(text)) {
        setAvailable(false); setRows([]); setAccounts([]);
      } else {
        setError(text);
      }
    }
  }

  useEffect(() => {
    let live = true;
    void Promise.all([
      apiGet(base) as Promise<OperatingCharge[]>,
      apiGet(base + "/gl-options") as Promise<GlOption[]>,
    ]).then(([saved, gl]) => {
      if (!live) return;
      setRows(saved); setAccounts(gl); setAvailable(true);
    }).catch((cause) => {
      if (!live) return;
      const text = cause instanceof Error ? cause.message : "Commercial operating charges unavailable.";
      if (/not authorized for billing|must be active/i.test(text)) setAvailable(false);
      else setError(text);
    });
    return () => { live = false; };
  }, [base]);

  async function issue(event: React.FormEvent) {
    event.preventDefault();
    if (!canEdit || busy) return;
    setBusy(true); setError(""); setMessage("");
    try {
      await apiPost(base, {
        kind, period_start: periodStart, period_end: periodEnd,
        posting_on: postingOn, due_on: dueOn,
        receivable_gl_account_id: Number(receivable),
        income_gl_account_id: Number(income),
        request_key: requestKey.trim(),
      });
      await reload();
      setRequestKey("");
      setMessage(`${kind} tenant charge posted through central accounting.`);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to post Commercial operating charge.");
    } finally { setBusy(false); }
  }

  async function reverse(row: OperatingCharge) {
    if (!canEdit || busy) return;
    const reversalOn = reverseDates[row.id] || "";
    const reason = (reverseReasons[row.id] || "").trim();
    if (!reversalOn || reason.length < 5) return;
    setBusy(true); setError(""); setMessage("");
    try {
      await apiPost(base + "/" + row.id + "/reverse", {
        reversal_on: reversalOn, reason,
      });
      await reload();
      setMessage(`${row.kind} charge reversed through central accounting.`);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to reverse Commercial operating charge.");
    } finally { setBusy(false); }
  }

  const receivables = accounts.filter((row) => row.account_type === "ASSET");
  const incomes = accounts.filter((row) => row.account_type === "INCOME");

  return (
    <section className="space-y-3 rounded border bg-slate-50 p-3">
      <h4 className="font-medium text-slate-900">Commercial CAM / NNN charges</h4>
      <p className="text-xs text-slate-600">
        Uses only the current internally authorized source-linked terms. Each posting creates a tenant charge
        and balanced central-GL receivable/income transaction. NNN uses the recorded CAM + tax + insurance
        monthly estimates. Reversals are preserved as separate GL transactions.
      </p>
      {!available && <p className="text-sm text-amber-700">
        Authorize the current Commercial terms for billing before posting CAM or NNN.
      </p>}
      {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
      {message && <p role="status" className="text-sm text-green-700">{message}</p>}
      {rows.map((row) => (
        <div key={row.id} className="space-y-1 rounded border bg-white p-2 text-xs">
          <div className="font-medium">{row.kind} · {row.status} · {row.period_start} to {row.period_end}</div>
          <div>CAM {row.cam_amount} · Tax {row.tax_amount} · Insurance {row.insurance_amount} · Total {row.total_amount}</div>
          <div>Tenant charge #{row.charge_id} · GL #{row.gl_transaction_id}</div>
          {row.reversal_transaction_id && <div>Reversal GL #{row.reversal_transaction_id} · {row.reversal_on}</div>}
          {canEdit && row.status === "POSTED" && <div className="flex flex-wrap items-end gap-2 pt-1">
            <label>Reversal date
              <input aria-label={`Reversal date ${row.id}`} type="date"
                value={reverseDates[row.id] || ""}
                onChange={(e) => setReverseDates((prior) => ({ ...prior, [row.id]: e.target.value }))}
                className="mt-1 block rounded border p-2" />
            </label>
            <label>Reversal reason
              <input aria-label={`Reversal reason ${row.id}`}
                value={reverseReasons[row.id] || ""}
                onChange={(e) => setReverseReasons((prior) => ({ ...prior, [row.id]: e.target.value }))}
                className="mt-1 block rounded border p-2" />
            </label>
            <button type="button" disabled={busy || !(reverseDates[row.id]) || (reverseReasons[row.id] || "").trim().length < 5}
              onClick={() => { void reverse(row); }}
              className="rounded border px-3 py-2 text-red-700 disabled:opacity-50">
              Reverse Commercial charge
            </button>
          </div>}
        </div>
      ))}
      {canEdit && available && <form onSubmit={(event) => { void issue(event); }} className="grid gap-2 md:grid-cols-2">
        <label className="text-xs">Charge type
          <select value={kind} onChange={(e) => setKind(e.target.value as "CAM" | "NNN")}
            className="mt-1 block w-full rounded border p-2">
            <option value="CAM">CAM</option>
            <option value="NNN">NNN</option>
          </select>
        </label>
        <label className="text-xs">Request key
          <input required minLength={8} value={requestKey} onChange={(e) => setRequestKey(e.target.value)}
            className="mt-1 block w-full rounded border p-2" placeholder="commercial-2026-03-cam" />
        </label>
        <label className="text-xs">Period start
          <input required type="date" value={periodStart} onChange={(e) => setPeriodStart(e.target.value)}
            className="mt-1 block w-full rounded border p-2" />
        </label>
        <label className="text-xs">Period end
          <input required type="date" value={periodEnd} onChange={(e) => setPeriodEnd(e.target.value)}
            className="mt-1 block w-full rounded border p-2" />
        </label>
        <label className="text-xs">Posting date
          <input required type="date" value={postingOn} onChange={(e) => setPostingOn(e.target.value)}
            className="mt-1 block w-full rounded border p-2" />
        </label>
        <label className="text-xs">Due date
          <input required type="date" value={dueOn} onChange={(e) => setDueOn(e.target.value)}
            className="mt-1 block w-full rounded border p-2" />
        </label>
        <label className="text-xs">Receivable GL
          <select required value={receivable} onChange={(e) => setReceivable(e.target.value)}
            className="mt-1 block w-full rounded border p-2">
            <option value="">Select receivable account</option>
            {receivables.map((row) => <option key={row.id} value={row.id}>{row.gl_number} · {row.name}</option>)}
          </select>
        </label>
        <label className="text-xs">Commercial income GL
          <select required value={income} onChange={(e) => setIncome(e.target.value)}
            className="mt-1 block w-full rounded border p-2">
            <option value="">Select income account</option>
            {incomes.map((row) => <option key={row.id} value={row.id}>{row.gl_number} · {row.name}</option>)}
          </select>
        </label>
        <button type="submit"
          disabled={busy || !requestKey.trim() || !periodStart || !periodEnd || !postingOn || !dueOn || !receivable || !income}
          className="rounded bg-slate-900 px-3 py-2 text-sm text-white disabled:opacity-50 md:col-span-2">
          {busy ? "Posting…" : "Post Commercial charge"}
        </button>
      </form>}
    </section>
  );
}
