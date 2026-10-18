export interface ApiEnvelope<T> {
  message: { success?: string; error?: string };
  error: Record<string, string>;
  data: T;
}

export interface Pagination {
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
}

export interface User {
  id: number;
  full_name: string;
  email: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface Business {
  id: number;
  name: string;
  currency: string;
  timezone: string;
  created_at: string;
  updated_at: string;
}

export interface Branch {
  id: number;
  business_id: number;
  name: string;
  branch_code: string | null;
  address: string | null;
  is_active: boolean;
  status: string;
  auto_created_from: string | null;
  created_at: string;
  updated_at: string;
}

export interface AuthToken {
  access_token: string;
  token_type: string;
}

export type InputMethod = "spreadsheet" | "form" | "photo";
export type ReportPeriodType = "daily" | "weekly" | "monthly" | "custom_range";
export type SubmissionStatus =
  | "pending"
  | "processing"
  | "reviewed"
  | "confirmed"
  | "rejected"
  | "failed";
export type ReviewStatus =
  | "pending_review"
  | "needs_correction"
  | "ready"
  | "accepted"
  | "rejected";
export type Granularity = "daily" | "weekly" | "monthly" | "custom_range";
export type IssueSeverity = "info" | "warning" | "error" | "critical";
export type ResolutionStatus = "open" | "resolved" | "ignored";

export interface SalesReportSubmission {
  id: number;
  business_id: number;
  submitted_by_user_id: number;
  branch_id: number | null;
  input_method: string;
  report_period_type: string;
  coverage_start: string;
  coverage_end: string;
  source_file_name: string | null;
  source_mime_type: string | null;
  status: SubmissionStatus;
  total_rows: number;
  accepted_rows: number;
  rejected_rows: number;
  confirmed_at: string | null;
  created_at: string;
  completed_at: string | null;
}

export interface DraftProduct {
  id: number;
  name: string;
  status: string;
  [key: string]: unknown;
}

export interface DraftBranch {
  id: number;
  business_id: number;
  name: string;
  status: string;
  missing_fields: string[];
  auto_created_from: string | null;
}

export interface ImportIssue {
  id: number;
  submission_id: number;
  staging_row_id: number | null;
  source_row_number: number | null;
  field_name: string | null;
  issue_code: string;
  severity: IssueSeverity;
  message: string;
  raw_value: string | null;
  resolution_status: ResolutionStatus;
  resolved_by_user_id: number | null;
  resolved_at: string | null;
  created_at: string;
}

export interface ProcessingSummary {
  total_rows: number;
  ready_rows: number;
  pending_review_rows: number;
  needs_correction_rows: number;
  issue_count: number;
  sheets_processed: string[];
  sheets_skipped: string[];
  sheets_ambiguous: string[];
  expenses_extracted: number;
  expenses_total_amount: string;
  auto_created_products: DraftProduct[];
  auto_created_branches: DraftBranch[];
}

export interface ProcessingResult {
  submission: SalesReportSubmission;
  summary: ProcessingSummary;
  issues: ImportIssue[];
}

export interface StagingRow {
  id: number;
  submission_id: number;
  source_row_number: number | null;
  source_sheet_name: string | null;
  raw_product_name: string | null;
  branch_id: number | null;
  product_id: number | null;
  period_start: string | null;
  period_end: string | null;
  granularity: Granularity | null;
  prepared_qty: string | null;
  sold_qty: string | null;
  leftover_qty: string | null;
  spoiled_qty: string | null;
  recorded_revenue: string | null;
  unit_price: string | null;
  unit_cost: string | null;
  review_status: ReviewStatus;
  review_notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface ManualFormRowInput {
  raw_product_name: string;
  branch_id: number;
  product_id?: number | null;
  period_start: string;
  period_end: string;
  granularity: Granularity;
  prepared_qty?: number | null;
  sold_qty?: number | null;
  leftover_qty?: number | null;
  spoiled_qty?: number | null;
  recorded_revenue?: number | null;
}

export interface ManualFormBatchCreate {
  report_period_type: ReportPeriodType;
  coverage_start: string;
  coverage_end: string;
  branch_id?: number | null;
  rows: ManualFormRowInput[];
}

export type RecordStatus = "active" | "superseded" | "cancelled";

export interface Product {
  id: number;
  business_id: number;
  name: string;
  sku: string | null;
  category: string | null;
  base_unit: string;
  is_active: boolean;
  status: string;
  auto_created_from: string | null;
  created_at: string;
  updated_at: string;
}

export interface ProductAlias {
  id: number;
  business_id: number;
  product_id: number;
  alias_name: string;
  normalized_alias: string;
  created_by_user_id: number | null;
  created_at: string;
}

export interface ProductCostHistory {
  id: number;
  business_id: number;
  product_id: number;
  effective_from: string;
  effective_to: string | null;
  unit_cost: string;
  cost_unit: string;
  source_submission_id: number | null;
  created_by_user_id: number | null;
  created_at: string;
}

export interface ProductPriceHistory {
  id: number;
  business_id: number;
  product_id: number;
  effective_from: string;
  effective_to: string | null;
  selling_price: string;
  price_unit: string;
  source_submission_id: number | null;
  created_by_user_id: number | null;
  created_at: string;
}

export interface Expense {
  id: number;
  business_id: number;
  branch_id: number | null;
  expense_date: string;
  category: string;
  description: string | null;
  amount: string;
  currency: string;
  source_submission_id: number | null;
  source_row_number: number | null;
  created_by_user_id: number | null;
  created_at: string;
  updated_at: string;
}

export interface ExpenseImportSummary {
  total_extracted: number;
  total_saved: number;
  total_amount: string;
  categories_breakdown: Record<string, string>;
  file_name: string | null;
  input_method: string;
  persisted: boolean;
}

export interface ExpenseImportItem {
  source_row_number: number | null;
  branch_id: number | null;
  branch_name: string | null;
  expense_date: string;
  category: string;
  description: string | null;
  amount: string;
  currency: string;
  source_file_name: string | null;
  confidence: number | null;
  warnings: string[];
}

export interface ExpenseImportResult {
  summary: ExpenseImportSummary;
  expenses: Expense[];
  items: ExpenseImportItem[];
  issues: Record<string, unknown>[];
}

export interface SalesReportObservation {
  id: number;
  business_id: number;
  branch_id: number;
  product_id: number;
  source_submission_id: number;
  source_staging_row_id: number | null;
  period_start: string;
  period_end: string;
  granularity: string;
  prepared_qty: string | null;
  opening_stock_qty: string | null;
  received_qty: string | null;
  available_stock_qty: string | null;
  sold_qty: string | null;
  leftover_qty: string | null;
  spoiled_qty: string | null;
  damaged_qty: string | null;
  staff_meals_qty: string | null;
  donated_qty: string | null;
  other_disposition_qty: string | null;
  recorded_revenue: string | null;
  record_status: RecordStatus;
  created_by_user_id: number | null;
  updated_by_user_id: number | null;
  created_at: string;
  updated_at: string;
}

// Forecasting

export interface ForecastPredictionPoint {
  forecast_date: string;
  predicted_qty: number;
  weekday: number | null;
}

export interface ForecastRun {
  id: number;
  business_id: number;
  branch_id: number;
  product_id: number;
  method: string;
  horizon_days: number;
  window_size: number;
  training_start: string | null;
  training_end: string | null;
  observations_used: number;
  is_reliable: boolean;
  reliability_note: string | null;
  mae: number | null;
  wape: number | null;
  forecast_bias: number | null;
  predictions: ForecastPredictionPoint[];
  created_at: string;
}

export interface DataSufficiency {
  branch_id: number;
  product_id: number;
  total_observations: number;
  daily_observations: number;
  distinct_weekdays: number;
  date_range_start: string | null;
  date_range_end: string | null;
  supports_baseline: boolean;
  supports_weekday: boolean;
  message: string;
}

// Business actions

export type ActionStatus =
  | "open"
  | "in_progress"
  | "implemented"
  | "dismissed"
  | "archived";
export type ActionUrgency = "critical" | "high" | "medium" | "low";

export interface BusinessAction {
  id: number;
  business_id: number;
  action_type: string;
  rule_label: string;
  category: string;
  title: string;
  ai_generated: boolean;
  urgency: string;
  expected_impact: string;
  priority_score: number;
  status: string;
  evidence_quality: string;
  rationale: string;
  supporting_data: Record<string, unknown> | null;
  recommended_steps: string[] | null;
  risks: string[] | null;
  success_metrics: string[] | null;
  limitations: string | null;
  dismissed_reason: string | null;
  branch_id: number | null;
  product_id: number | null;
  forecast_run_id: number | null;
  created_by_user_id: number | null;
  updated_by_user_id: number | null;
  created_at: string;
  updated_at: string;
}

// Promotions

export interface PromotionItem {
  product_id: number;
  product_name: string;
  discount_type: string;
  discount_value: number;
  original_price: number | null;
  discounted_price: number | null;
  unit_cost: number | null;
  margin_per_unit: number | null;
  margin_pct: number | null;
  expected_qty: number | null;
  estimated_contribution: number | null;
  cost_data_available: boolean;
  price_data_available: boolean;
  warnings: string[];
}

export interface PromotionPlan {
  id: number;
  business_id: number;
  title: string;
  promotion_type: string;
  status: string;
  branch_id: number | null;
  start_date: string;
  end_date: string;
  items: PromotionItem[];
  total_original_revenue: number | null;
  total_discounted_revenue: number | null;
  total_estimated_cost: number | null;
  total_estimated_margin: number | null;
  avg_margin_pct: number | null;
  is_financially_validated: boolean;
  min_margin_pct: number | null;
  warnings: string[] | null;
  assumptions: string[] | null;
  missing_data: string[] | null;
  risks: string[] | null;
  rationale: string | null;
  recommended_actions: string[] | null;
  created_by_user_id: number | null;
  updated_by_user_id: number | null;
  approved_by_user_id: number | null;
  approved_at: string | null;
  rejected_reason: string | null;
  created_at: string;
  updated_at: string;
}

// Artifacts

export type ArtifactType = "report" | "plan" | "file" | "image";
export type ArtifactStatus = "pending" | "generating" | "ready" | "failed";
export type ReportType =
  | "sales_summary"
  | "financial_summary"
  | "inventory_status"
  | "forecast_export"
  | "promotion_summary"
  | "action_center_summary";
export type ReportFormat = "csv" | "xlsx" | "pdf";
export type ImagePurpose =
  | "product_catalog"
  | "promotional_poster"
  | "promotion_visual";

export interface Artifact {
  id: number;
  business_id: number;
  title: string;
  artifact_type: string;
  file_format: string | null;
  storage_backend: string;
  file_size_bytes: number;
  mime_type: string | null;
  sha256_hash: string | null;
  purpose: string | null;
  source_entity_type: string | null;
  source_entity_id: number | null;
  generation_params: Record<string, unknown> | null;
  metadata_json: Record<string, unknown> | null;
  status: string;
  error_message: string | null;
  created_by_user_id: number | null;
  expires_at: string | null;
  download_count: number;
  last_downloaded_at: string | null;
  created_at: string;
  updated_at: string;
  download_url: string | null;
}

export interface ArtifactPagination {
  current_page: number;
  per_page: number;
  total_records: number;
  total_pages: number;
}
