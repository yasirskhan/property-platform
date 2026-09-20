// ============================================================
// deposits.ts
// ------------------------------------------------------------
// Typed API client for Bank Deposits (Phase 2 Step 7).
//
// Deposits tag receipts as "deposited." They do NOT post to
// the GL — receipts already credited cash when they were posted.
//
// All calls go through lib/api.ts for auth + error handling.
// ============================================================

import { apiGet, apiPost } from "@/lib/api";

// ------------------------------------------------------------
// Shapes (mirror backend schemas)
// ------------------------------------------------------------

export type DepositLine = {
  id: number;
  deposit_id: number;
  receipt_id: number;
  receipt_date: string | null;
  receipt_type: string | null;
  receipt_amount: string | null;
  receipt_reference: string | null;
  receipt_payer: string | null;
};

export type Deposit = {
  id: number;
  organization_id: number;

  bank_gl_account_id: number;
  bank_gl_account_number: string | null;
  bank_gl_account_name: string | null;

  deposit_date: string;         // YYYY-MM-DD
  deposit_number: string | null;
  description: string | null;
  total: string;
  notes: string | null;

  is_active: boolean;

  created_by_id: number | null;
  created_at: string | null;
  updated_at: string | null;

  line_count: number;
};

export type DepositDetail = Deposit & {
  lines: DepositLine[];
};

export type DepositList = {
  items: Deposit[];
  total: number;
};

export type UndepositedReceiptRow = {
  id: number;
  receipt_date: string;
  type: string;
  amount: string;
  reference_number: string | null;
  cash_gl_account_id: number;
  cash_gl_account_number: string | null;
  cash_gl_account_name: string | null;
  payer_label: string | null;
};

export type UndepositedReceiptsResponse = {
  items: UndepositedReceiptRow[];
  total: number;
  total_amount: string;
};

// ------------------------------------------------------------
// Write shapes
// ------------------------------------------------------------

export type DepositCreateIn = {
  bank_gl_account_id: number;
  deposit_date: string;
  deposit_number?: string | null;
  description?: string | null;
  notes?: string | null;
  receipt_ids: number[];
};

// ------------------------------------------------------------
// Query params
// ------------------------------------------------------------

export type DepositListFilters = {
  date_from?: string;
  date_to?: string;
  bank_gl_account_id?: number;
  limit?: number;
};

// ------------------------------------------------------------
// Helpers
// ------------------------------------------------------------

function qs(
  params: Record<string, string | number | boolean | undefined | null>
): string {
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

export function listDeposits(
  filters: DepositListFilters = {}
): Promise<DepositList> {
  return apiGet(`/api/accounting/deposits${qs(filters)}`);
}

export function getDeposit(id: number): Promise<DepositDetail> {
  return apiGet(`/api/accounting/deposits/${id}`);
}

export function createDeposit(
  payload: DepositCreateIn
): Promise<DepositDetail> {
  return apiPost(`/api/accounting/deposits`, payload);
}

export function listUndepositedReceipts(
  bankGlAccountId?: number
): Promise<UndepositedReceiptsResponse> {
  return apiGet(
    `/api/accounting/deposits/undeposited-receipts${qs({
      bank_gl_account_id: bankGlAccountId,
    })}`
  );
}