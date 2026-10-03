"use client";

import { useState } from "react";

import Flag from "@/components/features/Flag";
import { apiFetch, apiPost } from "@/lib/api";

type Parameter = string | number | boolean | null | undefined;

type Props = {
  reportKey: string;
  parameters?: Record<string, Parameter>;
  className?: string;
};

function cleanParameters(parameters: Record<string, Parameter>) {
  return Object.fromEntries(
    Object.entries(parameters).filter(([, value]) => value !== undefined && value !== null && value !== "")
  ) as Record<string, string | number | boolean>;
}

export default function ReportActions({ reportKey, parameters = {}, className = "" }: Props) {
  const [emailOpen, setEmailOpen] = useState(false);
  const [recipient, setRecipient] = useState("");
  const [busy, setBusy] = useState<"csv" | "email" | null>(null);
  const [message, setMessage] = useState("");
  const clean = cleanParameters(parameters);

  async function downloadCsv() {
    setBusy("csv");
    setMessage("");
    try {
      const query = new URLSearchParams();
      for (const [key, value] of Object.entries(clean)) query.set(key, String(value));
      const suffix = query.size ? `?${query.toString()}` : "";
      const response = await apiFetch(
        `/api/reporting/${encodeURIComponent(reportKey)}/export.csv${suffix}`,
        { method: "GET", headers: { Accept: "text/csv" } }
      );
      if (!response.ok) throw new Error(`CSV export failed (${response.status})`);
      const blob = await response.blob();
      const disposition = response.headers.get("content-disposition") || "";
      const filename = disposition.match(/filename="([^"]+)"/)?.[1] || "report.csv";
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = filename;
      link.click();
      URL.revokeObjectURL(url);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "CSV export failed.");
    } finally {
      setBusy(null);
    }
  }

  async function emailReport() {
    if (!recipient.trim()) return;
    setBusy("email");
    setMessage("");
    try {
      await apiPost(`/api/reporting/${encodeURIComponent(reportKey)}/email`, {
        recipient: recipient.trim(),
        parameters: clean,
      });
      setMessage("Report emailed.");
      setRecipient("");
      setEmailOpen(false);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Email failed.");
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className={`print:hidden ${className}`}>
      <div className="flex flex-wrap items-center gap-2">
        <button
          type="button"
          onClick={() => window.print()}
          className="px-3 py-1.5 rounded-md border border-slate-300 bg-white text-slate-700 text-sm hover:bg-slate-50"
        >
          Print
        </button>
        <Flag name="release.reporting.export">
          <button
            type="button"
            onClick={downloadCsv}
            disabled={busy !== null}
            className="px-3 py-1.5 rounded-md border border-slate-300 bg-white text-slate-700 text-sm hover:bg-slate-50 disabled:opacity-60"
          >
            {busy === "csv" ? "Exporting…" : "CSV"}
          </button>
          <button
            type="button"
            onClick={() => setEmailOpen((value) => !value)}
            disabled={busy !== null}
            className="px-3 py-1.5 rounded-md border border-slate-300 bg-white text-slate-700 text-sm hover:bg-slate-50 disabled:opacity-60"
          >
            Email
          </button>
        </Flag>
      </div>
      {emailOpen && (
        <div className="mt-2 flex flex-wrap items-center gap-2">
          <input
            type="email"
            aria-label="Email report to"
            value={recipient}
            onChange={(event) => setRecipient(event.target.value)}
            placeholder="recipient@example.com"
            className="w-64 max-w-full px-3 py-1.5 rounded-md border border-slate-300 text-sm"
          />
          <button
            type="button"
            onClick={emailReport}
            disabled={busy !== null || !recipient.trim()}
            className="px-3 py-1.5 rounded-md bg-slate-900 text-white text-sm disabled:opacity-60"
          >
            {busy === "email" ? "Sending…" : "Send"}
          </button>
        </div>
      )}
      {message && <div className="mt-2 text-xs text-slate-600">{message}</div>}
    </div>
  );
}
