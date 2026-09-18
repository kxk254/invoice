"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { logout } from "@/app/login/actions";

const LINKS = [
  { href: "/account-items", label: "Line items" },
  { href: "/invoices", label: "Invoices" },
  { href: "/import", label: "Import" },
  { href: "/restore", label: "Restore" },
];

function Logo() {
  return (
    <svg width="26" height="26" viewBox="0 0 32 32" className="shrink-0 rounded-md" aria-hidden="true">
      <defs>
        <linearGradient id="nav-logo-grad" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="#4f46e5" />
          <stop offset="100%" stopColor="#7c3aed" />
        </linearGradient>
      </defs>
      <rect width="32" height="32" rx="8" fill="url(#nav-logo-grad)" />
      <path
        d="M10.5 7.5 L16 15 M21.5 7.5 L16 15 M16 15 L16 25 M11 18.5 L21 18.5 M11 21.5 L21 21.5"
        fill="none"
        stroke="#ffffff"
        strokeWidth={2.8}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export default function Nav({ orgName, username }: { orgName: string; username: string }) {
  const pathname = usePathname();

  return (
    <div className="sticky top-0 z-30 border-b border-slate-200 bg-white/90 backdrop-blur">
      <div className="mx-auto flex w-full max-w-6xl flex-wrap items-center justify-between gap-x-6 gap-y-2 px-4 py-3">
        <div className="flex flex-wrap items-center gap-x-6 gap-y-2">
          <div className="flex items-center gap-2">
            <Logo />
            <span className="text-sm font-semibold text-slate-900">{orgName}</span>
          </div>
          <nav className="flex flex-wrap items-center gap-1 text-sm">
            {LINKS.map((link) => {
              const active = pathname === link.href || pathname?.startsWith(`${link.href}/`);
              return (
                <Link
                  key={link.href}
                  href={link.href}
                  aria-current={active ? "page" : undefined}
                  className={`rounded-md px-3 py-1.5 font-medium transition-colors ${
                    active ? "bg-brand-light text-brand-dark" : "text-slate-600 hover:bg-slate-100 hover:text-slate-900"
                  }`}
                >
                  {link.label}
                </Link>
              );
            })}
          </nav>
        </div>
        <div className="flex items-center gap-3 text-sm text-slate-500">
          <span className="hidden sm:inline">{username}</span>
          <form action={logout}>
            <button type="submit" className="btn-secondary px-3 py-1 text-xs">
              Sign out
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
