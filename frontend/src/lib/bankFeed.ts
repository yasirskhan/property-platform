import { apiGet, apiPost } from "@/lib/api";

export type BankFeedStatus = "MATCHED" | "UNMATCHED";

export type BankFeedTransaction = {
  id: number;
  bank_account_id: number;
  posted_date: string;
  amount: string;
  payee: string | null;
  description: string | null;
  memo: string | null;
  reference_number: string | null;
  source_provider: string;
  external_id: string | null;
  status: BankFeedStatus;
  matched_source_type: string | null;
  matched_source_id: number | null;
  created_at: string;
};

export type BankFeedList = {
  items: BankFeedTransaction[];
  total: number;
};

export type BankFeedImportResult = {
  imported: number;
  duplicates: number;
  matched: number;
  total: number;
};

export type BankFeedRematchResult = {
  matched: number;
  remaining_unmatched: number;
};

export function listBankFeed(
  bankAccountId: number,
  status?: BankFeedStatus
): Promise<BankFeedList> {
  const query = status ? `?status_filter=${encodeURIComponent(status)}` : "";
  return apiGet(
    `/api/accounting/bank-accounts/${bankAccountId}/bank-feed${query}`
  ) as Promise<BankFeedList>;
}

export function importBankFeed(
  bankAccountId: number,
  content: string
): Promise<BankFeedImportResult> {
  return apiPost(
    `/api/accounting/bank-accounts/${bankAccountId}/bank-feed/import`,
    { content }
  ) as Promise<BankFeedImportResult>;
}

export function rematchBankFeed(
  bankAccountId: number
): Promise<BankFeedRematchResult> {
  return apiPost(
    `/api/accounting/bank-accounts/${bankAccountId}/bank-feed/rematch`
  ) as Promise<BankFeedRematchResult>;
}
