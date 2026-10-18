import { request } from "./apiClient";
import type {
  ImportIssue,
  IssueSeverity,
  Pagination,
  ResolutionStatus,
} from "./types";

export interface ListIssuesOptions {
  resolutionStatus?: ResolutionStatus;
  severity?: IssueSeverity;
  page?: number;
  pageSize?: number;
}

export async function listIssues(
  submissionId: number,
  options: ListIssuesOptions = {},
): Promise<{ issues: ImportIssue[]; pagination: Pagination }> {
  const params = new URLSearchParams();
  if (options.resolutionStatus)
    params.set("resolution_status", options.resolutionStatus);
  if (options.severity) params.set("severity", options.severity);
  if (options.page) params.set("page", String(options.page));
  if (options.pageSize) params.set("page_size", String(options.pageSize));
  const query = params.toString();

  return request<{ issues: ImportIssue[]; pagination: Pagination }>(
    `/sales_report_submissions/${submissionId}/import_issues${query ? `?${query}` : ""}`,
  );
}

export async function updateIssue(
  submissionId: number,
  issueId: number,
  input: { resolution_status: ResolutionStatus },
): Promise<ImportIssue> {
  const data = await request<{ issue: ImportIssue }>(
    `/sales_report_submissions/${submissionId}/import_issues/${issueId}`,
    {
      method: "PATCH",
      body: JSON.stringify(input),
    },
  );
  return data.issue;
}
