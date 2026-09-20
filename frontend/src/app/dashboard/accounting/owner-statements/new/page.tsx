// ============================================================
// Generate Owner Statement page
// ------------------------------------------------------------
// Route: /dashboard/accounting/owner-statements/new
//
// Pick owner + period → Preview → Generate.
// Preview is read-only; Generate freezes the snapshot.
// ============================================================

"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import {
  previewOwnerStatement,
  generateOwnerStatement,
  StatementPreview,
} from "@/lib/ownerStatements";
import { apiGet } from "@/lib/api";

type Person = {
  id: number;
  full_name?: string;
  email?: string;
  role?: string;
};

export default function NewOwnerStatementPage() {
  const router = useRouter();

  const [owners, setOwners] = useState<Person[]>([]);
  const [ownerId, setOwnerId] = useState<number | "">("");
  const [periodStart, setPeriodStart] = useState("");
  const [periodEnd, setPeriodEnd] = useState(
    new Date().toISOString().slice(0, 10)
  );
  const [notes, setNotes] = useState("");

  const [preview, setPreview] = useState<StatementPreview | null>(null);
  const [previewing, setPreviewing] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState("");

  // Load owners + default period
  useEffect(() => {
    (async () => {
      try {
        const usersRaw = (await apiGet("/users")) as unknown;
        const list: Person[] = Array.isArray(usersRaw)
          ? (usersRaw as Person[])
          : (((usersRaw as { items?: Person[] })?.items ?? []) as Person[]);
        setOwners(
          list.filter((p) => (p.role || "").toUpperCase() === "OWNER")
        );

        const now = new Date();
        const firstOfMonth = new Date(now.getFullYear(), now.getMonth(), 1);
        setPeriodStart(firstOfMonth.toISOString().slice(0, 10));
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load");
      }
    })();
  }, []);

  function personLabel(p: Person): string {
    if (p.full_name) return p.full_name;
    return p.email || `#${p.id}`;
  }

  async function handlePreview() {
    setError("");
    setPreview(null);
    if (!ownerId) {
      setError("Pick an owner.");
      return;
    }
    if (!periodStart || !periodEnd) {
      setError("Pick a period.");
      return;
    }

    setPreviewing(true);
    try {
      const p = await previewOwnerStatement({
        owner_id: Number(ownerId),
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

  async function handleGenerate() {
    setError("");
    if (!preview || !preview.can_generate) {
      setError("Preview first, or the preview says it can't be generated.");
      return;
    }

    setGenerating(true);
    try {
      const stmt = await generateOwnerStatement({
        owner_id: Number(ownerId),
        period_start: periodStart,
        period_end: periodEnd,
        notes: notes || null,
      });
      router.push(`/dashboard/accounting/owner-statements/${stmt.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Generate failed");
    } finally {
      setGenerating(false);
    }
  }

  return (
    <div className="max-w-4xl">
      <div className="mb-6">
        <Link
          href="/dashboard/accounting/owner-statements"
          className="text-sm text-slate-500 hover:text-slate-800"
        >
          ← Back to Owner Statements
        </Link>
        <h1 className="text-2xl font-bold text-slate-900 mt-2">
          Generate Owner Statement
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
          <label className="block text-xs text-slate-500 mb-1">Owner *</label>
          <select
            required
            value={ownerId}
            onChange={(e) => {
              setOwnerId(e.target.value ? Number(e.target.value) : "");
              setPreview(null);
            }}
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
            disabled={previewing || !ownerId || !periodStart || !periodEnd}
            className="text-sm px-4 py-2 bg-slate-100 hover:bg-slate-200 rounded disabled:opacity-50"
          >
            {previewing ? "Calculating…" : "Preview statement"}
          </button>
        </div>
      </div>

      {/* Preview */}
      {preview && (
        <div className="bg-white border border-slate-200 rounded-xl p-5 mb-6 space-y-4">
          <div className="text-sm font-semibold text-slate-700">
            Preview — {preview.owner_name || preview.owner_email}
          </div>

          {!preview.can_generate && (
            <div className="px-3 py-2 bg-yellow-50 border border-yellow-200 text-yellow-800 rounded text-sm">
              {preview.reason || "This statement cannot be generated."}
            </div>
          )}

          {/* Totals */}
          <div className="grid grid-cols-3 gap-4 text-sm">
            <div>
              <div className="text-xs text-slate-500">Total income</div>
              <div className="font-mono">
                {Number(preview.total_income).toLocaleString("en-US", {
                  style: "currency",
                  currency: "USD",
                })}
              </div>
            </div>
            <div>
              <div className="text-xs text-slate-500">Total expense</div>
              <div className="font-mono">
                {Number(preview.total_expense).toLocaleString("en-US", {
                  style: "currency",
                  currency: "USD",
                })}
              </div>
            </div>
            <div>
              <div className="text-xs text-slate-500">Net</div>
              <div className="font-mono font-semibold">
                {Number(preview.total_net).toLocaleString("en-US", {
                  style: "currency",
                  currency: "USD",
                })}
              </div>
            </div>
          </div>

          {/* Per-property blocks */}
          <div className="border-t border-slate-200 pt-3 space-y-4">
            {preview.properties.length === 0 && (
              <div className="text-slate-500 text-sm">
                This owner has no properties with activity in the period.
              </div>
            )}
            {preview.properties.map((p) => (
              <div
                key={p.property_id}
                className="border border-slate-200 rounded p-3"
              >
                <div className="flex items-center justify-between mb-2">
                  <div className="font-semibold text-slate-800">
                    {p.property_name}
                  </div>
                  <div className="text-xs text-slate-500">
                    {p.ownership_pct}% ownership
                  </div>
                </div>
                <div className="grid grid-cols-4 gap-2 text-xs">
                  <div>
                    <div className="text-slate-500">Beginning</div>
                    <div className="font-mono">
                      {Number(p.beginning_cash).toLocaleString("en-US", {
                        style: "currency",
                        currency: "USD",
                      })}
                    </div>
                  </div>
                  <div>
                    <div className="text-slate-500">Income</div>
                    <div className="font-mono text-green-700">
                      {Number(p.income).toLocaleString("en-US", {
                        style: "currency",
                        currency: "USD",
                      })}
                    </div>
                  </div>
                  <div>
                    <div className="text-slate-500">Expense</div>
                    <div className="font-mono text-red-700">
                      {Number(p.expense).toLocaleString("en-US", {
                        style: "currency",
                        currency: "USD",
                      })}
                    </div>
                  </div>
                  <div>
                    <div className="text-slate-500">Ending</div>
                    <div className="font-mono font-semibold">
                      {Number(p.ending_cash).toLocaleString("en-US", {
                        style: "currency",
                        currency: "USD",
                      })}
                    </div>
                  </div>
                </div>
                <div className="text-xs text-slate-500 mt-2">
                  {p.transactions.length} transaction(s)
                </div>
              </div>
            ))}
          </div>

          {/* Actions */}
          <div className="flex items-center gap-3 pt-3 border-t border-slate-200">
            <button
              type="button"
              onClick={handleGenerate}
              disabled={generating || !preview.can_generate}
              className="text-sm px-5 py-2.5 bg-slate-900 text-white rounded-lg hover:bg-slate-700 disabled:opacity-50"
            >
              {generating ? "Generating…" : "Generate Statement"}
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