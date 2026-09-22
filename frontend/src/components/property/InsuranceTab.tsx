"use client";

import { useEffect, useRef, useState } from "react";
import { apiGet, apiUpload, fileUrl } from "@/lib/api";
import { formatMoney } from "@/lib/money";

type Insurance = {
  id: number;
  property_id: number;
  policy_type: string;
  provider: string;
  policy_number: string | null;
  coverage_amount: string | null;
  deductible: string | null;
  premium_amount: string | null;
  premium_frequency: string;
  start_date: string | null;
  end_date: string | null;
  agent_name: string | null;
  agent_phone: string | null;
  agent_email: string | null;
  document_url: string | null;
  notes: string | null;
  is_active: boolean;
};

const POLICY_TYPES = [
  { value: "hazard", label: "Hazard" },
  { value: "flood", label: "Flood" },
  { value: "umbrella", label: "Umbrella" },
  { value: "liability", label: "Liability" },
  { value: "earthquake", label: "Earthquake" },
  { value: "windstorm", label: "Windstorm" },
  { value: "other", label: "Other" },
];

const FREQUENCIES = [
  { value: "monthly", label: "Monthly" },
  { value: "quarterly", label: "Quarterly" },
  { value: "semi_annual", label: "Semi-Annual" },
  { value: "annual", label: "Annual" },
  { value: "other", label: "Other" },
];

export default function InsuranceTab({
  propertyId,
  canEdit,
}: {
  propertyId: number;
  canEdit: boolean;
}) {
  const [policies, setPolicies] = useState<Insurance[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [error, setError] = useState("");

  async function load() {
    setLoading(true);
    try {
      const data = await apiGet(`/properties/${propertyId}/insurance`);
      setPolicies(data);
    } catch {
      setPolicies([]);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [propertyId]);

  async function handleDelete(id: number) {
    if (!confirm("Delete this insurance policy?")) return;
    try {
      const token = localStorage.getItem("token");
      const res = await fetch(
        `http://127.0.0.1:8000/properties/${propertyId}/insurance/${id}`,
        { method: "DELETE", headers: { Authorization: `Bearer ${token}` } }
      );
      if (!res.ok) throw new Error("Delete failed");
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Delete failed");
    }
  }

  if (loading) return <p className="text-slate-500">Loading…</p>;

  const totalAnnualPremium = policies.reduce((sum, p) => {
    const amt = p.premium_amount ? Number(p.premium_amount) : 0;
    const freq = p.premium_frequency;
    const multiplier =
      freq === "monthly" ? 12 : freq === "quarterly" ? 4 : freq === "semi_annual" ? 2 : 1;
    return sum + amt * multiplier;
  }, 0);

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <p className="text-slate-600">
          {policies.length} {policies.length === 1 ? "policy" : "policies"}
        </p>
        {canEdit && (
          <button
            onClick={() => {
              setEditingId(null);
              setShowForm(true);
            }}
            className="text-sm px-4 py-2 bg-slate-900 text-white rounded-lg hover:bg-slate-700"
          >
            + Add Policy
          </button>
        )}
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-lg px-4 py-3 mb-4">
          {error}
        </div>
      )}

      {policies.length > 0 && (
        <div className="bg-slate-50 border border-slate-200 rounded-xl p-4 mb-4">
          <p className="text-sm text-slate-600">
            Total annual premium across all policies:{" "}
            <span className="font-semibold text-slate-900">
              {formatMoney(totalAnnualPremium)}
            </span>
          </p>
        </div>
      )}

      {showForm && (
        <InsuranceForm
          propertyId={propertyId}
          policyId={editingId}
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

      {policies.length === 0 && !showForm ? (
        <p className="text-slate-500">No insurance policies yet.</p>
      ) : (
        <div className="space-y-4">
          {policies.map((p) => (
            <div key={p.id} className="bg-white rounded-xl border border-slate-200 p-6">
              <div className="flex items-start justify-between mb-3">
                <div>
                  <h3 className="font-semibold text-slate-900">{p.provider}</h3>
                  <p className="text-xs text-slate-500 uppercase mt-0.5">
                    {p.policy_type}
                  </p>
                </div>
                {canEdit && (
                  <div className="flex gap-2">
                    <button
                      onClick={() => {
                        setEditingId(p.id);
                        setShowForm(true);
                      }}
                      className="text-xs px-3 py-1 border border-slate-200 rounded-lg hover:bg-slate-50"
                    >
                      Edit
                    </button>
                    <button
                      onClick={() => handleDelete(p.id)}
                      className="text-xs px-3 py-1 border border-red-200 text-red-700 rounded-lg hover:bg-red-50"
                    >
                      Delete
                    </button>
                  </div>
                )}
              </div>

              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                <div>
                  <p className="text-slate-500">Policy #</p>
                  <p className="font-medium text-slate-900">{p.policy_number || "—"}</p>
                </div>
                <div>
                  <p className="text-slate-500">Coverage</p>
                  <p className="font-medium text-slate-900">
                    {p.coverage_amount ? formatMoney(p.coverage_amount) : "—"}
                  </p>
                </div>
                <div>
                  <p className="text-slate-500">Deductible</p>
                  <p className="font-medium text-slate-900">
                    {p.deductible ? formatMoney(p.deductible) : "—"}
                  </p>
                </div>
                <div>
                  <p className="text-slate-500">Premium</p>
                  <p className="font-medium text-slate-900">
                    {p.premium_amount
                      ? `${formatMoney(p.premium_amount)} / ${p.premium_frequency.replace(
                          "_",
                          " "
                        )}`
                      : "—"}
                  </p>
                </div>
                <div>
                  <p className="text-slate-500">Start</p>
                  <p className="font-medium text-slate-900">{p.start_date || "—"}</p>
                </div>
                <div>
                  <p className="text-slate-500">End</p>
                  <p className="font-medium text-slate-900">{p.end_date || "—"}</p>
                </div>
                <div>
                  <p className="text-slate-500">Agent</p>
                  <p className="font-medium text-slate-900">{p.agent_name || "—"}</p>
                </div>
                <div>
                  <p className="text-slate-500">Agent Contact</p>
                  <p className="font-medium text-slate-900">
                    {p.agent_phone || p.agent_email || "—"}
                  </p>
                </div>
              </div>

              {p.document_url && (
                <div className="mt-3 pt-3 border-t border-slate-100">
                  <a
                    href={fileUrl(p.document_url)}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-sm text-blue-600 hover:underline"
                  >
                    📄 View policy document
                  </a>
                </div>
              )}

              {p.notes && (
                <p className="text-sm text-slate-600 mt-3 pt-3 border-t border-slate-100">
                  {p.notes}
                </p>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ------------------------------------------------------------
// FORM
// ------------------------------------------------------------
function InsuranceForm({
  propertyId,
  policyId,
  onCancel,
  onSaved,
}: {
  propertyId: number;
  policyId: number | null;
  onCancel: () => void;
  onSaved: () => void;
}) {
  const [policyType, setPolicyType] = useState("hazard");
  const [provider, setProvider] = useState("");
  const [policyNumber, setPolicyNumber] = useState("");
  const [coverageAmount, setCoverageAmount] = useState("");
  const [deductible, setDeductible] = useState("");
  const [premiumAmount, setPremiumAmount] = useState("");
  const [premiumFrequency, setPremiumFrequency] = useState("annual");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [agentName, setAgentName] = useState("");
  const [agentPhone, setAgentPhone] = useState("");
  const [agentEmail, setAgentEmail] = useState("");
  const [documentUrl, setDocumentUrl] = useState("");
  const [notes, setNotes] = useState("");
  const [uploading, setUploading] = useState(false);
  const [reading, setReading] = useState(false);
  const [extractMessage, setExtractMessage] = useState("");
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (policyId === null) return;
    apiGet(`/properties/${propertyId}/insurance/${policyId}`).then((p) => {
      setPolicyType(p.policy_type || "hazard");
      setProvider(p.provider || "");
      setPolicyNumber(p.policy_number || "");
      setCoverageAmount(p.coverage_amount?.toString() || "");
      setDeductible(p.deductible?.toString() || "");
      setPremiumAmount(p.premium_amount?.toString() || "");
      setPremiumFrequency(p.premium_frequency || "annual");
      setStartDate(p.start_date || "");
      setEndDate(p.end_date || "");
      setAgentName(p.agent_name || "");
      setAgentPhone(p.agent_phone || "");
      setAgentEmail(p.agent_email || "");
      setDocumentUrl(p.document_url || "");
      setNotes(p.notes || "");
    });
  }, [policyId, propertyId]);

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
    if (!policyId) {
      setExtractMessage("Save the policy first, then click Read Document.");
      return;
    }
    if (!documentUrl) {
      setExtractMessage("Upload a document first.");
      return;
    }
    setReading(true);
    setExtractMessage("");
    try {
      const token = localStorage.getItem("token");
      const res = await fetch(
        `http://127.0.0.1:8000/properties/${propertyId}/insurance/${policyId}/extract`,
        {
          method: "POST",
          headers: { Authorization: `Bearer ${token}` },
        }
      );
      const data = await res.json();

      if (!res.ok) {
        throw new Error(data.detail || "Extraction failed");
      }

      if (data.status === "success") {
        if (data.provider_name) setProvider(data.provider_name);
        if (data.policy_number) setPolicyNumber(data.policy_number);
        if (data.coverage_amount) setCoverageAmount(String(data.coverage_amount));
        if (data.effective_date) setStartDate(data.effective_date);
        if (data.expiration_date) setEndDate(data.expiration_date);
        setExtractMessage(
          "Fields extracted. Review the values and click Update to save."
        );
      } else if (data.status === "not_configured") {
        setExtractMessage(
          "OCR is not configured. Ask your admin to set it up in Settings → OCR."
        );
      } else {
        setExtractMessage(data.message || "Could not read this document.");
      }
    } catch (err) {
      setExtractMessage(err instanceof Error ? err.message : "Extraction failed");
    } finally {
      setReading(false);
    }
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setSaving(true);
    try {
      const body = {
        policy_type: policyType,
        provider,
        policy_number: policyNumber || null,
        coverage_amount: coverageAmount ? Number(coverageAmount) : null,
        deductible: deductible ? Number(deductible) : null,
        premium_amount: premiumAmount ? Number(premiumAmount) : null,
        premium_frequency: premiumFrequency,
        start_date: startDate || null,
        end_date: endDate || null,
        agent_name: agentName || null,
        agent_phone: agentPhone || null,
        agent_email: agentEmail || null,
        document_url: documentUrl || null,
        notes: notes || null,
      };

      const token = localStorage.getItem("token");
      const url = policyId
        ? `http://127.0.0.1:8000/properties/${propertyId}/insurance/${policyId}`
        : `http://127.0.0.1:8000/properties/${propertyId}/insurance`;
      const method = policyId ? "PATCH" : "POST";

      const res = await fetch(url, {
        method,
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
    <form onSubmit={handleSubmit} className="bg-slate-50 rounded-xl border border-slate-200 p-6 mb-4 space-y-4">
      <h4 className="font-semibold text-slate-900">
        {policyId ? "Edit Policy" : "New Policy"}
      </h4>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-lg px-4 py-3">
          {error}
        </div>
      )}

      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1">Policy Type</label>
          <select value={policyType} onChange={(e) => setPolicyType(e.target.value)} className="input">
            {POLICY_TYPES.map((t) => (
              <option key={t.value} value={t.value}>
                {t.label}
              </option>
            ))}
          </select>
        </div>
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
          <label className="block text-sm font-medium text-slate-700 mb-1">Coverage Amount</label>
          <input
            type="number"
            step="0.01"
            value={coverageAmount}
            onChange={(e) => setCoverageAmount(e.target.value)}
            className="input"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1">Deductible</label>
          <input
            type="number"
            step="0.01"
            value={deductible}
            onChange={(e) => setDeductible(e.target.value)}
            className="input"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1">Premium Amount</label>
          <input
            type="number"
            step="0.01"
            value={premiumAmount}
            onChange={(e) => setPremiumAmount(e.target.value)}
            className="input"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1">Premium Frequency</label>
          <select
            value={premiumFrequency}
            onChange={(e) => setPremiumFrequency(e.target.value)}
            className="input"
          >
            {FREQUENCIES.map((f) => (
              <option key={f.value} value={f.value}>
                {f.label}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1">Start Date</label>
          <input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} className="input" />
        </div>
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1">End Date</label>
          <input type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} className="input" />
        </div>
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1">Agent Name</label>
          <input
            type="text"
            value={agentName}
            onChange={(e) => setAgentName(e.target.value)}
            className="input"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1">Agent Phone</label>
          <input
            type="text"
            value={agentPhone}
            onChange={(e) => setAgentPhone(e.target.value)}
            className="input"
          />
        </div>
        <div className="col-span-2">
          <label className="block text-sm font-medium text-slate-700 mb-1">Agent Email</label>
          <input
            type="email"
            value={agentEmail}
            onChange={(e) => setAgentEmail(e.target.value)}
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
                {policyId && (
                  <button
                    type="button"
                    onClick={handleReadDocument}
                    disabled={reading}
                    className="px-4 py-2 text-sm bg-slate-900 text-white rounded-lg hover:bg-slate-700 disabled:opacity-50"
                  >
                    {reading ? "Reading…" : "Read Document"}
                  </button>
                )}
              </>
            )}
          </div>
          <p className="text-xs text-slate-500 mt-1">
            PDF or image. If OCR is configured, click <strong>Read Document</strong> to auto-fill fields.
          </p>
          {extractMessage && (
            <p className="text-xs text-slate-700 mt-2 bg-amber-50 border border-amber-200 rounded px-3 py-2">
              {extractMessage}
            </p>
          )}
        </div>

        <div className="col-span-2">
          <label className="block text-sm font-medium text-slate-700 mb-1">Notes</label>
          <textarea value={notes} onChange={(e) => setNotes(e.target.value)} rows={2} className="input" />
        </div>
      </div>

      <div className="flex gap-3">
        <button
          type="submit"
          disabled={saving}
          className="bg-slate-900 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-slate-700 disabled:opacity-50"
        >
          {saving ? "Saving…" : policyId ? "Update" : "Add Policy"}
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