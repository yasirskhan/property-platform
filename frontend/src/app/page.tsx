// ============================================================
// Home Page
// ------------------------------------------------------------
// This is the first page a visitor sees at http://localhost:3000
// For now, it's a simple landing page with links to login/signup.
// Later, this will route based on role if the user is logged in.
// ============================================================

import Link from "next/link";

export default function HomePage() {
  return (
    <main className="min-h-screen flex flex-col items-center justify-center bg-gradient-to-br from-slate-50 to-slate-200 p-8">
      <div className="max-w-2xl text-center">
        <h1 className="text-5xl font-bold text-slate-900 mb-4">
          Property Platform
        </h1>
        <p className="text-lg text-slate-600 mb-12">
          Manage properties, tenants, leases, payments, and maintenance — all in one place.
        </p>

        <div className="flex gap-4 justify-center">
          <Link
            href="/login"
            className="px-6 py-3 bg-slate-900 text-white rounded-lg font-medium hover:bg-slate-700 transition"
          >
            Log In
          </Link>
          <Link
            href="/signup"
            className="px-6 py-3 bg-white text-slate-900 border border-slate-300 rounded-lg font-medium hover:bg-slate-50 transition"
          >
            Sign Up
          </Link>
        </div>
      </div>

      <footer className="mt-16 text-sm text-slate-500">
        Property Platform v0.1.0
      </footer>
    </main>
  );
}