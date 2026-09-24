const API_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

const TOKEN_KEY = "platform_access_token";

export type PlatformUser = {
  id: number;
  email: string;
  role: string;
  is_active: boolean;
};

export function savePlatformToken(token: string) {
  if (typeof window !== "undefined") localStorage.setItem(TOKEN_KEY, token);
}

export function clearPlatformToken() {
  if (typeof window !== "undefined") localStorage.removeItem(TOKEN_KEY);
}

export function getPlatformToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN_KEY);
}

async function errorMessage(res: Response): Promise<string> {
  try {
    const data = await res.json();
    if (typeof data.detail === "string") return data.detail;
    if (Array.isArray(data.detail)) {
      return data.detail
        .map((item: { msg?: string }) => item.msg || JSON.stringify(item))
        .join(", ");
    }
    return JSON.stringify(data);
  } catch {
    return "Request failed (" + res.status + ")";
  }
}

export async function platformFetch(
  path: string,
  options: RequestInit = {}
): Promise<Response> {
  const token = getPlatformToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...((options.headers || {}) as Record<string, string>),
  };
  if (token) headers.Authorization = "Bearer " + token;

  return fetch(API_URL + path, {
    ...options,
    headers,
  });
}

async function platformJson(path: string, options: RequestInit = {}) {
  const res = await platformFetch(path, options);
  if (!res.ok) throw new Error(await errorMessage(res));
  if (res.status === 204) return null;
  return res.json();
}

export function platformGet(path: string) {
  return platformJson(path, { method: "GET" });
}

export function platformPost(path: string, body: unknown) {
  return platformJson(path, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function platformPatch(path: string, body: unknown) {
  return platformJson(path, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}

export function platformPut(path: string, body: unknown) {
  return platformJson(path, {
    method: "PUT",
    body: JSON.stringify(body),
  });
}
