import { apiDelete, apiGet, apiPost } from "@/lib/api";

export type DepositGLAccount = {
  gl_account_id: number;
  gl_number: string;
  name: string;
  offset_account: string | null;
};

export type DepositKeyAccount = DepositGLAccount & {
  id: number;
  organization_id: number;
  created_at: string;
};

export type OwnerHeldDepositSetup = {
  operating_cash_gl_number: string;
  key_accounts: DepositKeyAccount[];
  eligible_accounts: DepositGLAccount[];
};

export function getOwnerHeldDepositSetup(): Promise<OwnerHeldDepositSetup> {
  return apiGet("/api/accounting/owner-held-security-deposits");
}

export function addOwnerHeldDepositKeyAccount(
  glAccountId: number
): Promise<DepositKeyAccount> {
  return apiPost("/api/accounting/owner-held-security-deposits/key-accounts", {
    gl_account_id: glAccountId,
  });
}

export function removeOwnerHeldDepositKeyAccount(id: number): Promise<null> {
  return apiDelete(
    `/api/accounting/owner-held-security-deposits/key-accounts/${id}`
  );
}
