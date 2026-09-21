// ============================================================
// propertyAmenities.ts
// ------------------------------------------------------------
// Typed API client for Property Amenities (Phase 3 Step 3a).
// ============================================================

import { apiGet, apiPost, apiPatch, apiDelete } from "@/lib/api";

// ------------------------------------------------------------
// Shapes
// ------------------------------------------------------------

export type PropertyAmenity = {
  id: number;
  organization_id: number;
  property_id: number;
  name: string;
  category: string | null;
  notes: string | null;
  is_active: boolean;
  created_by_id: number | null;
  created_at: string | null;
  updated_at: string | null;
};

export type PropertyAmenityList = {
  items: PropertyAmenity[];
  total: number;
};

// ------------------------------------------------------------
// Write shapes
// ------------------------------------------------------------

export type PropertyAmenityCreateIn = {
  property_id: number;
  name: string;
  category?: string | null;
  notes?: string | null;
};

export type PropertyAmenityUpdateIn = {
  name?: string;
  category?: string | null;
  notes?: string | null;
  is_active?: boolean;
};

// ------------------------------------------------------------
// Endpoints
// ------------------------------------------------------------

export function listAmenities(
  propertyId: number,
  includeInactive = false
): Promise<PropertyAmenityList> {
  const q = includeInactive ? "?include_inactive=true" : "";
  return apiGet(`/api/properties/${propertyId}/amenities${q}`);
}

export function createAmenity(
  propertyId: number,
  payload: Omit<PropertyAmenityCreateIn, "property_id">
): Promise<PropertyAmenity> {
  return apiPost(`/api/properties/${propertyId}/amenities`, {
    ...payload,
    property_id: propertyId,
  });
}

export function updateAmenity(
  propertyId: number,
  amenityId: number,
  payload: PropertyAmenityUpdateIn
): Promise<PropertyAmenity> {
  return apiPatch(
    `/api/properties/${propertyId}/amenities/${amenityId}`,
    payload
  );
}

export function deleteAmenity(
  propertyId: number,
  amenityId: number
): Promise<null> {
  return apiDelete(
    `/api/properties/${propertyId}/amenities/${amenityId}`
  );
}