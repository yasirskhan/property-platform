"use client";

import { useEffect, useState } from "react";
import { apiGet, apiPost } from "@/lib/api";

type Option = { gl_account_id: number; gl_number: string; gl_name: string };
type Movement = {
  id: number; direction: "TO_RESERVE" | "FROM_RESERVE";
  planned_on: string; amount: string; memo: string;
  status: "DRAFT" | "CANCELLED";
  counterparty_gl_account_id: number;
  posting_enabled: false; funds_moved: false;
};

export default function HoaReserveMovementPlans({
  associationId, propertyId, reserveGlId, canEdit,
}: {
  associationId: number; propertyId: number; reserveGlId: number; canEdit: boolean;
}) {
  const root = "/api/hoa/associations/" + associationId;
  const base = root + "/reserve-movement-drafts";
  const query = "?property_id=" + propertyId;
  const [rows, setRows] = useState<Movement[]>([]);
  const [options, setOptions] = useState<Option[]>([]);
  const [counterpartId, setCounterpartId] = useState("");
  const [direction, setDirection] = useState<"TO_RESERVE" | "FROM_RESERVE">("TO_RESERVE");
  const [amount, setAmount] = useState("");
  const [day, setDay] = useState("");
  const [memo, setMemo] = useState("");
  const [key, setKey] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  async function refresh() {
    setRows(await apiGet(base + query) as Movement[]);
  }

  useEffect(() => {
    let alive = true;
    setError(""); setLoading(true); setRows([]);
    void Promise.all([
      apiGet(base + query) as Promise<Movement[]>,
      canEdit ? apiGet(root + "/reserve-counterpart-options" + query) as Promise<Option[]> : Promise.resolve([]),
    ]).then(([items, available]) => {
      if (!alive) return;
      setRows(items);
      setOptions(available.filter((option) => option.gl_account_id !== reserveGlId));
    }).catch((cause) => {
      if (alive) setError(cause instanceof Error ? cause.message : "Reserve planning unavailable.");
    }).finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
  }, [base, root, query, reserveGlId, canEdit]);

  async function save(event: React.FormEvent) {
    event.preventDefault();
    if (!canEdit || !counterpartId || !amount || !day || !memo.trim() || busy) return;
    // Preserve the same idempotency key across a failed network retry.
    const requestKey = key || window.crypto.randomUUID();
    setKey(requestKey);
    setBusy(true); setError(""); setMessage("");
    try {
      await apiPost(base, {
        property_id: propertyId, counterparty_gl_account_id: Number(counterpartId),
        direction, amount, planned_on: day, memo: memo.trim(), idempotency_key: requestKey,
      });
      await refresh();
      setCounterpartId(""); setAmount(""); setDay(""); setMemo(""); setKey("");
      setMessage("Unissued reserve movement request recorded. No funds were moved.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not prepare movement.");
    } finally { setBusy(false); }
  }

  async function cancel(row: Movement) {
    if (!canEdit || busy || !window.confirm("Cancel this unissued reserve movement request?")) return;
    setBusy(true); setError(""); setMessage("");
    try {
      await apiPost(base + "/" + row.id + "/cancel" + query, {});
      await refresh();
      setMessage("Request cancelled. There was no financial transfer or reversal.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not cancel request.");
    } finally { setBusy(false); }
  }

  return <section className="space-y-2 rounded border border-amber-300 bg-amber-50 p-3 text-xs">
    <h4 className="font-semibold">Reserve movement preparation</h4>
    <p className="text-amber-900">
      Unverified internal instructions only. Nothing is posted to the ledger,
      released to a bank or treated as certified reserve ownership. No
      withdrawal or transfer can be executed here.
    </p>
    {loading && <p>Loading movement requests…</p>}
    {error && <p role="alert" className="text-red-700">{error}</p>}
    {message && <p role="status" className="text-green-700">{message}</p>}
    {!loading && rows.length === 0 && <p>No movement requests recorded.</p>}
    {rows.map((row) => <div className="flex flex-wrap items-center gap-2 rounded border bg-white p-2"
      key={row.id}>
      <span>{row.planned_on} · {row.direction.replaceAll("_", " ")} ·
        Proposed ${row.amount} · {row.memo} · {row.status}</span>
      {canEdit && row.status === "DRAFT" &&
        <button type="button" disabled={busy} className="text-red-700 disabled:opacity-50"
          onClick={() => { void cancel(row); }}>Cancel draft</button>}
    </div>)}
    {canEdit && !loading && <form onSubmit={(event) => { void save(event); }}
      className="space-y-2 border-t pt-2">
      <label className="block">Existing same-org counterparty cash GL
        <select required value={counterpartId}
          onChange={(e) => { setCounterpartId(e.target.value); setKey(""); }}
          className="mt-1 block w-full rounded border bg-white p-2">
          <option value="">Choose existing cash-like account</option>
          {options.map((row) => <option key={row.gl_account_id} value={row.gl_account_id}>
            {row.gl_number} · {row.gl_name}
          </option>)}
        </select>
      </label>
      <label className="block">Planning direction
        <select value={direction}
          onChange={(e) => { setDirection(e.target.value as typeof direction); setKey(""); }}
          className="mt-1 block rounded border bg-white p-2">
          <option value="TO_RESERVE">To reserve (unissued)</option>
          <option value="FROM_RESERVE">From reserve (unissued)</option>
        </select>
      </label>
      <div className="flex flex-wrap gap-2">
        <label>Proposed date<input type="date" required value={day}
          onChange={(e) => { setDay(e.target.value); setKey(""); }}
          className="mt-1 block rounded border bg-white p-2" /></label>
        <label>Proposed amount<input type="number" min="0.01" step="0.01" required value={amount}
          onChange={(e) => { setAmount(e.target.value); setKey(""); }}
          className="mt-1 block rounded border bg-white p-2" /></label>
      </div>
      <label className="block">Staff memo<input maxLength={240} required value={memo}
        onChange={(e) => { setMemo(e.target.value); setKey(""); }}
        className="mt-1 block w-full rounded border bg-white p-2" /></label>
      <button type="submit" disabled={!counterpartId || !amount || !day || !memo.trim() || busy}
        className="rounded border bg-white px-3 py-2 disabled:opacity-50">
        {busy ? "Saving…" : "Prepare unissued movement"}
      </button>
    </form>}
  </section>;
}
