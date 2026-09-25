"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";

import { apiGet } from "@/lib/api";
import {
  getOwnerACH,
  saveOwnerACH,
  type OwnerACH,
} from "@/lib/ownerAch";

type OwnerUser = {
  id: number;
  first_name: string;
  last_name: string;
  email: string;
  role: string;
};

export default function OwnerACHPage() {
  const ownerId = Number(useParams().id);
  const [owner, setOwner] = useState<OwnerUser | null>(null);
  const [setup, setSetup] = useState<OwnerACH | null>(null);
  const [holderName, setHolderName] = useState("");
  const [bankName, setBankName] = useState("");
  const [routingNumber, setRoutingNumber] = useState("");
  const [accountNumber, setAccountNumber] = useState("");
  const [accountType, setAccountType] = useState<"CHECKING" | "SAVINGS">("CHECKING");
  const [enabled, setEnabled] = useState(true);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  useEffect(() => {
    (async () => {
      try {
        const [ownerData, achData] = await Promise.all([
          apiGet(`/users/${ownerId}`) as Promise<OwnerUser>,
          getOwnerACH(ownerId),
        ]);
        setOwner(ownerData);
        setSetup(achData);
        setHolderName(
          achData.account_holder_name ||
            `${ownerData.first_name} ${ownerData.last_name}`.trim(),
        );
        setBankName(achData.bank_name || "");
        setAccountType(achData.account_type || "CHECKING");
        setEnabled(achData.configured ? achData.is_enabled : true);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Could not load owner ACH setup.");
      } finally {
        setLoading(false);
      }
    })();
  }, [ownerId]);

  async function handleSave(event: React.FormEvent) {
    event.preventDefault();
    setError("");
    setSuccess("");

    if (!holderName.trim()) {
      setError("Account holder name is required.");
      return;
    }
    if (routingNumber.trim().length !== 9) {
      setError("Enter the full 9-digit routing number.");
      return;
    }
    if (!accountNumber.trim()) {
      setError("Enter the full bank account number.");
      return;
    }

    setSaving(true);
    try {
      const saved = await saveOwnerACH(ownerId, {
        account_holder_name: holderName.trim(),
        bank_name: bankName.trim() || null,
        routing_number: routingNumber.trim(),
        account_number: accountNumber.trim(),
        account_type: accountType,
        is_enabled: enabled,
      });
      setSetup(saved);
      setRoutingNumber("");
      setAccountNumber("");
      setSuccess("Owner ACH setup saved.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save owner ACH setup.");
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return <div className="p-6 text-sm text-slate-500">Loading owner ACH setup…</div>;
  }

  return (
    <div className="max-w-3xl p-6">
      <Link
        href={`/dashboard/team/${ownerId}`}
        className="text-sm text-slate-500 hover:text-slate-900"
      >
        ← Back to owner
      </Link>

      <div className="mt-4">
        <h1 className="text-2xl font-bold text-slate-900">Owner ACH Setup</h1>
        <p className="mt-1 text-sm text-slate-500">
          {owner
            ? `${owner.first_name} ${owner.last_name} · ${owner.email}`
            : "Owner payout bank details"}
        </p>
      </div>

      {setup?.configured && (
        <div className="mt-5 rounded-lg border border-slate-200 bg-slate-50 p-4 text-sm text-slate-700">
          Current destination: {setup.bank_name || "Bank"} · routing ending{" "}
          <span className="font-mono">{setup.routing_last4}</span> · account ending{" "}
          <span className="font-mono">{setup.account_last4}</span> ·{" "}
          {setup.account_type?.toLowerCase()}.
          <div className="mt-1 text-xs text-slate-500">
            Full bank numbers are never returned to the browser. Enter them again to change this setup.
          </div>
        </div>
      )}

      {error && (
        <div className="mt-5 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}
      {success && (
        <div className="mt-5 rounded-lg border border-green-200 bg-green-50 px-4 py-3 text-sm text-green-700">
          {success}
        </div>
      )}

      <form
        onSubmit={handleSave}
        className="mt-6 space-y-5 rounded-xl border border-slate-200 bg-white p-6"
      >
        <div>
          <label className="block text-sm font-medium text-slate-700">
            Account holder name
          </label>
          <input
            value={holderName}
            onChange={(event) => setHolderName(event.target.value)}
            maxLength={120}
            className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-slate-700">Bank name</label>
          <input
            value={bankName}
            onChange={(event) => setBankName(event.target.value)}
            maxLength={200}
            className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2"
          />
        </div>

        <div className="grid gap-4 md:grid-cols-2">
          <div>
            <label className="block text-sm font-medium text-slate-700">
              Routing number
            </label>
            <input
              inputMode="numeric"
              autoComplete="off"
              value={routingNumber}
              onChange={(event) =>
                setRoutingNumber(event.target.value.replace(/\D/g, "").slice(0, 9))
              }
              placeholder={setup?.routing_last4 ? `•••••${setup.routing_last4}` : "9 digits"}
              className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 font-mono"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700">
              Account number
            </label>
            <input
              autoComplete="off"
              value={accountNumber}
              onChange={(event) => setAccountNumber(event.target.value)}
              placeholder={setup?.account_last4 ? `••••${setup.account_last4}` : "Account number"}
              className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 font-mono"
            />
          </div>
        </div>

        <div>
          <label className="block text-sm font-medium text-slate-700">Account type</label>
          <select
            value={accountType}
            onChange={(event) =>
              setAccountType(event.target.value as "CHECKING" | "SAVINGS")
            }
            className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2"
          >
            <option value="CHECKING">Checking</option>
            <option value="SAVINGS">Savings</option>
          </select>
        </div>

        <label className="flex items-center gap-2 text-sm text-slate-700">
          <input
            type="checkbox"
            checked={enabled}
            onChange={(event) => setEnabled(event.target.checked)}
          />
          Enable this destination for owner ACH payments
        </label>

        <div className="flex items-center gap-3">
          <button
            type="submit"
            disabled={saving}
            className="rounded-lg bg-slate-900 px-5 py-2.5 text-sm font-medium text-white disabled:opacity-50"
          >
            {saving ? "Saving…" : setup?.configured ? "Replace ACH Setup" : "Save ACH Setup"}
          </button>
          <span className="text-xs text-slate-500">
            Saving bank details does not create a payment or GL entry.
          </span>
        </div>
      </form>
    </div>
  );
}
