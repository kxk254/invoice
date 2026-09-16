"use server";

import { redirect } from "next/navigation";
import { setTokens, clearTokens } from "@/lib/session";

const API_URL = process.env.DJANGO_API_URL ?? "http://localhost:8000/api/v1";

export type LoginState = { error?: string } | undefined;

export async function login(_prevState: LoginState, formData: FormData): Promise<LoginState> {
  const username = formData.get("username");
  const password = formData.get("password");

  const res = await fetch(`${API_URL}/token/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });

  if (!res.ok) {
    return { error: "Invalid username or password." };
  }

  const data = await res.json();
  await setTokens(data.access, data.refresh);
  redirect("/account-items");
}

export async function logout() {
  await clearTokens();
  redirect("/login");
}
