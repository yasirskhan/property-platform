"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

import { apiDelete, apiFetch, apiGet, apiPatch, apiPost } from "@/lib/api";
import VendorInsurancePanel from "@/components/vendors/VendorInsurancePanel";

type Vendor = {
  id: number; company_name: string; trade: string | null;
  business_email: string | null; phone: string | null;
  address_line1: string | null; address_line2: string | null;
  city: string | null; state: string | null; postal_code: string | null;
  country: string | null; contact_user_id: number | null; is_active: boolean;
  insurance_status: string; insurance_expires_on: string | null;
};
type VendorList = { items: Vendor[]; total: number };
type Me = { role: string };
type VendorContact = { id: number; role: string; is_active: boolean; first_name: string; last_name: string };
type VendorDraft = {
  company_name: string; trade: string; business_email: string; phone: string;
  address_line1: string; address_line2: string; city: string; state: string;
  postal_code: string; country: string; contact_user_id: string;
};
const EMPTY: VendorDraft = {
  company_name: "", trade: "", business_email: "", phone: "",
  address_line1: "", address_line2: "", city: "", state: "",
  postal_code: "", country: "USA", contact_user_id: "",
};

export default function VendorsPage() {
  const [me, setMe] = useState<Me | null>(null);
  const [vendors, setVendors] = useState<Vendor[]>([]);
  const [contacts, setContacts] = useState<VendorContact[]>([]);
  const [draft, setDraft] = useState<VendorDraft>({ ...EMPTY });
  const [editing, setEditing] = useState<number | null>(null);
  const [selectedVendor, setSelectedVendor] = useState<number | null>(null);
  const [showInactive, setShowInactive] = useState(false);
  const [search, setSearch] = useState("");
  const [tradeFilter, setTradeFilter] = useState("");
  const [insuranceFilter, setInsuranceFilter] = useState("");
  const [asOf, setAsOf] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  async function refresh(query: string, includeInactive: boolean,
    trade = tradeFilter, insurance = insuranceFilter, reference = asOf) {
    const q = new URLSearchParams({
      include_inactive: String(includeInactive),
      ...(query.trim() ? { search: query.trim() } : {}),
      ...(trade.trim() ? { trade: trade.trim() } : {}),
      ...(insurance ? { insurance_status: insurance } : {}),
      ...(reference ? { as_of: reference } : {}),
    });
    const result = await apiGet(`/api/vendors?${q}`) as VendorList;
    setVendors(result.items);
  }

  useEffect(() => {
    let mounted = true;
    (async () => {
      try {
        const who = await apiGet("/auth/me") as Me;
        if (!mounted) return;
        setMe(who);
        const result = await apiGet("/api/vendors") as VendorList;
        if (!mounted) return;
        setVendors(result.items);
        if (who.role === "ADMIN") {
          const users = await apiGet("/users") as VendorContact[];
          if (mounted) setContacts(users.filter((u) => u.role === "VENDOR" && u.is_active));
        }
      } catch (cause) {
        if (mounted) setError(cause instanceof Error ? cause.message : "Vendor companies unavailable.");
      } finally {
        if (mounted) setLoading(false);
      }
    })();
    return () => { mounted = false; };
  }, []);

  function setField(field: keyof VendorDraft, value: string) {
    setDraft((prior) => ({ ...prior, [field]: value }));
  }

  function edit(vendor: Vendor) {
    setEditing(vendor.id);
    setDraft({
      company_name: vendor.company_name, trade: vendor.trade || "",
      business_email: vendor.business_email || "", phone: vendor.phone || "",
      address_line1: vendor.address_line1 || "",
      address_line2: vendor.address_line2 || "", city: vendor.city || "",
      state: vendor.state || "", postal_code: vendor.postal_code || "",
      country: vendor.country || "",
      contact_user_id: vendor.contact_user_id ? String(vendor.contact_user_id) : "",
    });
    setError(""); setMessage("");
  }

  async function save(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true); setError(""); setMessage("");
    const payload = Object.fromEntries(Object.entries(draft).map(([key, value]) => [
      key, key === "contact_user_id" ? (value ? Number(value) : null)
        : value.trim() || (key === "company_name" ? "" : null),
    ]));
    try {
      if (editing === null) await apiPost("/api/vendors", payload);
      else await apiPatch(`/api/vendors/${editing}`, payload);
      setDraft({ ...EMPTY }); setEditing(null);
      await refresh(search, showInactive);
      setMessage("Vendor company saved. Existing bills and tax profiles were not changed.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Vendor company could not be saved.");
    } finally {
      setBusy(false);
    }
  }

  async function changeActive(vendor: Vendor) {
    if (!vendor.is_active && !window.confirm("Restore this vendor company?")) return;
    if (vendor.is_active && !window.confirm("Deactivate this vendor company?")) return;
    setBusy(true); setError("");
    try {
      if (vendor.is_active) await apiDelete(`/api/vendors/${vendor.id}`);
      else {
        const response = await apiFetch(`/api/vendors/${vendor.id}/restore`, { method: "POST" });
        if (!response.ok) throw new Error("Unable to restore vendor.");
      }
      await refresh(search, showInactive);
      setMessage(vendor.is_active ? "Vendor company deactivated." : "Vendor company restored.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Vendor status change failed.");
    } finally {
      setBusy(false);
    }
  }

  if (loading) return <p className="text-slate-500">Loading vendor companies…</p>;

  return (
    <div className="space-y-5">
      <Link className="text-sm text-slate-600 hover:underline" href="/dashboard">← Dashboard</Link>
      <div className="flex flex-wrap gap-3">
        <Link href="/dashboard/work-orders/vendor-assignments" className="text-sm text-blue-700 underline">
          Link vendor companies to work orders
        </Link>
      </div>
      <header>
        <h1 className="text-2xl font-semibold">Vendor companies</h1>
        <p className="mt-1 text-sm text-slate-500">
          Manage vendor company records separately from vendor portal users. Historical free-text bill
          payees, vendor reports and W-9 profiles are not automatically linked or changed.
        </p>
      </header>
      {error && <p role="alert" className="rounded border border-red-200 p-3 text-sm text-red-700">{error}</p>}
      {message && <p role="status" className="rounded border border-green-200 p-3 text-sm text-green-800">{message}</p>}
      {me?.role === "ADMIN" && (
        <form onSubmit={(event) => { void save(event); }} className="rounded-xl border bg-white p-5 space-y-3">
          <h2 className="font-semibold">{editing === null ? "Add vendor company" : "Edit vendor company"}</h2>
          <div className="grid gap-3 md:grid-cols-2">
            {([
              ["company_name", "Company name", true], ["trade", "Trade / specialty", false],
              ["business_email", "Business email", false], ["phone", "Phone", false],
              ["address_line1", "Address line 1", false], ["address_line2", "Address line 2", false],
              ["city", "City", false], ["state", "State", false],
              ["postal_code", "Postal code", false], ["country", "Country", false],
            ] as [keyof VendorDraft, string, boolean][]).map(([key, label, required]) => (
              <label key={key} className="text-sm font-medium">
                {label}
                <input
                  type={key === "business_email" ? "email" : "text"}
                  required={required} value={draft[key]}
                  maxLength={key === "company_name" ? 255 : key === "address_line1" || key === "address_line2" || key === "business_email" ? 255 : key === "trade" || key === "city" || key === "country" ? 100 : 50}
                  onChange={(event) => setField(key, event.target.value)}
                  className="mt-1 block w-full rounded border px-3 py-2"
                />
              </label>
            ))}
            <label className="text-sm font-medium">
              Linked vendor contact (optional)
              <select value={draft.contact_user_id}
                onChange={(event) => setField("contact_user_id", event.target.value)}
                className="mt-1 block w-full rounded border px-3 py-2">
                <option value="">No linked portal/contact user</option>
                {contacts.map((user) => (
                  <option key={user.id} value={user.id}>
                    {user.first_name} {user.last_name} (#{user.id})
                  </option>
                ))}
              </select>
            </label>
          </div>
          <div className="flex gap-2">
            <button disabled={busy} type="submit"
              className="rounded bg-slate-900 px-4 py-2 text-sm text-white disabled:opacity-50">
              {busy ? "Saving…" : editing === null ? "Create company" : "Save changes"}
            </button>
            {editing !== null && <button type="button" onClick={() => {
              setEditing(null); setDraft({ ...EMPTY }); setError("");
            }} className="rounded border px-4 py-2 text-sm">Cancel</button>}
          </div>
        </form>
      )}
      <section className="rounded-xl border bg-white p-5 space-y-3">
        <h2 className="font-semibold">Company directory</h2>
        <form onSubmit={(event) => { event.preventDefault(); void refresh(search, showInactive).catch(
          (cause) => setError(cause instanceof Error ? cause.message : "Search failed.")
        ); }} className="flex flex-wrap items-center gap-3">
          <input value={search} maxLength={100} onChange={(event) => setSearch(event.target.value)}
            placeholder="Search company name" aria-label="Search vendor companies"
            className="rounded border px-3 py-2 text-sm" />
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={showInactive}
              onChange={(event) => { setShowInactive(event.target.checked); void refresh(search, event.target.checked).catch(
                (cause) => setError(cause instanceof Error ? cause.message : "Refresh failed.")
              ); }} />
            Show inactive
          </label>
          <input value={tradeFilter} maxLength={100}
            onChange={(event) => setTradeFilter(event.target.value)}
            placeholder="Exact trade (e.g. Plumbing)" aria-label="Filter vendor trade"
            className="rounded border px-3 py-2 text-sm" />
          <select value={insuranceFilter} onChange={(event) => setInsuranceFilter(event.target.value)}
            aria-label="Filter insurance status" className="rounded border px-3 py-2 text-sm">
            <option value="">All insurance statuses</option>
            <option value="MISSING">No active policy</option>
            <option value="EXPIRED">Expired</option>
            <option value="EXPIRING_30_DAYS">Expiring within 30 days</option>
            <option value="UPCOMING">Upcoming</option>
            <option value="CURRENT">Current</option>
          </select>
          <label className="text-sm">Insurance status as of
            <input type="date" value={asOf} onChange={(event) => setAsOf(event.target.value)}
              className="ml-2 rounded border px-2 py-2 text-sm" />
          </label>
          <button type="submit" className="rounded border px-3 py-2 text-sm">Search</button>
        </form>
        {vendors.length === 0 ? <p className="text-sm text-slate-500">No vendor companies match.</p> : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead><tr className="border-b">
                <th className="px-3 py-2">Company</th><th className="px-3 py-2">Trade</th>
                <th className="px-3 py-2">Email</th><th className="px-3 py-2">Insurance</th><th className="px-3 py-2">Status</th>
                <th className="px-3 py-2">Actions</th>
              </tr></thead>
              <tbody>
                {vendors.map((v) => (
                  <tr key={v.id} className="border-b">
                    <td className="px-3 py-2 font-medium">{v.company_name}</td>
                    <td className="px-3 py-2">{v.trade || "—"}</td>
                    <td className="px-3 py-2">{v.business_email || "—"}</td>
                    <td className="px-3 py-2">
                      {v.insurance_status === "MISSING" ? "No active policy recorded" :
                       v.insurance_status === "EXPIRING_30_DAYS" ? "Expiring within 30 days" :
                       v.insurance_status}
                      {v.insurance_expires_on && <span className="block text-xs text-slate-500">
                        {v.insurance_expires_on}
                      </span>}
                    </td>
                    <td className="px-3 py-2">{v.is_active ? "Active" : "Inactive"}</td>
                    <td className="px-3 py-2">
                      <span className="flex gap-2">
                        <button type="button" className="underline"
                          onClick={() => setSelectedVendor(v.id)}>Insurance</button>
                        {me?.role === "ADMIN" && <>
                        {v.is_active && <button type="button" disabled={busy}
                          onClick={() => edit(v)} className="underline">Edit</button>}
                        <button type="button" disabled={busy} onClick={() => { void changeActive(v); }}
                          className="underline">{v.is_active ? "Deactivate" : "Restore"}</button>
                      </>}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
      {selectedVendor !== null && <VendorInsurancePanel
        vendorId={selectedVendor} canEdit={me?.role === "ADMIN"} />}
    </div>
  );
}
