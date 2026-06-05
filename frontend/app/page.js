"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth, homePathForRole } from "./lib/auth-context";

// Index route: send users to their role home, or to login.
export default function Home() {
  const { auth, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (loading) return;
    router.replace(auth ? homePathForRole(auth.role) : "/login");
  }, [auth, loading, router]);

  return (
    <div className="flex min-h-screen items-center justify-center text-sm text-gray-500">
      Loading HealthBridge…
    </div>
  );
}
