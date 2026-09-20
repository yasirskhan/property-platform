// ============================================================
// glAccounts.ts
// ------------------------------------------------------------
// Typed API client for the Chart of Accounts.
// All calls go through lib/api.ts for auth + error handling.
// ============================================================

import { apiGet, apiPost, apiPut, apiDelete } from "@/lib/api";

// ------------------------------------------------------------
// Shapes
// ------------------------------------------------------------

export type GLAccount = {
  id: number;
  organization_id: number;
  gl_number: string;
  name: string;
  account_type: string; // ASSET | LIABILITY | EQUITY | INCOME | EXPENSE
  sub_account_of: number | null;
  offset_account: string | null;
  subject_to_mgmt_fees: boolean;
  include_on_cash_flow: boolean;
  is_active: boolean;
  created_at: string | null;
  updated_at: string | null;
};

export type GLAccountGroup = {
  account_type: string;
  accounts: GLAccount[];
};

export type GLAccountList = {
  groups: GLAccountGroup[];
  total: number;
};

export type GLAccountCreate = {
  gl_number: string;
  name: string;
  account_type: string;
  sub_account_of?: number | null;
  offset_account?: string | null;
  subject_to_mgmt_fees?: boolean;
  include_on_cash_flow?: boolean;
};

export type GLAccountUpdate = {
  name?: string;
  account_type?: string;
  sub_account_of?: number | null;
  offset_account?: string | null;
  subject_to_mgmt_fees?: boolean;
  include_on_cash_flow?: boolean;
};

// ------------------------------------------------------------
// Display helpers
// ------------------------------------------------------------

export const ACCOUNT_TYPE_LABELS: Record<string, string> = {
  ASSET: "Assets",
  LIABILITY: "Liabilities",
  EQUITY: "Equity",
  INCOME: "Income",
  EXPENSE: "Expenses",
};

export const ACCOUNT_TYPE_ORDER = [
  "ASSET",
  "LIABILITY",
  "EQUITY",
  "INCOME",
  "EXPENSE",
];

// ------------------------------------------------------------
// Endpoints
// ------------------------------------------------------------

export function listGLAccounts(includeInactive = false): Promise<GLAccountList> {
  const q = includeInactive ? "?include_inactive=true" : "";
  return apiGet(`/api/accounting/gl-accounts${q}`);
}

export function getGLAccount(id: number): Promise<GLAccount> {
  return apiGet(`/api/accounting/gl-accounts/${id}`);
}

export function createGLAccount(payload: GLAccountCreate): Promise<GLAccount> {
  return apiPost("/api/accounting/gl-accounts", payload);
}

export function updateGLAccount(
  id: number,
  payload: GLAccountUpdate
): Promise<GLAccount> {
  return apiPut(`/api/accounting/gl-accounts/${id}`, payload);
}

export function deleteGLAccount(id: number): Promise<null> {
  return apiDelete(`/api/accounting/gl-accounts/${id}`);
}