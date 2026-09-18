import { apiGet } from "@/lib/api";
import type { AccountItem, Client, ItemCode, Me } from "@/lib/types";
import Nav from "@/components/Nav";
import AccountItemRow, { FieldInputs } from "./AccountItemRow";
import FilterForm from "./FilterForm";
import { createAccountItem, bulkUpdateAccountItems } from "./actions";

// This page's list depends entirely on the `month`/`company` query string;
// without this, some browsers/proxies can serve a cached response for the
// route and appear to ignore the filter even though the URL changed.
export const dynamic = "force-dynamic";

function monthStart(month: string) {
  return `${month}-01`;
}

// 請求日 (invoice_date) defaults to the 1st of the month *after* the
// 該当月 (action_date) being worked on, matching the model's own defaults
// (AccountItem.get_first_of_last_month / get_start_of_this_month). Pre-filling
// it here is just a starting point — the input stays editable so a user can
// pick a different issue date when needed.
function nextMonthStart(month: string) {
  const [year, mon] = month.split("-").map(Number);
  // `mon` is 1-indexed (e.g. 6 for June); passing it as JS Date's 0-indexed
  // month argument lands on July, i.e. the month after the one selected.
  return new Date(year, mon, 1).toISOString().slice(0, 10);
}

function thisMonthStart() {
  const today = new Date();
  return `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, "0")}-01`;
}

export default async function AccountItemsPage(props: PageProps<"/account-items">) {
  const params = await props.searchParams;
  const company = typeof params.company === "string" ? params.company : "";
  // No default month: filtering by "today" would show nothing until this
  // month's line items are entered. Show everything until the user filters.
  const month = typeof params.month === "string" ? params.month : "";

  const query = new URLSearchParams();
  if (month) query.set("month", monthStart(month));
  if (company) query.set("company", company);

  const [me, clients, itemCodes, items] = await Promise.all([
    apiGet<Me>("/me/"),
    apiGet<Client[]>("/clients/"),
    apiGet<ItemCode[]>("/item-codes/"),
    apiGet<AccountItem[]>(`/account-items/?${query.toString()}`),
  ]);

  return (
    <>
      <Nav orgName={me.organization.name} username={me.username} />
      <div className="mx-auto w-full max-w-6xl px-4 py-8">
      <h1 className="mb-6 text-xl font-semibold text-slate-900">Line items</h1>

      <FilterForm clients={clients} company={company} month={month} />

      {!month && (
        <p className="mb-4 text-sm text-slate-500">
          Pick a month above to edit that month&apos;s line items, then save them all at once.
        </p>
      )}

      <p className="mb-4 text-xs text-slate-500">
        Once an invoice has been sent, its rows can still be corrected — added to, edited, or removed — but its issue
        date is locked (grayed out) and removing a row only voids it: it stays visible here in gray for the record,
        while disappearing from totals, the PDF, and CSV exports. The invoice itself is then marked（修正版）.
      </p>

      {/* One shared form: existing rows name inputs "field__<id>" and save
          together via the button below; the "add row" draft keeps plain
          names and its own submit button, so the two never mix. */}
      <form action={bulkUpdateAccountItems}>
        <div className="overflow-x-auto card">
          {/* border-separate (not border-collapse) because sticky cells
              don't stick at all inside a border-collapsed table — row
              dividers are applied per-cell below instead of on <tr>, since
              <tr> borders don't paint under border-separate.
              table-fixed + colgroup because table-layout:auto redistributes
              leftover space across columns regardless of any width set on
              individual cells — the colgroup below is the one place that
              actually controls each column's width, including the sticky
              ones (whose "left" offsets must match it exactly).
              The table also needs an explicit width (not just table-fixed)
              equal to the sum of the colgroup widths below: a table-fixed
              table left at width:auto still stretches or shrinks to fill
              its container, proportionally resizing every column (and
              clipping numbers) as the viewport narrows. An explicit width
              locks every column at its declared size and lets the
              overflow-x-auto wrapper scroll instead. */}
          <table className="w-[1664px] table-fixed border-separate border-spacing-0 text-sm">
            <colgroup>
              <col className="w-40" />
              <col className="w-36" />
              <col className="w-32" />
              <col className="w-32" />
              <col className="w-32" />
              <col className="w-56" />
              <col className="w-64" />
              <col className="w-20" />
              <col className="w-28" />
              <col className="w-28" />
              <col className="w-28" />
              <col className="w-20" />
            </colgroup>
            <thead>
              <tr className="bg-slate-50 text-left text-xs font-medium text-slate-500">
                <th className="sticky left-0 z-20 border-b-2 border-slate-200 bg-slate-50 p-2">Client</th>
                <th className="sticky left-40 z-20 border-b-2 border-r border-slate-200 bg-slate-50 p-2">
                  Item code
                </th>
                <th className="border-b-2 border-slate-200 p-2">Invoice date</th>
                <th className="border-b-2 border-slate-200 p-2">Payment due</th>
                <th className="border-b-2 border-slate-200 p-2">Action date</th>
                <th className="border-b-2 border-slate-200 p-2">Action</th>
                <th className="border-b-2 border-slate-200 p-2">Note</th>
                <th className="border-b-2 border-slate-200 p-2 text-right">Tax rate</th>
                <th className="border-b-2 border-slate-200 p-2 text-right">Before tax</th>
                <th className="border-b-2 border-slate-200 p-2 text-right">Tax</th>
                <th className="border-b-2 border-slate-200 p-2 text-right">Total</th>
                <th className="border-b-2 border-slate-200 p-2" />
              </tr>
            </thead>
            <tbody>
              {items.map((item) => (
                <AccountItemRow key={item.id} item={item} clients={clients} itemCodes={itemCodes} />
              ))}
              {items.length === 0 && (
                <tr>
                  <td colSpan={12} className="border-b border-slate-100 p-4 text-center text-sm text-slate-400">
                    No line items for this filter.
                  </td>
                </tr>
              )}
              <tr className="bg-slate-50">
                <FieldInputs
                  clients={clients}
                  itemCodes={itemCodes}
                  defaults={
                    month
                      ? { action_date: monthStart(month), invoice_date: nextMonthStart(month) }
                      : { invoice_date: thisMonthStart() }
                  }
                  stickyBg="bg-slate-50"
                />
                <td className="p-1" />
              </tr>
            </tbody>
          </table>
        </div>

        <div className="mt-4 flex justify-end gap-3">
          <button
            type="submit"
            formAction={createAccountItem}
            className="inline-flex items-center justify-center gap-1.5 rounded-md bg-emerald-600 px-4 py-2 text-sm font-medium text-white shadow-sm transition-colors hover:bg-emerald-500"
          >
            Add row
          </button>
          <button type="submit" formNoValidate className="btn-primary py-2">
            Save all changes
          </button>
        </div>
      </form>
      </div>
    </>
  );
}
