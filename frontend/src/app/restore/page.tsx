import { apiGet } from "@/lib/api";
import type { Me } from "@/lib/types";
import Nav from "@/components/Nav";
import RestoreForm from "./RestoreForm";

export default async function RestorePage() {
  const me = await apiGet<Me>("/me/");
  return (
    <>
      <Nav orgName={me.organization.name} username={me.username} />
      <div className="mx-auto w-full max-w-2xl px-4 py-8">
      <h1 className="mb-2 text-xl font-semibold text-slate-900">Restore from backup</h1>
      <p className="mb-6 text-sm text-slate-500">
        Upload a full database backup JSON (the same file produced by the existing Postgres/NAS backup, or{" "}
        <code>python manage.py dumpdata</code>). Only your own organization&apos;s data (
        <strong>{me.organization.name}</strong>) is ever read or changed — other organizations and user accounts in
        the file are ignored entirely. Preview first: it shows exactly what would be created, updated, or deleted,
        with invoice numbers always kept intact, before anything is written.
      </p>

      <div className="rounded-lg border border-slate-200 bg-white p-6">
        <RestoreForm />
      </div>
      </div>
    </>
  );
}
