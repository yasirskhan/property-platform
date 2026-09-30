"use client";

import { FormEvent, useEffect, useState } from "react";
import { apiGet, apiPost } from "@/lib/api";

type ContextUnit = { id: number; unit_number: string; square_feet: number | null };
type ContextBill = {
  id: number;
  billing_period_start: string | null;
  billing_period_end: string | null;
  amount: string;
  period_valid: boolean;
};
type Rule = {
  id: number;
  revision_number: number;
  effective_date: string;
  basis: string;
  unit_inputs: { unit_id: number; weight: string }[];
  status: string;
  is_authorized: boolean;
};
type Preview = {
  bill_amount: string;
  allocated_total: string;
  basis: string;
  items: { unit_id: number; weight: string; share: string; amount: string }[];
  remainder_rule: string;
  meaning: string;
};

function requestKey(prefix: string) {
  const suffix =
    typeof crypto !== "undefined" && "randomUUID" in crypto
      ? crypto.randomUUID()
      : `${Date.now()}-${Math.random().toString(16).slice(2)}`;
  return `${prefix}-${suffix}`;
}

export default function RubsAllocationPanel({
  propertyId,
  utilityId,
}: {
  propertyId: number;
  utilityId: number;
}) {
  const [units, setUnits] = useState<ContextUnit[]>([]);
  const [bills, setBills] = useState<ContextBill[]>([]);
  const [rules, setRules] = useState<Rule[]>([]);
  const [basis, setBasis] = useState("SQUARE_FEET");
  const [effectiveDate, setEffectiveDate] = useState("");
  const [selected, setSelected] = useState<Record<number, boolean>>({});
  const [weights, setWeights] = useState<Record<number, string>>({});
  const [billId, setBillId] = useState("");
  const [ruleId, setRuleId] = useState("");
  const [preview, setPreview] = useState<Preview | null>(null);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  async function load() {
    const [context, revisions] = await Promise.all([
      apiGet(
        `/api/properties/${propertyId}/rubs/utilities/${utilityId}/allocation-context`
      ) as Promise<{ units: ContextUnit[]; bills: ContextBill[] }>,
      apiGet(
        `/api/properties/${propertyId}/rubs/utilities/${utilityId}/allocation-rules`
      ) as Promise<Rule[]>,
    ]);
    setUnits(context.units);
    setBills(context.bills);
    setRules(revisions);
    setRuleId(
      (current) =>
        current || String(revisions.find((row) => row.is_authorized)?.id ?? "")
    );
    setBillId(
      (current) =>
        current || String(context.bills.find((row) => row.period_valid)?.id ?? "")
    );
  }

  useEffect(() => {
    setPreview(null);
    setMessage("");
    setError("");
    setSelected({});
    setWeights({});
    setRuleId("");
    setBillId("");
    void load().catch((cause) =>
      setError(
        cause instanceof Error
          ? cause.message
          : "RUBs allocation setup unavailable."
      )
    );
  }, [propertyId, utilityId]);

  async function createRule(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true);
    setMessage("");
    setError("");
    try {
      const selectedUnits = units
        .filter((unit) => selected[unit.id])
        .map((unit) => ({
          unit_id: unit.id,
          ...(basis === "SQUARE_FEET" ? {} : { weight: weights[unit.id] }),
        }));
      const created = (await apiPost(
        `/api/properties/${propertyId}/rubs/utilities/${utilityId}/allocation-rules`,
        {
          basis,
          effective_date: effectiveDate,
          units: selectedUnits,
          request_key: requestKey("rubs-rule"),
        }
      )) as Rule;
      setMessage(
        `Draft rule revision ${created.revision_number} recorded. Authorization is still required.`
      );
      await load();
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : "Unable to create allocation rule."
      );
    } finally {
      setSaving(false);
    }
  }

  async function authorize(rule: Rule) {
    setSaving(true);
    setMessage("");
    setError("");
    try {
      const updated = (await apiPost(
        `/api/properties/${propertyId}/rubs/utilities/${utilityId}/allocation-rules/${rule.id}/authorize`,
        { request_key: requestKey("rubs-authorize") }
      )) as Rule;
      setMessage(
        `Rule revision ${updated.revision_number} explicitly authorized.`
      );
      setRuleId(String(updated.id));
      await load();
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : "Unable to authorize allocation rule."
      );
    } finally {
      setSaving(false);
    }
  }

  async function runPreview() {
    if (!ruleId || !billId) return;
    setSaving(true);
    setPreview(null);
    setMessage("");
    setError("");
    try {
      const result = (await apiPost(
        `/api/properties/${propertyId}/rubs/utilities/${utilityId}/allocation-preview`,
        { rule_revision_id: Number(ruleId), bill_id: Number(billId) }
      )) as Preview;
      setPreview(result);
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : "Unable to preview allocation."
      );
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="space-y-4 rounded-lg border p-4">
      <div>
        <h3 className="font-semibold text-slate-900">
          Allocation rule and preview
        </h3>
        <p className="text-xs text-slate-600">
          Staff must explicitly select included units. A draft rule never
          authorizes itself. Preview is finance-neutral and does not create
          tenant/owner charges or GL entries.
        </p>
      </div>

      <form className="space-y-3" onSubmit={createRule}>
        <div className="grid gap-3 sm:grid-cols-2">
          <label className="text-sm">
            Allocation basis
            <select
              className="mt-1 w-full rounded border px-3 py-2"
              value={basis}
              onChange={(event) => setBasis(event.target.value)}
            >
              <option value="SQUARE_FEET">Square feet</option>
              <option value="OCCUPANCY">Occupancy weight</option>
              <option value="FIXTURES">Fixture weight</option>
              <option value="MANUAL_WEIGHT">Manual weight</option>
            </select>
          </label>
          <label className="text-sm">
            Effective date
            <input
              required
              type="date"
              className="mt-1 w-full rounded border px-3 py-2"
              value={effectiveDate}
              onChange={(event) => setEffectiveDate(event.target.value)}
            />
          </label>
        </div>

        <fieldset className="space-y-2">
          <legend className="text-sm font-medium">
            Explicitly included units
          </legend>
          {units.length === 0 ? (
            <p className="text-xs text-slate-500">
              No active units are available.
            </p>
          ) : (
            units.map((unit) => (
              <div
                key={unit.id}
                className="flex flex-wrap items-center gap-3 text-sm"
              >
                <label className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={Boolean(selected[unit.id])}
                    onChange={(event) =>
                      setSelected((current) => ({
                        ...current,
                        [unit.id]: event.target.checked,
                      }))
                    }
                  />
                  Unit {unit.unit_number} (ID {unit.id})
                </label>
                {basis === "SQUARE_FEET" ? (
                  <span className="text-xs text-slate-500">
                    {unit.square_feet
                      ? `${unit.square_feet} sq ft`
                      : "square feet missing"}
                  </span>
                ) : (
                  <label className="text-xs">
                    Weight
                    <input
                      aria-label={`Weight for unit ${unit.unit_number}`}
                      type="number"
                      min="0.000001"
                      step="any"
                      className="ml-2 w-28 rounded border px-2 py-1"
                      value={weights[unit.id] ?? ""}
                      onChange={(event) =>
                        setWeights((current) => ({
                          ...current,
                          [unit.id]: event.target.value,
                        }))
                      }
                    />
                  </label>
                )}
              </div>
            ))
          )}
        </fieldset>

        <button
          type="submit"
          disabled={saving}
          className="rounded border px-4 py-2 text-sm font-medium disabled:opacity-50"
        >
          Create draft rule revision
        </button>
      </form>

      <div className="space-y-2">
        <h4 className="text-sm font-medium">Rule revisions</h4>
        {rules.length === 0 ? (
          <p className="text-xs text-slate-500">
            No allocation rules recorded.
          </p>
        ) : (
          rules.map((rule) => (
            <div
              key={rule.id}
              className="flex flex-wrap items-center justify-between gap-2 rounded border p-2 text-sm"
            >
              <span>
                Revision {rule.revision_number}: {rule.basis} effective{" "}
                {rule.effective_date} · {rule.status}
              </span>
              {!rule.is_authorized && (
                <button
                  type="button"
                  disabled={saving}
                  className="rounded border px-3 py-1 text-xs font-medium disabled:opacity-50"
                  onClick={() => void authorize(rule)}
                >
                  Authorize revision {rule.revision_number}
                </button>
              )}
            </div>
          ))
        )}
      </div>

      <div className="grid gap-3 sm:grid-cols-3">
        <label className="text-sm">
          Authorized rule
          <select
            className="mt-1 w-full rounded border px-3 py-2"
            value={ruleId}
            onChange={(event) => setRuleId(event.target.value)}
          >
            <option value="">Select authorized rule</option>
            {rules
              .filter((rule) => rule.is_authorized)
              .map((rule) => (
                <option key={rule.id} value={rule.id}>
                  Revision {rule.revision_number} · {rule.basis}
                </option>
              ))}
          </select>
        </label>

        <label className="text-sm">
          Utility bill
          <select
            className="mt-1 w-full rounded border px-3 py-2"
            value={billId}
            onChange={(event) => setBillId(event.target.value)}
          >
            <option value="">Select bill</option>
            {bills.map((bill) => (
              <option key={bill.id} value={bill.id}>
                Bill #{bill.id} · {bill.billing_period_start ?? "missing"} to{" "}
                {bill.billing_period_end ?? "missing"} · USD {bill.amount}
              </option>
            ))}
          </select>
        </label>

        <div className="flex items-end">
          <button
            type="button"
            disabled={saving || !ruleId || !billId}
            className="rounded border px-4 py-2 text-sm font-medium disabled:opacity-50"
            onClick={() => void runPreview()}
          >
            Preview allocation
          </button>
        </div>
      </div>

      {message && (
        <p role="status" className="text-sm text-slate-700">
          {message}
        </p>
      )}
      {error && (
        <p role="alert" className="text-sm text-red-700">
          {error}
        </p>
      )}

      {preview && (
        <div className="space-y-2 rounded border p-3">
          <p className="text-sm font-medium">
            Finance-neutral preview: USD {preview.allocated_total} of USD{" "}
            {preview.bill_amount}
          </p>
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b">
                <th className="p-2">Unit ID</th>
                <th className="p-2">Weight</th>
                <th className="p-2">Preview amount</th>
              </tr>
            </thead>
            <tbody>
              {preview.items.map((item) => (
                <tr key={item.unit_id} className="border-b">
                  <td className="p-2">{item.unit_id}</td>
                  <td className="p-2">{item.weight}</td>
                  <td className="p-2">USD {item.amount}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="text-xs text-slate-500">
            {preview.remainder_rule}
          </p>
          <p className="text-xs text-slate-500">{preview.meaning}</p>
        </div>
      )}
    </div>
  );
}
