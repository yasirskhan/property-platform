// ============================================================
// New Receipt page
// ------------------------------------------------------------
// Route: /dashboard/accounting/receipts/new
//
// Three tabs:
//   TENANT  - pick a tenant -> ONE blank row appears with GL
//             Account defaulted to 4100 Rent. Manager types
//             the amount received. "+ Add line" sits at the
//             right end of the row just under the last line.
//             Total row sits below that.
//   OWNER   - owner sends money in.
//   OTHER   - anything else, with "exclude from mgmt fee".
//
// On submit, POSTs to /api/accounting/receipts and redirects
// to the receipts list.
//
// Uses formatMoney() from lib/money.ts for every amount so the
// org's currency setting is respected (Section 59).
// ============================================================

"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import {
  createReceipt,
  listTenantOpenCharges,
  RECEIPT_TYPE_ORDER,
  RECEIPT_TYPE_LABELS,
  ReceiptCreateIn,
} from "@/lib/receipts";
import { apiGet } from "@/lib/api";
import { formatMoney } from "@/lib/money";
import { listGLAccounts, GLAccount } from "@/lib/glAccounts";

type Tab = "TENANT" | "OWNER" | "OTHER";

type Property = { id: number; name: string };

type Person = {
  id: number;
  full_name?: string;
  first_name?: string;
  last_name?: string;
  email?: string;
  role?: string;
};

// One row in the tenant charges table
type ChargeRow = {
  key: string;
  gl_account_id: number;
  gl_account_number: string;
  gl_account_name: string;
  description: string;
  amount_to_pay: number;
  is_prepayment: boolean;
  line_date: string;
};

let adhocCounter = 0;

export default function NewReceiptPage() {
  const router = useRouter();

  const [tab, setTab] = useState<Tab>("TENANT");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  // Shared dropdown data
  const [accounts, setAccounts] = useState<GLAccount[]>([]);
  const [properties, setProperties] = useState<Property[]>([]);
  const [tenants, setTenants] = useState<Person[]>([]);
  const [owners, setOwners] = useState<Person[]>([]);

  // Common form state
  const [receiptDate, setReceiptDate] = useState<string>(
    new Date().toISOString().slice(0, 10)
  );
  const [cashAccountId, setCashAccountId] = useState<number | "">("");
  const [propertyId, setPropertyId] = useState<number | "">("");
  const [reference, setReference] = useState("");
  const [remarks, setRemarks] = useState("");

  // TENANT state
  const [tenantUserId, setTenantUserId] = useState<number | "">("");
  const [tenantLines, setTenantLines] = useState<ChargeRow[]>([]);
  const [rentAccount, setRentAccount] = useState<GLAccount | null>(null);

  // OWNER state
  const [ownerUserId, setOwnerUserId] = useState<number | "">("");
  const [ownerPayerName, setOwnerPayerName] = useState("");
  const [ownerAmount, setOwnerAmount] = useState("");
  const [ownerIncomeAccountId, setOwnerIncomeAccountId] = useState<number | "">("");

  // OTHER state
  const [otherAmount, setOtherAmount] = useState("");
  const [otherReceivedFrom, setOtherReceivedFrom] = useState("");
  const [otherIncomeAccountId, setOtherIncomeAccountId] = useState<number | "">("");
  const [otherExclude, setOtherExclude] = useState(false);

  // ------------------------------------------------------------
  // Load reference data
  // ------------------------------------------------------------
  useEffect(() => {
    (async () => {
      try {
        const accts = await listGLAccounts(false);
        const flat: GLAccount[] = [];
        for (const g of accts.groups) flat.push(...g.accounts);
        setAccounts(flat);

        const cash = flat.find((a) => a.gl_number === "1150");
        if (cash) setCashAccountId(cash.id);

        const ownerFunds = flat.find((a) => a.gl_number === "2401");
        if (ownerFunds) setOwnerIncomeAccountId(ownerFunds.id);

        const rent = flat.find((a) => a.gl_number === "4100");
        if (rent) {
          setRentAccount(rent);
        } else {
          const firstIncome = flat.find(
            (a) => a.is_active && a.account_type === "INCOME"
          );
          if (firstIncome) setRentAccount(firstIncome);
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load accounts");
      }

      try {
        const propsRaw = (await apiGet("/properties")) as unknown;
        const props: Property[] = Array.isArray(propsRaw)
          ? (propsRaw as Property[])
          : (((propsRaw as { items?: Property[] })?.items ?? []) as Property[]);
        setProperties(props);
      } catch {
        setProperties([]);
      }

      try {
        const usersRaw = (await apiGet("/users")) as unknown;
        const list: Person[] = Array.isArray(usersRaw)
          ? (usersRaw as Person[])
          : (((usersRaw as { items?: Person[] })?.items ?? []) as Person[]);
        setTenants(list.filter((p) => (p.role || "").toUpperCase() === "TENANT"));
        setOwners(list.filter((p) => (p.role || "").toUpperCase() === "OWNER"));
      } catch {
        setTenants([]);
        setOwners([]);
      }
    })();
  }, []);

  // ------------------------------------------------------------
  // When tenant changes -> create ONE blank row prefilled with
  // the tenant's rent GL account.
  // ------------------------------------------------------------
  useEffect(() => {
    if (!tenantUserId) {
      setTenantLines([]);
      return;
    }
    let cancelled = false;
    (async () => {
      let rentId = rentAccount?.id ?? 0;
      let rentNumber = rentAccount?.gl_number ?? "";
      let rentName = rentAccount?.name ?? "";

      try {
        const data = await listTenantOpenCharges(Number(tenantUserId));
        if (cancelled) return;
        if (data.rent_gl_account_id) {
          rentId = data.rent_gl_account_id;
          rentNumber = data.rent_gl_account_number ?? rentNumber;
          rentName = data.rent_gl_account_name ?? rentName;
        }
      } catch {
        // Ignore — we still have the default rent account.
      }

      if (cancelled) return;
      setTenantLines([
        {
          key: `row-${Date.now()}`,
          gl_account_id: rentId,
          gl_account_number: rentNumber,
          gl_account_name: rentName,
          description: "",
          amount_to_pay: 0,
          is_prepayment: false,
          line_date: receiptDate,
        },
      ]);
    })();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tenantUserId]);

  // ------------------------------------------------------------
  // Derived
  // ------------------------------------------------------------
  const cashAccounts = useMemo(
    () =>
      accounts.filter(
        (a) =>
          a.is_active &&
          (a.account_type === "ASSET" ||
            a.gl_number === "1150" ||
            a.gl_number === "1160")
      ),
    [accounts]
  );

  const incomeAccounts = useMemo(
    () =>
      accounts.filter(
        (a) =>
          a.is_active &&
          (a.account_type === "INCOME" ||
            a.account_type === "LIABILITY" ||
            a.account_type === "EQUITY")
      ),
    [accounts]
  );

  const tenantTotal = tenantLines.reduce(
    (sum, r) => sum + Number(r.amount_to_pay || 0),
    0
  );

  function personLabel(p: Person): string {
    if (p.full_name) return p.full_name;
    const nm = `${p.first_name || ""} ${p.last_name || ""}`.trim();
    return nm || p.email || `#${p.id}`;
  }

  function accountLabel(a: GLAccount): string {
    return `${a.gl_number} ${a.name}`;
  }

  // ------------------------------------------------------------
  // Row actions
  // ------------------------------------------------------------
  function updateRow(key: string, patch: Partial<ChargeRow>) {
    setTenantLines((prev) =>
      prev.map((r) => (r.key === key ? { ...r, ...patch } : r))
    );
  }

  function removeRow(key: string) {
    setTenantLines((prev) => prev.filter((r) => r.key !== key));
  }

  function addRow() {
    adhocCounter += 1;
    const defaultId = rentAccount?.id ?? 0;
    const defaultNum = rentAccount?.gl_number ?? "";
    const defaultName = rentAccount?.name ?? "";
    setTenantLines((prev) => [
      ...prev,
      {
        key: `row-${Date.now()}-${adhocCounter}`,
        gl_account_id: defaultId,
        gl_account_number: defaultNum,
        gl_account_name: defaultName,
        description: "",
        amount_to_pay: 0,
        is_prepayment: false,
        line_date: receiptDate,
      },
    ]);
  }

  function resetTenantRows() {
    setTenantUserId("");
    setTenantLines([]);
  }

  // ------------------------------------------------------------
  // Submit
  // ------------------------------------------------------------
  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");

    if (!cashAccountId) {
      setError("Pick a cash account.");
      return;
    }

    let payload: ReceiptCreateIn;

    if (tab === "TENANT") {
      const valid = tenantLines.filter((r) => Number(r.amount_to_pay) > 0);
      if (valid.length === 0) {
        setError("Add at least one line with an amount greater than zero.");
        return;
      }
      payload = {
        type: "TENANT",
        receipt_date: receiptDate,
        amount: tenantTotal,
        cash_gl_account_id: Number(cashAccountId),
        tenant_user_id: tenantUserId ? Number(tenantUserId) : null,
        property_id: propertyId ? Number(propertyId) : null,
        reference_number: reference || null,
        remarks: remarks || null,
        lines: valid.map((r) => ({
          gl_account_id: r.gl_account_id,
          amount_to_pay: r.amount_to_pay,
          description: r.description || null,
          line_date: r.line_date,
          is_prepayment: r.is_prepayment,
        })),
      };
    } else if (tab === "OWNER") {
      const amt = Number(ownerAmount);
      if (!amt || amt <= 0) {
        setError("Enter an amount greater than zero.");
        return;
      }
      if (!ownerIncomeAccountId) {
        setError("Pick an income account.");
        return;
      }
      payload = {
        type: "OWNER",
        receipt_date: receiptDate,
        amount: amt,
        cash_gl_account_id: Number(cashAccountId),
        owner_user_id: ownerUserId ? Number(ownerUserId) : null,
        income_gl_account_id: Number(ownerIncomeAccountId),
        payer_name: ownerPayerName || null,
        property_id: propertyId ? Number(propertyId) : null,
        reference_number: reference || null,
        remarks: remarks || null,
      };
    } else {
      const amt = Number(otherAmount);
      if (!amt || amt <= 0) {
        setError("Enter an amount greater than zero.");
        return;
      }
      if (!otherIncomeAccountId) {
        setError("Pick an income account.");
        return;
      }
      payload = {
        type: "OTHER",
        receipt_date: receiptDate,
        amount: amt,
        cash_gl_account_id: Number(cashAccountId),
        income_gl_account_id: Number(otherIncomeAccountId),
        received_from: otherReceivedFrom || null,
        exclude_from_mgmt_fee: otherExclude,
        property_id: propertyId ? Number(propertyId) : null,
        reference_number: reference || null,
        remarks: remarks || null,
      };
    }

    setSubmitting(true);
    try {
      await createReceipt(payload);
      router.push(`/dashboard/accounting/receipts`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create receipt");
    } finally {
      setSubmitting(false);
    }
  }

  // ------------------------------------------------------------
  // Render
  // ------------------------------------------------------------
  return (
    <div className="max-w-5xl">
      <div className="mb-6">
        <Link
          href="/dashboard/accounting/receipts"
          className="text-sm text-slate-500 hover:text-slate-800"
        >
          ← Back to Receipts
        </Link>
        <h1 className="text-2xl font-bold text-slate-900 mt-2">New Receipt</h1>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-slate-200 mb-6">
        {RECEIPT_TYPE_ORDER.map((t) => (
          <button
            key={t}
            type="button"
            onClick={() => setTab(t)}
            className={`px-5 py-2 text-sm font-medium -mb-px border-b-2 ${
              tab === t
                ? "border-slate-900 text-slate-900"
                : "border-transparent text-slate-500 hover:text-slate-800"
            }`}
          >
            {RECEIPT_TYPE_LABELS[t]}
          </button>
        ))}
      </div>

      {error && (
        <div className="mb-4 px-4 py-2 bg-red-50 border border-red-200 text-red-700 rounded-lg text-sm">
          {error}
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Common fields */}
        <div className="bg-white border border-slate-200 rounded-xl p-5 grid grid-cols-2 gap-4">
          <div>
            <label className="block text-xs text-slate-500 mb-1">
              Receipt date *
            </label>
            <input
              type="date"
              required
              value={receiptDate}
              onChange={(e) => setReceiptDate(e.target.value)}
              className="w-full border border-slate-300 rounded px-3 py-2 text-sm"
            />
          </div>
          <div>
            <label className="block text-xs text-slate-500 mb-1">
              Cash account *
            </label>
            <select
              required
              value={cashAccountId}
              onChange={(e) =>
                setCashAccountId(e.target.value ? Number(e.target.value) : "")
              }
              className="w-full border border-slate-300 rounded px-3 py-2 text-sm"
            >
              <option value="">— Select —</option>
              {cashAccounts.map((a) => (
                <option key={a.id} value={a.id}>
                  {accountLabel(a)}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-xs text-slate-500 mb-1">Property</label>
            <select
              value={propertyId}
              onChange={(e) =>
                setPropertyId(e.target.value ? Number(e.target.value) : "")
              }
              className="w-full border border-slate-300 rounded px-3 py-2 text-sm"
            >
              <option value="">— None —</option>
              {properties.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-xs text-slate-500 mb-1">
              Reference #
            </label>
            <input
              type="text"
              value={reference}
              onChange={(e) => setReference(e.target.value)}
              placeholder="Check #, ACH trace, etc."
              className="w-full border border-slate-300 rounded px-3 py-2 text-sm"
            />
          </div>
          <div className="col-span-2">
            <label className="block text-xs text-slate-500 mb-1">Remarks</label>
            <textarea
              rows={2}
              value={remarks}
              onChange={(e) => setRemarks(e.target.value)}
              className="w-full border border-slate-300 rounded px-3 py-2 text-sm"
            />
          </div>
        </div>

        {/* TENANT tab */}
        {tab === "TENANT" && (
          <div className="bg-white border border-slate-200 rounded-xl p-5">
            <div className="grid grid-cols-2 gap-4 mb-4">
              <div>
                <label className="block text-xs text-slate-500 mb-1">
                  Tenant
                </label>
                <select
                  value={tenantUserId}
                  onChange={(e) =>
                    setTenantUserId(e.target.value ? Number(e.target.value) : "")
                  }
                  className="w-full border border-slate-300 rounded px-3 py-2 text-sm"
                >
                  <option value="">— Select —</option>
                  {tenants.map((p) => (
                    <option key={p.id} value={p.id}>
                      {personLabel(p)}
                    </option>
                  ))}
                </select>
                {tenantUserId && (
                  <button
                    type="button"
                    onClick={resetTenantRows}
                    className="text-xs text-slate-500 hover:text-slate-800 mt-1"
                  >
                    Clear tenant
                  </button>
                )}
              </div>
              <div className="text-xs text-slate-500 self-end pb-2">
                {tenantUserId
                  ? "Enter the amount received below. Add more rows if needed."
                  : "Pick a tenant to start."}
              </div>
            </div>

            <div className="text-sm font-semibold text-slate-700 mb-2">
              Lines ({tenantLines.length})
            </div>

            <table className="w-full text-sm">
              <thead className="bg-slate-50">
                <tr>
                  <th className="text-left px-3 py-2 font-medium text-slate-700">
                    GL Account
                  </th>
                  <th className="text-left px-3 py-2 font-medium text-slate-700">
                    Description
                  </th>
                  <th className="text-right px-3 py-2 font-medium text-slate-700 w-32">
                    Amount
                  </th>
                  <th className="text-center px-3 py-2 font-medium text-slate-700 w-20">
                    Prepay
                  </th>
                  <th className="w-16"></th>
                </tr>
              </thead>
              <tbody>
                {tenantLines.length === 0 && (
                  <tr>
                    <td
                      colSpan={5}
                      className="px-3 py-6 text-center text-slate-500 text-xs"
                    >
                      Pick a tenant above to start.
                    </td>
                  </tr>
                )}
                {tenantLines.map((row) => (
                  <tr key={row.key} className="border-t border-slate-100">
                    <td className="px-3 py-2">
                      <select
                        value={row.gl_account_id}
                        onChange={(e) => {
                          const id = Number(e.target.value);
                          const acct = accounts.find((a) => a.id === id);
                          updateRow(row.key, {
                            gl_account_id: id,
                            gl_account_number: acct?.gl_number ?? "",
                            gl_account_name: acct?.name ?? "",
                          });
                        }}
                        className="w-full border border-slate-300 rounded px-2 py-1 text-sm"
                      >
                        <option value={0}>— Select —</option>
                        {incomeAccounts.map((a) => (
                          <option key={a.id} value={a.id}>
                            {accountLabel(a)}
                          </option>
                        ))}
                      </select>
                    </td>
                    <td className="px-3 py-2">
                      <input
                        type="text"
                        value={row.description}
                        onChange={(e) =>
                          updateRow(row.key, { description: e.target.value })
                        }
                        placeholder="e.g. March rent"
                        className="w-full border border-slate-300 rounded px-2 py-1 text-sm"
                      />
                    </td>
                    <td className="px-3 py-2">
                      <input
                        type="number"
                        step="0.01"
                        min="0"
                        value={row.amount_to_pay || ""}
                        onChange={(e) =>
                          updateRow(row.key, {
                            amount_to_pay: Number(e.target.value) || 0,
                          })
                        }
                        className="w-full border border-slate-300 rounded px-2 py-1 text-sm text-right font-mono"
                      />
                    </td>
                    <td className="px-3 py-2 text-center">
                      <input
                        type="checkbox"
                        checked={row.is_prepayment}
                        onChange={(e) =>
                          updateRow(row.key, {
                            is_prepayment: e.target.checked,
                          })
                        }
                      />
                    </td>
                    <td className="px-3 py-2 text-right">
                      <button
                        type="button"
                        onClick={() => removeRow(row.key)}
                        className="text-red-600 hover:text-red-800 text-xs"
                      >
                        Remove
                      </button>
                    </td>
                  </tr>
                ))}

                {/* "+ Add line" row, sits right under the last data row,
                    button aligned to the right */}
                <tr className="border-t border-slate-100">
                  <td colSpan={5} className="px-3 py-2 text-right">
                    <button
                      type="button"
                      onClick={addRow}
                      className="text-xs px-3 py-1.5 bg-slate-100 hover:bg-slate-200 rounded"
                    >
                      + Add line
                    </button>
                  </td>
                </tr>
              </tbody>
              {tenantLines.length > 0 && (
                <tfoot>
                  <tr className="border-t border-slate-200 bg-slate-50">
                    <td
                      colSpan={2}
                      className="px-3 py-2 text-right font-medium text-slate-700"
                    >
                      Total
                    </td>
                    <td className="px-3 py-2 text-right font-mono font-semibold">
                      {formatMoney(tenantTotal.toFixed(2))}
                    </td>
                    <td colSpan={2}></td>
                  </tr>
                </tfoot>
              )}
            </table>
          </div>
        )}

        {/* OWNER tab */}
        {tab === "OWNER" && (
          <div className="bg-white border border-slate-200 rounded-xl p-5 grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs text-slate-500 mb-1">Owner</label>
              <select
                value={ownerUserId}
                onChange={(e) =>
                  setOwnerUserId(e.target.value ? Number(e.target.value) : "")
                }
                className="w-full border border-slate-300 rounded px-3 py-2 text-sm"
              >
                <option value="">— Select —</option>
                {owners.map((p) => (
                  <option key={p.id} value={p.id}>
                    {personLabel(p)}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-xs text-slate-500 mb-1">
                Payer name (optional)
              </label>
              <input
                type="text"
                value={ownerPayerName}
                onChange={(e) => setOwnerPayerName(e.target.value)}
                className="w-full border border-slate-300 rounded px-3 py-2 text-sm"
              />
            </div>
            <div>
              <label className="block text-xs text-slate-500 mb-1">
                Amount *
              </label>
              <input
                type="number"
                step="0.01"
                min="0"
                required
                value={ownerAmount}
                onChange={(e) => setOwnerAmount(e.target.value)}
                className="w-full border border-slate-300 rounded px-3 py-2 text-sm font-mono"
              />
            </div>
            <div>
              <label className="block text-xs text-slate-500 mb-1">
                Income account *
              </label>
              <select
                required
                value={ownerIncomeAccountId}
                onChange={(e) =>
                  setOwnerIncomeAccountId(
                    e.target.value ? Number(e.target.value) : ""
                  )
                }
                className="w-full border border-slate-300 rounded px-3 py-2 text-sm"
              >
                <option value="">— Select —</option>
                {incomeAccounts.map((a) => (
                  <option key={a.id} value={a.id}>
                    {accountLabel(a)}
                  </option>
                ))}
              </select>
              <div className="text-xs text-slate-400 mt-1">
                Defaults to 2401 Owner Funds.
              </div>
            </div>
          </div>
        )}

        {/* OTHER tab */}
        {tab === "OTHER" && (
          <div className="bg-white border border-slate-200 rounded-xl p-5 grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs text-slate-500 mb-1">
                Received from
              </label>
              <input
                type="text"
                value={otherReceivedFrom}
                onChange={(e) => setOtherReceivedFrom(e.target.value)}
                className="w-full border border-slate-300 rounded px-3 py-2 text-sm"
              />
            </div>
            <div>
              <label className="block text-xs text-slate-500 mb-1">
                Amount *
              </label>
              <input
                type="number"
                step="0.01"
                min="0"
                required
                value={otherAmount}
                onChange={(e) => setOtherAmount(e.target.value)}
                className="w-full border border-slate-300 rounded px-3 py-2 text-sm font-mono"
              />
            </div>
            <div>
              <label className="block text-xs text-slate-500 mb-1">
                Income account *
              </label>
              <select
                required
                value={otherIncomeAccountId}
                onChange={(e) =>
                  setOtherIncomeAccountId(
                    e.target.value ? Number(e.target.value) : ""
                  )
                }
                className="w-full border border-slate-300 rounded px-3 py-2 text-sm"
              >
                <option value="">— Select —</option>
                {incomeAccounts.map((a) => (
                  <option key={a.id} value={a.id}>
                    {accountLabel(a)}
                  </option>
                ))}
              </select>
            </div>
            <div className="flex items-end">
              <label className="flex items-center gap-2 text-sm text-slate-700">
                <input
                  type="checkbox"
                  checked={otherExclude}
                  onChange={(e) => setOtherExclude(e.target.checked)}
                />
                Exclude from management fee
              </label>
            </div>
          </div>
        )}

        {/* Actions */}
        <div className="flex items-center gap-3">
          <button
            type="submit"
            disabled={submitting}
            className="text-sm px-5 py-2.5 bg-slate-900 text-white rounded-lg hover:bg-slate-700 disabled:opacity-50"
          >
            {submitting ? "Posting…" : "Post Receipt"}
          </button>
          <Link
            href="/dashboard/accounting/receipts"
            className="text-sm px-4 py-2 text-slate-600 hover:text-slate-900"
          >
            Cancel
          </Link>
        </div>
      </form>
    </div>
  );
}