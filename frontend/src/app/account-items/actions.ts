"use server";

import { revalidatePath } from "next/cache";
import { apiMutate } from "@/lib/api";

const DATE_FIELDS = ["invoice_date", "payment_due", "action_date"];
const TEXT_FIELDS = ["action_name", "action_note"];
const NUM_FIELDS = ["invoice_bt", "invoice_tax", "invoice_at"];

// Only include a key if the submitted form actually has that field, so a
// row's PATCH never nulls out a field the UI doesn't render for editing —
// PATCH only touches keys present in the payload.
function accountItemPayload(formData: FormData): Record<string, unknown> {
  const payload: Record<string, unknown> = {
    company: Number(formData.get("company")),
    item_code: Number(formData.get("item_code")),
  };
  for (const key of [...DATE_FIELDS, ...TEXT_FIELDS]) {
    if (!formData.has(key)) continue;
    const v = formData.get(key);
    payload[key] = typeof v === "string" && v.length > 0 ? v : null;
  }
  for (const key of NUM_FIELDS) {
    if (!formData.has(key)) continue;
    const v = formData.get(key);
    payload[key] = typeof v === "string" && v.length > 0 ? Number(v) : 0;
  }
  return payload;
}

export async function createAccountItem(formData: FormData) {
  await apiMutate("/account-items/", "POST", accountItemPayload(formData));
  revalidatePath("/account-items");
}

export async function updateAccountItem(id: number, formData: FormData) {
  await apiMutate(`/account-items/${id}/`, "PATCH", accountItemPayload(formData));
  revalidatePath("/account-items");
}

export async function deleteAccountItem(id: number) {
  await apiMutate(`/account-items/${id}/`, "DELETE");
  revalidatePath("/account-items");
}
