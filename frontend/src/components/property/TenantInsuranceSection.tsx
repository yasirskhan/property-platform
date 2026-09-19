"use client";

import { useEffect, useRef, useState } from "react";
import { apiGet, apiUpload, fileUrl } from "@/lib/api";

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
  status: string;
  extraction_status: string;
  verified_by_id: number | null;
  verified_at: string | null;
  rejection_reason: string | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
};

const STATUS_STYLES: Record<string, { label: string; classes: string }> = {
  pending: {
    label: "Pending review",
    classes: "bg-amber-50 text-amber-700 border-amber-200",
  },
  verified: {
    label: "✅ Verified",
    classes: "bg-green-50 text-green-700 border-green-200",
  },
  rejected: {
    label: "❌ Rejected",
    classes: "bg-red-50 text-red-700 border-red-200",
  },
  expired: {
    label: "⚠️ Expired",
    classes: "bg-slate-100 text-slate-700 border-slate-200",
  },
  missing: {
    label: "Missing",
    classes: "bg-slate-100 text-slate-700 border-slate-200",
  },
};

export default function TenantInsuranceSection({
  leaseId,
  canVerify,
}: {
  leaseId: number;
  canVerify: boolean;
}) {
  const [records, setRecords] = useState<TenantInsurance[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);

  async function load() {
    setLoading(true);
    try {
      const data = await apiGet(`/tenant-insurance/lease/${leaseId}`);
      setRecords(data);
    } catch {
      setRecords([]);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [leaseId]);

  async function handleVerify(id: number, approve: boolean) {
    const reason = approve
      ? null
      : prompt("Reason for rejection (visible to tenant):");
    if (!approve && !reason) return;

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
          body: JSON.stringify({
            approve,
            rejection_reason: reason,
          }),
        }
      );
      if (!res.ok) {
        const d = await res.json();
        throw new Error(d.detail || "Verify failed");
      }
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Verify failed");
    }
  }

  if (loading) return <p className="text-slate-500">Loading…</p>;

  const latest = records.length > 0 ? records[0] : null;
  const statusStyle = latest
    ? STATUS_STYLES[latest.status] || STATUS_STYLES.pending
    : STATUS_STYLES.missing;

  return (
    <div className="bg-white rounded-xl border border-slate-200 p-6">
      <div className="flex items-start justify-between mb-4">
        <div>
          <h3 className="font-semibold text-slate-900">Rental Insurance</h3>
          <span
            className={`inline-block mt-1 text-xs px-2 py-1 rounded-full border ${statusStyle.classes}`}
          >
            {statusStyle.label}
          </span>
        </div>
        <button
          onClick={() => {
            setEditingId(null);
            setShowForm(true);
          }}
          className="text-sm px-4 py-2 bg-slate-900 text-white rounded-lg hover:bg-slate-700"
        >
          {latest ? "Update Insurance" : "Upload Insurance"}
        </button>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-lg px-4 py-3 mb-4">
          {error}
        </div>
      )}

      {showForm && (
        <InsuranceForm
          leaseId={leaseId}
          insuranceId={editingId || (latest ? latest.id : null)}
          existing={editingId || latest ? latest : null}
          onCancel={() => {
            setShowForm(false);
            setEditingId(null);
          }}
          onSaved={() => {
            setShowForm(false);
            setEditingId(null);
            load();
          }}
        />
      )}

      {!latest && !showForm ? (
        <p className="text-sm text-slate-500">
          No rental insurance on file. Upload a copy of your policy to comply with your lease.
        </p>
      ) : latest ? (
        <div className="space-y-3 text-sm">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <p className="text-slate-500">Provider</p>
              <p className="font-medium text-slate-900">{latest.provider || "—"}</p>
            </div>
            <div>
              <p className="text-slate-500">Policy #</p>
              <p className="font-medium text-slate-900">{latest.policy_number || "—"}</p>
            </div>
            <div>
              <p className="text-slate-500">Coverage</p>
              <p className="font-medium text-slate-900">
                {latest.coverage_amount
                  ? `$${Number(latest.coverage_amount).toLocaleString()}`
                  : "—"}
              </p>
            </div>
            <div>
              <p className="text-slate-500">Effective</p>
              <p className="font-medium text-slate-900">{latest.effective_date || "—"}</p>
            </div>
            <div>
              <p className="text-slate-500">Expires</p>
              <p className="font-medium text-slate-900">{latest.expiration_date || "—"}</p>
            </div>
          </div>

          {latest.document_url && (
            <div className="pt-3 border-t border-slate-100">
              <a
                href={fileUrl(latest.document_url)}
                target="_blank"
                rel="noopener noreferrer"
                className="text-blue-600 hover:underline"
              >
                📄 View uploaded policy
              </a>
            </div>
          )}

          {latest.status === "rejected" && latest.rejection_reason && (
            <div className="pt-3 border-t border-slate-100">
              <p className="text-slate-500">Rejection reason</p>
              <p className="text-red-700">{latest.rejection_reason}</p>
            </div>
          )}

          {latest.status === "verified" && latest.verified_at && (
            <p className="text-xs text-slate-500 pt-3 border-t border-slate-100">
              Verified on {new Date(latest.verified_at).toLocaleDateString()}
            </p>
          )}

          {canVerify && latest.status === "pending" && (
            <div className="pt-3 border-t border-slate-100 flex gap-3">
              <button
                onClick={() => handleVerify(latest.id, true)}
                className="text-sm px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700"
              >
                ✅ Approve
              </button>
              <button
                onClick={() => handleVerify(latest.id, false)}
                className="text-sm px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700"
              >
                ❌ Reject
              </button>
            </div>
          )}
        </div>
      ) : null}
    </div>
  );
}

// ------------------------------------------------------------
// FORM
// ------------------------------------------------------------
function InsuranceForm({
  leaseId,
  insuranceId,
  existing,
  onCancel,
  onSaved,
}: {
  leaseId: number;
  insuranceId: number | null;
  existing: TenantInsurance | null;
  onCancel: () => void;
  onSaved: () => void;
}) {
  const [provider, setProvider] = useState(existing?.provider || "");
  const [policyNumber, setPolicyNumber] = useState(existing?.policy_number || "");
  const [coverageAmount, setCoverageAmount] = useState(
    existing?.coverage_amount || ""
  );
  const [effectiveDate, setEffectiveDate] = useState(existing?.effective_date || "");
  const [expirationDate, setExpirationDate] = useState(existing?.expiration_date || "");
  const [documentUrl, setDocumentUrl] = useState(existing?.document_url || "");
  const [notes, setNotes] = useState(existing?.notes || "");
  const [uploading, setUploading] = useState(false);
  const [reading, setReading] = useState(false);
  const [extractMessage, setExtractMessage] = useState("");
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  async function handleUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    setExtractMessage("");
    try {
      const result = await apiUpload(file);
      setDocumentUrl(result.url);
    } catch (err) {
      setExtractMessage(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  }

  async function handleReadDocument() {
    // OCR endpoint for tenant insurance — not implemented yet.
    // When implemented, mirrors the property insurance flow.
    setExtractMessage(
      "Auto-read for tenant insurance is coming soon. Please enter the fields manually."
    );
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setSaving(true);
    try {
      const body = {
        provider: provider || null,
        policy_number: policyNumber || null,
        coverage_amount: coverageAmount ? Number(coverageAmount) : null,
        effective_date: effectiveDate || null,
        expiration_date: expirationDate || null,
        document_url: documentUrl || null,
        notes: notes || null,
      };

      const token = localStorage.getItem("token");
      const url = existing
        ? `http://127.0.0.1:8000/tenant-insurance/${existing.id}`
        : `http://127.0.0.1:8000/tenant-insurance`;
      const method = existing ? "PATCH" : "POST";

      const res = await fetch(url, {
        method,
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(
          existing ? body : { ...body, lease_id: leaseId }
        ),
      });

      if (!res.ok) {
        const d = await res.json();
        throw new Error(d.detail || "Save failed");
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
      className="bg-slate-50 rounded-xl border border-slate-200 p-5 mb-4 space-y-4"
    >
      <h4 className="font-semibold text-slate-900">
        {existing ? "Update Insurance" : "Upload Insurance"}
      </h4>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-lg px-4 py-3">
          {error}
        </div>
      )}

      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1">Provider</label>
          <input
            type="text"
            required
            value={provider}
            onChange={(e) => setProvider(e.target.value)}
            placeholder="State Farm"
            className="input"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1">Policy #</label>
          <input
            type="text"
            value={policyNumber}
            onChange={(e) => setPolicyNumber(e.target.value)}
            className="input"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1">
            Coverage Amount ($)
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
          <label className="block text-sm font-medium text-slate-700 mb-1">Effective Date</label>
          <input
            type="date"
            value={effectiveDate}
            onChange={(e) => setEffectiveDate(e.target.value)}
            className="input"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1">Expiration Date</label>
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
              {uploading ? "Uploading…" : documentUrl ? "Replace Document" : "Upload Document"}
            </button>
            {documentUrl && (
              <>
                <a
                  href={fileUrl(documentUrl)}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-sm text-blue-600 hover:underline"
                >
                  View uploaded file
                </a>
                <button
                  type="button"
                  onClick={handleReadDocument}
                  className="px-4 py-2 text-sm bg-slate-200 text-slate-700 rounded-lg hover:bg-slate-300"
                >
                  Read Document (coming soon)
                </button>
              </>
            )}
          </div>
          {extractMessage && (
            <p className="text-xs text-slate-700 mt-2 bg-amber-50 border border-amber-200 rounded px-3 py-2">
              {extractMessage}
            </p>
          )}
        </div>

        <div className="col-span-2">
          <label className="block text-sm font-medium text-slate-700 mb-1">Notes</label>
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
          {saving ? "Saving…" : existing ? "Update" : "Submit"}
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