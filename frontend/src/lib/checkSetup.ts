import { apiGet, apiPut } from "@/lib/api";
export type BankCheckSetup = {id:number|null;organization_id:number;bank_account_id:number;bank_account_name:string;next_check_number:number;check_number_prefix:string|null;check_stock_position:"TOP"|"MIDDLE"|"BOTTOM";memo_line_enabled:boolean;signature_line_enabled:boolean;created_at:string|null;updated_at:string|null};
export type BankCheckSetupUpdate = {next_check_number:number;check_number_prefix:string|null;check_stock_position:"TOP"|"MIDDLE"|"BOTTOM";memo_line_enabled:boolean;signature_line_enabled:boolean};
export const getCheckSetup=(bankId:number)=>apiGet(`/api/accounting/bank-accounts/${bankId}/check-setup`) as Promise<BankCheckSetup>;
export const updateCheckSetup=(bankId:number,payload:BankCheckSetupUpdate)=>apiPut(`/api/accounting/bank-accounts/${bankId}/check-setup`,payload) as Promise<BankCheckSetup>;
