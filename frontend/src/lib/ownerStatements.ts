// ============================================================
// ownerStatements.ts
// ------------------------------------------------------------
// Typed API client for Owner Statements (Phase 2 Step 10).
// ============================================================

import { apiGet, apiPost } from "@/lib/api";

// ------------------------------------------------------------
// Shapes
// ------------------------------------------------------------

export type StatementTransactionLine = {
  date: string;
  description: string | null;
  reference: string | null;
  income: string;
  expense: string;
  running_balance: string;
  gl_transaction_id: number | null;
};

export type StatementPropertyBlock = {
  property_id: number;
  property_name: string;
  ownership_pct: string;
  beginning_cash: string;
  ending_cash: string;
  income: string;
  expense: string;
  net: string;
  transactions: StatementTransactionLine[];
};

export type StatementPreview = {
  owner_id: number;
  owner_email: string | null;
  owner_name: string | null;
  period_start: string;
  period_end: string;
  total_beginning_cash: string;
  total_ending_cash: string;
  total_income: string;
  total_expense: string;
  total_net: string;
  properties: StatementPropertyBlock[];
  can_generate: boolean;
  reason: string | null;
};

export type OwnerStatement = {
  id: number;
  organization_id: number;
  owner_id: number;
  owner_email: string | null;
  owner_name: string | null;
  period_start: string;
  period_end: string;
  generated_at: string | null;
  total_beginning_cash: string;
  total_ending_cash: string;
  total_income: string;
  total_expense: string;
  total_net: string;
  pdf_url: string | null;
  notes: string | null;
  is_active: boolean;
  generated_by_id: number | null;
  created_at: string | null;
  updated_at: string | null;
};

export type OwnerStatementDetail = OwnerStatement & {
  properties: StatementPropertyBlock[];
};

export type OwnerStatementList = {
  items: OwnerStatement[];
  total: number;
};

// ------------------------------------------------------------
// Write shapes
// ------------------------------------------------------------

export type StatementPreviewIn = {
  owner_id: number;
  period_start: string;
  period_end: string;
};

export type StatementGenerateIn = StatementPreviewIn & {
  notes?: string | null;
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

export function previewOwnerStatement(
  payload: StatementPreviewIn
): Promise<StatementPreview> {
  return apiPost(`/api/accounting/owner-statements/preview`, payload);
}

export function generateOwnerStatement(
  payload: StatementGenerateIn
): Promise<OwnerStatementDetail> {
  return apiPost(`/api/accounting/owner-statements/generate`, payload);
}

export function listOwnerStatements(
  filters: {
    owner_id?: number;
    date_from?: string;
    date_to?: string;
    limit?: number;
  } = {}
): Promise<OwnerStatementList> {
  return apiGet(`/api/accounting/owner-statements${qs(filters)}`);
}

export function getOwnerStatement(
  id: number
): Promise<OwnerStatementDetail> {
  return apiGet(`/api/accounting/owner-statements/${id}`);
}