// ============================================================
// managementFees.ts
// ------------------------------------------------------------
// Typed API client for Management Fees (Phase 2 Step 9).
//
// Preview: read-only calculation for the UI.
// Run: actually posts the fee to the GL.
// ============================================================

import { apiGet, apiPost, apiPut } from "@/lib/api";

// ------------------------------------------------------------
// Shapes
// ------------------------------------------------------------

export type EligibleIncomeLine = {
  receipt_id: number | null;
  transaction_id: number | null;
  transaction_date: string | null;
  gl_account_id: number;
  gl_account_number: string | null;
  gl_account_name: string | null;
  amount: string;
};

export type FeePreview = {
  property_id: number;
  property_name: string | null;
  period_start: string;
  period_end: string;

  rent_income_total: string;
  other_fee_income_total: string;

  rent_fee_pct: string;
  other_fee_pct: string;

  rent_fee_amount: string;
  other_fee_amount: string;
  total_fee: string;

  rent_lines: EligibleIncomeLine[];
  other_lines: EligibleIncomeLine[];

  can_run: boolean;
  reason: string | null;
};

export type ManagementFeeRun = {
  id: number;
  organization_id: number;
  property_id: number;
  property_name: string | null;

  period_start: string;
  period_end: string;

  rent_income_total: string;
  other_fee_income_total: string;
  rent_fee_pct: string;
  other_fee_pct: string;
  rent_fee_amount: string;
  other_fee_amount: string;
  total_fee: string;

  expense_gl_account_id: number;
  expense_gl_account_number: string | null;
  expense_gl_account_name: string | null;

  cash_gl_account_id: number;
  cash_gl_account_number: string | null;
  cash_gl_account_name: string | null;

  gl_transaction_id: number | null;
  notes: string | null;
  is_reversed: boolean;
  reversal_of_id: number | null;
  is_active: boolean;
  created_by_id: number | null;
  created_at: string | null;
  updated_at: string | null;
};

export type ManagementFeeRunList = {
  items: ManagementFeeRun[];
  total: number;
};

// ------------------------------------------------------------
// Write shapes
// ------------------------------------------------------------

export type FeePreviewIn = {
  property_id: number;
  period_start: string;
  period_end: string;
};

export type FeeRunIn = {
  property_id: number;
  period_start: string;
  period_end: string;
  expense_gl_account_id?: number | null;
  cash_gl_account_id?: number | null;
  notes?: string | null;
};

export type FeeReverseIn = {
  reversal_date: string;
  memo?: string | null;
};

export type OvercollectionStrategy =
  | "CREDITS_THEN_RECEIPTS"
  | "RECEIPTS_THEN_CREDITS";

export type OvercollectionStrategyState = {
  strategy: OvercollectionStrategy;
  label: string;
  recommended: boolean;
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

export function previewManagementFee(
  payload: FeePreviewIn
): Promise<FeePreview> {
  return apiPost(`/api/accounting/management-fees/preview`, payload);
}

export function runManagementFee(
  payload: FeeRunIn
): Promise<ManagementFeeRun> {
  return apiPost(`/api/accounting/management-fees/run`, payload);
}

export function listManagementFees(filters: {
  property_id?: number;
  date_from?: string;
  date_to?: string;
  include_reversed?: boolean;
  limit?: number;
} = {}): Promise<ManagementFeeRunList> {
  return apiGet(`/api/accounting/management-fees${qs(filters)}`);
}

export function getManagementFee(id: number): Promise<ManagementFeeRun> {
  return apiGet(`/api/accounting/management-fees/${id}`);
}

export function reverseManagementFee(
  id: number,
  payload: FeeReverseIn
): Promise<ManagementFeeRun> {
  return apiPost(`/api/accounting/management-fees/${id}/reverse`, payload);
}

export function getOvercollectionStrategy(): Promise<OvercollectionStrategyState> {
  return apiGet("/api/accounting/management-fees/overcollection-strategy");
}

export function updateOvercollectionStrategy(
  strategy: OvercollectionStrategy
): Promise<OvercollectionStrategyState> {
  return apiPut("/api/accounting/management-fees/overcollection-strategy", {
    strategy,
  });
}

export type ManagementFeeGPRCandidate = {
  unit_id: number;
  property_id: number;
  property_name: string;
  unit_number: string;
  lease_id: number | null;
  market_rent: string;
  scheduled_rent: string;
  loss_gain: string;
  already_posted: boolean;
  transaction_id: number | null;
};

export type ManagementFeeGPRCandidateList = {
  month: string;
  items: ManagementFeeGPRCandidate[];
  total: number;
  unposted: number;
};

export type ManagementFeeGPRPostResult = {
  month: string;
  posted: number;
  transaction_ids: number[];
};

export function listManagementFeeGPRCandidates(
  month: string
): Promise<ManagementFeeGPRCandidateList> {
  return apiGet(
    `/api/accounting/management-fees/post-gpr?month=${encodeURIComponent(month)}`
  );
}

export function postManagementFeeGPR(
  month: string,
  unitIds: number[]
): Promise<ManagementFeeGPRPostResult> {
  return apiPost("/api/accounting/management-fees/post-gpr", {
    month,
    unit_ids: unitIds,
  });
}


export type ManagementFeeExclusion = {
  receipt_id: number;
  receipt_date: string;
  receipt_type: string;
  amount: string;
  property_id: number | null;
  property_name: string | null;
  reference_number: string | null;
  source_name: string | null;
  remarks: string | null;
  is_reversed: boolean;
};

export type ManagementFeeExclusionList = {
  items: ManagementFeeExclusion[];
  total: number;
};

export function listManagementFeeExclusions(filters: {
  date_from?: string;
  date_to?: string;
  property_id?: number;
  include_reversed?: boolean;
  limit?: number;
} = {}): Promise<ManagementFeeExclusionList> {
  return apiGet(
    `/api/accounting/management-fees/exclusions${qs(filters)}`
  );
}
