"use server";

import { revalidatePath } from "next/cache";
import { apiMutate, ApiError } from "@/lib/api";

export type AlignDatesChange = {
  id: number;
  company_id: number;
  company_name: string;
  period: string;
  current: string;
  target: string;
};

export type AlignDatesTie = {
  company_id: number;
  company_name: string;
  period: string;
  candidates: Record<string, number>;
};

export type AlignDatesState =
  | { changes: AlignDatesChange[]; skipped_ties: AlignDatesTie[]; applied?: number }
  | { error: string }
  | undefined;

async function runAlignDates(path: string, formData: FormData): Promise<AlignDatesState> {
  const company = formData.get("company");
  const month = formData.get("month");
  if (typeof month !== "string" || !month) return { error: "Pick a month first." };
  try {
    const res = await apiMutate(path, "POST", {
      company: typeof company === "string" ? company : "",
      month,
    });
    return await res.json();
  } catch (e) {
    return { error: e instanceof ApiError ? e.message : "Request failed." };
  }
}

export async function previewAlignInvoiceDates(_prev: AlignDatesState, formData: FormData): Promise<AlignDatesState> {
  return runAlignDates("/account-items/align-invoice-dates-preview/", formData);
}

export async function applyAlignInvoiceDates(_prev: AlignDatesState, formData: FormData): Promise<AlignDatesState> {
  const result = await runAlignDates("/account-items/align-invoice-dates/", formData);
  if (!("error" in (result ?? {}))) {
    revalidatePath("/invoices");
    revalidatePath("/account-items");
  }
  return result;
}

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
