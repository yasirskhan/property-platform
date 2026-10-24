import { apiGet, getToken } from "@/lib/api";

export type AuditCenterItem = {
  id: number; actor_type: "customer" | "platform" | "system"; actor_id: number | null;
  actor_name: string; actor_email: string | null; entity_type: string; entity_id: number;
  action: string; field_name: string | null; old_value: string | null; new_value: string | null;
  ip_address: string | null; created_at: string;
};
export type AuditCenterList = { items: AuditCenterItem[]; total: number; limit: number; offset: number };
export type AuditCenterFilters = { entity_type?: string; action?: string; actor_user_id?: number; date_from?: string; date_to?: string; search?: string; limit?: number; offset?: number };

function params(filters: AuditCenterFilters): string {
  const q=new URLSearchParams();
  Object.entries(filters).forEach(([k,v])=>{if(v!==undefined&&v!==null&&String(v)!=="") q.set(k,String(v));});
  return q.toString();
}
export function listAuditEvents(filters: AuditCenterFilters): Promise<AuditCenterList> {
  const q=params(filters); return apiGet(`/api/settings/audit${q?`?${q}`:""}`);
}
export async function downloadAuditCsv(filters: AuditCenterFilters): Promise<void> {
  const q=params(filters);
  const response=await fetch(`http://127.0.0.1:8000/api/settings/audit/export.csv${q?`?${q}`:""}`,{headers:{Authorization:`Bearer ${getToken()||""}`}});
  if(!response.ok){const data=await response.json().catch(()=>({}));throw new Error(data.detail||"Audit export failed");}
  const blob=await response.blob(), url=URL.createObjectURL(blob), link=document.createElement("a");
  link.href=url; link.download="audit-log.csv"; document.body.appendChild(link); link.click(); link.remove(); URL.revokeObjectURL(url);
}
