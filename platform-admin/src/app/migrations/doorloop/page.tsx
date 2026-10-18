"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  PlatformUser, clearPlatformToken, getPlatformToken,
  platformGet, platformPost, platformPostForm,
} from "@/lib/platformApi";

const ROOT = "/api/platform/migrations/doorloop";
const READ_ROLES = ["PLATFORM_ADMIN", "PLATFORM_TECH", "PLATFORM_SUPPORT", "PLATFORM_DEV"];
const WRITE_ROLES = ["PLATFORM_ADMIN", "PLATFORM_TECH", "PLATFORM_DEV"];
const MAX_FILE_BYTES = 10 * 1024 * 1024;

type MigrationRun = {
  id: number;
  organization_id: number;
  provider: string;
  source_account_ref: string;
  status: string;
  created_at: string;
};
type Readiness = {
  source_contract_verified: boolean;
  official_api_enabled: boolean;
  file_staging_enabled: boolean;
  controlled_commit_enabled: boolean;
  customer_business_mutation: boolean;
  blocker: string;
};
type SourceInspection = {
  run_id: number;
  headers: string[];
  row_count: number;
  file_format: string;
  sheet_name: string | null;
  source_file_sha256: string;
  source_file_bytes: number;
  source_contract_verified: false;
  can_stage_import: false;
  can_commit_import: false;
};
type Quality = {
  total_rows: number;
  missing_values_by_proposed_field: Record<string, number>;
  duplicate_nonempty_identity_rows: number;
  identity_field_evaluated: string | null;
  rows_returned: false;
  mapping_stored: false;
  can_stage_import: false;
  can_commit_import: false;
  customer_business_mutation: false;
};
type FieldProposal = { id: number; field: string; header: string };

function describeError(error: unknown) {
  return error instanceof Error ? error.message : "Operation failed";
}

export default function DoorLoopMigrationConsole() {
  const router = useRouter();
  const [me, setMe] = useState<PlatformUser | null>(null);
  const [runs, setRuns] = useState<MigrationRun[]>([]);
  const [readiness, setReadiness] = useState<Readiness | null>(null);
  const [runReadiness, setRunReadiness] = useState<Readiness | null>(null);
  const [runLookup, setRunLookup] = useState("");
  const [selectedRunId, setSelectedRunId] = useState<number | null>(null);
  const [organizationId, setOrganizationId] = useState("");
  const [sourceAccountRef, setSourceAccountRef] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [sheetName, setSheetName] = useState("");
  const [inspection, setInspection] = useState<SourceInspection | null>(null);
  const [proposals, setProposals] = useState<FieldProposal[]>([]);
  const [identityField, setIdentityField] = useState("");
  const [quality, setQuality] = useState<Quality | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const role = String(me?.role || "").toUpperCase();
  const canWrite = WRITE_ROLES.includes(role);
  const selectedRun = runs.find((run) => run.id === selectedRunId);

  const load = useCallback(async () => {
    if (!getPlatformToken()) {
      router.replace("/login");
      return;
    }
    try {
      const actor = await platformGet("/api/platform/auth/me") as PlatformUser;
      if (!READ_ROLES.includes(String(actor.role).toUpperCase())) {
        setError("Your platform role does not have migration access.");
        setMe(actor);
        return;
      }
      const [list, info] = await Promise.all([
        platformGet(ROOT + "/runs?limit=100") as Promise<MigrationRun[]>,
        platformGet(ROOT + "/resource-readiness") as Promise<Readiness>,
      ]);
      setMe(actor);
      setRuns(list);
      setReadiness(info);
      setSelectedRunId((previous) => previous !== null && list.some((item) => item.id === previous)
        ? previous : (list[0]?.id ?? null));
    } catch (err) {
      setError(describeError(err));
    }
  }, [router]);

  useEffect(() => { void load(); }, [load]);

  useEffect(() => {
    if (selectedRunId === null || !READ_ROLES.includes(role)) {
      setRunReadiness(null);
      return;
    }
    let active = true;
    setRunReadiness(null);
    platformGet(ROOT + "/runs/" + selectedRunId + "/source-readiness")
      .then((status: Readiness) => { if (active) setRunReadiness(status); })
      .catch((err: unknown) => { if (active) setError(describeError(err)); });
    return () => { active = false; };
  }, [selectedRunId, role]);

  function clearExport() {
    setFile(null);
    setSheetName("");
    setInspection(null);
    setProposals([]);
    setIdentityField("");
    setQuality(null);
  }

  function selectRun(value: string) {
    const id = Number(value);
    setSelectedRunId(Number.isSafeInteger(id) && id > 0 ? id : null);
    clearExport();
    setError("");
    setNotice("");
  }

  function selectFile(next: File | null) {
    setFile(next);
    setInspection(null);
    setProposals([]);
    setIdentityField("");
    setQuality(null);
    setNotice("");
  }

  async function perform(operation: () => Promise<void>) {
    if (busy) return;
    setBusy(true);
    setError("");
    setNotice("");
    try { await operation(); }
    catch (err) { setError(describeError(err)); }
    finally { setBusy(false); }
  }

  async function openRun() {
    const id = Number(runLookup);
    if (!Number.isSafeInteger(id) || id < 1) {
      setError("Enter a positive migration run ID.");
      return;
    }
    await perform(async () => {
      const found = await platformGet(ROOT + "/runs/" + id) as MigrationRun;
      if (found.id !== id || found.provider !== "DOORLOOP")
        throw new Error("Requested DoorLoop run was not found.");
      setRuns((current) => current.some((run) => run.id === found.id)
        ? current.map((run) => run.id === found.id ? found : run)
        : [found, ...current].slice(0, 100));
      selectRun(String(found.id));
      setRunLookup("");
      setNotice("DoorLoop run #" + id + " opened for review.");
    });
  }

  async function createRun(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!canWrite) return;
    await perform(async () => {
      const id = Number(organizationId);
      if (!Number.isSafeInteger(id) || id < 1 || !sourceAccountRef.trim())
        throw new Error("Enter a valid organization ID and nonsecret export label.");
      const created = await platformPost(ROOT + "/runs", {
        organization_id: id, source_account_ref: sourceAccountRef.trim(),
      }) as MigrationRun;
      clearExport();
      await load();
      setRuns((previous) => previous.some((row) => row.id === created.id)
        ? previous : [created, ...previous].slice(0, 100));
      setSelectedRunId(created.id);
      setSourceAccountRef("");
      setNotice("DoorLoop DRAFT run created and audited. No customer records were changed.");
    });
  }

  async function inspect() {
    if (!canWrite || !selectedRun || !file) return;
    await perform(async () => {
      if (file.size > MAX_FILE_BYTES) throw new Error("Export exceeds the 10 MB limit.");
      const form = new FormData();
      form.append("file", file);
      if (sheetName.trim()) form.append("sheet_name", sheetName.trim());
      const info = await platformPostForm(ROOT + "/runs/" + selectedRun.id + "/inspect-source", form) as SourceInspection;
      if (info.run_id !== selectedRun.id || info.source_contract_verified || info.can_stage_import
          || info.can_commit_import) throw new Error("Unexpected migration inspection response.");
      setInspection(info);
      setProposals([]);
      setIdentityField("");
      setQuality(null);
      setNotice("Export inspected without storing source rows. Define fields explicitly for a quality review.");
    });
  }

  function addField() {
    setProposals((current) => current.length >= 100 ? current
      : [...current, { id: Math.max(0, ...current.map((row) => row.id)) + 1, field: "", header: "" }]);
    setQuality(null);
  }

  function updateField(id: number, name: "field" | "header", value: string) {
    setProposals((current) => current.map((row) => row.id === id ? { ...row, [name]: value } : row));
    setQuality(null);
  }

  async function preview() {
    if (!canWrite || !selectedRun || !file || !inspection) return;
    await perform(async () => {
      if (proposals.length === 0 || proposals.some((item) =>
        !item.field.trim() || !item.header || item.field.length > 100)) {
        throw new Error("Choose at least one named field and an inspected column for each field.");
      }
      const entries = proposals.map((item) => [item.field.trim(), item.header] as const);
      if (new Set(entries.map(([name]) => name)).size !== entries.length
          || new Set(entries.map(([, header]) => header)).size !== entries.length) {
        throw new Error("Field names and source columns must each be unique.");
      }
      const mapping = Object.fromEntries(entries);
      const form = new FormData();
      form.append("file", file);
      if (sheetName.trim()) form.append("sheet_name", sheetName.trim());
      form.append("column_mapping_json", JSON.stringify(mapping));
      form.append("expected_source_sha256", inspection.source_file_sha256);
      if (identityField) form.append("identity_field", identityField);
      const result = await platformPostForm(
        ROOT + "/runs/" + selectedRun.id + "/preview-source-quality", form
      ) as Quality;
      if (result.rows_returned !== false || result.mapping_stored !== false
          || result.can_stage_import !== false || result.can_commit_import !== false
          || result.customer_business_mutation !== false) {
        throw new Error("Unexpected non-read-only quality preview response.");
      }
      setQuality(result);
      setNotice("Read-only source quality checked against the inspected file fingerprint.");
    });
  }

  return (
    <main className="min-h-screen bg-slate-100 text-slate-950">
      <header className="bg-slate-950 text-white">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-3 px-6 py-5">
          <div>
            <p className="text-xs uppercase tracking-widest text-slate-400">Platform migrations / Phase 4.17</p>
            <h1 className="text-xl font-bold">DoorLoop export review</h1>
          </div>
          <button onClick={() => router.push("/dashboard")} className="rounded-lg border border-slate-500 px-3 py-2 text-sm">
            Back to dashboard
          </button>
        </div>
      </header>
      <div className="mx-auto max-w-6xl space-y-5 px-6 py-6">
        {error && <p role="alert" className="rounded-lg border border-red-300 bg-red-50 p-3 text-sm text-red-800">{error}</p>}
        {notice && <p role="status" className="rounded-lg border border-slate-200 bg-white p-3 text-sm">{notice}</p>}
        <section className="rounded-xl border bg-white p-5">
          <h2 className="font-semibold">Import capability and safety</h2>
          <p className="mt-1 text-sm text-slate-600">
            DoorLoop is in source-discovery mode. Source files are inspected in memory; this console does not
            store export rows or mappings, stage records, or write to customer accounts.
          </p>
          {readiness ? (
            <p className="mt-3 text-sm text-amber-800">{readiness.blocker}</p>
          ) : <p className="mt-3 text-sm">Checking provider readiness…</p>}
          <p className="mt-2 text-xs text-slate-500">Signed in as {me?.email || "…"} · {role.replaceAll("_", " ")}</p>
        </section>
        {me && READ_ROLES.includes(role) ? (
          <>
            <section className="rounded-xl border bg-white p-5">
              <h2 className="font-semibold">Migration runs</h2>
              <div className="mt-3 grid gap-3 md:grid-cols-2">
                <label className="text-sm">Choose an active-organization run
                  <select className="input mt-1" value={selectedRunId ?? ""} onChange={(event) => selectRun(event.target.value)}>
                    <option value="">Select a run</option>
                    {runs.map((run) => <option key={run.id} value={run.id}>
                      #{run.id} · Organization {run.organization_id} · {run.source_account_ref} · {run.status}
                    </option>)}
                  </select>
                </label>
                <div className="self-end text-sm text-slate-600">
                  {selectedRun ? `Run #${selectedRun.id} · ${selectedRun.status} · Organization ${selectedRun.organization_id}`
                    : "No DoorLoop runs found."}
                </div>
              </div>
              <div className="mt-4 flex flex-wrap items-end gap-3">
                <label className="w-44 text-sm">Open older run by ID
                  <input className="input mt-1" type="number" step="1" min="1" value={runLookup}
                    onChange={(event) => setRunLookup(event.target.value)} />
                </label>
                <button type="button" disabled={busy || !runLookup.trim()} onClick={() => void openRun()}
                  className="rounded-lg border px-4 py-2 text-sm disabled:opacity-50">Open run</button>
              </div>
              {selectedRun && (
                <p className="mt-3 text-sm text-amber-800">
                  Run-specific source status: {runReadiness
                    ? runReadiness.blocker
                    : "Checking approved source contract…"}
                </p>
              )}
              {canWrite && (
                <form onSubmit={(event) => void createRun(event)} className="mt-5 grid items-end gap-3 border-t pt-5 md:grid-cols-[140px_1fr_auto]">
                  <label className="text-sm">Organization ID
                    <input className="input mt-1" required type="number" min="1" step="1"
                      value={organizationId} onChange={(event) => setOrganizationId(event.target.value)} />
                  </label>
                  <label className="text-sm">Nonsecret source label
                    <input className="input mt-1" required maxLength={255} value={sourceAccountRef}
                      placeholder="Authorized-export-reference" onChange={(event) => setSourceAccountRef(event.target.value)} />
                  </label>
                  <button disabled={busy} className="rounded-lg bg-slate-950 px-4 py-2 text-sm text-white disabled:opacity-50">Create DRAFT run</button>
                </form>
              )}
            </section>
            {canWrite && selectedRun && (
              <section className="rounded-xl border bg-white p-5">
                <h2 className="font-semibold">1. Inspect an authorized export</h2>
                <p className="mt-1 text-sm text-slate-600">CSV or XLSX only, up to 10 MB. No source rows are displayed or saved.</p>
                <div className="mt-4 grid items-end gap-3 md:grid-cols-[1fr_200px_auto]">
                  <label className="text-sm">Export file
                    <input key={selectedRunId} className="input mt-1" type="file" accept=".csv,.xlsx" onChange={(event) => selectFile(event.target.files?.[0] ?? null)} />
                  </label>
                  <label className="text-sm">XLSX sheet (optional)
                    <input className="input mt-1" maxLength={255} value={sheetName} onChange={(event) => {
                      setSheetName(event.target.value); setInspection(null); setProposals([]); setQuality(null);
                    }} />
                  </label>
                  <button disabled={busy || !file} onClick={() => void inspect()}
                    className="rounded-lg bg-slate-950 px-4 py-2 text-sm text-white disabled:opacity-50">Inspect source</button>
                </div>
                {inspection && (
                  <>
                    <div className="mt-5 rounded-lg bg-slate-50 p-4 text-sm">
                      <p><strong>{inspection.row_count}</strong> data rows · {inspection.file_format.toUpperCase()} · {inspection.source_file_bytes} bytes</p>
                      <p className="mt-2 break-all font-mono text-xs">SHA-256: {inspection.source_file_sha256}</p>
                      <p className="mt-2 text-slate-600">Export columns: {inspection.headers.join(", ")}</p>
                    </div>
                    <div className="mt-5 flex items-center justify-between">
                      <div>
                        <h3 className="font-semibold">2. Propose source field mapping</h3>
                        <p className="text-sm text-slate-600">Generic quality labels only, not approved customer import mappings.</p>
                      </div>
                      <button disabled={busy || proposals.length >= 100} onClick={addField}
                        className="rounded-lg border px-3 py-2 text-sm disabled:opacity-50">Add field</button>
                    </div>
                    <div className="mt-3 space-y-2">
                      {proposals.map((row) => (
                        <div key={row.id} className="grid items-center gap-2 md:grid-cols-[1fr_1fr_auto]">
                          <input className="input" aria-label="Proposed field name" placeholder="Review label (e.g. reference)"
                            maxLength={100} value={row.field} onChange={(event) => updateField(row.id, "field", event.target.value)} />
                          <select className="input" aria-label="Source column" value={row.header}
                            onChange={(event) => updateField(row.id, "header", event.target.value)}>
                            <option value="">Select source column</option>
                            {inspection.headers.map((header) => <option key={header} value={header}>{header}</option>)}
                          </select>
                          <button className="rounded-lg border px-3 py-2 text-sm" onClick={() => {
                            setProposals((current) => current.filter((entry) => entry.id !== row.id));
                            if (identityField === row.field) setIdentityField("");
                            setQuality(null);
                          }}>Remove</button>
                        </div>
                      ))}
                    </div>
                    <div className="mt-4 flex flex-wrap items-end gap-3">
                      <label className="w-64 text-sm">Identity field for duplicate check (optional)
                        <select className="input mt-1" value={identityField} onChange={(event) => {
                          setIdentityField(event.target.value); setQuality(null);
                        }}>
                          <option value="">None</option>
                          {proposals.filter((row) => row.field.trim() && row.header).map((row) =>
                            <option key={row.id} value={row.field.trim()}>{row.field.trim()}</option>)}
                        </select>
                      </label>
                      <button disabled={busy || proposals.length === 0} onClick={() => void preview()}
                        className="rounded-lg bg-teal-900 px-4 py-2 text-sm text-white disabled:opacity-50">
                        Preview quality (read only)
                      </button>
                    </div>
                    {quality && (
                      <div className="mt-5 rounded-lg border border-slate-200 p-4 text-sm">
                        <h3 className="font-semibold">File-bound quality results</h3>
                        <p className="mt-2">Rows assessed: {quality.total_rows}</p>
                        <p>Duplicate nonempty identities: {quality.duplicate_nonempty_identity_rows}</p>
                        <ul className="mt-2 list-inside list-disc">
                          {Object.entries(quality.missing_values_by_proposed_field).map(([field, count]) => (
                            <li key={field}>{field}: {count} missing values</li>
                          ))}
                        </ul>
                        <p className="mt-3 text-slate-600">No mapping authorization, data staging, customer mutation or import commit was performed.</p>
                      </div>
                    )}
                  </>
                )}
              </section>
            )}
            {!canWrite && <p className="rounded-xl border bg-white p-5 text-sm text-slate-600">
              Your role can review run metadata and readiness, but cannot create runs, inspect exports or submit mappings.
            </p>}
          </>
        ) : null}
      </div>
    </main>
  );
}
