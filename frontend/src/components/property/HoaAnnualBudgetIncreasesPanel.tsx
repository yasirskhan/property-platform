"use client";
import { useEffect, useState } from "react";
import { apiGet, apiPost } from "@/lib/api";

type Source = {
  charge_id: number; member_user_id: number; proposal_id: number;
  previous_amount: string; frequency: string;
};
type Increase = {
  id: number; budget_id: number; source_charge_id: number;
  proposal_id: number; member_user_id: number; previous_amount: string;
  proposed_amount: string; effective_on: string;
  new_board_decision_required: true; new_member_charge_posted: false;
};

export default function HoaAnnualBudgetIncreasesPanel({
  associationId, propertyId, budgetId, budgetYear, onClose,
}: {
  associationId: number; propertyId: number; budgetId: number;
  budgetYear: number; onClose: () => void;
}) {
  const base = "/api/hoa/associations/" + associationId +
    "/annual-budgets/" + budgetId;
  const query = "?property_id=" + propertyId;
  const [sources, setSources] = useState<Source[]>([]);
  const [increases, setIncreases] = useState<Increase[]>([]);
  const [sourceId, setSourceId] = useState("");
  const [title, setTitle] = useState("");
  const [amount, setAmount] = useState("");
  const [start, setStart] = useState(String(budgetYear) + "-01-01");
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);

  async function reload() {
    const [eligible, existing] = await Promise.all([
      apiGet(base + "/increase-sources" + query) as Promise<Source[]>,
      apiGet(base + "/increases" + query) as Promise<Increase[]>,
    ]);
    setSources(eligible); setIncreases(existing);
  }

  useEffect(() => {
    let live = true;
    void Promise.all([
      apiGet(base + "/increase-sources" + query) as Promise<Source[]>,
      apiGet(base + "/increases" + query) as Promise<Increase[]>,
    ]).then(([eligible, existing]) => {
      if (live) { setSources(eligible); setIncreases(existing); }
    }).catch(cause => {
      if (live) setError(cause instanceof Error ? cause.message : "Increase source unavailable.");
    }).finally(() => { if (live) setLoading(false); });
    return () => { live = false; };
  }, [base, query]);

  async function create(event: React.FormEvent) {
    event.preventDefault();
    if (busy || !sourceId || !title.trim() || !amount || !start) return;
    if (!window.confirm("Create a new assessment INCREASE proposal? A separate authorized board decision and member issuance are still required.")) return;
    setBusy(true); setError(""); setMessage("");
    try {
      const result = await apiPost(base + "/increases", {
        property_id: propertyId, source_charge_id: Number(sourceId),
        title: title.trim(), proposed_amount: amount, effective_on: start,
      }) as Increase;
      await reload();
      setMessage("Increase proposal #" + result.proposal_id +
        " created. Go to Draft assessments and record a separate authorized board decision before any member posting.");
      setSourceId(""); setTitle(""); setAmount("");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Cannot prepare increase.");
    } finally { setBusy(false); }
  }

  const available = sources.filter(item => !increases.some(i => i.source_charge_id === item.charge_id));
  return <section className="w-full space-y-2 rounded border border-teal-200 bg-white p-3">
    <div className="flex items-center justify-between">
      <h5 className="font-semibold">Annual budget-linked member increases</h5>
      <button type="button" onClick={onClose} className="text-blue-700">Close increases</button>
    </div>
    <p>An approved budget can support a new proposal, but does not approve the
      member increase. The previous issued recurring member assessment supplies
      the verified payer reference. A new association board decision, planning
      occurrence and accountant GL posting remain separate mandatory actions.</p>
    {error && <p role="alert" className="text-red-700">{error}</p>}
    {message && <p role="status" className="text-green-700">{message}</p>}
    {loading && <p>Loading eligible issued member assessments…</p>}
    {!loading && available.length === 0 && <p>No unlinked prior recurring member assessments available.</p>}
    {available.length > 0 && <form className="space-y-2" onSubmit={(event) => { void create(event); }}>
      <label className="block">Previously issued member assessment
        <select aria-label="Increase prior assessment" value={sourceId}
          onChange={e => setSourceId(e.target.value)} className="mt-1 block w-full rounded border p-2" required>
          <option value="">Choose existing posted assessment</option>
          {available.map(p => <option key={p.charge_id} value={p.charge_id}>
            Member #{p.member_user_id} · Issued assessment #{p.charge_id}
            {" · $"}{p.previous_amount} · {p.frequency}
          </option>)}
        </select>
      </label>
      <label className="block">Increase proposal title
        <input aria-label="Increase proposal title" required minLength={3}
          maxLength={120} value={title} onChange={e => setTitle(e.target.value)}
          className="mt-1 block w-full rounded border p-2"/>
      </label>
      <label className="block">New recurring assessment amount
        <input aria-label="Increase amount" type="number" min="0.01" step="0.01"
          required value={amount} onChange={e => setAmount(e.target.value)}
          className="mt-1 block rounded border p-2"/>
      </label>
      <label className="block">First assessment date in budget year
        <input aria-label="Increase first assessment date" type="date" required
          min={budgetYear + "-01-01"} max={budgetYear + "-12-31"}
          value={start} onChange={e => setStart(e.target.value)}
          className="mt-1 block rounded border p-2"/>
      </label>
      <button type="submit" disabled={busy || !sourceId || !title.trim() || !amount || !start}
        className="rounded bg-teal-900 px-3 py-2 text-white disabled:opacity-50">
        Create increase proposal</button>
    </form>}
    {increases.map(item => <p key={item.id} className="rounded border p-2">
      Previous assessment #{item.source_charge_id} · Member #{item.member_user_id}
      {" · $"}{item.previous_amount} → {"$"}{item.proposed_amount}
      {" · "}New proposal #{item.proposal_id} from {item.effective_on}.
      Separate board decision and member ledger posting required.</p>)}
  </section>;
}
