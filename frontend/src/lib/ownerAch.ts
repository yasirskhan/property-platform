import { apiGet, apiPut } from "@/lib/api";

export type OwnerACH = {
  owner_id: number;
  configured: boolean;
  account_holder_name: string | null;
  bank_name: string | null;
  routing_last4: string | null;
  account_last4: string | null;
  account_type: "CHECKING" | "SAVINGS" | null;
  is_enabled: boolean;
  updated_at: string | null;
};

export type OwnerACHUpsert = {
  account_holder_name: string;
  bank_name: string | null;
  routing_number: string;
  account_number: string;
  account_type: "CHECKING" | "SAVINGS";
  is_enabled: boolean;
};

export function getOwnerACH(ownerId: number): Promise<OwnerACH> {
  return apiGet(`/api/accounting/owners/${ownerId}/ach`);
}

export function saveOwnerACH(
  ownerId: number,
  payload: OwnerACHUpsert,
): Promise<OwnerACH> {
  return apiPut(`/api/accounting/owners/${ownerId}/ach`, payload);
}
