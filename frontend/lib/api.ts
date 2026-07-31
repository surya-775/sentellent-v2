// In production the API_URL is intentionally "" — /api/* is same-origin, routed to the
// backend ALB by CloudFront (see infra/terraform/frontend.tf). Using `||` here would silently
// override that empty string with the localhost fallback, so check for undefined explicitly.
const API_URL = process.env.NEXT_PUBLIC_API_URL !== undefined ? process.env.NEXT_PUBLIC_API_URL : "http://localhost:8000";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("token");
}

export function setToken(token: string) {
  localStorage.setItem("token", token);
}

export function clearToken() {
  localStorage.removeItem("token");
}

async function request(path: string, options: RequestInit = {}) {
  const token = getToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string> | undefined),
  };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(`${API_URL}${path}`, { ...options, headers });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`API error ${res.status}: ${text}`);
  }
  return res.json();
}

export const api = {
  me: () => request("/api/auth/me"),
  followStock: (nse_symbol: string, name?: string) =>
    request("/api/stocks/follow", { method: "POST", body: JSON.stringify({ nse_symbol, name }) }),
  listFollowed: () => request("/api/stocks/followed"),
  chat: (message: string) => request("/api/chat", { method: "POST", body: JSON.stringify({ message }) }),
  chatHistory: () => request("/api/chat/history"),
};

export function googleLoginUrl() {
  return `${API_URL}/api/auth/google/login`;
}
