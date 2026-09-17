import { NextRequest, NextResponse } from "next/server";
import { ACCESS_TOKEN_MAX_AGE, REFRESH_TOKEN_MAX_AGE } from "./lib/auth-cookies";

const API_URL = process.env.DJANGO_API_URL ?? "http://localhost:8000/api/v1";
const PUBLIC_PATHS = ["/login"];

export async function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const isPublic = PUBLIC_PATHS.some((p) => pathname.startsWith(p));

  const access = request.cookies.get("access_token")?.value;
  if (access) {
    if (isPublic) {
      return NextResponse.redirect(new URL("/account-items", request.url));
    }
    return NextResponse.next();
  }

  // Optimistic refresh: no access token, but maybe a still-valid refresh
  // token. This only reads the cookie and calls the auth server — it does
  // not touch business data, so it's safe to run on every request per the
  // Proxy guidance against slow work here.
  const refresh = request.cookies.get("refresh_token")?.value;
  if (refresh) {
    const refreshRes = await fetch(`${API_URL}/token/refresh/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh }),
    });
    if (refreshRes.ok) {
      const data = await refreshRes.json();
      const response = isPublic
        ? NextResponse.redirect(new URL("/account-items", request.url))
        : NextResponse.next();
      response.cookies.set("access_token", data.access, {
        httpOnly: true,
        secure: process.env.NODE_ENV === "production",
        sameSite: "lax",
        path: "/",
        maxAge: ACCESS_TOKEN_MAX_AGE,
      });
      if (data.refresh) {
        response.cookies.set("refresh_token", data.refresh, {
          httpOnly: true,
          secure: process.env.NODE_ENV === "production",
          sameSite: "lax",
          path: "/",
          maxAge: REFRESH_TOKEN_MAX_AGE,
        });
      }
      return response;
    }
  }

  if (isPublic) {
    return NextResponse.next();
  }
  return NextResponse.redirect(new URL("/login", request.url));
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico|icon|apple-icon).*)"],
};
