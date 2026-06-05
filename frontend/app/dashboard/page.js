"use client";

import { useEffect, useState } from "react";
import RequireRole from "../lib/RequireRole";
import Header from "../lib/Header";
import { useAuth } from "../lib/auth-context";
import { getGroups, getSummary } from "../lib/mockApi";
import { inr } from "../lib/format";
import { BandLegend } from "../lib/dashboard/BandBar";
import QuadrantChart from "../lib/dashboard/QuadrantChart";
import CohortCard from "../lib/dashboard/CohortCard";
import CohortTable from "../lib/dashboard/CohortTable";

function StatTile({ label, value, sub }) {
  return (
    <div className="card p-4">
      <p className="text-xs uppercase tracking-wide text-slate-400">{label}</p>
      <p className="mt-1 text-2xl font-semibold text-ink-900">{value}</p>
      {sub && <p className="text-xs text-slate-400">{sub}</p>}
    </div>
  );
}

function DashboardContent() {
  const { auth } = useAuth();
  const [summary, setSummary] = useState(null);
  const [cohorts, setCohorts] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!auth?.company_id) return;
    let cancelled = false;
    (async () => {
      try {
        const [s, g] = await Promise.all([
          getSummary(auth.company_id),
          getGroups(auth.company_id),
        ]);
        if (!cancelled) {
          setSummary(s.summary);
          setCohorts(g.cohorts);
        }
      } catch (e) {
        if (!cancelled) setError(e.message);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [auth?.company_id]);

  if (error) {
    return (
      <div className="rounded-xl bg-red-50 px-4 py-3 text-sm text-red-700">
        {error}
      </div>
    );
  }
  if (!summary || !cohorts) {
    return <p className="text-sm text-slate-500">Loading cohort results…</p>;
  }

  const priority = cohorts
    .filter((c) => c.quadrant === "Priority")
    .slice(0, 6);
  const attention = priority.length
    ? priority
    : [...cohorts].sort((a, b) => a.group_health_score - b.group_health_score).slice(0, 6);

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-xl font-semibold text-ink-900">
          {summary.company_name}
        </h1>
        <p className="mt-1 text-sm text-slate-500">
          Group Health Index across {summary.cohort_count} cohorts ·{" "}
          {summary.employees_covered.toLocaleString()} employees. Every cohort
          represents at least 20 people — no individual is ever shown.
        </p>
      </div>

      {/* KPIs */}
      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <StatTile label="Avg health score" value={summary.avg_health_score} sub="/ 1000" />
        <StatTile label="Employees" value={summary.employees_covered.toLocaleString()} sub={`${summary.cohort_count} cohorts`} />
        <StatTile label="Avg cost / head" value={inr(summary.avg_cost_per_head_inr)} sub="OPD + IPD claims" />
        <StatTile
          label="Priority cohorts"
          value={cohorts.filter((c) => c.quadrant === "Priority").length}
          sub="low score · high cost"
        />
      </div>

      {/* Quadrant chart */}
      <div className="card p-5">
        <div className="mb-3 flex items-center justify-between">
          <div>
            <h2 className="text-sm font-semibold text-ink-900">
              Health vs. cost — risk quadrants
            </h2>
            <p className="text-xs text-slate-400">
              Each bubble is a cohort; size = headcount. Bottom-right is healthy
              and cheap; top-left is the priority zone.
            </p>
          </div>
        </div>
        <QuadrantChart
          cohorts={cohorts}
          scoreAxis={summary.score_axis}
          costAxis={summary.cost_axis}
        />
      </div>

      {/* Attention cohorts */}
      <div>
        <h2 className="mb-3 text-sm font-semibold text-ink-900">
          {priority.length ? "Priority cohorts" : "Lowest-scoring cohorts"}
        </h2>
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
          {attention.map((c) => (
            <CohortCard key={c.cohort_id} cohort={c} />
          ))}
        </div>
      </div>

      {/* Full table */}
      <div>
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-ink-900">All cohorts</h2>
          <BandLegend />
        </div>
        <CohortTable cohorts={cohorts} />
      </div>
    </div>
  );
}

export default function DashboardPage() {
  return (
    <RequireRole role="hr">
      <Header />
      <main className="mx-auto max-w-6xl px-4 py-8">
        <DashboardContent />
      </main>
    </RequireRole>
  );
}
