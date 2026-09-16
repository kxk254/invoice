import { apiGet } from "@/lib/api";
import type { Client, InvoiceCode, Me } from "@/lib/types";
import Nav from "@/components/Nav";
import FilterForm from "./FilterForm";
import { runTaxCalc, markInvoiceSent, unmarkInvoiceSent } from "./actions";

// This page's list depends entirely on the `month`/`company` query string;
// without this, some browsers/proxies can serve a cached response for the
// route and appear to ignore the filter even though the URL changed.
export const dynamic = "force-dynamic";

function monthStart(month: string) {
  return `${month}-01`;
}

const yen = new Intl.NumberFormat("ja-JP");
const dateFmt = new Intl.DateTimeFormat("ja-JP", { dateStyle: "medium" });

export default async function InvoicesPage(props: PageProps<"/invoices">) {
  const params = await props.searchParams;
  const company = typeof params.company === "string" ? params.company : "";
  const month = typeof params.month === "string" && params.month ? params.month : "";

  const query = new URLSearchParams();
  if (month) query.set("month", monthStart(month));
  if (company) query.set("company", company);

  const [me, clients, invoices] = await Promise.all([
    apiGet<Me>("/me/"),
    apiGet<Client[]>("/clients/"),
    apiGet<InvoiceCode[]>(`/invoices/?${query.toString()}`),
  ]);

  return (
    <>
      <Nav orgName={me.organization.name} username={me.username} />
      <div className="mx-auto w-full max-w-6xl px-4 py-8">
      <h1 className="mb-6 text-xl font-semibold text-slate-900">Invoices</h1>

      <div className="mb-6 flex flex-wrap items-end justify-between gap-4 rounded-lg border border-slate-200 bg-white p-4">
        <FilterForm clients={clients} company={company} month={month} />

        <form action={runTaxCalc} className="flex items-end gap-2">
          <input type="hidden" name="company" value={company} />
          <input type="hidden" name="month" value={month ? monthStart(month) : ""} />
          <button
            type="submit"
            disabled={!month}
            className="rounded border border-slate-300 px-4 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-40"
            title={month ? undefined : "Pick a month first"}
          >
            Recalculate tax
          </button>
        </form>
      </div>

      <form action="/export-csv" method="get" className="mb-6 flex flex-wrap items-end gap-4 rounded-lg border border-slate-200 bg-white p-4">
        <div>
          <label className="block text-xs font-medium text-slate-500">Export CSV: from</label>
          <input type="date" name="start" required defaultValue={month ? monthStart(month) : ""} className="mt-1 rounded border border-slate-300 px-2 py-1 text-sm" />
        </div>
        <div>
          <label className="block text-xs font-medium text-slate-500">to</label>
          <input type="date" name="end" required className="mt-1 rounded border border-slate-300 px-2 py-1 text-sm" />
        </div>
        <button type="submit" className="rounded border border-slate-300 px-4 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50">
          Export CSV
        </button>
      </form>

      {month && (
        <div className="mb-6 overflow-x-auto rounded-lg border border-slate-200 bg-white">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-200 bg-slate-50 text-left text-xs font-medium text-slate-500">
                <th className="p-2">Client</th>
                <th className="p-2">Invoice no.</th>
                <th className="p-2">Payment due</th>
                <th className="p-2 text-right">Total (incl. tax)</th>
                <th className="p-2">Status</th>
                <th className="p-2" />
              </tr>
            </thead>
            <tbody>
              {invoices.map((invoice) => {
                const markSentWithId = markInvoiceSent.bind(null, invoice.id);
                const unmarkSentWithId = unmarkInvoiceSent.bind(null, invoice.id);
                return (
                  <tr key={invoice.id} className="border-b border-slate-100 last:border-0">
                    <td className="p-2 text-slate-900">{invoice.client_name}</td>
                    <td className="p-2 text-slate-500">{invoice.invoice_slug ?? invoice.account_item_slug}</td>
                    <td className="p-2 text-slate-500">{invoice.payment_due ?? "—"}</td>
                    <td className="p-2 text-right font-medium text-slate-900">¥{yen.format(invoice.invoice_at_gttl)}</td>
                    <td className="p-2">
                      {invoice.sent_at ? (
                        <span className="text-emerald-700">送信済み（{dateFmt.format(new Date(invoice.sent_at))}）</span>
                      ) : (
                        <span className="text-slate-400">未送信</span>
                      )}
                    </td>
                    <td className="whitespace-nowrap p-2 text-right">
                      <form action={invoice.sent_at ? unmarkSentWithId : markSentWithId} className="inline">
                        <button
                          type="submit"
                          className="rounded border border-slate-300 px-3 py-1 text-xs font-medium text-slate-700 hover:bg-slate-50"
                        >
                          {invoice.sent_at ? "未送信に戻す" : "送信済みにする"}
                        </button>
                      </form>
                    </td>
                  </tr>
                );
              })}
              {invoices.length === 0 && (
                <tr>
                  <td colSpan={6} className="p-4 text-center text-sm text-slate-400">
                    No invoices for this filter.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      <div className="space-y-4">
        {invoices.map((invoice) => (
          <div key={invoice.id} className="rounded-lg border border-slate-200 bg-white">
            <div className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-100 p-4">
              <div>
                <p className="font-medium text-slate-900">{invoice.client_name}</p>
                <p className="text-xs text-slate-500">{invoice.invoice_slug ?? invoice.account_item_slug}</p>
              </div>
              <div className="flex items-center gap-6 text-sm">
                <div className="text-right">
                  <p className="text-xs text-slate-500">Total (incl. tax)</p>
                  <p className="font-medium text-slate-900">¥{yen.format(invoice.invoice_at_gttl)}</p>
                </div>
                <div className="flex gap-2">
                  <a
                    href={`/invoices/${invoice.account_item_slug}/pdf`}
                    target="_blank"
                    rel="noreferrer"
                    className="rounded border border-slate-300 px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50"
                  >
                    Preview PDF
                  </a>
                  <a
                    href={`/invoices/${invoice.account_item_slug}/pdf?download=1`}
                    className="rounded bg-slate-900 px-3 py-1.5 text-xs font-medium text-white hover:bg-slate-800"
                  >
                    Download
                  </a>
                </div>
              </div>
            </div>
            <table className="w-full text-sm">
              <tbody>
                {invoice.items.map((item) => (
                  <tr key={item.id} className="border-b border-slate-50 last:border-0">
                    <td className="p-2 text-slate-600">{item.action_name}</td>
                    <td className="p-2 text-slate-400">{item.action_note}</td>
                    <td className="p-2 text-right text-slate-900">¥{yen.format(item.invoice_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ))}
        {invoices.length === 0 && (
          <div className="rounded-lg border border-slate-200 bg-white p-8 text-center text-sm text-slate-400">
            No invoices for this filter.
          </div>
        )}
      </div>
      </div>
    </>
  );
}
