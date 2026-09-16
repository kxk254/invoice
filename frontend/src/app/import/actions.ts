"use server";

import { apiMutate, ApiError } from "@/lib/api";

export type ImportState =
  | { created: number; errors: { index: number; detail: unknown }[] }
  | { error: string }
  | undefined;

export async function importJson(_prevState: ImportState, formData: FormData): Promise<ImportState> {
  const file = formData.get("file");
  if (!(file instanceof File) || file.size === 0) {
    return { error: "Choose a JSON file first." };
  }

  let parsed: unknown;
  try {
    parsed = JSON.parse(await file.text());
  } catch {
    return { error: "That file isn't valid JSON." };
  }

  // Accept either {"account_items": [...]} or a bare top-level array.
  const accountItems = Array.isArray(parsed)
    ? parsed
    : (parsed as { account_items?: unknown } | null)?.account_items;
  if (!Array.isArray(accountItems)) {
    return { error: 'Expected a JSON array, or an object with an "account_items" array — see the format below.' };
  }
  if (accountItems.length === 0) {
    return { error: "That file has no rows to import." };
  }

  try {
    const res = await apiMutate("/import/", "POST", { account_items: accountItems });
    const body = await res.json();
    return { created: body.created, errors: body.errors };
  } catch (e) {
    return { error: e instanceof ApiError ? e.message : "Import failed." };
  }
}
