"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { apiGet } from "@/lib/api";
import { formatDate, formatMoney } from "@/lib/money";
import {
  createRecurringBill,
  listRecurringBills,
  postRecurringBills,
  type RecurringBill,
} from "@/lib/bills";
import { useDisplay } from "@/contexts/DisplayContext";

type Property = { id: number; name: string };
type GLAccount = { id: number; gl_number: string; name: string; account_type: string };
type LineRow = { key: string; gl_account_id: number | ""; property_id: number | ""; description: string; amount: string };

function blankLine(key: string): LineRow {
  return { key, gl_account_id: "", property_id: "", description: "", amount: "" };
}

export default function RecurringBillsPage() {
  const { prefs } = useDisplay();
  const [rows, setRows] = useState<RecurringBill[]>([]);
  const [properties, setProperties] = useState<Property[]>([]);
  const [accounts, setAccounts] = useState<GLAccount[]>([]);
  const [cashAccounts, setCashAccounts] = useState<GLAccount[]>([]);
  const [selected, setSelected] = useState<number[]>([]);
  const [postDate, setPostDate] = useState(new Date().toISOString().slice(0, 10));
  const [posting, setPosting] = useState(false);
  const [saving, setSaving] = useState(false);
  const [showForm, setShowForm] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const [entryType, setEntryType] = useState<"BILL" | "CREDIT">("BILL");
  const [payeeName, setPayeeName] = useState("");
  const [startDate, setStartDate] = useState(new Date().toISOString().slice(0, 10));
  const [endDate, setEndDate] = useState("");
  const [billDay, setBillDay] = useState(String(new Date().getDate()));
  const [dueDay, setDueDay] = useState("");
  const [postCode, setPostCode] = useState("");
  const [referenceNumber, setReferenceNumber] = useState("");
  const [remarks, setRemarks] = useState("");
  const [cashAccountId, setCashAccountId] = useState<number | "">("");
  const [lines, setLines] = useState<LineRow[]>([blankLine("initial-1"), blankLine("initial-2")]);

  async function load() {
    setError(null);
    try {
      const [schedules, props, gls] = await Promise.all([
        listRecurringBills(),
        apiGet("/properties"),
        apiGet("/api/accounting/gl-accounts"),
      ]);
      setRows(schedules);
      setProperties(props as Property[]);
      const groups = (gls as { groups: { account_type: string; accounts: GLAccount[] }[] }).groups;
      setAccounts(groups.filter((g) => (g.account_type || "").toUpperCase() === "EXPENSE").flatMap((g) => g.accounts));
      setCashAccounts(groups.filter((g) => (g.account_type || "").toUpperCase() === "ASSET").flatMap((g) => g.accounts).filter((a) => a.gl_number.startsWith("11")));
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Could not load recurring bills.");
    }
  }

  useEffect(() => { load(); }, []);

  const total = useMemo(() => lines.reduce((sum, line) => sum + (parseFloat(line.amount) || 0), 0), [lines]);

  function updateLine(key: string, patch: Partial<LineRow>) {
    setLines((current) => current.map((line) => line.key === key ? { ...line, ...patch } : line));
  }

  async function saveSchedule() {
    const validLines = lines.filter((line) => line.gl_account_id && parseFloat(line.amount) > 0);
    if (!payeeName.trim() || !startDate || !billDay || validLines.length === 0) {
      setError("Payee, start date, bill day, and at least one line are required.");
      return;
    }
    setSaving(true);
    setError(null);
    setNotice(null);
    try {
      await createRecurringBill({
        entry_type: entryType,
        payee_name: payeeName.trim(),
        start_date: startDate,
        end_date: endDate || null,
        bill_day: Number(billDay),
        due_day: entryType === "BILL" && dueDay ? Number(dueDay) : null,
        post_code: postCode || null,
        reference_number: referenceNumber || null,
        remarks: remarks || null,
        cash_gl_account_id: entryType === "BILL" ? cashAccountId || null : null,
        lines: validLines.map((line) => ({
          gl_account_id: line.gl_account_id as number,
          property_id: line.property_id || null,
          description: line.description || null,
          amount: Number(line.amount),
        })),
      });
      setShowForm(false);
      setPayeeName("");
      setEndDate("");
      setPostCode("");
      setReferenceNumber("");
      setRemarks("");
      setCashAccountId("");
      setLines([blankLine("reset-1"), blankLine("reset-2")]);
      setNotice("Recurring schedule created.");
      await load();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Could not create recurring schedule.");
    } finally {
      setSaving(false);
    }
  }

  async function postSelected() {
    if (selected.length === 0) return;
    setPosting(true);
    setError(null);
    setNotice(null);
    try {
      const result = await postRecurringBills(postDate, selected);
      setNotice(`Posted ${result.posted_bills} bill(s) and ${result.posted_credits} credit(s).${result.failed ? ` ${result.failed} failed.` : ""}`);
      setSelected([]);
      await load();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Could not post selected schedules.");
    } finally {
      setPosting(false);
    }
  }

  return (
    <div className="p-6" data-layout-mode={(prefs?.layout_mode ?? "TABS").toLowerCase()} data-density={(prefs?.density ?? "COMFORTABLE").toLowerCase()}>
      <div className="flex items-center justify-between gap-3 mb-1">
        <div>
          <Link href="/dashboard/accounting/bills" className="text-sm text-slate-500 hover:text-slate-800">← Bills</Link>
          <h1 className="text-xl font-semibold text-slate-900 mt-2">Recurring Bills & Credits</h1>
        </div>
        <button type="button" onClick={() => setShowForm((v) => !v)} className="px-3 py-1.5 rounded-md bg-blue-600 text-white text-sm font-medium hover:bg-blue-700">
          {showForm ? "Close form" : "+ New recurring"}
        </button>
      </div>
      <p className="text-sm text-slate-500 mb-5">Monthly schedules with Bill/Credit type, post code, and selected manual posting.</p>

      {error && <div className="mb-4 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{error}</div>}
      {notice && <div className="mb-4 rounded-md border border-green-200 bg-green-50 px-3 py-2 text-sm text-green-700">{notice}</div>}

      {showForm && (
        <div className="bg-white border border-slate-200 rounded-lg p-5 mb-5 space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
            <label className="text-xs text-slate-600">Type
              <select value={entryType} onChange={(e) => setEntryType(e.target.value as "BILL" | "CREDIT")} className="mt-1 w-full border rounded-md px-2 py-1.5 text-sm bg-white">
                <option value="BILL">Bill</option><option value="CREDIT">Credit</option>
              </select>
            </label>
            <label className="text-xs text-slate-600 md:col-span-2">Payee
              <input value={payeeName} onChange={(e) => setPayeeName(e.target.value)} className="mt-1 w-full border rounded-md px-2 py-1.5 text-sm" />
            </label>
            <label className="text-xs text-slate-600">Post Code
              <input value={postCode} onChange={(e) => setPostCode(e.target.value)} className="mt-1 w-full border rounded-md px-2 py-1.5 text-sm" />
            </label>
            <label className="text-xs text-slate-600">Start Date
              <input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} className="mt-1 w-full border rounded-md px-2 py-1.5 text-sm" />
            </label>
            <label className="text-xs text-slate-600">End Date
              <input type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} className="mt-1 w-full border rounded-md px-2 py-1.5 text-sm" />
            </label>
            <label className="text-xs text-slate-600">Bill Day
              <input type="number" min="1" max="31" value={billDay} onChange={(e) => setBillDay(e.target.value)} className="mt-1 w-full border rounded-md px-2 py-1.5 text-sm" />
            </label>
            <label className="text-xs text-slate-600">Due Day
              <input type="number" min="1" max="31" disabled={entryType === "CREDIT"} value={dueDay} onChange={(e) => setDueDay(e.target.value)} className="mt-1 w-full border rounded-md px-2 py-1.5 text-sm disabled:bg-slate-100" />
            </label>
            <label className="text-xs text-slate-600">Reference
              <input value={referenceNumber} onChange={(e) => setReferenceNumber(e.target.value)} className="mt-1 w-full border rounded-md px-2 py-1.5 text-sm" />
            </label>
            <label className="text-xs text-slate-600 md:col-span-2">Remarks
              <input value={remarks} onChange={(e) => setRemarks(e.target.value)} className="mt-1 w-full border rounded-md px-2 py-1.5 text-sm" />
            </label>
            <label className="text-xs text-slate-600">Default cash account
              <select disabled={entryType === "CREDIT"} value={cashAccountId} onChange={(e) => setCashAccountId(e.target.value ? Number(e.target.value) : "")} className="mt-1 w-full border rounded-md px-2 py-1.5 text-sm bg-white disabled:bg-slate-100">
                <option value="">Choose when paying</option>
                {cashAccounts.map((a) => <option key={a.id} value={a.id}>{a.gl_number} {a.name}</option>)}
              </select>
            </label>
          </div>

          <div className="border rounded-md overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-slate-50"><tr><th className="text-left p-2">Account</th><th className="text-left p-2">Property</th><th className="text-left p-2">Description</th><th className="text-right p-2">Amount</th><th /></tr></thead>
              <tbody>
                {lines.map((line) => (
                  <tr key={line.key} className="border-t">
                    <td className="p-2"><select value={line.gl_account_id} onChange={(e) => updateLine(line.key,{gl_account_id:e.target.value?Number(e.target.value):""})} className="w-full border rounded px-2 py-1.5 bg-white"><option value="">Select...</option>{accounts.map((a)=><option key={a.id} value={a.id}>{a.gl_number} {a.name}</option>)}</select></td>
                    <td className="p-2"><select value={line.property_id} onChange={(e) => updateLine(line.key,{property_id:e.target.value?Number(e.target.value):""})} className="w-full border rounded px-2 py-1.5 bg-white"><option value="">(none)</option>{properties.map((p)=><option key={p.id} value={p.id}>{p.name}</option>)}</select></td>
                    <td className="p-2"><input value={line.description} onChange={(e) => updateLine(line.key,{description:e.target.value})} className="w-full border rounded px-2 py-1.5" /></td>
                    <td className="p-2"><input type="number" min="0" step="0.01" value={line.amount} onChange={(e) => updateLine(line.key,{amount:e.target.value})} className="w-full border rounded px-2 py-1.5 text-right" /></td>
                    <td className="p-2"><button type="button" disabled={lines.length <= 1} onClick={() => setLines((current)=>current.filter((x)=>x.key!==line.key))} className="text-slate-400 hover:text-red-600 disabled:opacity-30">✕</button></td>
                  </tr>
                ))}
              </tbody>
              <tfoot className="bg-slate-50"><tr><td colSpan={3} className="p-2"><button type="button" onClick={() => setLines((current)=>[...current,blankLine(`line-${crypto.randomUUID()}`)])} className="text-blue-600 text-xs hover:underline">+ Add line</button></td><td className="p-2 text-right font-mono">{formatMoney(total.toFixed(2))}</td><td /></tr></tfoot>
            </table>
          </div>
          <div className="flex justify-end"><button type="button" disabled={saving} onClick={saveSchedule} className="px-4 py-2 rounded-md bg-blue-600 text-white text-sm font-medium disabled:opacity-50">{saving ? "Saving..." : "Save recurring schedule"}</button></div>
        </div>
      )}

      <div className="bg-white border border-slate-200 rounded-lg mb-4 p-4 flex flex-wrap items-end gap-3">
        <label className="text-xs text-slate-600">Post due through
          <input type="date" value={postDate} onChange={(e) => setPostDate(e.target.value)} className="block mt-1 border rounded-md px-2 py-1.5 text-sm" />
        </label>
        <button type="button" disabled={posting || selected.length === 0} onClick={postSelected} className="px-3 py-1.5 rounded-md bg-slate-800 text-white text-sm font-medium disabled:opacity-40">
          {posting ? "Posting..." : `Post Selected (${selected.length})`}
        </button>
      </div>

      <div className="bg-white border border-slate-200 rounded-lg overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-slate-50"><tr><th className="p-2 w-10"></th><th className="text-left p-2">Type</th><th className="text-left p-2">Payee</th><th className="text-left p-2">Post Code</th><th className="text-left p-2">Next Post</th><th className="text-right p-2">Amount</th><th className="text-left p-2">Status</th></tr></thead>
          <tbody>
            {rows.length === 0 && <tr><td colSpan={7} className="p-6 text-center text-slate-500">No recurring schedules yet.</td></tr>}
            {rows.map((row) => {
              const amount=row.lines.reduce((sum,line)=>sum+parseFloat(line.amount),0);
              return <tr key={row.id} className="border-t">
                <td className="p-2"><input type="checkbox" checked={selected.includes(row.id)} disabled={!row.is_active} onChange={(e)=>setSelected((current)=>e.target.checked?[...current,row.id]:current.filter((id)=>id!==row.id))} /></td>
                <td className="p-2"><span className={`text-xs px-2 py-0.5 rounded ${row.entry_type==="CREDIT"?"bg-purple-50 text-purple-700":"bg-blue-50 text-blue-700"}`}>{row.entry_type}</span></td>
                <td className="p-2">{row.payee_name}</td>
                <td className="p-2 font-mono text-xs">{row.post_code || "—"}</td>
                <td className="p-2">{formatDate(row.next_post_date)}</td>
                <td className="p-2 text-right font-mono">{formatMoney(amount.toFixed(2))}</td>
                <td className="p-2">{row.is_active ? "Active" : "Complete"}</td>
              </tr>;
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
