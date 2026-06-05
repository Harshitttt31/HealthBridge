"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth, homePathForRole } from "../lib/auth-context";
import { DEMO_CREDENTIALS } from "../lib/mockApi";
import { Wordmark } from "../lib/Logo";

export default function LoginPage() {
  const { auth, loading, signIn } = useAuth();
  const router = useRouter();

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

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

  const roleLabel = (r) => (r === "hr" ? "HR" : "Provider");

  return (
    <main className="flex flex-1 items-center justify-center px-4 py-12">
      <div className="grid w-full max-w-4xl overflow-hidden rounded-3xl border border-slate-200/70 bg-white shadow-xl md:grid-cols-2">
        {/* Brand / value panel */}
        <div className="relative hidden flex-col justify-between bg-gradient-to-br from-brand-600 to-brand-800 p-8 text-white md:flex">
          <Wordmark />
          <div>
            <h2 className="text-2xl font-semibold leading-snug">
              Group Health Index Portal
            </h2>
            <p className="mt-3 text-sm leading-relaxed text-brand-50/90">
              Privacy-preserving health analytics across your workforce.
              Identifiers are removed and IDs tokenised before any data is
              combined.
            </p>
          </div>
          <ul className="space-y-2 text-sm text-brand-50/90">
            <li className="flex items-center gap-2">
              <span className="text-brand-200">✓</span> Every result covers ≥ 20
              employees
            </li>
            <li className="flex items-center gap-2">
              <span className="text-brand-200">✓</span> No individual is ever
              exposed
            </li>
            <li className="flex items-center gap-2">
              <span className="text-brand-200">✓</span> Data isolated per company
            </li>
          </ul>
        </div>

        {/* Form panel */}
        <div className="p-8">
          <div className="mb-6 md:hidden">
            <Wordmark />
          </div>
          <h1 className="text-xl font-semibold text-ink-900">Sign in</h1>
          <p className="mt-1 text-sm text-slate-500">
            HR and health-check providers use this portal.
          </p>

          <form onSubmit={handleSubmit} className="mt-6 space-y-4">
            <div>
              <label
                htmlFor="username"
                className="mb-1 block text-sm font-medium text-slate-700"
              >
                Username
              </label>
              <input
                id="username"
                type="text"
                autoComplete="username"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                className="input"
                placeholder="hr@acme"
                required
              />
            </div>

            <div>
              <label
                htmlFor="password"
                className="mb-1 block text-sm font-medium text-slate-700"
              >
                Password
              </label>
              <input
                id="password"
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="input"
                placeholder="••••••••"
                required
              />
            </div>

            {error && (
              <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">
                {error}
              </p>
            )}

            <button type="submit" disabled={submitting} className="btn-primary w-full">
              {submitting ? "Signing in…" : "Sign in"}
            </button>
          </form>

          {/* Demo helper — remove once the real backend is wired in. */}
          <div className="mt-6 rounded-xl border border-dashed border-slate-300 bg-slate-50/60 p-4">
            <p className="mb-2 text-xs font-medium uppercase tracking-wide text-slate-400">
              Demo accounts (password: demo123)
            </p>
            <div className="grid grid-cols-1 gap-1">
              {DEMO_CREDENTIALS.map((c) => (
                <button
                  key={c.username}
                  type="button"
                  onClick={() => fillDemo(c)}
                  className="flex items-center justify-between rounded-md px-2 py-1.5 text-left text-sm hover:bg-white"
                >
                  <span className="font-mono text-slate-700">{c.username}</span>
                  <span className="rounded-full bg-brand-50 px-2 py-0.5 text-xs font-medium text-brand-700">
                    {roleLabel(c.role)}
                  </span>
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>
    </main>
  );
}
