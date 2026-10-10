"use client";

import { useEffect, useState } from "react";
import { apiGet, apiPut } from "@/lib/api";

type Address = {
  address_line1: string; address_line2: string;
  city: string; state: string; postal_code: string; country: string;
};
type Details = {
  current_address: Address; previous_addresses: Address[];
  employer_name: string | null; employment_title: string | null;
  gross_monthly_income: string | null;
};
type PrivateResult = { application_id: number; configured: boolean; details: Details | null };
const BLANK: Address = { address_line1: "", address_line2: "", city: "", state: "", postal_code: "", country: "USA" };

export default function ApplicationPrivatePanel({ applicationId, canEdit, onClose }: {
  applicationId: number; canEdit: boolean; onClose: () => void;
}) {
  const [details, setDetails] = useState<Details>({
    current_address: { ...BLANK }, previous_addresses: [],
    employer_name: "", employment_title: "", gross_monthly_income: null,
  });
  const [configured, setConfigured] = useState(false);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  useEffect(() => {
    let mounted = true;
    apiGet(`/api/leasing/applications/${applicationId}/private-details`)
      .then((value: PrivateResult) => {
        if (!mounted) return;
        setConfigured(value.configured);
        if (value.details) setDetails({
          ...value.details,
          current_address: value.details.current_address,
          previous_addresses: value.details.previous_addresses,
          employer_name: value.details.employer_name || "",
          employment_title: value.details.employment_title || "",
          gross_monthly_income: value.details.gross_monthly_income ?? null,
        });
      })
      .catch((cause) => {
        if (mounted) setError(cause instanceof Error ? cause.message : "Private data unavailable.");
      })
      .finally(() => { if (mounted) setLoading(false); });
    return () => { mounted = false; };
  }, [applicationId]);

  function updateAddress(index: number | null, key: keyof Address, value: string) {
    if (index === null) {
      setDetails((old) => ({ ...old, current_address: { ...old.current_address, [key]: value } }));
      return;
    }
    setDetails((old) => ({
      ...old,
      previous_addresses: old.previous_addresses.map((addr, n) => n === index ? { ...addr, [key]: value } : addr),
    }));
  }

  async function save(event: React.FormEvent) {
    event.preventDefault();
    if (!canEdit) return;
    setBusy(true); setError(""); setMessage("");
    try {
      const next: Details = {
        ...details,
        employer_name: details.employer_name?.trim() || null,
        employment_title: details.employment_title?.trim() || null,
        gross_monthly_income: details.gross_monthly_income || null,
      };
      await apiPut(`/api/leasing/applications/${applicationId}/private-details`, next);
      setConfigured(true);
      setMessage("Private questionnaire encrypted and saved. This does not run screening.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Cannot save private questionnaire.");
    } finally {
      setBusy(false);
    }
  }

  function addressFields(addr: Address, index: number | null) {
    const keys: { key: keyof Address; label: string; max: number; required: boolean }[] = [
      { key: "address_line1", label: "Street address", max: 255, required: true },
      { key: "address_line2", label: "Address line 2", max: 255, required: false },
      { key: "city", label: "City", max: 100, required: true },
      { key: "state", label: "State / province", max: 50, required: true },
      { key: "postal_code", label: "Postal code", max: 20, required: true },
      { key: "country", label: "Country", max: 100, required: true },
    ];
    return (
      <div className="grid gap-2 md:grid-cols-3">
        {keys.map(({ key, label, max, required }) => (
          <label key={key} className="text-sm text-slate-700">
            {label}
            <input type="text" maxLength={max} required={required} disabled={!canEdit}
              value={addr[key] ?? ""}
              onChange={(event) => updateAddress(index, key, event.target.value)}
              className="mt-1 block w-full rounded border border-slate-300 px-2 py-1.5 disabled:bg-slate-50" />
          </label>
        ))}
      </div>
    );
  }

  return (
    <section className="rounded-xl border border-indigo-200 bg-white p-4">
      <div className="flex items-center justify-between gap-3">
        <h2 className="font-semibold">Private application details #{applicationId}</h2>
        <button type="button" onClick={onClose} className="rounded border px-3 py-1 text-sm">Close</button>
      </div>
      <p className="mt-1 text-sm text-slate-600">
        Stored with a separate encryption key. Authorized staff can review submitted information.
        Do not enter SSNs, birth dates, bank accounts, medical histories or screening reports.
      </p>
      {loading && <p className="mt-2 text-sm">Loading encrypted details…</p>}
      {error && <p role="alert" className="mt-2 text-sm text-red-700">{error}</p>}
      {message && <p role="status" className="mt-2 text-sm text-green-700">{message}</p>}
      {!loading && !error && !configured && !canEdit && (
        <p className="mt-2 text-sm text-slate-500">Applicant has not recorded private questionnaire details.</p>
      )}
      {!loading && (configured || canEdit) && <form onSubmit={(event) => { void save(event); }} className="mt-3 space-y-4" autoComplete="off">
        <div>
          <h3 className="mb-2 text-sm font-semibold">Current mailing address</h3>
          {addressFields(details.current_address, null)}
        </div>
        <div>
          <h3 className="mb-2 text-sm font-semibold">Previous addresses (up to 3)</h3>
          {details.previous_addresses.map((addr, index) => (
            <div key={index} className="mb-3 rounded border p-2">
              {addressFields(addr, index)}
              {canEdit && <button type="button"
                onClick={() => setDetails((old) => ({
                  ...old, previous_addresses: old.previous_addresses.filter((_item, n) => n !== index),
                }))} className="mt-2 text-xs text-red-700">Remove this address</button>}
            </div>
          ))}
          {canEdit && details.previous_addresses.length < 3 && <button type="button"
            onClick={() => setDetails((old) => ({
              ...old, previous_addresses: [...old.previous_addresses, { ...BLANK }],
            }))} className="rounded border px-3 py-1.5 text-sm">Add a previous address</button>}
        </div>
        <div className="grid gap-3 md:grid-cols-3">
          <label className="text-sm text-slate-700">Employer (optional)
            <input disabled={!canEdit} maxLength={200} value={details.employer_name || ""}
              onChange={(event) => setDetails((old) => ({ ...old, employer_name: event.target.value }))}
              className="mt-1 block w-full rounded border p-2" />
          </label>
          <label className="text-sm text-slate-700">Job title (optional)
            <input disabled={!canEdit} maxLength={100} value={details.employment_title || ""}
              onChange={(event) => setDetails((old) => ({ ...old, employment_title: event.target.value }))}
              className="mt-1 block w-full rounded border p-2" />
          </label>
          <label className="text-sm text-slate-700">Gross monthly income (optional)
            <input disabled={!canEdit} type="number" min="0.01" step="0.01" max="10000000"
              value={details.gross_monthly_income || ""}
              onChange={(event) => setDetails((old) => ({
                ...old, gross_monthly_income: event.target.value || null,
              }))} className="mt-1 block w-full rounded border p-2" />
          </label>
        </div>
        {canEdit && <button disabled={busy} type="submit"
          className="rounded bg-slate-900 px-4 py-2 text-sm text-white disabled:opacity-50">
          {busy ? "Encrypting…" : "Save encrypted questionnaire"}
        </button>}
      </form>}
    </section>
  );
}
