"use client";

import { useRef } from "react";
import type { Client } from "@/lib/types";

export default function FilterForm({
  clients,
  company,
  month,
  number,
}: {
  clients: Client[];
  company: string;
  month: string;
  number: string;
}) {
  const formRef = useRef<HTMLFormElement>(null);
  const cacheBustRef = useRef<HTMLInputElement>(null);

  // A browser or intermediary proxy can sometimes cache a GET response by
  // URL and reuse it for what looks like a "new" navigation. Stamping a
  // fresh value in here on every submit guarantees the URL is unique each
  // time, which defeats that regardless of where the caching happens.
  function stampCacheBust() {
    if (cacheBustRef.current) cacheBustRef.current.value = String(Date.now());
  }

  function submitFresh() {
    stampCacheBust();
    formRef.current?.requestSubmit();
  }

  return (
    <form ref={formRef} method="get" className="flex flex-wrap items-end gap-4" onSubmit={stampCacheBust}>
      <input ref={cacheBustRef} type="hidden" name="_ts" />
      <div>
        <label className="field-label">Client</label>
        <select
          name="company"
          defaultValue={company}
          onChange={submitFresh}
          className="field-input"
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
        <label className="field-label">Month</label>
        <input
          type="month"
          name="month"
          defaultValue={month}
          onChange={submitFresh}
          className="field-input"
        />
      </div>
      <div>
        <label className="field-label">Invoice #/ID</label>
        <input
          type="text"
          name="number"
          defaultValue={number}
          placeholder="e.g. 2025-0007 or 42"
          className="field-input"
        />
      </div>
      <button type="submit" className="btn-primary">
        Filter
      </button>
    </form>
  );
}
