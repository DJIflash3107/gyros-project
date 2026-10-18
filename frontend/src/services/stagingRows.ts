import { request } from "./apiClient";
import type {
  Granularity,
  Pagination,
  ReviewStatus,
  StagingRow,
} from "./types";

export interface StagingRowUpdateInput {
  raw_product_name?: string | null;
  branch_id?: number | null;
  product_id?: number | null;
  period_start?: string | null;
  period_end?: string | null;
  granularity?: Granularity | null;
  prepared_qty?: number | null;
  sold_qty?: number | null;
  leftover_qty?: number | null;
  spoiled_qty?: number | null;
  recorded_revenue?: number | null;
  unit_price?: number | null;
  unit_cost?: number | null;
  review_status?: ReviewStatus;
  review_notes?: string | null;
}

export interface BulkUpdateInput {
  row_ids?: number[];
  apply_to_all?: boolean;
  filter_review_status?: ReviewStatus;
  review_status?: ReviewStatus;
  review_notes?: string | null;
  branch_id?: number | null;
  product_id?: number | null;
}

export interface ListStagingRowsOptions {
  reviewStatus?: ReviewStatus;
  page?: number;
  pageSize?: number;
}

export async function listStagingRows(
  submissionId: number,
  options: ListStagingRowsOptions = {},
): Promise<{ staging_rows: StagingRow[]; pagination: Pagination }> {
  const params = new URLSearchParams();
  if (options.reviewStatus) params.set("review_status", options.reviewStatus);
  if (options.page) params.set("page", String(options.page));
  if (options.pageSize) params.set("page_size", String(options.pageSize));
  const query = params.toString();

  return request<{ staging_rows: StagingRow[]; pagination: Pagination }>(
    `/sales_report_submissions/${submissionId}/staging_rows${query ? `?${query}` : ""}`,
  );
}

export async function getStagingRow(
  submissionId: number,
  rowId: number,
): Promise<StagingRow> {
  const data = await request<{ staging_row: StagingRow }>(
    `/sales_report_submissions/${submissionId}/staging_rows/${rowId}`,
  );
  return data.staging_row;
}

export async function updateStagingRow(
  submissionId: number,
  rowId: number,
  input: StagingRowUpdateInput,
): Promise<StagingRow> {
  const data = await request<{ staging_row: StagingRow }>(
    `/sales_report_submissions/${submissionId}/staging_rows/${rowId}`,
    {
      method: "PATCH",
      body: JSON.stringify(input),
    },
  );
  return data.staging_row;
}

export async function bulkUpdateStagingRows(
  submissionId: number,
  input: BulkUpdateInput,
): Promise<{ updated_count: number; staging_rows: StagingRow[] }> {
  return request<{ updated_count: number; staging_rows: StagingRow[] }>(
    `/sales_report_submissions/${submissionId}/staging_rows/bulk`,
    {
      method: "PATCH",
      body: JSON.stringify(input),
    },
  );
}

export async function deleteStagingRow(
  submissionId: number,
  rowId: number,
): Promise<void> {
  await request<Record<string, never>>(
    `/sales_report_submissions/${submissionId}/staging_rows/${rowId}`,
    { method: "DELETE" },
  );
}
