import { request } from "./apiClient";
import type { Pagination, PromotionPlan } from "./types";

export interface PromotionItemInput {
  product_id: number;
  discount_type: "percentage" | "fixed_amount" | "bundle_price";
  discount_value: number;
  expected_qty?: number;
  notes?: string;
}

export interface GeneratePromotionInput {
  branch_id?: number;
  promotion_type?: "discount" | "bundle" | "time_limited" | "bogo";
  start_date: string;
  end_date: string;
  items: PromotionItemInput[];
  min_margin_pct?: number;
  persist?: boolean;
}

export interface GeneratePromotionResult {
  plan: PromotionPlan;
  data_summary: Record<string, unknown>;
}

export interface ListPromotionsOptions {
  status?: string;
  promotionType?: string;
  branchId?: number;
  startAfter?: string;
  endBefore?: string;
  page?: number;
  pageSize?: number;
}

export type PromotionStatusUpdate =
  | "draft"
  | "approved"
  | "rejected"
  | "archived";

export async function generate(
  businessId: number,
  input: GeneratePromotionInput,
): Promise<GeneratePromotionResult> {
  return request<GeneratePromotionResult>(
    `/businesses/${businessId}/promotions/generate`,
    { method: "POST", body: JSON.stringify(input) },
  );
}

export async function listPromotions(
  businessId: number,
  options: ListPromotionsOptions = {},
): Promise<PromotionPlan[]> {
  const params = new URLSearchParams();
  if (options.status) params.set("status", options.status);
  if (options.promotionType) params.set("promotion_type", options.promotionType);
  if (options.branchId) params.set("branch_id", String(options.branchId));
  if (options.startAfter) params.set("start_after", options.startAfter);
  if (options.endBefore) params.set("end_before", options.endBefore);
  if (options.page) params.set("page", String(options.page));
  params.set("page_size", String(options.pageSize ?? 20));

  const data = await request<{
    plans: PromotionPlan[];
    pagination: Pagination;
  }>(`/businesses/${businessId}/promotions?${params}`);
  return data.plans;
}

export async function getPromotion(
  businessId: number,
  planId: number,
): Promise<PromotionPlan> {
  const data = await request<{ plan: PromotionPlan }>(
    `/businesses/${businessId}/promotions/${planId}`,
  );
  return data.plan;
}

export async function updateStatus(
  businessId: number,
  planId: number,
  status: PromotionStatusUpdate,
  rejectedReason?: string,
): Promise<PromotionPlan> {
  const data = await request<{ plan: PromotionPlan }>(
    `/businesses/${businessId}/promotions/${planId}/status`,
    {
      method: "PATCH",
      body: JSON.stringify({
        status,
        ...(rejectedReason ? { rejected_reason: rejectedReason } : {}),
      }),
    },
  );
  return data.plan;
}

export async function evaluate(
  businessId: number,
  planId: number,
  minMarginPct?: number,
): Promise<GeneratePromotionResult> {
  return request<GeneratePromotionResult>(
    `/businesses/${businessId}/promotions/${planId}/evaluate`,
    {
      method: "POST",
      body: JSON.stringify(
        minMarginPct !== undefined ? { min_margin_pct: minMarginPct } : {},
      ),
    },
  );
}
