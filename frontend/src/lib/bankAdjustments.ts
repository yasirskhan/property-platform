import { apiGet, apiPost } from "@/lib/api";

export type BankAdjustment = {
  id: number;
  bank_account_id: number;
  bank_account_name: string;
  transaction_date: string;
  posted_at: string;
  direction: "INCREASE" | "DECREASE";
  amount: string;
  signed_amount: string;
  offset_gl_account_id: number;
  offset_gl_account_number: string | null;
  offset_gl_account_name: string | null;
  reference_number: string | null;
  memo: string | null;
  is_reversed: boolean;
  created_by_id: number | null;
};

export type BankAdjustmentList = {
  items: BankAdjustment[];
  total: number;
};

export type BankAdjustmentCreate = {
  adjustment_date: string;
  direction: "INCREASE" | "DECREASE";
  amount: string | number;
  offset_gl_account_id: number;
  reference_number?: string | null;
  memo?: string | null;
};

export type BankAdjustmentReverse = {
  reversal_date: string;
  memo?: string | null;
};

export function listBankAdjustments(
  bankAccountId: number
): Promise<BankAdjustmentList> {
  return apiGet(
    `/api/accounting/bank-accounts/${bankAccountId}/adjustments`
  ) as Promise<BankAdjustmentList>;
}

export function createBankAdjustment(
  bankAccountId: number,
  payload: BankAdjustmentCreate
): Promise<BankAdjustment> {
  return apiPost(
    `/api/accounting/bank-accounts/${bankAccountId}/adjustments`,
    payload
  ) as Promise<BankAdjustment>;
}

export function reverseBankAdjustment(
  bankAccountId: number,
  transactionId: number,
  payload: BankAdjustmentReverse
): Promise<BankAdjustment> {
  return apiPost(
    `/api/accounting/bank-accounts/${bankAccountId}/adjustments/${transactionId}/reverse`,
    payload
  ) as Promise<BankAdjustment>;
}
