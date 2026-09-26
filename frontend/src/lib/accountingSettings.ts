import { apiGet, apiPut } from "@/lib/api";

export type AccountingGLAccountChoice = {
  id: number;
  gl_number: string;
  name: string;
  account_type: string;
};

export type AccountingKeyAccountSummary = {
  id: number;
  key_type: string;
  gl_account_id: number;
  gl_number: string;
  name: string;
};

export type AccountingCheckSetupSummary = {
  bank_account_id: number;
  bank_account_name: string;
  configured: boolean;
  next_check_number: number | null;
};

export type AccountingSettings = {
  organization_id: number;
  gpr_rent_gl_account_id: number | null;
  gpr_market_gl_account_id: number | null;
  gpr_loss_gain_gl_account_id: number | null;
  receipt_cash_gl_account_id: number | null;
  report_export_format: "CSV" | "EXCEL";
  fiscal_year_start_month: number;
  accounting_basis: "ACCRUAL" | "CASH";
  gpr_rent_gl_account: AccountingGLAccountChoice | null;
  gpr_market_gl_account: AccountingGLAccountChoice | null;
  gpr_loss_gain_gl_account: AccountingGLAccountChoice | null;
  receipt_cash_gl_account: AccountingGLAccountChoice | null;
  eligible_income_accounts: AccountingGLAccountChoice[];
  eligible_cash_accounts: AccountingGLAccountChoice[];
  key_accounts: AccountingKeyAccountSummary[];
  check_setups: AccountingCheckSetupSummary[];
};

export type AccountingSettingsUpdate = {
  gpr_rent_gl_account_id: number | null;
  gpr_market_gl_account_id: number | null;
  gpr_loss_gain_gl_account_id: number | null;
  receipt_cash_gl_account_id: number | null;
  report_export_format: "CSV" | "EXCEL";
  fiscal_year_start_month: number;
  accounting_basis: "ACCRUAL" | "CASH";
};

export function getAccountingSettings(): Promise<AccountingSettings> {
  return apiGet("/api/settings/accounting");
}

export function updateAccountingSettings(
  payload: AccountingSettingsUpdate
): Promise<AccountingSettings> {
  return apiPut("/api/settings/accounting", payload);
}
