"use client";

import { useEffect, useMemo, useState } from "react";

import { apiFetch, apiGet, apiPost, apiPut } from "@/lib/api";

type SubjectType = "ORGANIZATION" | "OWNER" | "VENDOR";
type TaxProfile = {
  id: number;
  subject_type: SubjectType;
  subject_id: number;
  tin_last4: string;
  w9_on_file: boolean;
  w9_received_on: string | null;
};
type Member = {
  id: number;
  first_name: string;
  last_name: string;
  role: string;
  is_active: boolean;
};
type Review = {
  id: number;
  tax_year: number;
  form_type: "1099-NEC" | "1099-MISC";
  income_category: "NONEMPLOYEE_COMPENSATION" | "RENTS";
  payer_profile_id: number;
  payer_tin_last4: string;
  recipient_profile_id: number;
  recipient_subject_type: "OWNER" | "VENDOR";
  recipient_subject_id: number;
  recipient_tin_last4: string;
  amount: string | number;
  source_type: "BILL" | "CHECK" | "OWNER_LEDGER" | "EXTERNAL_STATEMENT" | "OTHER";
  source_reference: string;
  source_note: string | null;
  status: "PREPARED" | "REVIEWED" | "APPROVED";
  w9_evidence_present: boolean;
  profile_changed_since_review: boolean;
  source_review_confirmed: boolean;
  threshold_review_confirmed: boolean;
  recipient_review_confirmed: boolean;
};
type Preflight = {
  record_id: number;
  tax_year: number;
  form_type: string;
  review_status: string;
  ready_for_provider_handoff: boolean;
  filing_enabled: boolean;
  submission_status: "NOT_SUBMITTED";
  blockers: string[];
};
type Classification = "NEC" | "MISC";
type ApprovalChecks = { source: boolean; threshold: boolean; recipient: boolean };

const EMPTY_CHECKS: ApprovalChecks = { source: false, threshold: false, recipient: false };

function clientKey() {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) return crypto.randomUUID();
  return "manual-" + Date.now() + "-" + Math.random().toString(36).slice(2);
}

export default function Tax1099ReviewPanel({
  profiles,
  people,
}: {
  profiles: TaxProfile[];
  people: Member[];
}) {
  const [items, setItems] = useState<Review[]>([]);
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState<number | "new" | null>(null);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [editingId, setEditingId] = useState<number | null>(null);
  const [classification, setClassification] = useState<Classification>("NEC");
  const [taxYear, setTaxYear] = useState(String(new Date().getFullYear()));
  const [registerYear, setRegisterYear] = useState(String(new Date().getFullYear()));
  const [exporting, setExporting] = useState(false);
  const [recipientProfileId, setRecipientProfileId] = useState("");
  const [amount, setAmount] = useState("");
  const [sourceType, setSourceType] = useState<Review["source_type"]>("CHECK");
  const [sourceReference, setSourceReference] = useState("");
  const [sourceNote, setSourceNote] = useState("");
  const [approvalChecks, setApprovalChecks] = useState<Record<number, ApprovalChecks>>({});
  const [preflights, setPreflights] = useState<Record<number, Preflight>>({});

  useEffect(() => {
    let active = true;
    apiGet("/api/reporting/tax-1099-reviews")
      .then((rows) => { if (active) setItems(rows as Review[]); })
      .catch((cause) => {
        if (active) setError(cause instanceof Error ? cause.message : "1099 review records unavailable.");
      })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, []);

  const payer = useMemo(
    () => profiles.find((profile) => profile.subject_type === "ORGANIZATION"),
    [profiles]
  );
  const expectedType: SubjectType = classification === "NEC" ? "VENDOR" : "OWNER";
  const recipients = useMemo(
    () => profiles.filter((profile) => profile.subject_type === expectedType),
    [profiles, expectedType]
  );

  useEffect(() => {
    if (!recipients.some((profile) => String(profile.id) === recipientProfileId)) {
      setRecipientProfileId(recipients[0] ? String(recipients[0].id) : "");
    }
  }, [recipients, recipientProfileId]);

  function recipientName(item: Review) {
    const person = people.find((user) => user.id === item.recipient_subject_id);
    if (!person) return item.recipient_subject_type + " #" + item.recipient_subject_id;
    return person.first_name + " " + person.last_name;
  }

  function resetForm() {
    setEditingId(null);
    setClassification("NEC");
    setTaxYear(String(new Date().getFullYear()));
    setAmount("");
    setSourceType("CHECK");
    setSourceReference("");
    setSourceNote("");
    const firstVendor = profiles.find((profile) => profile.subject_type === "VENDOR");
    setRecipientProfileId(firstVendor ? String(firstVendor.id) : "");
  }

  function buildPayload() {
    if (!payer) throw new Error("Create the organization payer tax profile first.");
    if (!recipientProfileId) throw new Error("Create a " + expectedType.toLowerCase() + " tax profile first.");
    const parsedYear = Number(taxYear);
    const parsedAmount = Number(amount);
    if (!Number.isInteger(parsedYear) || parsedYear < 2020 || parsedYear > 2100) {
      throw new Error("Enter a valid tax year.");
    }
    if (!Number.isFinite(parsedAmount) || parsedAmount <= 0) {
      throw new Error("Enter the manually reviewed reportable amount.");
    }
    if (!sourceReference.trim()) {
      throw new Error("A supporting source/reference is required.");
    }
    return {
      tax_year: parsedYear,
      form_type: classification === "NEC" ? "1099-NEC" : "1099-MISC",
      income_category: classification === "NEC" ? "NONEMPLOYEE_COMPENSATION" : "RENTS",
      payer_profile_id: payer.id,
      recipient_profile_id: Number(recipientProfileId),
      amount: amount.trim(),
      source_type: sourceType,
      source_reference: sourceReference.trim(),
      source_note: sourceNote.trim() || null,
    };
  }

  async function save(event: React.FormEvent) {
    event.preventDefault();
    setBusyId(editingId ?? "new");
    setError("");
    setMessage("");
    try {
      const data = buildPayload();
      const saved = editingId === null
        ? await apiPost("/api/reporting/tax-1099-reviews", { ...data, idempotency_key: clientKey() }) as Review
        : await apiPut("/api/reporting/tax-1099-reviews/" + editingId, data) as Review;
      setItems((current) => [saved, ...current.filter((item) => item.id !== saved.id)]);
      setMessage(editingId === null ? "1099 record prepared for review." : "Prepared record updated.");
      resetForm();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "1099 record could not be saved.");
    } finally {
      setBusyId(null);
    }
  }

  function beginEdit(item: Review) {
    if (item.status !== "PREPARED") return;
    setEditingId(item.id);
    setClassification(item.form_type === "1099-NEC" ? "NEC" : "MISC");
    setTaxYear(String(item.tax_year));
    setRecipientProfileId(String(item.recipient_profile_id));
    setAmount(String(item.amount));
    setSourceType(item.source_type);
    setSourceReference(item.source_reference);
    setSourceNote(item.source_note || "");
    setError("");
    setMessage("");
  }

  function replaceItem(saved: Review) {
    setItems((current) => current.map((item) => item.id === saved.id ? saved : item));
  }

  async function markReviewed(item: Review) {
    setBusyId(item.id);
    setError("");
    setMessage("");
    try {
      const saved = await apiPost("/api/reporting/tax-1099-reviews/" + item.id + "/review") as Review;
      replaceItem(saved);
      setMessage("Record marked REVIEWED. It has not been filed.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Record could not be marked reviewed.");
    } finally {
      setBusyId(null);
    }
  }

  function updateCheck(id: number, key: keyof ApprovalChecks, value: boolean) {
    setApprovalChecks((current) => ({
      ...current,
      [id]: { ...(current[id] || EMPTY_CHECKS), [key]: value },
    }));
  }

  async function approve(item: Review) {
    const checks = approvalChecks[item.id] || EMPTY_CHECKS;
    if (!checks.source || !checks.threshold || !checks.recipient) {
      setError("Complete all three approval confirmations first.");
      return;
    }
    setBusyId(item.id);
    setError("");
    setMessage("");
    try {
      const saved = await apiPost("/api/reporting/tax-1099-reviews/" + item.id + "/approve", {
        source_review_confirmed: checks.source,
        threshold_review_confirmed: checks.threshold,
        recipient_review_confirmed: checks.recipient,
      }) as Review;
      replaceItem(saved);
      setMessage("Record APPROVED and locked. IRS/provider filing is still disabled.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Record could not be approved.");
    } finally {
      setBusyId(null);
    }
  }

  async function downloadInternalRegister() {
    const year = Number(registerYear);
    if (!Number.isSafeInteger(year) || year < 2020 || year > 2100) {
      setError("Enter a valid report tax year.");
      return;
    }
    setExporting(true);
    setError("");
    setMessage("");
    try {
      const response = await apiFetch(
        "/api/reporting/tax-1099-reviews/register.csv?tax_year=" + year,
        { method: "GET", headers: { Accept: "text/csv" } }
      );
      if (!response.ok) throw new Error("Internal register not available (" + response.status + ").");
      const blob = await response.blob();
      const fileUrl = URL.createObjectURL(blob);
      const element = document.createElement("a");
      element.href = fileUrl;
      element.download = "1099-internal-review-not-for-irs-" + year + ".csv";
      element.click();
      URL.revokeObjectURL(fileUrl);
      setMessage("Internal review register downloaded. This CSV is NOT an IRS or provider submission.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Register download failed.");
    } finally {
      setExporting(false);
    }
  }

  async function checkPreflight(item: Review) {
    setBusyId(item.id);
    setError("");
    setMessage("");
    try {
      const result = await apiGet(
        "/api/reporting/tax-1099-reviews/" + item.id + "/preflight"
      ) as Preflight;
      setPreflights((current) => ({ ...current, [item.id]: result }));
      setMessage("Local prerequisite check complete. No tax return has been submitted.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to check local prerequisites.");
    } finally {
      setBusyId(null);
    }
  }

  return (
    <section className="rounded-xl border border-slate-200 bg-white p-5">
      <h2 className="text-lg font-semibold text-slate-900">Manual 1099 data review</h2>
      <p className="mt-1 text-sm text-slate-600">
        Enter only an amount you reviewed from a documented source. The application does not
        calculate reportable 1099 amounts from bills, checks, owner payouts, or the general ledger.
      </p>
      <div className="mt-3 rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-950">
        No threshold is applied automatically. Before approval, review the selected tax year,
        form instructions, thresholds, exceptions, payer/recipient classification, and supporting records.
        Approval locks this preparation record but does not file it.
      </div>

      <div className="mt-3 flex flex-wrap items-end gap-3 rounded-lg border border-slate-200 bg-slate-50 p-3 print:hidden">
        <label className="text-sm font-medium text-slate-700">
          Internal register tax year
          <input type="number" min={2020} max={2100} value={registerYear}
            onChange={(event) => setRegisterYear(event.target.value)}
            className="mt-1 block w-28 rounded-lg border border-slate-300 p-2" />
        </label>
        <button type="button" disabled={exporting || loading} onClick={() => { void downloadInternalRegister(); }}
          className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm font-medium text-slate-800 disabled:opacity-50">
          {exporting ? "Exporting…" : "Download internal review CSV"}
        </button>
        <span className="text-xs font-medium text-amber-900">
          Masked IDs and preparation statuses only. Not for IRIS upload or tax filing.
        </span>
      </div>
      {error && <p role="alert" className="mt-3 rounded-lg border border-red-200 p-3 text-sm text-red-700">{error}</p>}
      {message && <p role="status" className="mt-3 rounded-lg border border-green-200 p-3 text-sm text-green-700">{message}</p>}

      <form onSubmit={(event) => { void save(event); }} className="mt-4 space-y-3">
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          <label className="text-sm font-medium text-slate-700">
            1099 classification
            <select value={classification} onChange={(event) => setClassification(event.target.value as Classification)}
              className="mt-1 block w-full rounded-lg border border-slate-300 p-2">
              <option value="NEC">1099-NEC · Nonemployee compensation · Vendor</option>
              <option value="MISC">1099-MISC · Rents · Owner</option>
            </select>
          </label>
          <label className="text-sm font-medium text-slate-700">
            Tax year
            <input required type="number" min={2020} max={2100} value={taxYear}
              onChange={(event) => setTaxYear(event.target.value)}
              className="mt-1 block w-full rounded-lg border border-slate-300 p-2" />
          </label>
          <label className="text-sm font-medium text-slate-700">
            Recipient taxpayer profile
            <select required value={recipientProfileId} onChange={(event) => setRecipientProfileId(event.target.value)}
              className="mt-1 block w-full rounded-lg border border-slate-300 p-2">
              {recipients.length === 0 && <option value="">No {expectedType.toLowerCase()} profile available</option>}
              {recipients.map((profile) => {
                const person = people.find((user) => user.id === profile.subject_id);
                const name = person ? person.first_name + " " + person.last_name : expectedType + " #" + profile.subject_id;
                return <option key={profile.id} value={profile.id}>{name} · TIN ending {profile.tin_last4}</option>;
              })}
            </select>
          </label>
          <label className="text-sm font-medium text-slate-700">
            Manually reviewed amount
            <input required type="number" min="0.01" step="0.01" value={amount}
              onChange={(event) => setAmount(event.target.value)}
              className="mt-1 block w-full rounded-lg border border-slate-300 p-2" />
          </label>
          <label className="text-sm font-medium text-slate-700">
            Supporting source
            <select value={sourceType} onChange={(event) => setSourceType(event.target.value as Review["source_type"])}
              className="mt-1 block w-full rounded-lg border border-slate-300 p-2">
              <option value="BILL">Bill review</option>
              <option value="CHECK">Check register review</option>
              <option value="OWNER_LEDGER">Owner ledger review</option>
              <option value="EXTERNAL_STATEMENT">External statement</option>
              <option value="OTHER">Other documented source</option>
            </select>
          </label>
          <label className="text-sm font-medium text-slate-700">
            Supporting reference
            <input required maxLength={160} value={sourceReference}
              onChange={(event) => setSourceReference(event.target.value)}
              placeholder="Example: Check register review #1042"
              className="mt-1 block w-full rounded-lg border border-slate-300 p-2" />
          </label>
        </div>
        <label className="block text-sm font-medium text-slate-700">
          Review note (optional; do not enter TINs)
          <textarea maxLength={1000} value={sourceNote} onChange={(event) => setSourceNote(event.target.value)}
            className="mt-1 block min-h-20 w-full rounded-lg border border-slate-300 p-2" />
        </label>
        {!payer && (
          <p className="text-sm text-amber-700">Create the encrypted organization payer profile before preparing a record.</p>
        )}
        <div className="flex flex-wrap gap-2">
          <button type="submit" disabled={busyId !== null || !payer || !recipientProfileId}
            className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50">
            {busyId === (editingId ?? "new") ? "Saving…" : editingId === null ? "Prepare record" : "Update prepared record"}
          </button>
          {editingId !== null && (
            <button type="button" onClick={resetForm} className="rounded-lg border px-4 py-2 text-sm">
              Cancel edit
            </button>
          )}
        </div>
      </form>

      <div className="mt-6 border-t border-slate-200 pt-4">
        <h3 className="text-sm font-semibold uppercase tracking-wide text-slate-500">Review queue</h3>
        {loading && <p className="mt-2 text-sm text-slate-500">Loading review records…</p>}
        {!loading && items.length === 0 && <p className="mt-2 text-sm text-slate-500">No 1099 review records yet.</p>}
        <div className="mt-3 space-y-3">
          {items.map((item) => {
            const checks = approvalChecks[item.id] || EMPTY_CHECKS;
            return (
              <article key={item.id} className="rounded-lg border border-slate-200 p-4">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <p className="font-semibold text-slate-900">
                      {item.form_type} · {item.income_category === "RENTS" ? "Rents" : "Nonemployee compensation"} · {item.tax_year}
                    </p>
                    <p className="mt-1 text-sm text-slate-600">
                      {recipientName(item)} · recipient TIN ending {item.recipient_tin_last4} · payer TIN ending {item.payer_tin_last4}
                    </p>
                    <p className="text-sm text-slate-600">
                      Amount {"$"}{Number(item.amount).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                      {" · "}{item.source_type}: {item.source_reference}
                    </p>
                    <p className="mt-1 text-xs text-slate-500">
                      Signed W-9 evidence: {item.w9_evidence_present ? "archived" : "missing"} · Status: {item.status}
                      {item.profile_changed_since_review && " · TAXPAYER PROFILE CHANGED — RE-REVIEW REQUIRED"}
                    </p>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {item.status === "PREPARED" && (
                      <>
                        <button type="button" disabled={busyId !== null} onClick={() => beginEdit(item)}
                          className="rounded-md border px-3 py-1.5 text-sm disabled:opacity-50">Edit</button>
                        <button type="button" disabled={busyId !== null || !item.w9_evidence_present}
                          onClick={() => { void markReviewed(item); }}
                          className="rounded-md bg-slate-900 px-3 py-1.5 text-sm text-white disabled:opacity-50">
                          {busyId === item.id ? "Working…" : "Mark reviewed"}
                        </button>
                      </>
                    )}
                    {item.status === "REVIEWED" && item.profile_changed_since_review && (
                      <button type="button" disabled={busyId !== null || !item.w9_evidence_present}
                        onClick={() => { void markReviewed(item); }}
                        className="rounded-md bg-amber-100 px-3 py-1.5 text-sm font-medium text-amber-950 disabled:opacity-50">
                        Re-review changed taxpayer profile
                      </button>
                    )}
                    <button type="button" disabled={busyId !== null}
                      onClick={() => { void checkPreflight(item); }}
                      className="rounded-md border px-3 py-1.5 text-sm disabled:opacity-50">
                      {busyId === item.id ? "Checking…" : "Check provider prerequisites"}
                    </button>
                    {item.status === "APPROVED" && (
                      <span className={item.profile_changed_since_review
                        ? "rounded-md bg-red-50 px-3 py-1.5 text-sm font-medium text-red-800"
                        : "rounded-md bg-green-50 px-3 py-1.5 text-sm font-medium text-green-800"}>
                        {item.profile_changed_since_review
                          ? "Previous approval STALE · create a corrected review · not filed"
                          : "Approved · locked · not filed"}
                      </span>
                    )}
                  </div>
                </div>
                {preflights[item.id] && (
                  <div className="mt-3 rounded-lg border border-slate-200 bg-slate-50 p-3 text-sm">
                    <p className="font-semibold text-slate-800">
                      {preflights[item.id].ready_for_provider_handoff
                        ? "Local prerequisites recorded · filing not enabled"
                        : "Prerequisites still missing"}
                    </p>
                    <p className="mt-1 text-slate-600">
                      No IRS/provider transmission, recipient delivery or form generation has occurred.
                    </p>
                    {preflights[item.id].blockers.length > 0 && (
                      <ul className="mt-2 list-disc pl-5 text-amber-900">
                        {preflights[item.id].blockers.map((blocker, index) => (
                          <li key={index}>{blocker}</li>
                        ))}
                      </ul>
                    )}
                  </div>
                )}
                {item.status === "REVIEWED" && !item.profile_changed_since_review && (
                  <fieldset className="mt-3 rounded-lg bg-slate-50 p-3">
                    <legend className="text-sm font-semibold text-slate-800">Approval checklist</legend>
                    <div className="mt-2 grid gap-2 text-sm text-slate-700">
                      <label className="flex gap-2">
                        <input type="checkbox" checked={checks.source}
                          onChange={(event) => updateCheck(item.id, "source", event.target.checked)} />
                        I reviewed the entered amount against the supporting source/reference.
                      </label>
                      <label className="flex gap-2">
                        <input type="checkbox" checked={checks.threshold}
                          onChange={(event) => updateCheck(item.id, "threshold", event.target.checked)} />
                        I reviewed the applicable tax-year threshold and exceptions; the system did not decide eligibility.
                      </label>
                      <label className="flex gap-2">
                        <input type="checkbox" checked={checks.recipient}
                          onChange={(event) => updateCheck(item.id, "recipient", event.target.checked)} />
                        I verified the payer, recipient, form/category, taxpayer profile, and signed W-9 evidence.
                      </label>
                    </div>
                    <button type="button" disabled={busyId !== null || !checks.source || !checks.threshold || !checks.recipient}
                      onClick={() => { void approve(item); }}
                      className="mt-3 rounded-md bg-slate-900 px-3 py-1.5 text-sm text-white disabled:opacity-50">
                      {busyId === item.id ? "Approving…" : "Approve and lock"}
                    </button>
                  </fieldset>
                )}
              </article>
            );
          })}
        </div>
      </div>
    </section>
  );
}
