import { useCallback, useEffect, useState } from "react";
import SidebarLayout from "../components/SidebarLayout";
import Toast, { type ToastType } from "../components/Toast";
import { useBusiness } from "../context/BusinessContext";
import { ApiError } from "../services/apiClient";
import {
  downloadArtifact,
  generateReport,
  listArtifacts,
} from "../services/artifacts";
import {
  generate,
  listActions,
  updateStatus,
} from "../services/businessActions";
import type { Artifact, BusinessAction } from "../services/types";

const URGENCY_OPTIONS = [
  { value: "", label: "All urgencies" },
  { value: "critical", label: "Critical" },
  { value: "high", label: "High" },
  { value: "medium", label: "Medium" },
  { value: "low", label: "Low" },
];

const STATUS_OPTIONS = [
  { value: "", label: "All statuses" },
  { value: "open", label: "Open" },
  { value: "in_progress", label: "In progress" },
  { value: "implemented", label: "Implemented" },
  { value: "dismissed", label: "Dismissed" },
];

function urgencyBadge(urgency: string) {
  switch (urgency) {
    case "critical":
      return "bg-red-100 text-red-800";
    case "high":
      return "bg-orange-100 text-orange-800";
    case "medium":
      return "bg-amber-100 text-amber-800";
    case "low":
      return "bg-slate-200 text-slate-600";
    default:
      return "bg-slate-200 text-slate-600";
  }
}

function statusBadge(status: string) {
  switch (status) {
    case "implemented":
      return "bg-emerald-100 text-emerald-800";
    case "in_progress":
      return "bg-blue-100 text-blue-800";
    case "dismissed":
      return "bg-slate-200 text-slate-600";
    case "ready":
      return "bg-emerald-100 text-emerald-800";
    case "failed":
      return "bg-red-100 text-red-800";
    case "pending":
    case "generating":
      return "bg-amber-100 text-amber-800";
    default:
      return "bg-slate-200 text-slate-600";
  }
}

function formatDateTime(value: string) {
  return new Date(value).toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function formatFileSize(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export default function Overview() {
  const { activeBusiness } = useBusiness();
  const [actions, setActions] = useState<BusinessAction[]>([]);
  const [artifacts, setArtifacts] = useState<Artifact[]>([]);
  const [urgencyFilter, setUrgencyFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [generating, setGenerating] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [toast, setToast] = useState<{
    message: string;
    type: ToastType;
    isOpen: boolean;
  }>({ message: "", type: "success", isOpen: false });

  const showToast = (message: string, type: ToastType = "success") => {
    setToast({ message, type, isOpen: true });
  };

  const closeToast = () => {
    setToast((prev) => ({ ...prev, isOpen: false }));
  };

  const fetchActions = useCallback(async () => {
    if (!activeBusiness) return;
    try {
      const list = await listActions(activeBusiness.id, {
        urgency: urgencyFilter || undefined,
        status: statusFilter || undefined,
        pageSize: 50,
      });
      setActions(list);
    } catch (err) {
      showToast(
        err instanceof ApiError ? err.message : "Failed to load recommendations",
        "error",
      );
    }
  }, [activeBusiness, urgencyFilter, statusFilter]);

  const fetchArtifacts = useCallback(async () => {
    if (!activeBusiness) return;
    try {
      const result = await listArtifacts(activeBusiness.id, { perPage: 10 });
      setArtifacts(result.artifacts);
    } catch {
      setArtifacts([]);
    }
  }, [activeBusiness]);

  useEffect(() => {
    queueMicrotask(() => {
      void fetchActions();
      void fetchArtifacts();
    });
  }, [fetchActions, fetchArtifacts]);

  const handleGenerate = async () => {
    if (!activeBusiness) return;
    setGenerating(true);
    try {
      const result = await generate(activeBusiness.id, { lookback_days: 30 });
      showToast(
        result.generated_count > 0
          ? `Generated ${result.generated_count} recommendations`
          : "No new recommendations found",
      );
      void fetchActions();
    } catch (err) {
      showToast(
        err instanceof ApiError
          ? err.message
          : "Failed to generate recommendations",
        "error",
      );
    } finally {
      setGenerating(false);
    }
  };

  const handleStatusUpdate = async (
    action: BusinessAction,
    status: "in_progress" | "implemented" | "dismissed",
  ) => {
    if (!activeBusiness) return;
    let dismissedReason: string | undefined;
    if (status === "dismissed") {
      const reason = window.prompt(
        "Reason for dismissing this recommendation (optional):",
      );
      if (reason === null) return;
      dismissedReason = reason || undefined;
    }
    try {
      await updateStatus(activeBusiness.id, action.id, status, dismissedReason);
      showToast(`Marked as ${status.replace("_", " ")}`);
      void fetchActions();
    } catch (err) {
      showToast(
        err instanceof ApiError ? err.message : "Failed to update status",
        "error",
      );
    }
  };

  const handleExport = async () => {
    if (!activeBusiness) return;
    setExporting(true);
    try {
      await generateReport(activeBusiness.id, {
        report_type: "action_center_summary",
        file_format: "xlsx",
      });
      showToast("Report generated");
      void fetchArtifacts();
    } catch (err) {
      showToast(
        err instanceof ApiError ? err.message : "Failed to generate report",
        "error",
      );
    } finally {
      setExporting(false);
    }
  };

  const handleDownload = async (artifact: Artifact) => {
    if (!activeBusiness) return;
    try {
      await downloadArtifact(activeBusiness.id, artifact.id);
    } catch (err) {
      showToast(
        err instanceof ApiError ? err.message : "Failed to download artifact",
        "error",
      );
    }
  };

  return (
    <SidebarLayout>
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold text-blue-950">Overview</h2>
          <p className="mt-1 text-slate-600">
            AI recommendations and reports for your business.
          </p>
        </div>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={handleExport}
            disabled={exporting}
            className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 transition-colors hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {exporting ? "Exporting…" : "Export report"}
          </button>
          <button
            type="button"
            onClick={handleGenerate}
            disabled={generating}
            className="rounded-lg bg-blue-700 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-blue-800 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {generating ? "Generating…" : "Generate recommendations"}
          </button>
        </div>
      </div>

      <div className="mt-6 rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h3 className="text-lg font-semibold text-blue-950">
            Recommendations
          </h3>
          <div className="flex gap-2">
            <select
              value={urgencyFilter}
              onChange={(e) => setUrgencyFilter(e.target.value)}
              className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm focus:border-blue-500 focus:outline-none"
            >
              {URGENCY_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm focus:border-blue-500 focus:outline-none"
            >
              {STATUS_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
          </div>
        </div>

        {actions.length === 0 ? (
          <p className="mt-4 text-sm text-slate-500">
            No recommendations yet. Click "Generate recommendations" to analyze
            your data.
          </p>
        ) : (
          <ul className="mt-4 space-y-3">
            {actions.map((action) => (
              <li
                key={action.id}
                className="rounded-lg border border-slate-200 p-4"
              >
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="font-medium text-blue-950">{action.title}</p>
                      <span
                        className={`rounded-full px-2 py-0.5 text-xs font-medium ${urgencyBadge(action.urgency)}`}
                      >
                        {action.urgency}
                      </span>
                      <span
                        className={`rounded-full px-2 py-0.5 text-xs font-medium ${statusBadge(action.status)}`}
                      >
                        {action.status.replace("_", " ")}
                      </span>
                    </div>
                    <p className="mt-1 text-sm text-slate-600">
                      {action.rationale}
                    </p>
                    <p className="mt-1 text-xs text-slate-500">
                      {action.category.replace("_", " ")} · Expected impact:{" "}
                      {action.expected_impact} ·{" "}
                      {formatDateTime(action.created_at)}
                    </p>
                  </div>
                  {(action.status === "open" ||
                    action.status === "in_progress") && (
                    <div className="flex flex-none gap-2">
                      {action.status === "open" && (
                        <button
                          type="button"
                          onClick={() =>
                            handleStatusUpdate(action, "in_progress")
                          }
                          className="rounded-lg border border-slate-300 px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50"
                        >
                          Start
                        </button>
                      )}
                      <button
                        type="button"
                        onClick={() =>
                          handleStatusUpdate(action, "implemented")
                        }
                        className="rounded-lg bg-emerald-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-emerald-700"
                      >
                        Mark implemented
                      </button>
                      <button
                        type="button"
                        onClick={() => handleStatusUpdate(action, "dismissed")}
                        className="rounded-lg border border-slate-300 px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50"
                      >
                        Dismiss
                      </button>
                    </div>
                  )}
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="mt-6 rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
        <h3 className="text-lg font-semibold text-blue-950">
          Reports &amp; artifacts
        </h3>
        {artifacts.length === 0 ? (
          <p className="mt-3 text-sm text-slate-500">
            No artifacts yet. Use "Export report" to generate one.
          </p>
        ) : (
          <ul className="mt-3 divide-y divide-slate-100">
            {artifacts.map((artifact) => (
              <li
                key={artifact.id}
                className="flex items-center justify-between gap-4 py-3"
              >
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium text-blue-950">
                    {artifact.title}
                  </p>
                  <p className="text-xs text-slate-500">
                    {artifact.artifact_type}
                    {artifact.file_format
                      ? ` · ${artifact.file_format.toUpperCase()}`
                      : ""}{" "}
                    · {formatFileSize(artifact.file_size_bytes)} ·{" "}
                    {formatDateTime(artifact.created_at)}
                  </p>
                </div>
                <div className="flex flex-none items-center gap-2">
                  <span
                    className={`rounded-full px-2 py-0.5 text-xs font-medium ${statusBadge(artifact.status)}`}
                  >
                    {artifact.status}
                  </span>
                  {artifact.status === "ready" && (
                    <button
                      type="button"
                      onClick={() => handleDownload(artifact)}
                      className="rounded-lg border border-slate-300 px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50"
                    >
                      Download
                    </button>
                  )}
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>

      <Toast
        message={toast.message}
        type={toast.type}
        isOpen={toast.isOpen}
        onClose={closeToast}
      />
    </SidebarLayout>
  );
}
