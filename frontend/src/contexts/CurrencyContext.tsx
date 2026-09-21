// ============================================================
// CurrencyContext.tsx
// ------------------------------------------------------------
// Loads the current user's display preferences (which includes
// the org's currency) on mount, and pushes the currency into
// lib/money.ts so every formatMoney() call uses it.
//
// Also exposes the full display preferences so other contexts
// (Display / Theme / Layout) can read them.
//
// See PROJECT_MASTER.md Sections 58 and 59.
// ============================================================

"use client";

import {
  createContext,
  useContext,
  useEffect,
  useState,
  useCallback,
  ReactNode,
} from "react";

import { setCurrency, setDateFormat } from "@/lib/money";
import { apiGet } from "@/lib/api";

// ------------------------------------------------------------
// Types
// ------------------------------------------------------------
export type LayoutMode = "TABS" | "VERTICAL";
export type ThemeMode = "LIGHT" | "DARK" | "AUTO";
export type Density = "COMPACT" | "COMFORTABLE" | "SPACIOUS";
export type DateFormat = "US" | "ISO" | "EU";
export type NumberFormat = "US" | "EU" | "SPACE";
export type FontSize = "SMALL" | "NORMAL" | "LARGE";

export interface DisplayPreferences {
  layout_mode: LayoutMode;
  theme: ThemeMode;
  density: Density;
  date_format: DateFormat;
  number_format: NumberFormat;
  font_size: FontSize;
  accent_color: string | null;
  reduce_motion: boolean;
  currency: string; // ISO 4217 (USD, INR, GBP, ...)
}

interface CurrencyContextValue {
  currency: string;
  prefs: DisplayPreferences | null;
  loading: boolean;
  /** Refetch prefs from the server. */
  refresh: () => Promise<void>;
  /** Optimistically update in-memory prefs (used by Display page after PUT). */
  setPrefs: (prefs: DisplayPreferences) => void;
}

const DEFAULT_PREFS: DisplayPreferences = {
  layout_mode: "TABS",
  theme: "LIGHT",
  density: "COMFORTABLE",
  date_format: "US",
  number_format: "US",
  font_size: "NORMAL",
  accent_color: null,
  reduce_motion: false,
  currency: "USD",
};

const CurrencyContext = createContext<CurrencyContextValue>({
  currency: "USD",
  prefs: null,
  loading: true,
  refresh: async () => {},
  setPrefs: () => {},
});

// ------------------------------------------------------------
// Provider
// ------------------------------------------------------------
export function CurrencyProvider({ children }: { children: ReactNode }) {
  const [prefs, setPrefsState] = useState<DisplayPreferences | null>(null);
  const [loading, setLoading] = useState(true);

  const apply = useCallback((p: DisplayPreferences) => {
    setPrefsState(p);
    setCurrency(p.currency);
    setDateFormat(p.date_format);
  }, []);

  const fetchPrefs = useCallback(async () => {
    try {
      const data = (await apiGet("/api/settings/display")) as DisplayPreferences;
      apply(data);
    } catch {
      // Not logged in yet, or endpoint unreachable — fall back to defaults.
      apply(DEFAULT_PREFS);
    } finally {
      setLoading(false);
    }
  }, [apply]);

  useEffect(() => {
    fetchPrefs();
  }, [fetchPrefs]);

  const setPrefs = useCallback(
    (p: DisplayPreferences) => {
      apply(p);
    },
    [apply]
  );

  return (
    <CurrencyContext.Provider
      value={{
        currency: prefs?.currency ?? "USD",
        prefs,
        loading,
        refresh: fetchPrefs,
        setPrefs,
      }}
    >
      {children}
    </CurrencyContext.Provider>
  );
}

// ------------------------------------------------------------
// Hook
// ------------------------------------------------------------
export function useCurrency() {
  return useContext(CurrencyContext);
}