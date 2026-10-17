// ============================================================
// propertyAppliances.ts
// AppFolio-parity field: condition.
// ============================================================

import { apiGet, apiPost, apiPatch, apiDelete } from "@/lib/api";

export type PropertyApplianceCondition =
  | "NEW"
  | "GOOD"
  | "FAIR"
  | "NEEDS_REPAIR";

export type PropertyAppliance = {
  id: number;
  organization_id: number;
  property_id: number;
  name: string;
  brand: string | null;
  model_number: string | null;
  serial_number: string | null;
  purchase_date: string | null;
  purchase_price: string | null;
  warranty_expires: string | null;
  condition: PropertyApplianceCondition | null;
  notes: string | null;
  is_active: boolean;
  delete_reason: string | null;
  created_by_id: number | null;
  created_at: string | null;
  updated_at: string | null;
};

export type PropertyApplianceList = {
  items: PropertyAppliance[];
  total: number;
};

export type PropertyApplianceCreateIn = {
  property_id: number;
  name: string;
  brand?: string | null;
  model_number?: string | null;
  serial_number?: string | null;
  purchase_date?: string | null;
  purchase_price?: number | string | null;
  warranty_expires?: string | null;
  condition?: PropertyApplianceCondition | null;
  notes?: string | null;
};

export type PropertyApplianceUpdateIn = {
  name?: string;
  brand?: string | null;
  model_number?: string | null;
  serial_number?: string | null;
  purchase_date?: string | null;
  purchase_price?: number | string | null;
  warranty_expires?: string | null;
  condition?: PropertyApplianceCondition | null;
  notes?: string | null;
  is_active?: boolean;
  delete_reason?: string | null;
};

export function listAppliances(
  propertyId: number,
  includeInactive = false
): Promise<PropertyApplianceList> {
  const q = includeInactive ? "?include_inactive=true" : "";
  return apiGet(`/api/properties/${propertyId}/appliances${q}`);
}

export function createAppliance(
  propertyId: number,
  payload: Omit<PropertyApplianceCreateIn, "property_id">
): Promise<PropertyAppliance> {
  return apiPost(`/api/properties/${propertyId}/appliances`, {
    ...payload,
    property_id: propertyId,
  });
}

export function updateAppliance(
  propertyId: number,
  applianceId: number,
  payload: PropertyApplianceUpdateIn
): Promise<PropertyAppliance> {
  return apiPatch(
    `/api/properties/${propertyId}/appliances/${applianceId}`,
    payload
  );
}

export function deleteAppliance(
  propertyId: number,
  applianceId: number,
  reason: string
): Promise<null> {
  return apiDelete(
    `/api/properties/${propertyId}/appliances/${applianceId}?reason=${encodeURIComponent(reason.trim())}`
  );
}