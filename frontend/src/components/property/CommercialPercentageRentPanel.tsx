"use client";

import { useEffect, useState } from "react";
import { apiGet, apiPost } from "@/lib/api";

type GlOption = {
  id: number; gl_number: string; name: string; account_type: "ASSET" | "INCOME";
};
type Evidence = {
  id: number; filename: string; target_type: "properties" | "leases";
};
type Row = {
  id: number; reporting_year: number; gross_sales: string;
  breakpoint_annual: string; rate_percent: string; excess_sales: string;
  percentage_rent_due: string; charge_id: number | null;
  gl_transaction_id: number | null; reversal_transaction_id: number | null;
  status: "POSTED" | "ZERO" | "REVERSED"; reversal_on: string | null;
};

export default function CommercialPercentageRentPanel({
  propertyId, abstractId, canEdit,
}: {
  propertyId: number; abstractId: number; canEdit: boolean;
}) {
  const base = `/api/properties/${propertyId}/commercial-lease-abstracts/${abstractId}/percentage-rent`;
  const operatingBase = `/api/properties/${propertyId}/commercial-lease-abstracts/${abstractId}/operating-charges`;
  const [rows, setRows] = useState<Row[]>([]);
  const [evidence, setEvidence] = useState<Evidence[]>([]);
  const [accounts, setAccounts] = useState<GlOption[]>([]);
  const [year, setYear] = useState("");
  const [grossSales, setGrossSales] = useState("");
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
      apiGet(base) as Promise<Row[]>,
      apiGet(base + "/evidence-candidates") as Promise<Evidence[]>,
      apiGet(operatingBase + "/gl-options") as Promise<GlOption[]>,
    ]);
    setRows(saved); setEvidence(docs); setAccounts(gl);
  }

  useEffect(() => {
    let live = true;
    void Promise.all([
      apiGet(base) as Promise<Row[]>,
      apiGet(base + "/evidence-candidates") as Promise<Evidence[]>,
      apiGet(operatingBase + "/gl-options") as Promise<GlOption[]>,
    ]).then(([saved, docs, gl]) => {
      if (!live) return;
      setRows(saved); setEvidence(docs); setAccounts(gl);
    }).catch((cause) => {
      if (live) setError(cause instanceof Error ? cause.message : "Percentage rent unavailable.");
    });
    return () => { live = false; };
  }, [base, operatingBase]);

  async function save(event: React.FormEvent) {
    event.preventDefault();
    if (!canEdit || busy) return;
    setBusy(true); setError(""); setMessage("");
    try {
      await apiPost(base, {
        reporting_year: Number(year),
        evidence_attachment_id: Number(evidenceId),
        gross_sales: grossSales,
        posting_on: postingOn,
        due_on: dueOn,
        receivable_gl_account_id: Number(receivable),
        income_gl_account_id: Number(income),
        request_key: requestKey.trim(),
      });
      await reload();
      setRequestKey("");
      setMessage("Percentage rent calculated from the current authorized terms and private sales evidence.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to record percentage rent.");
    } finally { setBusy(false); }
  }

  async function reverse(row: Row) {
    const reversalOn = reverseDates[row.id] || "";
    const reason = (reverseReasons[row.id] || "").trim();
    if (!canEdit || !reversalOn || reason.length < 5 || busy) return;
    setBusy(true); setError(""); setMessage("");
    try {
      await apiPost(base + "/" + row.id + "/reverse", {
        reversal_on: reversalOn, reason,
      });
      await reload();
      setMessage("Percentage-rent posting reversed.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to reverse percentage rent.");
    } finally { setBusy(false); }
  }

  const receivables = accounts.filter((row) => row.account_type === "ASSET");
  const incomes = accounts.filter((row) => row.account_type === "INCOME");

  return (
    <section className="space-y-3 rounded border bg-slate-50 p-3">
      <h4 className="font-medium text-slate-900">Percentage rent</h4>
      <p className="text-xs text-slate-600">
        Uses private tenant-sales evidence and the current internally authorized percentage-rate
        and annual breakpoint. Only sales above the recorded breakpoint are charged. This does not
        certify the sales evidence or lease interpretation.
      </p>
      {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
      {message && <p role="status" className="text-sm text-green-700">{message}</p>}
      {rows.map((row) => (
        <div key={row.id} className="space-y-1 rounded border bg-white p-2 text-xs">
          <div className="font-medium">{row.reporting_year} · {row.status}</div>
          <div>Gross sales {row.gross_sales} · Breakpoint {row.breakpoint_annual} · Rate {row.rate_percent}%</div>
          <div>Excess sales {row.excess_sales} · Percentage rent due {row.percentage_rent_due}</div>
          {canEdit && row.status === "POSTED" && <div className="flex flex-wrap gap-2">
            <label>Percentage rent reversal date {row.id}
              <input aria-label={`Percentage rent reversal date ${row.id}`} type="date"
                value={reverseDates[row.id] || ""}
                onChange={(e) => setReverseDates((prior) => ({ ...prior, [row.id]: e.target.value }))}
                className="ml-2 rounded border p-1" />
            </label>
            <label>Percentage rent reversal reason {row.id}
              <input aria-label={`Percentage rent reversal reason ${row.id}`}
                value={reverseReasons[row.id] || ""}
                onChange={(e) => setReverseReasons((prior) => ({ ...prior, [row.id]: e.target.value }))}
                className="ml-2 rounded border p-1" />
            </label>
            <button type="button" disabled={busy}
              onClick={() => { void reverse(row); }}
              className="text-red-700 disabled:opacity-50">Reverse percentage rent</button>
          </div>}
        </div>
      ))}
      {canEdit && <form onSubmit={(event) => { void save(event); }} className="grid gap-2 md:grid-cols-2">
        <label className="text-xs">Percentage rent reporting year
          <input required type="number" min="2000" max="2200" value={year}
            onChange={(e) => setYear(e.target.value)} className="mt-1 block w-full rounded border p-2" />
        </label>
        <label className="text-xs">Tenant gross sales
          <input required type="number" min="0" step="0.01" value={grossSales}
            onChange={(e) => setGrossSales(e.target.value)} className="mt-1 block w-full rounded border p-2" />
        </label>
        <label className="text-xs">Private tenant-sales evidence
          <select required value={evidenceId} onChange={(e) => setEvidenceId(e.target.value)}
            className="mt-1 block w-full rounded border p-2">
            <option value="">Select private evidence</option>
            {evidence.map((row) =>
              <option key={row.id} value={row.id}>{row.filename} · {row.target_type}</option>)}
          </select>
        </label>
        <label className="text-xs">Percentage-rent request key
          <input required minLength={8} value={requestKey}
            onChange={(e) => setRequestKey(e.target.value)} className="mt-1 block w-full rounded border p-2" />
        </label>
        <label className="text-xs">Percentage-rent posting date
          <input required type="date" value={postingOn}
            onChange={(e) => setPostingOn(e.target.value)} className="mt-1 block w-full rounded border p-2" />
        </label>
        <label className="text-xs">Percentage-rent due date
          <input required type="date" value={dueOn}
            onChange={(e) => setDueOn(e.target.value)} className="mt-1 block w-full rounded border p-2" />
        </label>
        <label className="text-xs">Percentage-rent receivable GL
          <select required value={receivable} onChange={(e) => setReceivable(e.target.value)}
            className="mt-1 block w-full rounded border p-2">
            <option value="">Select receivable</option>
            {receivables.map((row) =>
              <option key={row.id} value={row.id}>{row.gl_number} · {row.name}</option>)}
          </select>
        </label>
        <label className="text-xs">Percentage-rent income GL
          <select required value={income} onChange={(e) => setIncome(e.target.value)}
            className="mt-1 block w-full rounded border p-2">
            <option value="">Select income</option>
            {incomes.map((row) =>
              <option key={row.id} value={row.id}>{row.gl_number} · {row.name}</option>)}
          </select>
        </label>
        <button type="submit" disabled={busy}
          className="rounded bg-slate-900 px-3 py-2 text-sm text-white disabled:opacity-50">
          Record percentage rent
        </button>
      </form>}
    </section>
  );
}
