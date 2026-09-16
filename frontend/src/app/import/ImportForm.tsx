"use client";

import { useActionState } from "react";
import { importJson } from "./actions";

export default function ImportForm() {
  const [state, formAction, pending] = useActionState(importJson, undefined);

  return (
    <form action={formAction} className="flex flex-col gap-4">
      <input
        type="file"
        name="file"
        accept="application/json,.json"
        required
        className="text-sm file:mr-3 file:rounded file:border-0 file:bg-slate-900 file:px-3 file:py-1.5 file:text-sm file:font-medium file:text-white"
      />
      <button
        type="submit"
        disabled={pending}
        className="w-fit rounded bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-50"
      >
        {pending ? "Importing..." : "Import"}
      </button>

      {state && "error" in state && <p className="text-sm text-red-600">{state.error}</p>}

      {state && "created" in state && (
        <div className="rounded border border-slate-200 bg-slate-50 p-4 text-sm">
          <p className="font-medium text-emerald-700">Created {state.created} line item(s).</p>
          {state.errors.length > 0 && (
            <>
              <p className="mt-2 font-medium text-red-600">{state.errors.length} row(s) failed:</p>
              <ul className="mt-1 list-disc pl-5 text-slate-600">
                {state.errors.map((e) => (
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
