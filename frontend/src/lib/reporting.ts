import { apiGet } from "@/lib/api";

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
