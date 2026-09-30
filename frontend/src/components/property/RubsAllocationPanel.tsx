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
  bill_id: number;
  billing_period_start: string;
  billing_period_end: string;
  bill_amount: string;
  allocated_total: string;
  basis: string;
  items: { unit_id: number; weight: string; share: string; amount: string }[];
  remainder_rule: string;
  meaning: string;
};
type Snapshot = {
  id: number;
  bill_id: number;
  rule_revision_id: number;
  billing_period_start: string;
  billing_period_end: string;
  bill_amount: string;
  basis: string;
  allocated_total: string;
  items: { unit_id: number; weight: string; share: string; amount: string }[];
  remainder_rule: string;
  reviewed_at: string;
};
type TrueUpPreview = {
  prior_allocated_total: string;
  actual_total: string;
  adjustment_total: string;
  items: {
    unit_id: number;
    prior_allocated_amount: string;
    true_up_target_amount: string;
    difference: string;
  }[];
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
  const [snapshots, setSnapshots] = useState<Snapshot[]>([]);
  const [reportSnapshotId, setReportSnapshotId] = useState("");
  const [selectedSnapshots, setSelectedSnapshots] = useState<Record<number, boolean>>({});
  const [trueUpStart, setTrueUpStart] = useState("");
  const [trueUpEnd, setTrueUpEnd] = useState("");
  const [actualTotal, setActualTotal] = useState("");
  const [trueUpWeights, setTrueUpWeights] = useState<Record<number, string>>({});
  const [trueUp, setTrueUp] = useState<TrueUpPreview | null>(null);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  async function load() {
    const [context, revisions, reviewedSnapshots] = await Promise.all([
      apiGet(
        `/api/properties/${propertyId}/rubs/utilities/${utilityId}/allocation-context`
      ) as Promise<{ units: ContextUnit[]; bills: ContextBill[] }>,
      apiGet(
        `/api/properties/${propertyId}/rubs/utilities/${utilityId}/allocation-rules`
      ) as Promise<Rule[]>,
      apiGet(
        `/api/properties/${propertyId}/rubs/utilities/${utilityId}/allocation-snapshots`
      ) as Promise<Snapshot[]>,
    ]);
    setUnits(context.units);
    setBills(context.bills);
    setRules(revisions);
    setSnapshots(reviewedSnapshots);
    setReportSnapshotId((current) =>
      current && reviewedSnapshots.some((row) => String(row.id) === current)
        ? current
        : String(reviewedSnapshots[0]?.id ?? "")
    );
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
    setSnapshots([]);
    setReportSnapshotId("");
    setSelectedSnapshots({});
    setTrueUpStart("");
    setTrueUpEnd("");
    setActualTotal("");
    setTrueUpWeights({});
    setTrueUp(null);
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

  async function saveReviewedSnapshot() {
    if (!preview || !ruleId || !billId) return;
    setSaving(true);
    setMessage("");
    setError("");
    try {
      const saved = (await apiPost(
        `/api/properties/${propertyId}/rubs/utilities/${utilityId}/allocation-snapshots`,
        {
          rule_revision_id: Number(ruleId),
          bill_id: Number(billId),
          request_key: requestKey("rubs-snapshot"),
        }
      )) as Snapshot;
      setMessage(`Reviewed allocation snapshot #${saved.id} saved without posting finance.`);
      setReportSnapshotId(String(saved.id));
      setSelectedSnapshots((current) => ({ ...current, [saved.id]: true }));
      setTrueUpStart((current) => current || saved.billing_period_start);
      setTrueUpEnd((current) => current || saved.billing_period_end);
      await load();
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : "Unable to save reviewed allocation snapshot."
      );
    } finally {
      setSaving(false);
    }
  }

  async function runTrueUpPreview() {
    const selectedRows = snapshots.filter(
      (snapshot) => selectedSnapshots[snapshot.id]
    );
    const snapshotIds = selectedRows.map((snapshot) => snapshot.id);
    const selectedUnitIds = new Set(
      selectedRows.flatMap((snapshot) => snapshot.items.map((item) => item.unit_id))
    );
    setSaving(true);
    setTrueUp(null);
    setMessage("");
    setError("");
    try {
      const result = (await apiPost(
        `/api/properties/${propertyId}/rubs/utilities/${utilityId}/true-up-preview`,
        {
          period_start: trueUpStart,
          period_end: trueUpEnd,
          snapshot_ids: snapshotIds,
          actual_total: actualTotal,
          unit_weights: units
            .filter((unit) => selectedUnitIds.has(unit.id))
            .map((unit) => ({
              unit_id: unit.id,
              weight: trueUpWeights[unit.id],
            })),
        }
      )) as TrueUpPreview;
      setTrueUp(result);
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : "Unable to preview year-end true-up."
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

  const reportSnapshot =
    snapshots.find((snapshot) => String(snapshot.id) === reportSnapshotId) ?? null;

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
          <button
            type="button"
            disabled={saving}
            className="rounded border px-4 py-2 text-sm font-medium disabled:opacity-50"
            onClick={() => void saveReviewedSnapshot()}
          >
            Save reviewed allocation snapshot
          </button>
        </div>
      )}

      <div className="space-y-3 rounded border p-3">
        <div>
          <h4 className="text-sm font-medium">RUBs allocation detail report</h4>
          <p className="text-xs text-slate-500">
            Reviewed allocation detail per utility bill period. This report reads
            preserved review history only and does not create charges, invoices, or GL entries.
          </p>
        </div>
        {snapshots.length === 0 ? (
          <p className="text-xs text-slate-500">
            No reviewed allocation history is available for reporting.
          </p>
        ) : (
          <>
            <label className="block text-sm">
              Report bill period
              <select
                aria-label="RUBs report bill period"
                className="mt-1 w-full rounded border px-3 py-2"
                value={reportSnapshotId}
                onChange={(event) => setReportSnapshotId(event.target.value)}
              >
                {snapshots.map((snapshot) => (
                  <option key={snapshot.id} value={snapshot.id}>
                    {snapshot.billing_period_start} to {snapshot.billing_period_end} · Bill #{snapshot.bill_id}
                  </option>
                ))}
              </select>
            </label>
            {reportSnapshot && (
              <div className="space-y-2" aria-label="RUBs allocation detail report result">
                <p className="text-sm font-medium">
                  Bill period {reportSnapshot.billing_period_start} to{" "}
                  {reportSnapshot.billing_period_end} · Bill #{reportSnapshot.bill_id}
                </p>
                <p className="text-xs text-slate-600">
                  Rule revision #{reportSnapshot.rule_revision_id} · {reportSnapshot.basis} ·
                  Bill total USD {reportSnapshot.bill_amount} · Reviewed allocated total USD{" "}
                  {reportSnapshot.allocated_total}
                </p>
                <table className="w-full text-left text-sm">
                  <thead>
                    <tr className="border-b">
                      <th className="p-2">Unit</th>
                      <th className="p-2">Weight</th>
                      <th className="p-2">Share</th>
                      <th className="p-2">Allocated amount</th>
                    </tr>
                  </thead>
                  <tbody>
                    {reportSnapshot.items.map((item) => {
                      const unit = units.find((row) => row.id === item.unit_id);
                      return (
                        <tr key={item.unit_id} className="border-b">
                          <td className="p-2">
                            {unit ? unit.unit_number : `ID ${item.unit_id}`}
                          </td>
                          <td className="p-2">{item.weight}</td>
                          <td className="p-2">{item.share}</td>
                          <td className="p-2">USD {item.amount}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
                <p className="text-xs text-slate-500">
                  {reportSnapshot.remainder_rule}
                </p>
                <p className="text-xs text-slate-500">
                  Reviewed snapshot #{reportSnapshot.id} at {reportSnapshot.reviewed_at}.
                </p>
              </div>
            )}
          </>
        )}
      </div>

      <div className="space-y-3 rounded border p-3">
        <div>
          <h4 className="text-sm font-medium">Year-end true-up preview</h4>
          <p className="text-xs text-slate-500">
            Select reviewed allocation history, enter the explicit actual total and
            explicit per-unit true-up weights. This preview does not post charges or GL.
          </p>
        </div>
        {snapshots.length === 0 ? (
          <p className="text-xs text-slate-500">No reviewed allocation snapshots saved.</p>
        ) : (
          snapshots.map((snapshot) => (
            <label key={snapshot.id} className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                aria-label={`Reviewed snapshot ${snapshot.id}`}
                checked={Boolean(selectedSnapshots[snapshot.id])}
                onChange={(event) =>
                  setSelectedSnapshots((current) => ({
                    ...current,
                    [snapshot.id]: event.target.checked,
                  }))
                }
              />
              Snapshot #{snapshot.id}: {snapshot.billing_period_start} to{" "}
              {snapshot.billing_period_end} · USD {snapshot.allocated_total}
            </label>
          ))
        )}
        <div className="grid gap-3 sm:grid-cols-3">
          <label className="text-sm">
            True-up period start
            <input
              aria-label="True-up period start"
              type="date"
              className="mt-1 w-full rounded border px-3 py-2"
              value={trueUpStart}
              onChange={(event) => setTrueUpStart(event.target.value)}
            />
          </label>
          <label className="text-sm">
            True-up period end
            <input
              aria-label="True-up period end"
              type="date"
              className="mt-1 w-full rounded border px-3 py-2"
              value={trueUpEnd}
              onChange={(event) => setTrueUpEnd(event.target.value)}
            />
          </label>
          <label className="text-sm">
            Year-end actual total
            <input
              aria-label="Year-end actual total"
              type="number"
              min="0"
              step="0.01"
              className="mt-1 w-full rounded border px-3 py-2"
              value={actualTotal}
              onChange={(event) => setActualTotal(event.target.value)}
            />
          </label>
        </div>
        <div className="space-y-2">
          {units.map((unit) => (
            <label key={unit.id} className="block text-xs">
              True-up weight for unit {unit.unit_number}
              <input
                aria-label={`True-up weight for unit ${unit.unit_number}`}
                type="number"
                min="0.000001"
                step="any"
                className="ml-2 w-28 rounded border px-2 py-1"
                value={trueUpWeights[unit.id] ?? ""}
                onChange={(event) =>
                  setTrueUpWeights((current) => ({
                    ...current,
                    [unit.id]: event.target.value,
                  }))
                }
              />
            </label>
          ))}
        </div>
        <button
          type="button"
          disabled={
            saving ||
            !trueUpStart ||
            !trueUpEnd ||
            actualTotal === "" ||
            !snapshots.some((snapshot) => selectedSnapshots[snapshot.id]) ||
            units
              .filter((unit) =>
                snapshots
                  .filter((snapshot) => selectedSnapshots[snapshot.id])
                  .some((snapshot) =>
                    snapshot.items.some((item) => item.unit_id === unit.id)
                  )
              )
              .some((unit) => !trueUpWeights[unit.id])
          }
          className="rounded border px-4 py-2 text-sm font-medium disabled:opacity-50"
          onClick={() => void runTrueUpPreview()}
        >
          Preview year-end true-up
        </button>
        {trueUp && (
          <div className="space-y-2 rounded border p-3">
            <p className="text-sm font-medium">
              Finance-neutral true-up: USD {trueUp.prior_allocated_total} prior to USD{" "}
              {trueUp.actual_total} actual · difference USD {trueUp.adjustment_total}
            </p>
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b">
                  <th className="p-2">Unit ID</th>
                  <th className="p-2">Prior</th>
                  <th className="p-2">Target</th>
                  <th className="p-2">Difference</th>
                </tr>
              </thead>
              <tbody>
                {trueUp.items.map((item) => (
                  <tr key={item.unit_id} className="border-b">
                    <td className="p-2">{item.unit_id}</td>
                    <td className="p-2">USD {item.prior_allocated_amount}</td>
                    <td className="p-2">USD {item.true_up_target_amount}</td>
                    <td className="p-2">USD {item.difference}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="text-xs text-slate-500">{trueUp.remainder_rule}</p>
            <p className="text-xs text-slate-500">{trueUp.meaning}</p>
          </div>
        )}
      </div>
    </div>
  );
}
