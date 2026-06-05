"use client";

import RequireRole from "../lib/RequireRole";
import Header from "../lib/Header";

export default function DashboardPage() {
  return (
    <RequireRole role="hr">
      <Header />
      <main className="mx-auto max-w-6xl px-4 py-10">
        <h1 className="text-xl font-semibold text-ink-900">Group Health Index</h1>
        <p className="mt-1 text-sm text-slate-500">
          Cohort results appear here once both datasets are processed. Every
          cohort represents at least 20 employees — no individual is ever shown.
        </p>

        <div className="mt-8 rounded-2xl border border-dashed border-slate-300 bg-white/60 p-10 text-center text-sm text-slate-400">
          Dashboard with cohort cards, band distribution, weak domains, claims
          metrics, and the health-vs-cost quadrant chart — coming in the next
          step (mock data).
        </div>
      </main>
    </RequireRole>
  );
}
