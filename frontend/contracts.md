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
  "role": "hr | employer",
  "company_id": "ACME",
  "username": "hr@acme"
}
```
The real token is a signed JWT carrying `{ user_id, role, company_id }`.
Role determines landing page: `hr` → `/upload/hrms`, `employer` → `/upload/ahc`.

## POST /upload/hrms  (role: hr)   — TODO Phase B
## POST /upload/ahc   (role: employer) — TODO Phase B
Multipart file upload. Returns validation result + de-identified row count.

## POST /process  (either role) — TODO Phase B
Runs pipeline steps 4–5 + scoring + grouping + aggregation for caller's company.

## GET /results/groups  (either role) — TODO (shape locked in dashboard step)
Array of cohorts, each `n >= 20`. No field ever derived from < 20 employees.
