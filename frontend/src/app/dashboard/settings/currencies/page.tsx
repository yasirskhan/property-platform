// ============================================================
// Settings -> Currencies
// ------------------------------------------------------------
// Per-org currency management.
//
//   - Lists all currencies for the org
//   - "Add currency" opens an inline form
//   - System currencies cannot be deleted (server enforces)
//   - The currency currently in use cannot be deleted
//
// Only ADMIN/OWNER can add / edit / delete. Everyone in the org
// can view the list.
//
// See PROJECT_MASTER.md Section 68.
// ============================================================

"use client";

import { useEffect, useState } from "react";
import { apiGet, apiPost, apiDelete } from "@/lib/api";

// ------------------------------------------------------------
// Types
// ------------------------------------------------------------
interface Currency {
  id: number;
  code: string;
  name: string;
  symbol: string;
  locale: string;
  decimal_places: number;
  is_system: boolean;
  is_active: boolean;
}

interface NewCurrency {
  code: string;
  name: string;
  symbol: string;
  locale: string;
  decimal_places: number;
}

const EMPTY_NEW: NewCurrency = {
  code: "",
  name: "",
  symbol: "",
  locale: "en-US",
  decimal_places: 2,
};

// ------------------------------------------------------------
// Page
// ------------------------------------------------------------
export default function CurrenciesSettingsPage() {
  const [rows, setRows] = useState<Currency[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showAdd, setShowAdd] = useState(false);
  const [form, setForm] = useState<NewCurrency>(EMPTY_NEW);
  const [saving, setSaving] = useState(false);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const data = (await apiGet("/api/settings/currencies")) as Currency[];
      setRows(data);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Could not load currencies.";
      setError(msg);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function add() {
    setSaving(true);
    setError(null);
    try {
      await apiPost("/api/settings/currencies", {
        ...form,
        code: form.code.toUpperCase(),
      });
      setForm(EMPTY_NEW);
      setShowAdd(false);
      await load();
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Could not add currency.";
      setError(msg);
    } finally {
      setSaving(false);
    }
  }

  async function remove(id: number) {
    if (!confirm("Remove this currency?")) return;
    setError(null);
    try {
      await apiDelete(`/api/settings/currencies/${id}`);
      await load();
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Could not remove currency.";
      setError(msg);
    }
  }

  return (
    <div className="max-w-4xl mx-auto p-6">
      <div className="flex items-center justify-between mb-1">
        <h1 className="text-xl font-semibold text-slate-900">Currencies</h1>
        <button
          type="button"
          onClick={() => setShowAdd((v) => !v)}
          className="px-3 py-1.5 rounded-md bg-blue-600 text-white text-sm font-medium hover:bg-blue-700"
        >
          {showAdd ? "Cancel" : "+ Add currency"}
        </button>
      </div>
      <p className="text-sm text-slate-500 mb-6">
        What your organization can pick from when choosing a currency. Each org
        uses exactly one currency at a time. No conversion.
      </p>

      {/* Add form */}
      {showAdd && (
        <div className="bg-white rounded-lg border border-slate-200 p-5 mb-5">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs text-slate-600 mb-1">
                Code (3 letters, uppercase)
              </label>
              <input
                type="text"
                maxLength={3}
                value={form.code}
                onChange={(e) =>
                  setForm({ ...form, code: e.target.value.toUpperCase() })
                }
                placeholder="PKR"
                className="w-full border border-slate-300 rounded-md px-3 py-1.5 text-sm"
              />
            </div>
            <div>
              <label className="block text-xs text-slate-600 mb-1">Name</label>
              <input
                type="text"
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                placeholder="Pakistani Rupee"
                className="w-full border border-slate-300 rounded-md px-3 py-1.5 text-sm"
              />
            </div>
            <div>
              <label className="block text-xs text-slate-600 mb-1">Symbol</label>
              <input
                type="text"
                maxLength={10}
                value={form.symbol}
                onChange={(e) => setForm({ ...form, symbol: e.target.value })}
                placeholder="\u20a8"
                className="w-full border border-slate-300 rounded-md px-3 py-1.5 text-sm"
              />
            </div>
            <div>
              <label className="block text-xs text-slate-600 mb-1">
                Locale (for number format, e.g. en-PK, en-IN)
              </label>
              <input
                type="text"
                value={form.locale}
                onChange={(e) => setForm({ ...form, locale: e.target.value })}
                placeholder="en-PK"
                className="w-full border border-slate-300 rounded-md px-3 py-1.5 text-sm"
              />
            </div>
            <div>
              <label className="block text-xs text-slate-600 mb-1">
                Decimal places
              </label>
              <input
                type="number"
                min={0}
                max={4}
                value={form.decimal_places}
                onChange={(e) =>
                  setForm({ ...form, decimal_places: Number(e.target.value) })
                }
                className="w-full border border-slate-300 rounded-md px-3 py-1.5 text-sm"
              />
            </div>
          </div>
          <div className="flex items-center gap-3 mt-4">
            <button
              type="button"
              onClick={add}
              disabled={
                saving ||
                form.code.length !== 3 ||
                !form.name ||
                !form.symbol ||
                !form.locale
              }
              className="px-4 py-2 rounded-md bg-blue-600 text-white text-sm font-medium hover:bg-blue-700 disabled:opacity-50"
            >
              {saving ? "Adding..." : "Add currency"}
            </button>
            <span className="text-xs text-slate-500">
              Preview:{" "}
              {form.code.length === 3 && form.locale ? (
                <span className="font-mono">
                  {(() => {
                    try {
                      return new Intl.NumberFormat(form.locale, {
                        style: "currency",
                        currency: form.code,
                      }).format(1234.56);
                    } catch {
                      return "(invalid locale or code)";
                    }
                  })()}
                </span>
              ) : (
                "\u2014"
              )}
            </span>
          </div>
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="text-sm text-red-600 mb-3 bg-red-50 border border-red-200 rounded-md px-3 py-2">
          {error}
        </div>
      )}

      {/* List */}
      <div className="bg-white rounded-lg border border-slate-200 overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-slate-600">
            <tr>
              <th className="text-left px-4 py-2 font-medium">Code</th>
              <th className="text-left px-4 py-2 font-medium">Name</th>
              <th className="text-left px-4 py-2 font-medium">Symbol</th>
              <th className="text-left px-4 py-2 font-medium">Locale</th>
              <th className="text-left px-4 py-2 font-medium">Decimals</th>
              <th className="text-left px-4 py-2 font-medium">Type</th>
              <th className="text-right px-4 py-2 font-medium">Actions</th>
            </tr>
          </thead>
          <tbody>
            {loading && (
              <tr>
                <td colSpan={7} className="px-4 py-6 text-center text-slate-500">
                  Loading...
                </td>
              </tr>
            )}
            {!loading && rows.length === 0 && (
              <tr>
                <td colSpan={7} className="px-4 py-6 text-center text-slate-500">
                  No currencies found.
                </td>
              </tr>
            )}
            {rows.map((c) => (
              <tr key={c.id} className="border-t border-slate-100">
                <td className="px-4 py-2 font-mono">{c.code}</td>
                <td className="px-4 py-2">{c.name}</td>
                <td className="px-4 py-2">{c.symbol}</td>
                <td className="px-4 py-2 font-mono text-xs">{c.locale}</td>
                <td className="px-4 py-2">{c.decimal_places}</td>
                <td className="px-4 py-2">
                  {c.is_system ? (
                    <span className="text-xs px-2 py-0.5 rounded-full bg-slate-100 text-slate-600">
                      System
                    </span>
                  ) : (
                    <span className="text-xs px-2 py-0.5 rounded-full bg-blue-50 text-blue-700">
                      Custom
                    </span>
                  )}
                </td>
                <td className="px-4 py-2 text-right">
                  {!c.is_system && (
                    <button
                      type="button"
                      onClick={() => remove(c.id)}
                      className="text-xs text-red-600 hover:underline"
                    >
                      Remove
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}