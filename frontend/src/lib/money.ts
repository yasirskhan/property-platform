// ============================================================
// money.ts
// ------------------------------------------------------------
// Format money in the org's currency.
//
// Every amount in the app is stored in the org's single currency.
// No exchange, no conversion. See PROJECT_MASTER.md Section 59.
//
// Usage:
//   import { formatMoney } from "@/lib/money";
//   formatMoney(1234.56)  // "$1,234.56" for USD
//   formatMoney(1234.56)  // "₹1,234.56" for INR
//
// Reads the currency from CurrencyContext. If no provider is
// mounted (early render, tests), falls back to USD.
// ============================================================

export type CurrencyCode =
  | "USD" | "EUR" | "GBP" | "INR"
  | "AUD" | "CAD" | "NZD" | "SGD" | "AED";

// Best-guess locale per currency. Used by Intl.NumberFormat so
// the number style matches the currency's home country.
const CURRENCY_LOCALE: Record<CurrencyCode, string> = {
  USD: "en-US",
  EUR: "de-DE",
  GBP: "en-GB",
  INR: "en-IN",
  AUD: "en-AU",
  CAD: "en-CA",
  NZD: "en-NZ",
  SGD: "en-SG",
  AED: "en-AE",
};

// Module-level fallback. CurrencyContext updates this on mount.
let currentCurrency: CurrencyCode = "USD";

export function setCurrency(code: string | null | undefined): void {
  const upper = (code || "USD").toUpperCase() as CurrencyCode;
  currentCurrency = CURRENCY_LOCALE[upper] ? upper : "USD";
}

export function getCurrency(): CurrencyCode {
  return currentCurrency;
}

export function getCurrencyLocale(): string {
  return CURRENCY_LOCALE[currentCurrency] ?? "en-US";
}

/**
 * Format a money amount in the org's currency.
 *
 * @param amount  number or numeric string (backend sends strings for decimals)
 * @param opts    optional overrides
 *   - showSymbol: default true. If false, returns plain number.
 *   - decimals:   default 2.
 */
export function formatMoney(
  amount: number | string | null | undefined,
  opts: { showSymbol?: boolean; decimals?: number } = {}
): string {
  if (amount === null || amount === undefined || amount === "") return "";

  const n = typeof amount === "string" ? parseFloat(amount) : amount;
  if (Number.isNaN(n)) return "";

  const { showSymbol = true, decimals = 2 } = opts;

  if (!showSymbol) {
    return new Intl.NumberFormat(getCurrencyLocale(), {
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals,
    }).format(n);
  }

  return new Intl.NumberFormat(getCurrencyLocale(), {
    style: "currency",
    currency: currentCurrency,
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(n);
}

/**
 * Format a date according to the user's display preference.
 * Reads a "US" | "ISO" | "EU" string; falls back to US.
 * Kept here so date + money formatting live together.
 */
let currentDateFormat: "US" | "ISO" | "EU" = "US";

export function setDateFormat(fmt: string | null | undefined): void {
  const up = (fmt || "US").toUpperCase();
  currentDateFormat = (up === "ISO" || up === "EU") ? up : "US";
}

export function formatDate(input: string | Date | null | undefined): string {
  if (!input) return "";
  const d = input instanceof Date ? input : new Date(input);
  if (Number.isNaN(d.getTime())) return "";

  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");

  switch (currentDateFormat) {
    case "ISO": return `${y}-${m}-${day}`;
    case "EU":  return `${day}/${m}/${y}`;
    case "US":
    default:    return `${m}/${day}/${y}`;
  }
}