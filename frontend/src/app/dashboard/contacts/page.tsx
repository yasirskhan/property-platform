"use client";

import { useEffect, useState } from "react";
import { apiDelete, apiGet, apiPatch, apiPost } from "@/lib/api";

type ContactKind = "PERSON" | "BUSINESS";
type Contact = {
  id: number; display_name: string; contact_type: ContactKind;
  company_name: string | null; email: string | null; phone: string | null;
  job_title: string | null; address_line1: string | null; address_line2: string | null;
  city: string | null; state: string | null; postal_code: string | null;
  country: string | null; is_active: boolean;
};
type ContactDraft = {
  display_name: string; contact_type: ContactKind; company_name: string;
  email: string; phone: string; job_title: string;
  address_line1: string; address_line2: string; city: string;
  state: string; postal_code: string; country: string;
};
type ContactList = { items: Contact[]; total: number };
type Viewer = { role: string };
const EMPTY: ContactDraft = {
  display_name: "", contact_type: "PERSON", company_name: "",
  email: "", phone: "", job_title: "", address_line1: "",
  address_line2: "", city: "", state: "", postal_code: "", country: "",
};
const FIELD_LABELS: { key: keyof Omit<ContactDraft, "contact_type">; label: string; maxLength: number }[] = [
  { key: "display_name", label: "Contact name", maxLength: 255 },
  { key: "company_name", label: "Company (optional)", maxLength: 255 },
  { key: "email", label: "Email", maxLength: 255 },
  { key: "phone", label: "Phone", maxLength: 50 },
  { key: "job_title", label: "Job title", maxLength: 100 },
  { key: "address_line1", label: "Address line 1", maxLength: 255 },
  { key: "address_line2", label: "Address line 2", maxLength: 255 },
  { key: "city", label: "City", maxLength: 100 },
  { key: "state", label: "State / province", maxLength: 50 },
  { key: "postal_code", label: "Postal code", maxLength: 20 },
  { key: "country", label: "Country", maxLength: 100 },
];

export default function ContactsPage() {
  const [viewer, setViewer] = useState<Viewer | null>(null);
  const [rows, setRows] = useState<Contact[]>([]);
  const [search, setSearch] = useState("");
  const [showInactive, setShowInactive] = useState(false);
  const [draft, setDraft] = useState<ContactDraft>({ ...EMPTY });
  const [editing, setEditing] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  async function refresh(query: string, inactive: boolean) {
    const params = new URLSearchParams({ include_inactive: String(inactive) });
    if (query.trim()) params.set("search", query.trim());
    const payload = await apiGet(`/api/contacts?${params.toString()}`) as ContactList;
    setRows(payload.items);
  }

  useEffect(() => {
    let active = true;
    async function load() {
      try {
        const me = await apiGet("/auth/me") as Viewer;
        if (!active) return;
        setViewer(me);
        const result = await apiGet("/api/contacts") as ContactList;
        if (active) setRows(result.items);
      } catch (cause) {
        if (active) setError(cause instanceof Error ? cause.message : "Contacts unavailable.");
      } finally {
        if (active) setLoading(false);
      }
    }
    void load();
    return () => { active = false; };
  }, []);

  function populate(contact: Contact) {
    setEditing(contact.id);
    setDraft({
      display_name: contact.display_name, contact_type: contact.contact_type,
      company_name: contact.company_name || "", email: contact.email || "",
      phone: contact.phone || "", job_title: contact.job_title || "",
      address_line1: contact.address_line1 || "", address_line2: contact.address_line2 || "",
      city: contact.city || "", state: contact.state || "",
      postal_code: contact.postal_code || "", country: contact.country || "",
    });
    setError(""); setMessage("");
  }

  function clear() {
    setEditing(null);
    setDraft({ ...EMPTY });
  }

  async function save(event: React.FormEvent) {
    event.preventDefault();
    if (!draft.display_name.trim()) { setError("Contact name is required."); return; }
    setBusy(true); setError(""); setMessage("");
    const payload = {
      ...draft, display_name: draft.display_name.trim(),
      company_name: draft.company_name.trim() || null,
      email: draft.email.trim() || null,
      phone: draft.phone.trim() || null,
      job_title: draft.job_title.trim() || null,
      address_line1: draft.address_line1.trim() || null,
      address_line2: draft.address_line2.trim() || null,
      city: draft.city.trim() || null, state: draft.state.trim() || null,
      postal_code: draft.postal_code.trim() || null,
      country: draft.country.trim() || null,
    };
    try {
      if (editing === null) {
        await apiPost("/api/contacts", payload);
      } else {
        await apiPatch(`/api/contacts/${editing}`, payload);
      }
      await refresh(search, showInactive);
      setMessage(editing === null ? "Contact created." : "Contact updated.");
      clear();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Contact could not be saved.");
    } finally {
      setBusy(false);
    }
  }

  async function changeStatus(contact: Contact) {
    setBusy(true); setError(""); setMessage("");
    try {
      if (contact.is_active) {
        await apiDelete(`/api/contacts/${contact.id}`);
      } else {
        await apiPost(`/api/contacts/${contact.id}/restore`);
      }
      await refresh(search, showInactive);
      setMessage(contact.is_active ? "Contact deactivated." : "Contact restored.");
      if (editing === contact.id) clear();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Contact status could not be updated.");
    } finally {
      setBusy(false);
    }
  }

  const canWrite = viewer?.role === "ADMIN";

  return (
    <div className="space-y-5">
      <header>
        <h1 className="text-2xl font-semibold text-slate-900">Contacts</h1>
        <p className="mt-1 text-sm text-slate-600">
          Organization address book. These entries are not login accounts,
          vendor companies, or automatically linked accounting recipients.
        </p>
      </header>
      {loading && <p className="text-sm text-slate-500">Loading contacts…</p>}
      {error && <p role="alert" className="rounded border border-red-200 p-3 text-sm text-red-700">{error}</p>}
      {message && <p role="status" className="rounded border border-green-200 p-3 text-sm text-green-700">{message}</p>}
      {!loading && (
        <>
          <form onSubmit={(event) => { event.preventDefault(); setError(""); void refresh(search, showInactive).catch(
            (cause) => setError(cause instanceof Error ? cause.message : "Contact search failed.")
          ); }} className="flex flex-wrap items-end gap-3 rounded-xl border bg-white p-4">
            <label className="text-sm text-slate-700">
              Search name, company, or email
              <input value={search} maxLength={100} onChange={(event) => setSearch(event.target.value)}
                className="mt-1 block min-w-60 rounded border px-3 py-2" />
            </label>
            <label className="flex items-center gap-2 pb-2 text-sm text-slate-700">
              <input type="checkbox" checked={showInactive}
                onChange={(event) => setShowInactive(event.target.checked)} />
              Include inactive
            </label>
            <button type="submit" className="rounded bg-slate-900 px-4 py-2 text-sm text-white">Search</button>
          </form>
          {canWrite && (
            <form onSubmit={(event) => { void save(event); }} className="space-y-4 rounded-xl border bg-white p-4">
              <h2 className="font-semibold">{editing === null ? "Add contact" : "Edit contact"}</h2>
              <label className="block max-w-xs text-sm text-slate-700">
                Contact type
                <select value={draft.contact_type}
                  onChange={(event) => setDraft((old) => ({ ...old, contact_type: event.target.value as ContactKind }))}
                  className="mt-1 block w-full rounded border px-3 py-2">
                  <option value="PERSON">Person</option>
                  <option value="BUSINESS">Business</option>
                </select>
              </label>
              <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                {FIELD_LABELS.map(({ key, label, maxLength }) => (
                  <label key={key} className="text-sm text-slate-700">
                    {label}
                    <input type={key === "email" ? "email" : "text"}
                      required={key === "display_name"} maxLength={maxLength}
                      value={draft[key]} onChange={(event) => setDraft((old) => ({ ...old, [key]: event.target.value }))}
                      className="mt-1 block w-full rounded border px-3 py-2" />
                  </label>
                ))}
              </div>
              <div className="flex flex-wrap gap-2">
                <button disabled={busy} type="submit"
                  className="rounded bg-slate-900 px-4 py-2 text-sm text-white disabled:opacity-50">
                  {busy ? "Saving…" : editing === null ? "Add contact" : "Update contact"}
                </button>
                {editing !== null && <button type="button" onClick={clear}
                  className="rounded border px-4 py-2 text-sm">Cancel</button>}
              </div>
            </form>
          )}
          <section aria-label="Contact directory" className="space-y-2">
            <h2 className="font-semibold">Contact directory</h2>
            {rows.length === 0 && <p className="rounded border bg-white p-5 text-sm text-slate-500">No contacts match the filters.</p>}
            {rows.map((contact) => (
              <div key={contact.id} className="flex flex-wrap items-center justify-between gap-4 rounded-xl border bg-white p-4">
                <div className="min-w-0">
                  <div className="font-medium">{contact.display_name}
                    {!contact.is_active && <span className="ml-2 text-xs text-amber-700">(inactive)</span>}
                  </div>
                  <p className="text-xs text-slate-500">
                    {contact.contact_type === "BUSINESS" ? "Business" : "Person"}
                    {contact.company_name ? ` · ${contact.company_name}` : ""}
                  </p>
                  {contact.email && <p className="text-sm text-slate-600">{contact.email}</p>}
                  {contact.phone && <p className="text-sm text-slate-600">{contact.phone}</p>}
                </div>
                {canWrite && <div className="flex gap-2">
                  {contact.is_active && <button type="button" disabled={busy} onClick={() => populate(contact)}
                    className="rounded border px-3 py-1.5 text-sm disabled:opacity-50">Edit</button>}
                  <button type="button" disabled={busy} onClick={() => { void changeStatus(contact); }}
                    className="rounded border px-3 py-1.5 text-sm disabled:opacity-50">
                    {contact.is_active ? "Deactivate" : "Restore"}
                  </button>
                </div>}
              </div>
            ))}
          </section>
        </>
      )}
    </div>
  );
}
