"use server";

import { apiMutate, ApiError } from "@/lib/api";

export type ImportState =
  | {
      created: number;
      replaced_periods: { company: number; month: string; removed: number; added: number; invoice_slug: string | null }[];
      errors: { index: number; detail: unknown }[];
    }
  | { error: string }
  | undefined;

export type DiffState =
  | {
      total: number;
      matched: number;
      missing: { index: number; slug: string }[];
      differing: { index: number; slug: string; diffs: Record<string, { file: unknown; db: unknown }> }[];
      errors: { index: number; detail: unknown }[];
    }
  | { error: string }
  | undefined;

// Shared by both actions: read the uploaded file and pull out the row
// array, accepting either a bare array or {"account_items": [...]}.
async function readAccountItems(formData: FormData): Promise<unknown[] | { error: string }> {
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

  const accountItems = Array.isArray(parsed)
    ? parsed
    : (parsed as { account_items?: unknown } | null)?.account_items;
  if (!Array.isArray(accountItems)) {
    return { error: 'Expected a JSON array, or an object with an "account_items" array — see the format below.' };
  }
  if (accountItems.length === 0) {
    return { error: "That file has no rows." };
  }
  return accountItems;
}

export async function importJson(_prevState: ImportState, formData: FormData): Promise<ImportState> {
  const accountItems = await readAccountItems(formData);
  if (!Array.isArray(accountItems)) return accountItems;

  const mode = formData.get("mode") === "replace" ? "replace" : "create";

  try {
    const res = await apiMutate("/import/", "POST", { account_items: accountItems, mode });
    const body = await res.json();
    return { created: body.created, replaced_periods: body.replaced_periods ?? [], errors: body.errors };
  } catch (e) {
    return { error: e instanceof ApiError ? e.message : "Import failed." };
  }
}

// Read-only: never creates, updates, or deletes anything. Matches each row
// to the database by `slug` and reports missing/differing/matching rows.
export async function diffImportJson(_prevState: DiffState, formData: FormData): Promise<DiffState> {
  const accountItems = await readAccountItems(formData);
  if (!Array.isArray(accountItems)) return accountItems;

  try {
    const res = await apiMutate("/account-items/diff-import/", "POST", { account_items: accountItems });
    return await res.json();
  } catch (e) {
    return { error: e instanceof ApiError ? e.message : "Comparison failed." };
  }
}
