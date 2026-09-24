// ============================================================
// journalEntries.ts
// ------------------------------------------------------------
// Typed API client for Manual Journal Entries (Phase 2 Step 2b).
// ============================================================

import { apiGet, apiPatch, apiPost } from "@/lib/api";

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

export type RecurringJournalEntryLine = {
  id: number;
  gl_account_id: number;
  property_id: number | null;
  unit_id: number | null;
  owner_id: number | null;
  description: string | null;
  debit: string;
  credit: string;
};

export type RecurringJournalEntry = {
  id: number;
  organization_id: number;
  name: string;
  start_date: string;
  end_date: string | null;
  day_of_month: number;
  next_post_date: string;
  last_posted_date: string | null;
  reference_number: string | null;
  memo: string | null;
  is_active: boolean;
  created_by_id: number | null;
  created_at: string;
  updated_at: string;
  lines: RecurringJournalEntryLine[];
};

export type RecurringJournalEntryList = {
  items: RecurringJournalEntry[];
  total: number;
};

export type RecurringJournalEntryCreateIn = {
  name: string;
  start_date: string;
  end_date?: string | null;
  day_of_month: number;
  reference_number?: string | null;
  memo?: string | null;
  lines: JournalEntryLineIn[];
};

export function listRecurringJournalEntries(): Promise<RecurringJournalEntryList> {
  return apiGet("/api/accounting/journal-entries/recurring");
}

export function createRecurringJournalEntry(
  payload: RecurringJournalEntryCreateIn
): Promise<RecurringJournalEntry> {
  return apiPost("/api/accounting/journal-entries/recurring", payload);
}

export function setRecurringJournalEntryActive(
  id: number,
  isActive: boolean
): Promise<RecurringJournalEntry> {
  return apiPatch(
    `/api/accounting/journal-entries/recurring/${id}/status`,
    { is_active: isActive }
  );
}
