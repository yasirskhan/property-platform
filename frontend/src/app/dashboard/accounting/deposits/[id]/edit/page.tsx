"use client";

import { useEffect, useMemo, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  getDeposit,
  listUndepositedReceipts,
  updateDeposit,
  type DepositDetail,
  type UndepositedReceiptRow,
} from "@/lib/deposits";
import { formatDate, formatMoney } from "@/lib/money";

type EditableReceipt = {
  id: number;
  receipt_date: string;
  type: string;
  amount: string;
  reference_number: string | null;
  payer_label: string | null;
};

export default function EditDepositPage() {
  const id = Number(useParams().id);
  const router = useRouter();
  const [deposit, setDeposit] = useState<DepositDetail | null>(null);
  const [available, setAvailable] = useState<EditableReceipt[]>([]);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [depositDate, setDepositDate] = useState("");
  const [depositNumber, setDepositNumber] = useState("");
  const [description, setDescription] = useState("");
  const [notes, setNotes] = useState("");
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const current = await getDeposit(id);
        setDeposit(current);
        setDepositDate(current.deposit_date);
        setDepositNumber(current.deposit_number || "");
        setDescription(current.description || "");
        setNotes(current.notes || "");
        const open = await listUndepositedReceipts(current.bank_gl_account_id);
        const existing: EditableReceipt[] = current.lines.map((line) => ({
          id: line.receipt_id,
          receipt_date: line.receipt_date || current.deposit_date,
          type: line.receipt_type || "Receipt",
          amount: line.receipt_amount || "0",
          reference_number: line.receipt_reference,
          payer_label: line.receipt_payer,
        }));
        const extra: EditableReceipt[] = open.items.map(
          (row: UndepositedReceiptRow) => ({
            id: row.id,
            receipt_date: row.receipt_date,
            type: row.type,
            amount: row.amount,
            reference_number: row.reference_number,
            payer_label: row.payer_label,
          })
        );
        setAvailable([...existing, ...extra]);
        setSelected(new Set(existing.map((row) => row.id)));
      } catch (e) {
        setError(e instanceof Error ? e.message : "Could not load deposit.");
      }
    })();
  }, [id]);

  const chosen = useMemo(
    () => available.filter((row) => selected.has(row.id)),
    [available, selected]
  );
  const total = chosen.reduce((sum, row) => sum + Number(row.amount), 0);
  const mismatched = chosen.filter((row) => row.receipt_date !== depositDate);

  function toggle(id: number) {
    setSelected((old) => {
      const next = new Set(old);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  async function save() {
    if (!chosen.length) {
      setError("A deposit must include at least one receipt.");
      return;
    }
    setSaving(true);
    setError("");
    try {
      await updateDeposit(id, {
        deposit_date: depositDate,
        deposit_number: depositNumber || null,
        description: description || null,
        notes: notes || null,
        receipt_ids: chosen.map((row) => row.id),
      });
      router.push("/dashboard/accounting/deposits");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not edit deposit.");
      setSaving(false);
    }
  }

  if (!deposit) return <div className="p-6">{error || "Loading..."}</div>;

  return (
    <div className="max-w-5xl mx-auto p-6">
      <h1 className="text-xl font-semibold">Edit Bank Deposit</h1>
      <p className="text-sm text-slate-500 mb-5">
        {deposit.bank_gl_account_number} {deposit.bank_gl_account_name}
      </p>
      {error && <div className="mb-4 text-red-600">{error}</div>}
      {mismatched.length > 0 && (
        <div className="mb-4 rounded border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
          {mismatched.length} selected receipt{mismatched.length === 1 ? " has" : "s have"} a date different from the deposit date.
        </div>
      )}
      <div className="grid md:grid-cols-2 gap-3 mb-5">
        <label className="text-sm">Deposit date
          <input className="block w-full border rounded p-2" type="date" value={depositDate} onChange={(e) => setDepositDate(e.target.value)} />
        </label>
        <label className="text-sm">Deposit #
          <input className="block w-full border rounded p-2" value={depositNumber} onChange={(e) => setDepositNumber(e.target.value)} />
        </label>
        <label className="text-sm">Description
          <input className="block w-full border rounded p-2" value={description} onChange={(e) => setDescription(e.target.value)} />
        </label>
        <label className="text-sm">Notes
          <input className="block w-full border rounded p-2" value={notes} onChange={(e) => setNotes(e.target.value)} />
        </label>
      </div>
      <div className="border rounded bg-white overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-slate-50"><tr><th className="p-3"></th><th className="p-3 text-left">Date</th><th className="p-3 text-left">Payer</th><th className="p-3 text-left">Reference</th><th className="p-3 text-right">Amount</th></tr></thead>
          <tbody>{available.map((row) => <tr key={row.id} className="border-t"><td className="p-3"><input type="checkbox" checked={selected.has(row.id)} onChange={() => toggle(row.id)} /></td><td className="p-3">{formatDate(row.receipt_date)}</td><td className="p-3">{row.payer_label || row.type}</td><td className="p-3">{row.reference_number || "—"}</td><td className="p-3 text-right">{formatMoney(row.amount)}</td></tr>)}</tbody>
        </table>
      </div>
      <div className="mt-4 flex justify-end gap-3 items-center">
        <strong>Total {formatMoney(total)}</strong>
        <button className="border rounded px-4 py-2" onClick={() => router.back()}>Cancel</button>
        <button className="bg-blue-600 text-white rounded px-4 py-2 disabled:opacity-50" disabled={saving} onClick={() => void save()}>{saving ? "Saving…" : "Save Deposit"}</button>
      </div>
    </div>
  );
}
