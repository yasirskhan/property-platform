"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  PlatformUser,
  clearPlatformToken,
  getPlatformToken,
  platformGet,
  platformPost,
  platformPostForm,
} from "@/lib/platformApi";

const ROOT = "/api/platform/migrations/yardi";
const RESOURCES = ["PROPERTIES", "UNITS", "OWNERS", "VENDORS", "TENANTS", "LEASE_OCCUPANCY"] as const;
type Resource = (typeof RESOURCES)[number];
const REQUIRED_FIELDS: Record<Resource, string[]> = {
  PROPERTIES: ["source_id", "name", "address_line1", "city", "state", "zip_code"],
  UNITS: ["source_id", "source_property_id", "unit_name"],
  OWNERS: ["source_id", "name"],
  VENDORS: ["source_id", "name"],
  TENANTS: ["source_id", "name"],
  LEASE_OCCUPANCY: ["source_id", "source_tenant_id", "source_property_id", "source_unit_id"],
};


type MigrationRun = {
  id: number;
  organization_id: number;
  provider: "YARDI";
  source_account_ref: string;
  status: string;
};
type MigrationUpload = {
  id: number;
  detected_resource: string;
  filename: string;
  status: string;
  row_count: number;
  headers: string[];
  column_mapping: Record<string, string>;
  validation_summary: Record<string, unknown>;
  replayed?: boolean;
};
type ExistingTargetCandidate = { id: number; label: string };
type StagedRow = {
  id: number;
  row_number: number;
  resource: string;
  source_id: string | null;
  disposition: string;
  resolution_action: string | null;
  resolution_target_id?: number | null;
  resolution_target_unit_id?: number | null;
  resolution_target_owner_user_id?: number | null;
  resolution_target_vendor_id?: number | null;
  resolution_target_tenant_user_id?: number | null;
  resolved_by_platform_user_id?: number | null;
  resolved_at?: string | null;
  correction_evidence?: { action?: string; reason_code?: string }[];
  errors: string[];
  warnings: string[];
};
type DurableBinding = {
  id: number;
  resource: Resource;
  source_id: string;
  target_entity: string;
  target_id: number;
  target_current: boolean;
  unit_parent_relationship_current: boolean | null;
  parent_source_identity_collision: boolean | null;
  parent_source_fingerprint_drift: boolean | null;
  parent_target_review_collision: boolean | null;
  parent_target_binding_collision: boolean | null;
  source_identity_collision: boolean;
  target_review_collision: boolean;
  target_binding_collision: boolean;
  source_target_binding_collision: boolean;
  parent_source_binding_collision: boolean | null;
  created_by_platform_user_id: number | null;
  created_at: string | null;
};
type DurableBindingInventory = {
  run_id: number;
  total: number;
  offset: number;
  items: DurableBinding[];
  read_only: true;
  customer_business_mutation: false;
};
type LeaseRelationshipRow = {
  staged_row_id: number;
  row_number: number;
  source_id: string | null;
  blockers: string[];
  identity_links_complete: boolean;
  relationship_review_recorded: boolean;
  relationship_review_current: boolean;
  unit_source_parent_matches_lease: boolean | null;
  occupancy_or_lease_authorized: false;
};
type LeaseRelationshipPreview = {
  run_id: number;
  total: number;
  offset: number;
  limit: number;
  items: LeaseRelationshipRow[];
  read_only: true;
  controlled_commit_enabled: false;
  customer_business_mutation: false;
};
type SourceCollisionEntry = {
  resource: Resource; source_id: string; row_count: number;
  upload_count: number; source_versions: number;
  conflicting_source_versions: boolean;
  skipped_rows: number; remaining_unskipped_rows: number;
  disposition_status: "ALL_SKIPPED" | "ONE_UNSKIPPED" | "UNRESOLVED_MULTIPLE";
  sampled_rows: { staged_row_id: number; upload_id: number; row_number: number; disposition: string; resolution_action: string | null; skip_reason_code: string | null }[];
  sample_truncated: boolean; requires_manual_reconciliation: true;
};
type SourceCollisionInventory = {
  total: number; items: SourceCollisionEntry[];
  read_only: true; auto_merge_enabled: false; customer_business_mutation: false;
};
type Reconciliation = {
  review_fingerprint: string;
  staged_rows: number;
  invalid_rows: number;
  unresolved_rows: number;
  durable_mapping_count: number;
  resource_coverage: Record<string, Record<string, number>>;
  lease_relationship_readiness: Record<string, number | boolean>;
  controlled_commit_enabled: false;
  customer_business_mutation: false;
};
type ReviewDryRun = {
  review_fingerprint: string;
  invalid_rows: number;
  unresolved_rows: number;
  replayed: boolean;
};
type ResourceReadiness = {
  resource_capabilities: Record<string, { reviewed_existing_target_binding: boolean }>;
  blocked_pending_source_contract: string[];
  financial_posting_enabled: boolean;
};

const MATCH_RESOURCES: Partial<Record<Resource, { endpoint: string; targetKey: string; bindPath: string; rowKey: keyof StagedRow }>> = {
  PROPERTIES: { endpoint: "match-property", targetKey: "target_property_id", bindPath: "properties/bind-reviewed-matches", rowKey: "resolution_target_id" },
  UNITS: { endpoint: "match-unit", targetKey: "target_unit_id", bindPath: "bind-reviewed-units", rowKey: "resolution_target_unit_id" },
  OWNERS: { endpoint: "match-owner", targetKey: "target_owner_user_id", bindPath: "bind-reviewed-owners", rowKey: "resolution_target_owner_user_id" },
  VENDORS: { endpoint: "match-vendor", targetKey: "target_vendor_id", bindPath: "bind-reviewed-vendors", rowKey: "resolution_target_vendor_id" },
  TENANTS: { endpoint: "match-tenant", targetKey: "target_tenant_user_id", bindPath: "bind-reviewed-tenants", rowKey: "resolution_target_tenant_user_id" },
};
const SKIP_REASONS = ["NOT_IN_SCOPE", "DUPLICATE_SOURCE", "ALREADY_HANDLED", "UNSUPPORTED_SOURCE"] as const;

function readableError(err: unknown) {
  return err instanceof Error ? err.message : "Request failed";
}

export default function YardiMigrationConsole() {
  const router = useRouter();
  const [me, setMe] = useState<PlatformUser | null>(null);
  const [runs, setRuns] = useState<MigrationRun[]>([]);
  const [selectedRunId, setSelectedRunId] = useState<number | null>(null);
  const [orgId, setOrgId] = useState("");
  const [sourceRef, setSourceRef] = useState("");
  const [uploads, setUploads] = useState<MigrationUpload[]>([]);
  const [selectedUploadId, setSelectedUploadId] = useState<number | null>(null);
  const [rows, setRows] = useState<StagedRow[]>([]);
  const [rowOffset, setRowOffset] = useState(0);
  const PAGE_SIZE = 200;
  const [resource, setResource] = useState<Resource>("PROPERTIES");
  const [file, setFile] = useState<File | null>(null);
  const [mappingText, setMappingText] = useState('{"source_id":"ID","name":"Name"}');
  const [sheetName, setSheetName] = useState("");
  const [sourceHeaders, setSourceHeaders] = useState<string[]>([]);
  const [sourceRowCount, setSourceRowCount] = useState<number | null>(null);
  const [bindingInventory, setBindingInventory] = useState<DurableBindingInventory | null>(null);
  const [bindingOffset, setBindingOffset] = useState(0);
  const [bindingFilter, setBindingFilter] = useState<Resource | "ALL">("ALL");
  const BINDING_PAGE_SIZE = 50;
  const [leasePreview, setLeasePreview] = useState<LeaseRelationshipPreview | null>(null);
  const [leaseOffset, setLeaseOffset] = useState(0);
  const LEASE_PAGE_SIZE = 50;
  const [sourceCollisions, setSourceCollisions] = useState<SourceCollisionInventory | null>(null);
  const [collisionOffset, setCollisionOffset] = useState(0);
  const [collisionResource, setCollisionResource] = useState<Resource | "ALL">("ALL");
  const COLLISION_PAGE_SIZE = 20;
  const [reconciliation, setReconciliation] = useState<Reconciliation | null>(null);
  const [readiness, setReadiness] = useState<ResourceReadiness | null>(null);
  const [dryRun, setDryRun] = useState<ReviewDryRun | null>(null);
  const [targetIds, setTargetIds] = useState<Record<number, string>>({});
  const [targetQueries, setTargetQueries] = useState<Record<number, string>>({});
  const [candidateResults, setCandidateResults] = useState<Record<number, ExistingTargetCandidate[]>>({});
  const [skipReasons, setSkipReasons] = useState<Record<number, string>>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [refreshKey, setRefreshKey] = useState(0);

  const role = String(me?.role || "").toUpperCase();
  const canWrite = ["PLATFORM_ADMIN", "PLATFORM_TECH", "PLATFORM_DEV"].includes(role);
  const selectedRun = runs.find((item) => item.id === selectedRunId);

  const loadRuns = useCallback(async () => {
    if (!getPlatformToken()) {
      router.replace("/login");
      return;
    }
    try {
      const actor = await platformGet("/api/platform/auth/me") as PlatformUser;
      setMe(actor);
      if (!["PLATFORM_ADMIN", "PLATFORM_TECH", "PLATFORM_SUPPORT", "PLATFORM_DEV"].includes(actor.role.toUpperCase())) {
        setError("Your platform role does not have migration access.");
        return;
      }
      const [runList, resourceStatus] = await Promise.all([
        platformGet(ROOT + "/runs?limit=100") as Promise<MigrationRun[]>,
        platformGet(ROOT + "/resource-readiness") as Promise<ResourceReadiness>,
      ]);
      setRuns(runList);
      setReadiness(resourceStatus);
      setSelectedRunId((previous) => {
        if (previous !== null && runList.some((run) => run.id === previous)) return previous;
        return runList.length ? runList[0].id : null;
      });
    } catch (err) {
      setError(readableError(err));
    }
  }, [router]);

  useEffect(() => {
    void loadRuns();
  }, [loadRuns]);

  useEffect(() => {
    if (selectedRunId === null) {
      return;
    }
    let active = true;
    Promise.all([
      platformGet(ROOT + "/runs/" + selectedRunId + "/uploads") as Promise<MigrationUpload[]>,
      platformGet(ROOT + "/runs/" + selectedRunId + "/reconciliation") as Promise<Reconciliation>,
    ]).then(([nextUploads, review]) => {
      if (!active) return;
      setDryRun((previous) => previous?.review_fingerprint === review.review_fingerprint ? previous : null);
      setUploads(nextUploads);
      setReconciliation(review);
      setSelectedUploadId((previous) => {
        if (previous !== null && nextUploads.some((upload) => upload.id === previous)) return previous;
        return nextUploads.length ? nextUploads[0].id : null;
      });
    }).catch((err: unknown) => {
      if (active) setError(readableError(err));
    });
    return () => { active = false; };
  }, [selectedRunId, refreshKey]);

  useEffect(() => {
    if (selectedRunId === null || selectedUploadId === null) {
      return;
    }
    let active = true;
    platformGet(ROOT + "/runs/" + selectedRunId + "/uploads/" + selectedUploadId + "/rows?offset=" + rowOffset + "&limit=" + PAGE_SIZE)
      .then((data: StagedRow[]) => { if (active) setRows(data); })
      .catch((err: unknown) => { if (active) setError(readableError(err)); });
    return () => { active = false; };
  }, [selectedRunId, selectedUploadId, rowOffset, refreshKey]);

  useEffect(() => {
    if (selectedRunId === null) {
      return;
    }
    let active = true;
    const query = new URLSearchParams({
      offset: String(bindingOffset), limit: String(BINDING_PAGE_SIZE),
    });
    if (bindingFilter !== "ALL") query.set("resource", bindingFilter);
    platformGet(ROOT + "/runs/" + selectedRunId + "/bindings?" + query.toString())
      .then((data: DurableBindingInventory) => {
        if (active) setBindingInventory(data);
      })
      .catch((err: unknown) => { if (active) setError(readableError(err)); });
    return () => { active = false; };
  }, [selectedRunId, bindingOffset, bindingFilter, refreshKey]);

  useEffect(() => {
    if (selectedRunId === null) return;
    let active = true;
    platformGet(
      ROOT + "/runs/" + selectedRunId + "/lease-relationships?offset="
        + leaseOffset + "&limit=" + LEASE_PAGE_SIZE
    ).then((data: LeaseRelationshipPreview) => {
      if (active) setLeasePreview(data);
    }).catch((err: unknown) => {
      if (active) setError(readableError(err));
    });
    return () => { active = false; };
  }, [selectedRunId, leaseOffset, refreshKey]);

  useEffect(() => {
    if (selectedRunId === null) return;
    let active = true;
    const query = new URLSearchParams({ offset: String(collisionOffset), limit: String(COLLISION_PAGE_SIZE) });
    if (collisionResource !== "ALL") query.set("resource", collisionResource);
    platformGet(ROOT + "/runs/" + selectedRunId + "/source-collisions?" + query.toString())
      .then((data: SourceCollisionInventory) => { if (active) setSourceCollisions(data); })
      .catch((err: unknown) => { if (active) setError(readableError(err)); });
    return () => { active = false; };
  }, [selectedRunId, collisionOffset, collisionResource, refreshKey]);

  async function perform(work: () => Promise<void>) {
    if (busy) return;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await work();
    } catch (err) {
      setError(readableError(err));
    } finally {
      setBusy(false);
    }
  }

  async function createRun(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!canWrite) return;
    await perform(async () => {
      const organizationId = Number(orgId);
      if (!Number.isSafeInteger(organizationId) || organizationId <= 0 || !sourceRef.trim()) {
        throw new Error("Provide a valid organization ID and non-secret source account label.");
      }
      const created = await platformPost(ROOT + "/runs", {
        organization_id: organizationId,
        source_account_ref: sourceRef.trim(),
      }) as MigrationRun;
      setSelectedRunId(created.id);
      setSelectedUploadId(null);
      setDryRun(null);
      await loadRuns();
      setNotice("Yardi migration run created. No provider credentials were stored.");
    });
  }

  function currentMapping(): Record<string, string> {
    try {
      const parsed: unknown = JSON.parse(mappingText);
      if (typeof parsed === "object" && parsed !== null && !Array.isArray(parsed)) {
        return parsed as Record<string, string>;
      }
    } catch {
      // The user can correct the invalid draft JSON below.
    }
    return {};
  }

  function chooseColumn(field: string, header: string) {
    const next = currentMapping();
    if (header) next[field] = header;
    else delete next[field];
    setMappingText(JSON.stringify(next, null, 2));
  }

  async function inspectSource() {
    if (!canWrite || selectedRunId === null) return;
    await perform(async () => {
      if (!file) throw new Error("Choose a CSV or XLSX export before inspecting its headers.");
      const form = new FormData();
      form.append("file", file);
      if (sheetName.trim()) form.append("sheet_name", sheetName.trim());
      const preview = await platformPostForm(
        ROOT + "/runs/" + selectedRunId + "/inspect-source", form
      ) as { headers: string[]; row_count: number; raw_source_stored: false };
      setSourceHeaders(preview.headers);
      setSourceRowCount(preview.row_count);
      setNotice("Source headers inspected. No rows returned or staged; choose explicit field mappings below.");
    });
  }

  async function uploadFile(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!canWrite || selectedRunId === null) return;
    await perform(async () => {
      if (!file) throw new Error("Choose a CSV or XLSX export.");
      const mapping: unknown = JSON.parse(mappingText);
      if (typeof mapping !== "object" || !mapping || Array.isArray(mapping)
          || !Object.entries(mapping).every(([key, value]) => key && typeof value === "string" && value.length)) {
        throw new Error("Column mapping must be a JSON object of target fields to source headers.");
      }
      const form = new FormData();
      form.append("file", file);
      form.append("resource", resource);
      form.append("column_mapping_json", JSON.stringify(mapping));
      if (sheetName.trim()) form.append("sheet_name", sheetName.trim());
      const uploaded = await platformPostForm(ROOT + "/runs/" + selectedRunId + "/uploads", form) as MigrationUpload;
      setSelectedUploadId(uploaded.id);
      setRowOffset(0);
      setRefreshKey((key) => key + 1);
      setDryRun(null);
      setNotice(uploaded.replayed ? "Existing staged upload reused." : "Export staged for explicit review only.");
    });
  }

  async function searchTargets(row: StagedRow) {
    if (!canWrite || selectedRunId === null || !MATCH_RESOURCES[row.resource as Resource]) return;
    await perform(async () => {
      const search = (targetQueries[row.id] ?? "").trim();
      if (search.length < 2 || search.length > 80) {
        throw new Error("Enter 2–80 characters of the existing target name or unit label.");
      }
      const result = await platformGet(
        ROOT + "/runs/" + selectedRunId + "/existing-targets?resource="
          + encodeURIComponent(row.resource) + "&q=" + encodeURIComponent(search) + "&limit=20"
      ) as { candidates: ExistingTargetCandidate[]; auto_match_enabled: false };
      setCandidateResults((previous) => ({ ...previous, [row.id]: result.candidates }));
      setNotice(result.candidates.length + " organization-scoped candidate(s). Select a target; searching never creates a match.");
    });
  }

  async function acceptLeaseRelationship(row: StagedRow) {
    if (!canWrite || selectedRunId === null || row.resource !== "LEASE_OCCUPANCY" || row.resolution_action) return;
    await perform(async () => {
      if (row.errors.length || row.disposition === "INVALID") {
        throw new Error("Invalid lease source rows cannot be accepted.");
      }
      await platformPost(
        ROOT + "/runs/" + selectedRunId + "/staged-rows/" + row.id + "/accept-lease-relationship", {}
      );
      setDryRun(null);
      setRefreshKey((key) => key + 1);
      setNotice("Exact source Property, Unit and Tenant identities reviewed; no lease, occupancy or financial data created.");
    });
  }

  async function reviewRow(row: StagedRow, action: "MATCH_EXISTING" | "SKIP") {
    if (!canWrite || selectedRunId === null || row.resolution_action) return;
    await perform(async () => {
      const base = ROOT + "/runs/" + selectedRunId + "/staged-rows/" + row.id;
      if (action === "SKIP") {
        const reason = skipReasons[row.id] || "NOT_IN_SCOPE";
        await platformPost(base + "/skip", { reason_code: reason });
      } else {
        if (row.errors.length || row.disposition === "INVALID") throw new Error("Invalid source rows cannot be matched to existing targets.");
        const config = MATCH_RESOURCES[row.resource as Resource];
        if (!config) throw new Error("Existing-target matching is not supported for this resource.");
        const targetId = Number(targetIds[row.id]);
        if (!Number.isSafeInteger(targetId) || targetId <= 0) {
          throw new Error("Enter a valid existing target ID for row " + row.row_number + ".");
        }
        await platformPost(base + "/" + config.endpoint, { [config.targetKey]: targetId });
      }
      setDryRun(null);
      setRefreshKey((key) => key + 1);
      setNotice("Staff review decision recorded. No customer record was changed.");
    });
  }

  async function bindReviewed(resourceToBind: Resource) {
    if (!canWrite || selectedRunId === null) return;
    await perform(async () => {
      const config = MATCH_RESOURCES[resourceToBind];
      if (!config) throw new Error("No existing-target binding for this resource.");
      if (!dryRun || !reconciliation || dryRun.review_fingerprint !== reconciliation.review_fingerprint) {
        throw new Error("Record a current exact-fingerprint dry run before binding existing targets.");
      }
      const result = await platformPost(ROOT + "/runs/" + selectedRunId + "/" + config.bindPath, {
        review_fingerprint: dryRun.review_fingerprint,
      }) as { bound: number; replayed: boolean; customer_business_mutation: false };
      setDryRun(null);
      setRefreshKey((key) => key + 1);
      setNotice(result.replayed ? "Existing source mappings confirmed on replay." : result.bound + " existing identity mappings recorded; customer data unchanged.");
    });
  }

  async function recordDryRun() {
    if (!canWrite || selectedRunId === null) return;
    await perform(async () => {
      const result = await platformPost(
        ROOT + "/runs/" + selectedRunId + "/review-dry-run", {}
      ) as ReviewDryRun;
      setDryRun(result);
      setNotice("Read-only reviewed snapshot recorded. No customer records or financial data committed.");
    });
  }

  return (
    <main className="min-h-screen bg-slate-100 text-slate-950">
      <header className="border-b border-slate-800 bg-slate-950 text-white">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
          <div>
            <p className="text-xs uppercase tracking-widest text-slate-400">Platform migrations / Phase 4.15</p>
            <h1 className="text-xl font-semibold">Yardi export migration</h1>
          </div>
          <div className="flex gap-2 text-sm">
            <button className="rounded-lg border border-slate-600 px-3 py-2" onClick={() => router.push("/dashboard")}>Dashboard</button>
            <button className="rounded-lg border border-slate-600 px-3 py-2" onClick={() => {
              clearPlatformToken();
              router.replace("/login");
            }}>Sign out</button>
          </div>
        </div>
      </header>
      <div className="mx-auto max-w-6xl space-y-6 p-6">
        <section className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-950">
          <p className="font-semibold">Export and review only — not a live Yardi connection.</p>
          <p className="mt-1">This console stages mapped CSV/XLSX source data and produces read-only reconciliation. It cannot create tenants, leases, ownership interests, payments, accounting entries, or synthetic history. Official Yardi API integration requires an independently verified source contract.</p>
        </section>
        {error && <p role="alert" className="rounded-lg border border-red-300 bg-red-50 p-3 text-sm text-red-800">{error}</p>}
        {notice && <p role="status" className="rounded-lg border border-slate-200 bg-white p-3 text-sm">{notice}</p>}
        <section className="rounded-xl border bg-white p-5">
          <h2 className="text-lg font-semibold">Migration runs</h2>
          <p className="mt-1 text-sm text-slate-600">Only authorized platform staff can create or modify runs.</p>
          <label className="mt-3 block text-sm" htmlFor="yardi-run">Select a run</label>
          <select id="yardi-run" className="input mt-1" value={selectedRunId ?? ""} onChange={(event) => {
            setSelectedRunId(event.target.value ? Number(event.target.value) : null);
            setSelectedUploadId(null);
            setRows([]);
            setRowOffset(0);
            setCandidateResults({});
            setTargetQueries({});
            setTargetIds({});
            setBindingInventory(null);
            setBindingOffset(0);
            setLeasePreview(null);
            setLeaseOffset(0);
            setSourceCollisions(null);
            setCollisionOffset(0);
            setCollisionResource("ALL");
            setDryRun(null);
          }}>
            <option value="">Select run</option>
            {runs.map((run) => (
              <option key={run.id} value={run.id}>#{run.id} · Org {run.organization_id} · {run.source_account_ref} · {run.status}</option>
            ))}
          </select>
          {canWrite && <form className="mt-4 grid gap-3 sm:grid-cols-[8rem_1fr_auto]" onSubmit={(event) => { void createRun(event); }}>
            <label className="text-sm">Organization ID<input className="input mt-1" required inputMode="numeric" value={orgId} onChange={(event) => setOrgId(event.target.value)} /></label>
            <label className="text-sm">Source account label (never credentials)<input className="input mt-1" required maxLength={255} value={sourceRef} onChange={(event) => setSourceRef(event.target.value)} /></label>
            <button type="submit" disabled={busy} className="self-end rounded-lg bg-slate-950 px-4 py-2 text-sm font-medium text-white disabled:opacity-50">Create run</button>
          </form>}
          {selectedRun && <p className="mt-3 text-xs text-slate-500">Selected run #{selectedRun.id} · Provider {selectedRun.provider} · Organization {selectedRun.organization_id}</p>}
        </section>

        {selectedRun && <section className="rounded-xl border bg-white p-5">
          <h2 className="text-lg font-semibold">Stage an export</h2>
          <p className="mt-1 text-sm text-slate-600">Map target fields to exact headers from the source file. Mapping is required; unrecognized financial resources are rejected. Raw file bytes are not persisted.</p>
          {canWrite && <form className="mt-4 space-y-3" onSubmit={(event) => { void uploadFile(event); }}>
            <label className="block text-sm">Resource
              <select className="input mt-1" value={resource} onChange={(event) => {
                setResource(event.target.value as Resource);
                setMappingText("{}");
              }}>
                {RESOURCES.map((item) => <option key={item} value={item}>{item.replaceAll("_", " ")}</option>)}
              </select>
            </label>
            <label className="block text-sm">CSV or XLSX file
              <input type="file" className="input mt-1" accept=".csv,.xlsx" required onChange={(event) => {
                setFile(event.target.files?.[0] ?? null);
                setSourceHeaders([]);
                setSourceRowCount(null);
              }} />
            </label>
            <label className="block text-sm">Selected XLSX sheet (optional)
              <input className="input mt-1" value={sheetName} onChange={(event) => setSheetName(event.target.value)} placeholder="Sheet1" />
            </label>
            <div>
              <button type="button" disabled={!file || busy} className="rounded-lg border border-slate-500 px-3 py-2 text-sm font-medium disabled:opacity-50" onClick={() => { void inspectSource(); }}>
                Inspect source headers
              </button>
              {sourceRowCount !== null && <p className="mt-2 text-xs text-slate-600">{sourceRowCount} source data rows inspected; no upload staged yet.</p>}
              {sourceHeaders.length > 0 && (
                <div className="mt-3 grid gap-3 rounded-lg border bg-slate-50 p-4 sm:grid-cols-2">
                  {REQUIRED_FIELDS[resource].map((field) => (
                    <label className="text-sm" key={field}>{field.replaceAll("_", " ")} (required)
                      <select className="input mt-1" value={currentMapping()[field] ?? ""} onChange={(event) => chooseColumn(field, event.target.value)}>
                        <option value="">Select source column</option>
                        {sourceHeaders.map((header) => <option key={header} value={header}>{header}</option>)}
                      </select>
                    </label>
                  ))}
                </div>
              )}
            </div>
            <label className="block text-sm">Explicit JSON header mapping
              <textarea className="input mt-1 min-h-28 font-mono text-xs" required value={mappingText} onChange={(event) => setMappingText(event.target.value)} spellCheck={false} />
            </label>
            <p className="text-xs text-slate-600">Example: { '{"source_id":"Vendor ID","name":"Company Name"}' }. Units also require source_property_id and unit_name; leases require source_tenant_id, source_property_id and source_unit_id.</p>
            <button type="submit" disabled={busy} className="rounded-lg bg-slate-950 px-4 py-2 text-sm font-medium text-white disabled:opacity-50">Stage for review</button>
          </form>}
          {!canWrite && <p className="mt-3 text-sm text-slate-600">Your platform role is read-only.</p>}
        </section>}

        {selectedRun && <section id="yardi-staged-uploads" className="rounded-xl border bg-white p-5">
          <h2 className="text-lg font-semibold">Staged uploads and rows</h2>
          <label className="mt-3 block text-sm" htmlFor="yardi-upload">Choose upload</label>
          <select id="yardi-upload" className="input mt-1" value={selectedUploadId ?? ""} onChange={(event) => {
            setSelectedUploadId(event.target.value ? Number(event.target.value) : null);
            setRows([]);
            setRowOffset(0);
            setCandidateResults({});
            setTargetIds({});
          }}>
            <option value="">Select an upload</option>
            {uploads.map((upload) => <option key={upload.id} value={upload.id}>#{upload.id} · {upload.detected_resource} · {upload.filename} · {upload.row_count} rows · {upload.status}</option>)}
          </select>
          <div className="mt-4 overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="border-b text-xs uppercase text-slate-500">
                <tr><th className="p-2">Row</th><th className="p-2">Resource</th><th className="p-2">Source ID</th><th className="p-2">Disposition</th><th className="p-2">Review</th><th className="p-2">Validation</th></tr>
              </thead>
              <tbody className="divide-y">
                {rows.map((row) => <tr key={row.id}>
                  <td className="p-2">{row.row_number}</td>
                  <td className="p-2">{row.resource}</td>
                  <td className="p-2 font-mono">{row.source_id ?? "—"}</td>
                  <td className="p-2">{row.disposition}</td>
                  <td className="p-2">
                    <span>{row.resolution_action ?? "PENDING"}</span>
                    {row.resolution_action && <div className="mt-1 text-xs text-slate-600">
                      {row.resolved_by_platform_user_id !== null && row.resolved_by_platform_user_id !== undefined && <span>Platform reviewer #{row.resolved_by_platform_user_id}</span>}
                      {row.resolved_at && <span className="block">{new Date(row.resolved_at).toLocaleString()}</span>}
                      {row.resolution_action === "SKIP" && row.correction_evidence?.filter((item) => item.action === "SKIP").map((item) => item.reason_code).filter(Boolean).slice(-1).map((reason) => <span className="block" key={reason}>Reason: {reason?.replaceAll("_", " ")}</span>)}
                    </div>}
                    {row.resolution_action === "MATCH_EXISTING" && <span className="block text-xs text-slate-600">Target #{String(row.resolution_target_id ?? row.resolution_target_unit_id ?? row.resolution_target_owner_user_id ?? row.resolution_target_vendor_id ?? row.resolution_target_tenant_user_id ?? "—")}</span>}
                    {canWrite && !row.resolution_action && <div className="mt-2 flex min-w-44 flex-col gap-2">
                      {row.resource === "LEASE_OCCUPANCY" && row.errors.length === 0 && row.disposition !== "INVALID" && (
                        <button type="button" disabled={busy} className="rounded border border-slate-600 px-2 py-1 text-xs disabled:opacity-50" onClick={() => { void acceptLeaseRelationship(row); }}>
                          Accept exact identity links (no lease)
                        </button>
                      )}
                      {row.errors.length === 0 && row.disposition !== "INVALID" && MATCH_RESOURCES[row.resource as Resource] && <>
                        <input className="input text-xs" placeholder="Search existing target name" maxLength={80} aria-label={"Search existing target for row " + row.row_number} value={targetQueries[row.id] ?? ""} onChange={(event) => { setTargetQueries((previous) => ({ ...previous, [row.id]: event.target.value })); setTargetIds((previous) => ({ ...previous, [row.id]: "" })); setCandidateResults((previous) => { const next = { ...previous }; delete next[row.id]; return next; }); }} />
                        <button type="button" disabled={busy} className="rounded border border-slate-500 px-2 py-1 text-xs disabled:opacity-50" onClick={() => { void searchTargets(row); }}>Find existing targets</button>
                        {candidateResults[row.id] && <select className="input text-xs" aria-label={"Choose existing target for row " + row.row_number} value={targetIds[row.id] ?? ""} onChange={(event) => setTargetIds((previous) => ({ ...previous, [row.id]: event.target.value }))}>
                          <option value="">Choose a reviewed target</option>
                          {candidateResults[row.id].map((candidate) => <option key={candidate.id} value={candidate.id}>#{candidate.id} — {candidate.label}</option>)}
                        </select>}
                        <input className="input text-xs" type="number" min="1" placeholder="Existing target ID" aria-label={"Existing target ID for row " + row.row_number} value={targetIds[row.id] ?? ""} onChange={(event) => setTargetIds((previous) => ({ ...previous, [row.id]: event.target.value }))} />
                        <button type="button" disabled={busy} className="rounded border border-slate-500 px-2 py-1 text-xs disabled:opacity-50" onClick={() => { void reviewRow(row, "MATCH_EXISTING"); }}>Review existing target</button>
                      </>}
                      <select className="input text-xs" aria-label={"Skip reason for row " + row.row_number} value={skipReasons[row.id] ?? "NOT_IN_SCOPE"} onChange={(event) => setSkipReasons((previous) => ({ ...previous, [row.id]: event.target.value }))}>
                        {SKIP_REASONS.map((reason) => <option key={reason} value={reason}>{reason.replaceAll("_", " ")}</option>)}
                      </select>
                      <button type="button" disabled={busy} className="rounded border border-amber-600 px-2 py-1 text-xs disabled:opacity-50" onClick={() => { void reviewRow(row, "SKIP"); }}>Record explicit skip</button>
                    </div>}
                  </td>
                  <td className="p-2 text-xs">{[...row.errors, ...row.warnings].join("; ") || "—"}</td>
                </tr>)}
                {!rows.length && <tr><td className="p-3 text-slate-500" colSpan={6}>No displayed rows. Select a staged upload.</td></tr>}
              </tbody>
            </table>
          </div>
          <div className="mt-3 flex flex-wrap items-center justify-between gap-3 text-xs">
            <p className="text-slate-600">Showing rows {rows.length ? rowOffset + 1 : 0}–{rowOffset + rows.length} for the selected upload. Review actions are scoped to the current row and migration run.</p>
            <div className="flex gap-2">
              <button type="button" disabled={busy || rowOffset === 0} className="rounded border px-3 py-2 disabled:opacity-50" onClick={() => { setRows([]); setRowOffset((offset) => Math.max(0, offset - PAGE_SIZE)); }}>Previous 200</button>
              <button type="button" disabled={busy || rows.length < PAGE_SIZE} className="rounded border px-3 py-2 disabled:opacity-50" onClick={() => { setRows([]); setRowOffset((offset) => offset + PAGE_SIZE); }}>Next 200</button>
            </div>
          </div>
        </section>}

        {selectedRun && <section className="rounded-xl border bg-white p-5">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h2 className="text-lg font-semibold">Read-only reconciliation</h2>
            <div className="flex gap-2">
              <button disabled={busy} className="rounded-lg border px-3 py-2 text-sm disabled:opacity-50" onClick={() => setRefreshKey((key) => key + 1)}>Refresh</button>
              {canWrite && <button disabled={busy} className="rounded-lg bg-slate-950 px-3 py-2 text-sm text-white disabled:opacity-50" onClick={() => { void recordDryRun(); }}>Record review dry run</button>}
            </div>
          </div>
          {reconciliation && <>
            <p className="mt-2 text-sm">Staged: {reconciliation.staged_rows} · Invalid: {reconciliation.invalid_rows} · Needs review: {reconciliation.unresolved_rows} · Durable source mappings: {reconciliation.durable_mapping_count}</p>
            <p className="mt-2 break-all font-mono text-xs text-slate-500">Current fingerprint: {reconciliation.review_fingerprint}</p>
            <p className="mt-2 text-xs text-slate-700">
              Lease source identity links complete: {reconciliation.lease_relationship_readiness.complete_identity_links ?? 0}
              {" · "}Current Unit/Property mismatches: {reconciliation.lease_relationship_readiness.unit_property_mismatch ?? 0}
              {" · "}Original Unit source-parent conflicts: {reconciliation.lease_relationship_readiness.unit_source_parent_mismatch ?? 0}
              {" · "}Unskipped lease source-ID collision rows: {reconciliation.lease_relationship_readiness.lease_source_id_collisions ?? 0}
              {" · "}Lease rows with conflicting Property/Unit/Tenant source identities: {reconciliation.lease_relationship_readiness.identity_source_id_collisions ?? 0}
              {" · "}Lease rows with competing reviewed customer targets: {reconciliation.lease_relationship_readiness.identity_target_review_collisions ?? 0}
              {" · "}Lease rows with competing durable customer targets: {reconciliation.lease_relationship_readiness.identity_target_binding_collisions ?? 0}
              {" · "}Lease rows with divergent durable Yardi source identities: {reconciliation.lease_relationship_readiness.identity_source_binding_collisions ?? 0}
              {" · "}Stale accepted lease source reviews: {reconciliation.lease_relationship_readiness.accepted_relationship_stale ?? 0}.
              These counts are diagnostic only and never authorize occupancy or financial commits.
            </p>
            <ul className="mt-3 grid gap-2 sm:grid-cols-2">
              {Object.entries(reconciliation.resource_coverage).map(([name, stats]) => (
                <li key={name} className="rounded-lg border p-3 text-sm">
                  <strong>{name}</strong>
                  <p className="mt-1 text-slate-600">{stats.total ?? 0} staged · {stats.matched_existing ?? 0} reviewed matches · {stats.needs_review ?? 0} unresolved · {stats.invalid ?? 0} invalid{name === "LEASE_OCCUPANCY" ? " · " + (stats.accepted_relationship_review ?? 0) + " identity reviews recorded" : ""}</p>
                </li>
              ))}
            </ul>
            <p className="mt-3 text-sm font-medium text-amber-800">Customer record commit: disabled. Financial posting: disabled.</p>
            {dryRun && <p className="mt-2 break-all text-xs text-slate-500">Recorded review fingerprint: {dryRun.review_fingerprint}</p>}
            {canWrite && <div className="mt-4 border-t pt-3">
              <h3 className="text-sm font-semibold">Commit reviewed identity mappings only</h3>
              <p className="my-2 text-xs text-slate-600">Requires explicit row matching and the current dry-run fingerprint. No Property, Unit, Owner, Vendor, Tenant, lease, payment or accounting record will be created or overwritten.</p>
              <div className="flex flex-wrap gap-2">
                {RESOURCES.filter((item) => !!MATCH_RESOURCES[item] && (reconciliation.resource_coverage[item]?.total ?? 0) > 0).map((item) =>
                  <button key={item} type="button" disabled={busy || !dryRun || dryRun.review_fingerprint !== reconciliation.review_fingerprint} onClick={() => { void bindReviewed(item); }} className="rounded border border-slate-600 px-3 py-2 text-xs disabled:opacity-50">Bind reviewed {item.toLowerCase()} identities</button>
                )}
              </div>
            </div>}
          </>}
        </section>}
        {selectedRun && <section className="rounded-xl border bg-white p-5">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h2 className="text-lg font-semibold">Cross-upload source ID collisions</h2>
            <button type="button" disabled={busy} onClick={() => setRefreshKey((key) => key + 1)} className="rounded border px-3 py-2 text-xs">Refresh</button>
          </div>
          <p className="mt-2 text-sm">Repeated stable source IDs must be manually reviewed, whether their source rows are identical or changed. No automatic merge or customer mutation.</p>
          <label htmlFor="yardi-collision-resource" className="mt-3 block text-sm">Resource</label>
          <select id="yardi-collision-resource" className="input mt-1" value={collisionResource} onChange={(event) => {
            setCollisionResource(event.target.value as Resource | "ALL");
            setCollisionOffset(0);
            setSourceCollisions(null);
          }}>
            <option value="ALL">All resources</option>
            {RESOURCES.map((item) => <option key={item} value={item}>{item}</option>)}
          </select>
          <p className="mt-2 text-xs">{sourceCollisions?.total ?? "…"} repeated source-ID groups.</p>
          <div className="mt-3 overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead><tr><th className="p-2">Resource and source ID</th><th className="p-2">Versions</th><th className="p-2">Review disposition</th><th className="p-2">Staged row locations</th></tr></thead>
              <tbody className="divide-y">
                {sourceCollisions?.items.map((item) => <tr key={item.resource + item.source_id}>
                  <td className="p-2">{item.resource}: <span className="font-mono">{item.source_id}</span></td>
                  <td className="p-2">{item.conflicting_source_versions ? "Different source values" : "Duplicate source values"} · {item.source_versions} versions, {item.upload_count} uploads</td>
                  <td className="p-2 text-xs">
                    {item.disposition_status === "UNRESOLVED_MULTIPLE"
                      ? "Unresolved: multiple versions still unskipped"
                      : item.disposition_status === "ONE_UNSKIPPED"
                        ? "One unskipped source row; inspect its current review state"
                        : "All source rows explicitly skipped"}
                    <span className="block">{item.skipped_rows} skipped · {item.remaining_unskipped_rows} unskipped</span>
                  </td>
                  <td className="p-2 text-xs">{item.sampled_rows.map((sample) =>
                    <div key={sample.staged_row_id} className="mb-1">
                      Upload #{sample.upload_id}, row {sample.row_number} (staged #{sample.staged_row_id})
                      {" · "}{sample.resolution_action === "SKIP"
                        ? "SKIP: " + (sample.skip_reason_code ?? "reason unavailable")
                        : sample.resolution_action ?? "PENDING"}
                      {uploads.some((upload) => upload.id === sample.upload_id) &&
                        <button type="button" className="ml-2 underline disabled:opacity-50" disabled={busy}
                          onClick={() => {
                            setSelectedUploadId(sample.upload_id);
                            setRows([]);
                            setRowOffset(0);
                            setCandidateResults({});
                            setTargetIds({});
                            // Reload even when staff select the upload already on page one.
                            setRefreshKey((key) => key + 1);
                            document.getElementById("yardi-staged-uploads")?.scrollIntoView({ behavior: "smooth" });
                          }}>Review upload</button>}
                    </div>
                  )}{item.sample_truncated && <span>More rows exist; counts include all staged versions.</span>}</td>
                </tr>)}
                {sourceCollisions?.items.length === 0 && <tr><td colSpan={4} className="p-3">No source-ID collision groups detected.</td></tr>}
              </tbody>
            </table>
          </div>
          <div className="mt-3 flex justify-between text-xs">
            <span>{collisionOffset + (sourceCollisions?.items.length ? 1 : 0)}–{collisionOffset + (sourceCollisions?.items.length ?? 0)} of {sourceCollisions?.total ?? 0}</span>
            <div className="flex gap-2">
              <button type="button" disabled={busy || collisionOffset === 0} onClick={() => { setSourceCollisions(null); setCollisionOffset((n) => Math.max(0, n - COLLISION_PAGE_SIZE)); }}>Previous</button>
              <button type="button" disabled={busy || !sourceCollisions || collisionOffset + sourceCollisions.items.length >= sourceCollisions.total} onClick={() => { setSourceCollisions(null); setCollisionOffset((n) => n + COLLISION_PAGE_SIZE); }}>Next</button>
            </div>
          </div>
        </section>}
        {selectedRun && <section className="rounded-xl border bg-white p-5">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h2 className="text-lg font-semibold">Lease source relationship review</h2>
            <button type="button" disabled={busy} className="rounded border px-3 py-2 text-xs disabled:opacity-50" onClick={() => setRefreshKey((key) => key + 1)}>Refresh relationships</button>
          </div>
          <p className="mt-2 text-sm text-slate-600">
            Read-only diagnostics for staged lease source IDs against the same-run Property, Unit and Tenant identity bindings. Complete identity links do not authorize a lease, occupancy, rent, payment, deposit or accounting import.
          </p>
          <div className="mt-3 overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="border-b text-xs uppercase text-slate-500">
                <tr><th className="p-2">Source lease</th><th className="p-2">Row</th><th className="p-2">Identity dependencies</th><th className="p-2">Customer mutation</th></tr>
              </thead>
              <tbody className="divide-y">
                {leasePreview?.items.map((item) => <tr key={item.staged_row_id}>
                  <td className="p-2 font-mono text-xs">{item.source_id ?? "—"}</td>
                  <td className="p-2">{item.row_number}</td>
                  <td className="p-2">
                    <span>{item.identity_links_complete
                      ? "Identity links found — lease still not authorized"
                      : item.blockers.map((blocker) => blocker.replaceAll("_", " ").toLowerCase()).join("; ")}</span>
                    {item.relationship_review_recorded && <span className="block text-xs font-medium">{item.relationship_review_current ? "Accepted review remains current" : "Accepted review is stale — reconcile before further action"}</span>}
                    <span className="mt-1 block text-xs text-slate-600">
                      {item.unit_source_parent_matches_lease === true
                        ? "Original Unit source parent agrees"
                        : item.unit_source_parent_matches_lease === false
                          ? "Original Unit source parent conflicts — reconcile"
                          : "Original Unit source parent not verified"}
                    </span>
                  </td>
                  <td className="p-2">Disabled</td>
                </tr>)}
                {leasePreview?.items.length === 0 && <tr><td colSpan={4} className="p-3 text-slate-500">No staged lease source identities for this selection.</td></tr>}
              </tbody>
            </table>
          </div>
          <div className="mt-3 flex flex-wrap items-center justify-between gap-3 text-xs">
            <span>Showing {leasePreview?.items.length ? leaseOffset + 1 : 0}–{leaseOffset + (leasePreview?.items.length ?? 0)} of {leasePreview?.total ?? 0} source lease rows.</span>
            <div className="flex gap-2">
              <button type="button" disabled={busy || leaseOffset === 0} className="rounded border px-3 py-2 disabled:opacity-50" onClick={() => { setLeasePreview(null); setLeaseOffset((offset) => Math.max(0, offset - LEASE_PAGE_SIZE)); }}>Previous</button>
              <button type="button" disabled={busy || !leasePreview || leaseOffset + leasePreview.items.length >= leasePreview.total} className="rounded border px-3 py-2 disabled:opacity-50" onClick={() => { setLeasePreview(null); setLeaseOffset((offset) => offset + LEASE_PAGE_SIZE); }}>Next</button>
            </div>
          </div>
        </section>}
        {selectedRun && <section className="rounded-xl border bg-white p-5">
          <h2 className="text-lg font-semibold">Committed identity mappings</h2>
          <p className="mt-2 text-sm text-slate-600">Durable Yardi source-to-existing-target metadata. Status checks confirm the target is still active in this organization; mappings never create or update customer business records.</p>
          <div className="mt-3 flex flex-wrap items-center gap-3">
            <label htmlFor="yardi-binding-resource" className="text-sm">Resource</label>
            <select id="yardi-binding-resource" className="input" value={bindingFilter} onChange={(event) => {
              setBindingFilter(event.target.value as Resource | "ALL");
              setBindingOffset(0);
              setBindingInventory(null);
            }}>
              <option value="ALL">All identity resources</option>
              {RESOURCES.filter((item) => item !== "LEASE_OCCUPANCY").map((item) => <option key={item} value={item}>{item.replaceAll("_", " ")}</option>)}
            </select>
            <button type="button" disabled={busy} className="rounded border px-3 py-2 text-xs disabled:opacity-50" onClick={() => setRefreshKey((key) => key + 1)}>Refresh mappings</button>
          </div>
          <p className="mt-2 text-xs text-slate-600">{bindingInventory ? bindingInventory.total : "…"} matching durable mappings in this run.</p>
          <div className="mt-3 overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="border-b text-xs uppercase text-slate-500">
                <tr><th className="p-2">Resource</th><th className="p-2">Yardi source ID</th><th className="p-2">Existing target</th><th className="p-2">Current status</th><th className="p-2">Recorded by</th></tr>
              </thead>
              <tbody className="divide-y">
                {bindingInventory?.items.map((item) => <tr key={item.id}>
                  <td className="p-2">{item.resource}</td>
                  <td className="p-2 font-mono text-xs">{item.source_id}</td>
                  <td className="p-2 font-mono text-xs">{item.target_entity} #{item.target_id}</td>
                  <td className="p-2">
                    <span>{item.target_current ? "Active target" : "Unavailable — reconcile"}</span>
                    {item.source_identity_collision && <span className="mt-1 block text-xs font-semibold text-amber-800">Unskipped source-ID collision — review duplicate uploads</span>}
                    {item.target_review_collision && <span className="mt-1 block text-xs font-semibold text-amber-800">Another reviewed source claims this target — reconcile</span>}
                    {item.target_binding_collision && <span className="mt-1 block text-xs font-semibold text-amber-800">Another durable Yardi source identity is bound to this target — reconcile</span>}
                    {item.source_target_binding_collision && <span className="mt-1 block text-xs font-semibold text-amber-800">This Yardi source identity is bound to another customer target — reconcile</span>}
                    {item.resource === "UNITS" && <span className="mt-1 block text-xs text-slate-600">
                      {item.source_identity_collision ? "Source parent unverified until Unit duplicates are resolved" : (item.target_review_collision || item.target_binding_collision) ? "Customer Unit target has competing Yardi source claims — original parent unverified" : item.source_target_binding_collision ? "Unit source identity has another customer target — original parent unverified" : item.parent_source_identity_collision ? "Mapped Property source has unresolved duplicates — reconcile parent identity" : item.parent_source_fingerprint_drift ? "Mapped Property source version changed — re-review parent" : item.parent_target_review_collision ? "Another reviewed Yardi Property source claims this Unit's mapped parent — reconcile" : item.parent_target_binding_collision ? "Another durable Yardi Property identity claims this Unit's mapped parent — reconcile" : item.parent_source_binding_collision ? "Mapped Yardi Property source identity points at another customer Property — reconcile" : item.unit_parent_relationship_current === true ? "Source parent verified" : item.unit_parent_relationship_current === false ? "Source parent mismatch — reconcile" : "Source parent not verified"}
                    </span>}
                  </td>
                  <td className="p-2 text-xs">
                    {item.created_by_platform_user_id == null ? "System/unknown" : "Staff #" + item.created_by_platform_user_id}
                    {item.created_at && <span className="block">{new Date(item.created_at).toLocaleString()}</span>}
                  </td>
                </tr>)}
                {bindingInventory?.items.length === 0 && <tr><td className="p-3 text-slate-500" colSpan={5}>No committed metadata bindings in this selection.</td></tr>}
              </tbody>
            </table>
          </div>
          <div className="mt-3 flex flex-wrap items-center justify-between gap-3 text-xs">
            <span>Displaying {bindingInventory?.items.length ? bindingOffset + 1 : 0}–{bindingOffset + (bindingInventory?.items.length ?? 0)} of {bindingInventory?.total ?? 0}.</span>
            <div className="flex gap-2">
              <button type="button" disabled={busy || bindingOffset === 0} className="rounded border px-3 py-2 disabled:opacity-50" onClick={() => setBindingOffset((offset) => Math.max(0, offset - BINDING_PAGE_SIZE))}>Previous</button>
              <button type="button" disabled={busy || !bindingInventory || bindingOffset + bindingInventory.items.length >= bindingInventory.total} className="rounded border px-3 py-2 disabled:opacity-50" onClick={() => setBindingOffset((offset) => offset + BINDING_PAGE_SIZE)}>Next</button>
            </div>
          </div>
        </section>}
        {readiness && <section className="rounded-xl border bg-white p-5">
          <h2 className="text-lg font-semibold">Source contract boundaries</h2>
          <p className="mt-2 text-sm">Existing-target metadata review: {Object.entries(readiness.resource_capabilities).filter(([, value]) => value.reviewed_existing_target_binding).map(([key]) => key).join(", ")}.</p>
          <p className="mt-2 text-xs text-slate-600">Unsupported without authoritative source contracts: {readiness.blocked_pending_source_contract.join(", ")}.</p>
          <p className="mt-2 text-xs font-semibold text-slate-600">Accounting posting enabled: {String(readiness.financial_posting_enabled)}</p>
        </section>}
      </div>
    </main>
  );
}
