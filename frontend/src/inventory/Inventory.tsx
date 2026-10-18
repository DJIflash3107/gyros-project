import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import Modal from "../components/Modal";
import SidebarLayout from "../components/SidebarLayout";
import Toast, { type ToastType } from "../components/Toast";
import { useBusiness } from "../context/BusinessContext";
import { ApiError } from "../services/apiClient";
import {
  createProduct,
  deleteProduct,
  listProducts,
  updateProduct,
} from "../services/products";
import type { Product } from "../services/types";

type ModalMode = "addProduct" | "editProduct";

interface ProductFormData {
  name: string;
  sku: string;
  category: string;
  base_unit: string;
  is_active: boolean;
}

const emptyForm: ProductFormData = {
  name: "",
  sku: "",
  category: "",
  base_unit: "",
  is_active: true,
};

function statusBadge(status: string, isActive: boolean) {
  if (!isActive) {
    return "bg-slate-200 text-slate-600";
  }
  return status === "draft"
    ? "bg-amber-100 text-amber-800"
    : "bg-emerald-100 text-emerald-800";
}

function statusLabel(status: string, isActive: boolean) {
  if (!isActive) return "Inactive";
  return status === "draft" ? "Draft" : "Active";
}

export default function Inventory() {
  const { activeBusiness } = useBusiness();
  const [products, setProducts] = useState<Product[]>([]);
  const [loading, setLoading] = useState(true);
  const [categoryFilter, setCategoryFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [modalMode, setModalMode] = useState<ModalMode>("addProduct");
  const [editingId, setEditingId] = useState<number | null>(null);
  const [form, setForm] = useState<ProductFormData>(emptyForm);
  const [saving, setSaving] = useState(false);
  const [toast, setToast] = useState<{ message: string; type: ToastType; isOpen: boolean }>({
    message: "",
    type: "success",
    isOpen: false,
  });

  const showToast = (message: string, type: ToastType = "success") => {
    setToast({ message, type, isOpen: true });
  };

  const closeToast = () => {
    setToast((prev) => ({ ...prev, isOpen: false }));
  };

  const fetchProducts = useCallback(async () => {
    if (!activeBusiness) return;
    try {
      const list = await listProducts(activeBusiness.id, {
        category: categoryFilter || undefined,
        status: statusFilter || undefined,
      });
      setProducts(list);
    } catch (err) {
      showToast(
        err instanceof ApiError ? err.message : "Failed to load products",
        "error",
      );
    } finally {
      setLoading(false);
    }
  }, [activeBusiness, categoryFilter, statusFilter]);

  useEffect(() => {
    // Defer so no setState runs synchronously inside the effect body.
    queueMicrotask(() => {
      void fetchProducts();
    });
  }, [fetchProducts]);

  const categories = Array.from(
    new Set(products.map((p) => p.category).filter((c): c is string => !!c)),
  ).sort();

  const openAddProduct = () => {
    setForm(emptyForm);
    setEditingId(null);
    setModalMode("addProduct");
    setIsModalOpen(true);
  };

  const openEditProduct = (product: Product) => {
    setForm({
      name: product.name,
      sku: product.sku ?? "",
      category: product.category ?? "",
      base_unit: product.base_unit,
      is_active: product.is_active,
    });
    setEditingId(product.id);
    setModalMode("editProduct");
    setIsModalOpen(true);
  };

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!activeBusiness) return;
    setSaving(true);
    try {
      if (modalMode === "addProduct") {
        await createProduct(activeBusiness.id, {
          name: form.name,
          sku: form.sku || null,
          category: form.category || null,
          base_unit: form.base_unit,
          is_active: form.is_active,
        });
        showToast(`Added product: ${form.name}`);
      } else if (editingId != null) {
        await updateProduct(activeBusiness.id, editingId, {
          name: form.name,
          sku: form.sku || null,
          category: form.category || null,
          base_unit: form.base_unit,
          is_active: form.is_active,
        });
        showToast(`Updated product: ${form.name}`);
      }
      setIsModalOpen(false);
      await fetchProducts();
    } catch (err) {
      showToast(
        err instanceof ApiError ? err.message : "Failed to save product",
        "error",
      );
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (product: Product) => {
    if (!activeBusiness) return;
    if (!window.confirm(`Delete product "${product.name}"?`)) return;
    try {
      await deleteProduct(activeBusiness.id, product.id);
      showToast("Product deleted successfully");
      await fetchProducts();
    } catch (err) {
      showToast(
        err instanceof ApiError ? err.message : "Failed to delete product",
        "error",
      );
    }
  };

  return (
    <SidebarLayout>
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-blue-950">Inventory & Stocks</h2>
          <p className="mt-1 text-slate-600">Products and pricing.</p>
        </div>
        <button
          type="button"
          onClick={openAddProduct}
          className="rounded-lg bg-blue-900 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-blue-800"
        >
          Add Product
        </button>
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-3">
        <select
          value={categoryFilter}
          onChange={(e) => setCategoryFilter(e.target.value)}
          className="rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
        >
          <option value="">All categories</option>
          {categories.map((category) => (
            <option key={category} value={category}>
              {category}
            </option>
          ))}
        </select>
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
        >
          <option value="">All statuses</option>
          <option value="active">Active</option>
          <option value="draft">Draft</option>
        </select>
      </div>

      <div className="mt-4 overflow-x-auto rounded-xl border border-slate-200 bg-white shadow-sm">
        <table className="w-full min-w-[44rem] text-left text-sm">
          <thead className="bg-blue-950 text-white">
            <tr>
              <th className="px-6 py-3 font-medium">Product</th>
              <th className="px-6 py-3 font-medium">SKU</th>
              <th className="px-6 py-3 font-medium">Category</th>
              <th className="px-6 py-3 font-medium">Base Unit</th>
              <th className="px-6 py-3 font-medium">Status</th>
              <th className="px-6 py-3 font-medium">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {loading ? (
              <tr>
                <td colSpan={6} className="px-6 py-8 text-center text-slate-500">
                  Loading products...
                </td>
              </tr>
            ) : products.length === 0 ? (
              <tr>
                <td colSpan={6} className="px-6 py-8 text-center text-slate-500">
                  No products yet. Add your first product to get started.
                </td>
              </tr>
            ) : (
              products.map((product) => (
                <tr key={product.id} className="hover:bg-slate-50">
                  <td className="px-6 py-3 font-medium text-blue-900">
                    <Link
                      to={`/inventory/${product.id}`}
                      className="hover:underline"
                    >
                      {product.name}
                    </Link>
                  </td>
                  <td className="px-6 py-3 text-slate-700">{product.sku ?? "—"}</td>
                  <td className="px-6 py-3 text-slate-700">
                    {product.category ?? "—"}
                  </td>
                  <td className="px-6 py-3 text-slate-700">{product.base_unit}</td>
                  <td className="px-6 py-3">
                    <span
                      className={`inline-block rounded-full px-2.5 py-0.5 text-xs font-medium whitespace-nowrap ${statusBadge(product.status, product.is_active)}`}
                    >
                      {statusLabel(product.status, product.is_active)}
                    </span>
                  </td>
                  <td className="px-6 py-3">
                    <div className="flex items-center gap-3">
                      <button
                        type="button"
                        onClick={() => openEditProduct(product)}
                        className="text-sm font-medium text-blue-700 hover:text-blue-900"
                      >
                        Edit
                      </button>
                      <button
                        type="button"
                        onClick={() => handleDelete(product)}
                        className="text-sm font-medium text-red-600 hover:text-red-800"
                      >
                        Delete
                      </button>
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      <Modal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        title={modalMode === "addProduct" ? "Add Product" : "Edit Product"}
      >
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label
              htmlFor="productName"
              className="block text-sm font-medium text-slate-700"
            >
              Product Name
            </label>
            <input
              id="productName"
              type="text"
              required
              value={form.name}
              onChange={(e) => setForm((prev) => ({ ...prev, name: e.target.value }))}
              className="mt-1 block w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
            />
          </div>
          <div>
            <label
              htmlFor="productSku"
              className="block text-sm font-medium text-slate-700"
            >
              SKU
            </label>
            <input
              id="productSku"
              type="text"
              value={form.sku}
              onChange={(e) => setForm((prev) => ({ ...prev, sku: e.target.value }))}
              className="mt-1 block w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
            />
          </div>
          <div>
            <label
              htmlFor="productCategory"
              className="block text-sm font-medium text-slate-700"
            >
              Category
            </label>
            <input
              id="productCategory"
              type="text"
              value={form.category}
              onChange={(e) =>
                setForm((prev) => ({ ...prev, category: e.target.value }))
              }
              className="mt-1 block w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
            />
          </div>
          <div>
            <label
              htmlFor="productBaseUnit"
              className="block text-sm font-medium text-slate-700"
            >
              Base Unit
            </label>
            <input
              id="productBaseUnit"
              type="text"
              required
              placeholder="e.g. pcs, kg, L"
              value={form.base_unit}
              onChange={(e) =>
                setForm((prev) => ({ ...prev, base_unit: e.target.value }))
              }
              className="mt-1 block w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
            />
          </div>
          <label className="flex items-center gap-2 text-sm text-slate-700">
            <input
              type="checkbox"
              checked={form.is_active}
              onChange={(e) =>
                setForm((prev) => ({ ...prev, is_active: e.target.checked }))
              }
              className="h-4 w-4 rounded border-slate-300"
            />
            Active
          </label>
          <div className="flex gap-3 pt-2">
            <button
              type="submit"
              disabled={saving}
              className="rounded-lg bg-blue-900 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-blue-800 disabled:opacity-50"
            >
              {saving
                ? "Saving..."
                : modalMode === "addProduct"
                  ? "Add Product"
                  : "Save Changes"}
            </button>
            <button
              type="button"
              onClick={() => setIsModalOpen(false)}
              className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 transition-colors hover:bg-slate-50"
            >
              Cancel
            </button>
          </div>
        </form>
      </Modal>

      <Toast
        message={toast.message}
        type={toast.type}
        isOpen={toast.isOpen}
        onClose={closeToast}
      />
    </SidebarLayout>
  );
}
