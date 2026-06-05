import { readFile } from "node:fs/promises";
import path from "node:path";

// GET /api/results/groups?company=AURT
// Reads the pipeline's group-level output and returns ONLY the requested
// company's cohorts. Every cohort already satisfies k>=20 (enforced upstream),
// so nothing here is derived from < 20 employees.
export async function GET(request) {
  const company = new URL(request.url).searchParams.get("company");
  if (!company) {
    return Response.json({ error: "company is required" }, { status: 400 });
  }

  const file = path.join(process.cwd(), "app", "data", "groups.json");
  let data;
  try {
    data = JSON.parse(await readFile(file, "utf-8"));
  } catch {
    return Response.json(
      { error: "No processed results yet. Run the pipeline." },
      { status: 404 }
    );
  }

  const cohorts = (data.cohorts ?? []).filter(
    (c) => c.cohort_id?.startsWith(company + "-")
  );
  return Response.json({ cohorts });
}
