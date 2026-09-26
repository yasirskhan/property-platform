import { apiGet, apiPost, apiPut, apiDelete } from "@/lib/api";

export type ReportTier = "STANDARD" | "ENHANCED";
export type ReportPresentation = "BUTTON" | "TAB";

export type ReportDefinition = {
  key: string;
  title: string;
  category: string;
  tier: ReportTier;
  presentation: ReportPresentation;
  available: boolean;
  href: string | null;
  description: string | null;
};

export type ReportCatalog = {
  accounting_basis: "ACCRUAL" | "CASH";
  standard: ReportDefinition[];
  enhanced: ReportDefinition[];
};

export async function getReportCatalog(): Promise<ReportCatalog> {
  return apiGet("/api/reporting/catalog");
}


export type SavedReportParameters = Record<string, string | number | boolean | null>;
export type SavedReport = {
  id: number;
  organization_id: number;
  name: string;
  report_key: string;
  parameters: SavedReportParameters;
  created_at: string;
  updated_at: string;
};
export type SavedReportInput = Pick<SavedReport, "name" | "report_key" | "parameters">;

export async function getSavedReports(): Promise<{ items: SavedReport[]; total: number }> {
  return apiGet("/api/reporting/saved");
}

export async function createSavedReport(payload: SavedReportInput): Promise<SavedReport> {
  return apiPost("/api/reporting/saved", payload);
}

export async function updateSavedReport(id: number, payload: SavedReportInput): Promise<SavedReport> {
  return apiPut(`/api/reporting/saved/${id}`, payload);
}

export async function deleteSavedReport(id: number): Promise<void> {
  await apiDelete(`/api/reporting/saved/${id}`);
}
