"use server";

import { revalidatePath } from "next/cache";
import { apiMutate, ApiError } from "@/lib/api";

type ModelChange = { label: string; create: number[]; update: number[]; delete: number[] };

export type PreviewState =
  | {
      diff: {
        organization: ModelChange;
        bank_account: number[];
        item_code: ModelChange;
        client: ModelChange;
        account_item: ModelChange;
        invoice_code: ModelChange;
      };
      conflicts: unknown[];
    }
  | { error: string }
  | undefined;

export type ApplyState =
  | {
      bank_account: number;
      item_code: number;
      client: number;
      account_item: number;
      invoice_code: number;
      deleted: { invoice_code: number; account_item: number; client: number; item_code: number };
    }
  | { error: string }
  | undefined;

async function readBackup(formData: FormData): Promise<unknown[] | { error: string }> {
  const file = formData.get("file");
  if (!(file instanceof File) || file.size === 0) {
    return { error: "Choose a backup JSON file first." };
  }
  let parsed: unknown;
  try {
    parsed = JSON.parse(await file.text());
  } catch {
    return { error: "That file isn't valid JSON." };
  }
  if (!Array.isArray(parsed)) {
    return { error: "Expected a dumpdata JSON array (the format produced by the existing backup)." };
  }
  if (parsed.length === 0) {
    return { error: "That file has no rows." };
  }
  return parsed;
}

export async function previewRestore(_prevState: PreviewState, formData: FormData): Promise<PreviewState> {
  const backup = await readBackup(formData);
  if (!Array.isArray(backup)) return backup;

  try {
    const res = await apiMutate("/restore/preview/", "POST", backup);
    return await res.json();
  } catch (e) {
    return { error: e instanceof ApiError ? e.message : "Preview failed." };
  }
}

export async function applyRestore(_prevState: ApplyState, formData: FormData): Promise<ApplyState> {
  const backup = await readBackup(formData);
  if (!Array.isArray(backup)) return backup;

  try {
    const res = await apiMutate("/restore/apply/", "POST", { backup, confirm: true });
    const body = await res.json();
    revalidatePath("/invoices");
    revalidatePath("/account-items");
    return body;
  } catch (e) {
    return { error: e instanceof ApiError ? e.message : "Restore failed." };
  }
}
