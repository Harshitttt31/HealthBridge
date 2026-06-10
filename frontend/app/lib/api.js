// Real backend API client — talks to the FastAPI service (Step 12).
// Response shapes match the backend contract; see backend/app/auth.py and
// backend/app/results.py. This replaces the old mockApi for auth.

// Where the FastAPI backend lives. Override via NEXT_PUBLIC_API_BASE.
export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

// --- low-level fetch --------------------------------------------------------
// Thin wrapper that attaches the Bearer token and surfaces the backend's
// `detail` message on errors so the UI can show something useful.
export async function apiFetch(path, { token, headers, ...opts } = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    ...opts,
    headers: {
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...headers,
    },
  });

  if (!res.ok) {
    let message = `Request failed (${res.status})`;
    let detail = null;
    try {
      const body = await res.json();
      detail = body?.detail ?? null;
      // FastAPI `detail` is a string for simple errors, or a validation object
      // (see backend ingestion.ValidationResult.as_dict) for schema failures.
      if (typeof detail === "string") {
        message = detail;
      } else if (detail?.message) {
        message = detail.message;
      }
    } catch {
      // Non-JSON error body — keep the generic message.
    }
    const err = new Error(message);
    err.status = res.status;
    err.detail = detail; // structured validation info, when present
    throw err;
  }

  // 204 / empty bodies.
  if (res.status === 204) return null;
  return res.json();
}

// --- auth -------------------------------------------------------------------
// POST /auth/login -> { access_token, token_type, role, company_id }
// Returns the session shape the rest of the app consumes.
export async function login(email, password) {
  const data = await apiFetch("/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  return {
    token: data.access_token,
    role: data.role,
    company_id: data.company_id,
    email,
  };
}

// GET /auth/me -> { user_id, role, company_id } — confirms a token is still valid.
export async function getMe(token) {
  return apiFetch("/auth/me", { token });
}

// --- uploads ----------------------------------------------------------------
// POST /upload/{ahc|hrms} (multipart). Backend validates the schema, isolates
// to the caller's company, runs de-identify→noise→tokenize, and stores the set.
// Returns { upload_id, kind, company_id, rows_stored, rows_dropped_other_company,
//           warnings }. On schema failure it throws an Error whose `.detail`
// carries { missing_required, missing_expected, company_ids, message, ... }.
export async function uploadFile(kind, file, token) {
  const form = new FormData();
  form.append("file", file);
  return apiFetch(`/upload/${kind}`, { method: "POST", token, body: form });
}

// --- processing & results ---------------------------------------------------
// POST /process — combine + score + group + release for the caller's company.
// 409 if AHC/HRMS haven't both been uploaded yet. Returns a small summary.
export async function processData(token) {
  return apiFetch("/process", { method: "POST", token });
}

// GET /results/companies -> { companies: [{company_id, company_name}] }
// Returns all companies that have processed results. Used by the provider dropdown.
export async function getCompanies(token) {
  return apiFetch("/results/companies", { token });
}

// GET /results/groups -> { company_id, company_name, processed, cohort_count, cohorts }
// HR: company derived from JWT. Provider: must pass companyId.
export async function getGroups(token, companyId) {
  const qs = companyId ? `?company_id=${encodeURIComponent(companyId)}` : "";
  return apiFetch(`/results/groups${qs}`, { token });
}

// GET /results/summary -> flat company rollup (avg_health_score, avg_cost_per_head_inr,
// band_distribution, quadrants, score_axis, cost_axis, employees_covered, ...).
// HR: company derived from JWT. Provider: must pass companyId.
export async function getSummary(token, companyId) {
  const qs = companyId ? `?company_id=${encodeURIComponent(companyId)}` : "";
  return apiFetch(`/results/summary${qs}`, { token });
}

// --- demo credentials -------------------------------------------------------
// Seeded by `python -m app.seed`. HR accounts are per-company; one provider
// account covers all companies (uploads the full AHC dataset).
export const DEMO_CREDENTIALS = [
  { email: "hr@jpm001.demo", password: "demo1234", role: "hr" },
  { email: "hr@tcs001.demo", password: "demo1234", role: "hr" },
  { email: "provider@hclhealth.demo", password: "demo1234", role: "provider" },
];
