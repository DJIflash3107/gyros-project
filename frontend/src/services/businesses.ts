import { request } from "./apiClient";
import type { Business, Pagination } from "./types";

export async function listBusinesses(): Promise<Business[]> {
  const data = await request<{ businesses: Business[]; pagination: Pagination }>(
    "/businesses",
  );
  return data.businesses;
}

export async function createBusiness(input: {
  name: string;
  currency: string;
  timezone: string;
}): Promise<Business> {
  const data = await request<{ business: Business }>("/businesses", {
    method: "POST",
    body: JSON.stringify(input),
  });
  return data.business;
}
