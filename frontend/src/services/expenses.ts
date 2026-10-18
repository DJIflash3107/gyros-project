import { request, requestForm } from "./apiClient";
import {
  type EnqueuedJob,
  type PollJobOptions,
  waitForEnqueuedJob,
} from "./backgroundJobs";
import type {
  Expense,
  ExpenseImportResult,
  Granularity,
  Pagination,
  RecordStatus,
  SalesReportObservation,
} from "./types";

export interface ExpenseCreateInput {
  branch_id?: number | null;
  expense_date: string;
  category: string;
  description?: string | null;
  amount: string;
  currency?: string;
  source_submission_id?: number | null;
  source_row_number?: number | null;
  status?: "draft" | "ready" | "active";
}

export interface ExpenseUpdateInput {
  branch_id?: number | null;
  expense_date?: string;
  category?: string;
  description?: string | null;
  amount?: string;
  currency?: string;
  status?: "draft" | "ready" | "active";
}

export interface ListExpensesOptions {
  branchId?: number;
  category?: string;
  status?: "draft" | "ready" | "active" | "all";
  page?: number;
  pageSize?: number;
}

export async function listExpenses(
  businessId: number,
  options: ListExpensesOptions = {},
): Promise<Expense[]> {
  const params = new URLSearchParams();
  if (options.branchId) params.set("branch_id", String(options.branchId));
  if (options.category) params.set("category", options.category);
  if (options.status) params.set("status", options.status);
  if (options.page) params.set("page", String(options.page));
  params.set("page_size", String(options.pageSize ?? 100));
  const query = params.toString();

  const data = await request<{ expenses: Expense[]; pagination: Pagination }>(
    `/businesses/${businessId}/expenses?${query}`,
  );
  return data.expenses;
}

export async function getExpense(
  businessId: number,
  expenseId: number,
): Promise<Expense> {
  const data = await request<{ expense: Expense }>(
    `/businesses/${businessId}/expenses/${expenseId}`,
  );
  return data.expense;
}

export async function createExpense(
  businessId: number,
  input: ExpenseCreateInput,
): Promise<Expense> {
  const data = await request<{ expense: Expense }>(
    `/businesses/${businessId}/expenses`,
    {
      method: "POST",
      body: JSON.stringify(input),
    },
  );
  return data.expense;
}

export async function createExpensesBatch(
  businessId: number,
  items: ExpenseCreateInput[],
  options: PollJobOptions = {},
): Promise<{ summary: { total_saved: number; total_amount: number }; expenses: Expense[] }> {
  const accepted = await request<EnqueuedJob>(
    `/businesses/${businessId}/expenses/batch`,
    {
      method: "POST",
      body: JSON.stringify({ items }),
    },
  );
  return waitForEnqueuedJob(businessId, accepted, options);
}

export async function updateExpense(
  businessId: number,
  expenseId: number,
  input: ExpenseUpdateInput,
): Promise<Expense> {
  const data = await request<{ expense: Expense }>(
    `/businesses/${businessId}/expenses/${expenseId}`,
    {
      method: "PATCH",
      body: JSON.stringify(input),
    },
  );
  return data.expense;
}

export async function deleteExpense(
  businessId: number,
  expenseId: number,
): Promise<void> {
  await request<Record<string, never>>(
    `/businesses/${businessId}/expenses/${expenseId}`,
    { method: "DELETE" },
  );
}

export async function approveExpenses(
  businessId: number,
  expenseIds: number[],
): Promise<{ updated_count: number; expenses: Expense[] }> {
  return request<{ updated_count: number; expenses: Expense[] }>(
    `/businesses/${businessId}/expenses/approve`,
    { method: "POST", body: JSON.stringify({ expense_ids: expenseIds }) },
  );
}

export async function discardExpenses(
  businessId: number,
  expenseIds: number[],
): Promise<{ deleted_count: number }> {
  return request<{ deleted_count: number }>(
    `/businesses/${businessId}/expenses/discard`,
    { method: "POST", body: JSON.stringify({ expense_ids: expenseIds }) },
  );
}

export interface ImportExpensesInput {
  files: File[];
  inputMethod?: string;
  branchId?: number | null;
  defaultDate?: string;
  sourceSubmissionId?: number | null;
}

export async function importExpenses(
  businessId: number,
  input: ImportExpensesInput,
  options: PollJobOptions = {},
): Promise<ExpenseImportResult> {
  const formData = new FormData();
  for (const file of input.files) {
    formData.append("files", file);
  }
  formData.append("input_method", input.inputMethod ?? "spreadsheet");
  if (input.branchId != null) {
    formData.append("branch_id", String(input.branchId));
  }
  if (input.defaultDate) {
    formData.append("default_date", input.defaultDate);
  }
  if (input.sourceSubmissionId != null) {
    formData.append("source_submission_id", String(input.sourceSubmissionId));
  }

  const accepted = await requestForm<EnqueuedJob>(
    `/businesses/${businessId}/expenses/import`,
    formData,
  );
  return waitForEnqueuedJob(businessId, accepted, options);
}

export interface ObservationCreateInput {
  branch_id: number;
  product_id: number;
  source_submission_id: number;
  source_staging_row_id?: number | null;
  period_start: string;
  period_end: string;
  granularity: Granularity;
  prepared_qty?: string | null;
  opening_stock_qty?: string | null;
  received_qty?: string | null;
  available_stock_qty?: string | null;
  sold_qty?: string | null;
  leftover_qty?: string | null;
  spoiled_qty?: string | null;
  damaged_qty?: string | null;
  staff_meals_qty?: string | null;
  donated_qty?: string | null;
  other_disposition_qty?: string | null;
  recorded_revenue?: string | null;
  record_status?: RecordStatus;
}

export interface ObservationUpdateInput {
  prepared_qty?: string | null;
  opening_stock_qty?: string | null;
  received_qty?: string | null;
  available_stock_qty?: string | null;
  sold_qty?: string | null;
  leftover_qty?: string | null;
  spoiled_qty?: string | null;
  damaged_qty?: string | null;
  staff_meals_qty?: string | null;
  donated_qty?: string | null;
  other_disposition_qty?: string | null;
  recorded_revenue?: string | null;
  record_status?: RecordStatus;
}

export interface ListObservationsOptions {
  branchId?: number;
  productId?: number;
  recordStatus?: string;
  page?: number;
  pageSize?: number;
}

export async function listObservations(
  businessId: number,
  options: ListObservationsOptions = {},
): Promise<SalesReportObservation[]> {
  const params = new URLSearchParams();
  if (options.branchId) params.set("branch_id", String(options.branchId));
  if (options.productId) params.set("product_id", String(options.productId));
  if (options.recordStatus) params.set("record_status", options.recordStatus);
  if (options.page) params.set("page", String(options.page));
  params.set("page_size", String(options.pageSize ?? 100));
  const query = params.toString();

  const data = await request<{
    observations: SalesReportObservation[];
    pagination: Pagination;
  }>(`/businesses/${businessId}/sales_report_observations?${query}`);
  return data.observations;
}

export async function getObservation(
  businessId: number,
  observationId: number,
): Promise<SalesReportObservation> {
  const data = await request<{ observation: SalesReportObservation }>(
    `/businesses/${businessId}/sales_report_observations/${observationId}`,
  );
  return data.observation;
}

export async function createObservation(
  businessId: number,
  input: ObservationCreateInput,
): Promise<SalesReportObservation> {
  const data = await request<{ observation: SalesReportObservation }>(
    `/businesses/${businessId}/sales_report_observations`,
    {
      method: "POST",
      body: JSON.stringify(input),
    },
  );
  return data.observation;
}

export async function updateObservation(
  businessId: number,
  observationId: number,
  input: ObservationUpdateInput,
): Promise<SalesReportObservation> {
  const data = await request<{ observation: SalesReportObservation }>(
    `/businesses/${businessId}/sales_report_observations/${observationId}`,
    {
      method: "PATCH",
      body: JSON.stringify(input),
    },
  );
  return data.observation;
}

export async function deleteObservation(
  businessId: number,
  observationId: number,
): Promise<void> {
  await request<Record<string, never>>(
    `/businesses/${businessId}/sales_report_observations/${observationId}`,
    { method: "DELETE" },
  );
}
