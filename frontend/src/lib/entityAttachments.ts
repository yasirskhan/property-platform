import { apiDelete, apiGet, apiPatch, getToken } from "@/lib/api";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

export type EntityAttachment = {
  id: number;
  organization_id: number;
  entity_type: string;
  entity_id: number;
  original_name: string;
  content_type: string;
  size_bytes: number;
  share_with_tenants: boolean;
  share_with_owners: boolean;
  uploaded_by_id: number | null;
  uploaded_by_name: string | null;
  created_at: string;
};

export type EntityAttachmentList = { items: EntityAttachment[]; total: number };

export function listEntityAttachments(entityType: string, entityId: number): Promise<EntityAttachmentList> {
  return apiGet(`/api/attachments/${encodeURIComponent(entityType)}/${entityId}`);
}

export async function uploadEntityAttachment(
  entityType: string,
  entityId: number,
  file: File,
  shareWithTenants: boolean,
  shareWithOwners: boolean
): Promise<EntityAttachment> {
  const form = new FormData();
  form.append("file", file);
  form.append("share_with_tenants", String(shareWithTenants));
  form.append("share_with_owners", String(shareWithOwners));
  const token = getToken();
  const headers: HeadersInit = {};
  if (token) (headers as Record<string, string>)["Authorization"] = `Bearer ${token}`;
  const response = await fetch(
    `${API_URL}/api/attachments/${encodeURIComponent(entityType)}/${entityId}`,
    { method: "POST", headers, body: form }
  );
  if (!response.ok) throw new Error(await attachmentError(response));
  return response.json();
}

export function updateAttachmentSharing(
  attachmentId: number,
  values: { share_with_tenants?: boolean; share_with_owners?: boolean }
): Promise<EntityAttachment> {
  return apiPatch(`/api/attachments/item/${attachmentId}`, values);
}

export function deleteEntityAttachment(attachmentId: number): Promise<null> {
  return apiDelete(`/api/attachments/item/${attachmentId}`);
}

export async function downloadEntityAttachment(attachmentId: number, filename: string): Promise<void> {
  const token = getToken();
  const headers: HeadersInit = {};
  if (token) (headers as Record<string, string>)["Authorization"] = `Bearer ${token}`;
  const response = await fetch(`${API_URL}/api/attachments/download/${attachmentId}`, { headers });
  if (!response.ok) throw new Error(await attachmentError(response));
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

async function attachmentError(response: Response): Promise<string> {
  try {
    const data = await response.json();
    if (typeof data.detail === "string") return data.detail;
  } catch {}
  return `Request failed (${response.status})`;
}
