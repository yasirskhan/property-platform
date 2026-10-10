import{apiGet,apiPost,apiPut}from"@/lib/api";
export type ReconciliationItem={id:number;source_type:string;source_id:number;transaction_date:string;description:string|null;reference_number:string|null;signed_amount:string;cleared:boolean};
export type StatementLine={id:number;posted_date:string;amount:string;payee:string|null;memo:string|null;reference_number:string|null;matched_item_id:number|null};
export type Reconciliation={id:number;organization_id:number;bank_account_id:number;bank_account_name:string|null;statement_date:string;beginning_balance:string;ending_statement_balance:string;cleared_balance:string;difference:string;balanced:boolean;status:string;finished_at:string|null;items:ReconciliationItem[];statement_lines:StatementLine[]};
export const getCurrentReconciliation=(bankId:number)=>apiGet(`/api/accounting/bank-accounts/${bankId}/reconciliations/current`) as Promise<Reconciliation>;
export const startReconciliation=(bankId:number,payload:{statement_date:string;ending_statement_balance:string|number})=>apiPost(`/api/accounting/bank-accounts/${bankId}/reconciliations`,payload) as Promise<Reconciliation>;
export const setReconciliationSelection=(bankId:number,reconId:number,ids:number[])=>apiPut(`/api/accounting/bank-accounts/${bankId}/reconciliations/${reconId}/selection`,{cleared_item_ids:ids}) as Promise<Reconciliation>;
export const finishReconciliation=(bankId:number,reconId:number)=>apiPost(`/api/accounting/bank-accounts/${bankId}/reconciliations/${reconId}/finish`,{}) as Promise<Reconciliation>;
export const importQIF=(bankId:number,reconId:number,content:string)=>apiPost(`/api/accounting/bank-accounts/${bankId}/reconciliations/${reconId}/qif`,{content}) as Promise<{imported:number;matched:number;reconciliation:Reconciliation}>;
