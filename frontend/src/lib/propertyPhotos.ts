// ============================================================
// propertyPhotos.ts
// ------------------------------------------------------------
// Typed API client for Property Photos.
// Two-step upload: apiUpload(file) -> then createPhoto(...)
// ============================================================

import { apiGet, apiPost, apiPatch, apiDelete } from "@/lib/api";

export type PropertyPhoto = {
  id: number;
  organization_id: number;
  property_id: number;
  url: string;
  filename: string;
  original_name: string | null;
  content_type: string | null;
  size_bytes: number | null;
  caption: string | null;
  is_marketing: boolean;
  is_cover: boolean;
  sort_order: number;
  is_active: boolean;
  delete_reason: string | null;
  created_by_id: number | null;
  created_at: string | null;
  updated_at: string | null;
};

export type PropertyPhotoList = {
  items: PropertyPhoto[];
  total: number;
};

export type PropertyPhotoCreateIn = {
  property_id: number;
  url: string;
  filename: string;
  original_name?: string | null;
  content_type?: string | null;
  size_bytes?: number | null;
  caption?: string | null;
  is_marketing?: boolean;
  is_cover?: boolean;
  sort_order?: number;
};

export type PropertyPhotoUpdateIn = {
  caption?: string | null;
  is_marketing?: boolean;
  is_cover?: boolean;
  sort_order?: number;
  is_active?: boolean;
  delete_reason?: string | null;
};

export function listPhotos(
  propertyId: number,
  includeInactive = false
): Promise<PropertyPhotoList> {
  const q = includeInactive ? "?include_inactive=true" : "";
  return apiGet(`/api/properties/${propertyId}/photos${q}`);
}

export function createPhoto(
  propertyId: number,
  payload: Omit<PropertyPhotoCreateIn, "property_id">
): Promise<PropertyPhoto> {
  return apiPost(`/api/properties/${propertyId}/photos`, {
    ...payload,
    property_id: propertyId,
  });
}

export function updatePhoto(
  propertyId: number,
  photoId: number,
  payload: PropertyPhotoUpdateIn
): Promise<PropertyPhoto> {
  return apiPatch(
    `/api/properties/${propertyId}/photos/${photoId}`,
    payload
  );
}

export function deletePhoto(
  propertyId: number,
  photoId: number
): Promise<null> {
  return apiDelete(
    `/api/properties/${propertyId}/photos/${photoId}`
  );
}