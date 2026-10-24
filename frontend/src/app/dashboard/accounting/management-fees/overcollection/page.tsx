"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

import { useDisplay } from "@/contexts/DisplayContext";
import {
  getOvercollectionStrategy,
  updateOvercollectionStrategy,
  type OvercollectionStrategy,
} from "@/lib/managementFees";

const OPTIONS: Array<{
  value: OvercollectionStrategy;
  title: string;
  description: string;
  recommended?: boolean;
}> = [
  {
    value: "CREDITS_THEN_RECEIPTS",
    title: "Credits then Receipts",
    description:
      "Apply management-fee credits first, then collect against new eligible receipts.",
    recommended: true,
  },
  {
    value: "RECEIPTS_THEN_CREDITS",
    title: "Receipts then Credits",
    description:
      "Collect against new eligible receipts first, then apply management-fee credits.",
  },
];

export default function ManagementFeeOvercollectionPage() {
  const { prefs } = useDisplay();
  const [strategy, setStrategy] =
    useState<OvercollectionStrategy>("CREDITS_THEN_RECEIPTS");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  useEffect(() => {
    getOvercollectionStrategy()
      .then((result) => setStrategy(result.strategy))
      .catch((err) =>
        setError(err instanceof Error ? err.message : "Could not load strategy.")
      )
      .finally(() => setLoading(false));
  }, []);

  async function save() {
    setSaving(true);
    setError("");
    setMessage("");
    try {
      const result = await updateOvercollectionStrategy(strategy);
      setStrategy(result.strategy);
      setMessage("Overcollection strategy saved.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save strategy.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div
      className="max-w-3xl p-6"
      data-layout-mode={(prefs?.layout_mode ?? "TABS").toLowerCase()}
      data-density={(prefs?.density ?? "COMFORTABLE").toLowerCase()}
    >
      <Link
        href="/dashboard/accounting/management-fees"
        className="text-sm text-slate-500 hover:text-slate-800"
      >
        ← Back to Management Fees
      </Link>

      <div className="mt-4 mb-6">
        <h1 className="text-2xl font-bold text-slate-900">
          Management Fee Overcollection
        </h1>
        <p className="text-slate-500 mt-1">
          Choose the order used when management-fee credits and new receipts
          are both available for collection.
        </p>
      </div>

      {error && (
        <div className="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}
      {message && (
        <div className="mb-4 rounded-lg border border-green-200 bg-green-50 px-4 py-3 text-sm text-green-700">
          {message}
        </div>
      )}

      <div className="space-y-3">
        {OPTIONS.map((option) => (
          <label
            key={option.value}
            className="flex cursor-pointer gap-3 rounded-xl border border-slate-200 bg-white p-5"
          >
            <input
              type="radio"
              name="overcollection-strategy"
              value={option.value}
              checked={strategy === option.value}
              disabled={loading || saving}
              onChange={() => setStrategy(option.value)}
              className="mt-1"
            />
            <span>
              <span className="font-semibold text-slate-900">
                {option.title}
              </span>
              {option.recommended && (
                <span className="ml-2 rounded-full bg-green-50 px-2 py-0.5 text-xs font-medium text-green-700">
                  Recommended
                </span>
              )}
              <span className="mt-1 block text-sm text-slate-600">
                {option.description}
              </span>
            </span>
          </label>
        ))}
      </div>

      <div className="mt-6 flex justify-end">
        <button
          type="button"
          onClick={() => void save()}
          disabled={loading || saving}
          className="rounded-lg bg-slate-900 px-5 py-2.5 font-medium text-white disabled:opacity-50"
        >
          {saving ? "Saving…" : "Save Strategy"}
        </button>
      </div>
    </div>
  );
}
