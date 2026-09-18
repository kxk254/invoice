"use client";

import { useActionState, useEffect, useRef, useState } from "react";
import Spinner from "@/components/Spinner";
import { importJson, diffImportJson } from "./actions";

export default function ImportForm() {
  const [importState, importAction, importPending] = useActionState(importJson, undefined);
  const [diffState, diffAction, diffPending] = useActionState(diffImportJson, undefined);
  const [replace, setReplace] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Buttons stay on the officially-supported formAction path (so
  // importPending/diffPending track correctly — calling the useActionState
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
  }, [file, diffState, importState]);

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

      <label className="flex items-start gap-2 text-sm text-slate-700">
        <input
          type="checkbox"
          name="mode"
          value="replace"
          checked={replace}
          onChange={(e) => setReplace(e.target.checked)}
          className="mt-0.5 accent-brand"
        />
        <span>
          Replace existing periods
          <span className="block text-xs text-slate-500">
            For each client + invoice month in this file, delete that period&apos;s current line items and load these
            instead. The invoice number already issued for that period is kept. Unrelated periods are untouched. Off
            = only add new rows (may duplicate if re-run).
          </span>
        </span>
      </label>

      <div className="flex flex-wrap gap-3">
        <button
          type="submit"
          formAction={diffAction}
          disabled={!file || importPending || diffPending}
          className="btn-secondary w-fit py-2"
        >
          {diffPending && <Spinner />}
          {diffPending ? "Comparing..." : "Compare only (no changes)"}
        </button>
        <button
          type="submit"
          formAction={importAction}
          disabled={!file || importPending || diffPending}
          className="btn-primary w-fit py-2"
        >
          {importPending && <Spinner />}
          {importPending ? "Importing..." : "Import"}
        </button>
      </div>

      {diffState && "error" in diffState && <p className="text-sm text-red-600">{diffState.error}</p>}

      {diffState && "total" in diffState && (
        <div className="rounded-md border border-slate-200 bg-slate-50 p-4 text-sm">
          <p className="font-medium text-slate-900">
            {diffState.total} row(s) checked — {diffState.matched} match the database exactly.
          </p>
          {diffState.missing.length > 0 && (
            <>
              <p className="mt-3 font-medium text-amber-700">{diffState.missing.length} row(s) not found in the database:</p>
              <ul className="mt-1 list-disc pl-5 text-slate-600">
                {diffState.missing.map((m) => (
                  <li key={m.index}>
                    Row {m.index}: slug &quot;{m.slug}&quot;
                  </li>
                ))}
              </ul>
            </>
          )}
          {diffState.differing.length > 0 && (
            <>
              <p className="mt-3 font-medium text-red-600">{diffState.differing.length} row(s) differ from the database:</p>
              <ul className="mt-1 list-disc pl-5 text-slate-600">
                {diffState.differing.map((d) => (
                  <li key={d.index}>
                    Row {d.index} (slug &quot;{d.slug}&quot;):
                    <ul className="list-[circle] pl-5">
                      {Object.entries(d.diffs).map(([field, v]) => (
                        <li key={field}>
                          {field}: file={JSON.stringify(v.file)}, db={JSON.stringify(v.db)}
                        </li>
                      ))}
                    </ul>
                  </li>
                ))}
              </ul>
            </>
          )}
          {diffState.errors.length > 0 && (
            <>
              <p className="mt-3 font-medium text-red-600">{diffState.errors.length} row(s) couldn&apos;t be checked:</p>
              <ul className="mt-1 list-disc pl-5 text-slate-600">
                {diffState.errors.map((e) => (
                  <li key={e.index}>
                    Row {e.index}: {JSON.stringify(e.detail)}
                  </li>
                ))}
              </ul>
            </>
          )}
        </div>
      )}

      {importState && "error" in importState && <p className="text-sm text-red-600">{importState.error}</p>}

      {importState && "created" in importState && (
        <div className="rounded-md border border-slate-200 bg-slate-50 p-4 text-sm">
          <p className="font-medium text-emerald-700">Created {importState.created} line item(s).</p>
          {importState.replaced_periods.length > 0 && (
            <ul className="mt-2 list-disc pl-5 text-slate-600">
              {importState.replaced_periods.map((p, i) => (
                <li key={i}>
                  Client {p.company}, {p.month}: removed {p.removed}, added {p.added}
                  {p.invoice_slug ? ` (invoice ${p.invoice_slug} unchanged)` : ""}
                </li>
              ))}
            </ul>
          )}
          {importState.errors.length > 0 && (
            <>
              <p className="mt-2 font-medium text-red-600">{importState.errors.length} row(s) failed:</p>
              <ul className="mt-1 list-disc pl-5 text-slate-600">
                {importState.errors.map((e) => (
                  <li key={e.index}>
                    Row {e.index}: {JSON.stringify(e.detail)}
                  </li>
                ))}
              </ul>
            </>
          )}
          {importState.skipped_duplicates.length > 0 && (
            <>
              <p className="mt-2 font-medium text-amber-700">
                {importState.skipped_duplicates.length} row(s) skipped — already matched an existing line item:
              </p>
              <ul className="mt-1 list-disc pl-5 text-slate-600">
                {importState.skipped_duplicates.map((d) => (
                  <li key={d.index}>Row {d.index}</li>
                ))}
              </ul>
            </>
          )}
        </div>
      )}
    </form>
  );
}
