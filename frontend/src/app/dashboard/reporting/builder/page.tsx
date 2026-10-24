"use client";

import { useEffect, useState } from "react";
import SavedReportBuilder from "@/components/reporting/SavedReportBuilder";
import { getReportCatalog, ReportCatalog } from "@/lib/reporting";

export default function CustomReportsPage() {
  const [catalog, setCatalog] = useState<ReportCatalog | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    getReportCatalog()
      .then(setCatalog)
      .catch((cause) =>
        setError(cause instanceof Error ? cause.message : "Unable to load reports.")
      )
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="text-slate-500">Loading custom reports…</div>;
  if (error) return <div className="text-red-600">{error}</div>;
  if (!catalog) return null;

  return (
    <div className="space-y-5">
      <header>
        <h1 className="text-2xl font-bold text-slate-900">Custom Reports</h1>
        <p className="mt-1 text-sm text-slate-500">
          Save private report configurations using the existing report catalog and permissions.
        </p>
      </header>
      <SavedReportBuilder catalog={catalog} />
    </div>
  );
}
