"use client";

import { useEffect, useState } from "react";
import { apiGet } from "@/lib/api";

type FeeQuote = {
  application_id: number;
  status: "configured" | "unconfigured" | "unit_required";
  amount_cents: number | null;
  currency: "USD";
  checkout_available: boolean;
  message: string;
};

export default function ApplicationFeeQuote({ applicationId }: { applicationId: number }) {
  const [quote, setQuote] = useState<FeeQuote | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    let active = true;
    apiGet(`/api/leasing/applications/${applicationId}/fee-quote`)
      .then((data: FeeQuote) => { if (active) setQuote(data); })
      .catch((cause: unknown) => {
        if (active) setError(cause instanceof Error ? cause.message : "Fee quote unavailable.");
      })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [applicationId]);

  return (
    <div className="w-full rounded border border-slate-200 bg-slate-50 p-3 text-sm">
      {loading ? <p>Checking unit application fee…</p> : error ? (
        <p role="alert" className="text-red-700">{error}</p>
      ) : quote ? (
        <>
          <p className="font-medium">
            {quote.amount_cents === null ? "Application fee: not yet determined" : (
              `Application fee: ${(quote.amount_cents / 100).toLocaleString("en-US", {
                style: "currency", currency: quote.currency,
              })}`
            )}
          </p>
          <p className="mt-1 text-slate-600">{quote.message}</p>
          <p className="mt-1 text-slate-600">No payment has been collected. Checkout is not enabled.</p>
        </>
      ) : null}
    </div>
  );
}
