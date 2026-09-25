"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { apiGet } from "@/lib/api";
import { createVendorCredit } from "@/lib/bills";
import { formatMoney } from "@/lib/money";
import { useDisplay } from "@/contexts/DisplayContext";

type Property = { id: number; name: string };
type GLAccount = { id: number; gl_number: string; name: string; account_type: string };
type LineRow = { key: string; gl_account_id: number | ""; property_id: number | ""; description: string; amount: string };

function blankLine(key: string): LineRow {
  return { key, gl_account_id: "", property_id: "", description: "", amount: "" };
}

export default function NewVendorCreditPage() {
  const router = useRouter();
  const { prefs } = useDisplay();
  const [properties, setProperties] = useState<Property[]>([]);
  const [accounts, setAccounts] = useState<GLAccount[]>([]);
  const [payeeName, setPayeeName] = useState("");
  const [creditDate, setCreditDate] = useState(new Date().toISOString().slice(0, 10));
  const [referenceNumber, setReferenceNumber] = useState("");
  const [creditNumber, setCreditNumber] = useState("");
  const [remarks, setRemarks] = useState("");
  const [lines, setLines] = useState<LineRow[]>([blankLine("initial-1"), blankLine("initial-2")]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    Promise.all([apiGet("/properties"), apiGet("/api/accounting/gl-accounts")])
      .then(([props, gls]) => {
        if (cancelled) return;
        setProperties(props as Property[]);
        const groups = (gls as { groups: { account_type: string; accounts: GLAccount[] }[] }).groups;
        setAccounts(groups.filter((g) => (g.account_type || "").toUpperCase() === "EXPENSE").flatMap((g) => g.accounts));
      })
      .catch((e: unknown) => !cancelled && setError(e instanceof Error ? e.message : "Could not load form data."))
      .finally(() => !cancelled && setLoading(false));
    return () => { cancelled = true; };
  }, []);

  const total = useMemo(() => lines.reduce((sum, line) => sum + (parseFloat(line.amount) || 0), 0), [lines]);

  function updateLine(key: string, patch: Partial<LineRow>) {
    setLines((current) => current.map((line) => line.key === key ? { ...line, ...patch } : line));
  }

  async function submit() {
    const validLines = lines.filter((line) => line.gl_account_id && parseFloat(line.amount) > 0);
    if (!payeeName.trim() || !creditDate || validLines.length === 0) {
      setError("Payee, credit date, and at least one positive line are required.");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await createVendorCredit({
        payee_name: payeeName.trim(),
        credit_date: creditDate,
        reference_number: referenceNumber || null,
        credit_number: creditNumber || null,
        remarks: remarks || null,
        lines: validLines.map((line) => ({
          gl_account_id: line.gl_account_id as number,
          property_id: line.property_id || null,
          description: line.description || null,
          amount: Number(line.amount),
        })),
      });
      router.push("/dashboard/accounting/bills");
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Could not enter vendor credit.");
    } finally {
      setSaving(false);
    }
  }

  if (loading) return <div className="p-6 text-slate-500">Loading...</div>;

  return (
    <div className="max-w-5xl mx-auto p-6" data-layout-mode={(prefs?.layout_mode ?? "TABS").toLowerCase()} data-density={(prefs?.density ?? "COMFORTABLE").toLowerCase()}>
      <Link href="/dashboard/accounting/bills" className="text-sm text-slate-500 hover:text-slate-800">← Bills</Link>
      <h1 className="text-xl font-semibold text-slate-900 mt-2 mb-1">Enter Vendor Credit</h1>
      <p className="text-sm text-slate-500 mb-6">Enter a positive vendor credit. Accounting posts DR Accounts Payable / CR the selected expense accounts.</p>
      {error && <div className="mb-4 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{error}</div>}

      <div className="bg-white border border-slate-200 rounded-lg p-5 mb-5 grid grid-cols-1 md:grid-cols-2 gap-4">
        <label className="text-xs text-slate-600">Payee
          <input value={payeeName} onChange={(e)=>setPayeeName(e.target.value)} className="mt-1 w-full border rounded-md px-3 py-1.5 text-sm" />
        </label>
        <label className="text-xs text-slate-600">Credit Date
          <input type="date" value={creditDate} onChange={(e)=>setCreditDate(e.target.value)} className="mt-1 w-full border rounded-md px-3 py-1.5 text-sm" />
        </label>
        <label className="text-xs text-slate-600">Credit #
          <input value={creditNumber} onChange={(e)=>setCreditNumber(e.target.value)} placeholder="Auto if blank" className="mt-1 w-full border rounded-md px-3 py-1.5 text-sm" />
        </label>
        <label className="text-xs text-slate-600">Reference
          <input value={referenceNumber} onChange={(e)=>setReferenceNumber(e.target.value)} className="mt-1 w-full border rounded-md px-3 py-1.5 text-sm" />
        </label>
        <label className="text-xs text-slate-600 md:col-span-2">Remarks
          <input value={remarks} onChange={(e)=>setRemarks(e.target.value)} className="mt-1 w-full border rounded-md px-3 py-1.5 text-sm" />
        </label>
      </div>

      <div className="bg-white border border-slate-200 rounded-lg overflow-hidden mb-5">
        <table className="w-full text-sm">
          <thead className="bg-slate-50"><tr><th className="text-left p-3">Account</th><th className="text-left p-3">Property</th><th className="text-left p-3">Description</th><th className="text-right p-3">Amount</th><th /></tr></thead>
          <tbody>
            {lines.map((line)=>(
              <tr key={line.key} className="border-t">
                <td className="p-2"><select value={line.gl_account_id} onChange={(e)=>updateLine(line.key,{gl_account_id:e.target.value?Number(e.target.value):""})} className="w-full border rounded px-2 py-1.5 bg-white"><option value="">Select account...</option>{accounts.map((a)=><option key={a.id} value={a.id}>{a.gl_number} {a.name}</option>)}</select></td>
                <td className="p-2"><select value={line.property_id} onChange={(e)=>updateLine(line.key,{property_id:e.target.value?Number(e.target.value):""})} className="w-full border rounded px-2 py-1.5 bg-white"><option value="">(none)</option>{properties.map((p)=><option key={p.id} value={p.id}>{p.name}</option>)}</select></td>
                <td className="p-2"><input value={line.description} onChange={(e)=>updateLine(line.key,{description:e.target.value})} className="w-full border rounded px-2 py-1.5" /></td>
                <td className="p-2"><input type="number" min="0" step="0.01" value={line.amount} onChange={(e)=>updateLine(line.key,{amount:e.target.value})} className="w-full border rounded px-2 py-1.5 text-right" /></td>
                <td className="p-2"><button type="button" disabled={lines.length<=1} onClick={()=>setLines((current)=>current.filter((x)=>x.key!==line.key))} className="text-slate-400 hover:text-red-600 disabled:opacity-30">✕</button></td>
              </tr>
            ))}
          </tbody>
          <tfoot className="bg-slate-50"><tr><td colSpan={3} className="p-3"><button type="button" onClick={()=>setLines((current)=>[...current,blankLine(`line-${crypto.randomUUID()}`)])} className="text-blue-600 text-xs hover:underline">+ Add line</button></td><td className="p-3 text-right font-mono font-medium">{formatMoney(total.toFixed(2))}</td><td /></tr></tfoot>
        </table>
      </div>

      <div className="flex justify-end gap-3">
        <button type="button" onClick={()=>router.push("/dashboard/accounting/bills")} className="px-4 py-2 border rounded-md text-sm">Cancel</button>
        <button type="button" disabled={saving} onClick={submit} className="px-4 py-2 rounded-md bg-blue-600 text-white text-sm font-medium disabled:opacity-50">{saving ? "Saving..." : "Enter credit"}</button>
      </div>
    </div>
  );
}
