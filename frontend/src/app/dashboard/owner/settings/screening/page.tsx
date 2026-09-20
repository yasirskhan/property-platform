"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { apiGet, apiFetch } from "@/lib/api";

type Provider = {
  id: number;
  slug: string;
  name: string;
  description: string | null;
  pricing_info: string | null;
  api_docs_url: string | null;
  is_active: boolean;
};

type Settings = {
  id: number;
  organization_id: number;
  provider_slug: string | null;
  is_enabled: boolean;
  application_fee: string;
  fee_waived_for_managers: boolean;
  auto_screen_on_apply: boolean;
  account_id: string | null;
  has_api_key: boolean;
  has_api_secret: boolean;
};

export default function ScreeningSettingsPage() {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [orgId, setOrgId] = useState<number | null>(null);
  const [providers, setProviders] = useState<Provider[]>([]);
  const [settings, setSettings] = useState<Settings | null>(null);

  const [providerSlug, setProviderSlug] = useState("");
  const [isEnabled, setIsEnabled] = useState(false);
  const [applicationFee, setApplicationFee] = useState("0");
  const [feeWaived, setFeeWaived] = useState(false);
  const [autoScreen, setAutoScreen] = useState(false);
  const [accountId, setAccountId] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [apiSecret, setApiSecret] = useState("");

  useEffect(() => {
    (async () => {
      try {
        // Always try to fetch providers — even if org loading fails
        try {
          const provs = await apiGet("/screening-providers");
          setProviders(provs);
        } catch (e) {
          console.error("Could not load providers:", e);
        }

        const me = await apiGet("/auth/me");
        if (me.role !== "owner" && me.role !== "admin") {
          window.location.href = "/dashboard";
          return;
        }

        if (!me.organization_id) {
          setError(
            "Your account isn't linked to an organization yet. Contact support."
          );
          setLoading(false);
          return;
        }

        setOrgId(me.organization_id);

        try {
          const s: Settings = await apiGet(
            `/organizations/${me.organization_id}/screening-settings`
          );
          setSettings(s);
          setProviderSlug(s.provider_slug || "");
          setIsEnabled(s.is_enabled);
          setApplicationFee(s.application_fee?.toString() || "0");
          setFeeWaived(s.fee_waived_for_managers);
          setAutoScreen(s.auto_screen_on_apply);
          setAccountId(s.account_id || "");
        } catch {
          // No settings yet — use defaults
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : "Load failed");
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!orgId) {
      setError("Cannot save — no organization linked.");
      return;
    }
    setSaving(true);
    setError("");
    setMessage("");
    try {
      const body: Record<string, unknown> = {
        provider_slug: providerSlug || null,
        is_enabled: isEnabled,
        application_fee: Number(applicationFee),
        fee_waived_for_managers: feeWaived,
        auto_screen_on_apply: autoScreen,
        account_id: accountId || null,
      };
      if (apiKey) body.api_key = apiKey;
      if (apiSecret) body.api_secret = apiSecret;

      const res = await apiFetch(
        `/organizations/${orgId}/screening-settings`,
        {
          method: "PUT",
          body: JSON.stringify(body),
        }
      );
      if (!res.ok) {
        const d = await res.json();
        throw new Error(d.detail || "Save failed");
      }
      setMessage("Settings saved.");
      setApiKey("");
      setApiSecret("");

      const fresh = await apiGet(`/organizations/${orgId}/screening-settings`);
      setSettings(fresh);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed");
    } finally {
      setSaving(false);
    }
  }

  if (loading) return <div className="text-slate-500">Loading…</div>;

  return (
    <div className="max-w-3xl">
      <Link
        href="/dashboard"
        className="text-sm text-slate-500 hover:text-slate-900 mb-4 inline-block"
      >
        ← Back to dashboard
      </Link>

      <h1 className="text-2xl font-bold text-slate-900 mb-2">
        Tenant Screening
      </h1>
      <p className="text-slate-500 mb-6">
        Enable applicant screening for your properties. Choose a provider, set
        your application fee, and add credentials if required.
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

      {/* If no org, stop here and tell the user */}
      {!orgId && !error && (
        <div className="bg-amber-50 border border-amber-200 text-amber-800 text-sm rounded-lg px-4 py-3 mb-6">
          Your account isn&apos;t linked to an organization yet.
        </div>
      )}

      {orgId && (
        <form onSubmit={handleSubmit} className="space-y-6">
          <div className="bg-white rounded-xl border border-slate-200 p-6 space-y-4">
            <div className="flex items-center gap-3">
              <input
                type="checkbox"
                id="enabled"
                checked={isEnabled}
                onChange={(e) => setIsEnabled(e.target.checked)}
                className="w-4 h-4"
              />
              <label
                htmlFor="enabled"
                className="text-sm font-medium text-slate-700"
              >
                Enable tenant screening for my properties
              </label>
            </div>
            <p className="text-xs text-slate-500 pl-7">
              When enabled, applicants will be prompted to complete a screening
              during their application.
            </p>
          </div>

          {isEnabled && (
            <>
              <div className="bg-white rounded-xl border border-slate-200 p-6 space-y-4">
                <h2 className="font-semibold text-slate-900">
                  Screening Provider
                </h2>

                {providers.length === 0 ? (
                  <p className="text-sm text-slate-500">
                    No screening providers available. Ask your admin to seed the
                    provider catalog.
                  </p>
                ) : (
                  <div className="space-y-2">
                    {providers.map((p) => (
                      <label
                        key={p.slug}
                        className={`block border rounded-lg p-4 cursor-pointer transition ${
                          providerSlug === p.slug
                            ? "border-slate-900 bg-slate-50"
                            : "border-slate-200 hover:border-slate-400"
                        }`}
                      >
                        <div className="flex items-start gap-3">
                          <input
                            type="radio"
                            name="provider"
                            value={p.slug}
                            checked={providerSlug === p.slug}
                            onChange={(e) => setProviderSlug(e.target.value)}
                            className="mt-1"
                          />
                          <div className="flex-1">
                            <p className="font-medium text-slate-900">
                              {p.name}
                            </p>
                            {p.description && (
                              <p className="text-sm text-slate-600 mt-1">
                                {p.description}
                              </p>
                            )}
                            {p.pricing_info && (
                              <p className="text-xs text-slate-500 mt-1">
                                💰 {p.pricing_info}
                              </p>
                            )}
                          </div>
                        </div>
                      </label>
                    ))}
                  </div>
                )}
              </div>

              <div className="bg-white rounded-xl border border-slate-200 p-6 space-y-4">
                <h2 className="font-semibold text-slate-900">
                  Application Fee
                </h2>

                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">
                    Fee amount ($)
                  </label>
                  <input
                    type="number"
                    step="0.01"
                    min="0"
                    value={applicationFee}
                    onChange={(e) => setApplicationFee(e.target.value)}
                    className="input"
                  />
                  <p className="text-xs text-slate-500 mt-1">
                    Charged to applicants before screening runs. Set to 0 for
                    free applications.
                  </p>
                </div>

                <div className="flex items-center gap-3">
                  <input
                    type="checkbox"
                    id="waive"
                    checked={feeWaived}
                    onChange={(e) => setFeeWaived(e.target.checked)}
                    className="w-4 h-4"
                  />
                  <label htmlFor="waive" className="text-sm text-slate-700">
                    Waive fee when a manager submits on the applicant&apos;s
                    behalf
                  </label>
                </div>

                <div className="flex items-center gap-3">
                  <input
                    type="checkbox"
                    id="auto"
                    checked={autoScreen}
                    onChange={(e) => setAutoScreen(e.target.checked)}
                    className="w-4 h-4"
                  />
                  <label htmlFor="auto" className="text-sm text-slate-700">
                    Run screening automatically after payment
                  </label>
                </div>
              </div>

              <div className="bg-white rounded-xl border border-slate-200 p-6 space-y-4">
                <h2 className="font-semibold text-slate-900">
                  Provider Credentials (optional)
                </h2>
                <p className="text-xs text-slate-500">
                  Enter your provider account credentials. These are encrypted
                  and never shown after saving.
                </p>

                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">
                    Account ID
                  </label>
                  <input
                    type="text"
                    value={accountId}
                    onChange={(e) => setAccountId(e.target.value)}
                    placeholder={
                      settings?.account_id
                        ? "(already set)"
                        : "Your provider account ID"
                    }
                    className="input"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">
                    API Key
                  </label>
                  <input
                    type="password"
                    value={apiKey}
                    onChange={(e) => setApiKey(e.target.value)}
                    placeholder={
                      settings?.has_api_key
                        ? "(already set — leave blank to keep)"
                        : "Paste your API key"
                    }
                    className="input"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">
                    API Secret
                  </label>
                  <input
                    type="password"
                    value={apiSecret}
                    onChange={(e) => setApiSecret(e.target.value)}
                    placeholder={
                      settings?.has_api_secret
                        ? "(already set — leave blank to keep)"
                        : "Paste your API secret"
                    }
                    className="input"
                  />
                </div>
              </div>
            </>
          )}

          <button
            type="submit"
            disabled={saving}
            className="bg-slate-900 text-white px-6 py-2.5 rounded-lg font-medium hover:bg-slate-700 disabled:opacity-50"
          >
            {saving ? "Saving…" : "Save Settings"}
          </button>
        </form>
      )}
    </div>
  );
}