"use client";

import { useEffect, useState, type FormEvent } from "react";
import EntityAttachments from "@/components/EntityAttachments";
import { apiDelete, apiGet, apiPost, apiPut } from "@/lib/api";

type Viewer = { role: string };
type Addendum = {
  id: number; template_id: number; title: string; body: string;
  position: number; created_at: string; updated_at: string;
};
type Template = {
  id: number; title: string; body: string; property_id: number | null;
  organization_id: number; addenda: Addendum[];
};
type TemplatePayload = { title: string; body: string; property_id: number | null };
type AddendumPayload = { title: string; body: string; position: number };
const BASE = "/api/leasing/templates";

export default function LeaseTemplatesPage() {
  const [viewer, setViewer] = useState<Viewer | null>(null);
  const [rows, setRows] = useState<Template[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [propertyId, setPropertyId] = useState("");
  const [addendumId, setAddendumId] = useState<number | null>(null);
  const [addendumTitle, setAddendumTitle] = useState("");
  const [addendumBody, setAddendumBody] = useState("");
  const [addendumPosition, setAddendumPosition] = useState("0");
  const [attachmentTarget, setAttachmentTarget] = useState<{type: string; id: number} | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const admin = viewer?.role === "ADMIN";
  const selected = rows.find((row) => row.id === selectedId) || null;

  useEffect(() => {
    let mounted = true;
    async function load() {
      try {
        const [me, data] = await Promise.all([
          apiGet("/auth/me") as Promise<Viewer>,
          apiGet(BASE) as Promise<Template[]>,
        ]);
        if (!mounted) return;
        setViewer(me);
        setRows(data);
      } catch (cause) {
        if (mounted) setError(cause instanceof Error ? cause.message : "Unable to load lease templates.");
      } finally {
        if (mounted) setLoading(false);
      }
    }
    void load();
    return () => { mounted = false; };
  }, []);

  function select(row: Template | null) {
    setSelectedId(row?.id ?? null);
    setTitle(row?.title ?? "");
    setBody(row?.body ?? "");
    setPropertyId(row?.property_id ? String(row.property_id) : "");
    setAddendumId(null);
    setAddendumTitle("");
    setAddendumBody("");
    setAddendumPosition("0");
    setAttachmentTarget(null);
    setMessage("");
    setError("");
  }

  async function saveTemplate(event: FormEvent) {
    event.preventDefault();
    if (!admin) return;
    setBusy(true); setError(""); setMessage("");
    const property = propertyId.trim() ? Number(propertyId) : null;
    if (property !== null && (!Number.isSafeInteger(property) || property <= 0)) {
      setError("Enter a valid positive property ID or leave it blank.");
      setBusy(false);
      return;
    }
    const payload: TemplatePayload = { title: title.trim(), body, property_id: property };
    try {
      const saved = (selectedId === null
        ? await apiPost(BASE, payload)
        : await apiPut(`${BASE}/${selectedId}`, payload)) as Template;
      setRows((current) => [
        ...current.filter((row) => row.id !== saved.id), saved,
      ].sort((a, b) => a.id - b.id));
      setSelectedId(saved.id);
      setMessage("Lease draft saved. No document was sent or signed.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Lease draft could not be saved.");
    } finally {
      setBusy(false);
    }
  }

  async function deleteTemplate() {
    if (!admin || !selected || !window.confirm("Archive this lease template draft?")) return;
    setBusy(true); setError("");
    try {
      await apiDelete(`${BASE}/${selected.id}`);
      setRows((current) => current.filter((row) => row.id !== selected.id));
      select(null);
      setMessage("Draft archived.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to archive draft.");
    } finally {
      setBusy(false);
    }
  }

  function selectAddendum(row: Addendum | null) {
    setAddendumId(row?.id ?? null);
    setAddendumTitle(row?.title ?? "");
    setAddendumBody(row?.body ?? "");
    setAddendumPosition(String(row?.position ?? 0));
    setAttachmentTarget(null);
    setError(""); setMessage("");
  }

  async function saveAddendum(event: FormEvent) {
    event.preventDefault();
    if (!admin || selectedId === null) return;
    const position = Number(addendumPosition);
    if (!Number.isInteger(position) || position < 0 || position > 1000) {
      setError("Addendum position must be a whole number from 0 through 1000.");
      return;
    }
    setBusy(true); setError(""); setMessage("");
    const payload: AddendumPayload = {
      title: addendumTitle.trim(), body: addendumBody, position,
    };
    try {
      const saved = (addendumId === null
        ? await apiPost(`${BASE}/${selectedId}/addenda`, payload)
        : await apiPut(`${BASE}/${selectedId}/addenda/${addendumId}`, payload)) as Addendum;
      setRows((current) => current.map((row) => row.id === selectedId
        ? { ...row, addenda: [
          ...row.addenda.filter((entry) => entry.id !== saved.id), saved,
        ].sort((a, b) => a.position - b.position || a.id - b.id) }
        : row));
      selectAddendum(null);
      setMessage("Addendum draft saved.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to save addendum.");
    } finally {
      setBusy(false);
    }
  }

  async function deleteAddendum(row: Addendum) {
    if (!admin || selectedId === null || !window.confirm("Archive this addendum?")) return;
    setBusy(true); setError("");
    try {
      await apiDelete(`${BASE}/${selectedId}/addenda/${row.id}`);
      setRows((current) => current.map((item) => item.id === selectedId
        ? { ...item, addenda: item.addenda.filter((entry) => entry.id !== row.id) }
        : item));
      if (addendumId === row.id) selectAddendum(null);
      if (attachmentTarget?.type === "lease_template_addenda" && attachmentTarget.id === row.id) setAttachmentTarget(null);
      setMessage("Addendum archived.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to archive addendum.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-bold text-slate-900">Lease templates</h1>
        <p className="mt-1 text-sm text-slate-600">
          Draft a template, order its addenda, and attach supporting documents.
          Nothing on this page signs, activates, or sends a lease to a tenant.
        </p>
      </header>
      {loading && <p className="text-sm text-slate-500">Loading lease templates…</p>}
      {error && <p role="alert" className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</p>}
      {message && <p role="status" className="rounded-lg border border-green-200 bg-green-50 p-3 text-sm text-green-700">{message}</p>}
      {!loading && (
        <div className="grid gap-5 xl:grid-cols-[280px_1fr]">
          <aside className="rounded-xl border border-slate-200 bg-white p-4">
            <h2 className="font-semibold text-slate-900">Available drafts</h2>
            {admin && <button type="button" onClick={() => select(null)}
              className="mt-3 w-full rounded-lg bg-slate-900 px-3 py-2 text-sm text-white">
              New template
            </button>}
            {rows.length === 0 && <p className="mt-3 text-sm text-slate-500">No drafts available.</p>}
            <div className="mt-3 space-y-2">
              {rows.map((row) => (
                <button type="button" key={row.id} onClick={() => select(row)}
                  aria-pressed={selectedId === row.id}
                  className={`w-full rounded-lg border p-3 text-left text-sm ${selectedId === row.id
                    ? "border-slate-900 bg-slate-50" : "border-slate-200 hover:bg-slate-50"}`}>
                  <span className="block font-medium">{row.title}</span>
                  <span className="text-xs text-slate-500">{row.property_id === null
                    ? "Organization-wide" : `Property #${row.property_id}`}</span>
                </button>
              ))}
            </div>
          </aside>
          <main className="space-y-5">
            {admin && (
              <section className="rounded-xl border border-slate-200 bg-white p-5">
                <h2 className="text-lg font-semibold">{selected ? "Edit template" : "Create template"}</h2>
                <form onSubmit={(event) => { void saveTemplate(event); }} className="mt-3 space-y-3">
                  <label className="block text-sm font-medium">Title
                    <input required maxLength={120} value={title} onChange={(event) => setTitle(event.target.value)}
                      className="mt-1 w-full rounded-lg border p-2" />
                  </label>
                  <label className="block text-sm font-medium">Property ID (blank for organization-wide)
                    <input type="number" min={1} step={1} value={propertyId}
                      disabled={selected !== null} onChange={(event) => setPropertyId(event.target.value)}
                      className="mt-1 w-full rounded-lg border p-2" />
                  </label>
                  <label className="block text-sm font-medium">Plain-text template content
                    <textarea rows={8} maxLength={12000} required value={body}
                      onChange={(event) => setBody(event.target.value)}
                      className="mt-1 w-full rounded-lg border p-2" />
                  </label>
                  <p className="text-xs text-slate-500">
                    Available placeholders include {"{{tenant_name}}"}, {"{{property_name}}"} and {"{{unit_number}}"}.
                    They are saved as draft text only. HTML and executable expressions are rejected.
                  </p>
                  <div className="flex flex-wrap gap-2">
                    <button type="submit" disabled={busy}
                      className="rounded-lg bg-slate-900 px-4 py-2 text-sm text-white disabled:opacity-50">
                      {busy ? "Saving…" : selected ? "Save changes" : "Create draft"}
                    </button>
                    {selected && <button type="button" disabled={busy} onClick={() => { void deleteTemplate(); }}
                      className="rounded-lg border border-red-200 px-4 py-2 text-sm text-red-700">Archive</button>}
                  </div>
                </form>
              </section>
            )}
            {selected && (
              <>
                <section className="rounded-xl border border-slate-200 bg-white p-5">
                  <h2 className="font-semibold">{selected.title}</h2>
                  <p className="mt-1 text-xs text-slate-500">
                    {selected.property_id === null ? "Available within this organization" : `Property #${selected.property_id}`}
                  </p>
                  <pre className="mt-3 whitespace-pre-wrap break-words rounded-lg bg-slate-50 p-4 text-sm font-sans">{selected.body}</pre>
                  <div className="mt-4 flex flex-wrap gap-2">
                    <button type="button" onClick={() => setAttachmentTarget({type: "lease_templates", id: selected.id})}
                      className="rounded-lg border px-3 py-2 text-sm">Template attachments</button>
                  </div>
                </section>
                <section className="rounded-xl border border-slate-200 bg-white p-5">
                  <h2 className="font-semibold">Ordered addenda</h2>
                  {selected.addenda.length === 0 && <p className="mt-2 text-sm text-slate-500">No addenda recorded.</p>}
                  <div className="mt-3 space-y-3">
                    {selected.addenda.map((addendum) => (
                      <article key={addendum.id} className="rounded-lg border p-3">
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <h3 className="font-medium">{addendum.position}. {addendum.title}</h3>
                          <div className="flex flex-wrap gap-2">
                            <button type="button" onClick={() => setAttachmentTarget({type:"lease_template_addenda",id:addendum.id})}
                              className="rounded-md border px-3 py-1 text-xs">Attachments</button>
                            {admin && <>
                              <button type="button" onClick={() => selectAddendum(addendum)}
                                className="rounded-md border px-3 py-1 text-xs">Edit</button>
                              <button type="button" disabled={busy} onClick={() => { void deleteAddendum(addendum); }}
                                className="rounded-md border border-red-200 px-3 py-1 text-xs text-red-700">Archive</button>
                            </>}
                          </div>
                        </div>
                        <pre className="mt-2 whitespace-pre-wrap break-words text-sm font-sans">{addendum.body}</pre>
                      </article>
                    ))}
                  </div>
                  {admin && (
                    <form onSubmit={(event) => { void saveAddendum(event); }} className="mt-4 space-y-3 border-t pt-4">
                      <h3 className="font-semibold">{addendumId === null ? "Add addendum" : "Edit addendum"}</h3>
                      <label className="block text-sm font-medium">Title
                        <input required maxLength={120} value={addendumTitle} onChange={(event) => setAddendumTitle(event.target.value)}
                          className="mt-1 w-full rounded-lg border p-2" />
                      </label>
                      <label className="block text-sm font-medium">Order
                        <input required type="number" min={0} max={1000} step={1} value={addendumPosition}
                          onChange={(event) => setAddendumPosition(event.target.value)}
                          className="mt-1 w-full rounded-lg border p-2" />
                      </label>
                      <label className="block text-sm font-medium">Plain-text addendum
                        <textarea rows={5} required maxLength={12000} value={addendumBody}
                          onChange={(event) => setAddendumBody(event.target.value)}
                          className="mt-1 w-full rounded-lg border p-2" />
                      </label>
                      <div className="flex flex-wrap gap-2">
                        <button type="submit" disabled={busy} className="rounded-lg bg-slate-900 px-4 py-2 text-sm text-white disabled:opacity-50">
                          {busy ? "Saving…" : addendumId === null ? "Add draft" : "Save addendum"}
                        </button>
                        {addendumId !== null && <button type="button" onClick={() => selectAddendum(null)}
                          className="rounded-lg border px-4 py-2 text-sm">Cancel</button>}
                      </div>
                    </form>
                  )}
                </section>
                {attachmentTarget && (
                  <section className="rounded-xl border border-slate-200 bg-white p-5">
                    <div className="flex items-center justify-between gap-3">
                      <h2 className="font-semibold">Supporting attachments</h2>
                      <button type="button" onClick={() => setAttachmentTarget(null)}
                        className="rounded-lg border px-3 py-1.5 text-sm">Close</button>
                    </div>
                    <p className="my-2 text-xs text-slate-500">
                      Reuses the existing secure, organization-scoped business attachment service.
                      Do not upload W-9s or applicant sensitive information here.
                    </p>
                    <EntityAttachments key={attachmentTarget.type + attachmentTarget.id}
                      entityType={attachmentTarget.type} entityId={attachmentTarget.id}
                      canManage={Boolean(admin)} />
                  </section>
                )}
              </>
            )}
            {!selected && !admin && <p className="rounded-xl border bg-white p-6 text-sm text-slate-500">
              Select an available template to view its contents and addenda.
            </p>}
          </main>
        </div>
      )}
    </div>
  );
}
