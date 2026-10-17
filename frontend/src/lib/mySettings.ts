import { apiGet, apiPut } from "@/lib/api";

export type MySettings = {
  user_id: number;
  organization_id: number;
  email_notifications_enabled: boolean;
  email_signature: string | null;
  reply_to_email: string | null;
  language_override: string | null;
  export_format_override: "CSV" | "EXCEL" | null;
};

export type MySettingsUpdate = {
  email_notifications_enabled: boolean;
  email_signature: string | null;
  reply_to_email: string | null;
  language_override: string | null;
  export_format_override: "CSV" | "EXCEL" | null;
};

export function getMySettings(): Promise<MySettings> {
  return apiGet("/api/settings/my");
}

export function updateMySettings(payload: MySettingsUpdate): Promise<MySettings> {
  return apiPut("/api/settings/my", payload);
}
