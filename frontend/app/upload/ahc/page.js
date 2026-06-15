"use client";

import RequireRole from "../../lib/RequireRole";
import Header from "../../lib/Header";
import UploadWorkspace from "../../lib/UploadWorkspace";

// Combined AHC + HRA dataset — uploaded by Health Provider (Option 2).
// One row per employee across all companies: clinical labs plus the optional
// Health Risk Assessment questionnaire captured at the same checkup.
const REQUIRED_COLUMNS = [
  "company_id",
  "employee_id",
  "sex",
  "age",
  "bmi",
  "hba1c_percent",
  "systolic_bp_mmhg",
  "diastolic_bp_mmhg",
  "ldl_mg_dl",
  "hdl_mg_dl",
  "creatinine_mg_dl",
  "chronic_disease",
];

// HRA questionnaire columns (optional). When present and consented, they feed the
// Behavioural and Future-Risk pillars; otherwise scoring falls back to LABS-ONLY.
const HRA_COLUMNS = [
  "smoking",
  "alcohol",
  "physical_activity",
  "diet_quality",
  "sleep",
  "stress",
  "waist_cm",
  "fh_diabetes",
  "fh_hypertension",
  "fh_cvd",
  "fh_stroke",
  "fh_cancer",
  "hra_consent",
];

export default function AHCUploadPage() {
  return (
    <RequireRole role="provider">
      <Header />
      <UploadWorkspace
        kind="ahc"
        title="AHC + HRA Health-Check Upload"
        description="Provider workspace. Upload one combined export per employee: clinical labs plus the optional HRA questionnaire captured at the checkup. The questionnaire is split into an engine-only store and never shown to any dashboard; identifiers are stripped and IDs tokenised before any analysis."
        companyKey="CUG"
        requiredColumns={REQUIRED_COLUMNS}
        optionalColumns={HRA_COLUMNS}
        optionalLabel="HRA questionnaire (optional — drives the Behavioural & Future-Risk pillars)"
      />
    </RequireRole>
  );
}
