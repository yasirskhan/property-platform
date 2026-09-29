"use client";

import { useEffect, useState } from "react";
import { apiGet, apiPost, apiPut } from "@/lib/api";
import HoaAnnualBudgetIncreasesPanel from "@/components/property/HoaAnnualBudgetIncreasesPanel";

type Account = {
  id: number; number: string; name: string;
  account_type: "INCOME" | "EXPENSE";
};
type BudgetLine = {
  gl_account_id: number; annual_amount: string;
  gl_number: string; gl_name: string;
  account_type: "INCOME" | "EXPENSE";
};
type Budget = {
  id: number; calendar_year: number; revision: number; version: number;
  description: string; lines: BudgetLine[];
  total_income: string; total_expense: string; reserve_allocation: string;
  status: "DRAFT" | "APPROVED" | "DENIED";
  board_seat_id: number | null; decision_method: "DIRECT" | "OFFLINE" | null;
  decided_on: string | null; decision_note: string | null;
  member_assessment_issued: false; reserve_cash_transferred: false;
};
type EditableLine = { gl_account_id: string; annual_amount: string };

export default function HoaAnnualBudgetsPanel({
  associationId, propertyId, canEdit, onClose,
}: {
  associationId: number; propertyId: number; canEdit: boolean;
  onClose: () => void;
}) {
  const base = "/api/hoa/associations/" + associationId + "/annual-budgets";
  const query = "?property_id=" + propertyId;
  const [budgets, setBudgets] = useState<Budget[]>([]);
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [year, setYear] = useState(String(new Date().getFullYear()));
  const [description, setDescription] = useState("");
  const [reserve, setReserve] = useState("0.00");
  const [lines, setLines] = useState<EditableLine[]>([]);
  const [account, setAccount] = useState("");
  const [amount, setAmount] = useState("");
  const [editing, setEditing] = useState<number | null>(null);
  const [decision, setDecision] = useState<"APPROVED" | "DENIED">("APPROVED");
  const [note, setNote] = useState("");
  const [deciding, setDeciding] = useState<number | null>(null);
  const [increasing, setIncreasing] = useState<number | null>(null);
  const [bookActuals, setBookActuals] = useState<number | null>(null);
  const [actuals, setActuals] = useState<Record<number, {lines: Array<{gl_account_id:number;gl_number:string;gl_name:string;annual_budget:string;actual_book:string;variance_actual_minus_budget:string}>; accounting_basis:string;association_allocation_verified:boolean}> >({});
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  async function refresh() {
    setBudgets(await apiGet(base + query) as Budget[]);
  }

  useEffect(() => {
    let alive = true;
    void Promise.all([
      apiGet(base + query) as Promise<Budget[]>,
      canEdit ? apiGet(base + "/accounts" + query) as Promise<Account[]> : Promise.resolve([]),
    ]).then(([rows, gl]) => {
      if (!alive) return;
      setBudgets(rows); setAccounts(gl);
    }).catch(cause => {
      if (alive) setError(cause instanceof Error ? cause.message : "Annual budgets unavailable.");
    }).finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
  }, [base, query, canEdit]);

  function addLine() {
    if (!account || !amount || Number(amount) <= 0) return;
    if (lines.some(line => line.gl_account_id === account)) {
      setError("Each GL account may appear only once in an annual budget.");
      return;
    }
    setLines(prior => [...prior, { gl_account_id: account, annual_amount: amount }]);
    setAccount(""); setAmount(""); setError("");
  }

  function openDraft(item: Budget) {
    setEditing(item.id); setYear(String(item.calendar_year));
    setDescription(item.description); setReserve(item.reserve_allocation);
    setLines(item.lines.map(line => ({
      gl_account_id: String(line.gl_account_id),
      annual_amount: line.annual_amount,
    })));
    setError(""); setMessage("");
  }

  async function save(event: React.FormEvent) {
    event.preventDefault();
    if (!canEdit || busy || lines.length === 0 || !description.trim()) return;
    setBusy(true); setError(""); setMessage("");
    const payload = {
      property_id: propertyId, calendar_year: Number(year),
      description: description.trim(), reserve_allocation: reserve,
      lines: lines.map(line => ({
        gl_account_id: Number(line.gl_account_id),
        annual_amount: line.annual_amount,
      })),
    };
    try {
      if (editing !== null) {
        const prior = budgets.find(b => b.id === editing);
        if (!prior) throw Error("Budget draft no longer available.");
        await apiPut(base + "/" + editing, { ...payload, expected_version: prior.version });
      } else {
        await apiPost(base, payload);
      }
      await refresh(); setEditing(null); setLines([]); setDescription(""); setReserve("0.00");
      setMessage("Association annual budget saved. No member charges or reserve transfers posted.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Cannot save annual budget.");
    } finally { setBusy(false); }
  }

  async function showActuals(item: Budget) {
    if (bookActuals === item.id) { setBookActuals(null); return; }
    setError("");
    try {
      const report = await apiGet(base + "/" + item.id + "/book-actuals" + query) as {lines: Array<{gl_account_id:number;gl_number:string;gl_name:string;annual_budget:string;actual_book:string;variance_actual_minus_budget:string}>; accounting_basis:string;association_allocation_verified:boolean};
      setActuals(prior => ({...prior, [item.id]: report}));
      setBookActuals(item.id);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Budget actuals unavailable.");
    }
  }

  async function decide(item: Budget) {
    if (!canEdit || busy || deciding !== item.id || note.trim().length < 3) return;
    if (!window.confirm("Record this association board decision? The annual budget becomes final.")) return;
    setBusy(true); setError(""); setMessage("");
    try {
      await apiPost(base + "/" + item.id + "/decision", {
        property_id: propertyId, expected_version: item.version,
        decision, decision_note: note.trim(),
      });
      await refresh(); setDeciding(null); setNote("");
      setMessage("Annual budget board decision recorded. No assessment or GL posting occurred.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Cannot record annual budget decision.");
    } finally { setBusy(false); }
  }

  return <section className="w-full space-y-3 rounded border border-teal-200 bg-teal-50 p-4 text-xs">
    <div className="flex items-center justify-between gap-2">
      <h3 className="font-semibold">HOA annual operating budgets</h3>
      <button type="button" onClick={onClose} className="text-blue-700">Close budgets</button>
    </div>
    <p>Separate association budget, not the general property budget. An authorized
      association board login can adopt or deny a budget. The planned reserve allocation
      is not an actual transfer. Approved budget figures do not automatically assess members.</p>
    {loading && <p>Loading annual budgets…</p>}
    {error && <p role="alert" className="text-red-700">{error}</p>}
    {message && <p role="status" className="text-green-800">{message}</p>}
    {canEdit && !loading && <form onSubmit={(event) => { void save(event); }}
      className="space-y-2 rounded border bg-white p-3">
      <h4 className="font-semibold">{editing !== null ? "Revise annual budget draft" : "Prepare annual association budget"}</h4>
      <label className="block">Budget calendar year
        <input type="number" min={2000} max={2100} required value={year}
          disabled={editing !== null} onChange={e => setYear(e.target.value)}
          className="mt-1 block rounded border p-2" />
      </label>
      <label className="block">Budget purpose
        <input required minLength={3} maxLength={300} value={description}
          onChange={e => setDescription(e.target.value)}
          className="mt-1 block w-full rounded border p-2" />
      </label>
      <label className="block">Planned reserve allocation (included in annual expenses)
        <input type="number" min="0" step="0.01" required value={reserve}
          onChange={e => setReserve(e.target.value)}
          className="mt-1 block rounded border p-2" />
      </label>
      <div className="rounded border p-2">
        <p className="font-medium">HOA-specific annual GL line items</p>
        <label className="block">Budget GL account
          <select aria-label="HOA annual budget GL account" value={account}
            onChange={e => setAccount(e.target.value)} className="mt-1 block w-full rounded border p-2">
            <option value="">Choose income or expense GL</option>
            {accounts.map(a => <option key={a.id} value={a.id}>{a.number} · {a.name} ({a.account_type})</option>)}
          </select>
        </label>
        <label className="block">Annual budget line amount
          <input type="number" min="0.01" step="0.01" value={amount}
            onChange={e => setAmount(e.target.value)} className="mt-1 block rounded border p-2" />
        </label>
        <button type="button" onClick={addLine} disabled={!account || !amount || busy}
          className="mt-2 text-blue-700 disabled:opacity-50">Add annual budget line</button>
        <ol className="mt-2 space-y-1">
          {lines.map((line, index) => <li key={line.gl_account_id}>
            {accounts.find(a => String(a.id) === line.gl_account_id)?.name || line.gl_account_id}
            {" · $"}{line.annual_amount}
            <button type="button" onClick={() => setLines(before => before.filter((_, i) => i !== index))}
              className="ml-2 text-red-700">Remove</button>
          </li>)}
        </ol>
      </div>
      <button type="submit" disabled={busy || lines.length === 0 || !description.trim()}
        className="rounded bg-teal-900 px-3 py-2 text-white disabled:opacity-50">
        {editing === null ? "Create association budget draft" : "Save revised budget"}
      </button>
      {editing !== null && <button type="button" onClick={() => {
        setEditing(null); setLines([]); setDescription(""); setReserve("0.00");
      }} className="ml-2 text-blue-700">Cancel editing</button>}
    </form>}
    {!loading && budgets.length === 0 && <p>No association annual budgets recorded.</p>}
    {budgets.map(item => <article key={item.id} className="space-y-2 rounded border bg-white p-3">
      <h4 className="font-semibold">{item.calendar_year} · Revision {item.revision} · {item.status}</h4>
      <p>{item.description}</p>
      <p>Income: {"$"+item.total_income} · Expenses: {"$"+item.total_expense}
        {" · "}Planned reserve allocation: {"$"+item.reserve_allocation}</p>
      <ol className="space-y-1">{item.lines.map(line => <li key={line.gl_account_id}>
        {line.gl_number} · {line.gl_name} · {line.account_type}: {"$"+line.annual_amount}
      </li>)}</ol>
      {item.status !== "DRAFT" && <p role="status">Association board decision: {item.status}
        {" · "}Recorded on {item.decided_on} · {item.decision_method}
        {" · "}{item.decision_note}</p>}
      {item.status === "APPROVED" && canEdit && <>
        <button type="button" className="text-blue-700" onClick={() => { void showActuals(item); }}>
          {bookActuals === item.id ? "Hide budget actuals" : "Posted GL budget actuals"}
        </button>
        {bookActuals === item.id && actuals[item.id] && <div className="space-y-1 rounded border p-2">
          <h5 className="font-semibold">Posted GL budget comparison</h5>
          <p>Property-tagged posted GL activity, including reversals. This is not an independently allocated HOA-only financial report. Unassigned and other-property GL lines are excluded. Reserve allocations here are budget targets, not transfers.</p>
          <ol>{actuals[item.id].lines.map(line => <li key={line.gl_account_id}>
            {line.gl_number} · {line.gl_name} · Budget ${line.annual_budget} · Book actual ${line.actual_book} · Variance ${line.variance_actual_minus_budget}
          </li>)}</ol>
        </div>}
      </>}
      {item.status === "APPROVED" && canEdit && <>
        <button type="button" className="text-blue-700"
          onClick={() => setIncreasing(prior => prior === item.id ? null : item.id)}>
          {increasing === item.id ? "Hide assessment increases" : "Annual assessment increases"}</button>
        {increasing === item.id && <HoaAnnualBudgetIncreasesPanel
          associationId={associationId} propertyId={propertyId}
          budgetId={item.id} budgetYear={item.calendar_year}
          onClose={() => setIncreasing(null)} />}
      </>}
      {item.status === "DRAFT" && canEdit && <>
        <button type="button" onClick={() => openDraft(item)}
          className="text-blue-700">Edit annual draft</button>
        <button type="button" onClick={() => {
          setDeciding(deciding === item.id ? null : item.id); setNote("");
        }} className="ml-3 text-blue-700">Record annual budget decision</button>
        {deciding === item.id && <div className="space-y-2 rounded border p-2">
          <label className="block">Budget board decision
            <select aria-label="HOA annual board decision" value={decision}
              onChange={e => setDecision(e.target.value as "APPROVED" | "DENIED")}
              className="mt-1 block rounded border p-2">
              <option value="APPROVED">APPROVED</option>
              <option value="DENIED">DENIED</option>
            </select>
          </label>
          <label className="block">Budget board decision note
            <textarea maxLength={1500} value={note}
              onChange={e => setNote(e.target.value)}
              className="mt-1 block w-full rounded border p-2" />
          </label>
          <button type="button" disabled={busy || note.trim().length < 3}
            onClick={() => { void decide(item); }}
            className="rounded bg-teal-900 px-3 py-2 text-white disabled:opacity-50">
            Save annual board decision
          </button>
        </div>}
      </>}
    </article>)}
  </section>;
}
