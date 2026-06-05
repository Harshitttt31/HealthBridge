"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth, homePathForRole } from "../lib/auth-context";
import { DEMO_CREDENTIALS } from "../lib/mockApi";

export default function LoginPage() {
  const { auth, loading, signIn } = useAuth();
  const router = useRouter();

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  // Already logged in? Skip the form.
  useEffect(() => {
    if (!loading && auth) router.replace(homePathForRole(auth.role));
  }, [auth, loading, router]);

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    setSubmitting(true);
    try {
      const session = await signIn(username.trim(), password);
      router.replace(homePathForRole(session.role));
    } catch (err) {
      setError(err.message || "Login failed");
    } finally {
      setSubmitting(false);
    }
  }

  function fillDemo(cred) {
    setUsername(cred.username);
    setPassword(cred.password);
    setError("");
  }

  return (
    <main className="flex flex-1 items-center justify-center px-4 py-12">
      <div className="w-full max-w-md">
        <div className="mb-8 text-center">
          <h1 className="text-2xl font-semibold tracking-tight">HealthBridge</h1>
          <p className="mt-1 text-sm text-gray-500">
            Group Health Index Portal
          </p>
        </div>

        <form
          onSubmit={handleSubmit}
          className="space-y-4 rounded-xl border border-gray-200 bg-white p-6 shadow-sm"
        >
          <div>
            <label
              htmlFor="username"
              className="mb-1 block text-sm font-medium text-gray-700"
            >
              Username
            </label>
            <input
              id="username"
              type="text"
              autoComplete="username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-gray-900 focus:outline-none"
              placeholder="hr@acme"
              required
            />
          </div>

          <div>
            <label
              htmlFor="password"
              className="mb-1 block text-sm font-medium text-gray-700"
            >
              Password
            </label>
            <input
              id="password"
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-gray-900 focus:outline-none"
              placeholder="••••••••"
              required
            />
          </div>

          {error && (
            <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">
              {error}
            </p>
          )}

          <button
            type="submit"
            disabled={submitting}
            className="w-full rounded-lg bg-gray-900 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-gray-800 disabled:opacity-60"
          >
            {submitting ? "Signing in…" : "Sign in"}
          </button>
        </form>

        {/* Demo helper — remove once the real backend is wired in. */}
        <div className="mt-6 rounded-xl border border-dashed border-gray-300 bg-white p-4">
          <p className="mb-2 text-xs font-medium uppercase tracking-wide text-gray-400">
            Demo accounts (password: demo123)
          </p>
          <div className="grid grid-cols-1 gap-1.5">
            {DEMO_CREDENTIALS.map((c) => (
              <button
                key={c.username}
                type="button"
                onClick={() => fillDemo(c)}
                className="flex items-center justify-between rounded-md px-2 py-1.5 text-left text-sm hover:bg-gray-50"
              >
                <span className="font-mono text-gray-700">{c.username}</span>
                <span className="rounded bg-gray-100 px-1.5 py-0.5 text-xs text-gray-500">
                  {c.role}
                </span>
              </button>
            ))}
          </div>
        </div>
      </div>
    </main>
  );
}
