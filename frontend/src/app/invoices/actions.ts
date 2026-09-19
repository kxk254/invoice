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

export type TaxAmounts = { bt: number; tax: number; at: number };

export type TaxCalcRow = {
  id: number;
  company_name: string;
  action_name: string;
  item_code: string;
  invoice_date: string;
  tax_rate: number;
  invoice_sent: boolean;
  current: TaxAmounts;
};

export type TaxCalcFill = TaxCalcRow & { after: TaxAmounts };
export type TaxCalcConflict = TaxCalcRow & { if_bt: TaxAmounts; if_at: TaxAmounts };
export type TaxCalcPlan = { fills: TaxCalcFill[]; conflicts: TaxCalcConflict[] };
export type TaxCalcResult = { applied: number; unresolved: number; amended_invoices: number };
export type TaxCalcResolutions = Record<number, "bt" | "at">;

export type TaxCalcDateField = "invoice_date" | "action_date";

export async function previewTaxCalc(
  company: string,
  month: string,
  dateField: TaxCalcDateField = "invoice_date",
): Promise<TaxCalcPlan | { error: string }> {
  try {
    const res = await apiMutate("/invoices/tax-calc-preview/", "POST", { company, month, date_field: dateField });
    return await res.json();
  } catch (e) {
    return { error: e instanceof ApiError ? e.message : "Request failed." };
  }
}

export async function applyTaxCalc(
  company: string,
  month: string,
  resolutions: TaxCalcResolutions,
  dateField: TaxCalcDateField = "invoice_date",
): Promise<TaxCalcResult | { error: string }> {
  try {
    const res = await apiMutate("/invoices/tax-calc/", "POST", { company, month, resolutions, date_field: dateField });
    const result = await res.json();
    revalidatePath("/invoices");
    revalidatePath("/account-items");
    return result;
  } catch (e) {
    return { error: e instanceof ApiError ? e.message : "Request failed." };
  }
}

export async function markInvoiceSent(id: number) {
  await apiMutate(`/invoices/${id}/mark-sent/`, "POST");
  revalidatePath("/invoices");
}

export async function unmarkInvoiceSent(id: number) {
  await apiMutate(`/invoices/${id}/unmark-sent/`, "POST");
  revalidatePath("/invoices");
}
