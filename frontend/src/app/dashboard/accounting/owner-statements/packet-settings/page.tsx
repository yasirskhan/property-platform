"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  getOwnerPacketSettings,
  updateOwnerPacketSettings,
  type OwnerPacketReport,
} from "@/lib/ownerStatements";

const REPORTS: Array<{ key: OwnerPacketReport; label: string; detail: string }> = [
  {
    key: "OWNER_STATEMENT",
    label: "Owner Statement",
    detail: "Include the frozen owner statement for the selected period.",
  },
  {
    key: "PROPERTY_CASH_SUMMARY",
    label: "Property Cash Summary",
    detail: "Include ending cash, required reserves, prepaid rent, and available cash.",
  },
];

export default function OwnerPacketSettingsPage() {
  const [included, setIncluded] = useState<OwnerPacketReport[]>([]);
  const [emailOwner, setEmailOwner] = useState(false);
  const [coverMessage, setCoverMessage] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    getOwnerPacketSettings()
      .then((data) => {
        setIncluded(data.included_reports);
        setEmailOwner(data.email_owner);
        setCoverMessage(data.cover_message || "");
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Could not load settings."))
      .finally(() => setLoading(false));
  }, []);

  function toggle(report: OwnerPacketReport) {
    setIncluded((current) =>
      current.includes(report)
        ? current.filter((item) => item !== report)
        : [...current, report]
    );
  }

  async function save() {
    if (included.length === 0) {
      setError("Select at least one report.");
      return;
    }
    setSaving(true);
    setError("");
    setMessage("");
    try {
      const data = await updateOwnerPacketSettings({
        included_reports: included,
        email_owner: emailOwner,
        cover_message: coverMessage.trim() || null,
      });
      setIncluded(data.included_reports);
      setEmailOwner(data.email_owner);
      setCoverMessage(data.cover_message || "");
      setMessage("Owner packet settings saved.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save settings.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="p-6 max-w-3xl">
      <Link href="/dashboard/accounting/owner-statements" className="text-sm text-slate-500 hover:text-slate-900">
        ← Back to Owner Statements
      </Link>
      <Link href="/dashboard/accounting/owner-statements/packets" className="ml-4 text-sm text-blue-600 hover:underline">Prepare an owner packet</Link>
      <h1 className="text-xl font-semibold text-slate-900 mt-4">Owner Packet Customizer</h1>
      <p className="text-sm text-slate-500 mt-1 mb-6">
        Choose the frozen CSV reports and cover message included when you preview and send an owner packet.
      </p>

      {loading ? (
        <p className="text-sm text-slate-500">Loading…</p>
      ) : (
        <div className="space-y-5">
          <section className="bg-white border border-slate-200 rounded-lg p-5">
            <h2 className="font-medium text-slate-900 mb-3">Reports to include</h2>
            <div className="space-y-3">
              {REPORTS.map((report) => (
                <label key={report.key} className="flex gap-3 items-start">
                  <input
                    type="checkbox"
                    checked={included.includes(report.key)}
                    onChange={() => toggle(report.key)}
                    className="mt-1"
                  />
                  <span>
                    <span className="block text-sm font-medium text-slate-800">{report.label}</span>
                    <span className="block text-xs text-slate-500">{report.detail}</span>
                  </span>
                </label>
              ))}
            </div>
          </section>

          <section className="bg-white border border-slate-200 rounded-lg p-5">
            <label className="flex gap-3 items-start">
              <input
                type="checkbox"
                checked={emailOwner}
                onChange={(e) => setEmailOwner(e.target.checked)}
                className="mt-1"
              />
              <span>
                <span className="block text-sm font-medium text-slate-800">Allow reviewed owner-packet email delivery</span>
                <span className="block text-xs text-slate-500">
                  Delivery still requires a separate owner-specific preview and explicit recipient and content confirmations.
                </span>
              </span>
            </label>
          </section>

          <section className="bg-white border border-slate-200 rounded-lg p-5">
            <label className="block text-sm font-medium text-slate-800 mb-2">Cover message</label>
            <textarea
              value={coverMessage}
              onChange={(e) => setCoverMessage(e.target.value)}
              maxLength={2000}
              rows={5}
              className="w-full border border-slate-300 rounded-md px-3 py-2 text-sm"
              placeholder="Optional message shown on the owner packet cover."
            />
            <p className="text-xs text-slate-400 mt-1">{coverMessage.length}/2000</p>
          </section>

          {error && <div className="text-sm text-red-700 bg-red-50 border border-red-200 rounded-md px-3 py-2">{error}</div>}
          {message && <div className="text-sm text-green-700 bg-green-50 border border-green-200 rounded-md px-3 py-2">{message}</div>}

          <button
            type="button"
            onClick={save}
            disabled={saving || included.length === 0}
            className="px-4 py-2 rounded-md bg-blue-600 text-white text-sm font-medium hover:bg-blue-700 disabled:opacity-50"
          >
            {saving ? "Saving…" : "Save Owner Packet Settings"}
          </button>
        </div>
      )}
    </div>
  );
}
