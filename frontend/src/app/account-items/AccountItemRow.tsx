import type { AccountItem, Client, ItemCode } from "@/lib/types";
import { updateAccountItem, deleteAccountItem } from "./actions";

const inputClass =
  "w-full rounded border border-slate-300 px-2 py-1 text-sm focus:border-slate-500 focus:outline-none";

// Cells reference their row's <form> via the HTML `form` attribute rather
// than nesting inside it, since <form> can't wrap a <tr>/<td> directly
// without breaking table layout.
export function FieldInputs({
  formId,
  clients,
  itemCodes,
  defaults,
}: {
  formId: string;
  clients: Client[];
  itemCodes: ItemCode[];
  defaults?: Partial<AccountItem>;
}) {
  return (
    <>
      <td className="p-1">
        <select form={formId} name="company" defaultValue={defaults?.company ?? ""} required className={inputClass}>
          <option value="" disabled>
            —
          </option>
          {clients.map((c) => (
            <option key={c.id} value={c.id}>
              {c.short_name}
            </option>
          ))}
        </select>
      </td>
      <td className="p-1">
        <select form={formId} name="item_code" defaultValue={defaults?.item_code ?? ""} className={inputClass}>
          <option value="" disabled>
            —
          </option>
          {itemCodes.map((ic) => (
            <option key={ic.id} value={ic.id}>
              {ic.short_name}
            </option>
          ))}
        </select>
      </td>
      <td className="p-1">
        <input
          form={formId}
          type="date"
          name="invoice_date"
          defaultValue={defaults?.invoice_date ?? ""}
          className={inputClass}
        />
      </td>
      <td className="p-1">
        <input
          form={formId}
          type="date"
          name="payment_due"
          defaultValue={defaults?.payment_due ?? ""}
          className={inputClass}
        />
      </td>
      <td className="p-1">
        <input
          form={formId}
          type="date"
          name="action_date"
          defaultValue={defaults?.action_date ?? ""}
          className={inputClass}
        />
      </td>
      <td className="p-1">
        <input
          form={formId}
          type="text"
          name="action_name"
          defaultValue={defaults?.action_name ?? ""}
          className={inputClass}
        />
      </td>
      <td className="p-1">
        <input
          form={formId}
          type="text"
          name="action_note"
          defaultValue={defaults?.action_note ?? ""}
          className={inputClass}
        />
      </td>
      <td className="p-1">
        <input
          form={formId}
          type="number"
          name="invoice_bt"
          defaultValue={defaults?.invoice_bt ?? 0}
          className={`${inputClass} text-right`}
        />
      </td>
      <td className="p-1">
        <input
          form={formId}
          type="number"
          name="invoice_tax"
          defaultValue={defaults?.invoice_tax ?? 0}
          className={`${inputClass} text-right`}
        />
      </td>
      <td className="p-1">
        <input
          form={formId}
          type="number"
          name="invoice_at"
          defaultValue={defaults?.invoice_at ?? 0}
          className={`${inputClass} text-right`}
        />
      </td>
    </>
  );
}

export default function AccountItemRow({
  item,
  clients,
  itemCodes,
}: {
  item: AccountItem;
  clients: Client[];
  itemCodes: ItemCode[];
}) {
  const formId = `account-item-${item.id}`;
  const updateWithId = updateAccountItem.bind(null, item.id);
  const deleteWithId = deleteAccountItem.bind(null, item.id);

  return (
    <tr className="border-b border-slate-100 align-middle">
      <FieldInputs formId={formId} clients={clients} itemCodes={itemCodes} defaults={item} />
      <td className="whitespace-nowrap p-1 text-right">
        <form id={formId} action={updateWithId} className="hidden" />
        <button
          type="submit"
          form={formId}
          className="rounded bg-slate-900 px-3 py-1 text-xs font-medium text-white hover:bg-slate-800"
        >
          Save
        </button>
        <form action={deleteWithId} className="inline">
          <button
            type="submit"
            className="ml-2 rounded border border-red-200 px-3 py-1 text-xs font-medium text-red-600 hover:bg-red-50"
          >
            Delete
          </button>
        </form>
      </td>
    </tr>
  );
}
