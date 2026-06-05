"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "./auth-context";

export default function Header() {
  const { auth, signOut } = useAuth();
  const router = useRouter();

  function handleSignOut() {
    signOut();
    router.replace("/login");
  }

  const uploadHref = auth?.role === "hr" ? "/upload/hrms" : "/upload/ahc";

  return (
    <header className="border-b border-gray-200 bg-white">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3">
        <div className="flex items-center gap-6">
          <Link href="/" className="font-semibold tracking-tight">
            HealthBridge
          </Link>
          {auth && (
            <nav className="flex items-center gap-4 text-sm text-gray-600">
              <Link href={uploadHref} className="hover:text-gray-900">
                Upload
              </Link>
              <Link href="/dashboard" className="hover:text-gray-900">
                Dashboard
              </Link>
            </nav>
          )}
        </div>

        {auth && (
          <div className="flex items-center gap-3 text-sm">
            <span className="hidden text-gray-500 sm:inline">
              {auth.username}
            </span>
            <span className="rounded bg-gray-100 px-2 py-0.5 text-xs text-gray-600">
              {auth.role} · {auth.company_id}
            </span>
            <button
              onClick={handleSignOut}
              className="rounded-lg border border-gray-300 px-3 py-1 text-sm hover:bg-gray-50"
            >
              Sign out
            </button>
          </div>
        )}
      </div>
    </header>
  );
}
