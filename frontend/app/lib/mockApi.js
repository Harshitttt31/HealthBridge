// Mock backend API — Phase A (frontend-first).
// Every function here returns the SAME shape the real FastAPI backend will return,
// so swapping these for fetch() calls later is a drop-in change.
// See contracts.md for the locked response shapes.

// --- Demo users (will be seeded in SQLite by the real backend) ---
// role: 'hr' uploads HRMS claims; 'employer' uploads AHC health-checks.
const DEMO_USERS = [
  { username: "hr@acme", password: "demo123", role: "hr", company_id: "ACME" },
  { username: "employer@acme", password: "demo123", role: "employer", company_id: "ACME" },
  { username: "hr@globex", password: "demo123", role: "hr", company_id: "GLOBEX" },
  { username: "employer@globex", password: "demo123", role: "employer", company_id: "GLOBEX" },
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
