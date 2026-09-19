"use server";

import { revalidatePath } from "next/cache";
import { apiFetch, apiMutate } from "@/lib/api";

const DATE_FIELDS = ["invoice_date", "payment_due", "action_date"];
const TEXT_FIELDS = ["action_name", "action_note"];
const NUM_FIELDS = ["company", "item_code", "invoice_bt", "invoice_tax", "invoice_at"];
const DEFAULT_TAX_RATE = 10;

function coerceField(field: string, raw: FormDataEntryValue | null): unknown {
  const s = typeof raw === "string" ? raw : "";
  if (field === "tax_rate") return s.length > 0 ? Number(s) : DEFAULT_TAX_RATE;
  if (NUM_FIELDS.includes(field)) return s.length > 0 ? Number(s) : 0;
  if (DATE_FIELDS.includes(field) || TEXT_FIELDS.includes(field)) return s.length > 0 ? s : null;
  return raw;
}

// Used only by the "add row" line, whose inputs keep plain (unsuffixed)
// names since it isn't part of the bulk-save payload.
function accountItemPayload(formData: FormData): Record<string, unknown> {
  const payload: Record<string, unknown> = {};
  for (const field of [...NUM_FIELDS, "tax_rate", ...DATE_FIELDS, ...TEXT_FIELDS]) {
    if (!formData.has(field)) continue;
    payload[field] = coerceField(field, formData.get(field));
  }
  return payload;
}

export async function createAccountItem(formData: FormData) {
  await apiMutate("/account-items/", "POST", accountItemPayload(formData));
  revalidatePath("/account-items");
}

export async function deleteAccountItem(id: number) {
  await apiMutate(`/account-items/${id}/`, "DELETE");
  revalidatePath("/account-items");
}

// Existing rows share one <form> and name their inputs "field__<id>" so a
// single submit can save every edited row for the month in one request.
const NAME_SEP = "__";

export type BulkUpdateState = { error: string } | undefined;

// Field errors come back as {field: "message"} or {field: ["message", ...]}.
function messagesFrom(detail: unknown): string[] {
  if (typeof detail === "string") return [detail];
  if (Array.isArray(detail)) return detail.flatMap(messagesFrom);
  if (detail && typeof detail === "object") return Object.values(detail).flatMap(messagesFrom);
  return [];
}

// Returns a refusal (e.g. "that invoice was already sent") as state for the
// form to show, rather than throwing - these are expected, not crashes.
export async function bulkUpdateAccountItems(_prev: BulkUpdateState, formData: FormData): Promise<BulkUpdateState> {
  const rows = new Map<number, Record<string, unknown>>();
  for (const [key, value] of formData.entries()) {
    const sep = key.lastIndexOf(NAME_SEP);
    if (sep === -1) continue; // the "add row" draft's plain-named fields, not part of this save
    const field = key.slice(0, sep);
    const id = Number(key.slice(sep + NAME_SEP.length));
    if (!Number.isFinite(id)) continue;
    if (!rows.has(id)) rows.set(id, { id });
    rows.get(id)![field] = coerceField(field, value);
  }
  if (rows.size === 0) return undefined;

  const res = await apiFetch("/account-items/bulk-update/", {
    method: "POST",
    body: JSON.stringify({ items: Array.from(rows.values()) }),
  });
  if (res.status === 400) {
    const body = await res.json().catch(() => null);
    const messages = [...new Set(messagesFrom(body?.errors ?? body?.detail))];
    return { error: messages.length > 0 ? messages.join(" ") : "Some rows could not be saved. Nothing was changed." };
  }
  if (!res.ok) return { error: `Saving failed (${res.status}). Nothing was changed.` };

  revalidatePath("/account-items");
  return undefined;
}
