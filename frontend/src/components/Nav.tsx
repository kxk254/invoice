import Link from "next/link";
import { logout } from "@/app/login/actions";

export default function Nav({ orgName, username }: { orgName: string; username: string }) {
  return (
    <div className="border-b border-slate-200 bg-white">
      <div className="mx-auto flex w-full max-w-6xl items-center justify-between px-4 py-3">
        <div className="flex items-center gap-6">
          <span className="text-sm font-semibold text-slate-900">{orgName}</span>
          <nav className="flex gap-4 text-sm text-slate-600">
            <Link href="/account-items" className="hover:text-slate-900">
              Line items
            </Link>
            <Link href="/invoices" className="hover:text-slate-900">
              Invoices
            </Link>
            <Link href="/import" className="hover:text-slate-900">
              Import
            </Link>
            <Link href="/restore" className="hover:text-slate-900">
              Restore
            </Link>
          </nav>
        </div>
        <div className="flex items-center gap-3 text-sm text-slate-500">
          <span>{username}</span>
          <form action={logout}>
            <button type="submit" className="rounded border border-slate-300 px-3 py-1 text-xs text-slate-600 hover:bg-slate-50">
              Sign out
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
