// ============================================================
// New Management Fee page
// ------------------------------------------------------------
// Route: /dashboard/accounting/management-fees/new
//
// Flow (AppFolio parity):
//   1. Pick property + period
//   2. Click "Preview" → shows eligible income + calculated fee
//   3. Confirm → posts to GL
//
// Also shows the eligible rent lines so the manager can verify
// the base before committing.
// ============================================================

"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import {
  previewManagementFee,
  runManagementFee,
  FeePreview,
} from "@/lib/managementFees";
import { apiGet } from "@/lib/api";

type Property = { id: number; name: string };

export default function NewManagementFeePage() {
  const router = useRouter();

  const [properties, setProperties] = useState<Property[]>([]);
  const [propertyId, setPropertyId] = useState<number | "">("");
  const [periodStart, setPeriodStart] = useState("");
  const [periodEnd, setPeriodEnd] = useState(
    new Date().toISOString().slice(0, 10)
  );
  const [notes, setNotes] = useState("");

  const [preview, setPreview] = useState<FeePreview | null>(null);
  const [previewing, setPreviewing] = useState(false);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState("");

  // Load properties + set default period (start = 1st of current month)
  useEffect(() => {
    (async () => {
      try {
        const propsRaw = (await apiGet("/properties")) as unknown;
        const props: Property[] = Array.isArray(propsRaw)
          ? (propsRaw as Property[])
          : (((propsRaw as { items?: Property[] })?.items ?? []) as Property[]);
        setProperties(props);

        const now = new Date();
        const firstOfMonth = new Date(now.getFullYear(), now.getMonth(), 1);
        setPeriodStart(firstOfMonth.toISOString().slice(0, 10));
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load");
      }
    })();
  }, []);

  async function handlePreview() {
    setError("");
    setPreview(null);
    if (!propertyId) {
      setError("Pick a property.");
      return;
    }
    if (!periodStart || !periodEnd) {
      setError("Pick a period.");
      return;
    }

    setPreviewing(true);
    try {
      const p = await previewManagementFee({
        property_id: Number(propertyId),
        period_start: periodStart,
        period_end: periodEnd,
      });
      setPreview(p);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Preview failed");
    } finally {
      setPreviewing(false);
    }
  }

  async function handleRun() {
    setError("");
    if (!preview || !preview.can_run) {
      setError("Preview first, or the preview says this can't be run.");
      return;
    }

    setRunning(true);
    try {
      await runManagementFee({
        property_id: Number(propertyId),
        period_start: periodStart,
        period_end: periodEnd,
        notes: notes || null,
      });
      router.push(`/dashboard/accounting/management-fees`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Run failed");
    } finally {
      setRunning(false);
    }
  }

  return (
    <div className="max-w-4xl">
      <div className="mb-6">
        <Link
          href="/dashboard/accounting/management-fees"
          className="text-sm text-slate-500 hover:text-slate-800"
        >
          ← Back to Management Fees
        </Link>
        <h1 className="text-2xl font-bold text-slate-900 mt-2">
          Pay Management Fees
        </h1>
      </div>

      {error && (
        <div className="mb-4 px-4 py-2 bg-red-50 border border-red-200 text-red-700 rounded-lg text-sm">
          {error}
        </div>
      )}

      {/* Inputs */}
      <div className="bg-white border border-slate-200 rounded-xl p-5 mb-6 grid grid-cols-2 gap-4">
        <div>
          <label className="block text-xs text-slate-500 mb-1">
            Property *
          </label>
          <select
            required
            value={propertyId}
            onChange={(e) => {
              setPropertyId(e.target.value ? Number(e.target.value) : "");
              setPreview(null);
            }}
            className="w-full border border-slate-300 rounded px-3 py-2 text-sm"
          >
            <option value="">— Select —</option>
            {properties.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-xs text-slate-500 mb-1">Notes</label>
          <input
            type="text"
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            className="w-full border border-slate-300 rounded px-3 py-2 text-sm"
          />
        </div>
        <div>
          <label className="block text-xs text-slate-500 mb-1">
            Period start *
          </label>
          <input
            type="date"
            required
            value={periodStart}
            onChange={(e) => {
              setPeriodStart(e.target.value);
              setPreview(null);
            }}
            className="w-full border border-slate-300 rounded px-3 py-2 text-sm"
          />
        </div>
        <div>
          <label className="block text-xs text-slate-500 mb-1">
            Period end *
          </label>
          <input
            type="date"
            required
            value={periodEnd}
            onChange={(e) => {
              setPeriodEnd(e.target.value);
              setPreview(null);
            }}
            className="w-full border border-slate-300 rounded px-3 py-2 text-sm"
          />
        </div>
        <div className="col-span-2">
          <button
            type="button"
            onClick={handlePreview}
            disabled={previewing || !propertyId || !periodStart || !periodEnd}
            className="text-sm px-4 py-2 bg-slate-100 hover:bg-slate-200 rounded disabled:opacity-50"
          >
            {previewing ? "Calculating…" : "Preview fee"}
          </button>
        </div>
      </div>

      {/* Preview */}
      {preview && (
        <div className="bg-white border border-slate-200 rounded-xl p-5 mb-6 space-y-4">
          <div className="text-sm font-semibold text-slate-700">
            Preview — {preview.property_name}
          </div>

          {!preview.can_run && (
            <div className="px-3 py-2 bg-yellow-50 border border-yellow-200 text-yellow-800 rounded text-sm">
              {preview.reason || "This fee cannot be run."}
            </div>
          )}

          <div className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <div className="text-xs text-slate-500">Rent income</div>
              <div className="font-mono">
                {Number(preview.rent_income_total).toLocaleString("en-US", {
                  style: "currency",
                  currency: "USD",
                })}
              </div>
            </div>
            <div>
              <div className="text-xs text-slate-500">Other fee income</div>
              <div className="font-mono">
                {Number(preview.other_fee_income_total).toLocaleString("en-US", {
                  style: "currency",
                  currency: "USD",
                })}
              </div>
            </div>
          </div>

          <div className="border-t border-slate-200 pt-3 space-y-2 text-sm">
            <div className="flex justify-between">
              <span className="text-slate-600">
                Rent fee ({preview.rent_fee_pct}%)
              </span>
              <span className="font-mono">
                {Number(preview.rent_fee_amount).toLocaleString("en-US", {
                  style: "currency",
                  currency: "USD",
                })}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-600">
                Other fee ({preview.other_fee_pct}%)
              </span>
              <span className="font-mono">
                {Number(preview.other_fee_amount).toLocaleString("en-US", {
                  style: "currency",
                  currency: "USD",
                })}
              </span>
            </div>
            <div className="flex justify-between border-t border-slate-200 pt-2 font-semibold">
              <span>Total Fee</span>
              <span className="font-mono text-lg">
                {Number(preview.total_fee).toLocaleString("en-US", {
                  style: "currency",
                  currency: "USD",
                })}
              </span>
            </div>
          </div>

          {/* Eligible lines */}
          {preview.rent_lines.length > 0 && (
            <div className="border-t border-slate-200 pt-3">
              <div className="text-xs font-semibold text-slate-500 uppercase mb-2">
                Eligible rent lines ({preview.rent_lines.length})
              </div>
              <ul className="text-xs space-y-1">
                {preview.rent_lines.map((l, i) => (
                  <li key={i} className="flex justify-between">
                    <span className="text-slate-600">
                      {l.transaction_date} · receipt #{l.receipt_id} ·{" "}
                      {l.gl_account_number} {l.gl_account_name}
                    </span>
                    <span className="font-mono">
                      {Number(l.amount).toLocaleString("en-US", {
                        style: "currency",
                        currency: "USD",
                      })}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {preview.other_lines.length > 0 && (
            <div className="border-t border-slate-200 pt-3">
              <div className="text-xs font-semibold text-slate-500 uppercase mb-2">
                Eligible other fee lines ({preview.other_lines.length})
              </div>
              <ul className="text-xs space-y-1">
                {preview.other_lines.map((l, i) => (
                  <li key={i} className="flex justify-between">
                    <span className="text-slate-600">
                      {l.transaction_date} · receipt #{l.receipt_id} ·{" "}
                      {l.gl_account_number} {l.gl_account_name}
                    </span>
                    <span className="font-mono">
                      {Number(l.amount).toLocaleString("en-US", {
                        style: "currency",
                        currency: "USD",
                      })}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Actions */}
          <div className="flex items-center gap-3 pt-3 border-t border-slate-200">
            <button
              type="button"
              onClick={handleRun}
              disabled={running || !preview.can_run}
              className="text-sm px-5 py-2.5 bg-slate-900 text-white rounded-lg hover:bg-slate-700 disabled:opacity-50"
            >
              {running ? "Posting…" : "Post Management Fee"}
            </button>
            <button
              type="button"
              onClick={() => setPreview(null)}
              className="text-sm px-4 py-2 text-slate-600 hover:text-slate-900"
            >
              Clear preview
            </button>
          </div>
        </div>
      )}
    </div>
  );
}