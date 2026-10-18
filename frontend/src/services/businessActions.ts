import { request } from "./apiClient";
import type { BusinessAction, Pagination } from "./types";

export interface GenerateActionsInput {
  branch_id?: number;
  product_id?: number;
  categories?: string[];
  lookback_days?: number;
  persist?: boolean;
}

export interface GenerateActionsResult {
  generated_count: number;
  persisted_count: number;
  actions: BusinessAction[];
  data_summary: Record<string, unknown>;
}

export interface ListActionsOptions {
  status?: string;
  category?: string;
  urgency?: string;
  evidenceQuality?: string;
  branchId?: number;
  productId?: number;
  minPriority?: number;
  page?: number;
  pageSize?: number;
}

export type ActionStatusUpdate =
  | "in_progress"
  | "implemented"
  | "dismissed"
  | "archived";

export async function generate(
  businessId: number,
  input: GenerateActionsInput = {},
): Promise<GenerateActionsResult> {
  return request<GenerateActionsResult>(
    `/businesses/${businessId}/business-actions/generate`,
    { method: "POST", body: JSON.stringify(input) },
  );
}

export async function listActions(
  businessId: number,
  options: ListActionsOptions = {},
): Promise<BusinessAction[]> {
  const params = new URLSearchParams();
  if (options.status) params.set("status", options.status);
  if (options.category) params.set("category", options.category);
  if (options.urgency) params.set("urgency", options.urgency);
  if (options.evidenceQuality)
    params.set("evidence_quality", options.evidenceQuality);
  if (options.branchId) params.set("branch_id", String(options.branchId));
  if (options.productId) params.set("product_id", String(options.productId));
  if (options.minPriority !== undefined)
    params.set("min_priority", String(options.minPriority));
  if (options.page) params.set("page", String(options.page));
  params.set("page_size", String(options.pageSize ?? 20));

  const data = await request<{
    actions: BusinessAction[];
    pagination: Pagination;
  }>(`/businesses/${businessId}/business-actions?${params}`);
  return data.actions;
}

export async function getAction(
  businessId: number,
  actionId: number,
): Promise<BusinessAction> {
  const data = await request<{ action: BusinessAction }>(
    `/businesses/${businessId}/business-actions/${actionId}`,
  );
  return data.action;
}

export async function updateStatus(
  businessId: number,
  actionId: number,
  status: ActionStatusUpdate,
  dismissedReason?: string,
): Promise<BusinessAction> {
  const data = await request<{ action: BusinessAction }>(
    `/businesses/${businessId}/business-actions/${actionId}/status`,
    {
      method: "PATCH",
      body: JSON.stringify({
        status,
        ...(dismissedReason ? { dismissed_reason: dismissedReason } : {}),
      }),
    },
  );
  return data.action;
}
