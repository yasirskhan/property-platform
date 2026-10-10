"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import {
  PlatformUser,
  clearPlatformToken,
  getPlatformToken,
  platformGet,
  platformPatch,
  platformPost,
  platformPut,
} from "@/lib/platformApi";

type Organization = {
  id: number;
  name: string;
  slug: string;
  state: string;
  currency: string;
  data_region: string;
  is_active: boolean;
  subscription_status: string | null;
  plan_name: string | null;
};

type PricingTier = {
  id: number;
  min_properties: number;
  max_properties: number | null;
  monthly_price_cents: number;
  currency: string;
};

type Plan = {
  id: number;
  code: string;
  name: string;
  description: string | null;
  is_active: boolean;
  module_keys: string[];
  pricing_tiers: PricingTier[];
};

type Gate = {
  key: string;
  stage: "HIDDEN" | "INTERNAL" | "BETA" | "ALL_ORGS";
  organization_ids: number[];
  updated_at: string;
};

type FraudCase = {
  id: number;
  organization_id: number | null;
  status: string;
  risk_level: string;
  risk_score: number | null;
  reason: string;
};

type AuditRow = {
  id: number;
  platform_user_email: string | null;
  organization_id: number | null;
  entity_type: string;
  entity_id: number;
  action: string;
  created_at: string;
};

type Tab = "organizations" | "plans" | "release" | "fraud" | "audit";

const tabs: { id: Tab; label: string }[] = [
  { id: "organizations", label: "Organizations" },
  { id: "plans", label: "Plans" },
  { id: "release", label: "Release Gates" },
  { id: "fraud", label: "Fraud Review" },
  { id: "audit", label: "Staff Audit" },
];

function money(cents: number, currency = "USD") {
  return new Intl.NumberFormat("en-US", { style: "currency", currency }).format(cents / 100);
}

function Badge({ value }: { value: string }) {
  return <span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-medium text-slate-700">{value.replaceAll("_", " ")}</span>;
}

export default function PlatformDashboard() {
  const router = useRouter();
  const [me, setMe] = useState<PlatformUser | null>(null);
  const [tab, setTab] = useState<Tab>("organizations");
  const [organizations, setOrganizations] = useState<Organization[]>([]);
  const [plans, setPlans] = useState<Plan[]>([]);
  const [gates, setGates] = useState<Gate[]>([]);
  const [fraud, setFraud] = useState<FraudCase[]>([]);
  const [audit, setAudit] = useState<AuditRow[]>([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const role = String(me?.role || "").toUpperCase();
  const canCreateOrg = ["PLATFORM_ADMIN", "PLATFORM_SALES"].includes(role);
  const canManagePlan = ["PLATFORM_ADMIN", "PLATFORM_BILLING"].includes(role);
  const canManageRelease = ["PLATFORM_ADMIN", "PLATFORM_DEV"].includes(role);
  const canReviewFraud = ["PLATFORM_ADMIN", "PLATFORM_BILLING", "PLATFORM_SUPPORT"].includes(role);
  const canViewAudit = ["PLATFORM_ADMIN", "PLATFORM_BILLING", "PLATFORM_TECH", "PLATFORM_SUPPORT", "PLATFORM_DEV"].includes(role);

  const visibleTabs = useMemo(() => tabs.filter((item) => {
    if (item.id === "plans") return ["PLATFORM_ADMIN", "PLATFORM_SALES", "PLATFORM_BILLING"].includes(role);
    if (item.id === "release") return canManageRelease;
    if (item.id === "fraud") return ["PLATFORM_ADMIN", "PLATFORM_BILLING", "PLATFORM_SUPPORT", "PLATFORM_TECH"].includes(role);
    if (item.id === "audit") return canViewAudit;
    return true;
  }), [role, canManageRelease, canViewAudit]);

  const load = useCallback(async () => {
    setError("");
    try {
      const current: PlatformUser = await platformGet("/api/platform/auth/me");
      setMe(current);
      const normalized = String(current.role || "").toUpperCase();
      const calls: Promise<unknown>[] = [
        platformGet("/api/platform/admin/organizations").then(setOrganizations),
      ];
      if (["PLATFORM_ADMIN", "PLATFORM_SALES", "PLATFORM_BILLING"].includes(normalized)) calls.push(platformGet("/api/platform/admin/plans").then(setPlans));
      if (["PLATFORM_ADMIN", "PLATFORM_DEV"].includes(normalized)) calls.push(platformGet("/api/platform/flags").then(setGates));
      if (["PLATFORM_ADMIN", "PLATFORM_BILLING", "PLATFORM_SUPPORT", "PLATFORM_TECH"].includes(normalized)) calls.push(platformGet("/api/platform/fraud/cases").then(setFraud));
      if (["PLATFORM_ADMIN", "PLATFORM_BILLING", "PLATFORM_TECH", "PLATFORM_SUPPORT", "PLATFORM_DEV"].includes(normalized)) calls.push(platformGet("/api/platform/admin/audit").then(setAudit));
      await Promise.all(calls);
    } catch (err) {
      clearPlatformToken();
      setError(err instanceof Error ? err.message : "Unable to load platform console");
      router.replace("/login");
    }
  }, [router]);

  useEffect(() => {
    if (!getPlatformToken()) {
      router.replace("/login");
      return;
    }
    void load();
  }, [load, router]);

  function logout() {
    clearPlatformToken();
    router.replace("/login");
  }

  async function action(work: () => Promise<unknown>) {
    setBusy(true);
    setError("");
    try {
      await work();
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Operation failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="min-h-screen bg-slate-100">
      <header className="border-b border-slate-800 bg-slate-950 text-white">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-4">
          <div>
            <p className="text-xs font-semibold tracking-[0.18em] text-slate-400 uppercase">Internal Operations</p>
            <h1 className="text-xl font-bold">Platform Admin</h1>
          </div>
          <div className="flex items-center gap-4 text-sm">
            <div className="text-right">
              <p>{me?.email || "Loading…"}</p>
              <p className="text-xs text-slate-400">{role.replaceAll("_", " ")}</p>
            </div>
            <button className="rounded-lg border border-slate-700 px-3 py-2" onClick={logout}>Sign out</button>
          </div>
        </div>
      </header>

      <div className="mx-auto max-w-7xl px-6 py-6">
        <nav className="mb-6 flex flex-wrap gap-2">
          {visibleTabs.map((item) => (
            <button key={item.id} onClick={() => setTab(item.id)} className={"rounded-lg px-4 py-2 text-sm font-medium " + (tab === item.id ? "bg-slate-950 text-white" : "bg-white text-slate-700 hover:bg-slate-200")}>
              {item.label}
            </button>
          ))}
        </nav>

        {error ? <div className="mb-5 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</div> : null}

        {tab === "organizations" ? <OrganizationsPanel rows={organizations} canCreate={canCreateOrg} disabled={busy} onCreate={(body) => void action(() => platformPost("/api/platform/admin/organizations", body))} /> : null}
        {tab === "plans" ? <PlansPanel rows={plans} canManage={canManagePlan} disabled={busy} onCreate={(body) => void action(() => platformPost("/api/platform/admin/plans", body))} onUpdate={(id, body) => void action(() => platformPatch("/api/platform/admin/plans/" + id, body))} /> : null}
        {tab === "release" ? <ReleasePanel rows={gates} disabled={busy || !canManageRelease} onSave={(key, body) => void action(() => platformPut("/api/platform/flags/" + encodeURIComponent(key), body))} /> : null}
        {tab === "fraud" ? <FraudPanel rows={fraud} canReview={canReviewFraud} disabled={busy} onReview={(id, body) => void action(() => platformPatch("/api/platform/fraud/cases/" + id, body))} /> : null}
        {tab === "audit" ? <AuditPanel rows={audit} /> : null}
      </div>
    </main>
  );
}

function Panel({ title, description, children }: { title: string; description: string; children: React.ReactNode }) {
  return (
    <section className="rounded-xl border border-slate-200 bg-white shadow-sm">
      <div className="border-b border-slate-200 px-6 py-5">
        <h2 className="text-lg font-semibold">{title}</h2>
        <p className="mt-1 text-sm text-slate-500">{description}</p>
      </div>
      <div className="p-6">{children}</div>
    </section>
  );
}

function OrganizationsPanel({ rows, canCreate, disabled, onCreate }: {
  rows: Organization[];
  canCreate: boolean;
  disabled: boolean;
  onCreate: (body: { name: string; currency: string; data_region: string }) => void;
}) {
  const [name, setName] = useState("");
  const [currency, setCurrency] = useState("USD");
  const [region, setRegion] = useState("us-east-1");

  function submit(event: FormEvent) {
    event.preventDefault();
    onCreate({ name, currency, data_region: region });
    setName("");
  }

  return (
    <Panel title="Organizations" description="Customer organizations are visible to platform staff. Enterprise provisioning creates no customer credentials.">
      {canCreate ? (
        <form onSubmit={submit} className="mb-6 grid gap-3 rounded-lg bg-slate-50 p-4 md:grid-cols-4">
          <input className="input" required minLength={2} placeholder="Organization name" value={name} onChange={(event) => setName(event.target.value)} />
          <input className="input" required maxLength={3} value={currency} onChange={(event) => setCurrency(event.target.value.toUpperCase())} />
          <input className="input" required value={region} onChange={(event) => setRegion(event.target.value)} />
          <button disabled={disabled} className="rounded-lg bg-slate-950 px-4 py-2 text-sm font-medium text-white disabled:opacity-50">Create organization</button>
        </form>
      ) : null}
      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead className="border-b text-xs uppercase text-slate-500">
            <tr><th className="py-3 pr-4">Organization</th><th className="py-3 pr-4">State</th><th className="py-3 pr-4">Plan</th><th className="py-3 pr-4">Region</th><th className="py-3">Currency</th></tr>
          </thead>
          <tbody className="divide-y">
            {rows.map((row) => (
              <tr key={row.id}>
                <td className="py-3 pr-4"><div className="font-medium">{row.name}</div><div className="text-xs text-slate-500">#{row.id} · {row.slug}</div></td>
                <td className="py-3 pr-4"><Badge value={row.state} /></td>
                <td className="py-3 pr-4">{row.plan_name || row.subscription_status || "—"}</td>
                <td className="py-3 pr-4">{row.data_region}</td>
                <td className="py-3">{row.currency}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Panel>
  );
}

function PlansPanel({ rows, canManage, disabled, onCreate, onUpdate }: {
  rows: Plan[];
  canManage: boolean;
  disabled: boolean;
  onCreate: (body: unknown) => void;
  onUpdate: (id: number, body: unknown) => void;
}) {
  const [code, setCode] = useState("");
  const [name, setName] = useState("");
  const [price, setPrice] = useState("0");

  function submit(event: FormEvent) {
    event.preventDefault();
    onCreate({
      code,
      name,
      pricing_tiers: [{ min_properties: 1, max_properties: null, monthly_price_cents: Math.max(0, Math.round(Number(price) * 100)), currency: "USD" }],
    });
    setCode("");
    setName("");
    setPrice("0");
  }

  return (
    <Panel title="Plans" description="Billing owns plan lifecycle. Sales has read-only catalog access.">
      {canManage ? (
        <form onSubmit={submit} className="mb-6 grid gap-3 rounded-lg bg-slate-50 p-4 md:grid-cols-4">
          <input className="input" required minLength={2} placeholder="Code" value={code} onChange={(event) => setCode(event.target.value)} />
          <input className="input" required minLength={2} placeholder="Plan name" value={name} onChange={(event) => setName(event.target.value)} />
          <input className="input" type="number" min="0" step="0.01" required placeholder="Monthly price" value={price} onChange={(event) => setPrice(event.target.value)} />
          <button disabled={disabled} className="rounded-lg bg-slate-950 px-4 py-2 text-sm font-medium text-white disabled:opacity-50">Create plan</button>
        </form>
      ) : null}
      <div className="space-y-3">
        {rows.map((row) => (
          <div key={row.id} className="flex flex-wrap items-center justify-between gap-4 rounded-lg border p-4">
            <div>
              <div className="flex items-center gap-2"><p className="font-semibold">{row.name}</p><Badge value={row.is_active ? "ACTIVE" : "INACTIVE"} /></div>
              <p className="mt-1 text-sm text-slate-500">{row.code} · {row.pricing_tiers.map((tier) => money(tier.monthly_price_cents, tier.currency)).join(", ")}</p>
            </div>
            {canManage ? <button disabled={disabled} onClick={() => onUpdate(row.id, { is_active: !row.is_active })} className="rounded-lg border px-3 py-2 text-sm disabled:opacity-50">{row.is_active ? "Deactivate" : "Activate"}</button> : null}
          </div>
        ))}
      </div>
    </Panel>
  );
}

function ReleasePanel({ rows, disabled, onSave }: {
  rows: Gate[];
  disabled: boolean;
  onSave: (key: string, body: { stage: string; organization_ids: number[] }) => void;
}) {
  return <Panel title="Release Gates" description="Release stage is independent from plan entitlement, organization configuration, role permission, and user preference."><div className="space-y-3">{rows.map((row) => <ReleaseGateRow key={row.key} row={row} disabled={disabled} onSave={onSave} />)}</div></Panel>;
}

function ReleaseGateRow({ row, disabled, onSave }: {
  row: Gate;
  disabled: boolean;
  onSave: (key: string, body: { stage: string; organization_ids: number[] }) => void;
}) {
  const [stage, setStage] = useState(row.stage);
  const [orgs, setOrgs] = useState(row.organization_ids.join(","));

  return (
    <div className="grid items-center gap-3 rounded-lg border p-4 md:grid-cols-[1fr_180px_1fr_auto]">
      <div className="font-mono text-sm">{row.key}</div>
      <select className="input" value={stage} onChange={(event) => setStage(event.target.value as Gate["stage"])}>
        <option value="HIDDEN">Hidden</option><option value="INTERNAL">Internal</option><option value="BETA">Beta</option><option value="ALL_ORGS">All organizations</option>
      </select>
      <input className="input" value={orgs} disabled={stage === "HIDDEN" || stage === "ALL_ORGS"} onChange={(event) => setOrgs(event.target.value)} placeholder="Organization IDs: 1,2,3" />
      <button disabled={disabled} onClick={() => onSave(row.key, { stage, organization_ids: stage === "HIDDEN" || stage === "ALL_ORGS" ? [] : orgs.split(",").map((value) => Number(value.trim())).filter((value) => Number.isInteger(value) && value > 0) })} className="rounded-lg bg-slate-950 px-3 py-2 text-sm text-white disabled:opacity-50">Save</button>
    </div>
  );
}

function FraudPanel({ rows, canReview, disabled, onReview }: {
  rows: FraudCase[];
  canReview: boolean;
  disabled: boolean;
  onReview: (id: number, body: { status: string; resolution_notes: string | null }) => void;
}) {
  return (
    <Panel title="Fraud Review" description="Review queue stores risk signals and decisions without raw card data.">
      <div className="space-y-3">
        {rows.map((row) => (
          <div key={row.id} className="rounded-lg border p-4">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <div className="flex items-center gap-2"><p className="font-semibold">Case #{row.id}</p><Badge value={row.risk_level} /><Badge value={row.status} /></div>
                <p className="mt-2 text-sm text-slate-600">{row.reason}</p>
                <p className="mt-1 text-xs text-slate-500">Org {row.organization_id || "—"} · Risk score {row.risk_score ?? "—"}</p>
              </div>
              {canReview ? <div className="flex flex-wrap gap-2">{["IN_REVIEW", "APPROVED", "BLOCKED", "DISMISSED"].map((status) => <button key={status} disabled={disabled} onClick={() => onReview(row.id, { status, resolution_notes: "Reviewed in platform admin console" })} className="rounded-lg border px-3 py-2 text-xs font-medium disabled:opacity-50">{status.replaceAll("_", " ")}</button>)}</div> : null}
            </div>
          </div>
        ))}
      </div>
    </Panel>
  );
}

function AuditPanel({ rows }: { rows: AuditRow[] }) {
  return (
    <Panel title="Staff Audit" description="Immutable audit view limited to platform-actor activity.">
      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead className="border-b text-xs uppercase text-slate-500"><tr><th className="py-3 pr-4">Time</th><th className="py-3 pr-4">Actor</th><th className="py-3 pr-4">Entity</th><th className="py-3 pr-4">Action</th><th className="py-3">Organization</th></tr></thead>
          <tbody className="divide-y">
            {rows.map((row) => <tr key={row.id}><td className="py-3 pr-4 whitespace-nowrap">{new Date(row.created_at).toLocaleString()}</td><td className="py-3 pr-4">{row.platform_user_email || "—"}</td><td className="py-3 pr-4">{row.entity_type} #{row.entity_id}</td><td className="py-3 pr-4">{row.action}</td><td className="py-3">{row.organization_id || "—"}</td></tr>)}
          </tbody>
        </table>
      </div>
    </Panel>
  );
}
