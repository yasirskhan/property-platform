"use client";

import { useEffect, useState } from "react";
import { apiGet, apiPut } from "@/lib/api";
import HoaReserveMovementPlans from "@/components/property/HoaReserveMovementPlans";

type Option = {
  gl_account_id: number;
  gl_number: string;
  gl_name: string;
  bank_account_id: number | null;
  bank_display_name: string | null;
};
type Record = {
  id: number;
  gl_account_id: number;
  gl_number: string;
  gl_name: string;
  bank_account_id: number | null;
  bank_display_name: string | null;
  mapping_status: string;
  status: "STAFF_MAPPED_UNVERIFIED";
  posting_enabled: false;
};
type Book = Record & {
  as_of: string;
  account_wide_book_balance: string;
  property_tagged_book_balance: string;
  unallocated_or_other_property_balance: string;
  attribution_status: string;
  bank_statement_reconciled: false;
  legal_reserve_ownership_verified: false;
};

export default function HoaReserveBookPanel({
  associationId, propertyId, canEdit, onClose,
}: {
  associationId: number;
  propertyId: number;
  canEdit: boolean;
  onClose: () => void;
}) {
  const [saved, setSaved] = useState<Record | null>(null);
  const [options, setOptions] = useState<Option[]>([]);
  const [selected, setSelected] = useState("");
  const [bankMapped, setBankMapped] = useState(false);
  const [asOf, setAsOf] = useState("");
  const [book, setBook] = useState<Book | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const root = "/api/hoa/associations/" + associationId;
  const query = "?property_id=" + propertyId;

  useEffect(() => {
    let live = true;
    setLoading(true); setError(""); setBook(null);
    void Promise.all([
      apiGet(root + "/reserve-account" + query) as Promise<Record | null>,
      canEdit
        ? apiGet(root + "/reserve-options" + query) as Promise<Option[]>
        : Promise.resolve([]),
    ]).then(([record, available]) => {
      if (!live) return;
      setSaved(record); setOptions(available);
      setSelected(record ? String(record.gl_account_id) : "");
      setBankMapped(Boolean(record?.bank_account_id));
    }).catch((cause) => {
      if (live) setError(cause instanceof Error ? cause.message : "Reserve mapping unavailable.");
    }).finally(() => { if (live) setLoading(false); });
    return () => { live = false; };
  }, [root, query, canEdit]);

  async function save(event: React.FormEvent) {
    event.preventDefault();
    if (!canEdit || !selected || busy) return;
    const candidate = options.find((item) => item.gl_account_id === Number(selected));
    if (!candidate) return;
    setBusy(true); setError(""); setMessage(""); setBook(null);
    try {
      const result = await apiPut(root + "/reserve-account", {
        property_id: propertyId,
        gl_account_id: candidate.gl_account_id,
        bank_account_id: bankMapped ? candidate.bank_account_id : null,
      }) as Record;
      setSaved(result);
      setMessage("Staff GL reference recorded; no financial posting or bank movement occurred.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Cannot record reserve mapping.");
    } finally { setBusy(false); }
  }

  async function loadBook() {
    if (!asOf || !saved || !canEdit || busy) return;
    setBusy(true); setError(""); setBook(null);
    try {
      const params = new URLSearchParams({ property_id: String(propertyId), as_of: asOf });
      const result = await apiGet(root + "/reserve-book?" + params.toString()) as Book;
      setBook(result);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Read-only reserve book unavailable.");
    } finally { setBusy(false); }
  }

  const candidate = options.find((item) => item.gl_account_id === Number(selected));

  return (
    <section className="w-full space-y-3 rounded border bg-slate-50 p-4">
      <div className="flex items-center justify-between gap-2">
        <h3 className="text-sm font-semibold">HOA reserve book readiness</h3>
        <button type="button" onClick={onClose} className="text-blue-700">Close</button>
      </div>
      <p className="text-xs text-amber-800">
        A staff-scoped reference to an existing dedicated ASSET GL, not a
        certified reserve fund. Recorded posted GL activity is not a bank
        statement, statutory reserve, transfer approval, reconciliation or
        property-specific ownership proof. No bank account or routing
        numbers are displayed, and no money is moved or posted here.
      </p>
      {loading && <p className="text-xs">Loading…</p>}
      {error && <p role="alert" className="text-xs text-red-700">{error}</p>}
      {message && <p role="status" className="text-xs text-green-700">{message}</p>}
      {!loading && saved && (
        <div className="space-y-1 rounded border bg-white p-3 text-sm">
          <p className="font-medium">{saved.gl_number} · {saved.gl_name}</p>
          <p className="text-xs">
            {saved.bank_display_name ? "Recorded bank: " + saved.bank_display_name : "No bank mapping recorded"}
          </p>
          <p className="text-xs text-slate-600">{saved.mapping_status.replaceAll("_", " ")}</p>
          <p className="text-xs text-amber-900">Staff-mapped/unverified · Posting disabled</p>
        </div>
      )}
      {!loading && !saved && <p className="text-xs text-slate-600">No reserve GL reference recorded for this property.</p>}
      {canEdit && !loading && (
        <form onSubmit={(event) => { void save(event); }} className="space-y-2 border-t pt-3">
          <p className="text-xs">
            Choose a dedicated existing cash-like ASSET account. Other HOA
            references cannot reuse this GL. Configure a new cash account
            through the existing Chart of Accounts if needed.
          </p>
          <label className="block text-xs">Existing same-organization GL
            <select value={selected} required
              onChange={(event) => { setSelected(event.target.value); setBankMapped(false); setBook(null); }}
              className="mt-1 block w-full rounded border bg-white p-2">
              <option value="">Select a cash-like ASSET GL</option>
              {options.map((item) => (
                <option key={item.gl_account_id} value={item.gl_account_id}>
                  {item.gl_number} · {item.gl_name}
                </option>
              ))}
            </select>
          </label>
          {candidate?.bank_account_id && (
            <label className="flex items-center gap-2 text-xs">
              <input type="checkbox" checked={bankMapped}
                onChange={(event) => setBankMapped(event.target.checked)} />
              Link recorded bank display name: {candidate.bank_display_name}
            </label>
          )}
          <button type="submit" disabled={!selected || busy}
            className="rounded bg-slate-900 px-3 py-2 text-sm text-white disabled:opacity-50">
            {busy ? "Saving…" : "Record reserve GL reference"}
          </button>
        </form>
      )}
      {saved && canEdit && (
        <div className="space-y-2 border-t pt-3 text-xs">
          <label className="block">Book activity as of
            <input type="date" value={asOf}
              onChange={(event) => { setAsOf(event.target.value); setBook(null); }}
              className="mt-1 block rounded border p-2" />
          </label>
          <button type="button" disabled={!asOf || busy}
            onClick={() => { void loadBook(); }}
            className="rounded border bg-white px-3 py-2 disabled:opacity-50">
            Read posted GL book only
          </button>
          {book && (
            <div className="space-y-1 rounded border bg-white p-3">
              <p>Account-wide posted book: {book.account_wide_book_balance}</p>
              <p>Same-property GL-tagged book: {book.property_tagged_book_balance}</p>
              <p>Other/untagged GL book: {book.unallocated_or_other_property_balance}</p>
              <p>{book.attribution_status.replaceAll("_", " ")}</p>
              <p className="text-amber-900">
                Unaudited. Neither bank-reconciled nor legally verified reserve ownership.
              </p>
            </div>
          )}
        </div>
      )}
      {saved && canEdit && <HoaReserveMovementPlans associationId={associationId}
        propertyId={propertyId} reserveGlId={saved.gl_account_id} canEdit={canEdit} />}
      {saved && !canEdit && (
        <p className="text-xs text-slate-600">
          Organization-wide book balance is restricted to administrators/owners.
        </p>
      )}
    </section>
  );
}
