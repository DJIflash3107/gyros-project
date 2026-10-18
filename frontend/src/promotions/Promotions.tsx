import { useCallback, useEffect, useState } from "react";
import Modal from "../components/Modal";
import SidebarLayout from "../components/SidebarLayout";
import Toast, { type ToastType } from "../components/Toast";
import { useBusiness } from "../context/BusinessContext";
import { ApiError } from "../services/apiClient";
import { listProducts } from "../services/products";
import {
  evaluate,
  generate,
  getPromotion,
  listPromotions,
  updateStatus,
  type PromotionItemInput,
} from "../services/promotions";
import type { Product, PromotionPlan } from "../services/types";

const STATUS_OPTIONS = [
  { value: "", label: "All statuses" },
  { value: "draft", label: "Draft" },
  { value: "approved", label: "Approved" },
  { value: "rejected", label: "Rejected" },
  { value: "archived", label: "Archived" },
];

const TYPE_OPTIONS = [
  { value: "discount", label: "Discount" },
  { value: "bundle", label: "Bundle" },
  { value: "time_limited", label: "Time limited" },
  { value: "bogo", label: "Buy one get one" },
];

const DISCOUNT_TYPE_OPTIONS = [
  { value: "percentage", label: "Percentage" },
  { value: "fixed_amount", label: "Fixed amount" },
  { value: "bundle_price", label: "Bundle price" },
] as const;

function statusBadge(status: string) {
  switch (status) {
    case "approved":
      return "bg-emerald-100 text-emerald-800";
    case "draft":
      return "bg-amber-100 text-amber-800";
    case "rejected":
      return "bg-red-100 text-red-800";
    default:
      return "bg-slate-200 text-slate-600";
  }
}

function formatDate(value: string) {
  return new Date(value).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

function formatMoney(value: number | null) {
  if (value == null) return "—";
  return value.toLocaleString("en-US", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

interface ItemFormRow {
  product_id: number | "";
  discount_type: PromotionItemInput["discount_type"];
  discount_value: string;
  expected_qty: string;
}

const EMPTY_ITEM: ItemFormRow = {
  product_id: "",
  discount_type: "percentage",
  discount_value: "",
  expected_qty: "",
};

export default function Promotions() {
  const { activeBusiness, branches } = useBusiness();
  const [plans, setPlans] = useState<PromotionPlan[]>([]);
  const [products, setProducts] = useState<Product[]>([]);
  const [statusFilter, setStatusFilter] = useState("");
  const [selected, setSelected] = useState<PromotionPlan | null>(null);
  const [modalOpen, setModalOpen] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [evaluating, setEvaluating] = useState(false);
  const [formType, setFormType] = useState("discount");
  const [formBranchId, setFormBranchId] = useState<number | "">("");
  const [formStart, setFormStart] = useState("");
  const [formEnd, setFormEnd] = useState("");
  const [formMinMargin, setFormMinMargin] = useState("");
  const [formItems, setFormItems] = useState<ItemFormRow[]>([{ ...EMPTY_ITEM }]);
  const [toast, setToast] = useState<{
    message: string;
    type: ToastType;
    isOpen: boolean;
  }>({ message: "", type: "success", isOpen: false });

  const showToast = (message: string, type: ToastType = "success") => {
    setToast({ message, type, isOpen: true });
  };

  const closeToast = () => {
    setToast((prev) => ({ ...prev, isOpen: false }));
  };

  const fetchPlans = useCallback(async () => {
    if (!activeBusiness) return;
    try {
      const list = await listPromotions(activeBusiness.id, {
        status: statusFilter || undefined,
        pageSize: 50,
      });
      setPlans(list);
    } catch (err) {
      showToast(
        err instanceof ApiError ? err.message : "Failed to load promotions",
        "error",
      );
    }
  }, [activeBusiness, statusFilter]);

  useEffect(() => {
    queueMicrotask(() => {
      void fetchPlans();
      if (activeBusiness) {
        listProducts(activeBusiness.id, { isActive: true })
          .then(setProducts)
          .catch(() => setProducts([]));
      }
    });
  }, [fetchPlans, activeBusiness]);

  const resetForm = () => {
    setFormType("discount");
    setFormBranchId("");
    setFormStart("");
    setFormEnd("");
    setFormMinMargin("");
    setFormItems([{ ...EMPTY_ITEM }]);
  };

  const handleGenerate = async () => {
    if (!activeBusiness) return;
    if (!formStart || !formEnd) {
      showToast("Start and end dates are required", "error");
      return;
    }
    const items: PromotionItemInput[] = [];
    for (const row of formItems) {
      if (row.product_id === "" || row.discount_value === "") {
        showToast("Each item needs a product and discount value", "error");
        return;
      }
      items.push({
        product_id: row.product_id,
        discount_type: row.discount_type,
        discount_value: Number(row.discount_value),
        ...(row.expected_qty ? { expected_qty: Number(row.expected_qty) } : {}),
      });
    }
    setGenerating(true);
    try {
      const result = await generate(activeBusiness.id, {
        promotion_type: formType as "discount" | "bundle" | "time_limited" | "bogo",
        branch_id: formBranchId === "" ? undefined : formBranchId,
        start_date: formStart,
        end_date: formEnd,
        items,
        ...(formMinMargin ? { min_margin_pct: Number(formMinMargin) } : {}),
      });
      showToast("Promotion proposal generated");
      setModalOpen(false);
      resetForm();
      setSelected(result.plan);
      void fetchPlans();
    } catch (err) {
      showToast(
        err instanceof ApiError ? err.message : "Failed to generate proposal",
        "error",
      );
    } finally {
      setGenerating(false);
    }
  };

  const handleView = async (plan: PromotionPlan) => {
    if (!activeBusiness) return;
    if (selected?.id === plan.id) {
      setSelected(null);
      return;
    }
    try {
      const detail = await getPromotion(activeBusiness.id, plan.id);
      setSelected(detail);
    } catch (err) {
      showToast(
        err instanceof ApiError ? err.message : "Failed to load promotion",
        "error",
      );
    }
  };

  const handleApprove = async (plan: PromotionPlan) => {
    if (!activeBusiness) return;
    try {
      const updated = await updateStatus(activeBusiness.id, plan.id, "approved");
      showToast("Promotion approved");
      setSelected(updated);
      void fetchPlans();
    } catch (err) {
      showToast(
        err instanceof ApiError ? err.message : "Failed to approve",
        "error",
      );
    }
  };

  const handleReject = async (plan: PromotionPlan) => {
    if (!activeBusiness) return;
    const reason = window.prompt("Reason for rejection (required):");
    if (!reason) return;
    try {
      const updated = await updateStatus(
        activeBusiness.id,
        plan.id,
        "rejected",
        reason,
      );
      showToast("Promotion rejected");
      setSelected(updated);
      void fetchPlans();
    } catch (err) {
      showToast(
        err instanceof ApiError ? err.message : "Failed to reject",
        "error",
      );
    }
  };

  const handleEvaluate = async (plan: PromotionPlan) => {
    if (!activeBusiness) return;
    setEvaluating(true);
    try {
      const result = await evaluate(activeBusiness.id, plan.id);
      showToast("Evaluation updated");
      setSelected(result.plan);
      void fetchPlans();
    } catch (err) {
      showToast(
        err instanceof ApiError ? err.message : "Failed to evaluate",
        "error",
      );
    } finally {
      setEvaluating(false);
    }
  };

  const updateItem = (index: number, patch: Partial<ItemFormRow>) => {
    setFormItems((prev) =>
      prev.map((row, i) => (i === index ? { ...row, ...patch } : row)),
    );
  };

  return (
    <SidebarLayout>
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold text-blue-950">Promotions</h2>
          <p className="mt-1 text-slate-600">
            Generate and evaluate promotion proposals.
          </p>
        </div>
        <button
          type="button"
          onClick={() => setModalOpen(true)}
          className="rounded-lg bg-blue-700 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-blue-800"
        >
          Generate proposal
        </button>
      </div>

      <div className="mt-6 rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h3 className="text-lg font-semibold text-blue-950">Plans</h3>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm focus:border-blue-500 focus:outline-none"
          >
            {STATUS_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        </div>

        {plans.length === 0 ? (
          <p className="mt-4 text-sm text-slate-500">
            No promotion plans yet. Click "Generate proposal" to create one.
          </p>
        ) : (
          <ul className="mt-4 space-y-3">
            {plans.map((plan) => (
              <li key={plan.id} className="rounded-lg border border-slate-200">
                <button
                  type="button"
                  onClick={() => handleView(plan)}
                  className="flex w-full flex-wrap items-center justify-between gap-2 p-4 text-left hover:bg-slate-50"
                >
                  <div>
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="font-medium text-blue-950">{plan.title}</p>
                      <span
                        className={`rounded-full px-2 py-0.5 text-xs font-medium ${statusBadge(plan.status)}`}
                      >
                        {plan.status}
                      </span>
                    </div>
                    <p className="mt-1 text-xs text-slate-500">
                      {plan.promotion_type.replace("_", " ")} ·{" "}
                      {formatDate(plan.start_date)} – {formatDate(plan.end_date)}{" "}
                      · {plan.items.length} item
                      {plan.items.length === 1 ? "" : "s"}
                    </p>
                  </div>
                  {plan.is_financially_validated ? (
                    <span className="rounded-full bg-emerald-100 px-2 py-0.5 text-xs font-medium text-emerald-800">
                      Validated
                    </span>
                  ) : (
                    <span className="rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-800">
                      Not validated
                    </span>
                  )}
                </button>

                {selected?.id === plan.id && (
                  <div className="border-t border-slate-200 p-4">
                    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                      <div>
                        <p className="text-xs text-slate-500">
                          Original revenue
                        </p>
                        <p className="text-sm font-semibold text-blue-950">
                          {formatMoney(selected.total_original_revenue)}
                        </p>
                      </div>
                      <div>
                        <p className="text-xs text-slate-500">
                          Discounted revenue
                        </p>
                        <p className="text-sm font-semibold text-blue-950">
                          {formatMoney(selected.total_discounted_revenue)}
                        </p>
                      </div>
                      <div>
                        <p className="text-xs text-slate-500">Estimated cost</p>
                        <p className="text-sm font-semibold text-blue-950">
                          {formatMoney(selected.total_estimated_cost)}
                        </p>
                      </div>
                      <div>
                        <p className="text-xs text-slate-500">
                          Estimated margin
                        </p>
                        <p className="text-sm font-semibold text-blue-950">
                          {formatMoney(selected.total_estimated_margin)}
                          {selected.avg_margin_pct != null &&
                            ` (${selected.avg_margin_pct.toFixed(1)}%)`}
                        </p>
                      </div>
                    </div>

                    <div className="mt-4 overflow-x-auto">
                      <table className="w-full text-sm">
                        <thead>
                          <tr className="border-b border-slate-200 text-left text-xs uppercase tracking-wide text-slate-500">
                            <th className="py-2 pr-4">Product</th>
                            <th className="py-2 pr-4">Discount</th>
                            <th className="py-2 pr-4 text-right">Price</th>
                            <th className="py-2 pr-4 text-right">Margin/unit</th>
                            <th className="py-2 text-right">Contribution</th>
                          </tr>
                        </thead>
                        <tbody>
                          {selected.items.map((item) => (
                            <tr
                              key={item.product_id}
                              className="border-b border-slate-100 last:border-0"
                            >
                              <td className="py-2 pr-4 text-slate-700">
                                {item.product_name}
                              </td>
                              <td className="py-2 pr-4 text-slate-700">
                                {item.discount_type === "percentage"
                                  ? `${item.discount_value}%`
                                  : formatMoney(item.discount_value)}
                              </td>
                              <td className="py-2 pr-4 text-right text-slate-700">
                                {formatMoney(item.discounted_price)}
                              </td>
                              <td className="py-2 pr-4 text-right text-slate-700">
                                {formatMoney(item.margin_per_unit)}
                                {item.margin_pct != null &&
                                  ` (${item.margin_pct.toFixed(1)}%)`}
                              </td>
                              <td className="py-2 text-right font-medium text-blue-950">
                                {formatMoney(item.estimated_contribution)}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>

                    {selected.warnings && selected.warnings.length > 0 && (
                      <div className="mt-3 rounded-lg border border-amber-200 bg-amber-50 px-4 py-2 text-sm text-amber-800">
                        <p className="font-medium">Warnings</p>
                        <ul className="mt-1 list-inside list-disc">
                          {selected.warnings.map((w) => (
                            <li key={w}>{w}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                    {selected.risks && selected.risks.length > 0 && (
                      <div className="mt-3 rounded-lg border border-rose-200 bg-rose-50 px-4 py-2 text-sm text-rose-800">
                        <p className="font-medium">Risks</p>
                        <ul className="mt-1 list-inside list-disc">
                          {selected.risks.map((r) => (
                            <li key={r}>{r}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                    {selected.rationale && (
                      <p className="mt-3 text-sm text-slate-600">
                        {selected.rationale}
                      </p>
                    )}
                    {selected.rejected_reason && (
                      <p className="mt-3 text-sm text-rose-700">
                        Rejected: {selected.rejected_reason}
                      </p>
                    )}

                    <div className="mt-4 flex flex-wrap gap-2">
                      <button
                        type="button"
                        onClick={() => handleEvaluate(selected)}
                        disabled={evaluating}
                        className="rounded-lg border border-slate-300 px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50"
                      >
                        {evaluating ? "Evaluating…" : "Re-evaluate financials"}
                      </button>
                      {selected.status === "draft" && (
                        <>
                          <button
                            type="button"
                            onClick={() => handleApprove(selected)}
                            className="rounded-lg bg-emerald-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-emerald-700"
                          >
                            Approve
                          </button>
                          <button
                            type="button"
                            onClick={() => handleReject(selected)}
                            className="rounded-lg bg-rose-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-rose-700"
                          >
                            Reject
                          </button>
                        </>
                      )}
                    </div>
                  </div>
                )}
              </li>
            ))}
          </ul>
        )}
      </div>

      <Modal
        isOpen={modalOpen}
        onClose={() => setModalOpen(false)}
        title="Generate promotion proposal"
      >
        <div className="mt-4 space-y-4">
          <label className="block">
            <span className="text-sm font-medium text-slate-700">Type</span>
            <select
              value={formType}
              onChange={(e) => setFormType(e.target.value)}
              className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
            >
              {TYPE_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
          </label>
          <label className="block">
            <span className="text-sm font-medium text-slate-700">
              Branch (optional)
            </span>
            <select
              value={formBranchId}
              onChange={(e) =>
                setFormBranchId(
                  e.target.value === "" ? "" : Number(e.target.value),
                )
              }
              className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
            >
              <option value="">All branches</option>
              {branches.map((b) => (
                <option key={b.id} value={b.id}>
                  {b.name}
                </option>
              ))}
            </select>
          </label>
          <div className="grid grid-cols-2 gap-3">
            <label className="block">
              <span className="text-sm font-medium text-slate-700">
                Start date
              </span>
              <input
                type="date"
                value={formStart}
                onChange={(e) => setFormStart(e.target.value)}
                className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
              />
            </label>
            <label className="block">
              <span className="text-sm font-medium text-slate-700">
                End date
              </span>
              <input
                type="date"
                value={formEnd}
                onChange={(e) => setFormEnd(e.target.value)}
                className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
              />
            </label>
          </div>
          <label className="block">
            <span className="text-sm font-medium text-slate-700">
              Minimum margin % (optional)
            </span>
            <input
              type="number"
              min={0}
              max={100}
              value={formMinMargin}
              onChange={(e) => setFormMinMargin(e.target.value)}
              className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
            />
          </label>

          <div>
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium text-slate-700">Items</span>
              <button
                type="button"
                onClick={() =>
                  setFormItems((prev) => [...prev, { ...EMPTY_ITEM }])
                }
                className="text-xs font-medium text-blue-700 hover:text-blue-900"
              >
                + Add item
              </button>
            </div>
            <div className="mt-2 space-y-3">
              {formItems.map((row, index) => (
                <div
                  key={index}
                  className="space-y-2 rounded-lg border border-slate-200 p-3"
                >
                  <div className="flex items-center justify-between gap-2">
                    <select
                      value={row.product_id}
                      onChange={(e) =>
                        updateItem(index, {
                          product_id:
                            e.target.value === ""
                              ? ""
                              : Number(e.target.value),
                        })
                      }
                      className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
                    >
                      <option value="">Select product</option>
                      {products.map((p) => (
                        <option key={p.id} value={p.id}>
                          {p.name}
                        </option>
                      ))}
                    </select>
                    {formItems.length > 1 && (
                      <button
                        type="button"
                        onClick={() =>
                          setFormItems((prev) =>
                            prev.filter((_, i) => i !== index),
                          )
                        }
                        className="text-xs font-medium text-rose-600 hover:text-rose-800"
                      >
                        Remove
                      </button>
                    )}
                  </div>
                  <div className="grid grid-cols-3 gap-2">
                    <select
                      value={row.discount_type}
                      onChange={(e) =>
                        updateItem(index, {
                          discount_type: e.target
                            .value as PromotionItemInput["discount_type"],
                        })
                      }
                      className="rounded-lg border border-slate-300 px-2 py-2 text-sm focus:border-blue-500 focus:outline-none"
                    >
                      {DISCOUNT_TYPE_OPTIONS.map((o) => (
                        <option key={o.value} value={o.value}>
                          {o.label}
                        </option>
                      ))}
                    </select>
                    <input
                      type="number"
                      min={0}
                      placeholder="Value"
                      value={row.discount_value}
                      onChange={(e) =>
                        updateItem(index, { discount_value: e.target.value })
                      }
                      className="rounded-lg border border-slate-300 px-2 py-2 text-sm focus:border-blue-500 focus:outline-none"
                    />
                    <input
                      type="number"
                      min={1}
                      placeholder="Expected qty"
                      value={row.expected_qty}
                      onChange={(e) =>
                        updateItem(index, { expected_qty: e.target.value })
                      }
                      className="rounded-lg border border-slate-300 px-2 py-2 text-sm focus:border-blue-500 focus:outline-none"
                    />
                  </div>
                </div>
              ))}
            </div>
          </div>

          <button
            type="button"
            onClick={handleGenerate}
            disabled={generating}
            className="w-full rounded-lg bg-blue-700 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-blue-800 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {generating ? "Generating…" : "Generate"}
          </button>
        </div>
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
