"use client";

import { useActionState } from "react";
import Spinner from "@/components/Spinner";
import { previewAlignInvoiceDates, applyAlignInvoiceDates, type AlignDatesState } from "./actions";

const dateFmt = new Intl.DateTimeFormat("ja-JP", { dateStyle: "medium" });

function fmt(iso: string) {
  return dateFmt.format(new Date(iso));
}

// Each button's result is shown under its own state only (never merged into
// one panel) - two independent useActionState hooks means whichever ran
// last is not otherwise knowable, so showing "the newest one" would risk
// displaying a stale Apply result after a later Preview, or vice versa.
function ResultPanel({ state, appliedLabel }: { state: AlignDatesState; appliedLabel: string }) {
  if (!state) return null;
  if ("error" in state) return <p className="mt-2 text-sm text-red-600">{state.error}</p>;

  const { changes, skipped_ties } = state;
  if (changes.length === 0 && skipped_ties.length === 0) {
    return <p className="mt-2 text-sm text-emerald-700">Every invoice date already agrees within its period.</p>;
  }

  return (
    <div className="mt-2 rounded-md border border-slate-200 bg-slate-50 p-4 text-left text-sm">
      {changes.length > 0 && (
        <>
          <p className="font-medium text-slate-900">
            {changes.length} line item(s) {appliedLabel}:
          </p>
          <ul className="mt-1 list-disc pl-5 text-slate-600">
            {changes.map((c) => (
              <li key={c.id}>
                {c.company_name} ({c.period}): {fmt(c.current)} → {fmt(c.target)}
              </li>
            ))}
          </ul>
        </>
      )}
      {skipped_ties.length > 0 && (
        <>
          <p className="mt-3 font-medium text-amber-700">
            {skipped_ties.length} period(s) have no clear majority date — left unchanged:
          </p>
          <ul className="mt-1 list-disc pl-5 text-slate-600">
            {skipped_ties.map((t, i) => (
              <li key={i}>
                {t.company_name} ({t.period}):{" "}
                {Object.entries(t.candidates)
                  .map(([date, count]) => `${fmt(date)} ×${count}`)
                  .join(", ")}
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}

export default function AlignDatesForm({ company, month }: { company: string; month: string }) {
  const [previewState, previewAction, previewPending] = useActionState(previewAlignInvoiceDates, undefined);
  const [applyState, applyAction, applyPending] = useActionState(applyAlignInvoiceDates, undefined);

  const disabled = !month || previewPending || applyPending;

  return (
    <div className="flex flex-col items-end gap-2">
      <form className="flex flex-wrap items-end gap-2">
        <input type="hidden" name="company" value={company} />
        <input type="hidden" name="month" value={month} />
        <button
          type="submit"
          formAction={previewAction}
          disabled={disabled}
          className="btn-secondary"
          title={month ? "Same invoice period, mismatched issue dates — see which rows would change" : "Pick a month first"}
        >
          {previewPending && <Spinner />}
          {previewPending ? "Checking..." : "Preview date alignment"}
        </button>
        <button
          type="submit"
          formAction={applyAction}
          disabled={disabled}
          className="btn-secondary"
          title={month ? undefined : "Pick a month first"}
        >
          {applyPending && <Spinner />}
          {applyPending ? "Aligning..." : "Align invoice dates"}
        </button>
      </form>
      <div className="w-full">
        <ResultPanel state={previewState} appliedLabel="would change" />
        <ResultPanel state={applyState} appliedLabel="corrected" />
      </div>
    </div>
  );
}
