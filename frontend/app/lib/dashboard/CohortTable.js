"use client";

import { useState } from "react";
import { BAND_COLORS, QUADRANT_META, inr } from "../format";

const COLUMNS = [
  { key: "label", label: "Cohort", align: "left" },
  { key: "n", label: "Size", align: "right" },
  { key: "group_health_score", label: "Health", align: "right" },
  { key: "cost_per_head_inr", label: "Cost/head", align: "right" },
  { key: "claims_per_employee", label: "Claims/emp", align: "right" },
  { key: "avg_absenteeism_pct", label: "Absent%", align: "right" },
  { key: "quadrant", label: "Quadrant", align: "left" },
];

function valueFor(c, key) {
  if (key === "claims_per_employee") return c.claims?.claims_per_employee ?? 0;
  if (key === "avg_absenteeism_pct") return c.claims?.avg_absenteeism_pct ?? 0;
  return c[key];
}

export default function CohortTable({ cohorts }) {
  const [sortKey, setSortKey] = useState("group_health_score");
  const [asc, setAsc] = useState(true);

  const sorted = [...cohorts].sort((a, b) => {
    const va = valueFor(a, sortKey);
    const vb = valueFor(b, sortKey);
    const cmp = typeof va === "string" ? va.localeCompare(vb) : va - vb;
    return asc ? cmp : -cmp;
  });

  function toggle(key) {
    if (key === sortKey) setAsc(!asc);
    else {
      setSortKey(key);
      setAsc(true);
    }
  }

  return (
    <div className="card overflow-hidden">
      <div className="max-h-[560px] overflow-auto">
        <table className="w-full text-sm">
          <thead className="sticky top-0 bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
            <tr>
              {COLUMNS.map((col) => (
                <th
                  key={col.key}
                  onClick={() => toggle(col.key)}
                  className={`cursor-pointer select-none px-4 py-3 font-medium hover:text-slate-800 ${
                    col.align === "right" ? "text-right" : "text-left"
                  }`}
                >
                  {col.label}
                  {sortKey === col.key && (asc ? " ▲" : " ▼")}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {sorted.map((c) => {
              const q = QUADRANT_META[c.quadrant];
              return (
                <tr key={c.cohort_id} className="hover:bg-slate-50/60">
                  <td className="px-4 py-2.5 text-slate-700">{c.label}</td>
                  <td className="px-4 py-2.5 text-right text-slate-500">{c.n}</td>
                  <td className="px-4 py-2.5 text-right">
                    <span
                      className="font-medium"
                      style={{ color: BAND_COLORS[c.band] }}
                    >
                      {c.group_health_score}
                    </span>
                  </td>
                  <td className="px-4 py-2.5 text-right text-slate-600">
                    {inr(c.cost_per_head_inr)}
                  </td>
                  <td className="px-4 py-2.5 text-right text-slate-600">
                    {c.claims?.claims_per_employee}
                  </td>
                  <td className="px-4 py-2.5 text-right text-slate-600">
                    {c.claims?.avg_absenteeism_pct}
                  </td>
                  <td className="px-4 py-2.5">
                    <span
                      className="rounded-full px-2 py-0.5 text-xs font-medium"
                      style={{ backgroundColor: `${q?.color}1a`, color: q?.color }}
                    >
                      {q?.label}
                    </span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
