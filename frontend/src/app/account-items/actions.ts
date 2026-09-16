"use server";

import { revalidatePath } from "next/cache";
import { apiMutate } from "@/lib/api";

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

export async function bulkUpdateAccountItems(formData: FormData) {
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
  if (rows.size === 0) return;

  await apiMutate("/account-items/bulk-update/", "POST", { items: Array.from(rows.values()) });
  revalidatePath("/account-items");
}
