// Mock backend API — Phase A (frontend-first).
// Every function here returns the SAME shape the real FastAPI backend will return,
// so swapping these for fetch() calls later is a drop-in change.
// See contracts.md for the locked response shapes.

// --- Demo users (will be seeded in SQLite by the real backend) ---
// role 'hr'       — a company's HR; uploads HRMS claims and views the dashboard.
// role 'provider' — a health-check provider; uploads AHC reports for that company.
const DEMO_USERS = [
  { username: "hr@aurora", password: "demo123", role: "hr", company_id: "AURT" },
  { username: "provider@aurora", password: "demo123", role: "provider", company_id: "AURT" },
  { username: "hr@bluepeak", password: "demo123", role: "hr", company_id: "BLPK" },
  { username: "provider@bluepeak", password: "demo123", role: "provider", company_id: "BLPK" },
];

// Simulate network latency so the UI's loading states are exercised.
function delay(ms = 400) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

// POST /auth/login -> { token, role, company_id, username }
export async function login(username, password) {
  await delay();
  const user = DEMO_USERS.find(
    (u) => u.username === username && u.password === password
  );
  if (!user) {
    throw new Error("Invalid username or password");
  }
  // A fake opaque token; the real backend returns a signed JWT carrying
  // { user_id, role, company_id }.
  const token = `mock.${btoa(`${user.username}:${user.role}:${user.company_id}`)}`;
  return {
    token,
    role: user.role,
    company_id: user.company_id,
    username: user.username,
  };
}

export const DEMO_CREDENTIALS = DEMO_USERS.map(({ username, password, role }) => ({
  username,
  password,
  role,
}));

// GET /results/groups — cohort Group Health Index results for a company (k>=20).
// Backed for now by a Next.js route handler that reads the pipeline's JSON output.
export async function getGroups(companyId) {
  const res = await fetch(`/api/results/groups?company=${encodeURIComponent(companyId)}`);
  if (!res.ok) throw new Error("Failed to load group results");
  return res.json(); // { cohorts: [...] }
}

// GET /results/summary — company-level rollup (still group-aggregated).
export async function getSummary(companyId) {
  const res = await fetch(`/api/results/summary?company=${encodeURIComponent(companyId)}`);
  if (!res.ok) throw new Error("Failed to load summary");
  return res.json(); // { summary: {...} }
}
