import { apiGet } from "@/lib/api";
import type { AccountItem, Client, ItemCode, Me } from "@/lib/types";
import Nav from "@/components/Nav";
import AccountItemRow, { FieldInputs } from "./AccountItemRow";
import FilterForm from "./FilterForm";
import { createAccountItem } from "./actions";

function monthStart(month: string) {
  return `${month}-01`;
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

      <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white">
        <table className="w-full min-w-[900px] border-collapse text-sm">
          <thead>
            <tr className="border-b border-slate-200 bg-slate-50 text-left text-xs font-medium text-slate-500">
              <th className="p-2">Client</th>
              <th className="p-2">Item code</th>
              <th className="p-2">Invoice date</th>
              <th className="p-2">Payment due</th>
              <th className="p-2">Action date</th>
              <th className="p-2">Action</th>
              <th className="p-2">Note</th>
              <th className="p-2 text-right">Before tax</th>
              <th className="p-2 text-right">Tax</th>
              <th className="p-2 text-right">Total</th>
              <th className="p-2" />
            </tr>
          </thead>
          <tbody>
            {items.map((item) => (
              <AccountItemRow key={item.id} item={item} clients={clients} itemCodes={itemCodes} />
            ))}
            {items.length === 0 && (
              <tr>
                <td colSpan={11} className="p-4 text-center text-sm text-slate-400">
                  No line items for this filter.
                </td>
              </tr>
            )}
            <tr className="border-t-2 border-slate-200 bg-slate-50">
              <FieldInputs formId="new-account-item" clients={clients} itemCodes={itemCodes} />
              <td className="whitespace-nowrap p-1 text-right">
                <form id="new-account-item" action={createAccountItem} className="hidden" />
                <button
                  type="submit"
                  form="new-account-item"
                  className="rounded bg-emerald-600 px-3 py-1 text-xs font-medium text-white hover:bg-emerald-500"
                >
                  Add row
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      </div>
    </>
  );
}
