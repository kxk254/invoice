"use client";

import { useState, useTransition } from "react";
import Spinner from "@/components/Spinner";
import TaxRuleNote from "@/components/TaxRuleNote";
import {
  previewTaxCalc,
  applyTaxCalc,
  type TaxAmounts,
  type TaxCalcConflict,
  type TaxCalcFill,
  type TaxCalcDateField,
  type TaxCalcResult,
} from "./actions";

type Choice = "bt" | "at" | "skip";

const yen = new Intl.NumberFormat("ja-JP");

function Amounts({ a }: { a: TaxAmounts }) {
  return (
    <span className="tabular-nums">
      税抜 {yen.format(a.bt)} + 税 {yen.format(a.tax)} = 税込 {yen.format(a.at)}
    </span>
  );
}

function describe(result: TaxCalcResult) {
  const parts = [`${result.applied} line item(s) updated`];
  if (result.unresolved > 0) parts.push(`${result.unresolved} left unchanged`);
  if (result.amended_invoices > 0) parts.push(`${result.amended_invoices} sent invoice(s) marked 修正版`);
  return parts.join(", ") + ".";
}

export default function TaxCalcForm({
  company,
  month,
  dateField = "invoice_date",
}: {
  company: string;
  month: string;
  dateField?: TaxCalcDateField;
}) {
  const [pending, startTransition] = useTransition();
  const [message, setMessage] = useState<{ text: string; error?: boolean } | null>(null);
  const [dialog, setDialog] = useState<{ fills: TaxCalcFill[]; conflicts: TaxCalcConflict[] } | null>(null);
  const [choices, setChoices] = useState<Record<number, Choice>>({});

  function apply(resolutions: Record<number, "bt" | "at">) {
    startTransition(async () => {
      const result = await applyTaxCalc(company, month, resolutions, dateField);
      setDialog(null);
      setMessage("error" in result ? { text: result.error, error: true } : { text: describe(result) });
    });
  }

  function start() {
    setMessage(null);
    startTransition(async () => {
      const plan = await previewTaxCalc(company, month, dateField);
      if ("error" in plan) {
        setMessage({ text: plan.error, error: true });
        return;
      }
      if (plan.conflicts.length === 0) {
        const result = await applyTaxCalc(company, month, {}, dateField);
        setMessage("error" in result ? { text: result.error, error: true } : { text: describe(result) });
        return;
      }
      setChoices(Object.fromEntries(plan.conflicts.map((c) => [c.id, "skip" as Choice])));
      setDialog(plan);
    });
  }

  function confirm() {
    const resolutions: Record<number, "bt" | "at"> = {};
    for (const [id, choice] of Object.entries(choices)) {
      if (choice !== "skip") resolutions[Number(id)] = choice;
    }
    apply(resolutions);
  }

  const setAll = (choice: Choice) =>
    setChoices(Object.fromEntries((dialog?.conflicts ?? []).map((c) => [c.id, choice])));

  return (
    <div className="flex flex-col items-end gap-1">
      <button
        type="button"
        onClick={start}
        disabled={!month || pending}
        className="btn-secondary"
        title={month ? undefined : "Pick a month first"}
      >
        {pending && !dialog && <Spinner />}
        Recalculate tax
      </button>
      {message && <p className={`text-sm ${message.error ? "text-red-600" : "text-emerald-700"}`}>{message.text}</p>}

      {dialog && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 p-4" role="dialog" aria-modal="true">
          <div className="card flex max-h-[85vh] w-full max-w-3xl flex-col text-left">
            <div className="border-b border-slate-200 p-4">
              <h2 className="text-base font-semibold text-slate-900">
                {dialog.conflicts.length} line item(s) have 税抜 and 税込 amounts that don&apos;t match
              </h2>
              <p className="mt-1 text-sm text-slate-600">
                Choose which figure is correct for each row. The other one (and the tax) is recomputed from it.
                Rows left on &ldquo;Leave as is&rdquo; are not changed.
                {dialog.fills.length > 0 && ` ${dialog.fills.length} other row(s) with a missing amount are filled in automatically.`}
              </p>
              <TaxRuleNote className="mt-2" />
              <div className="mt-3 flex flex-wrap gap-2">
                <button type="button" className="btn-secondary" onClick={() => setAll("bt")}>Keep all 税抜</button>
                <button type="button" className="btn-secondary" onClick={() => setAll("at")}>Keep all 税込</button>
                <button type="button" className="btn-secondary" onClick={() => setAll("skip")}>Leave all as is</button>
              </div>
            </div>

            <ul className="divide-y divide-slate-100 overflow-y-auto p-4">
              {dialog.conflicts.map((c) => (
                <li key={c.id} className="py-3 text-sm">
                  <p className="font-medium text-slate-900">
                    {c.company_name} · {c.item_code}
                    {c.action_name && <span className="font-normal text-slate-500"> — {c.action_name}</span>}
                    <span className="ml-2 font-normal text-slate-500">({c.tax_rate}%)</span>
                    {c.invoice_sent && <span className="ml-2 badge-neutral text-amber-700">sent — will become 修正版</span>}
                  </p>
                  <p className="mt-0.5 text-slate-500">
                    Now: <Amounts a={c.current} />
                  </p>
                  <div className="mt-2 flex flex-col gap-1">
                    {(
                      [
                        ["bt", "Keep 税抜", c.if_bt],
                        ["at", "Keep 税込", c.if_at],
                      ] as const
                    ).map(([value, label, amounts]) => (
                      <label key={value} className="flex items-center gap-2">
                        <input
                          type="radio"
                          name={`choice-${c.id}`}
                          checked={choices[c.id] === value}
                          onChange={() => setChoices((prev) => ({ ...prev, [c.id]: value }))}
                        />
                        <span className="w-24 font-medium text-slate-700">{label}</span>
                        <span className="text-slate-600">→ <Amounts a={amounts} /></span>
                      </label>
                    ))}
                    <label className="flex items-center gap-2">
                      <input
                        type="radio"
                        name={`choice-${c.id}`}
                        checked={choices[c.id] === "skip"}
                        onChange={() => setChoices((prev) => ({ ...prev, [c.id]: "skip" }))}
                      />
                      <span className="font-medium text-slate-700">Leave as is</span>
                    </label>
                  </div>
                </li>
              ))}
            </ul>

            <div className="flex justify-end gap-2 border-t border-slate-200 p-4">
              <button type="button" className="btn-secondary" onClick={() => setDialog(null)} disabled={pending}>
                Cancel
              </button>
              <button type="button" className="btn-primary" onClick={confirm} disabled={pending}>
                {pending && <Spinner />}
                Apply
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
