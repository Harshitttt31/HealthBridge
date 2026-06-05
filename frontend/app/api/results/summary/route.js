import { readFile } from "node:fs/promises";
import path from "node:path";

// GET /api/results/summary?company=AURT — company-level rollup (group-aggregated).
export async function GET(request) {
  const company = new URL(request.url).searchParams.get("company");
  if (!company) {
    return Response.json({ error: "company is required" }, { status: 400 });
  }

  const file = path.join(process.cwd(), "app", "data", "summary.json");
  let data;
  try {
    data = JSON.parse(await readFile(file, "utf-8"));
  } catch {
    return Response.json({ error: "No summary yet." }, { status: 404 });
  }

  const summary = (data.companies ?? []).find((c) => c.company_id === company);
  if (!summary) {
    return Response.json({ error: "Unknown company" }, { status: 404 });
  }
  return Response.json({ summary });
}
