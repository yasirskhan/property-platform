// ============================================================
// TenantInsuranceSection.tsx
// ------------------------------------------------------------
// Shows tenant insurance records for a lease, lets a manager
// verify / reject, and add new records.
//
// Uses formatMoney() from lib/money.ts so the org's currency
// setting is respected (Section 59).
// ============================================================

"use client";

import { useEffect, useRef, useState } from "react";
import { apiGet, apiUpload, fileUrl } from "@/lib/api";
import { formatMoney, formatDate } from "@/lib/money";

type TenantInsurance = {
  id: number;
  lease_id: number;
  tenant_id: number;
  property_id: number;
  provider: string | null;
  policy_number: string | null;
  coverage_amount: string | null;
  effective_date: string | null;
  expiration_date: string | null;
  document_url: string | null;
  notes: string | null;
  status: "pending" | "verified" | "rejected" | "expired";
  extraction_status: string;
  verified_by_id: number | null;
  verified_at: string | null;
  rejection_reason: string | null;
  created_at: string;
  updated_at: string;
};

const STATUS_STYLES: Record<string, { label: string; classes: string }> = {
  pending: {
    label: "Pending",
    classes: "bg-amber-50 text-amber-800 border-amber-200",
  },
  verified: {
    label: "Verified",
    classes: "bg-green-50 text-green-800 border-green-200",
  },
  rejected: {
    label: "Rejected",
    classes: "bg-red-50 text-red-800 border-red-200",
  },
  expired: {
    label: "Expired",
    classes: "bg-slate-100 text-slate-700 border-slate-200",
  },
};

export default function TenantInsuranceSection({
  leaseId,
  canEdit,
}: {
  leaseId: number;
  canEdit: boolean;
}) {
  const [items, setItems] = useState<TenantInsurance[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [error, setError] = useState("");

  async function load() {
    setLoading(true);
    try {
      const data = await apiGet(`/tenant-insurance/lease/${leaseId}`);
      setItems(data);
    } catch {
      setItems([]);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [leaseId]);

  async function handleVerify(id: number, approve: boolean) {
    let reason: string | null = null;
    if (!approve) {
      reason = prompt("Reason for rejection?") || null;
      if (!reason) return;
    }
    try {
      const token = localStorage.getItem("token");
      const res = await fetch(
        `http://127.0.0.1:8000/tenant-insurance/${id}/verify`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({ approve, rejection_reason: reason }),
        }
      );
      if (!res.ok) throw new Error("Verify failed");
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Verify failed");
    }
  }

  if (loading) return <p className="text-slate-500">Loading…</p>;

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <p className="text-slate-600">
          {items.length} {items.length === 1 ? "record" : "records"}
        </p>
        {canEdit && (
          <button
            onClick={() => setShowForm(true)}
            className="text-sm px-4 py-2 bg-slate-900 text-white rounded-lg hover:bg-slate-700"
          >
            + Add Insurance
          </button>
        )}
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-lg px-4 py-3 mb-4">
          {error}
        </div>
      )}

      {showForm && (
        <InsuranceForm
          leaseId={leaseId}
          onCancel={() => setShowForm(false)}
          onSaved={() => {
            setShowForm(false);
            load();
          }}
        />
      )}

      {items.length === 0 && !showForm ? (
        <p className="text-slate-500">No tenant insurance records yet.</p>
      ) : (
        <div className="space-y-3">
          {items.map((rec) => {
            const statusStyle =
              STATUS_STYLES[rec.status] || STATUS_STYLES.pending;
            return (
              <div
                key={rec.id}
                className="bg-white rounded-xl border border-slate-200 p-5"
              >
                <div className="flex items-start justify-between mb-3">
                  <div>
                    <h3 className="font-semibold text-slate-900">
                      {rec.provider || "Unknown provider"}
                    </h3>
                    <span
                      className={`inline-block mt-1 text-xs px-2 py-1 rounded-full border ${statusStyle.classes}`}
                    >
                      {statusStyle.label}
                    </span>
                  </div>
                  {canEdit && rec.status === "pending" && (
                    <div className="flex gap-2">
                      <button
                        onClick={() => handleVerify(rec.id, true)}
                        className="text-xs px-3 py-1 bg-green-600 text-white rounded-lg hover:bg-green-700"
                      >
                        Approve
                      </button>
                      <button
                        onClick={() => handleVerify(rec.id, false)}
                        className="text-xs px-3 py-1 bg-red-600 text-white rounded-lg hover:bg-red-700"
                      >
                        Reject
                      </button>
                    </div>
                  )}
                </div>

                <div className="grid grid-cols-2 md:grid-cols-3 gap-4 text-sm">
                  <div>
                    <p className="text-slate-500">Policy #</p>
                    <p className="font-medium text-slate-900">
                      {rec.policy_number || "—"}
                    </p>
                  </div>
                  <div>
                    <p className="text-slate-500">Coverage</p>
                    <p className="font-medium text-slate-900">
                      {rec.coverage_amount
                        ? formatMoney(rec.coverage_amount)
                        : "—"}
                    </p>
                  </div>
                  <div>
                    <p className="text-slate-500">Effective</p>
                    <p className="font-medium text-slate-900">
                      {rec.effective_date || "—"}
                    </p>
                  </div>
                  <div>
                    <p className="text-slate-500">Expires</p>
                    <p className="font-medium text-slate-900">
                      {rec.expiration_date || "—"}
                    </p>
                  </div>
                  <div>
                    <p className="text-slate-500">Verified</p>
                    <p className="font-medium text-slate-900">
                      {rec.verified_at ? formatDate(rec.verified_at) : "—"}
                    </p>
                  </div>
                </div>

                {rec.rejection_reason && (
                  <p className="text-sm text-red-700 mt-3 pt-3 border-t border-slate-100">
                    <strong>Rejected:</strong> {rec.rejection_reason}
                  </p>
                )}

                {rec.document_url && (
                  <div className="mt-3 pt-3 border-t border-slate-100">
                    <a
                      href={fileUrl(rec.document_url)}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-sm text-blue-600 hover:underline"
                    >
                      📄 View policy document
                    </a>
                  </div>
                )}

                {rec.notes && (
                  <p className="text-sm text-slate-600 mt-3 pt-3 border-t border-slate-100">
                    {rec.notes}
                  </p>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

// ------------------------------------------------------------
// FORM
// ------------------------------------------------------------
function InsuranceForm({
  leaseId,
  onCancel,
  onSaved,
}: {
  leaseId: number;
  onCancel: () => void;
  onSaved: () => void;
}) {
  const [provider, setProvider] = useState("");
  const [policyNumber, setPolicyNumber] = useState("");
  const [coverageAmount, setCoverageAmount] = useState("");
  const [effectiveDate, setEffectiveDate] = useState("");
  const [expirationDate, setExpirationDate] = useState("");
  const [notes, setNotes] = useState("");
  const [documentUrl, setDocumentUrl] = useState("");
  const [uploading, setUploading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  async function handleUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    try {
      const result = await apiUpload(file);
      setDocumentUrl(result.url);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setSaving(true);
    try {
      const body = {
        lease_id: leaseId,
        provider: provider || null,
        policy_number: policyNumber || null,
        coverage_amount: coverageAmount ? Number(coverageAmount) : null,
        effective_date: effectiveDate || null,
        expiration_date: expirationDate || null,
        document_url: documentUrl || null,
        notes: notes || null,
      };

      const token = localStorage.getItem("token");
      const res = await fetch("http://127.0.0.1:8000/tenant-insurance", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(body),
      });

      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || "Save failed");
      }
      onSaved();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed");
      setSaving(false);
    }
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="bg-slate-50 rounded-xl border border-slate-200 p-6 mb-4 space-y-4"
    >
      <h4 className="font-semibold text-slate-900">New Tenant Insurance</h4>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-lg px-4 py-3">
          {error}
        </div>
      )}

      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1">
            Provider
          </label>
          <input
            type="text"
            value={provider}
            onChange={(e) => setProvider(e.target.value)}
            className="input"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1">
            Policy #
          </label>
          <input
            type="text"
            value={policyNumber}
            onChange={(e) => setPolicyNumber(e.target.value)}
            className="input"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1">
            Coverage Amount
          </label>
          <input
            type="number"
            step="0.01"
            value={coverageAmount}
            onChange={(e) => setCoverageAmount(e.target.value)}
            className="input"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1">
            Effective Date
          </label>
          <input
            type="date"
            value={effectiveDate}
            onChange={(e) => setEffectiveDate(e.target.value)}
            className="input"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1">
            Expiration Date
          </label>
          <input
            type="date"
            value={expirationDate}
            onChange={(e) => setExpirationDate(e.target.value)}
            className="input"
          />
        </div>
        <div className="col-span-2">
          <label className="block text-sm font-medium text-slate-700 mb-1">
            Policy Document
          </label>
          <div className="flex items-center gap-3 flex-wrap">
            <input
              ref={fileInputRef}
              type="file"
              accept="application/pdf,image/*"
              onChange={handleUpload}
              className="hidden"
            />
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              disabled={uploading}
              className="px-4 py-2 text-sm bg-slate-100 rounded-lg hover:bg-slate-200 disabled:opacity-50"
            >
              {uploading
                ? "Uploading…"
                : documentUrl
                ? "Replace Document"
                : "Upload Document"}
            </button>
            {documentUrl && (
              <a
                href={fileUrl(documentUrl)}
                target="_blank"
                rel="noopener noreferrer"
                className="text-sm text-blue-600 hover:underline"
              >
                View uploaded file
              </a>
            )}
          </div>
        </div>
        <div className="col-span-2">
          <label className="block text-sm font-medium text-slate-700 mb-1">
            Notes
          </label>
          <textarea
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            rows={2}
            className="input"
          />
        </div>
      </div>

      <div className="flex gap-3">
        <button
          type="submit"
          disabled={saving}
          className="bg-slate-900 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-slate-700 disabled:opacity-50"
        >
          {saving ? "Saving…" : "Add Insurance"}
        </button>
        <button
          type="button"
          onClick={onCancel}
          className="px-4 py-2 rounded-lg text-sm font-medium border border-slate-300 hover:bg-slate-100"
        >
          Cancel
        </button>
      </div>
    </form>
  );
}