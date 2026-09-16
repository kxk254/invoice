import "server-only";
import { getAccessToken } from "./session";

const API_URL = process.env.DJANGO_API_URL ?? "http://localhost:8000/api/v1";

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

// For use in Server Components (GET) and Server Actions (mutations). Attaches
// the access token issued at login; proxy.ts keeps that token fresh before
// any page render, so this never needs to refresh it itself.
export async function apiFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const access = await getAccessToken();
  const headers = new Headers(init.headers);
  if (access) headers.set("Authorization", `Bearer ${access}`);
  if (init.body && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");

  return fetch(`${API_URL}${path}`, { ...init, headers, cache: "no-store" });
}

export async function apiGet<T>(path: string): Promise<T> {
  const res = await apiFetch(path);
  if (!res.ok) throw new ApiError(res.status, `GET ${path} failed: ${res.status}`);
  return res.json();
}

export async function apiMutate(path: string, method: "POST" | "PATCH" | "DELETE", body?: unknown): Promise<Response> {
  const res = await apiFetch(path, {
    method,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    const detail = await res.text();
    throw new ApiError(res.status, `${method} ${path} failed: ${res.status} ${detail}`);
  }
  return res;
}
