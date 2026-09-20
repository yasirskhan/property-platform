// ============================================================
// Diagnostics Page
// ------------------------------------------------------------
// Route: /dashboard/accounting/diagnostics
//
// Runs the six financial health checks and displays them.
// Each check is a card: green check (pass) or red X (fail).
// Failed cards show a details list. A summary banner at the
// top says how many passed.
//
// Read-only report — it never posts anything.
// ============================================================

"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  getDiagnostics,
  DiagnosticsReport,
  DiagnosticCheck,
} from "@/lib/diagnostics";

export default function DiagnosticsPage() {
  const [data, setData] = useState<DiagnosticsReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [runAt, setRunAt] = useState<string>("");

  async function load() {
    setLoading(true);
    setError("");
    try {
      const report = await getDiagnostics();
      setData(report);
      setRunAt(new Date().toLocaleString());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Load failed");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (loading && !data) return <div className="text-slate-500">Loading…</div>;
  if (error) return <div className="text-red-600">{error}</div>;
  if (!data) return null;

  const allOk = data.all_passed;

  return (
    <div className="max-w-4xl">
      {/* Back link */}
      <div className="mb-4">
        <Link
          href="/dashboard"
          className="text-sm text-slate-500 hover:text-slate-800"
        >
          ← Back to Dashboard
        </Link>
      </div>

      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Diagnostics</h1>
          <p className="text-slate-500 mt-1 text-sm">
            Financial health checks for your trust accounting.
            {runAt && ` Last run: ${runAt}.`}
          </p>
        </div>
        <button
          onClick={load}
          disabled={loading}
          className="text-sm px-4 py-2 bg-slate-900 text-white rounded-lg hover:bg-slate-700 disabled:opacity-50"
        >
          {loading ? "Running…" : "Run again"}
        </button>
      </div>

      {/* Summary banner */}
      <div
        className={`mb-6 px-5 py-4 rounded-xl border ${
          allOk
            ? "bg-green-50 border-green-200 text-green-800"
            : "bg-yellow-50 border-yellow-200 text-yellow-900"
        }`}
      >
        <div className="flex items-center gap-2">
          <span className="text-2xl leading-none">
            {allOk ? "✓" : "!"}
          </span>
          <div>
            <div className="font-semibold">
              {data.passed_count} of {data.checks.length} checks passed
            </div>
            {!allOk && (
              <div className="text-sm opacity-80">
                {data.error_count} error{data.error_count === 1 ? "" : "s"}
                {", "}
                {data.warning_count} warning
                {data.warning_count === 1 ? "" : "s"}.
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Checks */}
      <div className="space-y-4">
        {data.checks.map((check) => (
          <CheckCard key={check.key} check={check} />
        ))}
      </div>
    </div>
  );
}

// ------------------------------------------------------------
// One diagnostic card
// ------------------------------------------------------------
function CheckCard({ check }: { check: DiagnosticCheck }) {
  const border =
    check.severity === "error"
      ? "border-red-200"
      : check.severity === "warning"
      ? "border-yellow-200"
      : "border-slate-200";

  const bg =
    check.severity === "error"
      ? "bg-red-50/30"
      : check.severity === "warning"
      ? "bg-yellow-50/30"
      : "bg-white";

  const iconBg =
    check.severity === "error"
      ? "bg-red-100 text-red-700"
      : check.severity === "warning"
      ? "bg-yellow-100 text-yellow-800"
      : "bg-green-100 text-green-700";

  const icon =
    check.severity === "error"
      ? "✕"
      : check.severity === "warning"
      ? "!"
      : "✓";

  return (
    <div className={`border ${border} ${bg} rounded-xl overflow-hidden`}>
      <div className="flex items-start gap-3 px-5 py-4">
        <div
          className={`flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center font-semibold ${iconBg}`}
        >
          {icon}
        </div>
        <div className="flex-1 min-w-0">
          <div className="font-semibold text-slate-900">{check.label}</div>
          <div className="text-sm text-slate-600 mt-1 whitespace-pre-wrap">
            {check.message}
          </div>

          {check.details.length > 0 && (
            <div className="mt-3 bg-white/60 border border-slate-200 rounded p-3 text-xs">
              <table className="w-full">
                <tbody>
                  {check.details.map((d, i) => (
                    <tr key={i} className="border-b border-slate-100 last:border-0">
                      {Object.entries(d).map(([k, v]) => (
                        <td key={k} className="py-1 pr-4 align-top">
                          <span className="text-slate-400">
                            {k.replace(/_/g, " ")}:
                          </span>{" "}
                          <span className="text-slate-700 font-mono">
                            {v === null || v === undefined ? "—" : String(v)}
                          </span>
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}