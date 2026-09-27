"use client";

import { useEffect, useState } from "react";
import { apiGet, apiPost, apiPut } from "@/lib/api";
import ApplicationPrivatePanel from "@/components/leasing/ApplicationPrivatePanel";

type ApplicationStatus = "draft" | "pending_payment" | "paid" | "screening"
  | "screened" | "approved" | "rejected" | "withdrawn";
type Application = {
  id: number; property_id: number; unit_id: number | null;
  applicant_user_id: number; status: ApplicationStatus;
  applicant_name: string; applicant_email: string; applicant_phone: string | null;
  move_in_date: string | null; lease_term_months: number | null;
  occupant_names: string[]; pet_description: string | null;
};
type Viewer = { role: string };
const EMPTY = {
  property_id: "", unit_id: "", applicant_name: "", applicant_email: "",
  applicant_phone: "", move_in_date: "", lease_term_months: "",
  occupant_names: "", pet_description: "",
};

export default function ApplicationsPage() {
  const [viewer, setViewer] = useState<Viewer | null>(null);
  const [rows, setRows] = useState<Application[]>([]);
  const [form, setForm] = useState({ ...EMPTY });
  const [editing, setEditing] = useState<number | null>(null);
  const [privateOpen, setPrivateOpen] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  async function load() {
    const items = await apiGet("/api/leasing/applications") as Application[];
    setRows(items);
  }
  useEffect(() => {
    let active = true;
    async function init() {
      try {
        const user = await apiGet("/auth/me") as Viewer;
        if (!active) return;
        setViewer(user);
        const items = await apiGet("/api/leasing/applications") as Application[];
        if (active) setRows(items);
      } catch (cause) {
        if (active) setError(cause instanceof Error ? cause.message : "Applications unavailable.");
      } finally {
        if (active) setLoading(false);
      }
    }
    void init();
    return () => { active = false; };
  }, []);

  function edit(row: Application) {
    setEditing(row.id);
    setForm({
      property_id: String(row.property_id), unit_id: row.unit_id ? String(row.unit_id) : "",
      applicant_name: row.applicant_name, applicant_email: row.applicant_email,
      applicant_phone: row.applicant_phone || "", move_in_date: row.move_in_date || "",
      lease_term_months: row.lease_term_months ? String(row.lease_term_months) : "",
      occupant_names: row.occupant_names.join("; "),
      pet_description: row.pet_description || "",
    });
    setError(""); setMessage("");
  }
  function clear() { setEditing(null); setForm({ ...EMPTY }); }

  async function save(event: React.FormEvent) {
    event.preventDefault(); setBusy(true); setError(""); setMessage("");
    const draft = {
      applicant_name: form.applicant_name.trim(), applicant_email: form.applicant_email.trim(),
      applicant_phone: form.applicant_phone.trim() || null,
      move_in_date: form.move_in_date || null,
      lease_term_months: form.lease_term_months ? Number(form.lease_term_months) : null,
      occupant_names: form.occupant_names.trim()
        ? form.occupant_names.split(";").map((item) => item.trim()) : [],
      pet_description: form.pet_description.trim() || null,
    };
    try {
      if (editing === null) {
        await apiPost("/api/leasing/applications", {
          ...draft, property_id: Number(form.property_id),
          unit_id: form.unit_id ? Number(form.unit_id) : null,
        });
      } else {
        await apiPut(`/api/leasing/applications/${editing}`, draft);
      }
      await load(); clear();
      setMessage("Draft saved. No payment, screening or lease was created.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Cannot save application.");
    } finally {
      setBusy(false);
    }
  }

  async function submit(id: number) {
    setBusy(true); setError(""); setMessage("");
    try {
      await apiPost(`/api/leasing/applications/${id}/submit`);
      await load();
      setMessage("Application submitted as pending payment. No fee has been charged.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Submission failed.");
    } finally {
      setBusy(false);
    }
  }

  const applicant = viewer?.role === "APPLICANT";
  return (
    <div className="space-y-5">
      <header>
        <h1 className="text-2xl font-bold text-slate-900">Rental applications</h1>
        <p className="mt-1 text-sm text-slate-600">
          {applicant
            ? "Create or edit your own application draft. Submitting marks it pending payment; no fee is charged here."
            : "Authorized property application overview. Approval, fees and screening are not available in this initial intake."}
        </p>
      </header>
      <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-950">
        Do not enter Social Security numbers, birth dates, bank details, financial statements
        or screening information. Secure verification and application-fee payment will be
        introduced separately; this screen does not approve a tenancy or activate a lease.
      </div>
      {loading && <p className="text-sm text-slate-500">Loading applications…</p>}
      {error && <p role="alert" className="rounded border border-red-200 p-3 text-sm text-red-700">{error}</p>}
      {message && <p role="status" className="rounded border border-green-200 p-3 text-sm text-green-700">{message}</p>}
      {!loading && applicant && (
        <form className="space-y-3 rounded-xl border bg-white p-4"
          onSubmit={(event) => { void save(event); }}>
          <h2 className="font-semibold">{editing === null ? "Start an application" : "Edit your draft"}</h2>
          <p className="text-xs text-slate-500">
            Enter the property and optional unit IDs provided by the property office.
            Public listings and online fee payment are not yet connected.
          </p>
          <div className="grid gap-3 md:grid-cols-2">
            <label className="text-sm text-slate-700">Property ID
              <input required type="number" min={1} disabled={editing !== null}
                value={form.property_id} onChange={(event) => setForm((old) => ({ ...old, property_id: event.target.value }))}
                className="mt-1 block w-full rounded border p-2" />
            </label>
            <label className="text-sm text-slate-700">Unit ID (optional)
              <input type="number" min={1} disabled={editing !== null}
                value={form.unit_id} onChange={(event) => setForm((old) => ({ ...old, unit_id: event.target.value }))}
                className="mt-1 block w-full rounded border p-2" />
            </label>
            <label className="text-sm text-slate-700">Your name
              <input required maxLength={255} value={form.applicant_name}
                onChange={(event) => setForm((old) => ({ ...old, applicant_name: event.target.value }))}
                className="mt-1 block w-full rounded border p-2" />
            </label>
            <label className="text-sm text-slate-700">Email
              <input required type="email" maxLength={255} value={form.applicant_email}
                onChange={(event) => setForm((old) => ({ ...old, applicant_email: event.target.value }))}
                className="mt-1 block w-full rounded border p-2" />
            </label>
            <label className="text-sm text-slate-700">Phone
              <input maxLength={50} value={form.applicant_phone}
                onChange={(event) => setForm((old) => ({ ...old, applicant_phone: event.target.value }))}
                className="mt-1 block w-full rounded border p-2" />
            </label>
            <label className="text-sm text-slate-700">Requested move-in date
              <input type="date" value={form.move_in_date}
                onChange={(event) => setForm((old) => ({ ...old, move_in_date: event.target.value }))}
                className="mt-1 block w-full rounded border p-2" />
            </label>
            <label className="text-sm text-slate-700">Lease term (months)
              <input type="number" min={1} max={60} value={form.lease_term_months}
                onChange={(event) => setForm((old) => ({ ...old, lease_term_months: event.target.value }))}
                className="mt-1 block w-full rounded border p-2" />
            </label>
            <label className="text-sm text-slate-700">Other occupants (semicolon-separated, max 8)
              <input value={form.occupant_names}
                onChange={(event) => setForm((old) => ({ ...old, occupant_names: event.target.value }))}
                className="mt-1 block w-full rounded border p-2" />
            </label>
          </div>
          <label className="block text-sm text-slate-700">Pet description (optional)
            <textarea rows={2} maxLength={500} value={form.pet_description}
              onChange={(event) => setForm((old) => ({ ...old, pet_description: event.target.value }))}
              className="mt-1 block w-full rounded border p-2" />
          </label>
          <div className="flex flex-wrap gap-2">
            <button disabled={busy} type="submit" className="rounded bg-slate-900 px-4 py-2 text-sm text-white disabled:opacity-50">
              {busy ? "Saving…" : editing === null ? "Save draft" : "Update draft"}
            </button>
            {editing !== null && <button type="button" onClick={clear}
              className="rounded border px-4 py-2 text-sm">Cancel edit</button>}
          </div>
        </form>
      )}
      {!loading && <section className="space-y-2">
        <h2 className="text-lg font-semibold">{applicant ? "My applications" : "Applications I can access"}</h2>
        {rows.length === 0 && <p className="rounded border bg-white p-4 text-sm text-slate-500">No applications available.</p>}
        {rows.map((row) => (
          <article key={row.id} className="flex flex-wrap items-center justify-between gap-4 rounded border bg-white p-4">
            <div className="space-y-1 text-sm">
              <p className="font-semibold">{row.applicant_name} · Property #{row.property_id}</p>
              <p className="text-slate-600">Status: {row.status.replaceAll("_", " ")} · Applicant #{row.applicant_user_id}</p>
              {row.unit_id && <p className="text-slate-600">Unit #{row.unit_id}</p>}
              <p className="text-slate-600">{row.applicant_email}</p>
              {row.move_in_date && <p className="text-slate-600">Requested move in: {row.move_in_date}</p>}
            </div>
            <div className="flex flex-wrap gap-2">
              <button type="button" onClick={() => setPrivateOpen((id) => id === row.id ? null : row.id)}
                className="rounded border px-3 py-2 text-sm">Private questionnaire</button>
            {applicant && row.status === "draft" && <div className="flex gap-2">
              <button type="button" disabled={busy} onClick={() => edit(row)}
                className="rounded border px-3 py-2 text-sm disabled:opacity-50">Edit</button>
              <button type="button" disabled={busy} onClick={() => { void submit(row.id); }}
                className="rounded bg-slate-900 px-3 py-2 text-sm text-white disabled:opacity-50">
                Submit, pending payment
              </button>
            </div>}
            </div>
          </article>
        ))}
      </section>}
      {privateOpen !== null && (
        <ApplicationPrivatePanel applicationId={privateOpen}
          canEdit={applicant && rows.some((row) => row.id === privateOpen && row.status === "draft")}
          onClose={() => setPrivateOpen(null)} />
      )}
    </div>
  );
}
