// Shared formatting + band/quadrant visual metadata for the dashboard.

export const BANDS = ["Excellent", "Good", "Fair", "Poor", "Critical"];

export const BAND_COLORS = {
  Excellent: "#0d9488",
  Good: "#22c55e",
  Fair: "#eab308",
  Poor: "#f97316",
  Critical: "#ef4444",
};

export const QUADRANT_META = {
  Priority: { color: "#ef4444", label: "Priority", hint: "Low score · high cost" },
  Watch: { color: "#f97316", label: "Watch", hint: "Low score · low cost" },
  "Costly but well": { color: "#eab308", label: "Costly but well", hint: "High score · high cost" },
  Healthy: { color: "#0d9488", label: "Healthy", hint: "High score · low cost" },
};

// Compact Indian-rupee formatting: ₹1.2L, ₹96.9k, ₹820.
export function inr(value) {
  if (value == null) return "—";
  const n = Number(value);
  if (n >= 1e7) return `₹${(n / 1e7).toFixed(1)}Cr`;
  if (n >= 1e5) return `₹${(n / 1e5).toFixed(1)}L`;
  if (n >= 1e3) return `₹${(n / 1e3).toFixed(1)}k`;
  return `₹${Math.round(n)}`;
}

export function bandForScore(score) {
  if (score >= 800) return "Excellent";
  if (score >= 650) return "Good";
  if (score >= 500) return "Fair";
  if (score >= 350) return "Poor";
  return "Critical";
}
