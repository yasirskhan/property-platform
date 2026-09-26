"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import {
  clearPlatformToken,
  platformGet,
  platformPost,
  savePlatformToken,
} from "@/lib/platformApi";

export default function PlatformLoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const token = await platformPost("/api/platform/auth/login", {
        email,
        password,
      });
      savePlatformToken(token.access_token);
      await platformGet("/api/platform/auth/me");
      router.replace("/dashboard");
    } catch (err) {
      clearPlatformToken();
      setError(err instanceof Error ? err.message : "Login failed");
      setBusy(false);
    }
  }

  return (
    <main className="min-h-screen bg-slate-950 flex items-center justify-center p-6">
      <div className="w-full max-w-md rounded-2xl bg-white p-8 shadow-2xl">
        <p className="text-xs font-semibold tracking-[0.2em] text-slate-500 uppercase">
          Internal Operations
        </p>
        <h1 className="mt-2 text-2xl font-bold text-slate-950">Platform Admin</h1>
        <p className="mt-2 text-sm text-slate-500">
          Platform staff credentials only. Customer accounts cannot sign in here.
        </p>
        <form className="mt-8 space-y-5" onSubmit={submit}>
          <label className="block text-sm font-medium">
            Email
            <input className="input mt-1" type="email" autoComplete="username" required value={email} onChange={(event) => setEmail(event.target.value)} />
          </label>
          <label className="block text-sm font-medium">
            Password
            <input className="input mt-1" type="password" autoComplete="current-password" required value={password} onChange={(event) => setPassword(event.target.value)} />
          </label>
          {error ? <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</div> : null}
          <button type="submit" disabled={busy} className="w-full rounded-lg bg-slate-950 px-4 py-2.5 font-medium text-white disabled:opacity-50">
            {busy ? "Signing in…" : "Sign in"}
          </button>
        </form>
      </div>
    </main>
  );
}
