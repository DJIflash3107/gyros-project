import { request, requestForm } from "./apiClient";
import {
  type EnqueuedJob,
  type PollJobOptions,
  waitForEnqueuedJob,
} from "./backgroundJobs";
import type {
  InputMethod,
  ManualFormBatchCreate,
  Pagination,
  ProcessingResult,
  ReportPeriodType,
  SalesReportSubmission,
} from "./types";

export interface ProcessUploadInput {
  files: File[];
  inputMethod: InputMethod;
  reportPeriodType: ReportPeriodType;
  coverageStart: string;
  coverageEnd: string;
  branchId?: number | null;
}

export async function processUpload(
  businessId: number,
  input: ProcessUploadInput,
  options: PollJobOptions = {},
): Promise<ProcessingResult> {
  const formData = new FormData();
  for (const file of input.files) {
    formData.append("files", file);
  }
  formData.append("input_method", input.inputMethod);
  formData.append("report_period_type", input.reportPeriodType);
  formData.append("coverage_start", input.coverageStart);
  formData.append("coverage_end", input.coverageEnd);
  if (input.branchId != null) {
    formData.append("branch_id", String(input.branchId));
  }

  const accepted = await requestForm<EnqueuedJob>(
    `/businesses/${businessId}/sales_report_submissions/process`,
    formData,
  );
  return waitForEnqueuedJob<ProcessingResult>(businessId, accepted, options);
}

export interface ReportStatusEvent {
  event: "report_status";
  step: string;
  message?: string;
}

export interface ValidationResultEvent {
  event: "validation_result";
  total: number;
  ready: number;
  pending_review: number;
  needs_correction: number;
  errors: number;
}

export interface ReportCompleteEvent {
  event: "report_complete";
  submission_id: number;
  total_rows: number;
  accepted_rows: number;
  rejected_rows: number;
  summary: ProcessingResult["summary"];
}

export interface ReportErrorEvent {
  event: "report_error";
  error_code: string;
  message: string;
}

export type StreamEvent =
  | ReportStatusEvent
  | ValidationResultEvent
  | ReportCompleteEvent
  | ReportErrorEvent;

// Kept as adapter for existing UI; backend processing now reports via job polling.
export async function processUploadStream(
  businessId: number,
  input: ProcessUploadInput,
  onEvent: (event: StreamEvent) => void,
  options: PollJobOptions = {},
): Promise<void> {
  const result = await processUpload(businessId, input, {
    ...options,
    onProgress: (job) => {
      options.onProgress?.(job);
      if (job.progress?.message) {
        onEvent({
          event: "report_status",
          step: job.progress.step ?? "processing",
          message: job.progress.message,
        });
      }
    },
  });

  onEvent({
    event: "validation_result",
    total: result.summary.total_rows,
    ready: result.summary.ready_rows,
    pending_review: result.summary.pending_review_rows,
    needs_correction: result.summary.needs_correction_rows,
    errors: result.summary.issue_count,
  });
  onEvent({
    event: "report_complete",
    submission_id: result.submission.id,
    total_rows: result.summary.total_rows,
    accepted_rows: result.submission.accepted_rows,
    rejected_rows: result.submission.rejected_rows,
    summary: result.summary,
  });
}

export async function batchForm(
  businessId: number,
  payload: ManualFormBatchCreate,
  options: PollJobOptions = {},
): Promise<ProcessingResult> {
  const accepted = await request<EnqueuedJob>(
    `/businesses/${businessId}/sales_report_submissions/batch_form`,
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
  );
  return waitForEnqueuedJob<ProcessingResult>(businessId, accepted, options);
}

export interface ListSubmissionsOptions {
  status?: string;
  page?: number;
  pageSize?: number;
}

export async function listSubmissions(
  businessId: number,
  options: ListSubmissionsOptions = {},
): Promise<{ submissions: SalesReportSubmission[]; pagination: Pagination }> {
  const params = new URLSearchParams();
  if (options.status) params.set("status", options.status);
  if (options.page) params.set("page", String(options.page));
  if (options.pageSize) params.set("page_size", String(options.pageSize));
  const query = params.toString();

  return request<{
    submissions: SalesReportSubmission[];
    pagination: Pagination;
  }>(
    `/businesses/${businessId}/sales_report_submissions${query ? `?${query}` : ""}`,
  );
}

export async function getSubmission(
  businessId: number,
  submissionId: number,
): Promise<SalesReportSubmission> {
  const data = await request<{ submission: SalesReportSubmission }>(
    `/businesses/${businessId}/sales_report_submissions/${submissionId}`,
  );
  return data.submission;
}

export async function updateSubmission(
  businessId: number,
  submissionId: number,
  input: {
    branch_id?: number | null;
    status?: string;
    total_rows?: number;
    accepted_rows?: number;
    rejected_rows?: number;
  },
): Promise<SalesReportSubmission> {
  const data = await request<{ submission: SalesReportSubmission }>(
    `/businesses/${businessId}/sales_report_submissions/${submissionId}`,
    {
      method: "PATCH",
      body: JSON.stringify(input),
    },
  );
  return data.submission;
}

export async function confirmSubmission(
  businessId: number,
  submissionId: number,
  options: PollJobOptions = {},
): Promise<SalesReportSubmission> {
  const accepted = await request<EnqueuedJob>(
    `/businesses/${businessId}/sales_report_submissions/${submissionId}/confirm`,
    { method: "POST" },
  );
  return waitForEnqueuedJob<SalesReportSubmission>(businessId, accepted, options);
}

export async function deleteSubmission(
  businessId: number,
  submissionId: number,
): Promise<void> {
  await request<Record<string, never>>(
    `/businesses/${businessId}/sales_report_submissions/${submissionId}`,
    { method: "DELETE" },
  );
}
