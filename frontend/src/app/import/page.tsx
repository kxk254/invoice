import { apiGet } from "@/lib/api";
import type { Me } from "@/lib/types";
import Nav from "@/components/Nav";
import ImportForm from "./ImportForm";

const EXAMPLE = `[
  {
    "company": "SCM",
    "item_code": "C01",
    "invoice_date": "2025-08-01",
    "payment_due": "2025-08-31",
    "action_date": "2025-07-01",
    "action_name": "業務委託費",
    "action_note": "note",
    "invoice_bt": 100000,
    "invoice_tax": 10000,
    "invoice_at": 110000
  }
]

// or wrapped: { "account_items": [ ...same objects... ] }`;

export default async function ImportPage() {
  const me = await apiGet<Me>("/me/");
  return (
    <>
      <Nav orgName={me.organization.name} username={me.username} />
      <div className="mx-auto w-full max-w-2xl px-4 py-8">
      <h1 className="mb-2 text-xl font-semibold text-slate-900">Import line items</h1>
      <p className="mb-6 text-sm text-slate-500">
        Adds rows to your organization only — never deletes or overwrites existing data.
        <code>company</code> and <code>item_code</code> can be either a numeric id or a short name/slug.
      </p>

      <div className="mb-6 rounded-lg border border-slate-200 bg-white p-6">
        <ImportForm />
      </div>

      <details className="rounded-lg border border-slate-200 bg-slate-50 p-4 text-sm">
        <summary className="cursor-pointer font-medium text-slate-700">Expected JSON format</summary>
        <pre className="mt-3 overflow-x-auto rounded bg-slate-900 p-3 text-xs text-slate-100">{EXAMPLE}</pre>
      </details>
      </div>
    </>
  );
}
