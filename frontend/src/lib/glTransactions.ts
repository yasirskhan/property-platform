// ============================================================
// glTransactions.ts
// ------------------------------------------------------------
// Typed API client for the General Ledger (transactions,
// ledger for an account, balances, trial balance).
//
// All calls go through lib/api.ts for auth + error handling.
//
// NOTE: formatMoney() and formatBalance() were removed from this
// file. They duplicated lib/money.ts and hardcoded USD. Pages that
// need money formatting must import from "@/lib/money" instead
// (Section 59 — per-org currency).
// ============================================================

import { apiGet } from "@/lib/api";

// ------------------------------------------------------------
// Shapes (mirror the backend schemas exactly)
// ------------------------------------------------------------

export type GLEntry = {
  id: number;
  transaction_id: number;
  gl_account_id: number;
  gl_account_number: string | null;
  gl_account_name: string | null;
  property_id: number | null;
  unit_id: number | null;
  description: string | null;
  debit: string;
  credit: string;
};

export type GLTransaction = {
  id: number;
  organization_id: number;
  transaction_date: string;      // YYYY-MM-DD
  posted_at: string;
  transaction_type: string;
  reference_number: string | null;
  memo: string | null;
  source_type: string | null;
  source_id: number | null;
  created_by_id: number | null;
  is_reversed: boolean;
  reversal_of_id: number | null;
  created_at: string | null;
  updated_at: string | null;
};

export type GLTransactionDetail = GLTransaction & {
  entries: GLEntry[];
};

export type GLTransactionList = {
  items: GLTransaction[];
  total: number;
};

export type LedgerLine = {
  entry_id: number;
  transaction_id: number;
  transaction_date: string;
  transaction_type: string;
  reference_number: string | null;
  memo: string | null;
  description: string | null;
  property_id: number | null;
  unit_id: number | null;
  debit: string;
  credit: string;
  running_balance: string;
};

export type Ledger = {
  gl_account_id: number;
  gl_number: string;
  name: string;
  account_type: string;
  opening_balance: string;
  closing_balance: string;
  lines: LedgerLine[];
};

export type GLAccountBalance = {
  gl_account_id: number;
  gl_number: string;
  name: string;
  account_type: string;
  debit_total: string;
  credit_total: string;
  balance: string;
};

export type TrialBalanceRow = {
  gl_account_id: number;
  gl_number: string;
  name: string;
  account_type: string;
  debit: string;
  credit: string;
};

export type TrialBalance = {
  as_of: string;
  rows: TrialBalanceRow[];
  total_debits: string;
  total_credits: string;
  is_balanced: boolean;
};

// ------------------------------------------------------------
// Query parameters
// ------------------------------------------------------------

export type TransactionListFilters = {
  date_from?: string;
  date_to?: string;
  transaction_type?: string;
  property_id?: number;
  source_type?: string;
  source_id?: number;
  limit?: number;
};

export type LedgerFilters = {
  date_from?: string;
  date_to?: string;
  property_id?: number;
};

// ------------------------------------------------------------
// Helpers
// ------------------------------------------------------------

function qs(params: Record<string, string | number | undefined | null>): string {
  const parts: string[] = [];
  for (const [k, v] of Object.entries(params)) {
    if (v === undefined || v === null || v === "") continue;
    parts.push(`${encodeURIComponent(k)}=${encodeURIComponent(String(v))}`);
  }
  return parts.length ? `?${parts.join("&")}` : "";
}

// ------------------------------------------------------------
// Endpoints
// ------------------------------------------------------------

export function listTransactions(
  filters: TransactionListFilters = {}
): Promise<GLTransactionList> {
  return apiGet(`/api/accounting/gl-transactions${qs(filters)}`);
}

export function getTransaction(id: number): Promise<GLTransactionDetail> {
  return apiGet(`/api/accounting/gl-transactions/${id}`);
}

export function getAccountLedger(
  accountId: number,
  filters: LedgerFilters = {}
): Promise<Ledger> {
  return apiGet(`/api/accounting/gl-accounts/${accountId}/ledger${qs(filters)}`);
}

export function getAccountBalance(
  accountId: number,
  asOf?: string
): Promise<GLAccountBalance> {
  return apiGet(
    `/api/accounting/gl-accounts/${accountId}/balance${qs({ as_of: asOf })}`
  );
}

export function getTrialBalance(
  asOf?: string,
  includeZero = false
): Promise<TrialBalance> {
  return apiGet(
    `/api/accounting/reports/trial-balance${qs({
      as_of: asOf,
      include_zero: includeZero ? "true" : undefined,
    })}`
  );
}