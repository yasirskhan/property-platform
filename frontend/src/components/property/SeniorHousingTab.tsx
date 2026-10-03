"use client";

import { FormEvent, useEffect, useState } from "react";
import { apiDelete, apiGet, apiPost } from "@/lib/api";

type AgeRestriction = {
  id: number;
  restriction_type: "AGE_55_PLUS" | "AGE_62_PLUS" | "OTHER_RECORDED";
  label: string;
  minimum_age: number | null;
  recorded_authority: string | null;
  reference_identifier: string | null;
  effective_start: string | null;
  effective_end: string | null;
  notes: string | null;
};

type CareResource = {
  id: number;
  resource_type: "CARE_COORDINATION" | "TRANSPORTATION" | "MEALS" | "SOCIAL_SERVICES" | "OTHER";
  provider_name: string;
  contact_name: string | null;
  phone: string | null;
  email: string | null;
  reference_url: string | null;
  availability_notes: string | null;
};

type HudProgram = {
  id: number;
  program_type: "HUD_202" | "HUD_811";
  label: string;
  recorded_authority: string | null;
  reference_identifier: string | null;
  readiness_status: "REFERENCE_ONLY" | "EVIDENCE_PENDING" | "EVIDENCE_RECORDED";
  evidence_reference: string | null;
  evidence_date: string | null;
  effective_start: string | null;
  effective_end: string | null;
  notes: string | null;
};

export default function SeniorHousingTab({
  propertyId,
  canEdit,
}: {
  propertyId: number;
  canEdit: boolean;
}) {
  const [ages, setAges] = useState<AgeRestriction[]>([]);
  const [care, setCare] = useState<CareResource[]>([]);
  const [hud, setHud] = useState<HudProgram[]>([]);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);

  const [ageType, setAgeType] = useState<AgeRestriction["restriction_type"]>("AGE_55_PLUS");
  const [ageLabel, setAgeLabel] = useState("");
  const [ageAuthority, setAgeAuthority] = useState("");
  const [ageReference, setAgeReference] = useState("");
  const [ageStart, setAgeStart] = useState("");
  const [ageEnd, setAgeEnd] = useState("");

  const [careType, setCareType] = useState<CareResource["resource_type"]>("CARE_COORDINATION");
  const [providerName, setProviderName] = useState("");
  const [contactName, setContactName] = useState("");
  const [carePhone, setCarePhone] = useState("");
  const [careEmail, setCareEmail] = useState("");
  const [careUrl, setCareUrl] = useState("");
  const [careNotes, setCareNotes] = useState("");

  const [hudType, setHudType] = useState<HudProgram["program_type"]>("HUD_202");
  const [hudLabel, setHudLabel] = useState("");
  const [hudAuthority, setHudAuthority] = useState("");
  const [hudReference, setHudReference] = useState("");
  const [hudStatus, setHudStatus] = useState<HudProgram["readiness_status"]>("REFERENCE_ONLY");
  const [hudEvidence, setHudEvidence] = useState("");
  const [hudEvidenceDate, setHudEvidenceDate] = useState("");
  const [hudStart, setHudStart] = useState("");
  const [hudEnd, setHudEnd] = useState("");

  async function load() {
    const [ageRows, careRows, hudRows] = await Promise.all([
      apiGet(`/api/properties/${propertyId}/senior-housing/age-restrictions`),
      apiGet(`/api/properties/${propertyId}/senior-housing/care-resources`),
      apiGet(`/api/properties/${propertyId}/senior-housing/hud-programs`),
    ]);
    setAges(ageRows as AgeRestriction[]);
    setCare(careRows as CareResource[]);
    setHud(hudRows as HudProgram[]);
  }

  useEffect(() => {
    let active = true;
    void (async () => {
      try {
        await load();
        if (active) setError("");
      } catch (cause) {
        if (active) setError(cause instanceof Error ? cause.message : "Senior Housing unavailable.");
      }
    })();
    return () => {
      active = false;
    };
  }, [propertyId]);

  async function run(action: () => Promise<void>) {
    setBusy(true);
    setError("");
    setMessage("");
    try {
      await action();
      await load();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Senior Housing action failed.");
    } finally {
      setBusy(false);
    }
  }

  async function createAge(event: FormEvent) {
    event.preventDefault();
    await run(async () => {
      await apiPost(`/api/properties/${propertyId}/senior-housing/age-restrictions`, {
        restriction_type: ageType,
        label: ageLabel,
        minimum_age: ageType === "AGE_55_PLUS" ? 55 : ageType === "AGE_62_PLUS" ? 62 : undefined,
        recorded_authority: ageAuthority || undefined,
        reference_identifier: ageReference || undefined,
        effective_start: ageStart || undefined,
        effective_end: ageEnd || undefined,
      });
      setAgeLabel("");
      setMessage("Age-restriction reference recorded; resident eligibility was not determined.");
    });
  }

  async function createCare(event: FormEvent) {
    event.preventDefault();
    await run(async () => {
      await apiPost(`/api/properties/${propertyId}/senior-housing/care-resources`, {
        resource_type: careType,
        provider_name: providerName,
        contact_name: contactName || undefined,
        phone: carePhone || undefined,
        email: careEmail || undefined,
        reference_url: careUrl || undefined,
        availability_notes: careNotes || undefined,
      });
      setProviderName("");
      setContactName("");
      setCarePhone("");
      setCareEmail("");
      setCareUrl("");
      setCareNotes("");
      setMessage("Care resource recorded as a property-level directory reference.");
    });
  }

  async function createHud(event: FormEvent) {
    event.preventDefault();
    await run(async () => {
      await apiPost(`/api/properties/${propertyId}/senior-housing/hud-programs`, {
        program_type: hudType,
        label: hudLabel,
        recorded_authority: hudAuthority || undefined,
        reference_identifier: hudReference || undefined,
        readiness_status: hudStatus,
        evidence_reference: hudEvidence || undefined,
        evidence_date: hudEvidenceDate || undefined,
        effective_start: hudStart || undefined,
        effective_end: hudEnd || undefined,
      });
      setHudLabel("");
      setMessage("HUD 202/811 reference recorded; HUD eligibility or funding was not certified.");
    });
  }

  async function archive(kind: "age-restrictions" | "care-resources" | "hud-programs", id: number) {
    if (!window.confirm("Archive this staff-recorded Senior Housing reference?")) return;
    await run(async () => {
      await apiDelete(`/api/properties/${propertyId}/senior-housing/${kind}/${id}`);
      setMessage("Senior Housing reference archived.");
    });
  }

  return (
    <section className="space-y-6">
      <div className="rounded-xl border bg-white p-5">
        <h2 className="text-lg font-semibold text-slate-900">Senior Housing</h2>
        <p className="mt-1 text-sm text-slate-600">
          Staff-recorded age-restriction references, property-level care resource directory entries,
          and HUD 202/811 readiness references. These records do not determine resident eligibility,
          store diagnoses or treatment plans, certify Fair Housing/HOPA compliance, establish HUD
          funding or subsidy status, or create accounting entries.
        </p>
      </div>

      {message && <p role="status" className="text-sm text-green-700">{message}</p>}
      {error && <p role="alert" className="text-sm text-red-700">{error}</p>}

      <div className="space-y-4 rounded-xl border bg-white p-5">
        <h3 className="font-semibold text-slate-900">Age-restriction references</h3>
        {canEdit && (
          <form className="grid gap-3 md:grid-cols-3" onSubmit={createAge}>
            <label className="text-sm">Restriction type
              <select aria-label="Senior restriction type" className="mt-1 w-full rounded border px-3 py-2" value={ageType} onChange={(e) => setAgeType(e.target.value as AgeRestriction["restriction_type"])}>
                <option value="AGE_55_PLUS">Recorded 55+</option>
                <option value="AGE_62_PLUS">Recorded 62+</option>
                <option value="OTHER_RECORDED">Other recorded restriction</option>
              </select>
            </label>
            <label className="text-sm">Staff label
              <input aria-label="Senior restriction label" required className="mt-1 w-full rounded border px-3 py-2" value={ageLabel} onChange={(e) => setAgeLabel(e.target.value)} />
            </label>
            <label className="text-sm">Recorded authority
              <input aria-label="Senior restriction authority" className="mt-1 w-full rounded border px-3 py-2" value={ageAuthority} onChange={(e) => setAgeAuthority(e.target.value)} />
            </label>
            <label className="text-sm">Reference identifier
              <input aria-label="Senior restriction reference" className="mt-1 w-full rounded border px-3 py-2" value={ageReference} onChange={(e) => setAgeReference(e.target.value)} />
            </label>
            <label className="text-sm">Effective start
              <input aria-label="Senior restriction start date" type="date" className="mt-1 w-full rounded border px-3 py-2" value={ageStart} onChange={(e) => setAgeStart(e.target.value)} />
            </label>
            <label className="text-sm">Effective end
              <input aria-label="Senior restriction end date" type="date" className="mt-1 w-full rounded border px-3 py-2" value={ageEnd} onChange={(e) => setAgeEnd(e.target.value)} />
            </label>
            <button disabled={busy} className="rounded border px-4 py-2 text-sm font-medium md:col-span-3">Record age-restriction reference</button>
          </form>
        )}
        <div aria-label="Senior age restriction list" className="space-y-2">
          {ages.length === 0 ? <p className="text-sm text-slate-500">No age-restriction references recorded.</p> : ages.map((row) => (
            <div key={row.id} className="flex flex-wrap items-center justify-between gap-3 rounded border p-3 text-sm">
              <div><strong>{row.label}</strong> · {row.restriction_type} · minimum age {row.minimum_age ?? "not recorded"} · {row.recorded_authority || "authority not recorded"}</div>
              {canEdit && <button type="button" disabled={busy} className="text-xs text-red-700" onClick={() => void archive("age-restrictions", row.id)}>Archive</button>}
            </div>
          ))}
        </div>
      </div>

      <div className="space-y-4 rounded-xl border bg-white p-5">
        <h3 className="font-semibold text-slate-900">Care coordination resources</h3>
        <p className="text-xs text-slate-500">Property-level directory only; do not enter resident medical or treatment information.</p>
        {canEdit && (
          <form className="grid gap-3 md:grid-cols-3" onSubmit={createCare}>
            <label className="text-sm">Resource type
              <select aria-label="Senior care resource type" className="mt-1 w-full rounded border px-3 py-2" value={careType} onChange={(e) => setCareType(e.target.value as CareResource["resource_type"])}>
                <option value="CARE_COORDINATION">Care coordination</option>
                <option value="TRANSPORTATION">Transportation</option>
                <option value="MEALS">Meals</option>
                <option value="SOCIAL_SERVICES">Social services</option>
                <option value="OTHER">Other</option>
              </select>
            </label>
            <label className="text-sm">Provider name
              <input aria-label="Senior care provider name" required className="mt-1 w-full rounded border px-3 py-2" value={providerName} onChange={(e) => setProviderName(e.target.value)} />
            </label>
            <label className="text-sm">Contact name
              <input aria-label="Senior care contact name" className="mt-1 w-full rounded border px-3 py-2" value={contactName} onChange={(e) => setContactName(e.target.value)} />
            </label>
            <label className="text-sm">Phone
              <input aria-label="Senior care phone" className="mt-1 w-full rounded border px-3 py-2" value={carePhone} onChange={(e) => setCarePhone(e.target.value)} />
            </label>
            <label className="text-sm">Email
              <input aria-label="Senior care email" type="email" className="mt-1 w-full rounded border px-3 py-2" value={careEmail} onChange={(e) => setCareEmail(e.target.value)} />
            </label>
            <label className="text-sm">Reference URL
              <input aria-label="Senior care reference URL" className="mt-1 w-full rounded border px-3 py-2" value={careUrl} onChange={(e) => setCareUrl(e.target.value)} />
            </label>
            <label className="text-sm md:col-span-3">Availability notes
              <textarea aria-label="Senior care availability notes" className="mt-1 w-full rounded border px-3 py-2" value={careNotes} onChange={(e) => setCareNotes(e.target.value)} />
            </label>
            <button disabled={busy} className="rounded border px-4 py-2 text-sm font-medium md:col-span-3">Record care resource</button>
          </form>
        )}
        <div aria-label="Senior care resource list" className="space-y-2">
          {care.length === 0 ? <p className="text-sm text-slate-500">No care resources recorded.</p> : care.map((row) => (
            <div key={row.id} className="flex flex-wrap items-center justify-between gap-3 rounded border p-3 text-sm">
              <div><strong>{row.provider_name}</strong> · {row.resource_type} · {row.contact_name || "contact not recorded"}</div>
              {canEdit && <button type="button" disabled={busy} className="text-xs text-red-700" onClick={() => void archive("care-resources", row.id)}>Archive</button>}
            </div>
          ))}
        </div>
      </div>

      <div className="space-y-4 rounded-xl border bg-white p-5">
        <h3 className="font-semibold text-slate-900">HUD 202/811 readiness references</h3>
        <p className="text-xs text-slate-500">Recorded references only; this does not certify HUD eligibility, funding, occupancy, subsidy, or payment status.</p>
        {canEdit && (
          <form className="grid gap-3 md:grid-cols-3" onSubmit={createHud}>
            <label className="text-sm">Program
              <select aria-label="Senior HUD program type" className="mt-1 w-full rounded border px-3 py-2" value={hudType} onChange={(e) => setHudType(e.target.value as HudProgram["program_type"])}>
                <option value="HUD_202">HUD 202</option>
                <option value="HUD_811">HUD 811</option>
              </select>
            </label>
            <label className="text-sm">Staff label
              <input aria-label="Senior HUD label" required className="mt-1 w-full rounded border px-3 py-2" value={hudLabel} onChange={(e) => setHudLabel(e.target.value)} />
            </label>
            <label className="text-sm">Readiness status
              <select aria-label="Senior HUD readiness status" className="mt-1 w-full rounded border px-3 py-2" value={hudStatus} onChange={(e) => setHudStatus(e.target.value as HudProgram["readiness_status"])}>
                <option value="REFERENCE_ONLY">Reference only</option>
                <option value="EVIDENCE_PENDING">Evidence pending</option>
                <option value="EVIDENCE_RECORDED">Evidence recorded</option>
              </select>
            </label>
            <label className="text-sm">Recorded authority
              <input aria-label="Senior HUD authority" className="mt-1 w-full rounded border px-3 py-2" value={hudAuthority} onChange={(e) => setHudAuthority(e.target.value)} />
            </label>
            <label className="text-sm">Reference identifier
              <input aria-label="Senior HUD reference identifier" className="mt-1 w-full rounded border px-3 py-2" value={hudReference} onChange={(e) => setHudReference(e.target.value)} />
            </label>
            <label className="text-sm">Evidence reference
              <input aria-label="Senior HUD evidence reference" className="mt-1 w-full rounded border px-3 py-2" value={hudEvidence} onChange={(e) => setHudEvidence(e.target.value)} />
            </label>
            <label className="text-sm">Evidence date
              <input aria-label="Senior HUD evidence date" type="date" className="mt-1 w-full rounded border px-3 py-2" value={hudEvidenceDate} onChange={(e) => setHudEvidenceDate(e.target.value)} />
            </label>
            <label className="text-sm">Effective start
              <input aria-label="Senior HUD effective start" type="date" className="mt-1 w-full rounded border px-3 py-2" value={hudStart} onChange={(e) => setHudStart(e.target.value)} />
            </label>
            <label className="text-sm">Effective end
              <input aria-label="Senior HUD effective end" type="date" className="mt-1 w-full rounded border px-3 py-2" value={hudEnd} onChange={(e) => setHudEnd(e.target.value)} />
            </label>
            <button disabled={busy} className="rounded border px-4 py-2 text-sm font-medium md:col-span-3">Record HUD 202/811 reference</button>
          </form>
        )}
        <div aria-label="Senior HUD program list" className="space-y-2">
          {hud.length === 0 ? <p className="text-sm text-slate-500">No HUD 202/811 references recorded.</p> : hud.map((row) => (
            <div key={row.id} className="flex flex-wrap items-center justify-between gap-3 rounded border p-3 text-sm">
              <div><strong>{row.label}</strong> · {row.program_type} · {row.readiness_status} · {row.evidence_reference || "evidence reference not recorded"}</div>
              {canEdit && <button type="button" disabled={busy} className="text-xs text-red-700" onClick={() => void archive("hud-programs", row.id)}>Archive</button>}
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
