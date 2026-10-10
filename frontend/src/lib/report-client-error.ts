export async function reportClientError(error: Error): Promise<void> {
  const apiUrl =
    process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

  const message = error.message.slice(0, 2000);
  const stack = error.stack?.slice(0, 12000);
  const path =
    typeof window !== "undefined"
      ? window.location.pathname.slice(0, 500)
      : undefined;

  try {
    await fetch(`${apiUrl}/api/observability/client-error`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message, stack, path }),
      keepalive: true,
    });
  } catch {
    // Error reporting must never create a second application failure.
  }
}
