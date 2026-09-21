// ============================================================
// Settings -> Display
// ------------------------------------------------------------
// Per-user display preferences + per-org currency.
//
// Layout mode + theme + date format are wired.
// Currency is org-wide (not per-user) - changing it here
// updates the org for everyone. Requires Admin/Owner.
// Density, number format, font size, accent, reduce motion
// are shown but marked "Coming soon".
//
// See PROJECT_MASTER.md Sections 58 and 59.
// ============================================================

"use client";

import { useEffect, useState } from "react";
import { apiGet, apiPut } from "@/lib/api";
import { useCurrency } from "@/contexts/CurrencyContext";
import type {
  DisplayPreferences,
  LayoutMode,
  ThemeMode,
  Density,
  DateFormat,
  NumberFormat,
  FontSize,
} from "@/contexts/CurrencyContext";

// ------------------------------------------------------------
// Currencies the org can pick from. Keep this list small and
// alphabetical. Matches CURRENCY_LOCALE in lib/money.ts.
// ------------------------------------------------------------
const CURRENCY_OPTIONS = [
  { code: "USD", label: "USD - US Dollar" },
  { code: "EUR", label: "EUR - Euro" },
  { code: "GBP", label: "GBP - British Pound" },
  { code: "INR", label: "INR - Indian Rupee" },
  { code: "AUD", label: "AUD - Australian Dollar" },
  { code: "CAD", label: "CAD - Canadian Dollar" },
  { code: "NZD", label: "NZD - New Zealand Dollar" },
  { code: "SGD", label: "SGD - Singapore Dollar" },
  { code: "AED", label: "AED - UAE Dirham" },
];

// ------------------------------------------------------------
// Small building blocks
// ------------------------------------------------------------
function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-3 py-3 border-b border-slate-100 last:border-b-0">
      <div>
        <div className="text-sm font-medium text-slate-800">{label}</div>
        {hint && <div className="text-xs text-slate-500 mt-0.5">{hint}</div>}
      </div>
      <div className="md:col-span-2">{children}</div>
    </div>
  );
}

function Segmented<T extends string>({
  value,
  options,
  onChange,
  disabled,
}: {
  value: T;
  options: { value: T; label: string }[];
  onChange: (v: T) => void;
  disabled?: boolean;
}) {
  return (
    <div className="inline-flex rounded-md border border-slate-200 overflow-hidden">
      {options.map((opt) => (
        <button
          key={opt.value}
          type="button"
          disabled={disabled}
          onClick={() => onChange(opt.value)}
          className={
            "px-3 py-1.5 text-sm border-r border-slate-200 last:border-r-0 transition " +
            (value === opt.value
              ? "bg-blue-600 text-white"
              : "bg-white text-slate-700 hover:bg-slate-50") +
            (disabled ? " opacity-50 cursor-not-allowed" : "")
          }
        >
          {opt.label}
        </button>
      ))}
    </div>
  );
}

// ------------------------------------------------------------
// Page
// ------------------------------------------------------------
export default function DisplaySettingsPage() {
  const { prefs, refresh, setPrefs } = useCurrency();
  const [local, setLocal] = useState<DisplayPreferences | null>(null);
  const [saving, setSaving] = useState(false);
  const [savedAt, setSavedAt] = useState<Date | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (prefs) setLocal(prefs);
  }, [prefs]);

  useEffect(() => {
    if (!local) refresh();
  }, [local, refresh]);

  if (!local) {
    return (
      <div className="max-w-3xl mx-auto p-6 text-slate-500">Loading...</div>
    );
  }

  function update<K extends keyof DisplayPreferences>(
    key: K,
    value: DisplayPreferences[K]
  ) {
    setLocal((prev) => (prev ? { ...prev, [key]: value } : prev));
  }

  async function save() {
    if (!local) return;
    setSaving(true);
    setError(null);
    try {
      const updated = (await apiPut("/api/settings/display", {
        layout_mode: local.layout_mode,
        theme: local.theme,
        density: local.density,
        date_format: local.date_format,
        number_format: local.number_format,
        font_size: local.font_size,
        accent_color: local.accent_color,
        reduce_motion: local.reduce_motion,
      })) as DisplayPreferences;

      setPrefs(updated);
      setSavedAt(new Date());
    } catch (e) {
      setError("Could not save. Please try again.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="max-w-3xl mx-auto p-6">
      <h1 className="text-xl font-semibold text-slate-900 mb-1">Display</h1>
      <p className="text-sm text-slate-500 mb-6">
        Personal preferences for how the app looks, plus your organization's
        currency.
      </p>

      <div className="bg-white rounded-lg border border-slate-200 p-5">
        {/* Currency - org-wide */}
        <Field
          label="Currency"
          hint="Applies to everyone in your organization. No conversion - all amounts are in this currency."
        >
          <select
            value={local.currency}
            onChange={(e) => update("currency", e.target.value)}
            className="border border-slate-300 rounded-md px-3 py-1.5 text-sm bg-white"
          >
            {CURRENCY_OPTIONS.map((c) => (
              <option key={c.code} value={c.code}>
                {c.label}
              </option>
            ))}
          </select>
          <div className="text-xs text-slate-500 mt-1">
            Preview:{" "}
            <span className="font-mono">
              {new Intl.NumberFormat(undefined, {
                style: "currency",
                currency: local.currency || "USD",
              }).format(1234.56)}
            </span>
          </div>
        </Field>

        {/* Layout mode */}
        <Field
          label="Layout mode"
          hint="How multi-section pages (like Property Detail) are arranged."
        >
          <Segmented<LayoutMode>
            value={local.layout_mode}
            onChange={(v) => update("layout_mode", v)}
            options={[
              { value: "TABS", label: "Tabs" },
              { value: "VERTICAL", label: "Vertical" },
            ]}
          />
        </Field>

        {/* Theme */}
        <Field label="Theme" hint="Light, dark, or follow your OS.">
          <Segmented<ThemeMode>
            value={local.theme}
            onChange={(v) => update("theme", v)}
            options={[
              { value: "LIGHT", label: "Light" },
              { value: "DARK", label: "Dark" },
              { value: "AUTO", label: "Auto" },
            ]}
          />
        </Field>

        {/* Density */}
        <Field label="Density" hint="Row height and spacing. Coming soon.">
          <Segmented<Density>
            value={local.density}
            onChange={(v) => update("density", v)}
            disabled
            options={[
              { value: "COMPACT", label: "Compact" },
              { value: "COMFORTABLE", label: "Comfortable" },
              { value: "SPACIOUS", label: "Spacious" },
            ]}
          />
        </Field>

        {/* Date format */}
        <Field label="Date format" hint="How dates are displayed.">
          <Segmented<DateFormat>
            value={local.date_format}
            onChange={(v) => update("date_format", v)}
            options={[
              { value: "US", label: "MM/DD/YYYY" },
              { value: "ISO", label: "YYYY-MM-DD" },
              { value: "EU", label: "DD/MM/YYYY" },
            ]}
          />
        </Field>

        {/* Number format */}
        <Field label="Number format" hint="Coming soon.">
          <Segmented<NumberFormat>
            value={local.number_format}
            onChange={(v) => update("number_format", v)}
            disabled
            options={[
              { value: "US", label: "1,234.56" },
              { value: "EU", label: "1.234,56" },
              { value: "SPACE", label: "1 234,56" },
            ]}
          />
        </Field>

        {/* Font size */}
        <Field label="Font size" hint="Coming soon.">
          <Segmented<FontSize>
            value={local.font_size}
            onChange={(v) => update("font_size", v)}
            disabled
            options={[
              { value: "SMALL", label: "Small" },
              { value: "NORMAL", label: "Normal" },
              { value: "LARGE", label: "Large" },
            ]}
          />
        </Field>

        {/* Reduce motion */}
        <Field
          label="Reduce motion"
          hint="Disable non-essential animations. Coming soon."
        >
          <label className="inline-flex items-center gap-2 opacity-50">
            <input
              type="checkbox"
              disabled
              checked={local.reduce_motion}
              onChange={(e) => update("reduce_motion", e.target.checked)}
            />
            <span className="text-sm text-slate-700">
              Reduce motion in the UI
            </span>
          </label>
        </Field>
      </div>

      {/* Actions */}
      <div className="flex items-center justify-between mt-5">
        <div className="text-xs text-slate-500">
          {error && <span className="text-red-600">{error}</span>}
          {savedAt && !error && (
            <span>Saved at {savedAt.toLocaleTimeString()}</span>
          )}
        </div>
        <button
          type="button"
          onClick={save}
          disabled={saving}
          className="px-4 py-2 rounded-md bg-blue-600 text-white text-sm font-medium hover:bg-blue-700 disabled:opacity-50"
        >
          {saving ? "Saving..." : "Save"}
        </button>
      </div>
    </div>
  );
}