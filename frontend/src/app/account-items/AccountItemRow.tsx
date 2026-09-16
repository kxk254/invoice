import type { AccountItem, Client, ItemCode } from "@/lib/types";
import { deleteAccountItem } from "./actions";

const inputClass =
  "rounded border border-slate-300 px-2 py-1 text-sm focus:border-slate-500 focus:outline-none";

// All rows (existing + the "add row" draft) live inside one shared <form>
// now, so a single submit can bulk-save every edited row for the month.
// Existing rows suffix their input names with "__<id>" (see actions.ts);
// the draft row leaves `nameSuffix` unset and keeps plain names.
export function FieldInputs({
  clients,
  itemCodes,
  defaults,
  nameSuffix,
  stickyBg = "bg-white",
}: {
  clients: Client[];
  itemCodes: ItemCode[];
  defaults?: Partial<AccountItem>;
  nameSuffix?: string;
  stickyBg?: string;
}) {
  const n = (field: string) => (nameSuffix ? `${field}__${nameSuffix}` : field);
  return (
    <>
      {/* Client and item code stay pinned while scrolling horizontally, so
          it's always clear which row you're entering values for. Row
          dividers live on each <td> (not the <tr>) because table rows don't
          paint borders under border-separate, which sticky cells require —
          border-collapse breaks position:sticky on table cells entirely. */}
      <td className={`sticky left-0 z-10 border-b border-slate-100 p-1 ${stickyBg}`}>
        <select name={n("company")} defaultValue={defaults?.company ?? ""} required className={`${inputClass} w-full`}>
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
      <td className={`sticky left-40 z-10 border-b border-r border-b-slate-100 border-r-slate-200 p-1 ${stickyBg}`}>
        <select name={n("item_code")} defaultValue={defaults?.item_code ?? ""} className={`${inputClass} w-full`}>
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
      <td className="border-b border-slate-100 p-1">
        <input
          type="date"
          name={n("invoice_date")}
          defaultValue={defaults?.invoice_date ?? ""}
          className={`${inputClass} w-full`}
        />
      </td>
      <td className="border-b border-slate-100 p-1">
        <input
          type="date"
          name={n("payment_due")}
          defaultValue={defaults?.payment_due ?? ""}
          className={`${inputClass} w-full`}
        />
      </td>
      <td className="border-b border-slate-100 p-1">
        <input
          type="date"
          name={n("action_date")}
          defaultValue={defaults?.action_date ?? ""}
          className={`${inputClass} w-full`}
        />
      </td>
      <td className="border-b border-slate-100 p-1">
        <input
          type="text"
          name={n("action_name")}
          defaultValue={defaults?.action_name ?? ""}
          className={`${inputClass} w-full`}
        />
      </td>
      <td className="border-b border-slate-100 p-1">
        <input
          type="text"
          name={n("action_note")}
          defaultValue={defaults?.action_note ?? ""}
          className={`${inputClass} w-full`}
        />
      </td>
      <td className="border-b border-slate-100 p-1">
        <input
          type="number"
          name={n("tax_rate")}
          min={0}
          max={100}
          defaultValue={defaults?.tax_rate ?? 10}
          className={`${inputClass} w-full text-right`}
        />
      </td>
      <td className="border-b border-slate-100 p-1">
        <input
          type="number"
          name={n("invoice_bt")}
          defaultValue={defaults?.invoice_bt ?? 0}
          className={`${inputClass} w-full text-right`}
        />
      </td>
      <td className="border-b border-slate-100 p-1">
        <input
          type="number"
          name={n("invoice_tax")}
          defaultValue={defaults?.invoice_tax ?? 0}
          className={`${inputClass} w-full text-right`}
        />
      </td>
      <td className="border-b border-slate-100 p-1">
        <input
          type="number"
          name={n("invoice_at")}
          defaultValue={defaults?.invoice_at ?? 0}
          className={`${inputClass} w-full text-right`}
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
  const deleteWithId = deleteAccountItem.bind(null, item.id);

  return (
    <tr className="align-middle">
      <FieldInputs clients={clients} itemCodes={itemCodes} defaults={item} nameSuffix={String(item.id)} />
      <td className="whitespace-nowrap border-b border-slate-100 p-1 text-right">
        <button
          type="submit"
          formAction={deleteWithId}
          formNoValidate
          className="rounded border border-red-200 px-3 py-1 text-xs font-medium text-red-600 hover:bg-red-50"
        >
          Delete
        </button>
      </td>
    </tr>
  );
}
