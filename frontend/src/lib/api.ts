// ============================================================
// api.ts
// ------------------------------------------------------------
// Small helper to talk to our FastAPI backend.
//
// All frontend → backend calls go through this file.
// That way, if the backend URL changes later, we change it
// in one place.
// ============================================================

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

// ------------------------------------------------------------
// Basic fetch wrapper with auth token support
// ------------------------------------------------------------
export async function apiFetch(
  path: string,
  options: RequestInit = {}
): Promise<Response> {
  const token =
    typeof window !== "undefined" ? localStorage.getItem("token") : null;

  const headers: HeadersInit = {
    "Content-Type": "application/json",
    ...(options.headers || {}),
  };

  if (token) {
    (headers as Record<string, string>)["Authorization"] = `Bearer ${token}`;
  }

  return fetch(`${API_URL}${path}`, {
    ...options,
    headers,
  });
}

// ------------------------------------------------------------
// Convenience wrappers
// ------------------------------------------------------------
export async function apiGet(path: string) {
  const res = await apiFetch(path, { method: "GET" });
  if (!res.ok) throw new Error(await errorMessage(res));
  return res.json();
}

export async function apiPost(path: string, body?: unknown) {
  const res = await apiFetch(path, {
    method: "POST",
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) throw new Error(await errorMessage(res));
  if (res.status === 204) return null;
  return res.json();
}

export async function apiPatch(path: string, body?: unknown) {
  const res = await apiFetch(path, {
    method: "PATCH",
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) throw new Error(await errorMessage(res));
  return res.json();
}

export async function apiPut(path: string, body?: unknown) {
  const res = await apiFetch(path, {
    method: "PUT",
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) throw new Error(await errorMessage(res));
  if (res.status === 204) return null;
  return res.json();
}

export async function apiDelete(path: string) {
  const res = await apiFetch(path, { method: "DELETE" });
  if (!res.ok) throw new Error(await errorMessage(res));
  return null;
}

// ------------------------------------------------------------
// Extract a readable error message from the response
// ------------------------------------------------------------
async function errorMessage(res: Response): Promise<string> {
  try {
    const data = await res.json();
    if (typeof data.detail === "string") return data.detail;
    if (Array.isArray(data.detail)) {
      return data.detail.map((d: { msg: string }) => d.msg).join(", ");
    }
    return JSON.stringify(data);
  } catch {
    return `Request failed (${res.status})`;
  }
}

// ------------------------------------------------------------
// Auth helpers
// ------------------------------------------------------------
export function saveToken(token: string) {
  if (typeof window !== "undefined") localStorage.setItem("token", token);
}

export function clearToken() {
  if (typeof window !== "undefined") localStorage.removeItem("token");
}

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("token");
}

export function isLoggedIn(): boolean {
  return !!getToken();
}

// ------------------------------------------------------------
// File upload helper (multipart/form-data)
// ------------------------------------------------------------
export async function apiUpload(file: File): Promise<{
  url: string;
  filename: string;
  original_name: string;
  size: number;
  content_type: string;
}> {
  const formData = new FormData();
  formData.append("file", file);

  const token = getToken();
  const headers: HeadersInit = {};
  if (token) {
    (headers as Record<string, string>)["Authorization"] = `Bearer ${token}`;
  }

  const res = await fetch(`${API_URL}/uploads`, {
    method: "POST",
    headers,
    body: formData,
  });

  if (!res.ok) {
    let detail = `Upload failed (${res.status})`;
    try {
      const data = await res.json();
      if (typeof data.detail === "string") detail = data.detail;
    } catch {}
    throw new Error(detail);
  }

  return res.json();
}

// ------------------------------------------------------------
// Full URL for a stored file path (e.g. "/uploads/abc.pdf")
// ------------------------------------------------------------
export function fileUrl(path: string | null | undefined): string {
  if (!path) return "";
  if (path.startsWith("http")) return path;
  return `${API_URL}${path}`;
}