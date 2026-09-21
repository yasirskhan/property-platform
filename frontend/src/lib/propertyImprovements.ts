// ============================================================
// propertyImprovements.ts
// ------------------------------------------------------------
// Typed API client for Property Improvements (Phase 3 Step 3c).
// ============================================================

import { apiGet, apiPost, apiPatch, apiDelete } from "@/lib/api";

export type PropertyImprovement = {
  id: number;
  organization_id: number;
  property_id: number;
  improvement_date: string;
  description: string;
  cost: string | null;
  contractor: string | null;
  category: string | null;
  notes: string | null;
  is_active: boolean;
  created_by_id: number | null;
  created_at: string | null;
  updated_at: string | null;
};

export type PropertyImprovementList = {
  items: PropertyImprovement[];
  total: number;
};

export type PropertyImprovementCreateIn = {
  property_id: number;
  improvement_date: string;
  description: string;
  cost?: number | string | null;
  contractor?: string | null;
  category?: string | null;
  notes?: string | null;
};

export type PropertyImprovementUpdateIn = {
  improvement_date?: string;
  description?: string;
  cost?: number | string | null;
  contractor?: string | null;
  category?: string | null;
  notes?: string | null;
  is_active?: boolean;
};

export function listImprovements(
  propertyId: number,
  includeInactive = false
): Promise<PropertyImprovementList> {
  const q = includeInactive ? "?include_inactive=true" : "";
  return apiGet(`/api/properties/${propertyId}/improvements${q}`);
}

export function createImprovement(
  propertyId: number,
  payload: Omit<PropertyImprovementCreateIn, "property_id">
): Promise<PropertyImprovement> {
  return apiPost(`/api/properties/${propertyId}/improvements`, {
    ...payload,
    property_id: propertyId,
  });
}

export function updateImprovement(
  propertyId: number,
  improvementId: number,
  payload: PropertyImprovementUpdateIn
): Promise<PropertyImprovement> {
  return apiPatch(
    `/api/properties/${propertyId}/improvements/${improvementId}`,
    payload
  );
}

export function deleteImprovement(
  propertyId: number,
  improvementId: number
): Promise<null> {
  return apiDelete(
    `/api/properties/${propertyId}/improvements/${improvementId}`
  );
}