"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";

import {
  getReportCatalog,
  ReportCatalog,
  ReportDefinition,
  ReportTier,
} from "@/lib/reporting";

const TABS: { key: ReportTier; label: string }[] = [
  { key: "STANDARD", label: "Standard Reports" },
  { key: "ENHANCED", label: "Enhanced Reports" },
];

export default function ReportingPage() {
  const [catalog, setCatalog] = useState<ReportCatalog | null>(null);
  const [tier, setTier] = useState<ReportTier>("STANDARD");
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    getReportCatalog()
      .then(setCatalog)
      .catch((err) => setError(err instanceof Error ? err.message : "Unable to load reports."))
      .finally(() => setLoading(false));
  }, []);

  const items = useMemo(() => {
    if (!catalog) return [];
    const source = tier === "STANDARD" ? catalog.standard : catalog.enhanced;
    const q = search.trim().toLowerCase();
    if (!q) return source;
    return source.filter(
      (item) =>
        item.title.toLowerCase().includes(q) ||
        item.category.toLowerCase().includes(q)
    );
  }, [catalog, search, tier]);

  const groups = useMemo(() => {
    const result = new Map<string, ReportDefinition[]>();
    for (const item of items) {
      const group = result.get(item.category) || [];
      group.push(item);
      result.set(item.category, group);
    }
    return Array.from(result.entries());
  }, [items]);

  if (loading) return <div className="text-slate-500">Loading reports…</div>;
  if (error) return <div className="text-red-600">{error}</div>;
  if (!catalog) return null;

  return (
    <div>
      <div className="flex flex-wrap items-start justify-between gap-4 mb-6">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Reports</h1>
          <p className="text-sm text-slate-500 mt-1">
            Accounting basis: <span className="font-medium text-slate-700">{catalog.accounting_basis}</span>
          </p>
        </div>
        <input
          aria-label="Search reports"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          placeholder="Search reports"
          className="w-72 max-w-full px-3 py-2 border border-slate-300 rounded-lg text-sm"
        />
      </div>

      <div className="border-b border-slate-200 mb-6">
        <nav className="flex gap-1" aria-label="Report tiers">
          {TABS.map((tab) => (
            <button
              key={tab.key}
              type="button"
              onClick={() => setTier(tab.key)}
              className={`px-4 py-2 text-sm font-medium border-b-2 ${
                tier === tab.key
                  ? "border-slate-900 text-slate-900"
                  : "border-transparent text-slate-500 hover:text-slate-900"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </nav>
      </div>

      {groups.length === 0 ? (
        <div className="border border-slate-200 bg-white rounded-xl p-10 text-center text-slate-500">
          No reports match your search.
        </div>
      ) : (
        <div className="space-y-7">
          {groups.map(([category, reports]) => (
            <section key={category}>
              <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500 mb-3">
                {category}
              </h2>
              <div className={tier === "STANDARD" ? "flex flex-wrap gap-2" : "grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3"}>
                {reports.map((report) => (
                  <ReportControl key={report.key} report={report} />
                ))}
              </div>
            </section>
          ))}
        </div>
      )}
    </div>
  );
}

function ReportControl({ report }: { report: ReportDefinition }) {
  const common =
    report.presentation === "BUTTON"
      ? "inline-flex items-center rounded-lg border px-3 py-2 text-sm"
      : "block rounded-xl border p-4 text-left";

  if (!report.available || !report.href) {
    return (
      <div
        className={`${common} border-slate-200 bg-slate-50 text-slate-400`}
        aria-disabled="true"
        title="Scheduled in Phase 3.7"
      >
        <div>
          <div className="font-medium">{report.title}</div>
          {report.presentation === "TAB" && (
            <div className="text-xs mt-1">Scheduled in Phase 3.7</div>
          )}
        </div>
      </div>
    );
  }

  return (
    <Link
      href={report.href}
      className={`${common} border-slate-300 bg-white text-slate-800 hover:border-slate-500 hover:bg-slate-50`}
    >
      <div>
        <div className="font-medium">{report.title}</div>
        {report.description && report.presentation === "TAB" && (
          <div className="text-xs text-slate-500 mt-1">{report.description}</div>
        )}
      </div>
    </Link>
  );
}
