// ============================================================
// receipts.ts
// ------------------------------------------------------------
// Typed API client for Receipts (Phase 2 Step 5).
//
// Three types (mirrors backend):
//   TENANT  - tenant pays rent/fees
//   OWNER   - owner sends money in
//   OTHER   - anything else
//
// All calls go through lib/api.ts for auth + error handling.
// ============================================================

import { apiGet, apiPost } from "@/lib/api";

// ------------------------------------------------------------
// Shapes (mirror the backend schemas exactly)
// ------------------------------------------------------------

export type ReceiptLine = {
  id: number;
  receipt_id: number;
  gl_account_id: number;
  gl_account_number: string | null;
  gl_account_name: string | null;
  property_id: number | null;
  unit_id: number | null;
  description: string | null;
  amount_to_pay: string;
  line_date: string | null;      // YYYY-MM-DD
  is_prepayment: boolean;
};

export type Receipt = {
  id: number;
  organization_id: number;
  type: "TENANT" | "OWNER" | "OTHER" | "APPLICATION_FEE";
  receipt_date: string;          // YYYY-MM-DD
  amount: string;

  cash_gl_account_id?: number | null;
  cash_gl_account_number: string | null;
  cash_gl_account_name: string | null;

  tenant_user_id: number | null;
  owner_user_id: number | null;
  income_gl_account_id: number | null;
  payer_name: string | null;

  received_from: string | null;
  exclude_from_mgmt_fee: boolean;

  property_id: number | null;
  unit_id: number | null;
  reference_number: string | null;
  remarks: string | null;
  notes: string | null;

  gl_transaction_id: number | null;
  deposit_id: number | null;
  is_deposited: boolean;
  is_reversed: boolean;
  reversal_of_id: number | null;
  is_active: boolean;

  created_by_id: number | null;
  created_at: string | null;
  updated_at: string | null;
};

export type ReceiptDetail = Receipt & {
  lines: ReceiptLine[];
};

export type ReceiptList = {
  items: Receipt[];
  total: number;
};

// ------------------------------------------------------------
// Write shapes (payloads we POST)
// ------------------------------------------------------------

export type ReceiptLineIn = {
  gl_account_id: number;
  property_id?: number | null;
  unit_id?: number | null;
  description?: string | null;
  amount_to_pay: number | string;
  line_date?: string | null;
  is_prepayment?: boolean;
};

export type ReceiptCreateIn = {
  type: "TENANT" | "OWNER" | "OTHER" | "APPLICATION_FEE";
  receipt_date: string;
  amount: number | string;
  cash_gl_account_id: number;

  // TENANT
  tenant_user_id?: number | null;

  // OWNER
  owner_user_id?: number | null;
  income_gl_account_id?: number | null;
  payer_name?: string | null;

  // OTHER
  received_from?: string | null;
  exclude_from_mgmt_fee?: boolean;

  // Common
  property_id?: number | null;
  unit_id?: number | null;
  reference_number?: string | null;
  remarks?: string | null;
  notes?: string | null;

  // Lines (TENANT only — OWNER/OTHER auto-generate one)
  lines?: ReceiptLineIn[];
};

export type ReceiptReverseIn = {
  reversal_date: string;
  memo?: string | null;
};

export type ReceiptNSFIn = {
  process_date: string;
  memo?: string | null;
};

// ------------------------------------------------------------
// Open charge (for the tenant charges table)
// ------------------------------------------------------------

export type TenantOpenCharge = {
  charge_id: number;
  charge_date: string | null;
  description: string | null;
  balance: string;
  amount_due: string;
  amount_paid: string;
  gl_account_id: number | null;
  gl_account_number: string | null;
  gl_account_name: string | null;
};

export type TenantOpenChargesResponse = {
  items: TenantOpenCharge[];
  total: number;
  lease_id: number | null;
  rent_gl_account_id: number | null;
  rent_gl_account_number: string | null;
  rent_gl_account_name: string | null;
};

// ------------------------------------------------------------
// Query parameters
// ------------------------------------------------------------

export type ReceiptListFilters = {
  date_from?: string;
  date_to?: string;
  type?: "TENANT" | "OWNER" | "OTHER";
  property_id?: number;
  include_reversed?: boolean;
  limit?: number;
};

// ------------------------------------------------------------
// Helpers
// ------------------------------------------------------------

function qs(params: Record<string, string | number | boolean | undefined | null>): string {
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

export function listReceipts(
  filters: ReceiptListFilters = {}
): Promise<ReceiptList> {
  return apiGet(`/api/accounting/receipts${qs(filters)}`);
}

export function getReceipt(id: number): Promise<ReceiptDetail> {
  return apiGet(`/api/accounting/receipts/${id}`);
}

export function createReceipt(
  payload: ReceiptCreateIn
): Promise<ReceiptDetail> {
  return apiPost(`/api/accounting/receipts`, payload);
}

export function reverseReceipt(
  id: number,
  payload: ReceiptReverseIn
): Promise<ReceiptDetail> {
  return apiPost(`/api/accounting/receipts/${id}/reverse`, payload);
}

export function getReceiptPrintData(id: number): Promise<ReceiptDetail> {
  return apiGet(`/api/accounting/receipts/${id}/print-data`);
}

export function getReceiptRepeatData(id: number): Promise<ReceiptDetail> {
  return apiGet(`/api/accounting/receipts/${id}/repeat-data`);
}

export function processReceiptNSF(
  id: number,
  payload: ReceiptNSFIn
): Promise<ReceiptDetail> {
  return apiPost(`/api/accounting/receipts/${id}/process-nsf`, payload);
}

export function listTenantOpenCharges(
  userId: number
): Promise<TenantOpenChargesResponse> {
  return apiGet(`/api/accounting/receipts/tenant/${userId}/open-charges`);
}

// ------------------------------------------------------------
// Display helpers
// ------------------------------------------------------------

export const RECEIPT_TYPE_LABELS: Record<string, string> = {
  TENANT: "Tenant",
  OWNER: "Owner",
  OTHER: "Other",
  APPLICATION_FEE: "Application Fee",
};

export const RECEIPT_TYPE_ORDER: Array<"TENANT" | "OWNER" | "OTHER"> = [
  "TENANT",
  "OWNER",
  "OTHER",
];