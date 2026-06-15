import BandBar from "./BandBar";
import { BAND_COLORS, QUADRANT_META, inr } from "../format";

// A focused card for a single cohort (used for priority/attention cohorts).
export default function CohortCard({ cohort }) {
  const q = QUADRANT_META[cohort.quadrant];
  return (
    <div className="card p-5">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-sm font-medium text-ink-900">{cohort.label}</p>
          <p className="text-xs text-slate-400">
            {cohort.n} employees · {cohort.quasi_ids?.gender}
            {cohort.quasi_ids?.band !== "All" ? ` · ${cohort.quasi_ids.band}` : ""}
          </p>
        </div>
        <span
          className="whitespace-nowrap rounded-full px-2 py-0.5 text-xs font-medium"
          style={{ backgroundColor: `${q?.color}1a`, color: q?.color }}
        >
          {q?.label}
        </span>
      </div>

      <div className="mt-4 flex items-end gap-2">
        <span
          className="text-3xl font-semibold"
          style={{ color: BAND_COLORS[cohort.band] }}
        >
          {cohort.group_health_score}
        </span>
        <span className="mb-1 text-xs text-slate-400">/ 1000 · {cohort.band}</span>
      </div>

      <div className="mt-3">
        <BandBar distribution={cohort.band_distribution} />
      </div>

      <div className="mt-4 grid grid-cols-2 gap-3 text-xs">
        <div>
          <p className="text-slate-400">Cost / head</p>
          <p className="font-medium text-ink-900">{inr(cohort.cost_per_head_inr)}</p>
        </div>
        <div>
          <p className="text-slate-400">Absenteeism</p>
          <p className="font-medium text-ink-900">{cohort.claims?.avg_absenteeism_pct}%/mo</p>
        </div>
      </div>

      {cohort.weakest_domains?.length > 0 && (
        <div className="mt-4">
          <p className="mb-1 text-xs text-slate-400">Weakest domains</p>
          <div className="flex flex-wrap gap-1.5">
            {cohort.weakest_domains.map((d) => (
              <span
                key={d.domain}
                className="rounded-md bg-slate-100 px-2 py-0.5 text-xs text-slate-600"
              >
                {d.domain} <span className="text-slate-400">{d.score}</span>
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
