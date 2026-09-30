"use client";

import { useEffect, useState } from "react";
import { apiGet, apiPost } from "@/lib/api";
import CommercialOperatingChargesPanel from "@/components/property/CommercialOperatingChargesPanel";

type Escalation = { id?: number; starts_on: string; monthly_base_rent: string };
type OptionRow = {
  id?: number;
  option_type: "RENEWAL" | "EXPANSION" | "TERMINATION" | "PURCHASE" | "OTHER";
  exercise_start_on: string | null;
  exercise_end_on: string | null;
  summary: string;
};
type Terms = {
  id: number; revision: number; effective_on: string; source_filename: string;
  source_status: "STAFF_LINKED_UNVERIFIED"; terms_status: "STAFF_ABSTRACTED_UNVERIFIED";
  base_rent_monthly: string | null; cam_estimate_monthly: string;
  property_tax_estimate_monthly: string; insurance_estimate_monthly: string;
  cam_share_percent: string | null; percentage_rent_rate: string | null;
  percentage_rent_breakpoint_annual: string | null; ti_allowance_total: string | null;
  co_tenancy_summary: string | null; billing_authorized: boolean;
  billing_authorized_at: string | null; billing_authorization_note: string | null;
  escalations: Escalation[]; options: OptionRow[]; is_active: boolean;
};

export default function CommercialLeaseTermsPanel({
  propertyId, abstractId, sourceAttachmentId, canEdit,
}: {
  propertyId: number; abstractId: number; sourceAttachmentId: number | null; canEdit: boolean;
}) {
  const base = `/api/properties/${propertyId}/commercial-lease-abstracts/${abstractId}/terms`;
  const [history, setHistory] = useState<Terms[]>([]);
  const [effectiveOn, setEffectiveOn] = useState("");
  const [baseRent, setBaseRent] = useState("");
  const [cam, setCam] = useState("0.00");
  const [tax, setTax] = useState("0.00");
  const [insurance, setInsurance] = useState("0.00");
  const [camShare, setCamShare] = useState("");
  const [pctRate, setPctRate] = useState("");
  const [pctBreakpoint, setPctBreakpoint] = useState("");
  const [tiAllowance, setTiAllowance] = useState("");
  const [coTenancy, setCoTenancy] = useState("");
  const [escalations, setEscalations] = useState<Escalation[]>([]);
  const [options, setOptions] = useState<OptionRow[]>([]);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [authorizationNote, setAuthorizationNote] = useState("");
  const [error, setError] = useState("");

  async function reload() {
    setHistory(await apiGet(base) as Terms[]);
  }

  useEffect(() => {
    let live = true;
    void apiGet(base).then((rows) => { if (live) setHistory(rows as Terms[]); })
      .catch((cause) => { if (live) setError(cause instanceof Error ? cause.message : "Terms unavailable."); });
    return () => { live = false; };
  }, [base]);

  async function save(event: React.FormEvent) {
    event.preventDefault();
    if (!canEdit || !sourceAttachmentId || !effectiveOn || busy) return;
    setBusy(true); setError(""); setMessage("");
    try {
      await apiPost(base, {
        source_attachment_id: sourceAttachmentId,
        effective_on: effectiveOn,
        base_rent_monthly: baseRent || null,
        cam_estimate_monthly: cam || "0.00",
        property_tax_estimate_monthly: tax || "0.00",
        insurance_estimate_monthly: insurance || "0.00",
        cam_share_percent: camShare || null,
        percentage_rent_rate: pctRate || null,
        percentage_rent_breakpoint_annual: pctBreakpoint || null,
        ti_allowance_total: tiAllowance || null,
        co_tenancy_summary: coTenancy || null,
        escalations: escalations.filter((row) => row.starts_on && row.monthly_base_rent),
        options: options.filter((row) => row.summary.trim()).map((row) => ({
          ...row,
          exercise_start_on: row.exercise_start_on || null,
          exercise_end_on: row.exercise_end_on || null,
        })),
      });
      await reload();
      setMessage("Commercial terms revision recorded from the linked private source. No billing was generated.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to record commercial terms.");
    } finally { setBusy(false); }
  }



  async function authorize(row: Terms) {
    if (!canEdit || !row.is_active || row.billing_authorized || authorizationNote.trim().length < 10 || busy) return;
    setBusy(true); setError(""); setMessage("");
    try {
      await apiPost(base + "/" + row.id + "/billing-authorization", {
        note: authorizationNote.trim(),
      });
      await reload();
      setAuthorizationNote("");
      setMessage("Current commercial terms were authorized internally for billing. This is not a platform legal certification.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to authorize commercial terms.");
    } finally { setBusy(false); }
  }

  return (
    <div className="space-y-3 border-t pt-3">
      <h3 className="font-medium text-slate-900">Commercial lease terms</h3>
      <p className="text-xs text-slate-600">
        Staff-abstracted terms remain unverified until your organization validates the source.
        Recording terms does not create rent, CAM, NNN, percentage-rent, TI, invoice, charge, or GL activity.
      </p>
      {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
      {message && <p role="status" className="text-sm text-green-700">{message}</p>}
      {history.map((row) => (
        <div key={row.id} className="rounded border p-2 text-xs">
          <div className="font-medium">Revision {row.revision} · {row.is_active ? "CURRENT" : "HISTORICAL"}</div>
          <div>{row.terms_status.replaceAll("_", " ")} · Source: {row.source_filename}</div>
          <div>Effective {row.effective_on} · Base rent {row.base_rent_monthly || "not recorded"}</div>
          <div>CAM {row.cam_estimate_monthly} · Tax {row.property_tax_estimate_monthly} · Insurance {row.insurance_estimate_monthly}</div>
          <div>CAM share {row.cam_share_percent || "not recorded"} · % rent {row.percentage_rent_rate || "not recorded"} · Breakpoint {row.percentage_rent_breakpoint_annual || "not recorded"}</div>
          <div>TI allowance {row.ti_allowance_total || "not recorded"}</div>
          <div>Billing authorization: {row.billing_authorized ? "INTERNALLY AUTHORIZED" : "NOT AUTHORIZED"}</div>
          {row.co_tenancy_summary && <div>Co-tenancy: {row.co_tenancy_summary}</div>}
          {row.escalations.map((item) => <div key={item.id}>Escalation {item.starts_on}: {item.monthly_base_rent}</div>)}
          {row.options.map((item) => <div key={item.id}>{item.option_type}: {item.summary}</div>)}
          {canEdit && row.is_active && !row.billing_authorized && <div className="mt-2 space-y-1">
            <label className="block">Internal billing authorization note
              <input value={authorizationNote} onChange={(e) => setAuthorizationNote(e.target.value)}
                className="mt-1 block w-full rounded border p-2" placeholder="Confirm source review and billing approval" />
            </label>
            <button type="button" disabled={busy || authorizationNote.trim().length < 10}
              onClick={() => { void authorize(row); }}
              className="rounded border px-3 py-2 text-blue-700 disabled:opacity-50">
              Authorize current terms for billing
            </button>
          </div>}
        </div>
      ))}
      {canEdit && !sourceAttachmentId && (
        <p className="text-sm text-amber-700">Link a private lease source document before recording terms.</p>
      )}
      {history.some((row) => row.is_active && row.billing_authorized) && (
        <CommercialOperatingChargesPanel propertyId={propertyId} abstractId={abstractId} canEdit={canEdit} />
      )}
      {canEdit && sourceAttachmentId && (
        <form onSubmit={(event) => { void save(event); }} className="space-y-2 rounded border p-3">
          <label className="block text-xs">Terms effective date
            <input required type="date" value={effectiveOn} onChange={(e) => setEffectiveOn(e.target.value)}
              className="mt-1 block rounded border p-2" />
          </label>
          <div className="grid gap-2 md:grid-cols-4">
            <Money label="Base rent monthly" value={baseRent} setValue={setBaseRent} />
            <Money label="CAM estimate monthly" value={cam} setValue={setCam} />
            <Money label="Property tax estimate monthly" value={tax} setValue={setTax} />
            <Money label="Insurance estimate monthly" value={insurance} setValue={setInsurance} />
            <Money label="CAM share percent" value={camShare} setValue={setCamShare} />
            <Money label="Percentage rent rate" value={pctRate} setValue={setPctRate} />
            <Money label="Annual percentage breakpoint" value={pctBreakpoint} setValue={setPctBreakpoint} />
            <Money label="TI allowance total" value={tiAllowance} setValue={setTiAllowance} />
          </div>
          <label className="block text-xs">Co-tenancy summary
            <textarea value={coTenancy} onChange={(e) => setCoTenancy(e.target.value)}
              className="mt-1 block w-full rounded border p-2" rows={2} />
          </label>

          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium">Rent escalations</span>
              <button type="button" className="text-xs text-blue-700"
                onClick={() => setEscalations((rows) => [...rows, { starts_on: "", monthly_base_rent: "" }])}>
                Add escalation
              </button>
            </div>
            {escalations.map((row, index) => (
              <div key={index} className="flex flex-wrap gap-2">
                <input aria-label={`Escalation ${index + 1} start`} type="date" value={row.starts_on}
                  onChange={(e) => setEscalations((rows) => rows.map((item, i) => i === index ? { ...item, starts_on: e.target.value } : item))}
                  className="rounded border p-2 text-xs" />
                <input aria-label={`Escalation ${index + 1} monthly rent`} type="number" step="0.01" min="0.01"
                  value={row.monthly_base_rent}
                  onChange={(e) => setEscalations((rows) => rows.map((item, i) => i === index ? { ...item, monthly_base_rent: e.target.value } : item))}
                  className="rounded border p-2 text-xs" />
                <button type="button" className="text-xs text-red-700"
                  onClick={() => setEscalations((rows) => rows.filter((_, i) => i !== index))}>Remove</button>
              </div>
            ))}
          </div>

          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium">Lease options</span>
              <button type="button" className="text-xs text-blue-700"
                onClick={() => setOptions((rows) => [...rows, { option_type: "RENEWAL", exercise_start_on: "", exercise_end_on: "", summary: "" }])}>
                Add option
              </button>
            </div>
            {options.map((row, index) => (
              <div key={index} className="grid gap-2 md:grid-cols-4">
                <select aria-label={`Option ${index + 1} type`} value={row.option_type}
                  onChange={(e) => setOptions((rows) => rows.map((item, i) => i === index ? { ...item, option_type: e.target.value as OptionRow["option_type"] } : item))}
                  className="rounded border p-2 text-xs">
                  {["RENEWAL", "EXPANSION", "TERMINATION", "PURCHASE", "OTHER"].map((value) => <option key={value}>{value}</option>)}
                </select>
                <input aria-label={`Option ${index + 1} start`} type="date" value={row.exercise_start_on || ""}
                  onChange={(e) => setOptions((rows) => rows.map((item, i) => i === index ? { ...item, exercise_start_on: e.target.value } : item))}
                  className="rounded border p-2 text-xs" />
                <input aria-label={`Option ${index + 1} end`} type="date" value={row.exercise_end_on || ""}
                  onChange={(e) => setOptions((rows) => rows.map((item, i) => i === index ? { ...item, exercise_end_on: e.target.value } : item))}
                  className="rounded border p-2 text-xs" />
                <input aria-label={`Option ${index + 1} summary`} value={row.summary}
                  onChange={(e) => setOptions((rows) => rows.map((item, i) => i === index ? { ...item, summary: e.target.value } : item))}
                  className="rounded border p-2 text-xs" placeholder="Source-linked option summary" />
                <button type="button" className="text-xs text-red-700"
                  onClick={() => setOptions((rows) => rows.filter((_, i) => i !== index))}>Remove option</button>
              </div>
            ))}
          </div>
          <button type="submit" disabled={busy || !effectiveOn}
            className="rounded bg-slate-900 px-3 py-2 text-sm text-white disabled:opacity-50">
            {busy ? "Saving…" : "Record terms revision"}
          </button>
        </form>
      )}
    </div>
  );
}

function Money({ label, value, setValue }: {
  label: string; value: string; setValue: (value: string) => void;
}) {
  return <label className="text-xs">{label}
    <input type="number" step="0.01" min="0" value={value}
      onChange={(e) => setValue(e.target.value)}
      className="mt-1 block w-full rounded border p-2" />
  </label>;
}
