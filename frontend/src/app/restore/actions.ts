"use server";

import { revalidatePath } from "next/cache";
import { apiMutate, ApiError } from "@/lib/api";

type ModelChange = { label: string; create: number[]; kept: number[]; remapped: number; skipped_sent: number; skipped_partial: number };

export type RestorePeriod = {
  period: string;
  company_name: string | null;
  sent: boolean;
  live_lines: number;
  decision: "add" | "skip" | null;
  lines: { invoice_date: string | null; action_name: string; invoice_bt: number }[];
};

export type PreviewState =
  | {
      periods: RestorePeriod[];
      diff: {
        bank_account: ModelChange;
        item_code: ModelChange;
        client: ModelChange;
        account_item: ModelChange;
        invoice_code: ModelChange;
      };
      conflicts: unknown[];
    }
  | { error: string }
  | undefined;

type Counts = { bank_account: number; item_code: number; client: number; account_item: number; invoice_code: number };

export type ApplyState =
  | { added: Counts; kept: Counts; renumbered: Counts; skipped_sent: Counts; skipped_partial: Counts; backup_file: string | null }
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
    // Per-period choices for periods that are already partly in the database
    // ("add" the missing lines, or leave the period alone - the default).
    let decisions: Record<string, "add" | "skip"> = {};
    const raw = formData.get("decisions");
    if (typeof raw === "string" && raw) {
      try {
        decisions = JSON.parse(raw);
      } catch {
        return { error: "Could not read the period choices." };
      }
    }
    const res = await apiMutate("/restore/apply/", "POST", { backup, confirm: true, decisions });
    const body = await res.json();
    revalidatePath("/invoices");
    revalidatePath("/account-items");
    return body;
  } catch (e) {
    return { error: e instanceof ApiError ? e.message : "Restore failed." };
  }
}
