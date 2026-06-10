"use client";

import Link from "next/link";
import { useRouter, usePathname } from "next/navigation";
import { useAuth } from "./auth-context";
import { Wordmark } from "./Logo";

export default function Header() {
  const { auth, signOut } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  function handleSignOut() {
    signOut();
    router.replace("/login");
  }

  const uploadHref = auth?.role === "hr" ? "/upload/hrms" : "/upload/ahc";
  const links = [
    { href: uploadHref, label: "Upload" },
    { href: "/dashboard", label: "Dashboard" },
  ];

  const roleLabel = auth?.role === "hr" ? "HR" : auth?.role === "provider" ? "Health Provider" : "";

  return (
    <header className="sticky top-0 z-10 border-b border-slate-200/70 bg-white/80 backdrop-blur">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3">
        <div className="flex items-center gap-8">
          <Link href="/">
            <Wordmark />
          </Link>
          {auth && (
            <nav className="flex items-center gap-1 text-sm">
              {links.map((l) => {
                const active = pathname === l.href;
                return (
                  <Link
                    key={l.href}
                    href={l.href}
                    className={`rounded-lg px-3 py-1.5 transition-colors ${
                      active
                        ? "bg-brand-50 font-medium text-brand-700"
                        : "text-slate-600 hover:bg-slate-50 hover:text-slate-900"
                    }`}
                  >
                    {l.label}
                  </Link>
                );
              })}
            </nav>
          )}
        </div>

        {auth && (
          <div className="flex items-center gap-3 text-sm">
            <span className="hidden text-slate-500 sm:inline">
              {auth.email}
            </span>
            <span className="rounded-full bg-brand-50 px-2.5 py-0.5 text-xs font-medium text-brand-700 ring-1 ring-brand-100">
              {roleLabel}{auth.role === "hr" ? ` · ${auth.company_id}` : ""}
            </span>
            <button onClick={handleSignOut} className="btn-ghost">
              Sign out
            </button>
          </div>
        )}
      </div>
    </header>
  );
}
