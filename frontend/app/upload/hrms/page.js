"use client";

import RequireRole from "../../lib/RequireRole";
import Header from "../../lib/Header";
import UploadWorkspace from "../../lib/UploadWorkspace";

// HRMS claims dataset — uploaded by HR. One row per claim.
const REQUIRED_COLUMNS = [
  "company_id",
  "employee_id",
  "department",
  "work_location",
  "band",
  "gender",
  "age",
  "claim_id",
  "claim_date",
  "insurance_claim_opd_inr",
  "insurance_claim_ipd_inr",
  "absenteeism_percent_per_month",
];

export default function HRMSUploadPage() {
  return (
    <RequireRole role="hr">
      <Header />
      <UploadWorkspace
        title="HRMS Claims Upload"
        description="Upload your HRMS claims export (one row per claim). Identifiers are stripped and IDs tokenised before any analysis."
        companyKey="companyID"
        requiredColumns={REQUIRED_COLUMNS}
      />
    </RequireRole>
  );
}
