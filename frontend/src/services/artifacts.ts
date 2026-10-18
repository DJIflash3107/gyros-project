import { request } from "./apiClient";
import type {
  Artifact,
  ArtifactPagination,
  ImagePurpose,
  ReportFormat,
  ReportType,
} from "./types";

const BASE_URL = import.meta.env.VITE_API_BASE_URL;

export interface GenerateReportInput {
  report_type: ReportType;
  file_format?: ReportFormat;
  branch_id?: number;
  start_date?: string;
  end_date?: string;
  title?: string;
  parameters?: Record<string, unknown>;
}

export interface GeneratePlanInput {
  source_plan_id: number;
  file_format?: ReportFormat;
  title?: string;
  include_financials?: boolean;
  include_schedule?: boolean;
}

export interface GenerateImageInput {
  purpose: ImagePurpose;
  prompt: string;
  negative_prompt?: string;
  orientation?: "square" | "portrait" | "landscape";
  product_id?: number;
  promotion_plan_id?: number;
  title?: string;
  style?: string;
}

export interface ListArtifactsOptions {
  artifactType?: string;
  fileFormat?: string;
  purpose?: string;
  status?: string;
  page?: number;
  perPage?: number;
}

export interface ListArtifactsResult {
  artifacts: Artifact[];
  pagination: ArtifactPagination;
}

export interface DownloadUrlResult {
  artifact_id: number;
  download_url: string;
  expires_in_seconds: number;
  file_name: string;
  mime_type: string;
  file_size_bytes: number;
}

export async function generateReport(
  businessId: number,
  input: GenerateReportInput,
): Promise<Artifact> {
  return request<Artifact>(
    `/businesses/${businessId}/artifacts/generate-report`,
    { method: "POST", body: JSON.stringify(input) },
  );
}

export async function generatePlan(
  businessId: number,
  input: GeneratePlanInput,
): Promise<Artifact> {
  return request<Artifact>(
    `/businesses/${businessId}/artifacts/generate-plan`,
    { method: "POST", body: JSON.stringify(input) },
  );
}

export async function generateImage(
  businessId: number,
  input: GenerateImageInput,
): Promise<Artifact> {
  return request<Artifact>(
    `/businesses/${businessId}/artifacts/generate-image`,
    { method: "POST", body: JSON.stringify(input) },
  );
}

export async function listArtifacts(
  businessId: number,
  options: ListArtifactsOptions = {},
): Promise<ListArtifactsResult> {
  const params = new URLSearchParams();
  if (options.artifactType) params.set("artifact_type", options.artifactType);
  if (options.fileFormat) params.set("file_format", options.fileFormat);
  if (options.purpose) params.set("purpose", options.purpose);
  if (options.status) params.set("status", options.status);
  if (options.page) params.set("page", String(options.page));
  params.set("per_page", String(options.perPage ?? 20));

  return request<ListArtifactsResult>(
    `/businesses/${businessId}/artifacts?${params}`,
  );
}

export async function getArtifact(
  businessId: number,
  artifactId: number,
): Promise<Artifact> {
  return request<Artifact>(
    `/businesses/${businessId}/artifacts/${artifactId}`,
  );
}

export async function getDownloadUrl(
  businessId: number,
  artifactId: number,
  expiresIn?: number,
): Promise<DownloadUrlResult> {
  const params = expiresIn ? `?expires_in=${expiresIn}` : "";
  return request<DownloadUrlResult>(
    `/businesses/${businessId}/artifacts/${artifactId}/download-url${params}`,
  );
}

export async function downloadArtifact(
  businessId: number,
  artifactId: number,
): Promise<void> {
  const result = await getDownloadUrl(businessId, artifactId);
  const url = result.download_url.startsWith("http")
    ? result.download_url
    : `${BASE_URL.replace(/\/api\/v1\/?$/, "")}${result.download_url}`;
  window.open(url, "_blank");
}

export async function deleteArtifact(
  businessId: number,
  artifactId: number,
): Promise<void> {
  await request<{ id: number }>(
    `/businesses/${businessId}/artifacts/${artifactId}`,
    { method: "DELETE" },
  );
}
