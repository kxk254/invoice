"use client";

import { useActionState, useEffect, useRef, useState } from "react";
import Spinner from "@/components/Spinner";
import { previewRestore, applyRestore, type RestorePeriod } from "./actions";

const LABELS: Record<string, string> = {
  bank_account: "Bank accounts",
  item_code: "Item codes",
  client: "Clients",
  account_item: "Line items",
  invoice_code: "Invoices",
};

export default function RestoreForm() {
  const [previewState, previewAction, previewPending] = useActionState(previewRestore, undefined);
  const [applyState, applyAction, applyPending] = useActionState(applyRestore, undefined);
  const [file, setFile] = useState<File | null>(null);
  // Per-period choice for periods that are already partly in the database.
  // Tied to the preview it was made on, so a new preview starts from a clean slate.
  const [picked, setPicked] = useState<{ source: unknown; map: Record<string, "add" | "skip"> }>({ source: null, map: {} });
  const decisions = picked.source === previewState ? picked.map : {};
  const setDecisions = (next: Record<string, "add" | "skip">) => setPicked({ source: previewState, map: next });
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Buttons stay on the officially-supported formAction path (so
  // previewPending/applyPending track correctly — calling the useActionState
  // dispatcher manually, even inside startTransition, doesn't reliably keep
  // it inside a transition across the action's own await). The side effect
  // of a real formAction submission is that once it resolves, React resets
  // every uncontrolled field in the <form>, which clears this <input
  // type="file"> (and its 選択 label). So instead we keep the picked File in
  // state and, right after each action settles, hand it back to the input
  // via a DataTransfer — the input's own value is the only thing formData
  // reads from at the next submission, and this is the only supported way
  // to set it programmatically.
  useEffect(() => {
    if (file && fileInputRef.current && fileInputRef.current.files?.length === 0) {
      const dt = new DataTransfer();
      dt.items.add(file);
      fileInputRef.current.files = dt.files;
    }
  }, [file, previewState, applyState]);

  const hasPreview = previewState && "diff" in previewState;
  const choosable = hasPreview ? previewState.periods.filter((p) => !p.sent) : [];
  const setAllDecisions = (choice: "add" | "skip") => setDecisions(Object.fromEntries(choosable.map((p) => [p.period, choice])));
  const hasConflicts = hasPreview && previewState.conflicts.length > 0;
  const canApply = hasPreview && !hasConflicts && file;

  return (
    <form className="flex flex-col gap-4">
      <input
        type="file"
        name="file"
        accept="application/json,.json"
        required
        ref={fileInputRef}
        onChange={(e) => setFile(e.target.files?.[0] ?? null)}
        className="text-sm file:mr-3 file:rounded-md file:border-0 file:bg-brand file:px-3 file:py-1.5 file:text-sm file:font-medium file:text-white file:transition-colors hover:file:bg-brand-dark"
      />

      <div className="flex flex-wrap gap-3">
        <button
          type="submit"
          formAction={previewAction}
          disabled={!file || previewPending || applyPending}
          className="btn-secondary w-fit py-2"
        >
          {previewPending && <Spinner />}
          {previewPending ? "Checking..." : "Preview restore"}
        </button>
      </div>

      {previewState && "error" in previewState && <p className="text-sm text-red-600">{previewState.error}</p>}

      {hasPreview && (
        <div className="rounded-md border border-slate-200 bg-slate-50 p-4 text-sm">
          {hasConflicts ? (
            <>
              <p className="font-medium text-red-600">
                {previewState.conflicts.length} row(s) in this backup share an id with another organization&apos;s
                data. Restore is blocked until the backup is fixed — nothing has been changed.
              </p>
              <pre className="mt-2 overflow-x-auto rounded bg-slate-900 p-3 text-xs text-slate-100">
                {JSON.stringify(previewState.conflicts, null, 2)}
              </pre>
            </>
          ) : (
            <>
              <p className="font-medium text-slate-900">
                This backup matches your organization. Applying it only adds what is missing — nothing that is already
                in the database is changed or removed:
              </p>
              <ul className="mt-2 list-disc pl-5 text-slate-600">
                {(["bank_account", "item_code", "client", "account_item", "invoice_code"] as const).map((key) => {
                  const d = previewState.diff[key];
                  return (
                    <li key={key}>
                      {LABELS[key]}: add {d.create.length}, already present {d.kept.length}
                      {d.skipped_sent > 0 && ` — ${d.skipped_sent} skipped: their invoice was already sent`}
                      {d.remapped > 0 && ` (${d.remapped} will get a new id because its old id is used by another record)`}
                    </li>
                  );
                })}
              </ul>

              {previewState.periods.length > 0 && (
                <div className="mt-4 border-t border-slate-200 pt-3">
                  <p className="font-medium text-slate-900">
                    {previewState.periods.length} period(s) are already in the database, at least in part
                  </p>
                  <p className="mt-1 text-slate-600">
                    Choose per period whether to add the lines the database is missing. Periods left on &ldquo;Leave
                    as is&rdquo; are not changed. Periods whose invoice was already sent are never changed.
                  </p>
                  {choosable.length > 0 && (
                    <div className="mt-2 flex gap-2">
                      <button type="button" className="btn-secondary" onClick={() => setAllDecisions("skip")}>Leave all as is</button>
                      <button type="button" className="btn-secondary" onClick={() => setAllDecisions("add")}>Add missing lines to all</button>
                    </div>
                  )}
                  <ul className="mt-3 divide-y divide-slate-200">
                    {previewState.periods.map((p: RestorePeriod) => {
                      const total = p.lines.reduce((sum, l) => sum + l.invoice_bt, 0);
                      const choice = decisions[p.period] ?? "skip";
                      return (
                        <li key={p.period} className="py-2">
                          <p className="font-medium text-slate-900">
                            {p.company_name ?? p.period} · {p.period}
                            {p.sent && <span className="ml-2 badge-neutral text-amber-700">sent — not changed</span>}
                          </p>
                          <p className="text-slate-600">
                            In the database: {p.live_lines} line(s). Missing from it: {p.lines.length} line(s), ¥
                            {total.toLocaleString("ja-JP")}
                          </p>
                          <details className="text-slate-500">
                            <summary className="cursor-pointer">Show missing lines</summary>
                            <ul className="mt-1 list-disc pl-5">
                              {p.lines.map((l, i) => (
                                <li key={i}>
                                  {l.invoice_date} {l.action_name} — ¥{l.invoice_bt.toLocaleString("ja-JP")}
                                </li>
                              ))}
                            </ul>
                          </details>
                          {!p.sent && (
                            <div className="mt-1 flex gap-4">
                              {(["skip", "add"] as const).map((value) => (
                                <label key={value} className="flex items-center gap-1.5">
                                  <input
                                    type="radio"
                                    name={`period-${p.period}`}
                                    checked={choice === value}
                                    onChange={() => setDecisions({ ...decisions, [p.period]: value })}
                                  />
                                  {value === "skip" ? "Leave as is" : "Add the missing lines"}
                                </label>
                              ))}
                            </div>
                          )}
                        </li>
                      );
                    })}
                  </ul>
                </div>
              )}
              <input type="hidden" name="decisions" value={JSON.stringify(decisions)} />

              <button
                type="submit"
                formAction={applyAction}
                disabled={!canApply || applyPending}
                className="btn-primary mt-3 w-fit py-2"
              >
                {applyPending && <Spinner />}
                {applyPending ? "Adding..." : "Add missing data"}
              </button>
            </>
          )}
        </div>
      )}

      {applyState && "error" in applyState && <p className="text-sm text-red-600">{applyState.error}</p>}

      {applyState && "added" in applyState && (
        <div className="rounded-md border border-emerald-200 bg-emerald-50 p-4 text-sm">
          <p className="font-medium text-emerald-700">Done. Existing data was left untouched.</p>
          {applyState.backup_file && (
            <p className="mt-1 text-slate-600">
              A copy of the database from just before this import was saved as <code>{applyState.backup_file}</code>.
            </p>
          )}
          {applyState.skipped_sent.account_item > 0 && (
            <p className="mt-1 text-amber-700">
              {applyState.skipped_sent.account_item} line item(s) were not added because their invoice was already sent.
            </p>
          )}
          {applyState.renumbered.invoice_code > 0 && (
            <p className="mt-1 text-amber-700">
              {applyState.renumbered.invoice_code} invoice(s) got a new id, so their invoice number changed.
            </p>
          )}
          <ul className="mt-2 list-disc pl-5 text-slate-700">
            {(["account_item", "invoice_code", "client", "item_code", "bank_account"] as const).map((key) => (
              <li key={key}>
                {LABELS[key]}: {applyState.added[key]} added, {applyState.kept[key]} already present
              </li>
            ))}
          </ul>
        </div>
      )}
    </form>
  );
}
