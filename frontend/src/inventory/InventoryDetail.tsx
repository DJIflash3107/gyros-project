import { useCallback, useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import Breadcrumbs from "../components/Breadcrumbs";
import Modal from "../components/Modal";
import SidebarLayout from "../components/SidebarLayout";
import Toast, { type ToastType } from "../components/Toast";
import { useBusiness } from "../context/BusinessContext";
import { ApiError } from "../services/apiClient";
import {
  activateProduct,
  createProductAlias,
  createProductCost,
  createProductPrice,
  deleteProductAlias,
  deleteProductCost,
  deleteProductPrice,
  getProduct,
  listProductAliases,
  listProductCostHistory,
  listProductPriceHistory,
  updateProductCost,
  updateProductPrice,
} from "../services/products";
import type {
  Product,
  ProductAlias,
  ProductCostHistory,
  ProductPriceHistory,
} from "../services/types";

interface HistoryFormData {
  effective_from: string;
  effective_to: string;
  value: string;
  unit: string;
}

const emptyHistoryForm: HistoryFormData = {
  effective_from: "",
  effective_to: "",
  value: "",
  unit: "",
};

type HistoryModalState =
  | { kind: "price" | "cost"; mode: "add" }
  | { kind: "price"; mode: "edit"; entry: ProductPriceHistory }
  | { kind: "cost"; mode: "edit"; entry: ProductCostHistory }
  | null;

interface ActivateFormData {
  base_unit: string;
  name: string;
  sku: string;
  category: string;
}

function formatAmount(value: string) {
  const num = Number(value);
  return Number.isNaN(num) ? value : num.toFixed(2);
}

export default function InventoryDetail() {
  const { id } = useParams<{ id: string }>();
  const productId = Number(id);
  const { activeBusiness } = useBusiness();

  const [product, setProduct] = useState<Product | null>(null);
  const [priceHistory, setPriceHistory] = useState<ProductPriceHistory[]>([]);
  const [costHistory, setCostHistory] = useState<ProductCostHistory[]>([]);
  const [aliases, setAliases] = useState<ProductAlias[]>([]);
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);

  const [historyModal, setHistoryModal] = useState<HistoryModalState>(null);
  const [historyForm, setHistoryForm] = useState<HistoryFormData>(emptyHistoryForm);
  const [newAlias, setNewAlias] = useState("");
  const [isActivateOpen, setIsActivateOpen] = useState(false);
  const [activateForm, setActivateForm] = useState<ActivateFormData>({
    base_unit: "",
    name: "",
    sku: "",
    category: "",
  });
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

  const fetchAll = useCallback(async () => {
    if (!activeBusiness || Number.isNaN(productId)) return;
    try {
      const [p, prices, costs, aliasList] = await Promise.all([
        getProduct(activeBusiness.id, productId),
        listProductPriceHistory(activeBusiness.id, { productId }),
        listProductCostHistory(activeBusiness.id, { productId }),
        listProductAliases(activeBusiness.id, { productId }),
      ]);
      setProduct(p);
      setPriceHistory(prices);
      setCostHistory(costs);
      setAliases(aliasList);
      setNotFound(false);
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) {
        setNotFound(true);
      } else {
        showToast(
          err instanceof ApiError ? err.message : "Failed to load product",
          "error",
        );
      }
    } finally {
      setLoading(false);
    }
  }, [activeBusiness, productId]);

  useEffect(() => {
    // Defer so no setState runs synchronously inside the effect body.
    queueMicrotask(() => {
      void fetchAll();
    });
  }, [fetchAll]);

  const openAddHistory = (kind: "price" | "cost") => {
    setHistoryForm({
      ...emptyHistoryForm,
      unit: product?.base_unit ?? "",
    });
    setHistoryModal({ kind, mode: "add" });
  };

  const openEditPrice = (entry: ProductPriceHistory) => {
    setHistoryForm({
      effective_from: entry.effective_from,
      effective_to: entry.effective_to ?? "",
      value: entry.selling_price,
      unit: entry.price_unit,
    });
    setHistoryModal({ kind: "price", mode: "edit", entry });
  };

  const openEditCost = (entry: ProductCostHistory) => {
    setHistoryForm({
      effective_from: entry.effective_from,
      effective_to: entry.effective_to ?? "",
      value: entry.unit_cost,
      unit: entry.cost_unit,
    });
    setHistoryModal({ kind: "cost", mode: "edit", entry });
  };

  const handleHistorySubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!activeBusiness || !historyModal) return;
    setSaving(true);
    try {
      if (historyModal.kind === "price") {
        if (historyModal.mode === "add") {
          await createProductPrice(activeBusiness.id, {
            product_id: productId,
            effective_from: historyForm.effective_from,
            effective_to: historyForm.effective_to || null,
            selling_price: historyForm.value,
            price_unit: historyForm.unit,
          });
          showToast("Price added");
        } else {
          await updateProductPrice(activeBusiness.id, historyModal.entry.id, {
            effective_to: historyForm.effective_to || null,
            selling_price: historyForm.value,
            price_unit: historyForm.unit,
          });
          showToast("Price updated");
        }
      } else if (historyModal.mode === "add") {
        await createProductCost(activeBusiness.id, {
          product_id: productId,
          effective_from: historyForm.effective_from,
          effective_to: historyForm.effective_to || null,
          unit_cost: historyForm.value,
          cost_unit: historyForm.unit,
        });
        showToast("Cost added");
      } else {
        await updateProductCost(activeBusiness.id, historyModal.entry.id, {
          effective_to: historyForm.effective_to || null,
          unit_cost: historyForm.value,
          cost_unit: historyForm.unit,
        });
        showToast("Cost updated");
      }
      setHistoryModal(null);
      await fetchAll();
    } catch (err) {
      showToast(
        err instanceof ApiError ? err.message : "Failed to save entry",
        "error",
      );
    } finally {
      setSaving(false);
    }
  };

  const handleDeleteHistory = async (kind: "price" | "cost", entryId: number) => {
    if (!activeBusiness) return;
    if (!window.confirm("Delete this history entry?")) return;
    try {
      if (kind === "price") {
        await deleteProductPrice(activeBusiness.id, entryId);
      } else {
        await deleteProductCost(activeBusiness.id, entryId);
      }
      showToast("Entry deleted");
      await fetchAll();
    } catch (err) {
      showToast(
        err instanceof ApiError ? err.message : "Failed to delete entry",
        "error",
      );
    }
  };

  const handleAddAlias = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!activeBusiness || !newAlias.trim()) return;
    try {
      await createProductAlias(activeBusiness.id, {
        product_id: productId,
        alias_name: newAlias.trim(),
      });
      setNewAlias("");
      showToast("Alias added");
      await fetchAll();
    } catch (err) {
      showToast(
        err instanceof ApiError ? err.message : "Failed to add alias",
        "error",
      );
    }
  };

  const handleDeleteAlias = async (alias: ProductAlias) => {
    if (!activeBusiness) return;
    if (!window.confirm(`Delete alias "${alias.alias_name}"?`)) return;
    try {
      await deleteProductAlias(activeBusiness.id, alias.id);
      showToast("Alias deleted");
      await fetchAll();
    } catch (err) {
      showToast(
        err instanceof ApiError ? err.message : "Failed to delete alias",
        "error",
      );
    }
  };

  const openActivate = () => {
    if (!product) return;
    setActivateForm({
      base_unit: product.base_unit === "draft" ? "" : product.base_unit,
      name: product.name,
      sku: product.sku ?? "",
      category: product.category ?? "",
    });
    setIsActivateOpen(true);
  };

  const handleActivate = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!activeBusiness) return;
    setSaving(true);
    try {
      await activateProduct(activeBusiness.id, productId, {
        base_unit: activateForm.base_unit,
        name: activateForm.name || undefined,
        sku: activateForm.sku || null,
        category: activateForm.category || null,
      });
      showToast("Product activated");
      setIsActivateOpen(false);
      await fetchAll();
    } catch (err) {
      showToast(
        err instanceof ApiError ? err.message : "Failed to activate product",
        "error",
      );
    } finally {
      setSaving(false);
    }
  };

  if (notFound) {
    return (
      <SidebarLayout>
        <h2 className="text-2xl font-bold text-blue-950">Product Not Found</h2>
        <p className="mt-1 text-slate-600">The requested product does not exist.</p>
      </SidebarLayout>
    );
  }

  return (
    <SidebarLayout>
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-blue-950">
            {product?.name ?? "Product"}
          </h2>
          <Breadcrumbs
            items={[
              { label: "Inventory", to: "/inventory" },
              { label: product?.name ?? "..." },
            ]}
          />
          <p className="mt-3 text-slate-600">
            Product details, price & cost history, and aliases.
          </p>
        </div>
        {product?.status === "draft" && (
          <button
            type="button"
            onClick={openActivate}
            className="rounded-lg bg-emerald-700 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-emerald-600"
          >
            Activate Product
          </button>
        )}
      </div>

      {loading ? (
        <p className="mt-6 text-sm text-slate-500">Loading product...</p>
      ) : product ? (
        <>
          <div className="mt-6 max-w-xl rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
            <dl className="space-y-3 text-sm">
              <div className="flex justify-between border-b border-slate-100 pb-2">
                <dt className="text-slate-500">Name</dt>
                <dd className="font-medium text-slate-900">{product.name}</dd>
              </div>
              <div className="flex justify-between border-b border-slate-100 pb-2">
                <dt className="text-slate-500">SKU</dt>
                <dd className="font-medium text-slate-900">
                  {product.sku ?? "—"}
                </dd>
              </div>
              <div className="flex justify-between border-b border-slate-100 pb-2">
                <dt className="text-slate-500">Category</dt>
                <dd className="font-medium text-slate-900">
                  {product.category ?? "—"}
                </dd>
              </div>
              <div className="flex justify-between border-b border-slate-100 pb-2">
                <dt className="text-slate-500">Base Unit</dt>
                <dd className="font-medium text-slate-900">{product.base_unit}</dd>
              </div>
              {product.auto_created_from && (
                <div className="flex justify-between border-b border-slate-100 pb-2">
                  <dt className="text-slate-500">Auto-created From</dt>
                  <dd className="font-medium text-slate-900">
                    {product.auto_created_from}
                  </dd>
                </div>
              )}
              <div className="flex justify-between">
                <dt className="text-slate-500">Status</dt>
                <dd>
                  <span
                    className={`inline-block rounded-full px-2.5 py-0.5 text-xs font-medium whitespace-nowrap ${
                      !product.is_active
                        ? "bg-slate-200 text-slate-600"
                        : product.status === "draft"
                          ? "bg-amber-100 text-amber-800"
                          : "bg-emerald-100 text-emerald-800"
                    }`}
                  >
                    {!product.is_active
                      ? "Inactive"
                      : product.status === "draft"
                        ? "Draft"
                        : "Active"}
                  </span>
                </dd>
              </div>
            </dl>
          </div>

          <div className="mt-8 grid gap-6 xl:grid-cols-2">
            <div className="rounded-xl border border-slate-200 bg-white shadow-sm">
              <div className="flex items-center justify-between border-b border-slate-100 px-6 py-4">
                <h3 className="font-semibold text-blue-950">Price History</h3>
                <button
                  type="button"
                  onClick={() => openAddHistory("price")}
                  className="text-sm font-medium text-blue-700 hover:text-blue-900"
                >
                  + Add Price
                </button>
              </div>
              <table className="w-full text-left text-sm">
                <thead className="bg-slate-50 text-slate-600">
                  <tr>
                    <th className="px-6 py-2 font-medium">From</th>
                    <th className="px-6 py-2 font-medium">To</th>
                    <th className="px-6 py-2 font-medium">Price</th>
                    <th className="px-6 py-2 font-medium">Unit</th>
                    <th className="px-6 py-2 font-medium"></th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {priceHistory.length === 0 ? (
                    <tr>
                      <td colSpan={5} className="px-6 py-4 text-center text-slate-500">
                        No price history yet.
                      </td>
                    </tr>
                  ) : (
                    priceHistory.map((entry) => (
                      <tr key={entry.id} className="hover:bg-slate-50">
                        <td className="px-6 py-2 text-slate-700">
                          {entry.effective_from}
                        </td>
                        <td className="px-6 py-2 text-slate-700">
                          {entry.effective_to ?? "current"}
                        </td>
                        <td className="px-6 py-2 font-medium text-slate-900">
                          {formatAmount(entry.selling_price)}
                        </td>
                        <td className="px-6 py-2 text-slate-700">{entry.price_unit}</td>
                        <td className="px-6 py-2">
                          <div className="flex items-center gap-2">
                            <button
                              type="button"
                              onClick={() => openEditPrice(entry)}
                              className="text-xs font-medium text-blue-700 hover:text-blue-900"
                            >
                              Edit
                            </button>
                            <button
                              type="button"
                              onClick={() => handleDeleteHistory("price", entry.id)}
                              className="text-xs font-medium text-red-600 hover:text-red-800"
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

            <div className="rounded-xl border border-slate-200 bg-white shadow-sm">
              <div className="flex items-center justify-between border-b border-slate-100 px-6 py-4">
                <h3 className="font-semibold text-blue-950">Cost History</h3>
                <button
                  type="button"
                  onClick={() => openAddHistory("cost")}
                  className="text-sm font-medium text-blue-700 hover:text-blue-900"
                >
                  + Add Cost
                </button>
              </div>
              <table className="w-full text-left text-sm">
                <thead className="bg-slate-50 text-slate-600">
                  <tr>
                    <th className="px-6 py-2 font-medium">From</th>
                    <th className="px-6 py-2 font-medium">To</th>
                    <th className="px-6 py-2 font-medium">Cost</th>
                    <th className="px-6 py-2 font-medium">Unit</th>
                    <th className="px-6 py-2 font-medium"></th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {costHistory.length === 0 ? (
                    <tr>
                      <td colSpan={5} className="px-6 py-4 text-center text-slate-500">
                        No cost history yet.
                      </td>
                    </tr>
                  ) : (
                    costHistory.map((entry) => (
                      <tr key={entry.id} className="hover:bg-slate-50">
                        <td className="px-6 py-2 text-slate-700">
                          {entry.effective_from}
                        </td>
                        <td className="px-6 py-2 text-slate-700">
                          {entry.effective_to ?? "current"}
                        </td>
                        <td className="px-6 py-2 font-medium text-slate-900">
                          {formatAmount(entry.unit_cost)}
                        </td>
                        <td className="px-6 py-2 text-slate-700">{entry.cost_unit}</td>
                        <td className="px-6 py-2">
                          <div className="flex items-center gap-2">
                            <button
                              type="button"
                              onClick={() => openEditCost(entry)}
                              className="text-xs font-medium text-blue-700 hover:text-blue-900"
                            >
                              Edit
                            </button>
                            <button
                              type="button"
                              onClick={() => handleDeleteHistory("cost", entry.id)}
                              className="text-xs font-medium text-red-600 hover:text-red-800"
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
          </div>

          <div className="mt-8 max-w-xl rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
            <h3 className="font-semibold text-blue-950">Aliases</h3>
            <p className="mt-1 text-xs text-slate-500">
              Alternative names used to match this product in sales reports.
            </p>
            {aliases.length === 0 ? (
              <p className="mt-3 text-sm text-slate-500">No aliases yet.</p>
            ) : (
              <ul className="mt-3 divide-y divide-slate-100">
                {aliases.map((alias) => (
                  <li
                    key={alias.id}
                    className="flex items-center justify-between py-2 text-sm"
                  >
                    <span className="text-slate-900">{alias.alias_name}</span>
                    <button
                      type="button"
                      onClick={() => handleDeleteAlias(alias)}
                      className="text-xs font-medium text-red-600 hover:text-red-800"
                    >
                      Delete
                    </button>
                  </li>
                ))}
              </ul>
            )}
            <form onSubmit={handleAddAlias} className="mt-4 flex gap-2">
              <input
                type="text"
                required
                placeholder="New alias name"
                value={newAlias}
                onChange={(e) => setNewAlias(e.target.value)}
                className="flex-1 rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
              />
              <button
                type="submit"
                className="rounded-lg bg-blue-900 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-blue-800"
              >
                Add
              </button>
            </form>
          </div>
        </>
      ) : null}

      <Modal
        isOpen={historyModal !== null}
        onClose={() => setHistoryModal(null)}
        title={
          historyModal?.mode === "edit"
            ? historyModal.kind === "price"
              ? "Edit Price"
              : "Edit Cost"
            : historyModal?.kind === "price"
              ? "Add Price"
              : "Add Cost"
        }
      >
        <form onSubmit={handleHistorySubmit} className="space-y-4">
          {historyModal?.mode === "add" && (
            <div>
              <label
                htmlFor="historyFrom"
                className="block text-sm font-medium text-slate-700"
              >
                Effective From
              </label>
              <input
                id="historyFrom"
                type="date"
                required
                value={historyForm.effective_from}
                onChange={(e) =>
                  setHistoryForm((prev) => ({
                    ...prev,
                    effective_from: e.target.value,
                  }))
                }
                className="mt-1 block w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
              />
            </div>
          )}
          <div>
            <label
              htmlFor="historyTo"
              className="block text-sm font-medium text-slate-700"
            >
              Effective To (leave empty for current)
            </label>
            <input
              id="historyTo"
              type="date"
              value={historyForm.effective_to}
              onChange={(e) =>
                setHistoryForm((prev) => ({ ...prev, effective_to: e.target.value }))
              }
              className="mt-1 block w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
            />
          </div>
          <div>
            <label
              htmlFor="historyValue"
              className="block text-sm font-medium text-slate-700"
            >
              {historyModal?.kind === "price" ? "Selling Price" : "Unit Cost"}
            </label>
            <input
              id="historyValue"
              type="number"
              min={0}
              step="0.01"
              required
              value={historyForm.value}
              onChange={(e) =>
                setHistoryForm((prev) => ({ ...prev, value: e.target.value }))
              }
              className="mt-1 block w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
            />
          </div>
          <div>
            <label
              htmlFor="historyUnit"
              className="block text-sm font-medium text-slate-700"
            >
              Unit
            </label>
            <input
              id="historyUnit"
              type="text"
              required
              value={historyForm.unit}
              onChange={(e) =>
                setHistoryForm((prev) => ({ ...prev, unit: e.target.value }))
              }
              className="mt-1 block w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
            />
          </div>
          <div className="flex gap-3 pt-2">
            <button
              type="submit"
              disabled={saving}
              className="rounded-lg bg-blue-900 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-blue-800 disabled:opacity-50"
            >
              {saving ? "Saving..." : "Save"}
            </button>
            <button
              type="button"
              onClick={() => setHistoryModal(null)}
              className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 transition-colors hover:bg-slate-50"
            >
              Cancel
            </button>
          </div>
        </form>
      </Modal>

      <Modal
        isOpen={isActivateOpen}
        onClose={() => setIsActivateOpen(false)}
        title="Activate Product"
      >
        <form onSubmit={handleActivate} className="space-y-4">
          <p className="text-sm text-slate-600">
            Complete the required fields to activate this draft product.
          </p>
          <div>
            <label
              htmlFor="activateBaseUnit"
              className="block text-sm font-medium text-slate-700"
            >
              Base Unit
            </label>
            <input
              id="activateBaseUnit"
              type="text"
              required
              placeholder="e.g. pcs, kg, L"
              value={activateForm.base_unit}
              onChange={(e) =>
                setActivateForm((prev) => ({ ...prev, base_unit: e.target.value }))
              }
              className="mt-1 block w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
            />
          </div>
          <div>
            <label
              htmlFor="activateName"
              className="block text-sm font-medium text-slate-700"
            >
              Name
            </label>
            <input
              id="activateName"
              type="text"
              value={activateForm.name}
              onChange={(e) =>
                setActivateForm((prev) => ({ ...prev, name: e.target.value }))
              }
              className="mt-1 block w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
            />
          </div>
          <div>
            <label
              htmlFor="activateSku"
              className="block text-sm font-medium text-slate-700"
            >
              SKU
            </label>
            <input
              id="activateSku"
              type="text"
              value={activateForm.sku}
              onChange={(e) =>
                setActivateForm((prev) => ({ ...prev, sku: e.target.value }))
              }
              className="mt-1 block w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
            />
          </div>
          <div>
            <label
              htmlFor="activateCategory"
              className="block text-sm font-medium text-slate-700"
            >
              Category
            </label>
            <input
              id="activateCategory"
              type="text"
              value={activateForm.category}
              onChange={(e) =>
                setActivateForm((prev) => ({ ...prev, category: e.target.value }))
              }
              className="mt-1 block w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
            />
          </div>
          <div className="flex gap-3 pt-2">
            <button
              type="submit"
              disabled={saving}
              className="rounded-lg bg-emerald-700 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-emerald-600 disabled:opacity-50"
            >
              {saving ? "Activating..." : "Activate"}
            </button>
            <button
              type="button"
              onClick={() => setIsActivateOpen(false)}
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
