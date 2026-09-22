// ============================================================
// New Management Fee page
// ------------------------------------------------------------
// Preview a fee calculation for a property + period, then run it.
// Run creates a Bill (DR 6001 / CR 2100).
//
// Uses formatMoney() from lib/money.ts for every amount so the
// org's currency setting is respected (Section 59).
// ============================================================

"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { apiGet } from "@/lib/api";
import { formatMoney } from "@/lib/money";
import {
  previewManagementFee,
  runManagementFee,
  type FeePreview,
} from "@/lib/managementFees";

interface Property {
  id: number;
  name: string;
  mgmt_fee_pct?: string | null;
  mgmt_fee_flat?: string | null;
  mgmt_fee_min?: string | null;
}

export default function NewManagementFeePage() {
  const router = useRouter();

  const [properties, setProperties] = useState<Property[]>([]);
  const [propertyId, setPropertyId] = useState<number | "">("");
  const [periodStart, setPeriodStart] = useState<string>(() => {
    const d = new Date();
    d.setDate(1);
    return d.toISOString().slice(0, 10);
  });
  const [periodEnd, setPeriodEnd] = useState<string>(() => {
    const d = new Date();
    d.setMonth(d.getMonth() + 1);
    d.setDate(0);
    return d.toISOString().slice(0, 10);
  });
  const [preview, setPreview] = useState<FeePreview | null>(null);

  const [loading, setLoading] = useState(true);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiGet("/properties")
      .then((p) => setProperties(p as Property[]))
      .catch((e) =>
        setError(e instanceof Error ? e.message : "Could not load properties.")
      )
      .finally(() => setLoading(false));
  }, []);

  async function doPreview() {
    if (!propertyId) {
      setError("Pick a property.");
      return;
    }
    setPreviewLoading(true);
    setError(null);
    setPreview(null);
    try {
      const p = await previewManagementFee({
        property_id: propertyId,
        period_start: periodStart,
        period_end: periodEnd,
      });
      setPreview(p);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Could not preview.");
    } finally {
      setPreviewLoading(false);
    }
  }

  async function doRun() {
    if (!preview || !propertyId) return;
    setRunning(true);
    setError(null);
    try {
      const run = await runManagementFee({
        property_id: propertyId,
        period_start: periodStart,
        period_end: periodEnd,
      });
      router.push(`/dashboard/accounting/management-fees?highlight=${run.id}`);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Could not run fee.");
    } finally {
      setRunning(false);
    }
  }

  if (loading) {
    return (
      <div className="max-w-3xl mx-auto p-6 text-slate-500">Loading...</div>
    );
  }

  return (
    <div className="max-w-3xl mx-auto p-6">
      <h1 className="text-xl font-semibold text-slate-900 mb-1">
        Pay Management Fees
      </h1>
      <p className="text-sm text-slate-500 mb-6">
        Calculate management fees for a property and period. Running creates a
        Bill you can pay like any other payable.
      </p>

      {error && (
        <div className="text-sm text-red-600 mb-4 bg-red-50 border border-red-200 rounded-md px-3 py-2">
          {error}
        </div>
      )}

      <div className="bg-white rounded-lg border border-slate-200 p-5 mb-5">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
          <div>
            <label className="block text-xs text-slate-600 mb-1">
              Property <span className="text-red-500">*</span>
            </label>
            <select
              value={propertyId}
              onChange={(e) =>
                setPropertyId(e.target.value ? Number(e.target.value) : "")
              }
              className="w-full border border-slate-300 rounded-md px-3 py-1.5 text-sm bg-white"
            >
              <option value="">Select property...</option>
              {properties.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-xs text-slate-600 mb-1">
              Period start <span className="text-red-500">*</span>
            </label>
            <input
              type="date"
              value={periodStart}
              onChange={(e) => setPeriodStart(e.target.value)}
              className="w-full border border-slate-300 rounded-md px-3 py-1.5 text-sm"
            />
          </div>
          <div>
            <label className="block text-xs text-slate-600 mb-1">
              Period end <span className="text-red-500">*</span>
            </label>
            <input
              type="date"
              value={periodEnd}
              onChange={(e) => setPeriodEnd(e.target.value)}
              className="w-full border border-slate-300 rounded-md px-3 py-1.5 text-sm"
            />
          </div>
        </div>
        <div className="flex justify-end">
          <button
            type="button"
            onClick={doPreview}
            disabled={previewLoading}
            className="px-4 py-2 rounded-md bg-slate-700 text-white text-sm font-medium hover:bg-slate-800 disabled:opacity-50"
          >
            {previewLoading ? "Computing..." : "Preview"}
          </button>
        </div>
      </div>

      {preview && (
        <div className="bg-white rounded-lg border border-slate-200 p-5 mb-5">
          <h2 className="text-base font-semibold text-slate-900 mb-3">
            Preview
          </h2>

          <div className="grid grid-cols-2 gap-3 mb-4 text-sm">
            <div>
              <div className="text-xs text-slate-500">Rent income</div>
              <div className="font-mono">
                {formatMoney(preview.rent_income_total)}
              </div>
            </div>
            <div>
              <div className="text-xs text-slate-500">
                Other fee income
              </div>
              <div className="font-mono">
                {formatMoney(preview.other_fee_income_total)}
              </div>
            </div>
            <div>
              <div className="text-xs text-slate-500">
                Rent fee ({preview.rent_fee_pct}%)
              </div>
              <div className="font-mono">
                {formatMoney(preview.rent_fee_amount)}
              </div>
            </div>
            <div>
              <div className="text-xs text-slate-500">
                Other fee ({preview.other_fee_pct}%)
              </div>
              <div className="font-mono">
                {formatMoney(preview.other_fee_amount)}
              </div>
            </div>
            <div className="col-span-2 border-t border-slate-200 pt-3">
              <div className="text-xs text-slate-500">Total fee</div>
              <div className="text-xl font-semibold font-mono">
                {formatMoney(preview.total_fee)}
              </div>
            </div>
          </div>

          {preview.rent_lines.length > 0 && (
            <div className="mb-3">
              <div className="text-xs text-slate-500 mb-1">Rent lines</div>
              <div className="border border-slate-200 rounded-md overflow-hidden">
                <table className="w-full text-sm">
                  <tbody>
                    {preview.rent_lines.map((l, i) => (
                      <tr key={i} className="border-t border-slate-100 first:border-t-0">
                        <td className="px-3 py-2 text-slate-500">
                          {l.gl_account_number} {l.gl_account_name}
                        </td>
                        <td className="px-3 py-2 text-right font-mono">
                          {formatMoney(l.amount)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {preview.other_lines.length > 0 && (
            <div className="mb-3">
              <div className="text-xs text-slate-500 mb-1">Other fee lines</div>
              <div className="border border-slate-200 rounded-md overflow-hidden">
                <table className="w-full text-sm">
                  <tbody>
                    {preview.other_lines.map((l, i) => (
                      <tr key={i} className="border-t border-slate-100 first:border-t-0">
                        <td className="px-3 py-2 text-slate-500">
                          {l.gl_account_number} {l.gl_account_name}
                        </td>
                        <td className="px-3 py-2 text-right font-mono">
                          {formatMoney(l.amount)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          <div className="flex justify-end mt-4">
            <button
              type="button"
              onClick={doRun}
              disabled={running || !preview.can_run}
              className="px-4 py-2 rounded-md bg-blue-600 text-white text-sm font-medium hover:bg-blue-700 disabled:opacity-50"
            >
              {running ? "Running..." : "Run fee"}
            </button>
          </div>
          {!preview.can_run && preview.reason && (
            <div className="text-xs text-red-600 mt-2 text-right">
              {preview.reason}
            </div>
          )}
        </div>
      )}
    </div>
  );
}