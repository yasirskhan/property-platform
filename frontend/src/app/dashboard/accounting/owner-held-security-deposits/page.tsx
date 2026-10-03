"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { apiGet, apiPatch } from "@/lib/api";
import { useDisplay } from "@/contexts/DisplayContext";
import {
  addOwnerHeldDepositKeyAccount,
  getOwnerHeldDepositSetup,
  OwnerHeldDepositSetup,
  removeOwnerHeldDepositKeyAccount,
} from "@/lib/ownerHeldDeposits";

type Lease = {
  id: number;
  tenant_id: number;
  start_date: string;
  end_date: string;
  security_deposit: string;
  security_deposit_gl_account_id: number | null;
  status: string;
};

type Person = {
  id: number;
  first_name?: string;
  last_name?: string;
  email: string;
};

export default function OwnerHeldSecurityDepositsPage() {
  const { prefs } = useDisplay();
  const [setup, setSetup] = useState<OwnerHeldDepositSetup | null>(null);
  const [leases, setLeases] = useState<Lease[]>([]);
  const [people, setPeople] = useState<Person[]>([]);
  const [newKeyAccountId, setNewKeyAccountId] = useState<number | "">("");
  const [leaseId, setLeaseId] = useState<number | "">("");
  const [depositAccountId, setDepositAccountId] = useState<number | "">("");
  const [amount, setAmount] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  async function load() {
    setLoading(true);
    setError("");
    try {
      const [setupData, leaseData, usersData] = await Promise.all([
        getOwnerHeldDepositSetup(),
        apiGet("/leases"),
        apiGet("/users"),
      ]);
      setSetup(setupData);
      setLeases(Array.isArray(leaseData) ? (leaseData as Lease[]) : []);
      setPeople(Array.isArray(usersData) ? (usersData as Person[]) : []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load owner-held deposits.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, []);

  const peopleById = useMemo(
    () => new Map(people.map((person) => [person.id, person])),
    [people]
  );

  const availableKeyAccounts = useMemo(() => {
    if (!setup) return [];
    const configured = new Set(setup.key_accounts.map((item) => item.gl_account_id));
    return setup.eligible_accounts.filter((item) => !configured.has(item.gl_account_id));
  }, [setup]);

  function chooseLease(value: number | "") {
    setLeaseId(value);
    const lease = leases.find((item) => item.id === value);
    setAmount(lease ? String(lease.security_deposit ?? "") : "");
    setDepositAccountId(lease?.security_deposit_gl_account_id ?? "");
    setMessage("");
  }

  async function addKeyAccount() {
    if (!newKeyAccountId) return;
    setBusy(true);
    setError("");
    setMessage("");
    try {
      await addOwnerHeldDepositKeyAccount(Number(newKeyAccountId));
      setNewKeyAccountId("");
      await load();
      setMessage("Deposit Key Account added.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not add Key Account.");
    } finally {
      setBusy(false);
    }
  }

  async function removeKeyAccount(id: number) {
    setBusy(true);
    setError("");
    setMessage("");
    try {
      await removeOwnerHeldDepositKeyAccount(id);
      await load();
      setMessage("Deposit Key Account removed.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not remove Key Account.");
    } finally {
      setBusy(false);
    }
  }

  async function saveMoveIn() {
    if (!leaseId || !depositAccountId || !amount || Number(amount) < 0) {
      setError("Choose a lease, deposit account, and valid amount.");
      return;
    }
    setBusy(true);
    setError("");
    setMessage("");
    try {
      await apiPatch(`/leases/${leaseId}`, {
        security_deposit: Number(amount),
        security_deposit_gl_account_id: Number(depositAccountId),
      });
      await load();
      setMessage("Move-in security deposit settings saved.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save move-in deposit.");
    } finally {
      setBusy(false);
    }
  }

  if (loading && !setup) {
    return <div className="p-6 text-slate-500">Loading…</div>;
  }

  return (
    <div
      className="max-w-5xl mx-auto p-6"
      data-layout-mode={(prefs?.layout_mode ?? "TABS").toLowerCase()}
      data-density={(prefs?.density ?? "COMFORTABLE").toLowerCase()}
    >
      <div className="flex items-start justify-between gap-4 mb-6">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Owner Held Security Deposits</h1>
          <p className="text-sm text-slate-500 mt-1">
            Configure approved deposit liability accounts and select one during move-in.
          </p>
        </div>
        <Link href="/dashboard/accounting/gl-accounts" className="text-sm text-blue-600 hover:underline">
          Back to GL Accounts
        </Link>
      </div>

      {error && <div className="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>}
      {message && <div className="mb-4 rounded-lg border border-green-200 bg-green-50 px-4 py-3 text-sm text-green-700">{message}</div>}

      <section className="bg-white border border-slate-200 rounded-xl p-5 mb-6">
        <h2 className="text-lg font-semibold text-slate-900">Deposit Key Accounts</h2>
        <p className="text-sm text-slate-500 mt-1 mb-4">
          Eligible accounts must be LIABILITY accounts offset to Operating Cash GL {setup?.operating_cash_gl_number ?? "—"},
          excluded from management fees and cash flow.
        </p>

        <div className="space-y-2 mb-4">
          {(setup?.key_accounts ?? []).map((item) => (
            <div key={item.id} className="flex items-center justify-between rounded-lg border border-slate-200 px-3 py-2 text-sm">
              <span><span className="font-mono">{item.gl_number}</span> · {item.name}</span>
              <button type="button" disabled={busy} onClick={() => void removeKeyAccount(item.id)} className="text-red-600 hover:text-red-800 disabled:opacity-50">
                Remove
              </button>
            </div>
          ))}
          {setup?.key_accounts.length === 0 && (
            <div className="text-sm text-slate-500">No deposit Key Accounts configured yet.</div>
          )}
        </div>

        <div className="flex flex-col sm:flex-row gap-3">
          <select
            value={newKeyAccountId}
            onChange={(event) => setNewKeyAccountId(event.target.value ? Number(event.target.value) : "")}
            className="flex-1 border border-slate-300 rounded-lg px-3 py-2 text-sm bg-white"
          >
            <option value="">Select an eligible liability account…</option>
            {availableKeyAccounts.map((item) => (
              <option key={item.gl_account_id} value={item.gl_account_id}>
                {item.gl_number} · {item.name}
              </option>
            ))}
          </select>
          <button
            type="button"
            onClick={() => void addKeyAccount()}
            disabled={busy || !newKeyAccountId}
            className="px-4 py-2 rounded-lg bg-slate-900 text-white text-sm disabled:opacity-50"
          >
            Add Key Account
          </button>
        </div>
        {availableKeyAccounts.length === 0 && setup?.key_accounts.length === 0 && (
          <p className="text-xs text-slate-500 mt-3">
            Create or edit a GL liability account first. Its offset account must be Operating Cash, with Management Fees and Cash Flow both off.
          </p>
        )}
      </section>

      <section className="bg-white border border-slate-200 rounded-xl p-5">
        <h2 className="text-lg font-semibold text-slate-900">Move In</h2>
        <p className="text-sm text-slate-500 mt-1 mb-4">
          Store the owner-held security deposit amount and approved deposit account on the lease.
        </p>

        <div className="grid md:grid-cols-3 gap-4">
          <div>
            <label className="block text-xs font-medium text-slate-600 mb-1">Lease</label>
            <select
              value={leaseId}
              onChange={(event) => chooseLease(event.target.value ? Number(event.target.value) : "")}
              className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm bg-white"
            >
              <option value="">Select a lease…</option>
              {leases.map((lease) => {
                const tenant = peopleById.get(lease.tenant_id);
                const tenantLabel = tenant
                  ? `${tenant.first_name ?? ""} ${tenant.last_name ?? ""}`.trim() || tenant.email
                  : `Tenant #${lease.tenant_id}`;
                return (
                  <option key={lease.id} value={lease.id}>
                    Lease #{lease.id} · {tenantLabel} · {lease.start_date}
                  </option>
                );
              })}
            </select>
          </div>

          <div>
            <label className="block text-xs font-medium text-slate-600 mb-1">Security deposit amount</label>
            <input
              type="number"
              min="0"
              step="0.01"
              value={amount}
              onChange={(event) => setAmount(event.target.value)}
              className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm"
              placeholder="0.00"
            />
          </div>

          <div>
            <label className="block text-xs font-medium text-slate-600 mb-1">Deposit Key Account</label>
            <select
              value={depositAccountId}
              onChange={(event) => setDepositAccountId(event.target.value ? Number(event.target.value) : "")}
              className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm bg-white"
            >
              <option value="">Select account…</option>
              {(setup?.key_accounts ?? []).map((item) => (
                <option key={item.id} value={item.gl_account_id}>
                  {item.gl_number} · {item.name}
                </option>
              ))}
            </select>
          </div>
        </div>

        <div className="flex justify-end mt-5">
          <button
            type="button"
            onClick={() => void saveMoveIn()}
            disabled={busy || !leaseId || !depositAccountId}
            className="px-4 py-2 rounded-lg bg-blue-600 text-white text-sm font-medium hover:bg-blue-700 disabled:opacity-50"
          >
            {busy ? "Saving…" : "Save move-in deposit"}
          </button>
        </div>
      </section>
    </div>
  );
}
