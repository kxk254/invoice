"use client";

import { useActionState, useEffect, useRef, useState } from "react";
import Spinner from "@/components/Spinner";
import { previewRestore, applyRestore } from "./actions";

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
  const [understood, setUnderstood] = useState(false);
  const [file, setFile] = useState<File | null>(null);
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
  const hasConflicts = hasPreview && previewState.conflicts.length > 0;
  const canApply = hasPreview && !hasConflicts && understood && file;

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
              <p className="font-medium text-slate-900">This backup matches your organization. Applying it would:</p>
              <ul className="mt-2 list-disc pl-5 text-slate-600">
                <li>
                  Organization profile: update in place ({previewState.diff.organization.update.length} field set)
                </li>
                <li>Bank accounts: create/update {previewState.diff.bank_account.length} (never deleted)</li>
                {(["item_code", "client", "account_item", "invoice_code"] as const).map((key) => {
                  const d = previewState.diff[key];
                  return (
                    <li key={key}>
                      {LABELS[key]}: create {d.create.length}, update {d.update.length}, delete {d.delete.length}
                    </li>
                  );
                })}
              </ul>

              <label className="mt-4 flex items-start gap-2 text-sm text-slate-700">
                <input
                  type="checkbox"
                  checked={understood}
                  onChange={(e) => setUnderstood(e.target.checked)}
                  className="mt-0.5 accent-red-600"
                />
                <span>
                  I understand the &quot;delete&quot; rows above will be permanently removed, and this cannot be
                  undone from here.
                </span>
              </label>

              <button
                type="submit"
                formAction={applyAction}
                disabled={!canApply || applyPending}
                className="btn-danger mt-3 w-fit py-2"
              >
                {applyPending && <Spinner />}
                {applyPending ? "Restoring..." : "Apply restore"}
              </button>
            </>
          )}
        </div>
      )}

      {applyState && "error" in applyState && <p className="text-sm text-red-600">{applyState.error}</p>}

      {applyState && "invoice_code" in applyState && (
        <div className="rounded-md border border-emerald-200 bg-emerald-50 p-4 text-sm">
          <p className="font-medium text-emerald-700">Restore complete.</p>
          <ul className="mt-2 list-disc pl-5 text-slate-700">
            <li>Line items: {applyState.account_item} restored, {applyState.deleted.account_item} removed</li>
            <li>Invoices: {applyState.invoice_code} restored, {applyState.deleted.invoice_code} removed</li>
            <li>Clients: {applyState.client} restored, {applyState.deleted.client} removed</li>
            <li>Item codes: {applyState.item_code} restored, {applyState.deleted.item_code} removed</li>
            <li>Bank accounts: {applyState.bank_account} restored</li>
          </ul>
        </div>
      )}
    </form>
  );
}
