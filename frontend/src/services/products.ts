import { request } from "./apiClient";
import type {
  Pagination,
  Product,
  ProductAlias,
  ProductCostHistory,
  ProductPriceHistory,
} from "./types";

export interface ProductCreateInput {
  name: string;
  sku?: string | null;
  category?: string | null;
  base_unit: string;
  is_active?: boolean;
}

export interface ProductUpdateInput {
  name?: string;
  sku?: string | null;
  category?: string | null;
  base_unit?: string;
  is_active?: boolean;
}

export interface ProductActivateInput {
  base_unit: string;
  name?: string;
  sku?: string | null;
  category?: string | null;
}

export interface ListProductsOptions {
  category?: string;
  isActive?: boolean;
  status?: string;
  page?: number;
  pageSize?: number;
}

export async function listProducts(
  businessId: number,
  options: ListProductsOptions = {},
): Promise<Product[]> {
  const params = new URLSearchParams();
  if (options.category) params.set("category", options.category);
  if (options.isActive !== undefined)
    params.set("is_active", String(options.isActive));
  if (options.status) params.set("status", options.status);
  if (options.page) params.set("page", String(options.page));
  params.set("page_size", String(options.pageSize ?? 100));
  const query = params.toString();

  const data = await request<{ products: Product[]; pagination: Pagination }>(
    `/businesses/${businessId}/products?${query}`,
  );
  return data.products;
}

export async function getProduct(
  businessId: number,
  productId: number,
): Promise<Product> {
  const data = await request<{ product: Product }>(
    `/businesses/${businessId}/products/${productId}`,
  );
  return data.product;
}

export async function createProduct(
  businessId: number,
  input: ProductCreateInput,
): Promise<Product> {
  const data = await request<{ product: Product }>(
    `/businesses/${businessId}/products`,
    {
      method: "POST",
      body: JSON.stringify(input),
    },
  );
  return data.product;
}

export async function updateProduct(
  businessId: number,
  productId: number,
  input: ProductUpdateInput,
): Promise<Product> {
  const data = await request<{ product: Product }>(
    `/businesses/${businessId}/products/${productId}`,
    {
      method: "PATCH",
      body: JSON.stringify(input),
    },
  );
  return data.product;
}

export async function activateProduct(
  businessId: number,
  productId: number,
  input: ProductActivateInput,
): Promise<Product> {
  const data = await request<{ product: Product }>(
    `/businesses/${businessId}/products/${productId}/activate`,
    {
      method: "POST",
      body: JSON.stringify(input),
    },
  );
  return data.product;
}

export async function deleteProduct(
  businessId: number,
  productId: number,
): Promise<void> {
  await request<Record<string, never>>(
    `/businesses/${businessId}/products/${productId}`,
    { method: "DELETE" },
  );
}

export interface ProductAliasCreateInput {
  product_id: number;
  alias_name: string;
  normalized_alias?: string | null;
}

export interface ProductAliasUpdateInput {
  alias_name?: string;
  normalized_alias?: string | null;
}

export async function listProductAliases(
  businessId: number,
  options: { productId?: number; page?: number; pageSize?: number } = {},
): Promise<ProductAlias[]> {
  const params = new URLSearchParams();
  if (options.productId) params.set("product_id", String(options.productId));
  if (options.page) params.set("page", String(options.page));
  params.set("page_size", String(options.pageSize ?? 100));
  const query = params.toString();

  const data = await request<{
    aliases: ProductAlias[];
    pagination: Pagination;
  }>(`/businesses/${businessId}/product_aliases?${query}`);
  return data.aliases;
}

export async function createProductAlias(
  businessId: number,
  input: ProductAliasCreateInput,
): Promise<ProductAlias> {
  const data = await request<{ alias: ProductAlias }>(
    `/businesses/${businessId}/product_aliases`,
    {
      method: "POST",
      body: JSON.stringify(input),
    },
  );
  return data.alias;
}

export async function updateProductAlias(
  businessId: number,
  aliasId: number,
  input: ProductAliasUpdateInput,
): Promise<ProductAlias> {
  const data = await request<{ alias: ProductAlias }>(
    `/businesses/${businessId}/product_aliases/${aliasId}`,
    {
      method: "PATCH",
      body: JSON.stringify(input),
    },
  );
  return data.alias;
}

export async function deleteProductAlias(
  businessId: number,
  aliasId: number,
): Promise<void> {
  await request<Record<string, never>>(
    `/businesses/${businessId}/product_aliases/${aliasId}`,
    { method: "DELETE" },
  );
}

export interface ProductCostCreateInput {
  product_id: number;
  effective_from: string;
  effective_to?: string | null;
  unit_cost: string;
  cost_unit: string;
  source_submission_id?: number | null;
}

export interface ProductCostUpdateInput {
  effective_to?: string | null;
  unit_cost?: string;
  cost_unit?: string;
}

export async function listProductCostHistory(
  businessId: number,
  options: { productId?: number; page?: number; pageSize?: number } = {},
): Promise<ProductCostHistory[]> {
  const params = new URLSearchParams();
  if (options.productId) params.set("product_id", String(options.productId));
  if (options.page) params.set("page", String(options.page));
  params.set("page_size", String(options.pageSize ?? 100));
  const query = params.toString();

  const data = await request<{
    cost_histories: ProductCostHistory[];
    pagination: Pagination;
  }>(`/businesses/${businessId}/product_cost_history?${query}`);
  return data.cost_histories;
}

export async function createProductCost(
  businessId: number,
  input: ProductCostCreateInput,
): Promise<ProductCostHistory> {
  const data = await request<{ cost_history: ProductCostHistory }>(
    `/businesses/${businessId}/product_cost_history`,
    {
      method: "POST",
      body: JSON.stringify(input),
    },
  );
  return data.cost_history;
}

export async function updateProductCost(
  businessId: number,
  costId: number,
  input: ProductCostUpdateInput,
): Promise<ProductCostHistory> {
  const data = await request<{ cost_history: ProductCostHistory }>(
    `/businesses/${businessId}/product_cost_history/${costId}`,
    {
      method: "PATCH",
      body: JSON.stringify(input),
    },
  );
  return data.cost_history;
}

export async function deleteProductCost(
  businessId: number,
  costId: number,
): Promise<void> {
  await request<Record<string, never>>(
    `/businesses/${businessId}/product_cost_history/${costId}`,
    { method: "DELETE" },
  );
}

export interface ProductPriceCreateInput {
  product_id: number;
  effective_from: string;
  effective_to?: string | null;
  selling_price: string;
  price_unit: string;
  source_submission_id?: number | null;
}

export interface ProductPriceUpdateInput {
  effective_to?: string | null;
  selling_price?: string;
  price_unit?: string;
}

export async function listProductPriceHistory(
  businessId: number,
  options: { productId?: number; page?: number; pageSize?: number } = {},
): Promise<ProductPriceHistory[]> {
  const params = new URLSearchParams();
  if (options.productId) params.set("product_id", String(options.productId));
  if (options.page) params.set("page", String(options.page));
  params.set("page_size", String(options.pageSize ?? 100));
  const query = params.toString();

  const data = await request<{
    price_histories: ProductPriceHistory[];
    pagination: Pagination;
  }>(`/businesses/${businessId}/product_price_history?${query}`);
  return data.price_histories;
}

export async function createProductPrice(
  businessId: number,
  input: ProductPriceCreateInput,
): Promise<ProductPriceHistory> {
  const data = await request<{ price_history: ProductPriceHistory }>(
    `/businesses/${businessId}/product_price_history`,
    {
      method: "POST",
      body: JSON.stringify(input),
    },
  );
  return data.price_history;
}

export async function updateProductPrice(
  businessId: number,
  priceId: number,
  input: ProductPriceUpdateInput,
): Promise<ProductPriceHistory> {
  const data = await request<{ price_history: ProductPriceHistory }>(
    `/businesses/${businessId}/product_price_history/${priceId}`,
    {
      method: "PATCH",
      body: JSON.stringify(input),
    },
  );
  return data.price_history;
}

export async function deleteProductPrice(
  businessId: number,
  priceId: number,
): Promise<void> {
  await request<Record<string, never>>(
    `/businesses/${businessId}/product_price_history/${priceId}`,
    { method: "DELETE" },
  );
}
