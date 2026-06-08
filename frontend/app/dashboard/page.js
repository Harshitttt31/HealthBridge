"use client";

import { useEffect, useState } from "react";
import RequireRole from "../lib/RequireRole";
import Header from "../lib/Header";
import { useAuth } from "../lib/auth-context";
import { getGroups, getSummary, processData } from "../lib/api";
import { inr, MIN_GROUP } from "../lib/format";
import { BandLegend } from "../lib/dashboard/BandBar";
import QuadrantChart from "../lib/dashboard/QuadrantChart";
import CohortCard from "../lib/dashboard/CohortCard";
import CohortTable from "../lib/dashboard/CohortTable";

// Turn a /process error into something an HR user can act on.
// 409 = one/both datasets not uploaded yet; 422 = AHC & HRMS didn't match.
function friendlyProcessError(e) {
  if (e.status === 409) {
    return (
      "Both files must be uploaded before processing. " +
      "Ask the health-check provider to upload the AHC file, and make sure the " +
      "HRMS claims file is uploaded too."
    );
  }
  if (e.status === 422) {
    return (
      "Processing ran but no employees matched across the AHC and HRMS files. " +
      "Check that both files are for the same company and period."
    );
  }
  return e.message || "Processing failed. Please try again.";
}

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
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [processing, setProcessing] = useState(false);
  const [processError, setProcessError] = useState("");

  const token = auth?.token;

  async function load() {
    setError("");
    try {
      const [s, g] = await Promise.all([getSummary(token), getGroups(token)]);
      // Live endpoints return flat objects; company is derived from the JWT.
      setSummary(s);
      setCohorts(g.cohorts ?? []);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (!token) return;
    let cancelled = false;
    (async () => {
      if (!cancelled) await load();
    })();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  async function handleProcess() {
    setProcessError("");
    setProcessing(true);
    try {
      await processData(token);
      await load();
    } catch (e) {
      setProcessError(friendlyProcessError(e));
    } finally {
      setProcessing(false);
    }
  }

  if (loading) {
    return <p className="text-sm text-slate-500">Loading cohort results…</p>;
  }
  if (error) {
    return (
      <div className="rounded-xl bg-red-50 px-4 py-3 text-sm text-red-700">
        {error}
      </div>
    );
  }

  // Hard k-anonymity guard in the UI: never render a cohort below the floor,
  // even if a bad payload slipped past the backend. This is the authoritative
  // "no drill below 20" enforcement for everything rendered downstream.
  const safeCohorts = (cohorts ?? []).filter((c) => (c?.n ?? 0) >= MIN_GROUP);
  const suppressed = (cohorts?.length ?? 0) - safeCohorts.length;

  // No results yet for this company — offer to run processing.
  if (!summary?.processed || !safeCohorts.length) {
    return (
      <div className="space-y-4">
        <h1 className="text-xl font-semibold text-ink-900">
          {summary?.company_name || auth?.company_id}
        </h1>
        <div className="card p-6">
          <p className="text-sm font-medium text-ink-900">No results yet</p>
          <p className="mt-1 text-sm text-slate-500">
            Once both the AHC health-check and HRMS claims files have been
            uploaded, run processing to build the Group Health Index. Every
            cohort covers at least 20 employees.
          </p>
          {processError && (
            <p className="mt-3 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">
              {processError}
            </p>
          )}
          <button
            type="button"
            onClick={handleProcess}
            disabled={processing}
            className="btn-primary mt-4"
          >
            {processing ? "Processing…" : "Run processing"}
          </button>
          {processing && (
            <p className="mt-2 text-xs text-slate-400">
              This can take up to a minute for a full 100k-row dataset.
            </p>
          )}
        </div>
      </div>
    );
  }

  const priority = safeCohorts
    .filter((c) => c.quadrant === "Priority")
    .slice(0, 6);
  const attention = priority.length
    ? priority
    : [...safeCohorts].sort((a, b) => a.group_health_score - b.group_health_score).slice(0, 6);

  return (
    <div className="space-y-8">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold text-ink-900">
            {summary.company_name}
          </h1>
          <p className="mt-1 text-sm text-slate-500">
            Group Health Index across {summary.cohort_count} cohorts ·{" "}
            {summary.employees_covered.toLocaleString()} employees. Every cohort
            represents at least 20 people — no individual is ever shown.
          </p>
          {suppressed > 0 && (
            <p className="mt-2 rounded-lg bg-amber-50 px-3 py-2 text-xs text-amber-700">
              {suppressed} cohort(s) below the {MIN_GROUP}-employee privacy floor
              were hidden.
            </p>
          )}
          {processError && (
            <p className="mt-2 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">
              {processError}
            </p>
          )}
        </div>
        <button
          type="button"
          onClick={handleProcess}
          disabled={processing}
          className="btn-ghost shrink-0"
          title="Re-run the pipeline over the latest uploads"
        >
          {processing ? "Processing…" : "Re-process"}
        </button>
      </div>

      {/* KPIs */}
      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <StatTile label="Avg health score" value={summary.avg_health_score} sub="/ 1000" />
        <StatTile label="Employees" value={summary.employees_covered.toLocaleString()} sub={`${summary.cohort_count} cohorts`} />
        <StatTile label="Avg cost / head" value={inr(summary.avg_cost_per_head_inr)} sub="OPD + IPD claims" />
        <StatTile
          label="Priority cohorts"
          value={safeCohorts.filter((c) => c.quadrant === "Priority").length}
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
          cohorts={safeCohorts}
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
        <CohortTable cohorts={safeCohorts} />
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
