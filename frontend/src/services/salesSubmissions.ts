import { ApiError, getToken, request, requestForm } from "./apiClient";
import type {
  InputMethod,
  ManualFormBatchCreate,
  Pagination,
  ProcessingResult,
  ReportPeriodType,
  SalesReportSubmission,
} from "./types";

const BASE_URL = import.meta.env.VITE_API_BASE_URL;

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

  return requestForm<ProcessingResult>(
    `/businesses/${businessId}/sales_report_submissions/process`,
    formData,
  );
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

function parseSseChunk(buffer: string): {
  events: StreamEvent[];
  rest: string;
} {
  const events: StreamEvent[] = [];
  const blocks = buffer.split("\n\n");
  const rest = blocks.pop() ?? "";
  for (const block of blocks) {
    for (const line of block.split("\n")) {
      if (line.startsWith("data: ")) {
        try {
          events.push(JSON.parse(line.slice(6)) as StreamEvent);
        } catch {
          // skip malformed event payloads
        }
      }
    }
  }
  return { events, rest };
}

export async function processUploadStream(
  businessId: number,
  input: ProcessUploadInput,
  onEvent: (event: StreamEvent) => void,
): Promise<void> {
  const formData = new FormData();
  for (const file of input.files) {
    formData.append("files", file);
  }
  formData.append("input_method", input.inputMethod);
  formData.append("report_period_type", input.reportPeriodType);
  formData.append("coverage_start", input.coverageStart);
  formData.append("coverage_end", input.coverageEnd);
  formData.append("stream", "true");
  if (input.branchId != null) {
    formData.append("branch_id", String(input.branchId));
  }

  const headers: Record<string, string> = {};
  const token = getToken();
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }

  const response = await fetch(
    `${BASE_URL}/businesses/${businessId}/sales_report_submissions/process`,
    { method: "POST", headers, body: formData },
  );

  const contentType = response.headers.get("content-type") ?? "";
  if (!contentType.includes("text/event-stream")) {
    // Non-SSE response means an error envelope (or legacy JSON path).
    let message = "Upload failed";
    let errors: Record<string, string> = {};
    try {
      const envelope = await response.json();
      message =
        envelope.message?.error ??
        Object.values(envelope.error ?? {})[0] ??
        message;
      errors = envelope.error ?? {};
    } catch {
      // keep defaults
    }
    throw new ApiError(response.status, message, errors);
  }

  if (!response.body) {
    throw new ApiError(500, "Streaming not supported by the server");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const parsed = parseSseChunk(buffer);
    buffer = parsed.rest;
    for (const event of parsed.events) {
      onEvent(event);
    }
  }

  buffer += decoder.decode();
  const parsed = parseSseChunk(buffer);
  for (const event of parsed.events) {
    onEvent(event);
  }
}

export async function batchForm(
  businessId: number,
  payload: ManualFormBatchCreate,
): Promise<ProcessingResult> {
  return request<ProcessingResult>(
    `/businesses/${businessId}/sales_report_submissions/batch_form`,
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
  );
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
): Promise<SalesReportSubmission> {
  const data = await request<{ submission: SalesReportSubmission }>(
    `/businesses/${businessId}/sales_report_submissions/${submissionId}/confirm`,
    { method: "POST" },
  );
  return data.submission;
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
