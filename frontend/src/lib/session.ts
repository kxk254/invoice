import "server-only";
import { cookies } from "next/headers";
import { ACCESS_TOKEN_MAX_AGE } from "./auth-cookies";

const cookieOpts = {
  httpOnly: true,
  secure: process.env.NODE_ENV === "production",
  sameSite: "lax" as const,
  path: "/",
};

// Can only be called from a Server Action or Route Handler (cookies() is
// read-only during Server Component render).
export async function setTokens(access: string, refresh?: string) {
  const store = await cookies();
  store.set("access_token", access, { ...cookieOpts, maxAge: ACCESS_TOKEN_MAX_AGE });
  if (refresh) {
    // No maxAge: a session cookie, dropped when the browser closes.
    store.set("refresh_token", refresh, cookieOpts);
  }
}

export async function clearTokens() {
  const store = await cookies();
  store.delete("access_token");
  store.delete("refresh_token");
}

export async function getAccessToken(): Promise<string | undefined> {
  const store = await cookies();
  return store.get("access_token")?.value;
}
