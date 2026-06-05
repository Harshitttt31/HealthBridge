"use client";

import RequireRole from "../../lib/RequireRole";
import Header from "../../lib/Header";
import UploadWorkspace from "../../lib/UploadWorkspace";

// AHC health-check dataset — uploaded by Employer. One row per employee.
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

export default function AHCUploadPage() {
  return (
    <RequireRole role="provider">
      <Header />
      <UploadWorkspace
        title="AHC Health-Check Upload"
        description="Provider workspace. Upload the annual health-check export (one row per employee). Identifiers are stripped and IDs tokenised before any analysis."
        companyKey="CUG"
        requiredColumns={REQUIRED_COLUMNS}
      />
    </RequireRole>
  );
}
