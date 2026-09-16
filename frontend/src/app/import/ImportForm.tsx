"use client";

import { useActionState } from "react";
import { importJson, diffImportJson } from "./actions";

export default function ImportForm() {
  const [importState, importAction, importPending] = useActionState(importJson, undefined);
  const [diffState, diffAction, diffPending] = useActionState(diffImportJson, undefined);

  return (
    <form className="flex flex-col gap-4">
      <input
        type="file"
        name="file"
        accept="application/json,.json"
        required
        className="text-sm file:mr-3 file:rounded file:border-0 file:bg-slate-900 file:px-3 file:py-1.5 file:text-sm file:font-medium file:text-white"
      />
      <div className="flex flex-wrap gap-3">
        <button
          type="submit"
          formAction={diffAction}
          disabled={importPending || diffPending}
          className="w-fit rounded border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50"
        >
          {diffPending ? "Comparing..." : "Compare only (no changes)"}
        </button>
        <button
          type="submit"
          formAction={importAction}
          disabled={importPending || diffPending}
          className="w-fit rounded bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-50"
        >
          {importPending ? "Importing..." : "Import"}
        </button>
      </div>

      {diffState && "error" in diffState && <p className="text-sm text-red-600">{diffState.error}</p>}

      {diffState && "total" in diffState && (
        <div className="rounded border border-slate-200 bg-slate-50 p-4 text-sm">
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
        <div className="rounded border border-slate-200 bg-slate-50 p-4 text-sm">
          <p className="font-medium text-emerald-700">Created {importState.created} line item(s).</p>
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
        </div>
      )}
    </form>
  );
}
