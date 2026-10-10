import { apiGet, apiPost } from "@/lib/api";

export type OwnerPayoutCandidate = {
  owner_id: number;
  owner_name: string;
  owner_email: string;
  available_balance: string;
  ach_configured: boolean;
  ach_enabled: boolean;
  account_last4: string | null;
  can_pay: boolean;
  reason: string | null;
};

export type OwnerPayoutPreview = {
  bank_account_id: number;
  bank_account_name: string;
  book_balance: string;
  candidates: OwnerPayoutCandidate[];
};

export type OwnerPayout = {
  id: number;
  batch_reference: string;
  owner_id: number;
  owner_name: string;
  owner_email: string;
  bank_account_id: number;
  bank_account_name: string;
  effective_date: string;
  amount: string;
  destination_last4: string;
  status: string;
  gl_transaction_id: number | null;
  created_by_id: number | null;
  confirmed_by_id: number | null;
  created_at: string | null;
  confirmed_at: string | null;
};

export type OwnerPayoutDraft = {
  batch_reference: string;
  entry_count: number;
  total_amount: string;
  funds_moved: boolean;
  accounting_posted: boolean;
  payouts: OwnerPayout[];
};

export type OwnerPayoutConfirm = {
  batch_reference: string;
  entry_count: number;
  total_amount: string;
  funds_moved_by_app: boolean;
  externally_confirmed: boolean;
  accounting_posted: boolean;
  payouts: OwnerPayout[];
};

export type OwnerPayoutList = {
  items: OwnerPayout[];
  total: number;
};

export type OwnerPayoutDraftIn = {
  bank_account_id: number;
  effective_date: string;
  payouts: Array<{ owner_id: number; amount: string }>;
};

export function previewOwnerPayouts(
  bankAccountId: number
): Promise<OwnerPayoutPreview> {
  return apiGet(
    "/api/accounting/owner-payouts/preview?bank_account_id=" +
      encodeURIComponent(String(bankAccountId))
  );
}

export function createOwnerPayoutDraft(
  payload: OwnerPayoutDraftIn
): Promise<OwnerPayoutDraft> {
  return apiPost("/api/accounting/owner-payouts/draft", payload);
}

export function confirmOwnerPayoutBatch(
  batchReference: string,
  confirmationDate: string
): Promise<OwnerPayoutConfirm> {
  return apiPost(
    "/api/accounting/owner-payouts/" +
      encodeURIComponent(batchReference) +
      "/confirm-external-payment",
    { confirmation_date: confirmationDate }
  );
}

export function listOwnerPayouts(limit = 100): Promise<OwnerPayoutList> {
  return apiGet(
    "/api/accounting/owner-payouts?limit=" +
      encodeURIComponent(String(limit))
  );
}
