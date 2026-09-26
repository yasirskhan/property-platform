"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

import { apiGet, apiPut } from "@/lib/api";

type SubjectType = "ORGANIZATION" | "OWNER" | "VENDOR";
type TaxClass = "INDIVIDUAL" | "SOLE_PROPRIETOR" | "C_CORP" | "S_CORP" | "PARTNERSHIP" | "TRUST_ESTATE" | "LLC" | "OTHER";
type TinType = "SSN" | "EIN" | "ITIN";
type Member = { id: number; first_name: string; last_name: string; role: string; is_active: boolean };
type CurrentUser = { id: number; organization_id: number; role: string };
type TaxProfile = {
  id: number; subject_type: SubjectType; subject_id: number;
  tin_last4: string; w9_on_file: boolean; w9_received_on: string | null;
  updated_at: string;
};

function subjectKey(type: SubjectType, id: number) {
  return `${type}:${id}`;
}

export default function TaxPreparationPage() {
  const [viewer, setViewer] = useState<CurrentUser | null>(null);
  const [people, setPeople] = useState<Member[]>([]);
  const [profiles, setProfiles] = useState<TaxProfile[]>([]);
  const [subject, setSubject] = useState("");
  const [legalName, setLegalName] = useState("");
  const [businessName, setBusinessName] = useState("");
  const [taxClass, setTaxClass] = useState<TaxClass | "">("");
  const [tinType, setTinType] = useState<TinType | "">("");
  const [tin, setTin] = useState("");
  const [address1, setAddress1] = useState("");
  const [address2, setAddress2] = useState("");
  const [city, setCity] = useState("");
  const [state, setState] = useState("");
  const [postal, setPostal] = useState("");
  const [country, setCountry] = useState("USA");
  const [w9OnFile, setW9OnFile] = useState(false);
  const [receivedOn, setReceivedOn] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  useEffect(() => {
    let active = true;
    async function load() {
      try {
        const me = await apiGet("/auth/me") as CurrentUser;
        if (!active) return;
        setViewer(me);
        if (me.role !== "ADMIN") {
          setError("Only organization administrators can manage taxpayer profiles.");
          return;
        }
        const [users, saved] = await Promise.all([
          apiGet("/users") as Promise<Member[]>,
          apiGet("/api/reporting/tax-profiles") as Promise<TaxProfile[]>,
        ]);
        if (!active) return;
        setPeople(users.filter((u) => u.is_active && (u.role === "OWNER" || u.role === "VENDOR")));
        setProfiles(saved);
        setSubject(subjectKey("ORGANIZATION", me.organization_id));
      } catch (cause) {
        if (active) setError(cause instanceof Error ? cause.message : "Taxpayer profiles unavailable.");
      } finally {
        if (active) setLoading(false);
      }
    }
    void load();
    return () => { active = false; };
  }, []);

  function clearEntry() {
    setLegalName(""); setBusinessName(""); setTaxClass(""); setTinType("");
    setTin(""); setAddress1(""); setAddress2(""); setCity("");
    setState(""); setPostal(""); setCountry("USA");
    setW9OnFile(false); setReceivedOn("");
  }

  async function save(event: React.FormEvent) {
    event.preventDefault();
    const [type, rawId] = subject.split(":") as [SubjectType, string];
    const subjectId = Number(rawId);
    if (!type || !Number.isSafeInteger(subjectId) || subjectId <= 0 || !taxClass || !tinType) {
      setError("Choose a recipient, tax classification and taxpayer ID type.");
      return;
    }
    setBusy(true);
    setError(""); setMessage("");
    try {
      const saved = await apiPut("/api/reporting/tax-profiles", {
        subject_type: type, subject_id: subjectId,
        legal_name: legalName.trim(), business_name: businessName.trim() || null,
        tax_classification: taxClass, tin_type: tinType, tin,
        address_line1: address1.trim(), address_line2: address2.trim() || null,
        city: city.trim(), state: state.trim(), postal_code: postal.trim(), country: country.trim(),
        w9_on_file: type !== "ORGANIZATION" && w9OnFile,
        w9_received_on: type !== "ORGANIZATION" && w9OnFile ? receivedOn : null,
      }) as TaxProfile;
      setProfiles((prior) => [saved, ...prior.filter((row) => row.id !== saved.id)]);
      clearEntry();
      setMessage("Encrypted tax profile saved. This does not submit a tax return or electronically collect a W-9.");
    } catch (cause) {
      // Never put the entered TIN in an error message or console.
      setError(cause instanceof Error ? cause.message : "Profile could not be saved.");
    } finally {
      setTin("");
      setBusy(false);
    }
  }

  const options = [
    ...(viewer ? [{ value: subjectKey("ORGANIZATION", viewer.organization_id), label: "Organization payer" }] : []),
    ...people.map((user) => ({
      value: subjectKey(user.role as SubjectType, user.id),
      label: `${user.role === "OWNER" ? "Owner" : "Vendor"}: ${user.first_name} ${user.last_name} (#${user.id})`,
    })),
  ];
  const isPayer = subject.startsWith("ORGANIZATION:");
  const displayName = (profile: TaxProfile) =>
    profile.subject_type === "ORGANIZATION" ? "Organization payer"
      : options.find((opt) => opt.value === subjectKey(profile.subject_type, profile.subject_id))?.label
        || `${profile.subject_type} #${profile.subject_id}`;

  return (
    <div className="space-y-5">
      <Link href="/dashboard/reporting" className="text-sm text-slate-600 hover:text-slate-900">← Reports</Link>
      <header>
        <h1 className="text-2xl font-bold text-slate-900">1099 preparation</h1>
        <p className="mt-1 text-sm text-slate-600">
          Collect encrypted taxpayer details and track receipt of signed paper W-9 forms.
          This is a preparation workspace, not an IRS filing service.
        </p>
      </header>
      <section className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-950">
        <h2 className="font-semibold">Tax filing is not enabled</h2>
        <p className="mt-1">
          For 2026 returns, the roadmap uses IRS IRIS or an approved provider instead of FIRE.
          Filing requires current IRS templates, verified payer and recipient records, payment review,
          and separate IRIS/provider credentials. This page does not prepare an IRS-submittable file,
          submit returns, or generate recipient copies.
        </p>
        <p className="mt-2">
          Use the official{" "}
          <a className="underline" href="https://www.irs.gov/forms-pubs/about-form-w-9"
             target="_blank" rel="noopener noreferrer">IRS Form W-9</a>{" "}
          for signed paper forms. Record a receipt date only after you have verified and
          securely retained the signed form outside this application. Do not upload W-9 documents
          through general attachments.
        </p>
      </section>
      {loading && <p className="text-sm text-slate-500">Loading tax preparation…</p>}
      {error && <p role="alert" className="rounded-lg border border-red-200 p-3 text-sm text-red-700">{error}</p>}
      {message && <p role="status" className="rounded-lg border border-green-200 p-3 text-sm text-green-700">{message}</p>}
      {viewer?.role === "ADMIN" && !loading && (
        <>
          <section className="rounded-xl border border-slate-200 bg-white p-5">
            <h2 className="text-lg font-semibold text-slate-900">Taxpayer profile intake</h2>
            <p className="mt-1 text-sm text-slate-500">
              Restricted to organization administrators. The saved record displays only
              masked taxpayer ID digits. Enter an ID again whenever you replace a profile.
            </p>
            <form onSubmit={(event) => { void save(event); }} className="mt-4 space-y-4" autoComplete="off">
              <div className="grid gap-3 md:grid-cols-2">
                <label className="text-sm font-medium text-slate-700">Taxpayer
                  <select required value={subject} onChange={(event) => { setSubject(event.target.value); clearEntry(); }}
                    className="mt-1 block w-full rounded-lg border border-slate-300 p-2">
                    {options.map((opt) => <option value={opt.value} key={opt.value}>{opt.label}</option>)}
                  </select>
                </label>
                <label className="text-sm font-medium text-slate-700">Legal tax name
                  <input required maxLength={200} value={legalName}
                    onChange={(event) => setLegalName(event.target.value)}
                    className="mt-1 block w-full rounded-lg border border-slate-300 p-2" />
                </label>
                <label className="text-sm font-medium text-slate-700">Business name, if applicable
                  <input maxLength={200} value={businessName}
                    onChange={(event) => setBusinessName(event.target.value)}
                    className="mt-1 block w-full rounded-lg border border-slate-300 p-2" />
                </label>
                <label className="text-sm font-medium text-slate-700">Federal tax classification
                  <select required value={taxClass} onChange={(event) => setTaxClass(event.target.value as TaxClass)}
                    className="mt-1 block w-full rounded-lg border border-slate-300 p-2">
                    <option value="">Select based on verified tax documentation</option>
                    <option value="INDIVIDUAL">Individual</option>
                    <option value="SOLE_PROPRIETOR">Sole proprietor</option>
                    <option value="C_CORP">C corporation</option>
                    <option value="S_CORP">S corporation</option>
                    <option value="PARTNERSHIP">Partnership</option>
                    <option value="TRUST_ESTATE">Trust / estate</option>
                    <option value="LLC">LLC, classification to be reviewed</option>
                    <option value="OTHER">Other, review required</option>
                  </select>
                </label>
                <label className="text-sm font-medium text-slate-700">Taxpayer ID type
                  <select required value={tinType} onChange={(event) => setTinType(event.target.value as TinType)}
                    className="mt-1 block w-full rounded-lg border border-slate-300 p-2">
                    <option value="">Select ID type</option>
                    <option value="SSN">SSN</option>
                    <option value="EIN">EIN</option>
                    <option value="ITIN">ITIN</option>
                  </select>
                </label>
                <label className="text-sm font-medium text-slate-700">Taxpayer ID (encrypted on save)
                  <input type="password" inputMode="numeric" autoComplete="off" required
                    value={tin} onChange={(event) => setTin(event.target.value)}
                    placeholder="Nine digits" maxLength={11}
                    className="mt-1 block w-full rounded-lg border border-slate-300 p-2" />
                </label>
                <label className="text-sm font-medium text-slate-700">Mailing address, line 1
                  <input required maxLength={255} value={address1}
                    onChange={(event) => setAddress1(event.target.value)}
                    className="mt-1 block w-full rounded-lg border border-slate-300 p-2" />
                </label>
                <label className="text-sm font-medium text-slate-700">Mailing address, line 2
                  <input maxLength={255} value={address2}
                    onChange={(event) => setAddress2(event.target.value)}
                    className="mt-1 block w-full rounded-lg border border-slate-300 p-2" />
                </label>
                <label className="text-sm font-medium text-slate-700">City
                  <input required maxLength={100} value={city}
                    onChange={(event) => setCity(event.target.value)}
                    className="mt-1 block w-full rounded-lg border border-slate-300 p-2" />
                </label>
                <label className="text-sm font-medium text-slate-700">State
                  <input required maxLength={50} value={state}
                    onChange={(event) => setState(event.target.value)}
                    className="mt-1 block w-full rounded-lg border border-slate-300 p-2" />
                </label>
                <label className="text-sm font-medium text-slate-700">Postal code
                  <input required maxLength={20} value={postal}
                    onChange={(event) => setPostal(event.target.value)}
                    className="mt-1 block w-full rounded-lg border border-slate-300 p-2" />
                </label>
                <label className="text-sm font-medium text-slate-700">Country
                  <input required maxLength={100} value={country}
                    onChange={(event) => setCountry(event.target.value)}
                    className="mt-1 block w-full rounded-lg border border-slate-300 p-2" />
                </label>
              </div>
              {!isPayer && (
                <div className="rounded-lg bg-slate-50 p-3">
                  <label className="flex items-start gap-2 text-sm text-slate-700">
                    <input type="checkbox" checked={w9OnFile} onChange={(event) => setW9OnFile(event.target.checked)}
                      className="mt-1" />
                    <span>I have verified a signed paper W-9 and it is securely retained outside this system.</span>
                  </label>
                  {w9OnFile && <label className="mt-2 block text-sm text-slate-700">
                    W-9 received date
                    <input required type="date" value={receivedOn} onChange={(event) => setReceivedOn(event.target.value)}
                      className="ml-2 rounded-lg border border-slate-300 p-2" />
                  </label>}
                </div>
              )}
              <button type="submit" disabled={busy || !subject}
                className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-60">
                {busy ? "Saving…" : "Save encrypted profile"}
              </button>
            </form>
          </section>
          <section className="rounded-xl border border-slate-200 bg-white p-5">
            <h2 className="text-lg font-semibold text-slate-900">Taxpayer readiness</h2>
            {profiles.length === 0 ? (
              <p className="mt-2 text-sm text-slate-500">No encrypted taxpayer profiles recorded.</p>
            ) : (
              <div className="mt-3 space-y-2">
                {profiles.map((profile) => (
                  <div key={profile.id} className="flex flex-wrap items-center justify-between gap-3 rounded-lg border p-3 text-sm">
                    <div>
                      <p className="font-medium">{displayName(profile)}</p>
                      <p className="text-slate-500">Taxpayer ID ending {profile.tin_last4}</p>
                    </div>
                    <p className="text-slate-600">
                      {profile.subject_type === "ORGANIZATION"
                        ? "Payer profile recorded"
                        : profile.w9_on_file
                          ? `Signed paper W-9 recorded ${profile.w9_received_on || ""}`
                          : "Signed W-9 still needed"}
                    </p>
                  </div>
                ))}
              </div>
            )}
          </section>
        </>
      )}
    </div>
  );
}
