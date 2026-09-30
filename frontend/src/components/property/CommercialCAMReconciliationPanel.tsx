"use client";

import { useEffect, useState } from "react";
import { apiGet, apiPost } from "@/lib/api";

type GlOption = { id: number; gl_number: string; name: string; account_type: "ASSET" | "INCOME" };
type Evidence = { id: number; filename: string; target_type: "properties" | "leases" };
type Reconciliation = {
  id: number; reconciliation_year: number; actual_cam_total: string;
  share_percent: string; actual_tenant_share: string; estimated_cam_billed: string;
  true_up_amount: string; charge_id: number | null; gl_transaction_id: number | null;
  reversal_transaction_id: number | null; status: "POSTED" | "ZERO" | "REVERSED";
  reversal_on: string | null;
};

export default function CommercialCAMReconciliationPanel({
  propertyId, abstractId, canEdit,
}: {
  propertyId: number; abstractId: number; canEdit: boolean;
}) {
  const base = `/api/properties/${propertyId}/commercial-lease-abstracts/${abstractId}/cam-reconciliations`;
  const operatingBase = `/api/properties/${propertyId}/commercial-lease-abstracts/${abstractId}/operating-charges`;
  const [rows, setRows] = useState<Reconciliation[]>([]);
  const [evidence, setEvidence] = useState<Evidence[]>([]);
  const [accounts, setAccounts] = useState<GlOption[]>([]);
  const [year, setYear] = useState("");
  const [actual, setActual] = useState("");
  const [evidenceId, setEvidenceId] = useState("");
  const [postingOn, setPostingOn] = useState("");
  const [dueOn, setDueOn] = useState("");
  const [receivable, setReceivable] = useState("");
  const [income, setIncome] = useState("");
  const [requestKey, setRequestKey] = useState("");
  const [reverseDates, setReverseDates] = useState<Record<number, string>>({});
  const [reverseReasons, setReverseReasons] = useState<Record<number, string>>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  async function reload() {
    const [saved, docs, gl] = await Promise.all([
      apiGet(base) as Promise<Reconciliation[]>,
      apiGet(base + "/evidence-candidates") as Promise<Evidence[]>,
      apiGet(operatingBase + "/gl-options") as Promise<GlOption[]>,
    ]);
    setRows(saved); setEvidence(docs); setAccounts(gl);
  }

  useEffect(() => {
    let live = true;
    void Promise.all([
      apiGet(base) as Promise<Reconciliation[]>,
      apiGet(base + "/evidence-candidates") as Promise<Evidence[]>,
      apiGet(operatingBase + "/gl-options") as Promise<GlOption[]>,
    ]).then(([saved, docs, gl]) => {
      if (!live) return;
      setRows(saved); setEvidence(docs); setAccounts(gl);
    }).catch((cause) => {
      if (live) setError(cause instanceof Error ? cause.message : "CAM reconciliation unavailable.");
    });
    return () => { live = false; };
  }, [base, operatingBase]);

  async function save(event: React.FormEvent) {
    event.preventDefault();
    if (!canEdit || busy) return;
    setBusy(true); setError(""); setMessage("");
    try {
      await apiPost(base, {
        reconciliation_year: Number(year),
        evidence_attachment_id: Number(evidenceId),
        actual_cam_total: actual,
        posting_on: postingOn, due_on: dueOn,
        receivable_gl_account_id: Number(receivable),
        income_gl_account_id: Number(income),
        request_key: requestKey.trim(),
      });
      await reload();
      setMessage("Annual CAM reconciliation recorded through central accounting.");
      setRequestKey("");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to record CAM reconciliation.");
    } finally { setBusy(false); }
  }

  async function reverse(row: Reconciliation) {
    const reversalOn = reverseDates[row.id] || "";
    const reason = (reverseReasons[row.id] || "").trim();
    if (!canEdit || !reversalOn || reason.length < 5 || busy) return;
    setBusy(true); setError(""); setMessage("");
    try {
      await apiPost(base + "/" + row.id + "/reverse", { reversal_on: reversalOn, reason });
      await reload();
      setMessage("CAM reconciliation posting reversed.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to reverse CAM reconciliation.");
    } finally { setBusy(false); }
  }

  const receivables = accounts.filter((row) => row.account_type === "ASSET");
  const incomes = accounts.filter((row) => row.account_type === "INCOME");

  return (
    <section className="space-y-3 rounded border bg-slate-50 p-3">
      <h4 className="font-medium text-slate-900">Annual CAM reconciliation</h4>
      <p className="text-xs text-slate-600">
        Compares private-evidence actual CAM to the current authorized CAM share and the CAM component
        already posted for the selected year. Positive true-ups create a tenant charge; negative true-ups
        reduce receivables through central GL. This does not certify the source document or lease interpretation.
      </p>
      {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
      {message && <p role="status" className="text-sm text-green-700">{message}</p>}
      {rows.map((row) => (
        <div key={row.id} className="space-y-1 rounded border bg-white p-2 text-xs">
          <div className="font-medium">{row.reconciliation_year} · {row.status}</div>
          <div>Actual CAM {row.actual_cam_total} · Share {row.share_percent}% · Tenant actual {row.actual_tenant_share}</div>
          <div>Estimated CAM billed {row.estimated_cam_billed} · True-up {row.true_up_amount}</div>
          {row.gl_transaction_id && <div>GL #{row.gl_transaction_id}{row.charge_id ? ` · Tenant charge #${row.charge_id}` : " · Tenant credit adjustment"}</div>}
          {row.reversal_transaction_id && <div>Reversal GL #{row.reversal_transaction_id}</div>}
          {canEdit && row.status === "POSTED" && <div className="flex flex-wrap items-end gap-2">
            <label>CAM reversal date
              <input aria-label={`CAM reversal date ${row.id}`} type="date"
                value={reverseDates[row.id] || ""}
                onChange={(e) => setReverseDates((prior) => ({ ...prior, [row.id]: e.target.value }))}
                className="mt-1 block rounded border p-2" />
            </label>
            <label>CAM reversal reason
              <input aria-label={`CAM reversal reason ${row.id}`}
                value={reverseReasons[row.id] || ""}
                onChange={(e) => setReverseReasons((prior) => ({ ...prior, [row.id]: e.target.value }))}
                className="mt-1 block rounded border p-2" />
            </label>
            <button type="button" disabled={busy || !reverseDates[row.id] || (reverseReasons[row.id] || "").trim().length < 5}
              onClick={() => { void reverse(row); }}
              className="rounded border px-3 py-2 text-red-700 disabled:opacity-50">
              Reverse CAM reconciliation
            </button>
          </div>}
        </div>
      ))}
      {canEdit && <form onSubmit={(event) => { void save(event); }} className="grid gap-2 md:grid-cols-2">
        <label className="text-xs">Reconciliation year
          <input required type="number" min="2000" max="2200" value={year} onChange={(e) => setYear(e.target.value)}
            className="mt-1 block w-full rounded border p-2" />
        </label>
        <label className="text-xs">Actual CAM total
          <input required type="number" min="0" step="0.01" value={actual} onChange={(e) => setActual(e.target.value)}
            className="mt-1 block w-full rounded border p-2" />
        </label>
        <label className="text-xs">Private CAM evidence
          <select required value={evidenceId} onChange={(e) => setEvidenceId(e.target.value)}
            className="mt-1 block w-full rounded border p-2">
            <option value="">Select evidence</option>
            {evidence.map((row) => <option key={row.id} value={row.id}>{row.filename} · {row.target_type}</option>)}
          </select>
        </label>
        <label className="text-xs">CAM reconciliation request key
          <input required minLength={8} value={requestKey} onChange={(e) => setRequestKey(e.target.value)}
            className="mt-1 block w-full rounded border p-2" />
        </label>
        <label className="text-xs">CAM reconciliation posting date
          <input required type="date" value={postingOn} onChange={(e) => setPostingOn(e.target.value)}
            className="mt-1 block w-full rounded border p-2" />
        </label>
        <label className="text-xs">CAM reconciliation due date
          <input required type="date" value={dueOn} onChange={(e) => setDueOn(e.target.value)}
            className="mt-1 block w-full rounded border p-2" />
        </label>
        <label className="text-xs">CAM receivable GL
          <select required value={receivable} onChange={(e) => setReceivable(e.target.value)}
            className="mt-1 block w-full rounded border p-2">
            <option value="">Select receivable account</option>
            {receivables.map((row) => <option key={row.id} value={row.id}>{row.gl_number} · {row.name}</option>)}
          </select>
        </label>
        <label className="text-xs">CAM income GL
          <select required value={income} onChange={(e) => setIncome(e.target.value)}
            className="mt-1 block w-full rounded border p-2">
            <option value="">Select income account</option>
            {incomes.map((row) => <option key={row.id} value={row.id}>{row.gl_number} · {row.name}</option>)}
          </select>
        </label>
        <button type="submit"
          disabled={busy || !year || !actual || !evidenceId || !postingOn || !dueOn || !receivable || !income || requestKey.trim().length < 8}
          className="rounded bg-slate-900 px-3 py-2 text-sm text-white disabled:opacity-50 md:col-span-2">
          {busy ? "Reconciling…" : "Record annual CAM reconciliation"}
        </button>
      </form>}
    </section>
  );
}
