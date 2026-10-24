"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { getBankAccount, type BankAccount } from "@/lib/bankAccounts";
import { generateACHFile, type ACHEntry } from "@/lib/achFiles";

const emptyEntry = (): ACHEntry => ({
  recipient_name: "",
  routing_number: "",
  account_number: "",
  account_type: "CHECKING",
  amount: 0,
  identification: "",
});

export default function ACHFilePage() {
  const bankId = Number(useParams().id);
  const [bank, setBank] = useState<BankAccount | null>(null);
  const [effectiveDate, setEffectiveDate] = useState("");
  const [companyId, setCompanyId] = useState("");
  const [description, setDescription] = useState("PAYMENT");
  const [entries, setEntries] = useState<ACHEntry[]>([emptyEntry()]);
  const [error, setError] = useState("");
  const [working, setWorking] = useState(false);

  useEffect(() => {
    getBankAccount(bankId)
      .then(setBank)
      .catch((err) => setError(err instanceof Error ? err.message : "Could not load bank account"));
  }, [bankId]);

  function update(index: number, patch: Partial<ACHEntry>) {
    setEntries((rows) => rows.map((row, i) => (i === index ? { ...row, ...patch } : row)));
  }

  async function generate() {
    setError("");
    if (!effectiveDate) {
      setError("Effective date is required.");
      return;
    }
    if (entries.some((x) => !x.recipient_name || !x.routing_number || !x.account_number || Number(x.amount) <= 0)) {
      setError("Complete every recipient row with name, routing, account, and amount.");
      return;
    }
    setWorking(true);
    try {
      const result = await generateACHFile(bankId, {
        effective_date: effectiveDate,
        company_id: companyId.trim() || null,
        entry_description: description.trim() || "PAYMENT",
        entries,
      });
      const blob = new Blob([result.content], { type: result.content_type });
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = result.filename;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not generate ACH file");
    } finally {
      setWorking(false);
    }
  }

  return (
    <div className="max-w-6xl p-6">
      <Link href="/dashboard/accounting/bank-accounts" className="text-sm text-slate-500 hover:text-slate-900">
        ← Back to Bank Accounts
      </Link>
      <h1 className="mt-4 text-2xl font-bold text-slate-900">ACH File Generation</h1>
      <p className="mt-1 text-sm text-slate-500">
        {bank?.name || "Bank account"} · {bank?.ach_format || "format not configured"} · file generation does not post accounting entries.
      </p>
      {error && <div className="mt-4 rounded border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</div>}

      <div className="mt-6 grid grid-cols-3 gap-4 rounded-xl border border-slate-200 bg-white p-5">
        <label className="text-sm">Effective Date<input type="date" className="mt-1 w-full rounded border px-3 py-2" value={effectiveDate} onChange={(e) => setEffectiveDate(e.target.value)} /></label>
        <label className="text-sm">Company ID {bank?.ach_format === "NACHA" ? "*" : "(optional)"}<input maxLength={10} className="mt-1 w-full rounded border px-3 py-2" value={companyId} onChange={(e) => setCompanyId(e.target.value)} /></label>
        <label className="text-sm">Entry Description<input maxLength={10} className="mt-1 w-full rounded border px-3 py-2" value={description} onChange={(e) => setDescription(e.target.value)} /></label>
      </div>

      <div className="mt-5 overflow-x-auto rounded-xl border border-slate-200 bg-white">
        <table className="w-full text-sm">
          <thead className="bg-slate-50"><tr><th className="p-3 text-left">Recipient</th><th className="p-3 text-left">Routing</th><th className="p-3 text-left">Account</th><th className="p-3 text-left">Type</th><th className="p-3 text-right">Amount</th><th className="p-3 text-left">ID</th><th /></tr></thead>
          <tbody>
            {entries.map((entry, index) => (
              <tr key={index} className="border-t">
                <td className="p-2"><input className="w-44 rounded border px-2 py-1.5" value={entry.recipient_name} onChange={(e) => update(index, { recipient_name: e.target.value })} /></td>
                <td className="p-2"><input className="w-32 rounded border px-2 py-1.5 font-mono" maxLength={9} value={entry.routing_number} onChange={(e) => update(index, { routing_number: e.target.value })} /></td>
                <td className="p-2"><input className="w-40 rounded border px-2 py-1.5 font-mono" maxLength={17} value={entry.account_number} onChange={(e) => update(index, { account_number: e.target.value })} /></td>
                <td className="p-2"><select className="rounded border px-2 py-1.5" value={entry.account_type} onChange={(e) => update(index, { account_type: e.target.value as "CHECKING" | "SAVINGS" })}><option value="CHECKING">Checking</option><option value="SAVINGS">Savings</option></select></td>
                <td className="p-2"><input className="w-28 rounded border px-2 py-1.5 text-right" type="number" step="0.01" min="0.01" value={entry.amount || ""} onChange={(e) => update(index, { amount: Number(e.target.value) })} /></td>
                <td className="p-2"><input className="w-32 rounded border px-2 py-1.5" maxLength={15} value={entry.identification || ""} onChange={(e) => update(index, { identification: e.target.value })} /></td>
                <td className="p-2"><button type="button" disabled={entries.length === 1} className="text-xs text-red-600 disabled:opacity-30" onClick={() => setEntries((rows) => rows.filter((_, i) => i !== index))}>Remove</button></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="mt-4 flex gap-3">
        <button type="button" className="rounded border px-4 py-2 text-sm" onClick={() => setEntries((rows) => [...rows, emptyEntry()])}>+ Add Recipient</button>
        <button type="button" disabled={working} className="rounded bg-slate-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50" onClick={() => void generate()}>{working ? "Generating…" : "Generate & Download"}</button>
      </div>
    </div>
  );
}
