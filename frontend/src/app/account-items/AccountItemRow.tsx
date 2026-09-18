import type { AccountItem, Client, ItemCode } from "@/lib/types";
import { deleteAccountItem } from "./actions";

const inputClass =
  "rounded-md border border-slate-300 px-2 py-1 text-sm outline-none transition-colors focus:border-brand focus:ring-2 focus:ring-brand-light disabled:cursor-not-allowed disabled:border-slate-200 disabled:bg-slate-100 disabled:text-slate-400";

const dateFmt = new Intl.DateTimeFormat("ja-JP", { dateStyle: "medium" });

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
  locked = false,
  voided = false,
}: {
  clients: Client[];
  itemCodes: ItemCode[];
  defaults?: Partial<AccountItem>;
  nameSuffix?: string;
  stickyBg?: string;
  // Invoice already sent: issue date is frozen (server rejects a change
  // regardless), so the input is disabled here to make that obvious upfront
  // rather than as a save-time error.
  locked?: boolean;
  // Logically deleted: kept as a read-only audit row, excluded from
  // totals/PDF/CSV. A disabled input is also omitted from form submission
  // entirely, so a voided row never ends up in the bulk-save payload.
  voided?: boolean;
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
        <select
          name={n("company")}
          defaultValue={defaults?.company ?? ""}
          required
          disabled={voided}
          className={`${inputClass} w-full`}
        >
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
        <select
          name={n("item_code")}
          defaultValue={defaults?.item_code ?? ""}
          disabled={voided}
          className={`${inputClass} w-full`}
        >
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
          disabled={voided || locked}
          title={locked && !voided ? "Invoice already sent — issue date can no longer be changed" : undefined}
          className={`${inputClass} w-full`}
        />
      </td>
      <td className="border-b border-slate-100 p-1">
        <input
          type="date"
          name={n("payment_due")}
          defaultValue={defaults?.payment_due ?? ""}
          disabled={voided}
          className={`${inputClass} w-full`}
        />
      </td>
      <td className="border-b border-slate-100 p-1">
        <input
          type="date"
          name={n("action_date")}
          defaultValue={defaults?.action_date ?? ""}
          disabled={voided}
          className={`${inputClass} w-full`}
        />
      </td>
      <td className="border-b border-slate-100 p-1">
        <input
          type="text"
          name={n("action_name")}
          defaultValue={defaults?.action_name ?? ""}
          disabled={voided}
          className={`${inputClass} w-full`}
        />
      </td>
      <td className="border-b border-slate-100 p-1">
        <input
          type="text"
          name={n("action_note")}
          defaultValue={defaults?.action_note ?? ""}
          disabled={voided}
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
          disabled={voided}
          className={`${inputClass} w-full text-right`}
        />
      </td>
      <td className="border-b border-slate-100 p-1">
        <input
          type="number"
          name={n("invoice_bt")}
          defaultValue={defaults?.invoice_bt ?? 0}
          disabled={voided}
          className={`${inputClass} w-full text-right`}
        />
      </td>
      <td className="border-b border-slate-100 p-1">
        <input
          type="number"
          name={n("invoice_tax")}
          defaultValue={defaults?.invoice_tax ?? 0}
          disabled={voided}
          className={`${inputClass} w-full text-right`}
        />
      </td>
      <td className="border-b border-slate-100 p-1">
        <input
          type="number"
          name={n("invoice_at")}
          defaultValue={defaults?.invoice_at ?? 0}
          disabled={voided}
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
  const voided = Boolean(item.deleted_at);

  return (
    <tr className={`align-middle ${voided ? "bg-slate-50 opacity-60" : ""}`}>
      <FieldInputs
        clients={clients}
        itemCodes={itemCodes}
        defaults={item}
        nameSuffix={String(item.id)}
        locked={item.invoice_issued}
        voided={voided}
        stickyBg={voided ? "bg-slate-50" : "bg-white"}
      />
      <td className="whitespace-nowrap border-b border-slate-100 p-1 text-right">
        {voided ? (
          <span className="badge-neutral" title={item.deleted_at ? dateFmt.format(new Date(item.deleted_at)) : undefined}>
            Voided
          </span>
        ) : (
          <button type="submit" formAction={deleteWithId} formNoValidate className="btn-danger-ghost">
            Delete
          </button>
        )}
      </td>
    </tr>
  );
}
