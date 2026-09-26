"use client";

import { useEffect, useState } from "react";
import { SlidersHorizontal } from "lucide-react";

import { apiGet, apiPut } from "@/lib/api";
import { useFeatureContext } from "@/contexts/FeatureContext";

type FeatureSetting = {
  key: string;
  label: string;
  allowed: boolean;
  release_allowed: boolean;
  entitlement_allowed: boolean;
  org_config_allowed: boolean;
  permission_allowed: boolean;
  org_configurable: boolean;
  enabled: boolean;
};

type FeatureSettingsPayload = {
  items: FeatureSetting[];
};

export default function FeaturesSettingsPage() {
  const { refresh: refreshFlags } = useFeatureContext();
  const [items, setItems] = useState<FeatureSetting[]>([]);
  const [loading, setLoading] = useState(true);
  const [savingKey, setSavingKey] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const payload = (await apiGet(
        "/api/features/settings"
      )) as FeatureSettingsPayload;
      setItems(payload.items || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load features.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, []);

  async function setEnabled(item: FeatureSetting, enabled: boolean) {
    setSavingKey(item.key);
    setError(null);
    setItems((current) =>
      current.map((row) =>
        row.key === item.key ? { ...row, enabled } : row
      )
    );
    try {
      const updated = (await apiPut(
        `/api/features/settings/${encodeURIComponent(item.key)}`,
        { enabled }
      )) as FeatureSetting;
      setItems((current) =>
        current.map((row) => (row.key === item.key ? updated : row))
      );
      await refreshFlags();
    } catch (err) {
      setItems((current) =>
        current.map((row) =>
          row.key === item.key ? { ...row, enabled: item.enabled } : row
        )
      );
      setError(err instanceof Error ? err.message : "Could not update feature.");
    } finally {
      setSavingKey(null);
    }
  }

  return (
    <div className="max-w-4xl mx-auto p-6">
      <div className="flex items-center gap-3 mb-1">
        <SlidersHorizontal className="w-6 h-6 text-slate-700" />
        <h1 className="text-2xl font-semibold text-slate-900">Features</h1>
      </div>
      <p className="text-sm text-slate-500 mb-6">
        Choose which optional capabilities your organization uses. Platform
        release availability, plan access, and permissions remain separate.
      </p>

      {error && (
        <div className="mb-4 rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      <div className="overflow-hidden rounded-lg border border-slate-200 bg-white">
        {loading ? (
          <div className="p-6 text-sm text-slate-500">Loading features...</div>
        ) : items.length === 0 ? (
          <div className="p-6 text-sm text-slate-500">
            No configurable features are currently available.
          </div>
        ) : (
          <div className="divide-y divide-slate-100">
            {items.map((item) => {
              const planBlocked = !item.entitlement_allowed;
              const permissionBlocked = !item.permission_allowed;
              const disabled =
                savingKey === item.key || planBlocked || permissionBlocked;

              return (
                <div
                  key={item.key}
                  className="flex items-center justify-between gap-6 p-5"
                >
                  <div className="min-w-0">
                    <div className="font-medium text-slate-900">
                      {item.label}
                    </div>
                    <div className="mt-1 text-xs text-slate-500">
                      {planBlocked
                        ? "Not included in the current plan."
                        : permissionBlocked
                          ? "Your role does not allow this capability."
                          : "Available to your organization."}
                    </div>
                  </div>
                  <label className="inline-flex shrink-0 items-center gap-2 text-sm text-slate-700">
                    <input
                      type="checkbox"
                      aria-label={item.label}
                      checked={item.enabled}
                      disabled={disabled}
                      onChange={(event) =>
                        void setEnabled(item, event.target.checked)
                      }
                      className="h-4 w-4"
                    />
                    <span>{item.enabled ? "On" : "Off"}</span>
                  </label>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
