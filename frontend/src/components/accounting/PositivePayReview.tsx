"use client";

import { useState } from "react";
import { apiGet } from "@/lib/api";

type BankRef = { id: number; name: string };
type ReviewItem = {
  check_id: number;
  check_date: string;
  check_number: string;
  recorded_payee: string;
  status: "ISSUED" | "VOID";
  nominal_amount: string;
  review_flags: string[];
};
type Preflight = {
  bank_account_id: number;
  total: number;
  issued: number;
  voided: number;
  needs_review: number;
  items: ReviewItem[];
  bank_file_format_configured: false;
  bank_file_export_available: false;
  submission_status: "NOT_SUBMITTED";
  meaning: string;
};

export default function PositivePayReview({
  account, onClose,
}: { account: BankRef; onClose: () => void }) {
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<Preflight | null>(null);

  async function review(event: React.FormEvent) {
    event.preventDefault();
    setResult(null);
    setError("");
    if (dateFrom && dateTo && dateFrom > dateTo) {
      setError("From date must not be after To date.");
      return;
    }
    setLoading(true);
    const query = new URLSearchParams();
    if (dateFrom) query.set("date_from", dateFrom);
    if (dateTo) query.set("date_to", dateTo);
    try {
      const suffix = query.toString();
      const preview = await apiGet(
        `/api/accounting/bank-accounts/${account.id}/positive-pay/preflight${suffix ? `?${suffix}` : ""}`
      ) as Preflight;
      if (
        preview.bank_account_id !== account.id ||
        preview.bank_file_export_available !== false ||
        preview.submission_status !== "NOT_SUBMITTED"
      ) {
        setError("Positive-pay review returned an unexpected state.");
        return;
      }
      setResult(preview);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to review recorded checks.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div role="dialog" aria-modal="true" aria-label="Positive-pay check review"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <section className="w-full max-w-4xl max-h-[90vh] overflow-y-auto rounded-xl bg-white p-5 shadow-xl">
        <div className="flex items-center justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold text-slate-900">Positive-pay check review</h2>
            <p className="text-sm text-slate-600">{account.name}</p>
          </div>
          <button type="button" onClick={onClose} aria-label="Close positive-pay review"
            className="rounded border border-slate-300 px-3 py-1 text-sm">Close</button>
        </div>
        <p className="mt-3 rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-950">
          Internal check issue/void review only. No bank-specific positive-pay template has been
          configured or approved. No bank-upload file is generated, no checks are sent to a bank,
          and no check, ledger or reconciliation data is changed. Obtain the bank specification
          and review the recorded checks before attempting any future file submission.
        </p>
        <form onSubmit={(event) => { void review(event); }}
          className="mt-4 flex flex-wrap items-end gap-3">
          <label className="text-sm text-slate-700">
            From check date
            <input type="date" value={dateFrom} onChange={(event) => {
              setDateFrom(event.target.value); setResult(null);
            }} className="mt-1 block rounded border border-slate-300 p-2" />
          </label>
          <label className="text-sm text-slate-700">
            Through check date
            <input type="date" value={dateTo} onChange={(event) => {
              setDateTo(event.target.value); setResult(null);
            }} className="mt-1 block rounded border border-slate-300 p-2" />
          </label>
          <button type="submit" disabled={loading}
            className="rounded bg-slate-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-60">
            {loading ? "Checking…" : "Review recorded checks"}
          </button>
        </form>
        {error && <p role="alert" className="mt-3 text-sm text-red-700">{error}</p>}
        {result && (
          <div className="mt-5">
            <div className="grid gap-2 sm:grid-cols-4 text-sm">
              {([
                ["Recorded checks", result.total],
                ["Issued", result.issued],
                ["Voided", result.voided],
                ["Need review", result.needs_review],
              ] as const).map(([label, value]) => (
                <div key={label} className="rounded border border-slate-200 p-3">
                  <div className="text-xs text-slate-500">{label}</div>
                  <div className="font-semibold">{value}</div>
                </div>
              ))}
            </div>
            <p className="mt-3 text-xs text-slate-600">
              Status: not submitted. The amounts are recorded check face amounts,
              not reconciled balances or proof of bank acceptance. Review flags identify
              missing recorded values; they do not certify a check as bank-eligible.
            </p>
            <div className="mt-3 overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="bg-slate-50">
                  <tr>
                    {["Date", "Check #", "Recorded payee", "Status", "Face amount", "Review flags"].map((name) => (
                      <th key={name} className="border-b px-3 py-2 font-medium">{name}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {result.items.map((item) => (
                    <tr key={item.check_id} className="border-b">
                      <td className="px-3 py-2">{item.check_date}</td>
                      <td className="px-3 py-2 font-mono">{item.check_number || "Missing"}</td>
                      <td className="px-3 py-2">{item.recorded_payee}</td>
                      <td className="px-3 py-2">{item.status}</td>
                      <td className="px-3 py-2 font-mono">{item.nominal_amount}</td>
                      <td className="px-3 py-2">
                        {item.review_flags.length ? item.review_flags.join("; ") : "No missing fields flagged"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {result.items.length === 0 && (
                <p className="p-4 text-sm text-slate-500">No recorded checks match these dates.</p>
              )}
            </div>
            <p className="mt-3 text-xs text-slate-600">{result.meaning}</p>
          </div>
        )}
      </section>
    </div>
  );
}
