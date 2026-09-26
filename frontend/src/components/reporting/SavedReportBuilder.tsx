"use client";

import { useEffect, useMemo, useState } from "react";

import ReportActions from "@/components/reporting/ReportActions";
import {
  createSavedReport,
  deleteSavedReport,
  getSavedReports,
  updateSavedReport,
  type ReportCatalog,
  type SavedReport,
  type SavedReportParameters,
} from "@/lib/reporting";

const SUPPORTED = new Set([
  "accounting.chart_of_accounts",
  "accounting.trial_balance",
  "accounting.general_ledger",
  "owner.statement",
]);

const PARAM_FIELDS: Record<string, { key: string; label: string; type: "checkbox" | "date" | "number"; required?: boolean }[]> = {
  "accounting.chart_of_accounts": [
    { key: "include_inactive", label: "Include inactive accounts", type: "checkbox" },
  ],
  "accounting.trial_balance": [
    { key: "as_of", label: "As of", type: "date" },
    { key: "include_zero", label: "Include zero balances", type: "checkbox" },
  ],
  "accounting.general_ledger": [
    { key: "account_id", label: "GL account ID", type: "number", required: true },
    { key: "date_from", label: "From date", type: "date" },
    { key: "date_to", label: "To date", type: "date" },
    { key: "property_id", label: "Property ID (optional)", type: "number" },
  ],
  "owner.statement": [
    { key: "statement_id", label: "Frozen owner statement ID", type: "number", required: true },
  ],
};

export default function SavedReportBuilder({ catalog }: { catalog: ReportCatalog }) {
  const available = useMemo(
    () => [...catalog.standard, ...catalog.enhanced].filter((report) => SUPPORTED.has(report.key)),
    [catalog]
  );
  const [items, setItems] = useState<SavedReport[]>([]);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState<number | null>(null);
  const [name, setName] = useState("");
  const [reportKey, setReportKey] = useState("accounting.chart_of_accounts");
  const [parameters, setParameters] = useState<SavedReportParameters>({});
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");

  useEffect(() => {
    getSavedReports()
      .then(({ items: rows }) => setItems(rows))
      .catch((error) => setMessage(error instanceof Error ? error.message : "Cannot load saved reports."))
      .finally(() => setLoading(false));
  }, []);

  function clearForm() {
    setEditing(null);
    setName("");
    setReportKey("accounting.chart_of_accounts");
    setParameters({});
  }

  function edit(item: SavedReport) {
    setEditing(item.id);
    setName(item.name);
    setReportKey(item.report_key);
    setParameters({ ...item.parameters });
    setMessage("");
  }

  async function save(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setMessage("");
    try {
      const payload = { name: name.trim(), report_key: reportKey, parameters };
      if (editing === null) {
        const result = await createSavedReport(payload);
        setItems((previous) => [result, ...previous]);
      } else {
        const result = await updateSavedReport(editing, payload);
        setItems((previous) => previous.map((item) => item.id === result.id ? result : item));
      }
      clearForm();
      setMessage("Saved configuration updated.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Cannot save report.");
    } finally {
      setBusy(false);
    }
  }

  async function remove(id: number) {
    if (!window.confirm("Delete this saved report configuration?")) return;
    setBusy(true);
    setMessage("");
    try {
      await deleteSavedReport(id);
      setItems((previous) => previous.filter((item) => item.id !== id));
      if (editing === id) clearForm();
      setMessage("Saved report deleted.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Cannot delete report.");
    } finally {
      setBusy(false);
    }
  }

  const titleFor = (key: string) => available.find((item) => item.key === key)?.title || key;

  return (
    <section className="mb-6 rounded-xl border border-slate-200 bg-white p-4">
      <h2 className="text-lg font-semibold text-slate-900">Custom report builder</h2>
      <p className="mt-1 text-sm text-slate-500">
        Save private configurations for available reports. Exports use live permissions and server-generated data.
      </p>
      <form onSubmit={save} className="mt-4 space-y-3">
        <div className="grid gap-3 md:grid-cols-2">
          <label className="block text-sm font-medium text-slate-700">
            Configuration name
            <input
              required maxLength={100} value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder="Month-end review"
              className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2"
            />
          </label>
          <label className="block text-sm font-medium text-slate-700">
            Report
            <select
              value={reportKey}
              onChange={(event) => { setReportKey(event.target.value); setParameters({}); }}
              className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2"
            >
              {available.map((report) => <option key={report.key} value={report.key}>{report.title}</option>)}
            </select>
          </label>
        </div>
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          {(PARAM_FIELDS[reportKey] || []).map((field) => (
            <label key={field.key} className="block text-sm font-medium text-slate-700">
              {field.type === "checkbox" ? (
                <span className="flex items-center gap-2 pt-2">
                  <input type="checkbox" checked={parameters[field.key] === true}
                    onChange={(event) => setParameters((previous) => ({ ...previous, [field.key]: event.target.checked }))} />
                  {field.label}
                </span>
              ) : (
                <>
                  {field.label}
                  <input
                    type={field.type} min={field.type === "number" ? 1 : undefined}
                    required={field.required} value={String(parameters[field.key] ?? "")}
                    onChange={(event) => setParameters((previous) => ({ ...previous, [field.key]: event.target.value }))}
                    className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2"
                  />
                </>
              )}
            </label>
          ))}
        </div>
        <div className="flex flex-wrap gap-2">
          <button disabled={busy || !name.trim()} type="submit"
            className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50">
            {busy ? "Saving…" : editing === null ? "Save configuration" : "Update configuration"}
          </button>
          {editing !== null && (
            <button type="button" onClick={clearForm} className="rounded-lg border px-4 py-2 text-sm">Cancel edit</button>
          )}
        </div>
      </form>
      {message && <p role="status" className="mt-3 text-sm text-slate-600">{message}</p>}
      <div className="mt-5 border-t border-slate-200 pt-4">
        <h3 className="text-sm font-semibold text-slate-700">My saved reports</h3>
        {loading && <p className="mt-2 text-sm text-slate-500">Loading saved reports…</p>}
        {!loading && items.length === 0 && <p className="mt-2 text-sm text-slate-500">No saved configurations yet.</p>}
        <div className="mt-2 space-y-3">
          {items.map((item) => (
            <div key={item.id} className="flex flex-wrap items-center justify-between gap-3 rounded-lg border p-3">
              <div className="min-w-0">
                <div className="font-medium text-slate-900">{item.name}</div>
                <div className="text-xs text-slate-500">{titleFor(item.report_key)}</div>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <ReportActions reportKey={item.report_key} parameters={item.parameters} />
                <button type="button" disabled={busy} onClick={() => edit(item)}
                  className="rounded-md border px-3 py-1.5 text-sm disabled:opacity-50">Edit</button>
                <button type="button" disabled={busy} onClick={() => remove(item.id)}
                  className="rounded-md border px-3 py-1.5 text-sm text-red-700 disabled:opacity-50">Delete</button>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
