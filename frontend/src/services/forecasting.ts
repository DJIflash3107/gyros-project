import { request } from "./apiClient";
import type {
  DataSufficiency,
  ForecastRun,
  Pagination,
} from "./types";

export interface PredictInput {
  branch_id: number;
  product_id: number;
  horizon_days?: number;
  window_size?: number;
}

export interface ListRunsOptions {
  branchId?: number;
  productId?: number;
  page?: number;
  pageSize?: number;
}

export async function predict(
  businessId: number,
  input: PredictInput,
): Promise<ForecastRun> {
  const data = await request<{ forecast_run: ForecastRun }>(
    `/businesses/${businessId}/forecasting/predict`,
    { method: "POST", body: JSON.stringify(input) },
  );
  return data.forecast_run;
}

export async function sufficiency(
  businessId: number,
  branchId: number,
  productId: number,
): Promise<DataSufficiency> {
  const params = new URLSearchParams({
    branch_id: String(branchId),
    product_id: String(productId),
  });
  const data = await request<{ sufficiency: DataSufficiency }>(
    `/businesses/${businessId}/forecasting/sufficiency?${params}`,
  );
  return data.sufficiency;
}

export async function listRuns(
  businessId: number,
  options: ListRunsOptions = {},
): Promise<ForecastRun[]> {
  const params = new URLSearchParams();
  if (options.branchId) params.set("branch_id", String(options.branchId));
  if (options.productId) params.set("product_id", String(options.productId));
  if (options.page) params.set("page", String(options.page));
  params.set("page_size", String(options.pageSize ?? 20));

  const data = await request<{
    forecast_runs: ForecastRun[];
    pagination: Pagination;
  }>(`/businesses/${businessId}/forecasting/runs?${params}`);
  return data.forecast_runs;
}

export async function getRun(
  businessId: number,
  runId: number,
): Promise<ForecastRun> {
  const data = await request<{ forecast_run: ForecastRun }>(
    `/businesses/${businessId}/forecasting/runs/${runId}`,
  );
  return data.forecast_run;
}
