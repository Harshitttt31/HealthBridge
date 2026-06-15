"use client";

import { useRef, useState } from "react";

import { useAuth } from "./auth-context";
import { uploadFile } from "./api";

// A drag-drop upload panel that POSTs to the real backend.
// The client header peek (CSV only) is a best-effort hint; the backend performs
// the authoritative validation, isolation, and de-identification on upload.
//
// props:
//   kind                — "ahc" | "hrms" (which backend endpoint to hit)
//   title, description  — page copy
//   accept              — file input accept string
//   requiredColumns     — string[] the dataset must contain (for validation hints)
//   companyKey          — the source column that maps to company_id (CUG | companyID)
export default function UploadWorkspace({
  kind,
  title,
  description,
  accept = ".csv,.xlsx",
  requiredColumns = [],
  optionalColumns = [],
  optionalLabel = "Optional columns",
  companyKey,
}) {
  const { auth } = useAuth();
  const inputRef = useRef(null);
  const [file, setFile] = useState(null);
  const [dragging, setDragging] = useState(false);
  const [header, setHeader] = useState(null); // parsed column names (CSV only, best-effort)
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState(null); // backend success payload
  const [validation, setValidation] = useState(null); // backend 422 detail

  function pickFile(f) {
    setError("");
    setHeader(null);
    setResult(null);
    setValidation(null);
    if (!f) return;
    const ok = /\.(csv|xlsx)$/i.test(f.name);
    if (!ok) {
      setError("Unsupported file type. Upload a .csv or .xlsx file.");
      return;
    }
    setFile(f);
    // Best-effort header peek for CSV so the user gets instant schema feedback.
    if (/\.csv$/i.test(f.name)) {
      const reader = new FileReader();
      reader.onload = () => {
        const firstLine = String(reader.result).split(/\r?\n/)[0] || "";
        const cols = firstLine.split(",").map((c) => c.trim().replace(/^"|"$/g, ""));
        setHeader(cols);
      };
      reader.readAsText(f.slice(0, 64 * 1024)); // first 64KB is plenty for the header
    }
  }

  function onDrop(e) {
    e.preventDefault();
    setDragging(false);
    pickFile(e.dataTransfer.files?.[0]);
  }

  async function handleUpload() {
    if (!file || !auth?.token) return;
    setError("");
    setResult(null);
    setValidation(null);
    setSubmitting(true);
    try {
      const payload = await uploadFile(kind, file, auth.token);
      setResult(payload);
    } catch (err) {
      // Schema failures arrive as a structured 422 detail; everything else is
      // a plain message (bad file, no rows for this company, auth, network).
      if (err.detail && typeof err.detail === "object") {
        setValidation(err.detail);
      }
      setError(err.message || "Upload failed");
    } finally {
      setSubmitting(false);
    }
  }

  // The company key arrives under any of these aliases; the backend reconciles
  // them all to company_id. The real AHC/HRMS files use CUG.
  const COMPANY_KEY_ALIASES = ["company_id", "CUG", "companyID", companyKey];
  const headerHasCompanyKey =
    header && COMPANY_KEY_ALIASES.some((a) => a && header.includes(a));

  // Validation status per required column (only meaningful when we parsed a header).
  const columnStatus =
    header &&
    requiredColumns.map((col) => ({
      col,
      present:
        header.includes(col) ||
        (col === "company_id" && headerHasCompanyKey),
    }));

  const hasCompanyKey = header ? headerHasCompanyKey : null;

  // Optional columns are non-blocking: present them as a separate, informational
  // checklist so the uploader can see what enrichment (e.g. HRA) was detected.
  const optionalStatus =
    header && optionalColumns.length
      ? optionalColumns.map((col) => ({ col, present: header.includes(col) }))
      : null;
  const optionalDetected = optionalStatus?.some((c) => c.present);

  return (
    <div className="mx-auto max-w-3xl px-4 py-10">
      <h1 className="text-xl font-semibold text-ink-900">{title}</h1>
      <p className="mt-1 text-sm text-slate-500">{description}</p>

      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        onClick={() => inputRef.current?.click()}
        className={`mt-6 cursor-pointer rounded-2xl border-2 border-dashed p-10 text-center transition-colors ${
          dragging
            ? "border-brand-500 bg-brand-50"
            : "border-slate-300 bg-white/60 hover:border-brand-400"
        }`}
      >
        <input
          ref={inputRef}
          type="file"
          accept={accept}
          className="hidden"
          onChange={(e) => pickFile(e.target.files?.[0])}
        />
        <p className="text-sm font-medium text-slate-700">
          {file ? file.name : "Drag & drop a CSV / XLSX file here"}
        </p>
        <p className="mt-1 text-xs text-slate-400">
          {file
            ? `${(file.size / 1024).toFixed(1)} KB — click to choose another`
            : "or click to browse"}
        </p>
      </div>

      {error && (
        <p className="mt-3 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">
          {error}
        </p>
      )}

      {columnStatus && (
        <div className="card mt-6 p-4">
          <p className="mb-3 text-sm font-medium text-slate-700">
            Schema validation
          </p>
          {companyKey && (
            <p className="mb-3 text-xs text-gray-500">
              Company key <code className="font-mono">{companyKey}</code> →{" "}
              <code className="font-mono">company_id</code>:{" "}
              {hasCompanyKey ? (
                <span className="text-green-700">found</span>
              ) : (
                <span className="text-red-700">missing</span>
              )}
            </p>
          )}
          <ul className="grid grid-cols-2 gap-x-6 gap-y-1 text-sm">
            {columnStatus.map(({ col, present }) => (
              <li key={col} className="flex items-center gap-2">
                <span className={present ? "text-green-600" : "text-red-500"}>
                  {present ? "✓" : "✗"}
                </span>
                <span className="font-mono text-xs text-gray-600">{col}</span>
              </li>
            ))}
          </ul>
          {optionalStatus && (
            <div className="mt-4 border-t border-slate-100 pt-3">
              <p className="mb-2 text-xs font-medium text-slate-600">
                {optionalLabel}{" "}
                {optionalDetected ? (
                  <span className="text-green-700">— detected</span>
                ) : (
                  <span className="text-slate-400">— not detected (LABS-ONLY)</span>
                )}
              </p>
              <ul className="grid grid-cols-2 gap-x-6 gap-y-1 text-sm">
                {optionalStatus.map(({ col, present }) => (
                  <li key={col} className="flex items-center gap-2">
                    <span className={present ? "text-green-600" : "text-slate-300"}>
                      {present ? "✓" : "○"}
                    </span>
                    <span className="font-mono text-xs text-gray-600">{col}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
          <p className="mt-3 text-xs text-gray-400">
            Header preview is best-effort (CSV only). The backend performs the
            authoritative validation on upload.
          </p>
        </div>
      )}

      <button
        type="button"
        disabled={!file || submitting}
        onClick={handleUpload}
        className="btn-primary mt-6"
      >
        {submitting ? "Uploading…" : "Upload & validate"}
      </button>

      {/* Backend validation failure (422): show the authoritative detail. */}
      {validation && (
        <div className="card mt-6 border-red-200 bg-red-50/60 p-4">
          <p className="mb-2 text-sm font-medium text-red-800">
            The backend rejected this file
          </p>
          {validation.missing_required?.length > 0 && (
            <p className="text-sm text-red-700">
              Missing required column(s):{" "}
              <span className="font-mono text-xs">
                {validation.missing_required.join(", ")}
              </span>
            </p>
          )}
          {validation.company_ids?.length > 0 && (
            <p className="mt-1 text-xs text-red-700">
              Companies found in file: {validation.company_ids.join(", ")}
            </p>
          )}
          {validation.message && (
            <p className="mt-2 text-xs text-red-600">{validation.message}</p>
          )}
        </div>
      )}

      {/* Plain (non-validation) error: bad file type, no rows, auth, network. */}
      {error && !validation && (
        <p className="mt-6 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">
          {error}
        </p>
      )}

      {/* Success: rows stored, isolation drops, and any soft warnings. */}
      {result && (
        <div className="card mt-6 border-green-200 bg-green-50/60 p-4">
          <p className="mb-2 text-sm font-medium text-green-800">
            Upload accepted — {result.rows_stored.toLocaleString()} row(s) stored
            for {result.company_id}
          </p>
          {result.rows_dropped_other_company > 0 && (
            <p className="text-xs text-slate-600">
              {result.rows_dropped_other_company.toLocaleString()} row(s) for other
              companies were dropped (isolation).
            </p>
          )}
          {result.hra_rows_stored > 0 && (
            <p className="text-xs text-slate-600">
              {result.hra_rows_stored.toLocaleString()} consented HRA questionnaire
              row(s) stored to the engine-only store.
            </p>
          )}
          {result.warnings?.length > 0 && (
            <ul className="mt-2 list-disc space-y-0.5 pl-5 text-xs text-amber-700">
              {result.warnings.map((w, i) => (
                <li key={i}>{w}</li>
              ))}
            </ul>
          )}
          <p className="mt-3 text-xs text-slate-500">
            Identifiers were stripped and IDs tokenised before storage. Once both
            AHC and HRMS are uploaded, run processing to build the Group Health
            Index.
          </p>
        </div>
      )}
    </div>
  );
}
