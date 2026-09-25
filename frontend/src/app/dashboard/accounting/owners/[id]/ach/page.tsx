"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";

import { useFlag } from "@/hooks/useFlag";
import { apiGet } from "@/lib/api";
import {
  listBankAccounts,
  type BankAccount,
} from "@/lib/bankAccounts";
import {
  generateOwnerACHTestFile,
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
  const testFileEnabled = useFlag("release.accounting.ach_test_file");
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

  const [banks, setBanks] = useState<BankAccount[]>([]);
  const [testBankId, setTestBankId] = useState("");
  const [testDate, setTestDate] = useState("");
  const [testCompanyId, setTestCompanyId] = useState("");
  const [generatingTest, setGeneratingTest] = useState(false);

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

  useEffect(() => {
    if (!testFileEnabled) return;
    listBankAccounts()
      .then((result) => {
        const configured = result.items.filter((bank) => Boolean(bank.ach_format));
        setBanks(configured);
        if (configured.length === 1) setTestBankId(String(configured[0].id));
      })
      .catch((err) => {
        setError(err instanceof Error ? err.message : "Could not load ACH source banks.");
      });
  }, [testFileEnabled]);

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

  async function handleGenerateTestFile() {
    setError("");
    setSuccess("");
    if (!setup?.configured || !setup.is_enabled) {
      setError("Configure and enable the owner ACH destination first.");
      return;
    }
    if (!testBankId) {
      setError("Choose the source bank account.");
      return;
    }
    if (!testDate) {
      setError("Choose the effective date.");
      return;
    }

    const bank = banks.find((item) => item.id === Number(testBankId));
    if (bank?.ach_format === "NACHA" && !testCompanyId.trim()) {
      setError("Company ID is required for a NACHA test file.");
      return;
    }

    setGeneratingTest(true);
    try {
      const result = await generateOwnerACHTestFile(
        ownerId,
        Number(testBankId),
        {
          effective_date: testDate,
          company_id: testCompanyId.trim() || null,
          entry_description: "PRENOTE",
        },
      );
      const blob = new Blob([result.content], { type: result.content_type });
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = result.filename;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(url);
      setSuccess("$0 ACH test file generated. No payment or accounting entry was created.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not generate ACH test file.");
    } finally {
      setGeneratingTest(false);
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

      {testFileEnabled && (
        <section className="mt-6 rounded-xl border border-slate-200 bg-white p-6">
          <h2 className="font-semibold text-slate-900">$0 ACH Test File</h2>
          <p className="mt-1 text-sm text-slate-500">
            Generate a zero-dollar CSV test row or NACHA prenote for this owner. This verifies file setup only and does not post a payment.
          </p>

          <div className="mt-5 grid gap-4 md:grid-cols-2">
            <label className="text-sm text-slate-700">
              Source bank account
              <select
                value={testBankId}
                onChange={(event) => setTestBankId(event.target.value)}
                className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2"
              >
                <option value="">Choose a bank</option>
                {banks.map((bank) => (
                  <option key={bank.id} value={bank.id}>
                    {bank.name} · {bank.ach_format}
                  </option>
                ))}
              </select>
            </label>

            <label className="text-sm text-slate-700">
              Effective date
              <input
                type="date"
                value={testDate}
                onChange={(event) => setTestDate(event.target.value)}
                className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2"
              />
            </label>

            <label className="text-sm text-slate-700 md:col-span-2">
              Company ID
              <input
                value={testCompanyId}
                maxLength={10}
                onChange={(event) => setTestCompanyId(event.target.value)}
                placeholder="Required for NACHA"
                className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2"
              />
            </label>
          </div>

          {banks.length === 0 && (
            <p className="mt-4 text-sm text-amber-700">
              No active bank account has an ACH format configured yet.
            </p>
          )}

          <button
            type="button"
            disabled={generatingTest || banks.length === 0}
            onClick={() => void handleGenerateTestFile()}
            className="mt-5 rounded-lg bg-slate-900 px-5 py-2.5 text-sm font-medium text-white disabled:opacity-50"
          >
            {generatingTest ? "Generating…" : "Generate $0 Test File"}
          </button>
        </section>
      )}
    </div>
  );
}
