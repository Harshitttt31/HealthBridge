# Frontend ⇄ Backend API contracts

These are the response shapes the Next.js app expects. The mock functions in
`app/lib/mockApi.js` return exactly these shapes, so the real FastAPI backend
must conform to them — that's what keeps frontend-first development from causing
rework.

## POST /auth/login

Request: `{ username, password }`

Response:
```json
{
  "token": "<JWT string>",
  "role": "hr | provider",
  "company_id": "ACME",
  "username": "hr@acme"
}
```
The real token is a signed JWT carrying `{ user_id, role, company_id }`.
Role determines landing page: `hr` → `/dashboard`, `provider` → `/upload/ahc`.
HR also has access to `/upload/hrms`; only HR sees the dashboard.

## POST /upload/hrms  (role: hr)
Multipart file upload. Returns `{ upload_id, kind, company_id, rows_stored, warnings }`.

## POST /upload/ahc   (role: provider) — combined AHC + HRA (Option 2)
Multipart file upload of one combined file: clinical labs **plus** the optional
HRA questionnaire on the same row, keyed by `employee_id` and tagged with `CUG`.
On ingest the questionnaire half is split off into an **engine-only** store
(consented rows only) and never served to a dashboard.

Response:
```json
{
  "kind": "ahc",
  "companies_stored": ["jpm001", "tcs001"],
  "rows_stored": 200000,
  "hra_rows_stored": 140000,
  "hra_companies": ["jpm001", "tcs001"],
  "warnings": []
}
```
Optional HRA columns: `smoking, alcohol, physical_activity, diet_quality, sleep,
stress, waist_cm, fh_diabetes, fh_hypertension, fh_cvd, fh_stroke, fh_cancer,
hra_consent`. Absent/declined → scoring falls back to `LABS-ONLY`.

## POST /process  (either role)
Runs pipeline steps 4–5 + scoring + grouping + aggregation for the caller's
company. Scoring is the **three-pillar** Group Health Index:
Clinical (0.45) + Behavioural (0.20) + Future-Risk (0.35), with a per-employee
completeness tier (`COMPLETE` / `LABS-ONLY`). Raw HRA is consumed into pillar
sub-scores and dropped before grouping.

## GET /results/groups  (either role)
Array of cohorts, each `n >= 20`. No field ever derived from < 20 employees.
Each cohort additionally carries:
```json
{
  "hra_coverage_pct": 72.0,
  "pillars": { "clinical": 81.4, "behavioural": 66.9, "future": 74.2 }
}
```
(`pillars.behavioural` is `null` when every row in the cohort is labs-only.)

## GET /results/summary  (either role)
Company rollup including `hra_coverage_pct` (headcount-weighted share of
`COMPLETE` profiles) alongside `avg_health_score`, `avg_cost_per_head_inr`,
`band_distribution`, `quadrants`, `score_axis`, `cost_axis`.
