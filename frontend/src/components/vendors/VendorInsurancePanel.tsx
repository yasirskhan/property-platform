"use client";

import { useEffect, useState } from "react";

import { apiDelete, apiFetch, apiGet, apiPatch, apiPost } from "@/lib/api";

type Policy = {
  id: number; vendor_id: number; carrier: string; coverage_type: string;
  policy_number: string | null; coverage_amount: string | null;
  effective_date: string | null; expiration_date: string;
  is_active: boolean; status: string;
};
type PolicyList = { items: Policy[]; total: number; as_of: string };
type Draft = {
  carrier: string; coverage_type: string; policy_number: string;
  coverage_amount: string; effective_date: string; expiration_date: string;
};
const EMPTY: Draft = {
  carrier: "", coverage_type: "", policy_number: "",
  coverage_amount: "", effective_date: "", expiration_date: "",
};
const INPUTS: [keyof Draft, string, string, boolean][] = [
  ["carrier", "Insurance carrier", "text", true],
  ["coverage_type", "Coverage type", "text", true],
  ["policy_number", "Policy number", "text", false],
  ["coverage_amount", "Coverage amount (optional)", "number", false],
  ["effective_date", "Effective date", "date", false],
  ["expiration_date", "Expiration date", "date", true],
];

export default function VendorInsurancePanel({ vendorId, canEdit }: {
  vendorId: number; canEdit: boolean;
}) {
  const [list, setList] = useState<PolicyList | null>(null);
  const [draft, setDraft] = useState<Draft>({ ...EMPTY });
  const [editing, setEditing] = useState<number | null>(null);
  const [showInactive, setShowInactive] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  async function load(inactive: boolean) {
    const params = new URLSearchParams({ include_inactive: String(inactive) });
    const data = await apiGet(`/api/vendors/${vendorId}/insurance?${params}`) as PolicyList;
    setList(data);
  }
  useEffect(() => {
    let active = true;
    setList(null); setError(""); setEditing(null); setDraft({ ...EMPTY });
    apiGet(`/api/vendors/${vendorId}/insurance?include_inactive=${showInactive}`)
      .then((data) => { if (active) setList(data as PolicyList); })
      .catch((cause) => { if (active) setError(cause instanceof Error ? cause.message : "Insurance unavailable."); });
    return () => { active = false; };
  }, [vendorId, showInactive]);

  async function save(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true); setError(""); setMessage("");
    const payload = Object.fromEntries(Object.entries(draft).map(([key, value]) => [
      key, value.trim() || null,
    ]));
    try {
      if (editing === null) await apiPost(`/api/vendors/${vendorId}/insurance`, payload);
      else await apiPatch(`/api/vendors/${vendorId}/insurance/${editing}`, payload);
      setDraft({ ...EMPTY }); setEditing(null);
      await load(showInactive);
      setMessage("Policy metadata saved; no premium or GL transaction was created.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to save insurance.");
    } finally { setBusy(false); }
  }

  async function changeActive(policy: Policy) {
    if (!window.confirm(policy.is_active ? "Deactivate policy?" : "Restore policy?")) return;
    setBusy(true); setError("");
    try {
      if (policy.is_active) await apiDelete(`/api/vendors/${vendorId}/insurance/${policy.id}`);
      else {
        const response = await apiFetch(
          `/api/vendors/${vendorId}/insurance/${policy.id}/restore`, { method: "POST" },
        );
        if (!response.ok) throw new Error("Unable to restore policy.");
      }
      await load(showInactive);
      setMessage("Policy status updated.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to change policy.");
    } finally { setBusy(false); }
  }

  function edit(policy: Policy) {
    setEditing(policy.id);
    setDraft({
      carrier: policy.carrier, coverage_type: policy.coverage_type,
      policy_number: policy.policy_number || "",
      coverage_amount: policy.coverage_amount || "",
      effective_date: policy.effective_date || "",
      expiration_date: policy.expiration_date,
    });
    setError("");
  }

  return (
    <section className="space-y-3 rounded-xl border bg-white p-5">
      <h2 className="font-semibold">Vendor insurance</h2>
      <p className="text-sm text-slate-600">
        Recorded policy metadata and expiry only. This does not verify insurer coverage,
        pay premiums or post GL transactions. General attachments may hold
        non-tax insurance certificates; never store W-9 documents there.
      </p>
      {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
      {message && <p role="status" className="text-sm text-green-700">{message}</p>}
      {canEdit && (
        <form onSubmit={(event) => { void save(event); }} className="space-y-3">
          <div className="grid gap-3 md:grid-cols-2">
            {INPUTS.map(([key, label, type, required]) => (
              <label key={key} className="text-sm font-medium">{label}
                <input required={required} type={type} value={draft[key]}
                  step={type === "number" ? "0.01" : undefined}
                  min={type === "number" ? 0 : undefined}
                  maxLength={type === "text" ? 255 : undefined}
                  onChange={(event) => setDraft((prior) => ({ ...prior, [key]: event.target.value }))}
                  className="mt-1 block w-full rounded border px-3 py-2" />
              </label>
            ))}
          </div>
          <div className="flex gap-2">
            <button type="submit" disabled={busy}
              className="rounded bg-slate-900 px-4 py-2 text-sm text-white disabled:opacity-50">
              {busy ? "Saving…" : editing === null ? "Add insurance policy" : "Update policy"}
            </button>
            {editing !== null && <button type="button" className="rounded border px-3 py-2 text-sm"
              onClick={() => { setEditing(null); setDraft({ ...EMPTY }); }}>Cancel</button>}
          </div>
        </form>
      )}
      <label className="flex items-center gap-2 text-sm">
        <input type="checkbox" checked={showInactive}
          onChange={(event) => setShowInactive(event.target.checked)} />
        Show inactive policies
      </label>
      {!list ? <p className="text-sm text-slate-500">Loading insurance…</p>
        : list.items.length === 0 ? <p className="text-sm text-slate-500">No recorded policies.</p>
        : <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead><tr className="border-b">
              <th className="px-3 py-2">Carrier / coverage</th>
              <th className="px-3 py-2">Expires</th>
              <th className="px-3 py-2">Recorded status</th>
              <th className="px-3 py-2">Actions</th>
            </tr></thead>
            <tbody>
              {list.items.map((policy) => (
                <tr className="border-b" key={policy.id}>
                  <td className="px-3 py-2">{policy.carrier} · {policy.coverage_type}</td>
                  <td className="px-3 py-2">{policy.expiration_date}</td>
                  <td className="px-3 py-2">
                    {policy.status === "EXPIRING_30_DAYS" ? "Expiring within 30 days" : policy.status}
                  </td>
                  <td className="px-3 py-2">
                    {canEdit && <span className="flex gap-2">
                      {policy.is_active && <button type="button" className="underline" disabled={busy}
                        onClick={() => edit(policy)}>Edit</button>}
                      <button type="button" disabled={busy} className="underline"
                        onClick={() => { void changeActive(policy); }}>
                        {policy.is_active ? "Deactivate" : "Restore"}
                      </button>
                    </span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>}
    </section>
  );
}
