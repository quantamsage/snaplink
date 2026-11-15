// The ONLY place the frontend talks to the backend. No business logic here: it sends
// requests, attaches the token, and turns error responses into friendly messages.
import { clearToken, getToken } from "./auth";

const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/$/, "");

export type User = { id: number; email: string; created_at: string };
export type Link = {
  id: number;
  code: string;
  short_url: string;
  target_url: string;
  created_at: string;
  click_count: number;
  expires_at: string | null;
  max_clicks: number | null;
  active: boolean;
  inactive_reason: "expired" | "click_limit" | null;
};
export type LinkLimits = { expires_at?: string | null; max_clicks?: number | null };
export type LinkList = { items: Link[]; total: number };
export type LinkStats = {
  link_id: number;
  total_clicks: number;
  window_clicks: number;
  days: number;
  daily: { date: string; clicks: number }[];
  top_referrers: { referrer: string; clicks: number }[];
};

export class ApiError extends Error {
  constructor(public status: number, public code: string, message: string) {
    super(message);
  }
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await send(path, options);
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

async function send(path: string, options: RequestInit = {}): Promise<Response> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;

  let response: Response;
  try {
    response = await fetch(`${API_URL}${path}`, { ...options, headers });
  } catch {
    throw new ApiError(
      0,
      "network_error",
      "Can't reach the server. Check that the backend is running, then try again.",
    );
  }

  if (!response.ok) {
    let body: unknown = null;
    try {
      body = await response.json();
    } catch {
      // Non-JSON reply (e.g. a proxy error page): fall through to the generic message.
    }
    const err = (body as { error?: { code?: string; message?: string } } | null)?.error;
    if (response.status === 401 && token) clearToken(); // expired or invalid session
    throw new ApiError(response.status, err?.code ?? "error", err?.message ?? "Something went wrong. Please try again.");
  }
  return response;
}

export const api = {
  register: (email: string, password: string) =>
    request<User>("/api/auth/register", { method: "POST", body: JSON.stringify({ email, password }) }),
  login: (email: string, password: string) =>
    request<{ access_token: string; expires_in: number }>("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),
  me: () => request<User>("/api/auth/me"),
  listLinks: () => request<LinkList>("/api/links?limit=100"),
  createLink: (target_url: string, custom_code: string | null, limits: LinkLimits = {}) =>
    request<Link>("/api/links", { method: "POST", body: JSON.stringify({ target_url, custom_code, ...limits }) }),
  updateLimits: (id: number, limits: LinkLimits) =>
    request<Link>(`/api/links/${id}`, { method: "PATCH", body: JSON.stringify(limits) }),
  /** QR image as a Blob (the endpoint needs the token, so an <img src> can't load it directly). */
  qrCode: async (id: number, format: "svg" | "png") =>
    (await send(`/api/links/${id}/qr?format=${format}`)).blob(),
  getLink: (id: string) => request<Link>(`/api/links/${encodeURIComponent(id)}`),
  deleteLink: (id: number) => request<void>(`/api/links/${id}`, { method: "DELETE" }),
  stats: (id: string, days: number) =>
    request<LinkStats>(`/api/links/${encodeURIComponent(id)}/stats?days=${days}`),
};
