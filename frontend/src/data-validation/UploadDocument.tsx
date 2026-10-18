import { useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  CheckCircleIcon,
  DocumentArrowUpIcon,
} from "@heroicons/react/24/outline";
import SidebarLayout from "../components/SidebarLayout";
import Breadcrumbs from "../components/Breadcrumbs";
import { useBusiness } from "../context/BusinessContext";
import { ApiError } from "../services/apiClient";
import {
  processUploadStream,
  type ValidationResultEvent,
} from "../services/salesSubmissions";
import type {
  InputMethod,
  ProcessingSummary,
  ReportPeriodType,
} from "../services/types";

function detectInputMethod(files: File[]): InputMethod {
  const allImages = files.every(
    (f) => f.type.startsWith("image/") || /\.(jpe?g|png|webp)$/i.test(f.name),
  );
  return allImages ? "photo" : "spreadsheet";
}

function firstDayOfCurrentMonth(): string {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-01`;
}

function today(): string {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`;
}

interface StreamOutcome {
  submissionId: number;
  summary: ProcessingSummary;
}

export default function UploadDocument() {
  const navigate = useNavigate();
  const { activeBusiness, branches } = useBusiness();
  const [dragActive, setDragActive] = useState(false);
  const [files, setFiles] = useState<File[]>([]);
  const [branchId, setBranchId] = useState<string>("");
  const [periodType, setPeriodType] = useState<ReportPeriodType>("monthly");
  const [coverageStart, setCoverageStart] = useState(firstDayOfCurrentMonth());
  const [coverageEnd, setCoverageEnd] = useState(today());
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<StreamOutcome | null>(null);
  const [progress, setProgress] = useState<string[]>([]);
  const [stats, setStats] = useState<ValidationResultEvent | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const addFiles = (incoming: FileList | null) => {
    if (!incoming) return;
    setFiles((prev) => [...prev, ...Array.from(incoming)]);
    setResult(null);
  };

  const removeFile = (index: number) => {
    setFiles((prev) => prev.filter((_, i) => i !== index));
  };

  const handleDrag = (event: React.DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    event.stopPropagation();
    if (event.type === "dragenter" || event.type === "dragover") {
      setDragActive(true);
    } else if (event.type === "dragleave") {
      setDragActive(false);
    }
  };

  const handleDrop = (event: React.DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    event.stopPropagation();
    setDragActive(false);
    addFiles(event.dataTransfer.files);
  };

  const handleSubmit = async () => {
    if (!activeBusiness || files.length === 0) return;
    setSubmitting(true);
    setError(null);
    setResult(null);
    setProgress([`Uploading ${files.length} file(s)...`]);
    setStats(null);
    let failed = false;
    try {
      await processUploadStream(
        activeBusiness.id,
        {
          files,
          inputMethod: detectInputMethod(files),
          reportPeriodType: periodType,
          coverageStart,
          coverageEnd,
          branchId: branchId ? Number(branchId) : null,
        },
        (event) => {
          if (event.event === "report_status") {
            if (event.message) {
              setProgress((prev) => [...prev, event.message as string]);
            }
          } else if (event.event === "validation_result") {
            setStats(event);
          } else if (event.event === "report_complete") {
            setResult({
              submissionId: event.submission_id,
              summary: event.summary,
            });
          } else if (event.event === "report_error") {
            failed = true;
            setError(event.message);
          }
        },
        {
          onProgress: (job) => {
            const message = job.progress?.message ?? job.status;
            setProgress((prev) => prev[prev.length - 1] === message ? prev : [...prev, message]);
          },
        },
      );
      if (!failed) {
        setFiles([]);
      }
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : "Upload failed. Please try again.",
      );
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <SidebarLayout>
      <Breadcrumbs
        items={[
          { label: "Data Validation", to: "/data-validation" },
          { label: "Upload Document" },
        ]}
      />
      <div className="mt-2 flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-blue-950">Upload Document</h2>
          <p className="mt-1 text-slate-600">
            Upload a spreadsheet or photos for AI extraction and staging.
          </p>
        </div>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => navigate("/data-validation/manual")}
            className="rounded-lg bg-slate-100 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-200"
          >
            Manual Entry
          </button>
          <button
            type="button"
            onClick={() => navigate("/data-validation")}
            className="rounded-lg bg-slate-100 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-200"
          >
            Back to Submissions
          </button>
        </div>
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-3">
        <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm lg:col-span-2">
          <div
            onDragEnter={handleDrag}
            onDragOver={handleDrag}
            onDragLeave={handleDrag}
            onDrop={handleDrop}
            onClick={() => inputRef.current?.click()}
            className={`cursor-pointer rounded-xl border-2 border-dashed p-10 text-center transition-colors ${
              dragActive
                ? "border-blue-500 bg-blue-50"
                : "border-slate-300 bg-slate-50 hover:border-blue-400 hover:bg-blue-50/50"
            }`}
          >
            <DocumentArrowUpIcon className="mx-auto h-10 w-10 text-slate-400" />
            <p className="mt-3 font-medium text-slate-700">
              Click or drag & drop files here
            </p>
            <p className="mt-1 text-sm text-slate-500">
              Spreadsheets (.xlsx, .xls, .csv) or photos (.jpg, .png, .webp)
            </p>
            <input
              ref={inputRef}
              type="file"
              multiple
              accept=".xlsx,.xls,.csv,.pdf,.png,.jpg,.jpeg,.webp"
              onChange={(e) => addFiles(e.target.files)}
              className="hidden"
            />
          </div>

          {files.length > 0 && (
            <ul className="mt-4 divide-y divide-slate-100 rounded-lg border border-slate-200">
              {files.map((file, index) => (
                <li
                  key={`${file.name}-${index}`}
                  className="flex items-center justify-between px-4 py-2 text-sm"
                >
                  <span className="text-slate-700">{file.name}</span>
                  <button
                    type="button"
                    onClick={() => removeFile(index)}
                    className="text-rose-600 hover:text-rose-700"
                  >
                    Remove
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>

        <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
          <h3 className="text-sm font-semibold text-blue-950">
            Submission details
          </h3>
          <div className="mt-4 space-y-4">
            <label className="block text-sm">
              <span className="font-medium text-slate-700">Branch</span>
              <select
                value={branchId}
                onChange={(e) => setBranchId(e.target.value)}
                className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
              >
                <option value="">All / detect from file</option>
                {branches.map((branch) => (
                  <option key={branch.id} value={branch.id}>
                    {branch.name}
                  </option>
                ))}
              </select>
            </label>
            <label className="block text-sm">
              <span className="font-medium text-slate-700">Period type</span>
              <select
                value={periodType}
                onChange={(e) =>
                  setPeriodType(e.target.value as ReportPeriodType)
                }
                className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
              >
                <option value="daily">Daily</option>
                <option value="weekly">Weekly</option>
                <option value="monthly">Monthly</option>
                <option value="custom_range">Custom range</option>
              </select>
            </label>
            <label className="block text-sm">
              <span className="font-medium text-slate-700">Coverage start</span>
              <input
                type="date"
                value={coverageStart}
                onChange={(e) => setCoverageStart(e.target.value)}
                className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
              />
            </label>
            <label className="block text-sm">
              <span className="font-medium text-slate-700">Coverage end</span>
              <input
                type="date"
                value={coverageEnd}
                onChange={(e) => setCoverageEnd(e.target.value)}
                className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
              />
            </label>
            <button
              type="button"
              onClick={handleSubmit}
              disabled={submitting || files.length === 0 || !activeBusiness}
              className="w-full rounded-lg bg-blue-950 px-4 py-2 text-sm font-medium text-white hover:bg-blue-900 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {submitting ? "Processing…" : "Upload & Process"}
            </button>
            {error && (
              <p className="rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700">
                {error}
              </p>
            )}
          </div>
        </div>
      </div>

      {progress.length > 0 && !result && (
        <div className="mt-8 rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
          <h3 className="text-sm font-semibold text-blue-950">
            Processing progress
          </h3>
          <ul className="mt-3 space-y-2">
            {progress.map((step, index) => {
              const isLast = index === progress.length - 1;
              return (
                <li key={index} className="flex items-center gap-2 text-sm">
                  {isLast && submitting ? (
                    <span className="h-4 w-4 animate-spin rounded-full border-2 border-blue-300 border-t-blue-700" />
                  ) : (
                    <CheckCircleIcon className="h-4 w-4 text-emerald-600" />
                  )}
                  <span
                    className={
                      isLast && submitting ? "text-blue-900 font-medium" : "text-slate-600"
                    }
                  >
                    {step}
                  </span>
                </li>
              );
            })}
          </ul>
          {stats && (
            <p className="mt-3 text-sm text-slate-600">
              Validated {stats.total} row(s): {stats.ready} ready,{" "}
              {stats.pending_review} pending review, {stats.needs_correction}{" "}
              needs correction{stats.errors > 0 && `, ${stats.errors} error(s)`}.
            </p>
          )}
        </div>
      )}

      {result && (
        <div className="mt-8 rounded-xl border border-emerald-200 bg-emerald-50 p-6">
          <h3 className="text-lg font-semibold text-emerald-900">
            Submission #{result.submissionId} processed
          </h3>
          <dl className="mt-3 grid grid-cols-2 gap-x-6 gap-y-1 text-sm text-emerald-900 sm:grid-cols-4">
            <div>
              <dt className="font-medium">Total rows</dt>
              <dd>{result.summary.total_rows}</dd>
            </div>
            <div>
              <dt className="font-medium">Ready</dt>
              <dd>{result.summary.ready_rows}</dd>
            </div>
            <div>
              <dt className="font-medium">Pending review</dt>
              <dd>{result.summary.pending_review_rows}</dd>
            </div>
            <div>
              <dt className="font-medium">Issues</dt>
              <dd>{result.summary.issue_count}</dd>
            </div>
          </dl>
          {result.summary.auto_created_products.length > 0 && (
            <p className="mt-3 text-sm text-amber-800">
              Draft products created:{" "}
              {result.summary.auto_created_products
                .map((p) => p.name)
                .join(", ")}{" "}
              — activate them in Inventory before confirming.
            </p>
          )}
          {result.summary.auto_created_branches.length > 0 && (
            <p className="mt-1 text-sm text-amber-800">
              Draft branches created:{" "}
              {result.summary.auto_created_branches
                .map((b) => b.name)
                .join(", ")}
            </p>
          )}
          <button
            type="button"
            onClick={() =>
              navigate(`/data-validation?submission=${result.submissionId}`)
            }
            className="mt-4 rounded-lg bg-blue-950 px-4 py-2 text-sm font-medium text-white hover:bg-blue-900"
          >
            Review in Data Validation
          </button>
        </div>
      )}
    </SidebarLayout>
  );
}
