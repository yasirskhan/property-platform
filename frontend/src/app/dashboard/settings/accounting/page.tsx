"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

import {
  getAccountingSettings,
  updateAccountingSettings,
  type AccountingSettings,
  type AccountingSettingsUpdate,
} from "@/lib/accountingSettings";

const MONTHS = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];

export default function AccountingSettingsPage() {
  const [settings, setSettings] = useState<AccountingSettings | null>(null);
  const [form, setForm] = useState<AccountingSettingsUpdate | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  useEffect(() => {
    getAccountingSettings()
      .then((data) => {
        setSettings(data);
        setForm({
          gpr_rent_gl_account_id: data.gpr_rent_gl_account_id,
          gpr_market_gl_account_id: data.gpr_market_gl_account_id,
          gpr_loss_gain_gl_account_id: data.gpr_loss_gain_gl_account_id,
          receipt_cash_gl_account_id: data.receipt_cash_gl_account_id,
          report_export_format: data.report_export_format,
          fiscal_year_start_month: data.fiscal_year_start_month,
          accounting_basis: data.accounting_basis,
        });
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Could not load Accounting Settings."))
      .finally(() => setLoading(false));
  }, []);

  async function save() {
    if (!form) return;
    setSaving(true);
    setError("");
    setMessage("");
    try {
      const data = await updateAccountingSettings(form);
      setSettings(data);
      setForm({
        gpr_rent_gl_account_id: data.gpr_rent_gl_account_id,
        gpr_market_gl_account_id: data.gpr_market_gl_account_id,
        gpr_loss_gain_gl_account_id: data.gpr_loss_gain_gl_account_id,
        receipt_cash_gl_account_id: data.receipt_cash_gl_account_id,
        report_export_format: data.report_export_format,
        fiscal_year_start_month: data.fiscal_year_start_month,
      });
      setMessage("Accounting Settings saved.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save Accounting Settings.");
    } finally {
      setSaving(false);
    }
  }

  if (loading) return <div className="p-6 text-sm text-slate-500">Loading Accounting Settings…</div>;
  if (!settings || !form) return <div className="p-6 text-sm text-red-700">{error || "Accounting Settings unavailable."}</div>;

  const accountSelect = (
    label: string,
    value: number | null,
    accounts: AccountingSettings["eligible_income_accounts"],
    onChange: (value: number | null) => void,
    automaticText: string
  ) => (
    <label className="block">
      <span className="block text-sm font-medium text-slate-800 mb-1">{label}</span>
      <select
        value={value ?? ""}
        onChange={(event) => onChange(event.target.value ? Number(event.target.value) : null)}
        className="w-full border border-slate-300 rounded-md px-3 py-2 text-sm bg-white"
      >
        <option value="">{automaticText}</option>
        {accounts.map((account) => (
          <option key={account.id} value={account.id}>
            {account.gl_number} · {account.name}
          </option>
        ))}
      </select>
    </label>
  );

  return (
    <div className="max-w-5xl mx-auto p-6 space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">Accounting Settings</h1>
        <p className="text-sm text-slate-500 mt-1">
          Organization-wide defaults. Existing accounting behavior remains unchanged until you explicitly choose an override.
        </p>
      </div>

      {error && <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>}
      {message && <div className="rounded-md border border-green-200 bg-green-50 px-4 py-3 text-sm text-green-700">{message}</div>}

      <section className="rounded-lg border border-slate-200 bg-white p-5">
        <div className="flex items-start justify-between gap-4 mb-4">
          <div>
            <h2 className="font-semibold text-slate-900">Key Accounts</h2>
            <p className="text-sm text-slate-500">Uses the existing organization Key Accounts registry.</p>
          </div>
          <Link href="/dashboard/accounting/owner-held-security-deposits" className="text-sm text-blue-600 hover:underline">
            Manage Key Accounts
          </Link>
        </div>
        {settings.key_accounts.length === 0 ? (
          <p className="text-sm text-slate-500">No special Key Accounts configured.</p>
        ) : (
          <div className="divide-y divide-slate-100">
            {settings.key_accounts.map((item) => (
              <div key={item.id} className="py-2 flex justify-between gap-4 text-sm">
                <span className="text-slate-600">{item.key_type.replaceAll("_", " ")}</span>
                <span className="font-medium text-slate-900">{item.gl_number} · {item.name}</span>
              </div>
            ))}
          </div>
        )}
      </section>

      <section className="rounded-lg border border-slate-200 bg-white p-5">
        <h2 className="font-semibold text-slate-900">Gross Potential Rent accounts</h2>
        <p className="text-sm text-slate-500 mt-1 mb-4">
          Blank values keep the verified standard accounts 4100, 4115, and 4120.
        </p>
        <div className="grid gap-4 md:grid-cols-3">
          {accountSelect("Scheduled rent", form.gpr_rent_gl_account_id, settings.eligible_income_accounts, (v) => setForm({ ...form, gpr_rent_gl_account_id: v }), "Standard 4100")}
          {accountSelect("Gross potential rent", form.gpr_market_gl_account_id, settings.eligible_income_accounts, (v) => setForm({ ...form, gpr_market_gl_account_id: v }), "Standard 4115")}
          {accountSelect("Loss / gain to market", form.gpr_loss_gain_gl_account_id, settings.eligible_income_accounts, (v) => setForm({ ...form, gpr_loss_gain_gl_account_id: v }), "Standard 4120")}
        </div>
      </section>

      <section className="rounded-lg border border-slate-200 bg-white p-5">
        <h2 className="font-semibold text-slate-900">Receipts</h2>
        <p className="text-sm text-slate-500 mt-1 mb-4">
          Automatic continues to use the first active Operating bank account, then standard 1150 if no bank exists.
        </p>
        <div className="max-w-xl">
          {accountSelect(
            "Default cash account",
            form.receipt_cash_gl_account_id,
            settings.eligible_cash_accounts,
            (v) => setForm({ ...form, receipt_cash_gl_account_id: v }),
            "Automatic"
          )}
        </div>
      </section>

      <section className="rounded-lg border border-slate-200 bg-white p-5">
        <div className="flex items-start justify-between gap-4 mb-4">
          <div>
            <h2 className="font-semibold text-slate-900">Check Writing</h2>
            <p className="text-sm text-slate-500">Per-bank numbering and check stock stay in the verified Check Setup workflow.</p>
          </div>
          <Link href="/dashboard/accounting/bank-accounts" className="text-sm text-blue-600 hover:underline">
            Bank Accounts
          </Link>
        </div>
        {settings.check_setups.length === 0 ? (
          <p className="text-sm text-slate-500">No active bank accounts.</p>
        ) : (
          <div className="divide-y divide-slate-100">
            {settings.check_setups.map((bank) => (
              <div key={bank.bank_account_id} className="py-3 flex items-center justify-between gap-4">
                <div>
                  <div className="text-sm font-medium text-slate-900">{bank.bank_account_name}</div>
                  <div className="text-xs text-slate-500">
                    {bank.configured ? "Configured · next check " + bank.next_check_number : "Not configured"}
                  </div>
                </div>
                <Link
                  href={"/dashboard/accounting/bank-accounts/" + bank.bank_account_id + "/check-setup"}
                  className="text-sm text-blue-600 hover:underline"
                >
                  {bank.configured ? "Edit setup" : "Set up"}
                </Link>
              </div>
            ))}
          </div>
        )}
      </section>

      <section className="rounded-lg border border-slate-200 bg-white p-5">
        <h2 className="font-semibold text-slate-900">Report defaults</h2>
        <p className="text-sm text-slate-500 mt-1 mb-4">
          These defaults are stored now and consumed by the reporting layer as Phase 3.7 reports are built.
        </p>
        <div className="grid gap-4 md:grid-cols-3">
          <label>
            <span className="block text-sm font-medium text-slate-800 mb-1">Accounting basis</span>
            <select
              value={form.accounting_basis}
              onChange={(e) => setForm({ ...form, accounting_basis: e.target.value as "ACCRUAL" | "CASH" })}
              className="w-full border border-slate-300 rounded-md px-3 py-2 text-sm bg-white"
            >
              <option value="ACCRUAL">Accrual</option>
              <option value="CASH">Cash</option>
            </select>
            <span className="block text-xs text-slate-500 mt-1">
              Reports only. GL posting stays accrual and is never rewritten by this setting.
            </span>
          </label>
          <label>
            <span className="block text-sm font-medium text-slate-800 mb-1">Fiscal year starts</span>
            <select
              value={form.fiscal_year_start_month}
              onChange={(e) => setForm({ ...form, fiscal_year_start_month: Number(e.target.value) })}
              className="w-full border border-slate-300 rounded-md px-3 py-2 text-sm bg-white"
            >
              {MONTHS.map((month, index) => <option key={month} value={index + 1}>{month}</option>)}
            </select>
          </label>
          <label>
            <span className="block text-sm font-medium text-slate-800 mb-1">Export format</span>
            <select
              value={form.report_export_format}
              onChange={(e) => setForm({ ...form, report_export_format: e.target.value as "CSV" | "EXCEL" })}
              className="w-full border border-slate-300 rounded-md px-3 py-2 text-sm bg-white"
            >
              <option value="CSV">CSV</option>
              <option value="EXCEL">Excel</option>
            </select>
          </label>
        </div>
      </section>

      <section className="rounded-lg border border-slate-200 bg-white p-5 flex items-center justify-between gap-4">
        <div>
          <h2 className="font-semibold text-slate-900">Management Fees</h2>
          <p className="text-sm text-slate-500">Overcollection remains in its existing verified workflow.</p>
        </div>
        <Link href="/dashboard/accounting/management-fees/overcollection" className="text-sm text-blue-600 hover:underline">
          Overcollection strategy
        </Link>
      </section>

      <button
        type="button"
        onClick={() => void save()}
        disabled={saving}
        className="px-4 py-2 rounded-md bg-blue-600 text-white text-sm font-medium hover:bg-blue-700 disabled:opacity-50"
      >
        {saving ? "Saving…" : "Save Accounting Settings"}
      </button>
    </div>
  );
}
