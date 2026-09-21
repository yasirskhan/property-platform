// ============================================================
// New Charge page
// ------------------------------------------------------------
// Enter a one-off charge against a tenant.
//
// Fields: tenant, date, GL account (INCOME), amount, description.
// Unit and property are auto-filled from the tenant's lease.
//
// See PROJECT_MASTER.md Section 19.
// ============================================================

"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { apiGet, apiPost } from "@/lib/api";

interface User {
  id: number;
  first_name: string;
  last_name: string;
  email: string;
  role: string;
}

interface GLAccount {
  id: number;
  gl_number: string;
  name: string;
  account_type: string;
}

export default function NewChargePage() {
  const router = useRouter();

  const [tenants, setTenants] = useState<User[]>([]);
  const [accounts, setAccounts] = useState<GLAccount[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [tenantId, setTenantId] = useState<number | "">("");
  const [chargeDate, setChargeDate] = useState<string>(
    new Date().toISOString().slice(0, 10)
  );
  const [glAccountId, setGlAccountId] = useState<number | "">("");
  const [amount, setAmount] = useState("");
  const [description, setDescription] = useState("");

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const [users, gls] = await Promise.all([
          apiGet("/users?role=TENANT"),
          apiGet("/api/accounting/gl-accounts"),
        ]);

        if (cancelled) return;

        setTenants(users as User[]);

        // gl-accounts returns { groups: [{ account_type, accounts: [...] }], total }
        const groups = (gls as {
          groups: { account_type: string; accounts: GLAccount[] }[];
        }).groups;
        const incomeAccounts = groups
          .filter((g) => (g.account_type || "").toUpperCase() === "INCOME")
          .flatMap((g) => g.accounts);
        setAccounts(incomeAccounts);
      } catch (e: unknown) {
        if (!cancelled) {
          setError(
            e instanceof Error ? e.message : "Could not load form data."
          );
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, []);

  async function submit() {
    if (!tenantId || !glAccountId || !amount || !description) {
      setError("Fill in all fields.");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await apiPost("/api/accounting/charges", {
        tenant_user_id: tenantId,
        charge_date: chargeDate,
        gl_account_id: glAccountId,
        amount: parseFloat(amount),
        description,
      });
      router.push("/dashboard/accounting/charges");
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Could not save charge.");
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return <div className="max-w-2xl mx-auto p-6 text-slate-500">Loading...</div>;
  }

  return (
    <div className="max-w-2xl mx-auto p-6">
      <h1 className="text-xl font-semibold text-slate-900 mb-1">New Charge</h1>
      <p className="text-sm text-slate-500 mb-6">
        One-off amount owed by a tenant.
      </p>

      {error && (
        <div className="text-sm text-red-600 mb-4 bg-red-50 border border-red-200 rounded-md px-3 py-2">
          {error}
        </div>
      )}

      <div className="bg-white rounded-lg border border-slate-200 p-5 space-y-4">
        <div>
          <label className="block text-xs text-slate-600 mb-1">
            Tenant <span className="text-red-500">*</span>
          </label>
          <select
            value={tenantId}
            onChange={(e) =>
              setTenantId(e.target.value ? Number(e.target.value) : "")
            }
            className="w-full border border-slate-300 rounded-md px-3 py-1.5 text-sm bg-white"
          >
            <option value="">Select a tenant...</option>
            {tenants.map((t) => (
              <option key={t.id} value={t.id}>
                {t.first_name} {t.last_name} &lt;{t.email}&gt;
              </option>
            ))}
          </select>
          <div className="text-xs text-slate-500 mt-1">
            Unit and property auto-fill from the tenant&apos;s most recent lease.
          </div>
        </div>

        <div>
          <label className="block text-xs text-slate-600 mb-1">
            Charge date <span className="text-red-500">*</span>
          </label>
          <input
            type="date"
            value={chargeDate}
            onChange={(e) => setChargeDate(e.target.value)}
            className="w-full border border-slate-300 rounded-md px-3 py-1.5 text-sm"
          />
        </div>

        <div>
          <label className="block text-xs text-slate-600 mb-1">
            GL account (INCOME) <span className="text-red-500">*</span>
          </label>
          <select
            value={glAccountId}
            onChange={(e) =>
              setGlAccountId(e.target.value ? Number(e.target.value) : "")
            }
            className="w-full border border-slate-300 rounded-md px-3 py-1.5 text-sm bg-white"
          >
            <option value="">Select an income account...</option>
            {accounts.map((a) => (
              <option key={a.id} value={a.id}>
                {a.gl_number} &mdash; {a.name}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label className="block text-xs text-slate-600 mb-1">
            Amount <span className="text-red-500">*</span>
          </label>
          <input
            type="number"
            step="0.01"
            min="0"
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            placeholder="0.00"
            className="w-full border border-slate-300 rounded-md px-3 py-1.5 text-sm"
          />
        </div>

        <div>
          <label className="block text-xs text-slate-600 mb-1">
            Description <span className="text-red-500">*</span>
          </label>
          <input
            type="text"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            maxLength={500}
            placeholder="Late fee for October rent"
            className="w-full border border-slate-300 rounded-md px-3 py-1.5 text-sm"
          />
        </div>
      </div>

      <div className="flex items-center justify-end gap-3 mt-5">
        <button
          type="button"
          onClick={() => router.push("/dashboard/accounting/charges")}
          className="px-4 py-2 rounded-md border border-slate-300 text-slate-700 text-sm font-medium hover:bg-slate-50"
        >
          Cancel
        </button>
        <button
          type="button"
          onClick={submit}
          disabled={saving}
          className="px-4 py-2 rounded-md bg-blue-600 text-white text-sm font-medium hover:bg-blue-700 disabled:opacity-50"
        >
          {saving ? "Saving..." : "Save charge"}
        </button>
      </div>
    </div>
  );
}