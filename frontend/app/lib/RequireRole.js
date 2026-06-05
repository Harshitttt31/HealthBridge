"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth, homePathForRole } from "./auth-context";

// Client-side guard. `role` is optional:
//   - omitted: any logged-in user may view
//   - 'hr' | 'employer': only that role; others are bounced to their own home.
// Enforces invariant FR-01 in the UI (HR can't reach AHC, Employer can't reach HRMS).
// The real backend enforces this again server-side via the JWT.
export default function RequireRole({ role, children }) {
  const { auth, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (loading) return;
    if (!auth) {
      router.replace("/login");
    } else if (role && auth.role !== role) {
      router.replace(homePathForRole(auth.role));
    }
  }, [auth, loading, role, router]);

  // While resolving auth, or about to redirect, render nothing.
  if (loading || !auth || (role && auth.role !== role)) {
    return (
      <div className="flex min-h-[40vh] items-center justify-center text-sm text-gray-500">
        Loading…
      </div>
    );
  }

  return children;
}
