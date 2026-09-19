"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { apiGet, apiFetch } from "@/lib/api";

type OcrSettings = {
  provider: string;
  mindee_api_key: string;
  google_api_key: string;
  aws_access_key: string;
  aws_secret_key: string;
  aws_region: string;
  has_mindee_key: boolean;
  has_google_key: boolean;
  has_aws_key: boolean;
};

const PROVIDERS = [
  { value: "none", label: "Disabled (no auto-read)" },
  { value: "mindee", label: "Mindee" },
  { value: "google", label: "Google Cloud Vision" },
  { value: "aws", label: "AWS Textract" },
];

export default function OcrSettingsPage() {
  const [settings, setSettings] = useState<OcrSettings | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const [provider, setProvider] = useState("none");
  const [mindeeKey, setMindeeKey] = useState("");
  const [googleKey, setGoogleKey] = useState("");
  const [awsAccess, setAwsAccess] = useState("");
  const [awsSecret, setAwsSecret] = useState("");
  const [awsRegion, setAwsRegion] = useState("us-east-1");

  useEffect(() => {
    (async () => {
      try {
        const me = await apiGet("/auth/me");
        if (me.role !== "admin") {
          window.location.href = "/dashboard";
          return;
        }
        const data = await apiGet("/platform-settings/ocr");
        setSettings(data);
        setProvider(data.provider || "none");
        setAwsRegion(data.aws_region || "us-east-1");
      } catch (err) {
        setError(err instanceof Error ? err.message : "Load failed");
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError("");
    setMessage("");
    try {
      const body: Record<string, string> = { provider, aws_region: awsRegion };
      if (mindeeKey) body.mindee_api_key = mindeeKey;
      if (googleKey) body.google_api_key = googleKey;
      if (awsAccess) body.aws_access_key = awsAccess;
      if (awsSecret) body.aws_secret_key = awsSecret;

      const res = await apiFetch("/platform-settings/ocr", {
        method: "PUT",
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        const d = await res.json();
        throw new Error(d.detail || "Save failed");
      }
      setMessage("Settings saved.");
      setMindeeKey("");
      setGoogleKey("");
      setAwsAccess("");
      setAwsSecret("");

      const fresh = await apiGet("/platform-settings/ocr");
      setSettings(fresh);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed");
    } finally {
      setSaving(false);
    }
  }

  if (loading) return <div className="text-slate-500">Loading…</div>;

  return (
    <div className="max-w-2xl">
      <Link
        href="/dashboard"
        className="text-sm text-slate-500 hover:text-slate-900 mb-4 inline-block"
      >
        ← Back to dashboard
      </Link>

      <h1 className="text-2xl font-bold text-slate-900 mb-2">OCR Settings</h1>
      <p className="text-slate-500 mb-6">
        Configure the OCR provider used to read insurance documents.
        If disabled, uploads still work — users type fields manually.
      </p>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-lg px-4 py-3 mb-6">
          {error}
        </div>
      )}
      {message && (
        <div className="bg-green-50 border border-green-200 text-green-700 text-sm rounded-lg px-4 py-3 mb-6">
          {message}
        </div>
      )}

      <form onSubmit={handleSave} className="space-y-6">
        <div className="bg-white rounded-xl border border-slate-200 p-6 space-y-4">
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">
              OCR Provider
            </label>
            <select
              value={provider}
              onChange={(e) => setProvider(e.target.value)}
              className="input"
            >
              {PROVIDERS.map((p) => (
                <option key={p.value} value={p.value}>
                  {p.label}
                </option>
              ))}
            </select>
          </div>

          {provider === "mindee" && (
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">
                Mindee API Key
              </label>
              <input
                type="password"
                value={mindeeKey}
                onChange={(e) => setMindeeKey(e.target.value)}
                placeholder={
                  settings?.has_mindee_key
                    ? "(already set — leave blank to keep)"
                    : "Paste your Mindee API key"
                }
                className="input"
              />
              <p className="text-xs text-slate-500 mt-1">
                Get a key at mindee.com → API Keys
              </p>
            </div>
          )}

          {provider === "google" && (
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">
                Google Cloud Vision API Key
              </label>
              <input
                type="password"
                value={googleKey}
                onChange={(e) => setGoogleKey(e.target.value)}
                placeholder={
                  settings?.has_google_key
                    ? "(already set — leave blank to keep)"
                    : "Paste your Google API key"
                }
                className="input"
              />
              <p className="text-xs text-slate-500 mt-1">
                Google Cloud Console → APIs & Services → Credentials
              </p>
            </div>
          )}

          {provider === "aws" && (
            <>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">
                  AWS Access Key
                </label>
                <input
                  type="password"
                  value={awsAccess}
                  onChange={(e) => setAwsAccess(e.target.value)}
                  placeholder={settings?.has_aws_key ? "(already set)" : "AKIA..."}
                  className="input"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">
                  AWS Secret Key
                </label>
                <input
                  type="password"
                  value={awsSecret}
                  onChange={(e) => setAwsSecret(e.target.value)}
                  className="input"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">
                  Region
                </label>
                <input
                  type="text"
                  value={awsRegion}
                  onChange={(e) => setAwsRegion(e.target.value)}
                  className="input"
                />
              </div>
            </>
          )}
        </div>

        <button
          type="submit"
          disabled={saving}
          className="bg-slate-900 text-white px-6 py-2.5 rounded-lg font-medium hover:bg-slate-700 disabled:opacity-50"
        >
          {saving ? "Saving…" : "Save Settings"}
        </button>
      </form>
    </div>
  );
}