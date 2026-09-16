"use server";

import { revalidatePath } from "next/cache";
import { apiMutate } from "@/lib/api";

export async function runTaxCalc(formData: FormData) {
  const company = formData.get("company");
  const month = formData.get("month");
  await apiMutate("/invoices/tax-calc/", "POST", {
    company: typeof company === "string" ? company : "",
    month,
  });
  revalidatePath("/invoices");
}

export async function markInvoiceSent(id: number) {
  await apiMutate(`/invoices/${id}/mark-sent/`, "POST");
  revalidatePath("/invoices");
}

export async function unmarkInvoiceSent(id: number) {
  await apiMutate(`/invoices/${id}/unmark-sent/`, "POST");
  revalidatePath("/invoices");
}
