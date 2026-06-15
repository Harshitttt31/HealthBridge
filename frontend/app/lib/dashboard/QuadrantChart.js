"use client";

import {
  ScatterChart, Scatter, XAxis, YAxis, ZAxis, CartesianGrid,
  Tooltip, ReferenceLine, ResponsiveContainer, Cell,
} from "recharts";
import { QUADRANT_META, inr } from "../format";

function PointTooltip({ active, payload }) {
  if (!active || !payload?.length) return null;
  const c = payload[0].payload;
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-3 text-xs shadow-md">
      <p className="font-medium text-ink-900">{c.label}</p>
      <p className="mt-1 text-slate-500">{c.n} employees</p>
      <p className="text-slate-600">Health score: <b>{c.group_health_score}</b></p>
      <p className="text-slate-600">Cost / head: <b>{inr(c.cost_per_head_inr)}</b></p>
      <p className="mt-1" style={{ color: QUADRANT_META[c.quadrant]?.color }}>
        {QUADRANT_META[c.quadrant]?.label}
      </p>
    </div>
  );
}

// 2-axis risk placement: x = Health Index, y = claims cost-per-head.
// Bubble size = cohort headcount. Reference lines mark the quadrant split.
export default function QuadrantChart({ cohorts, scoreAxis = 650, costAxis }) {
  const data = cohorts.map((c) => ({
    x: c.group_health_score,
    y: c.cost_per_head_inr,
    z: c.n,
    ...c,
  }));

  return (
    <div className="h-[380px] w-full">
      <ResponsiveContainer width="100%" height="100%">
        <ScatterChart margin={{ top: 10, right: 20, bottom: 30, left: 10 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
          <XAxis
            type="number" dataKey="x" name="Health score"
            domain={[300, 1000]} tick={{ fontSize: 12, fill: "#64748b" }}
            label={{ value: "Group Health Score →", position: "insideBottom", offset: -15, fontSize: 12, fill: "#64748b" }}
          />
          <YAxis
            type="number" dataKey="y" name="Cost / head"
            tick={{ fontSize: 12, fill: "#64748b" }}
            tickFormatter={inr}
            label={{ value: "↑ Claims cost / head", angle: -90, position: "insideLeft", fontSize: 12, fill: "#64748b" }}
          />
          <ZAxis type="number" dataKey="z" range={[40, 400]} name="Headcount" />
          {costAxis != null && <ReferenceLine y={costAxis} stroke="#94a3b8" strokeDasharray="4 4" />}
          <ReferenceLine x={scoreAxis} stroke="#94a3b8" strokeDasharray="4 4" />
          <Tooltip content={<PointTooltip />} cursor={{ strokeDasharray: "3 3" }} />
          <Scatter data={data} fillOpacity={0.7}>
            {data.map((d, i) => (
              <Cell key={i} fill={QUADRANT_META[d.quadrant]?.color ?? "#94a3b8"} />
            ))}
          </Scatter>
        </ScatterChart>
      </ResponsiveContainer>
    </div>
  );
}
