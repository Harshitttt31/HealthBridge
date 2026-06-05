"use client";

import { useRef, useState } from "react";

// A drag-drop upload panel with client-side schema feedback.
// In Phase A this only inspects the file locally (name, size, header row).
// Later, `onUpload` will POST the file to the real backend endpoint.
//
// props:
//   title, description  — page copy
//   accept              — file input accept string
//   requiredColumns     — string[] the dataset must contain (for validation hints)
//   companyKey          — the source column that maps to company_id (CUG | companyID)
export default function UploadWorkspace({
  title,
  description,
  accept = ".csv,.xlsx",
  requiredColumns = [],
  companyKey,
}) {
  const inputRef = useRef(null);
  const [file, setFile] = useState(null);
  const [dragging, setDragging] = useState(false);
  const [header, setHeader] = useState(null); // parsed column names (CSV only, best-effort)
  const [error, setError] = useState("");

  function pickFile(f) {
    setError("");
    setHeader(null);
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

  // Validation status per required column (only meaningful when we parsed a header).
  const columnStatus =
    header &&
    requiredColumns.map((col) => ({
      col,
      present:
        header.includes(col) ||
        (companyKey && col === "company_id" && header.includes(companyKey)),
    }));

  const hasCompanyKey =
    header && companyKey ? header.includes(companyKey) : null;

  return (
    <div className="mx-auto max-w-3xl px-4 py-10">
      <h1 className="text-xl font-semibold">{title}</h1>
      <p className="mt-1 text-sm text-gray-500">{description}</p>

      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        onClick={() => inputRef.current?.click()}
        className={`mt-6 cursor-pointer rounded-xl border-2 border-dashed p-10 text-center transition-colors ${
          dragging
            ? "border-gray-900 bg-gray-50"
            : "border-gray-300 hover:border-gray-400"
        }`}
      >
        <input
          ref={inputRef}
          type="file"
          accept={accept}
          className="hidden"
          onChange={(e) => pickFile(e.target.files?.[0])}
        />
        <p className="text-sm font-medium text-gray-700">
          {file ? file.name : "Drag & drop a CSV / XLSX file here"}
        </p>
        <p className="mt-1 text-xs text-gray-400">
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
        <div className="mt-6 rounded-xl border border-gray-200 bg-white p-4">
          <p className="mb-3 text-sm font-medium text-gray-700">
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
          <p className="mt-3 text-xs text-gray-400">
            Header preview is best-effort (CSV only). The backend performs the
            authoritative validation on upload.
          </p>
        </div>
      )}

      <button
        type="button"
        disabled={!file}
        // TODO: POST to /upload/{ahc|hrms}, then enable /process.
        onClick={() => alert("Upload wiring comes in Phase B (backend).")}
        className="mt-6 rounded-lg bg-gray-900 px-4 py-2 text-sm font-medium text-white hover:bg-gray-800 disabled:opacity-50"
      >
        Upload &amp; validate
      </button>
    </div>
  );
}
