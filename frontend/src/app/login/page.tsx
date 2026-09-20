// ============================================================
// Login Page
// ------------------------------------------------------------
// Users enter email + password, we call the backend, store the
// JWT, and redirect based on role.
//
// Roles come back from the backend UPPERCASE (ADMIN, OWNER, ...).
// ============================================================

"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { apiPost, saveToken, apiGet } from "@/lib/api";

type Me = {
  id: number;
  email: string;
  role: string;
  organization_id: number | null;
};

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      // 1. Log in — get the token
      const loginResult = await apiPost("/auth/login", { email, password });
      saveToken(loginResult.access_token);

      // 2. Fetch the user's profile
      const me: Me = await apiGet("/auth/me");

      // 3. Everyone lands on the shared dashboard.
      //    The dashboard layout reads the role and renders the
      //    right sidebar items based on menu permissions.
      router.push("/dashboard");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
      setLoading(false);
    }
  }

  return (
    <main className="min-h-screen flex items-center justify-center bg-gradient-to-br from-slate-50 to-slate-200 p-6">
      <div className="w-full max-w-md bg-white rounded-2xl shadow-lg p-8">
        <div className="text-center mb-8">
          <h1 className="text-2xl font-bold text-slate-900">Welcome back</h1>
          <p className="text-slate-500 mt-1">
            Log in to your Property Platform account
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-5">
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">
              Email
            </label>
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full px-4 py-2 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-slate-900 focus:border-transparent"
              placeholder="you@example.com"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">
              Password
            </label>
            <input
              type="password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full px-4 py-2 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-slate-900 focus:border-transparent"
              placeholder="••••••••"
            />
          </div>
          <div className="text-right">
            <Link
              href="/forgot-password"
              className="text-sm text-slate-500 hover:underline"
            >
              Forgot password?
            </Link>
          </div>

          {error && (
            <div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-lg px-4 py-3">
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={loading}
            className="w-full bg-slate-900 text-white py-2.5 rounded-lg font-medium hover:bg-slate-700 disabled:opacity-50 transition"
          >
            {loading ? "Logging in..." : "Log In"}
          </button>
        </form>

        <p className="mt-6 text-center text-sm">
          <Link href="/" className="text-slate-500 hover:underline">
            ← Back to home
          </Link>
        </p>
      </div>
    </main>
  );
}