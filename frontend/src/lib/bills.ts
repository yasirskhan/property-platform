// ============================================================
// bills.ts
// ------------------------------------------------------------
// Typed API client for Bills (Phase 2 Step 6).
//
// Two-step accrual:
//   Enter  -> DR Expense / CR AP
//   Pay    -> DR AP     / CR Cash
//
// All calls go through lib/api.ts for auth + error handling.
// ============================================================

import { apiGet, apiPost } from "@/lib/api";

// ------------------------------------------------------------
// Shapes (mirror backend schemas)
// ------------------------------------------------------------

export type BillLine = {
  id: number;
  bill_id: number;
  gl_account_id: number;
  gl_account_number: string | null;
  gl_account_name: string | null;
  property_id: number | null;
  unit_id: number | null;
  description: string | null;
  amount: string;
};

export type Bill = {
  id: number;
  organization_id: number;

  bill_number: string | null;
  payee_name: string;
  payee_user_id: number | null;

  bill_date: string;             // YYYY-MM-DD
  due_date: string | null;
  reference_number: string | null;

  amount: string;
  amount_paid: string;
  status: "UNPAID" | "PARTIAL" | "PAID" | "VOID";

  property_id: number | null;
  unit_id: number | null;

  payable_gl_account_id: number;
  payable_gl_account_number: string | null;
  payable_gl_account_name: string | null;

  remarks: string | null;
  notes: string | null;

  source_type: string | null;
  source_id: number | null;

  gl_transaction_id: number | null;
  is_reversed: boolean;
  reversal_of_id: number | null;
  is_active: boolean;

  created_by_id: number | null;
  created_at: string | null;
  updated_at: string | null;
};

export type BillDetail = Bill & {
  lines: BillLine[];
};

export type BillList = {
  items: Bill[];
  total: number;
};

// ------------------------------------------------------------
// Write shapes
// ------------------------------------------------------------

export type BillLineIn = {
  gl_account_id: number;
  property_id?: number | null;
  unit_id?: number | null;
  description?: string | null;
  amount: number | string;
};

export type BillCreateIn = {
  payee_name: string;
  payee_user_id?: number | null;

  bill_date: string;
  due_date?: string | null;
  reference_number?: string | null;
  bill_number?: string | null;

  payable_gl_account_id?: number | null;

  property_id?: number | null;
  unit_id?: number | null;

  remarks?: string | null;
  notes?: string | null;

  source_type?: string | null;
  source_id?: number | null;

  lines: BillLineIn[];
};

export type BillPayIn = {
  payment_date: string;
  cash_gl_account_id: number;
  amount: number | string;
  reference_number?: string | null;
  remarks?: string | null;
};

export type BillReverseIn = {
  reversal_date: string;
  memo?: string | null;
};

// ------------------------------------------------------------
// Query parameters
// ------------------------------------------------------------

export type BillListFilters = {
  date_from?: string;
  date_to?: string;
  status?: "UNPAID" | "PARTIAL" | "PAID" | "VOID";
  property_id?: number;
  payee_name?: string;
  include_reversed?: boolean;
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

export function listBills(filters: BillListFilters = {}): Promise<BillList> {
  return apiGet(`/api/accounting/bills${qs(filters)}`);
}

export function getBill(id: number): Promise<BillDetail> {
  return apiGet(`/api/accounting/bills/${id}`);
}

export function createBill(payload: BillCreateIn): Promise<BillDetail> {
  return apiPost(`/api/accounting/bills`, payload);
}

export function payBill(id: number, payload: BillPayIn): Promise<BillDetail> {
  return apiPost(`/api/accounting/bills/${id}/pay`, payload);
}

export function reverseBill(
  id: number,
  payload: BillReverseIn
): Promise<BillDetail> {
  return apiPost(`/api/accounting/bills/${id}/reverse`, payload);
}

// ------------------------------------------------------------
// Display helpers
// ------------------------------------------------------------

export const BILL_STATUS_LABELS: Record<string, string> = {
  UNPAID: "Unpaid",
  PARTIAL: "Partial",
  PAID: "Paid",
  VOID: "Void",
};

export const BILL_STATUS_ORDER: Array<"UNPAID" | "PARTIAL" | "PAID" | "VOID"> =
  ["UNPAID", "PARTIAL", "PAID", "VOID"];

export const BILL_STATUS_COLORS: Record<string, string> = {
  UNPAID: "bg-yellow-50 text-yellow-700",
  PARTIAL: "bg-blue-50 text-blue-700",
  PAID: "bg-green-50 text-green-700",
  VOID: "bg-red-50 text-red-700",
};