"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import {
  apiGet,
  apiPost,
  clearToken,
  isLoggedIn,
  saveToken,
} from "@/lib/api";

type PricingTier = {
  id: number;
  min_properties: number;
  max_properties: number | null;
  monthly_price_cents: number;
  currency: string;
};

type BillingPlan = {
  id: number;
  code: string;
  name: string;
  description: string | null;
  pricing_tiers: PricingTier[];
};

type BillingCatalog = {
  plans: BillingPlan[];
};

type BillingState = {
  organization_state: string;
  billing_settings: {
    billing_email: string | null;
    currency: string;
    has_provider_customer: boolean;
  } | null;
  subscription: {
    subscription_id: number;
    plan_id: number;
    plan_code: string;
    plan_name: string;
    status: string;
    current_period_start: string | null;
    current_period_end: string | null;
    cancel_at_period_end: boolean;
  } | null;
  latest_checkout: {
    attempt_id: number;
    plan_id: number;
    pricing_tier_id: number;
    status: string;
    url: string | null;
    created_at: string;
    updated_at: string;
  } | null;
};

function money(cents: number, currency: string) {
  try {
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: currency.toUpperCase(),
      maximumFractionDigits: 2,
    }).format(cents / 100);
  } catch {
    return `${currency.toUpperCase()} ${(cents / 100).toFixed(2)}`;
  }
}

function propertyRange(tier: PricingTier) {
  if (tier.max_properties === null) {
    return `${tier.min_properties}+ properties`;
  }
  if (tier.min_properties === tier.max_properties) {
    return `${tier.min_properties} ${tier.min_properties === 1 ? "property" : "properties"}`;
  }
  return `${tier.min_properties}–${tier.max_properties} properties`;
}

function checkoutStorageKey(tierId: number) {
  return `billing-checkout-idempotency:${tierId}`;
}

function newIdempotencyKey() {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  return `checkout-${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

export default function SignupPage() {
  const [authenticated, setAuthenticated] = useState(false);
  const [checkoutStatus, setCheckoutStatus] = useState("");
  const [billingState, setBillingState] = useState<BillingState | null>(null);
  const [catalog, setCatalog] = useState<BillingCatalog | null>(null);
  const [billingLoading, setBillingLoading] = useState(false);
  const [checkoutTierId, setCheckoutTierId] = useState<number | null>(null);
  const [error, setError] = useState("");

  const [organizationName, setOrganizationName] = useState("");
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [creatingAccount, setCreatingAccount] = useState(false);

  const loadBilling = useCallback(async () => {
    setBillingLoading(true);
    setError("");
    try {
      const [state, planCatalog] = await Promise.all([
        apiGet("/api/billing/state"),
        apiGet("/api/billing/catalog"),
      ]);
      setBillingState(state);
      setCatalog(planCatalog);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load billing");
    } finally {
      setBillingLoading(false);
    }
  }, []);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const status = params.get("checkout") || "";
    setCheckoutStatus(status);

    if (status === "success" || status === "cancelled") {
      const selectedTier = sessionStorage.getItem("billing-selected-tier");
      if (selectedTier) {
        sessionStorage.removeItem(checkoutStorageKey(Number(selectedTier)));
      }
      sessionStorage.removeItem("billing-selected-tier");
    }

    if (isLoggedIn()) {
      setAuthenticated(true);
      void loadBilling();
    }
  }, [loadBilling]);

  async function handleAccountCreate(e: React.FormEvent) {
    e.preventDefault();
    setError("");

    if (password !== confirmPassword) {
      setError("Passwords do not match");
      return;
    }

    setCreatingAccount(true);
    try {
      await apiPost("/auth/signup", {
        email,
        password,
        first_name: firstName,
        last_name: lastName,
        organization_name: organizationName,
        role: "ADMIN",
      });

      const login = await apiPost("/auth/login", { email, password });
      saveToken(login.access_token);
      setAuthenticated(true);
      setCheckoutStatus("pending");
      await loadBilling();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Account creation failed");
    } finally {
      setCreatingAccount(false);
    }
  }

  async function launchCheckout(tier: PricingTier) {
    setError("");
    setCheckoutTierId(tier.id);

    const storageKey = checkoutStorageKey(tier.id);
    let idempotencyKey = sessionStorage.getItem(storageKey);
    if (!idempotencyKey) {
      idempotencyKey = newIdempotencyKey();
      sessionStorage.setItem(storageKey, idempotencyKey);
    }
    sessionStorage.setItem("billing-selected-tier", String(tier.id));

    try {
      const result = await apiPost("/api/billing/checkout-session", {
        pricing_tier_id: tier.id,
        idempotency_key: idempotencyKey,
      });
      if (!result?.url) {
        throw new Error("Checkout did not return a payment URL");
      }
      window.location.assign(result.url);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to start checkout");
      setCheckoutTierId(null);
    }
  }

  function signOut() {
    clearToken();
    setAuthenticated(false);
    setBillingState(null);
    setCatalog(null);
    setCheckoutStatus("");
    setError("");
  }

  const accountIsActive =
    billingState?.organization_state === "ACTIVE" &&
    billingState?.subscription?.status === "ACTIVE";

  if (!authenticated) {
    return (
      <main className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-200 p-6 py-12">
        <div className="mx-auto w-full max-w-2xl rounded-2xl bg-white p-8 shadow-lg">
          <div className="mb-8 text-center">
            <h1 className="text-3xl font-bold text-slate-900">
              Create your account
            </h1>
            <p className="mt-2 text-slate-500">
              Start your property management organization, then choose a plan.
            </p>
          </div>

          <form onSubmit={handleAccountCreate} className="space-y-5">
            <div>
              <label
                htmlFor="organization-name"
                className="mb-1 block text-sm font-medium text-slate-700"
              >
                Company name
              </label>
              <input
                id="organization-name"
                type="text"
                required
                minLength={2}
                maxLength={255}
                value={organizationName}
                onChange={(e) => setOrganizationName(e.target.value)}
                className="input"
                placeholder="Acme Property Management"
              />
            </div>

            <div className="grid gap-4 sm:grid-cols-2">
              <div>
                <label
                  htmlFor="first-name"
                  className="mb-1 block text-sm font-medium text-slate-700"
                >
                  First name
                </label>
                <input
                  id="first-name"
                  type="text"
                  required
                  maxLength={100}
                  value={firstName}
                  onChange={(e) => setFirstName(e.target.value)}
                  className="input"
                />
              </div>
              <div>
                <label
                  htmlFor="last-name"
                  className="mb-1 block text-sm font-medium text-slate-700"
                >
                  Last name
                </label>
                <input
                  id="last-name"
                  type="text"
                  required
                  maxLength={100}
                  value={lastName}
                  onChange={(e) => setLastName(e.target.value)}
                  className="input"
                />
              </div>
            </div>

            <div>
              <label
                htmlFor="signup-email"
                className="mb-1 block text-sm font-medium text-slate-700"
              >
                Email
              </label>
              <input
                id="signup-email"
                type="email"
                required
                autoComplete="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="input"
                placeholder="you@example.com"
              />
            </div>

            <div className="grid gap-4 sm:grid-cols-2">
              <div>
                <label
                  htmlFor="signup-password"
                  className="mb-1 block text-sm font-medium text-slate-700"
                >
                  Password
                </label>
                <input
                  id="signup-password"
                  type="password"
                  required
                  minLength={8}
                  maxLength={128}
                  autoComplete="new-password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="input"
                />
              </div>
              <div>
                <label
                  htmlFor="confirm-password"
                  className="mb-1 block text-sm font-medium text-slate-700"
                >
                  Confirm password
                </label>
                <input
                  id="confirm-password"
                  type="password"
                  required
                  minLength={8}
                  maxLength={128}
                  autoComplete="new-password"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  className="input"
                />
              </div>
            </div>

            {error && (
              <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={creatingAccount}
              className="w-full rounded-lg bg-slate-900 py-2.5 font-medium text-white transition hover:bg-slate-700 disabled:opacity-50"
            >
              {creatingAccount ? "Creating account..." : "Create account"}
            </button>
          </form>

          <div className="mt-6 rounded-lg border border-slate-200 bg-slate-50 p-4 text-sm text-slate-600">
            Payment details are entered only on Stripe Checkout after you
            choose a plan. Property Platform does not collect card numbers or
            security codes.
          </div>

          <p className="mt-6 text-center text-sm text-slate-500">
            Already have an account?{" "}
            <Link href="/login" className="font-medium text-slate-900 hover:underline">
              Log in
            </Link>
          </p>
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-slate-50 p-6 py-12">
      <div className="mx-auto max-w-5xl">
        <div className="mb-8 flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <h1 className="text-3xl font-bold text-slate-900">
              Choose your plan
            </h1>
            <p className="mt-2 text-slate-600">
              Select the property range that matches your organization.
            </p>
          </div>
          <button
            type="button"
            onClick={signOut}
            className="self-start rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-100"
          >
            Log out
          </button>
        </div>

        {checkoutStatus === "cancelled" && (
          <div className="mb-6 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
            Checkout was cancelled. Your account is saved and you can choose a
            plan when you are ready.
          </div>
        )}

        {checkoutStatus === "success" && !accountIsActive && (
          <div className="mb-6 rounded-lg border border-blue-200 bg-blue-50 px-4 py-3 text-sm text-blue-800">
            Stripe returned you to Property Platform. We are confirming the
            subscription from the signed payment webhook.
          </div>
        )}

        {error && (
          <div className="mb-6 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {error}
          </div>
        )}

        {billingLoading && !billingState ? (
          <div className="rounded-xl border border-slate-200 bg-white p-8 text-center text-slate-500">
            Loading billing status...
          </div>
        ) : accountIsActive ? (
          <div className="rounded-2xl border border-green-200 bg-white p-8 shadow-sm">
            <h2 className="text-2xl font-semibold text-slate-900">
              Your subscription is active
            </h2>
            <p className="mt-2 text-slate-600">
              {billingState?.subscription?.plan_name
                ? `${billingState.subscription.plan_name} is ready to use.`
                : "Your account is ready to use."}
            </p>
            <Link
              href="/dashboard"
              className="mt-6 inline-block rounded-lg bg-slate-900 px-5 py-2.5 font-medium text-white hover:bg-slate-700"
            >
              Go to dashboard
            </Link>
          </div>
        ) : (
          <>
            {checkoutStatus === "success" && (
              <div className="mb-6">
                <button
                  type="button"
                  onClick={() => void loadBilling()}
                  disabled={billingLoading}
                  className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-100 disabled:opacity-50"
                >
                  {billingLoading ? "Checking..." : "Refresh payment status"}
                </button>
              </div>
            )}

            {catalog && catalog.plans.length === 0 ? (
              <div className="rounded-2xl border border-slate-200 bg-white p-8">
                <h2 className="text-xl font-semibold text-slate-900">
                  Self-service plans are not configured yet
                </h2>
                <p className="mt-2 text-slate-600">
                  Your account is saved. An active plan and pricing tier must be
                  configured before Stripe Checkout can start.
                </p>
              </div>
            ) : (
              <div className="grid gap-6 lg:grid-cols-2">
                {catalog?.plans.map((plan) => (
                  <section
                    key={plan.id}
                    className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm"
                  >
                    <h2 className="text-xl font-semibold text-slate-900">
                      {plan.name}
                    </h2>
                    {plan.description && (
                      <p className="mt-2 text-sm text-slate-600">
                        {plan.description}
                      </p>
                    )}

                    <div className="mt-5 space-y-3">
                      {plan.pricing_tiers.length === 0 ? (
                        <p className="text-sm text-slate-500">
                          No self-service pricing tiers are available for this
                          plan.
                        </p>
                      ) : (
                        plan.pricing_tiers.map((tier) => (
                          <div
                            key={tier.id}
                            className="flex flex-col gap-3 rounded-xl border border-slate-200 p-4 sm:flex-row sm:items-center sm:justify-between"
                          >
                            <div>
                              <p className="font-medium text-slate-900">
                                {propertyRange(tier)}
                              </p>
                              <p className="text-sm text-slate-500">
                                {money(tier.monthly_price_cents, tier.currency)}
                                /month
                              </p>
                            </div>
                            <button
                              type="button"
                              onClick={() => void launchCheckout(tier)}
                              disabled={checkoutTierId !== null}
                              className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700 disabled:opacity-50"
                            >
                              {checkoutTierId === tier.id
                                ? "Opening Stripe..."
                                : "Choose plan"}
                            </button>
                          </div>
                        ))
                      )}
                    </div>
                  </section>
                ))}
              </div>
            )}

            <div className="mt-6 rounded-lg border border-slate-200 bg-white p-4 text-sm text-slate-600">
              Card details are collected by Stripe on its hosted Checkout page,
              not by Property Platform.
            </div>
          </>
        )}
      </div>
    </main>
  );
}
