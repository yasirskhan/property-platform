// ============================================================
// Diagnostics — Placeholder
// ------------------------------------------------------------
// Route: /dashboard/accounting/diagnostics
//
// The 6 financial diagnostics (Section 35 of PROJECT_MASTER)
// will be built in Step 8 of Phase 2. For now, this page is
// a placeholder so the sidebar link doesn't 404.
// ============================================================

"use client";

import { AlertCircle } from "lucide-react";

export default function DiagnosticsPage() {
  return (
    <div className="max-w-3xl">
      <div className="flex items-center gap-3 mb-1">
        <AlertCircle className="w-6 h-6 text-slate-700" />
        <h1 className="text-2xl font-semibold text-slate-900">Diagnostics</h1>
      </div>
      <p className="text-sm text-slate-500 mb-8">
        Financial health checks for your trust accounting.
      </p>

      <div className="bg-white border border-slate-200 rounded-lg p-8 text-center">
        <p className="text-slate-600 mb-2">
          Diagnostics will be available soon.
        </p>
        <p className="text-sm text-slate-400">
          The six financial checks (Security Deposit Funds Mismatch,
          Escrow Cash Mismatch, Clearing Account Balances, Fee GL
          Negative/Positive, and Trust Account 3-Way Reconciliation)
          are planned for a later step in the accounting phase.
        </p>
      </div>
    </div>
  );
}