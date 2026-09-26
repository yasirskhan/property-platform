"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { apiPost, saveToken, apiGet, clearToken } from "@/lib/api";

type Me = { id: number; email: string; role: string; organization_id: number | null };
type LoginResult = {
  access_token?: string | null;
  token_type: string;
  two_factor_required: boolean;
  challenge_token?: string | null;
};

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [challengeToken, setChallengeToken] = useState("");
  const [twoFactorCode, setTwoFactorCode] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function finishLogin(accessToken: string) {
    saveToken(accessToken);
    const me: Me = await apiGet("/auth/me");
    const role = String(me.role || "").toUpperCase();
    if (me.organization_id && (role === "ADMIN" || role === "OWNER")) {
      const billing = await apiGet("/api/billing/state");
      if (billing.organization_state === "PENDING_BILLING") {
        router.push("/signup?checkout=pending");
        return;
      }
    }
    router.push("/dashboard");
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      if (challengeToken) {
        const verified: LoginResult = await apiPost("/auth/two-factor/verify", {
          challenge_token: challengeToken,
          code: twoFactorCode,
        });
        if (!verified.access_token) throw new Error("Two-step verification did not return a session.");
        await finishLogin(verified.access_token);
        return;
      }

      const loginResult: LoginResult = await apiPost("/auth/login", { email, password });
      if (loginResult.two_factor_required) {
        if (!loginResult.challenge_token) throw new Error("Two-step challenge could not be created.");
        setChallengeToken(loginResult.challenge_token);
        setPassword("");
        setLoading(false);
        return;
      }
      if (!loginResult.access_token) throw new Error("Login did not return a session.");
      await finishLogin(loginResult.access_token);
    } catch (err) {
      clearToken();
      setError(err instanceof Error ? err.message : "Login failed");
      setLoading(false);
    }
  }

  return (
    <main className="min-h-screen flex items-center justify-center bg-gradient-to-br from-slate-50 to-slate-200 p-6">
      <div className="w-full max-w-md bg-white rounded-2xl shadow-lg p-8">
        <div className="text-center mb-8">
          <h1 className="text-2xl font-bold text-slate-900">
            {challengeToken ? "Two-step verification" : "Welcome back"}
          </h1>
          <p className="text-slate-500 mt-1">
            {challengeToken
              ? "Enter the 6-digit code from your authenticator app or one recovery code."
              : "Log in to your Property Platform account"}
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-5">
          {!challengeToken ? (
            <>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Email</label>
                <input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} className="w-full px-4 py-2 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-slate-900" placeholder="you@example.com" />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Password</label>
                <input type="password" required value={password} onChange={(e) => setPassword(e.target.value)} className="w-full px-4 py-2 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-slate-900" placeholder="••••••••" />
              </div>
              <div className="text-right">
                <Link href="/forgot-password" className="text-sm text-slate-500 hover:underline">Forgot password?</Link>
              </div>
            </>
          ) : (
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Verification or recovery code</label>
              <input autoFocus required value={twoFactorCode} onChange={(e) => setTwoFactorCode(e.target.value)} className="w-full px-4 py-2 border border-slate-300 rounded-lg font-mono tracking-wider focus:outline-none focus:ring-2 focus:ring-slate-900" placeholder="123456" />
            </div>
          )}

          {error && <div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-lg px-4 py-3">{error}</div>}

          <button type="submit" disabled={loading} className="w-full bg-slate-900 text-white py-2.5 rounded-lg font-medium hover:bg-slate-700 disabled:opacity-50 transition">
            {loading ? "Checking..." : challengeToken ? "Verify" : "Log In"}
          </button>
          {challengeToken && (
            <button type="button" onClick={() => { setChallengeToken(""); setTwoFactorCode(""); setError(""); }} className="w-full text-sm text-slate-500 hover:underline">
              Use a different account
            </button>
          )}
        </form>

        <p className="mt-6 text-center text-sm">
          <Link href="/" className="text-slate-500 hover:underline">← Back to home</Link>
        </p>
      </div>
    </main>
  );
}
