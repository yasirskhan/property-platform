// ============================================================
// New Owner Statement page
// ------------------------------------------------------------
// Pick an owner + period, preview, generate a frozen snapshot.
//
// Uses formatMoney() from lib/money.ts for every amount so the
// org's currency setting is respected (Section 59).
// ============================================================

"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { apiGet } from "@/lib/api";
import { formatMoney } from "@/lib/money";
import { useDisplay } from "@/contexts/DisplayContext";
import {
  previewOwnerStatement,
  generateOwnerStatement,
  type StatementPreview,
} from "@/lib/ownerStatements";

interface Person {
  id: number;
  first_name: string;
  last_name: string;
  email: string;
  role: string;
}

function personLabel(p: Person): string {
  const nm = `${p.first_name || ""} ${p.last_name || ""}`.trim();
  return nm || p.email || `#${p.id}`;
}

export default function NewOwnerStatementPage() {
  const router = useRouter();
  const { prefs } = useDisplay();

  const [owners, setOwners] = useState<Person[]>([]);
  const [ownerId, setOwnerId] = useState<number | "">("");
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
  const [preview, setPreview] = useState<StatementPreview | null>(null);
  const [notes, setNotes] = useState("");

  const [loading, setLoading] = useState(true);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiGet("/users?role=OWNER")
      .then((u) => setOwners(u as Person[]))
      .catch((e) =>
        setError(e instanceof Error ? e.message : "Could not load owners.")
      )
      .finally(() => setLoading(false));
  }, []);

  async function doPreview() {
    if (!ownerId) {
      setError("Pick an owner.");
      return;
    }
    setPreviewLoading(true);
    setError(null);
    setPreview(null);
    try {
      const p = await previewOwnerStatement({
        owner_id: ownerId,
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

  async function doGenerate() {
    if (!ownerId || !preview) return;
    setGenerating(true);
    setError(null);
    try {
      const stmt = await generateOwnerStatement({
        owner_id: ownerId,
        period_start: periodStart,
        period_end: periodEnd,
        notes: notes || null,
      });
      router.push(`/dashboard/accounting/owner-statements/${stmt.id}`);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Could not generate.");
    } finally {
      setGenerating(false);
    }
  }

  if (loading) {
    return (
      <div className="max-w-3xl mx-auto p-6 text-slate-500">Loading...</div>
    );
  }

  return (
    <div className="max-w-3xl mx-auto p-6" data-layout-mode={(prefs?.layout_mode ?? "TABS").toLowerCase()} data-density={(prefs?.density ?? "COMFORTABLE").toLowerCase()}>
      <h1 className="text-xl font-semibold text-slate-900 mb-1">
        New Owner Statement
      </h1>
      <p className="text-sm text-slate-500 mb-6">
        Preview shows the transactions before freezing. Once generated, the
        statement never changes.
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
              Owner <span className="text-red-500">*</span>
            </label>
            <select
              value={ownerId}
              onChange={(e) =>
                setOwnerId(e.target.value ? Number(e.target.value) : "")
              }
              className="w-full border border-slate-300 rounded-md px-3 py-1.5 text-sm bg-white"
            >
              <option value="">Select owner...</option>
              {owners.map((o) => (
                <option key={o.id} value={o.id}>
                  {personLabel(o)}
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
              <div className="text-xs text-slate-500">Total income</div>
              <div className="font-mono">
                {formatMoney(preview.total_income)}
              </div>
            </div>
            <div>
              <div className="text-xs text-slate-500">Total expense</div>
              <div className="font-mono">
                {formatMoney(preview.total_expense)}
              </div>
            </div>
            <div>
              <div className="text-xs text-slate-500">Required reserves</div>
              <div className="font-mono">{formatMoney(preview.total_required_reserves)}</div>
            </div>
            <div>
              <div className="text-xs text-slate-500">Prepaid rent</div>
              <div className="font-mono">{formatMoney(preview.total_prepaid_rent)}</div>
            </div>
            <div>
              <div className="text-xs text-slate-500">Available cash</div>
              <div className="font-mono">{formatMoney(preview.total_available_cash)}</div>
            </div>
            <div>
              <div className="text-xs text-slate-500">Net movement</div>
              <div className="font-mono">{formatMoney(preview.total_net)}</div>
            </div>
          </div>

          <div className="text-xs text-slate-500 mb-2">
            Per-property summary
          </div>
          <div className="border border-slate-200 rounded-md overflow-hidden mb-4">
            <table className="w-full text-sm">
              <thead className="bg-slate-50 text-slate-600">
                <tr>
                  <th className="text-left px-3 py-2 font-medium">
                    Property
                  </th>
                  <th className="text-right px-3 py-2 font-medium">
                    Beginning
                  </th>
                  <th className="text-right px-3 py-2 font-medium">Income</th>
                  <th className="text-right px-3 py-2 font-medium">Expense</th>
                  <th className="text-right px-3 py-2 font-medium">Ending</th>
                </tr>
              </thead>
              <tbody>
                {preview.properties.map((p) => (
                  <tr key={p.property_id} className="border-t border-slate-100">
                    <td className="px-3 py-2">{p.property_name}</td>
                    <td className="px-3 py-2 text-right font-mono">
                      {formatMoney(p.beginning_cash)}
                    </td>
                    <td className="px-3 py-2 text-right font-mono">
                      {formatMoney(p.income)}
                    </td>
                    <td className="px-3 py-2 text-right font-mono">
                      {formatMoney(p.expense)}
                    </td>
                    <td className="px-3 py-2 text-right font-mono">
                      {formatMoney(p.ending_cash)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="mb-4">
            <label className="block text-xs text-slate-600 mb-1">
              Notes (optional)
            </label>
            <input
              type="text"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              className="w-full border border-slate-300 rounded-md px-3 py-1.5 text-sm"
            />
          </div>

          <div className="flex justify-end">
            <button
              type="button"
              onClick={doGenerate}
              disabled={generating || !preview.can_generate}
              className="px-4 py-2 rounded-md bg-blue-600 text-white text-sm font-medium hover:bg-blue-700 disabled:opacity-50"
            >
              {generating ? "Generating..." : "Generate statement"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}