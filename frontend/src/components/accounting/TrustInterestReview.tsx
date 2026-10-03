"use client";

import { useEffect, useState } from "react";
import { apiGet, apiPut } from "@/lib/api";

type BankRef = { id: number; name: string; account_type: "OPERATING" | "ESCROW" };
type ProposedRecipient = "UNDETERMINED" | "TENANT" | "STATE" | "HOUSING_FUND" | "OTHER";
type Readiness = {
  bank_account_id: number;
  bank_account_type: string;
  configured: boolean;
  jurisdiction: string | null;
  proposed_recipient: ProposedRecipient;
  basis_reference_recorded: boolean;
  legal_review_required: true;
  interest_allocation_enabled: false;
  interest_posting_enabled: false;
  updated_at: string | null;
};

const RECIPIENTS: { value: ProposedRecipient; label: string }[] = [
  { value: "UNDETERMINED", label: "Undetermined — further review" },
  { value: "TENANT", label: "Tenant (proposed)" },
  { value: "STATE", label: "State (proposed)" },
  { value: "HOUSING_FUND", label: "Housing fund (proposed)" },
  { value: "OTHER", label: "Other (proposed)" },
];

export default function TrustInterestReview({
  account, onClose,
}: { account: BankRef; onClose: () => void }) {
  const [readiness, setReadiness] = useState<Readiness | null>(null);
  const [recipient, setRecipient] = useState<ProposedRecipient>("UNDETERMINED");
  const [jurisdiction, setJurisdiction] = useState("");
  const [basisReference, setBasisReference] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError("");
    void (async () => {
      try {
        const result = await apiGet(`/api/accounting/bank-accounts/${account.id}/interest-readiness`) as Readiness;
        if (!active) return;
        setReadiness(result);
        setRecipient(result.proposed_recipient);
        setJurisdiction(result.jurisdiction || "");
        setBasisReference("");
      } catch (cause) {
        if (active) setError(cause instanceof Error ? cause.message : "Interest readiness unavailable.");
      } finally {
        if (active) setLoading(false);
      }
    })();
    return () => { active = false; };
  }, [account.id]);

  async function save(event: React.FormEvent) {
    event.preventDefault();
    setError("");
    setMessage("");
    setSaving(true);
    try {
      const result = await apiPut(
        `/api/accounting/bank-accounts/${account.id}/interest-readiness`,
        {
          proposed_recipient: recipient,
          jurisdiction: jurisdiction.trim() || null,
          basis_reference: basisReference.trim() || null,
        },
      ) as Readiness;
      setReadiness(result);
      setBasisReference("");
      setMessage("Readiness note saved. Legal review is still required; no interest was posted.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not save interest readiness.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div role="dialog" aria-modal="true" aria-label="Trust-interest readiness"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <section className="w-full max-w-xl max-h-[90vh] overflow-y-auto rounded-xl bg-white p-5 shadow-xl">
        <div className="flex items-center justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold text-slate-900">Trust-interest readiness</h2>
            <p className="text-sm text-slate-600">{account.name} · {account.account_type}</p>
          </div>
          <button type="button" onClick={onClose} aria-label="Close interest readiness"
            className="rounded border border-slate-300 px-3 py-1 text-sm">Close</button>
        </div>
        <p className="mt-3 rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-950">
          This is an internal proposal only. Confirm the applicable jurisdiction, lease and
          custody rules with qualified counsel before establishing entitlement. Nothing on
          this page calculates interest, moves trust money or posts to the ledger.
        </p>
        {loading && <p className="mt-3 text-sm text-slate-600">Loading…</p>}
        {error && <p role="alert" className="mt-3 text-sm text-red-700">{error}</p>}
        {message && <p role="status" className="mt-3 text-sm text-green-700">{message}</p>}
        {!loading && readiness && (
          <>
            <div className="mt-3 rounded-lg bg-slate-50 p-3 text-sm text-slate-700">
              {readiness.configured ? "Staff proposal recorded." : "No staff proposal recorded."}
              {" "}Independent legal review is still required.
              {readiness.basis_reference_recorded && (
                <p className="mt-1 text-xs text-slate-600">
                  A supporting reference was recorded. Re-enter it to change this proposal;
                  the original reference is not returned to the browser.
                </p>
              )}
            </div>
            <form onSubmit={(event) => { void save(event); }} className="mt-4 space-y-3">
              <label className="block text-sm font-medium text-slate-700">
                Proposed interest recipient
                <select value={recipient} onChange={(event) => setRecipient(event.target.value as ProposedRecipient)}
                  className="mt-1 w-full rounded border border-slate-300 p-2">
                  {RECIPIENTS.map((choice) => <option key={choice.value} value={choice.value}>{choice.label}</option>)}
                </select>
              </label>
              <label className="block text-sm font-medium text-slate-700">
                Jurisdiction (as recorded by staff)
                <input value={jurisdiction} maxLength={80}
                  required={recipient !== "UNDETERMINED"}
                  onChange={(event) => setJurisdiction(event.target.value)}
                  className="mt-1 w-full rounded border border-slate-300 p-2"
                  placeholder="State or relevant jurisdiction" />
              </label>
              <label className="block text-sm font-medium text-slate-700">
                Source or review reference (not taxpayer or bank data)
                <input value={basisReference} maxLength={200}
                  required={recipient !== "UNDETERMINED"}
                  onChange={(event) => setBasisReference(event.target.value)}
                  className="mt-1 w-full rounded border border-slate-300 p-2"
                  placeholder="Reviewed source reference" />
              </label>
              <button type="submit" disabled={saving}
                className="rounded bg-slate-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-60">
                {saving ? "Saving…" : "Save staff proposal"}
              </button>
            </form>
          </>
        )}
      </section>
    </div>
  );
}
