import { request } from "./apiClient";
import type { Branch, Pagination } from "./types";

export interface BranchCreateInput {
  name: string;
  branch_code?: string | null;
  address?: string | null;
  is_active?: boolean;
}

export interface BranchUpdateInput {
  name?: string;
  branch_code?: string | null;
  address?: string | null;
  is_active?: boolean;
}

export interface BranchActivateInput {
  name?: string;
  branch_code?: string | null;
  address?: string | null;
}

export async function listBranches(
  businessId: number,
  options: { isActive?: boolean; status?: string } = {},
): Promise<Branch[]> {
  const params = new URLSearchParams();
  if (options.isActive !== undefined)
    params.set("is_active", String(options.isActive));
  if (options.status) params.set("status", options.status);
  params.set("page_size", "100");
  const query = params.toString();

  const data = await request<{ branches: Branch[]; pagination: Pagination }>(
    `/businesses/${businessId}/branches?${query}`,
  );
  return data.branches;
}

export async function getBranch(
  businessId: number,
  branchId: number,
): Promise<Branch> {
  const data = await request<{ branch: Branch }>(
    `/businesses/${businessId}/branches/${branchId}`,
  );
  return data.branch;
}

export async function createBranch(
  businessId: number,
  input: BranchCreateInput,
): Promise<Branch> {
  const data = await request<{ branch: Branch }>(
    `/businesses/${businessId}/branches`,
    {
      method: "POST",
      body: JSON.stringify(input),
    },
  );
  return data.branch;
}

export async function updateBranch(
  businessId: number,
  branchId: number,
  input: BranchUpdateInput,
): Promise<Branch> {
  const data = await request<{ branch: Branch }>(
    `/businesses/${businessId}/branches/${branchId}`,
    {
      method: "PATCH",
      body: JSON.stringify(input),
    },
  );
  return data.branch;
}

export async function activateBranch(
  businessId: number,
  branchId: number,
  input: BranchActivateInput = {},
): Promise<Branch> {
  const data = await request<{ branch: Branch }>(
    `/businesses/${businessId}/branches/${branchId}/activate`,
    {
      method: "POST",
      body: JSON.stringify(input),
    },
  );
  return data.branch;
}

export async function deleteBranch(
  businessId: number,
  branchId: number,
): Promise<void> {
  await request<Record<string, never>>(
    `/businesses/${businessId}/branches/${branchId}`,
    { method: "DELETE" },
  );
}
