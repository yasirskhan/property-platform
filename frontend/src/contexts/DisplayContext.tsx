// ============================================================
// DisplayContext.tsx
// ------------------------------------------------------------
// Reads the display preferences (loaded by CurrencyProvider)
// and applies them to the document:
//
//   - theme:   sets data-theme="light|dark" on <html>
//   - density: sets data-density="compact|comfortable|spacious"
//   - font:    sets data-font="small|normal|large"
//   - motion:  sets data-motion="reduce" when reduce_motion is on
//   - accent:  sets --accent CSS variable
//
// Also exposes layout_mode so multi-section pages can render
// either TABS or VERTICAL. That's consumed by page components,
// not by this provider.
//
// See PROJECT_MASTER.md Section 58.
// ============================================================

"use client";

import { createContext, useContext, useEffect, ReactNode } from "react";
import { useCurrency, DisplayPreferences } from "./CurrencyContext";

interface DisplayContextValue {
  prefs: DisplayPreferences | null;
  loading: boolean;
}

const DisplayContext = createContext<DisplayContextValue>({
  prefs: null,
  loading: true,
});

function applyToDocument(p: DisplayPreferences | null) {
  if (typeof document === "undefined") return;
  const html = document.documentElement;

  // Theme
  const theme = p?.theme ?? "LIGHT";
  if (theme === "AUTO") {
    const dark = window.matchMedia("(prefers-color-scheme: dark)").matches;
    html.setAttribute("data-theme", dark ? "dark" : "light");
  } else {
    html.setAttribute("data-theme", theme.toLowerCase());
  }

  // Density
  html.setAttribute("data-density", (p?.density ?? "COMFORTABLE").toLowerCase());

  // Font size
  html.setAttribute("data-font", (p?.font_size ?? "NORMAL").toLowerCase());

  // Reduce motion
  if (p?.reduce_motion) {
    html.setAttribute("data-motion", "reduce");
  } else {
    html.removeAttribute("data-motion");
  }

  // Accent color (optional)
  if (p?.accent_color) {
    html.style.setProperty("--accent", p.accent_color);
  } else {
    html.style.removeProperty("--accent");
  }
}

export function DisplayProvider({ children }: { children: ReactNode }) {
  const { prefs, loading } = useCurrency();

  useEffect(() => {
    applyToDocument(prefs);
  }, [prefs]);

  // Re-apply on OS theme change when theme = AUTO
  useEffect(() => {
    if (typeof window === "undefined") return;
    if (prefs?.theme !== "AUTO") return;

    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const handler = () => applyToDocument(prefs);
    mq.addEventListener("change", handler);
    return () => mq.removeEventListener("change", handler);
  }, [prefs]);

  return (
    <DisplayContext.Provider value={{ prefs, loading }}>
      {children}
    </DisplayContext.Provider>
  );
}

export function useDisplay() {
  return useContext(DisplayContext);
}