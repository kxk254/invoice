"use client";

import { useRef } from "react";
import type { Client } from "@/lib/types";

export default function FilterForm({ clients, company, month }: { clients: Client[]; company: string; month: string }) {
  const formRef = useRef<HTMLFormElement>(null);
  const cacheBustRef = useRef<HTMLInputElement>(null);

  // A browser or intermediary proxy can sometimes cache a GET response by
  // URL and reuse it for what looks like a "new" navigation. Stamping a
  // fresh value in here on every submit guarantees the URL is unique each
  // time, which defeats that regardless of where the caching happens.
  function submitFresh() {
    if (cacheBustRef.current) cacheBustRef.current.value = String(Date.now());
    formRef.current?.requestSubmit();
  }

  return (
    <form ref={formRef} method="get" className="flex flex-wrap items-end gap-4">
      <input ref={cacheBustRef} type="hidden" name="_ts" />
      <div>
        <label className="block text-xs font-medium text-slate-500">Client</label>
        <select
          name="company"
          defaultValue={company}
          onChange={submitFresh}
          className="mt-1 rounded border border-slate-300 px-2 py-1 text-sm"
        >
          <option value="">All clients</option>
          {clients.map((c) => (
            <option key={c.id} value={c.id}>
              {c.short_name}
            </option>
          ))}
        </select>
      </div>
      <div>
        <label className="block text-xs font-medium text-slate-500">Month</label>
        <input
          type="month"
          name="month"
          defaultValue={month}
          onChange={submitFresh}
          className="mt-1 rounded border border-slate-300 px-2 py-1 text-sm"
        />
      </div>
      <button
        type="submit"
        onClick={() => cacheBustRef.current && (cacheBustRef.current.value = String(Date.now()))}
        className="rounded bg-slate-900 px-4 py-1.5 text-sm font-medium text-white hover:bg-slate-800"
      >
        Filter
      </button>
    </form>
  );
}
