// ============================================================
// journalEntries.ts
// ------------------------------------------------------------
// Typed API client for Manual Journal Entries (Phase 2 Step 2b).
// ============================================================

import { apiGet, apiPost } from "@/lib/api";

// ------------------------------------------------------------
// Shapes
// ------------------------------------------------------------

export type JournalEntryLineIn = {
  gl_account_id: number;
  property_id?: number | null;
  unit_id?: number | null;
  owner_id?: number | null;
  description?: string | null;
  debit?: number | string;
  credit?: number | string;
};

export type JournalEntryCreateIn = {
  transaction_date: string;
  reference_number?: string | null;
  memo?: string | null;
  lines: JournalEntryLineIn[];
};

export type JournalEntry = {
  id: number;
  organization_id: number;
  transaction_date: string;
  posted_at: string | null;
  transaction_type: string;
  reference_number: string | null;
  memo: string | null;
  source_type: string | null;
  source_id: number | null;
  created_by_id: number | null;
  is_reversed: boolean;
  reversal_of_id: number | null;
  created_at: string | null;
  updated_at: string | null;
};

export type JournalEntryList = {
  items: JournalEntry[];
  total: number;
};

// ------------------------------------------------------------
// Helpers
// ------------------------------------------------------------

function qs(
  params: Record<string, string | number | boolean | undefined | null>
): string {
  const parts: string[] = [];
  for (const [k, v] of Object.entries(params)) {
    if (v === undefined || v === null || v === "") continue;
    parts.push(`${encodeURIComponent(k)}=${encodeURIComponent(String(v))}`);
  }
  return parts.length ? `?${parts.join("&")}` : "";
}

// ------------------------------------------------------------
// Endpoints
// ------------------------------------------------------------

export function listJournalEntries(
  filters: {
    date_from?: string;
    date_to?: string;
    include_reversed?: boolean;
    limit?: number;
  } = {}
): Promise<JournalEntryList> {
  return apiGet(`/api/accounting/journal-entries${qs(filters)}`);
}

export function createJournalEntry(
  payload: JournalEntryCreateIn
): Promise<JournalEntry> {
  return apiPost(`/api/accounting/journal-entries`, payload);
}