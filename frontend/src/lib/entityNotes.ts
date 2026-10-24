import { apiGet, apiPost } from "@/lib/api";

export type EntityNote = {
  id: number;
  organization_id: number;
  entity_type: string;
  entity_id: number;
  body: string;
  created_by_id: number | null;
  created_by_name: string | null;
  created_at: string;
};

export type EntityNoteList = {
  items: EntityNote[];
  total: number;
};

export function listEntityNotes(
  entityType: string,
  entityId: number
): Promise<EntityNoteList> {
  return apiGet(
    `/api/notes/${encodeURIComponent(entityType)}/${entityId}`
  );
}

export function addEntityNote(
  entityType: string,
  entityId: number,
  body: string
): Promise<EntityNote> {
  return apiPost(
    `/api/notes/${encodeURIComponent(entityType)}/${entityId}`,
    { body }
  );
}
