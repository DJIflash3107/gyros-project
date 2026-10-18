import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { ArrowUpTrayIcon } from "@heroicons/react/24/outline";
import SidebarLayout from "../components/SidebarLayout";
import { useBusiness } from "../context/BusinessContext";
import { ApiError } from "../services/apiClient";
import {
  confirmSubmission,
  getSubmission,
  listSubmissions,
} from "../services/salesSubmissions";
import { listIssues, updateIssue } from "../services/importIssues";
import {
  bulkUpdateStagingRows,
  listStagingRows,
  updateStagingRow,
  type StagingRowUpdateInput,
} from "../services/stagingRows";
import type {
  ImportIssue,
  ReviewStatus,
  SalesReportSubmission,
  StagingRow,
} from "../services/types";

const REVIEW_STATUSES: ReviewStatus[] = [
  "pending_review",
  "needs_correction",
  "ready",
  "accepted",
  "rejected",
];

const EDITABLE_NUMBER_FIELDS = [
  "sold_qty",
  "prepared_qty",
  "leftover_qty",
  "spoiled_qty",
  "recorded_revenue",
] as const;

type NumberField = (typeof EDITABLE_NUMBER_FIELDS)[number];

interface RowDraft {
  raw_product_name: string;
  branch_id: string;
  period_start: string;
  period_end: string;
  sold_qty: string;
  prepared_qty: string;
  leftover_qty: string;
  spoiled_qty: string;
  recorded_revenue: string;
  review_status: ReviewStatus;
}

function toDraft(row: StagingRow): RowDraft {
  return {
    raw_product_name: row.raw_product_name ?? "",
    branch_id: row.branch_id != null ? String(row.branch_id) : "",
    period_start: row.period_start ?? "",
    period_end: row.period_end ?? "",
    sold_qty: row.sold_qty ?? "",
    prepared_qty: row.prepared_qty ?? "",
    leftover_qty: row.leftover_qty ?? "",
    spoiled_qty: row.spoiled_qty ?? "",
    recorded_revenue: row.recorded_revenue ?? "",
    review_status: row.review_status,
  };
}

function statusBadge(status: string): string {
  switch (status) {
    case "ready":
    case "accepted":
    case "confirmed":
      return "bg-emerald-100 text-emerald-700";
    case "pending_review":
    case "pending":
    case "processing":
      return "bg-amber-100 text-amber-700";
    case "needs_correction":
    case "rejected":
    case "failed":
      return "bg-rose-100 text-rose-700";
    default:
      return "bg-slate-100 text-slate-700";
  }
}

function formatDate(value: string): string {
  return new Date(value).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
  });
}

export default function DataValidation() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const { activeBusiness, branches } = useBusiness();

  const [submissions, setSubmissions] = useState<SalesReportSubmission[]>([]);
  const [submission, setSubmission] = useState<SalesReportSubmission | null>(
    null,
  );
  const [rows, setRows] = useState<StagingRow[]>([]);
  const [drafts, setDrafts] = useState<Record<number, RowDraft>>({});
  const [dirty, setDirty] = useState<Set<number>>(new Set());
  const [issues, setIssues] = useState<ImportIssue[]>([]);
  const [loadingList, setLoadingList] = useState(true);
  const [loadingDetail, setLoadingDetail] = useState(() =>
    Boolean(searchParams.get("submission")),
  );
  const [saving, setSaving] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [pageError, setPageError] = useState<string | null>(null);
  const [confirmError, setConfirmError] = useState<string | null>(null);

  const selectedId = Number(searchParams.get("submission")) || null;

  // Effects only trigger async fetches; all setState happens after awaits
  // so no state is set synchronously inside an effect body.
  const fetchSubmissions = useCallback(async () => {
    if (!activeBusiness) return;
    try {
      const { submissions: list } = await listSubmissions(activeBusiness.id, {
        pageSize: 100,
      });
      setSubmissions(list);
      setPageError(null);
    } catch (err) {
      setPageError(
        err instanceof ApiError ? err.message : "Failed to load submissions",
      );
    } finally {
      setLoadingList(false);
    }
  }, [activeBusiness]);

  const fetchDetail = useCallback(
    async (submissionId: number) => {
      if (!activeBusiness) return;
      try {
        const [detail, rowPage, issuePage] = await Promise.all([
          getSubmission(activeBusiness.id, submissionId),
          listStagingRows(submissionId, { pageSize: 100 }),
          listIssues(submissionId, { pageSize: 100 }),
        ]);
        setSubmission(detail);
        setRows(rowPage.staging_rows);
        setDrafts(
          Object.fromEntries(
            rowPage.staging_rows.map((row) => [row.id, toDraft(row)]),
          ),
        );
        setDirty(new Set());
        setIssues(issuePage.issues);
        setPageError(null);
        setConfirmError(null);
      } catch (err) {
        setPageError(
          err instanceof ApiError
            ? err.message
            : "Failed to load submission detail",
        );
      } finally {
        setLoadingDetail(false);
      }
    },
    [activeBusiness],
  );

  useEffect(() => {
    // Defer so no setState runs synchronously inside the effect body.
    queueMicrotask(() => {
      void fetchSubmissions();
    });
  }, [fetchSubmissions]);

  useEffect(() => {
    if (!selectedId) return;
    // Defer so no setState runs synchronously inside the effect body.
    queueMicrotask(() => {
      void fetchDetail(selectedId);
    });
  }, [selectedId, fetchDetail]);

  const handleSelectSubmission = (submissionId: number) => {
    setLoadingDetail(true);
    setSearchParams({ submission: String(submissionId) });
  };

  const clearSelection = () => {
    setSubmission(null);
    setRows([]);
    setIssues([]);
    setConfirmError(null);
    setSearchParams({});
  };

  const updateDraft = (
    rowId: number,
    field: keyof RowDraft,
    value: string,
  ) => {
    setDrafts((prev) => ({
      ...prev,
      [rowId]: { ...prev[rowId], [field]: value },
    }));
    setDirty((prev) => new Set(prev).add(rowId));
  };

  const handleSave = async () => {
    if (!submission || dirty.size === 0) return;
    setSaving(true);
    setPageError(null);
    try {
      const requests = [...dirty].map((rowId) => {
        const draft = drafts[rowId];
        const input: StagingRowUpdateInput = {
          raw_product_name: draft.raw_product_name || null,
          branch_id: draft.branch_id ? Number(draft.branch_id) : null,
          period_start: draft.period_start || null,
          period_end: draft.period_end || null,
          review_status: draft.review_status,
        };
        for (const field of EDITABLE_NUMBER_FIELDS) {
          const raw = draft[field as NumberField].trim();
          input[field] = raw === "" ? null : Number(raw);
        }
        return updateStagingRow(submission.id, rowId, input);
      });
      const updatedRows = await Promise.all(requests);
      setRows((prev) =>
        prev.map((row) => updatedRows.find((u) => u.id === row.id) ?? row),
      );
      setDirty(new Set());
    } catch (err) {
      setPageError(
        err instanceof ApiError ? err.message : "Failed to save changes",
      );
    } finally {
      setSaving(false);
    }
  };

  const handleMarkAllReady = async () => {
    if (!submission) return;
    setSaving(true);
    setPageError(null);
    try {
      const result = await bulkUpdateStagingRows(submission.id, {
        apply_to_all: true,
        review_status: "ready",
      });
      setRows(result.staging_rows);
      setDrafts(
        Object.fromEntries(
          result.staging_rows.map((row) => [row.id, toDraft(row)]),
        ),
      );
      setDirty(new Set());
    } catch (err) {
      setPageError(
        err instanceof ApiError ? err.message : "Failed to mark rows ready",
      );
    } finally {
      setSaving(false);
    }
  };

  const handleResolveIssue = async (
    issueId: number,
    status: "resolved" | "ignored",
  ) => {
    if (!submission) return;
    try {
      const updated = await updateIssue(submission.id, issueId, {
        resolution_status: status,
      });
      setIssues((prev) =>
        prev.map((issue) => (issue.id === issueId ? updated : issue)),
      );
    } catch (err) {
      setPageError(
        err instanceof ApiError ? err.message : "Failed to update issue",
      );
    }
  };

  const handleConfirm = async () => {
    if (!activeBusiness || !submission) return;
    setConfirming(true);
    setConfirmError(null);
    try {
      await confirmSubmission(activeBusiness.id, submission.id);
      clearSelection();
      setLoadingList(true);
      await fetchSubmissions();
    } catch (err) {
      if (err instanceof ApiError) {
        const detail = Object.values(err.errors).join(" ");
        setConfirmError(detail ? `${err.message}: ${detail}` : err.message);
      } else {
        setConfirmError("Failed to confirm submission");
      }
    } finally {
      setConfirming(false);
    }
  };

  const openIssues = useMemo(
    () => issues.filter((issue) => issue.resolution_status === "open"),
    [issues],
  );

  const confirmable =
    submission != null && submission.status !== "confirmed";

  return (
    <SidebarLayout>
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-blue-950">Data Validation</h2>
          <p className="mt-1 text-slate-600">
            Review staged sales rows, resolve issues, and confirm submissions.
          </p>
        </div>
        <button
          type="button"
          onClick={() => navigate("/data-validation/upload")}
          className="inline-flex items-center gap-2 rounded-lg bg-blue-950 px-4 py-2 text-sm font-medium text-white hover:bg-blue-900"
        >
          <ArrowUpTrayIcon className="h-4 w-4" />
          Upload File
        </button>
      </div>

      {pageError && (
        <p className="mt-4 rounded-lg bg-rose-50 px-4 py-2 text-sm text-rose-700">
          {pageError}
        </p>
      )}

      <div className="mt-8">
        <h3 className="text-lg font-semibold text-blue-950">Submissions</h3>
        <div className="mt-4 overflow-x-auto rounded-xl border border-slate-200 bg-white shadow-sm">
          <table className="w-full min-w-[44rem] text-left text-sm">
            <thead className="bg-blue-950 text-white">
              <tr>
                <th className="px-6 py-3 font-medium">ID</th>
                <th className="px-6 py-3 font-medium">Source</th>
                <th className="px-6 py-3 font-medium">Coverage</th>
                <th className="px-6 py-3 font-medium">Status</th>
                <th className="px-6 py-3 font-medium">Rows</th>
                <th className="px-6 py-3 font-medium">Created</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {loadingList ? (
                <tr>
                  <td colSpan={6} className="px-6 py-6 text-center text-slate-500">
                    Loading submissions…
                  </td>
                </tr>
              ) : submissions.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-6 py-6 text-center text-slate-500">
                    No submissions yet. Upload a file to get started.
                  </td>
                </tr>
              ) : (
                submissions.map((item) => (
                  <tr
                    key={item.id}
                    onClick={() => handleSelectSubmission(item.id)}
                    className={`cursor-pointer hover:bg-slate-50 ${
                      selectedId === item.id ? "bg-blue-50" : ""
                    }`}
                  >
                    <td className="px-6 py-3 font-medium text-blue-900">
                      #{item.id}
                    </td>
                    <td className="px-6 py-3 text-slate-700">
                      {item.source_file_name ?? item.input_method}
                    </td>
                    <td className="px-6 py-3 text-slate-700">
                      {formatDate(item.coverage_start)} –{" "}
                      {formatDate(item.coverage_end)}
                    </td>
                    <td className="px-6 py-3">
                      <span
                        className={`inline-flex rounded-full px-2.5 py-0.5 text-xs font-medium ${statusBadge(item.status)}`}
                      >
                        {item.status}
                      </span>
                    </td>
                    <td className="px-6 py-3 text-slate-700">
                      {item.total_rows}
                    </td>
                    <td className="px-6 py-3 text-slate-700">
                      {formatDate(item.created_at)}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {selectedId && (
        <div className="mt-10">
          {loadingDetail ? (
            <p className="text-sm text-slate-500">Loading submission…</p>
          ) : submission ? (
            <>
              <div className="flex flex-wrap items-center justify-between gap-3">
                <h3 className="text-lg font-semibold text-blue-950">
                  Staging rows — submission #{submission.id}
                </h3>
                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={handleMarkAllReady}
                    disabled={saving || rows.length === 0}
                    className="rounded-lg bg-slate-100 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-200 disabled:opacity-50"
                  >
                    Mark all ready
                  </button>
                  <button
                    type="button"
                    onClick={handleSave}
                    disabled={saving || dirty.size === 0}
                    className="rounded-lg bg-blue-950 px-4 py-2 text-sm font-medium text-white hover:bg-blue-900 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    {saving
                      ? "Saving…"
                      : `Save changes${dirty.size > 0 ? ` (${dirty.size})` : ""}`}
                  </button>
                </div>
              </div>

              <div className="mt-4 overflow-x-auto rounded-xl border border-slate-200 bg-white shadow-sm">
                <table className="w-full min-w-[72rem] text-left text-sm">
                  <thead className="bg-slate-100 text-slate-700">
                    <tr>
                      <th className="px-3 py-2 font-medium">#</th>
                      <th className="px-3 py-2 font-medium">Product</th>
                      <th className="px-3 py-2 font-medium">Branch</th>
                      <th className="px-3 py-2 font-medium">Start</th>
                      <th className="px-3 py-2 font-medium">End</th>
                      <th className="px-3 py-2 font-medium">Sold</th>
                      <th className="px-3 py-2 font-medium">Prepared</th>
                      <th className="px-3 py-2 font-medium">Revenue</th>
                      <th className="px-3 py-2 font-medium">Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {rows.length === 0 ? (
                      <tr>
                        <td
                          colSpan={9}
                          className="px-6 py-6 text-center text-slate-500"
                        >
                          No staging rows for this submission.
                        </td>
                      </tr>
                    ) : (
                      rows.map((row) => {
                        const draft = drafts[row.id];
                        if (!draft) return null;
                        const isDirty = dirty.has(row.id);
                        return (
                          <tr
                            key={row.id}
                            className={isDirty ? "bg-amber-50" : ""}
                          >
                            <td className="px-3 py-2 text-slate-500">
                              {row.source_row_number ?? row.id}
                            </td>
                            <td className="px-3 py-2">
                              <input
                                value={draft.raw_product_name}
                                onChange={(e) =>
                                  updateDraft(
                                    row.id,
                                    "raw_product_name",
                                    e.target.value,
                                  )
                                }
                                className="w-40 rounded border border-slate-200 px-2 py-1 focus:border-blue-500 focus:outline-none"
                              />
                            </td>
                            <td className="px-3 py-2">
                              <select
                                value={draft.branch_id}
                                onChange={(e) =>
                                  updateDraft(
                                    row.id,
                                    "branch_id",
                                    e.target.value,
                                  )
                                }
                                className="rounded border border-slate-200 px-2 py-1 focus:border-blue-500 focus:outline-none"
                              >
                                <option value="">—</option>
                                {branches.map((branch) => (
                                  <option key={branch.id} value={branch.id}>
                                    {branch.name}
                                  </option>
                                ))}
                              </select>
                            </td>
                            <td className="px-3 py-2">
                              <input
                                type="date"
                                value={draft.period_start}
                                onChange={(e) =>
                                  updateDraft(
                                    row.id,
                                    "period_start",
                                    e.target.value,
                                  )
                                }
                                className="rounded border border-slate-200 px-2 py-1 focus:border-blue-500 focus:outline-none"
                              />
                            </td>
                            <td className="px-3 py-2">
                              <input
                                type="date"
                                value={draft.period_end}
                                onChange={(e) =>
                                  updateDraft(
                                    row.id,
                                    "period_end",
                                    e.target.value,
                                  )
                                }
                                className="rounded border border-slate-200 px-2 py-1 focus:border-blue-500 focus:outline-none"
                              />
                            </td>
                            <td className="px-3 py-2">
                              <input
                                type="number"
                                value={draft.sold_qty}
                                onChange={(e) =>
                                  updateDraft(
                                    row.id,
                                    "sold_qty",
                                    e.target.value,
                                  )
                                }
                                className="w-20 rounded border border-slate-200 px-2 py-1 focus:border-blue-500 focus:outline-none"
                              />
                            </td>
                            <td className="px-3 py-2">
                              <input
                                type="number"
                                value={draft.prepared_qty}
                                onChange={(e) =>
                                  updateDraft(
                                    row.id,
                                    "prepared_qty",
                                    e.target.value,
                                  )
                                }
                                className="w-20 rounded border border-slate-200 px-2 py-1 focus:border-blue-500 focus:outline-none"
                              />
                            </td>
                            <td className="px-3 py-2">
                              <input
                                type="number"
                                value={draft.recorded_revenue}
                                onChange={(e) =>
                                  updateDraft(
                                    row.id,
                                    "recorded_revenue",
                                    e.target.value,
                                  )
                                }
                                className="w-24 rounded border border-slate-200 px-2 py-1 focus:border-blue-500 focus:outline-none"
                              />
                            </td>
                            <td className="px-3 py-2">
                              <select
                                value={draft.review_status}
                                onChange={(e) =>
                                  updateDraft(
                                    row.id,
                                    "review_status",
                                    e.target.value,
                                  )
                                }
                                className={`rounded-full px-2 py-1 text-xs font-medium ${statusBadge(draft.review_status)}`}
                              >
                                {REVIEW_STATUSES.map((status) => (
                                  <option key={status} value={status}>
                                    {status}
                                  </option>
                                ))}
                              </select>
                            </td>
                          </tr>
                        );
                      })
                    )}
                  </tbody>
                </table>
              </div>

              {issues.length > 0 && (
                <div className="mt-8">
                  <h3 className="text-lg font-semibold text-blue-950">
                    Import issues ({openIssues.length} open)
                  </h3>
                  <ul className="mt-4 divide-y divide-slate-100 rounded-xl border border-slate-200 bg-white shadow-sm">
                    {issues.map((issue) => (
                      <li
                        key={issue.id}
                        className="flex flex-wrap items-center justify-between gap-3 px-6 py-3"
                      >
                        <div className="flex items-center gap-3">
                          <span
                            className={`inline-flex rounded-full px-2.5 py-0.5 text-xs font-medium ${
                              issue.severity === "error" ||
                              issue.severity === "critical"
                                ? "bg-rose-100 text-rose-700"
                                : issue.severity === "warning"
                                  ? "bg-amber-100 text-amber-700"
                                  : "bg-slate-100 text-slate-700"
                            }`}
                          >
                            {issue.severity}
                          </span>
                          <div>
                            <p className="text-sm text-slate-800">
                              {issue.message}
                            </p>
                            <p className="text-xs text-slate-500">
                              {issue.issue_code}
                              {issue.source_row_number != null &&
                                ` · row ${issue.source_row_number}`}
                              {issue.raw_value && ` · "${issue.raw_value}"`}
                            </p>
                          </div>
                        </div>
                        {issue.resolution_status === "open" ? (
                          <div className="flex gap-2">
                            <button
                              type="button"
                              onClick={() =>
                                handleResolveIssue(issue.id, "resolved")
                              }
                              className="rounded-lg bg-emerald-100 px-3 py-1 text-xs font-medium text-emerald-700 hover:bg-emerald-200"
                            >
                              Resolve
                            </button>
                            <button
                              type="button"
                              onClick={() =>
                                handleResolveIssue(issue.id, "ignored")
                              }
                              className="rounded-lg bg-slate-100 px-3 py-1 text-xs font-medium text-slate-600 hover:bg-slate-200"
                            >
                              Ignore
                            </button>
                          </div>
                        ) : (
                          <span className="text-xs text-slate-500">
                            {issue.resolution_status}
                          </span>
                        )}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {confirmable && (
                <div className="mt-8 rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div>
                      <h3 className="text-lg font-semibold text-blue-950">
                        Confirm submission
                      </h3>
                      <p className="mt-1 text-sm text-slate-600">
                        Finalizes staged rows into sales records. Draft products
                        must be activated in{" "}
                        <Link
                          to="/inventory"
                          className="font-medium text-blue-700 underline"
                        >
                          Inventory
                        </Link>{" "}
                        first.
                      </p>
                    </div>
                    <button
                      type="button"
                      onClick={handleConfirm}
                      disabled={confirming || dirty.size > 0}
                      className="rounded-lg bg-emerald-600 px-5 py-2 text-sm font-medium text-white hover:bg-emerald-500 disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      {confirming ? "Confirming…" : "Confirm submission"}
                    </button>
                  </div>
                  {dirty.size > 0 && (
                    <p className="mt-2 text-sm text-amber-700">
                      Save your row changes before confirming.
                    </p>
                  )}
                  {confirmError && (
                    <p className="mt-3 rounded-lg bg-rose-50 px-4 py-2 text-sm text-rose-700">
                      {confirmError}
                    </p>
                  )}
                </div>
              )}
            </>
          ) : null}
        </div>
      )}
    </SidebarLayout>
  );
}
