import { apiPost } from "@/lib/api";

export type ACHEntry = {
  recipient_name: string;
  routing_number: string;
  account_number: string;
  account_type: "CHECKING" | "SAVINGS";
  amount: number;
  identification?: string | null;
};

export type ACHGenerateResult = {
  format: "CSV" | "NACHA";
  filename: string;
  content_type: string;
  content: string;
  entry_count: number;
  total_amount: string;
};

export function generateACHFile(
  bankId: number,
  payload: {
    effective_date: string;
    company_id?: string | null;
    entry_description: string;
    entries: ACHEntry[];
  }
): Promise<ACHGenerateResult> {
  return apiPost(`/api/accounting/bank-accounts/${bankId}/ach-file`, payload);
}
