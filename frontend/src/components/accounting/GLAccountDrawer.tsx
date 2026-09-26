// ============================================================
// GLAccountDrawer.tsx
// ------------------------------------------------------------
// Create/edit drawer for a GL account.
//
// Opens from the Chart of Accounts page. In create mode, the
// GL number field is editable. In edit mode, the GL number is
// locked (renumbering historical accounts is dangerous).
// ============================================================

"use client";

import { useEffect, useState } from "react";
import { X, Loader2, Save } from "lucide-react";
import {
  createGLAccount,
  updateGLAccount,
  GLAccount,
  ACCOUNT_TYPE_LABELS,
  ACCOUNT_TYPE_ORDER,
} from "@/lib/glAccounts";

type Props = {
  account: GLAccount | null;      // null = create mode
  allAccounts: GLAccount[];       // for the "sub-account of" dropdown
  onClose: () => void;
  onSaved: () => void | Promise<void>;
};

export default function GLAccountDrawer({
  account,
  allAccounts,
  onClose,
  onSaved,
}: Props) {
  const isEdit = account !== null;

  const [glNumber, setGlNumber] = useState(account?.gl_number ?? "");
  const [name, setName] = useState(account?.name ?? "");
  const [accountType, setAccountType] = useState(
    account?.account_type ?? "ASSET"
  );
  const [subAccountOf, setSubAccountOf] = useState<string>(
    account?.sub_account_of?.toString() ?? ""
  );
  const [offsetAccount, setOffsetAccount] = useState(
    account?.offset_account ?? ""
  );
  const [subjectToMgmtFees, setSubjectToMgmtFees] = useState(
    account?.subject_to_mgmt_fees ?? false
  );
  const [includeOnCashFlow, setIncludeOnCashFlow] = useState(
    account?.include_on_cash_flow ?? true
  );
  const [mustClear, setMustClear] = useState(account?.must_clear ?? false);

  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  // Reset form when the account prop changes (e.g. opening for a
  // different row).
  useEffect(() => {
    setGlNumber(account?.gl_number ?? "");
    setName(account?.name ?? "");
    setAccountType(account?.account_type ?? "ASSET");
    setSubAccountOf(account?.sub_account_of?.toString() ?? "");
    setOffsetAccount(account?.offset_account ?? "");
    setSubjectToMgmtFees(account?.subject_to_mgmt_fees ?? false);
    setIncludeOnCashFlow(account?.include_on_cash_flow ?? true);
    setMustClear(account?.must_clear ?? false);
    setError("");
  }, [account]);

  async function handleSave() {
    setError("");

    if (!name.trim()) {
      setError("Account name is required.");
      return;
    }
    if (!isEdit && !glNumber.trim()) {
      setError("GL number is required.");
      return;
    }

    setSaving(true);
    try {
      if (isEdit) {
        await updateGLAccount(account!.id, {
          name: name.trim(),
          account_type: accountType,
          sub_account_of: subAccountOf ? Number(subAccountOf) : null,
          offset_account: offsetAccount.trim() || null,
          subject_to_mgmt_fees: subjectToMgmtFees,
          include_on_cash_flow: includeOnCashFlow,
          must_clear: mustClear,
        });
      } else {
        await createGLAccount({
          gl_number: glNumber.trim(),
          name: name.trim(),
          account_type: accountType,
          sub_account_of: subAccountOf ? Number(subAccountOf) : null,
          offset_account: offsetAccount.trim() || null,
          subject_to_mgmt_fees: subjectToMgmtFees,
          include_on_cash_flow: includeOnCashFlow,
          must_clear: mustClear,
        });
      }
      await onSaved();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed");
    } finally {
      setSaving(false);
    }
  }

  // Options for the "sub-account of" dropdown — exclude self
  const parentOptions = allAccounts.filter(
    (a) => (!account || a.id !== account.id) && a.is_active
  );

  return (
    <div className="fixed inset-0 bg-black/30 z-40 flex justify-end">
      <div className="w-[520px] bg-white h-full shadow-xl flex flex-col">
        {/* Header */}
        <div className="px-5 py-4 border-b border-slate-200 flex items-center justify-between">
          <div>
            <div className="text-sm text-slate-500">
              {isEdit ? "Edit account" : "New account"}
            </div>
            <div className="font-medium text-slate-900">
              {isEdit
                ? `${account!.gl_number} ${account!.name}`
                : "Add a GL account"}
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded hover:bg-slate-100"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto px-5 py-4 space-y-4">
          {error && (
            <div className="p-3 bg-red-50 border border-red-200 text-red-700 text-sm rounded">
              {error}
            </div>
          )}

          {/* GL Number */}
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">
              GL Number *
            </label>
            <input
              type="text"
              value={glNumber}
              onChange={(e) => setGlNumber(e.target.value)}
              disabled={isEdit}
              placeholder="e.g. 6195"
              className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm font-mono disabled:bg-slate-100 disabled:text-slate-500"
            />
            {isEdit && (
              <div className="text-xs text-slate-400 mt-1">
                GL number cannot be changed after creation.
              </div>
            )}
          </div>

          {/* Name */}
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">
              Account Name *
            </label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Pool Service"
              className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm"
            />
          </div>

          {/* Account Type */}
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">
              Account Type *
            </label>
            <select
              value={accountType}
              onChange={(e) => setAccountType(e.target.value)}
              className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm"
            >
              {ACCOUNT_TYPE_ORDER.map((t) => (
                <option key={t} value={t}>
                  {ACCOUNT_TYPE_LABELS[t] || t}
                </option>
              ))}
            </select>
          </div>

          {/* Sub-account of */}
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">
              Sub-account of
            </label>
            <select
              value={subAccountOf}
              onChange={(e) => setSubAccountOf(e.target.value)}
              className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm"
            >
              <option value="">— None (top-level) —</option>
              {parentOptions.map((a) => (
                <option key={a.id} value={a.id.toString()}>
                  {a.gl_number} — {a.name}
                </option>
              ))}
            </select>
          </div>

          {/* Offset Account */}
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">
              Offset Account
            </label>
            <input
              type="text"
              value={offsetAccount}
              onChange={(e) => setOffsetAccount(e.target.value)}
              placeholder="e.g. 1150"
              className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm font-mono"
            />
            <div className="text-xs text-slate-400 mt-1">
              Optional. Used for bank reconciliation and diagnostics.
            </div>
          </div>

          {/* Toggles */}
          <div className="pt-2 space-y-3">
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={subjectToMgmtFees}
                onChange={(e) => setSubjectToMgmtFees(e.target.checked)}
                className="w-4 h-4 accent-blue-600"
              />
              <span className="text-sm text-slate-700">
                Subject to management fees
              </span>
            </label>

            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={includeOnCashFlow}
                onChange={(e) => setIncludeOnCashFlow(e.target.checked)}
                className="w-4 h-4 accent-blue-600"
              />
              <span className="text-sm text-slate-700">
                Include on Cash Flow report
              </span>
            </label>

            <label className="flex items-start gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={mustClear}
                onChange={(e) => setMustClear(e.target.checked)}
                className="w-4 h-4 accent-blue-600 mt-0.5"
              />
              <span>
                <span className="block text-sm text-slate-700">
                  Must clear to zero
                </span>
                <span className="block text-xs text-slate-400">
                  Use for clearing accounts that diagnostics expect to net to zero.
                </span>
              </span>
            </label>
          </div>
        </div>

        {/* Footer */}
        <div className="px-5 py-4 border-t border-slate-200 flex items-center gap-3">
          <button
            onClick={handleSave}
            disabled={saving}
            className="inline-flex items-center gap-2 px-4 py-2 bg-blue-600 text-white text-sm rounded hover:bg-blue-700 disabled:opacity-50"
          >
            {saving ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Save className="w-4 h-4" />
            )}
            {isEdit ? "Save changes" : "Create account"}
          </button>
          <button
            onClick={onClose}
            disabled={saving}
            className="px-4 py-2 text-sm text-slate-600 hover:text-slate-900 disabled:opacity-50"
          >
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
}