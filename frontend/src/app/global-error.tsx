"use client";

import { useEffect } from "react";

import { reportClientError } from "@/lib/report-client-error";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    void reportClientError(error);
  }, [error]);

  return (
    <html lang="en">
      <body>
        <main className="mx-auto flex min-h-screen max-w-lg flex-col justify-center gap-4 p-6">
          <h1 className="text-2xl font-semibold">Something went wrong</h1>
          <p className="text-sm">
            The error was reported. You can try the application again.
          </p>
          <button type="button" onClick={reset} className="w-fit rounded border px-4 py-2">
            Try again
          </button>
        </main>
      </body>
    </html>
  );
}
