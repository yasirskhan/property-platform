// ============================================================
// diagnostics.ts
// ------------------------------------------------------------
// Typed API client for the Financial Diagnostics report.
//
// One endpoint: GET /api/accounting/diagnostics
// ============================================================

import { apiGet, apiPost } from "@/lib/api";

// ------------------------------------------------------------
// Shapes
// ------------------------------------------------------------

export type DiagnosticDetail = Record<string, string | number | null>;

export type DiagnosticCheck = {
  key: string;
  label: string;
  passed: boolean;
  severity: "ok" | "warning" | "error";
  message: string;
  details: DiagnosticDetail[];
};

export type DiagnosticsReport = {
  checks: DiagnosticCheck[];
  passed_count: number;
  failed_count: number;
  error_count: number;
  warning_count: number;
  all_passed: boolean;
};

// ------------------------------------------------------------
// Endpoint
// ------------------------------------------------------------

export function getDiagnostics(): Promise<DiagnosticsReport> {
  return apiGet(`/api/accounting/diagnostics`);
}

export type RefundNegativeResult = {
  transaction_id: number;
  gl_account_id: number;
  gl_number: string;
  offset_gl_account_id: number;
  offset_gl_number: string;
  amount: string;
};

export function refundNegativeDiagnostic(
  glAccountId: number,
  transactionDate: string
): Promise<RefundNegativeResult> {
  return apiPost("/api/accounting/diagnostics/refund-negative", {
    gl_account_id: glAccountId,
    transaction_date: transactionDate,
  });
}
