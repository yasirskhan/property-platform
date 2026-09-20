// ============================================================
// bankAccounts.ts
// ------------------------------------------------------------
// Typed API client for Bank Accounts (Phase 2 Step 4).
// ============================================================

import { apiGet, apiPost, apiPatch, apiDelete } from "@/lib/api";

// ------------------------------------------------------------
// Shapes
// ------------------------------------------------------------

export type BankAccount = {
  id: number;
  organization_id: number;
  name: string;
  bank_name: string | null;
  routing_number: string | null;
  account_number: string | null;
  gl_account_id: number;
  gl_account_number: string | null;
  gl_account_name: string | null;
  account_type: "OPERATING" | "ESCROW";
  ach_format: "CSV" | "NACHA" | null;
  notes: string | null;
  is_active: boolean;
  created_by_id: number | null;
  created_at: string | null;
  updated_at: string | null;
};

export type BankAccountList = {
  items: BankAccount[];
  total: number;
};

// ------------------------------------------------------------
// Write shapes
// ------------------------------------------------------------

export type BankAccountCreateIn = {
  name: string;
  bank_name?: string | null;
  routing_number?: string | null;
  account_number?: string | null;
  gl_account_id: number;
  account_type?: "OPERATING" | "ESCROW";
  ach_format?: "CSV" | "NACHA" | null;
  notes?: string | null;
};

export type BankAccountUpdateIn = {
  name?: string;
  bank_name?: string | null;
  routing_number?: string | null;
  account_number?: string | null;
  account_type?: "OPERATING" | "ESCROW";
  ach_format?: "CSV" | "NACHA" | null;
  notes?: string | null;
  is_active?: boolean;
};

// ------------------------------------------------------------
// Endpoints
// ------------------------------------------------------------

export function listBankAccounts(
  includeInactive = false
): Promise<BankAccountList> {
  const q = includeInactive ? "?include_inactive=true" : "";
  return apiGet(`/api/accounting/bank-accounts${q}`);
}

export function getBankAccount(id: number): Promise<BankAccount> {
  return apiGet(`/api/accounting/bank-accounts/${id}`);
}

export function createBankAccount(
  payload: BankAccountCreateIn
): Promise<BankAccount> {
  return apiPost(`/api/accounting/bank-accounts`, payload);
}

export function updateBankAccount(
  id: number,
  payload: BankAccountUpdateIn
): Promise<BankAccount> {
  return apiPatch(`/api/accounting/bank-accounts/${id}`, payload);
}

export function deleteBankAccount(id: number): Promise<null> {
  return apiDelete(`/api/accounting/bank-accounts/${id}`);
}