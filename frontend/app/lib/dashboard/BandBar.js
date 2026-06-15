import { BANDS, BAND_COLORS } from "../format";

// Horizontal stacked bar of the band distribution (% per health band).
export default function BandBar({ distribution }) {
  return (
    <div>
      <div className="flex h-2.5 w-full overflow-hidden rounded-full bg-slate-100">
        {BANDS.map((b) => {
          const pct = distribution?.[b] ?? 0;
          if (!pct) return null;
          return (
            <div
              key={b}
              style={{ width: `${pct}%`, backgroundColor: BAND_COLORS[b] }}
              title={`${b}: ${pct}%`}
            />
          );
        })}
      </div>
    </div>
  );
}

export function BandLegend() {
  return (
    <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-500">
      {BANDS.map((b) => (
        <span key={b} className="flex items-center gap-1.5">
          <span
            className="h-2.5 w-2.5 rounded-full"
            style={{ backgroundColor: BAND_COLORS[b] }}
          />
          {b}
        </span>
      ))}
    </div>
  );
}
