import { useCallback, useEffect, useMemo, useState } from "react";
import SidebarLayout from "../components/SidebarLayout";
import Toast, { type ToastType } from "../components/Toast";
import { useBusiness } from "../context/BusinessContext";
import { ApiError } from "../services/apiClient";
import { createExpense } from "../services/expenses";
import { listProductPriceHistory, listProducts } from "../services/products";
import { batchForm } from "../services/salesSubmissions";
import type { ManualFormRowInput, Product } from "../services/types";

interface CartItem {
  productId: number;
  name: string;
  price: number;
  qty: number;
}

interface ExpenseFormData {
  expense_date: string;
  category: string;
  description: string;
  amount: string;
}

function todayString() {
  return new Date().toISOString().slice(0, 10);
}

export default function DailyRecord() {
  const { activeBusiness, branches } = useBusiness();
  const [products, setProducts] = useState<Product[]>([]);
  const [prices, setPrices] = useState<Record<number, number>>({});
  const [cart, setCart] = useState<CartItem[]>([]);
  const [branchId, setBranchId] = useState<number | null>(null);
  const [recordDate, setRecordDate] = useState(todayString());
  const [expenseForm, setExpenseForm] = useState<ExpenseFormData>({
    expense_date: todayString(),
    category: "",
    description: "",
    amount: "",
  });
  const [submitting, setSubmitting] = useState(false);
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
      const [productList, priceHistory] = await Promise.all([
        listProducts(activeBusiness.id, { isActive: true, status: "active" }),
        listProductPriceHistory(activeBusiness.id),
      ]);
      setProducts(productList);

      // Latest open-ended price per product (effective_to == null).
      const current: Record<number, number> = {};
      const sorted = [...priceHistory].sort((a, b) =>
        a.effective_from.localeCompare(b.effective_from),
      );
      for (const entry of sorted) {
        if (entry.effective_to == null) {
          current[entry.product_id] = Number(entry.selling_price);
        }
      }
      setPrices(current);
    } catch (err) {
      showToast(
        err instanceof ApiError ? err.message : "Failed to load products",
        "error",
      );
    }
  }, [activeBusiness]);

  useEffect(() => {
    // Defer so no setState runs synchronously inside the effect body.
    queueMicrotask(() => {
      void fetchProducts();
    });
  }, [fetchProducts]);

  const effectiveBranchId =
    branchId ?? (branches.length > 0 ? branches[0].id : null);

  const addToCart = (product: Product) => {
    setCart((prev) => {
      const existing = prev.find((item) => item.productId === product.id);
      if (existing) {
        return prev.map((item) =>
          item.productId === product.id
            ? { ...item, qty: item.qty + 1 }
            : item,
        );
      }
      return [
        ...prev,
        {
          productId: product.id,
          name: product.name,
          price: prices[product.id] ?? 0,
          qty: 1,
        },
      ];
    });
  };

  const removeFromCart = (productId: number) => {
    setCart((prev) => prev.filter((item) => item.productId !== productId));
  };

  const updateQty = (productId: number, qty: number) => {
    if (qty <= 0) {
      removeFromCart(productId);
      return;
    }
    setCart((prev) =>
      prev.map((item) => (item.productId === productId ? { ...item, qty } : item)),
    );
  };

  const updatePrice = (productId: number, price: number) => {
    setCart((prev) =>
      prev.map((item) =>
        item.productId === productId ? { ...item, price } : item,
      ),
    );
  };

  const subtotal = cart.reduce((sum, item) => sum + item.price * item.qty, 0);

  const canSubmit = useMemo(
    () => cart.length > 0 && effectiveBranchId != null && !submitting,
    [cart.length, effectiveBranchId, submitting],
  );

  const submitCart = async (kind: "sale" | "spoiled") => {
    if (!activeBusiness || cart.length === 0) {
      showToast("Cart is empty", "error");
      return;
    }
    if (effectiveBranchId == null) {
      showToast("Select a branch first", "error");
      return;
    }
    setSubmitting(true);
    try {
      const rows: ManualFormRowInput[] = cart.map((item) => ({
        raw_product_name: item.name,
        branch_id: effectiveBranchId,
        product_id: item.productId,
        period_start: recordDate,
        period_end: recordDate,
        granularity: "daily",
        ...(kind === "sale"
          ? {
              sold_qty: item.qty,
              recorded_revenue: Number((item.price * item.qty).toFixed(2)),
            }
          : { spoiled_qty: item.qty }),
      }));
      const result = await batchForm(activeBusiness.id, {
        report_period_type: "daily",
        coverage_start: recordDate,
        coverage_end: recordDate,
        branch_id: effectiveBranchId,
        rows,
      });
      showToast(
        kind === "sale"
          ? `Sale of $${subtotal.toFixed(2)} recorded (submission #${result.submission.id})`
          : `Spoiled items recorded (submission #${result.submission.id})`,
      );
      setCart([]);
    } catch (err) {
      showToast(
        err instanceof ApiError ? err.message : "Failed to record",
        "error",
      );
    } finally {
      setSubmitting(false);
    }
  };

  const handleExpenseSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!activeBusiness) return;
    setSubmitting(true);
    try {
      await createExpense(activeBusiness.id, {
        branch_id: effectiveBranchId,
        expense_date: expenseForm.expense_date,
        category: expenseForm.category,
        description: expenseForm.description || null,
        amount: expenseForm.amount,
      });
      showToast("Expense recorded");
      setExpenseForm({
        expense_date: recordDate,
        category: "",
        description: "",
        amount: "",
      });
    } catch (err) {
      showToast(
        err instanceof ApiError ? err.message : "Failed to record expense",
        "error",
      );
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <SidebarLayout>
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold text-blue-950">Daily Record</h2>
          <p className="mt-1 text-slate-600">
            Record today&apos;s sales, spoiled items, and expenses.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <div>
            <label
              htmlFor="recordDate"
              className="block text-xs font-medium text-slate-500"
            >
              Date
            </label>
            <input
              id="recordDate"
              type="date"
              value={recordDate}
              onChange={(e) => setRecordDate(e.target.value)}
              className="mt-1 rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
            />
          </div>
          <div>
            <label
              htmlFor="recordBranch"
              className="block text-xs font-medium text-slate-500"
            >
              Branch
            </label>
            <select
              id="recordBranch"
              value={effectiveBranchId ?? ""}
              onChange={(e) => setBranchId(Number(e.target.value))}
              className="mt-1 rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
            >
              {branches.length === 0 && <option value="">No branches</option>}
              {branches.map((branch) => (
                <option key={branch.id} value={branch.id}>
                  {branch.name}
                </option>
              ))}
            </select>
          </div>
        </div>
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2 space-y-4">
          {products.length === 0 ? (
            <p className="rounded-xl border border-slate-200 bg-white p-6 text-sm text-slate-500 shadow-sm">
              No active products yet. Add products on the Inventory page first.
            </p>
          ) : (
            <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
              {products.map((product) => (
                <button
                  key={product.id}
                  type="button"
                  onClick={() => addToCart(product)}
                  className="rounded-xl border border-slate-200 bg-white p-5 text-left shadow-sm transition hover:border-blue-300 hover:shadow-md"
                >
                  <p className="font-semibold text-blue-950">{product.name}</p>
                  <p className="mt-1 text-sm text-slate-600">
                    {prices[product.id] != null
                      ? `$${prices[product.id].toFixed(2)}`
                      : "No price set"}
                  </p>
                </button>
              ))}
            </div>
          )}

          <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
            <h3 className="font-semibold text-blue-950">Record Expense</h3>
            <form
              onSubmit={handleExpenseSubmit}
              className="mt-4 grid gap-4 sm:grid-cols-2"
            >
              <div>
                <label
                  htmlFor="expenseDate"
                  className="block text-sm font-medium text-slate-700"
                >
                  Date
                </label>
                <input
                  id="expenseDate"
                  type="date"
                  required
                  value={expenseForm.expense_date}
                  onChange={(e) =>
                    setExpenseForm((prev) => ({
                      ...prev,
                      expense_date: e.target.value,
                    }))
                  }
                  className="mt-1 block w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
                />
              </div>
              <div>
                <label
                  htmlFor="expenseCategory"
                  className="block text-sm font-medium text-slate-700"
                >
                  Category
                </label>
                <input
                  id="expenseCategory"
                  type="text"
                  required
                  placeholder="e.g. Ingredients, Rent"
                  value={expenseForm.category}
                  onChange={(e) =>
                    setExpenseForm((prev) => ({ ...prev, category: e.target.value }))
                  }
                  className="mt-1 block w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
                />
              </div>
              <div>
                <label
                  htmlFor="expenseAmount"
                  className="block text-sm font-medium text-slate-700"
                >
                  Amount
                </label>
                <input
                  id="expenseAmount"
                  type="number"
                  min={0}
                  step="0.01"
                  required
                  value={expenseForm.amount}
                  onChange={(e) =>
                    setExpenseForm((prev) => ({ ...prev, amount: e.target.value }))
                  }
                  className="mt-1 block w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
                />
              </div>
              <div>
                <label
                  htmlFor="expenseDescription"
                  className="block text-sm font-medium text-slate-700"
                >
                  Description
                </label>
                <input
                  id="expenseDescription"
                  type="text"
                  value={expenseForm.description}
                  onChange={(e) =>
                    setExpenseForm((prev) => ({
                      ...prev,
                      description: e.target.value,
                    }))
                  }
                  className="mt-1 block w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
                />
              </div>
              <div className="sm:col-span-2">
                <button
                  type="submit"
                  disabled={submitting}
                  className="rounded-lg bg-blue-900 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-blue-800 disabled:opacity-50"
                >
                  {submitting ? "Saving..." : "Add Expense"}
                </button>
              </div>
            </form>
          </div>
        </div>

        <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <h3 className="text-lg font-semibold text-blue-950">Current Order</h3>

          {cart.length === 0 ? (
            <p className="mt-4 text-sm text-slate-500">No items added yet.</p>
          ) : (
            <ul className="mt-4 space-y-3">
              {cart.map((item) => (
                <li
                  key={item.productId}
                  className="flex items-center justify-between gap-2 text-sm"
                >
                  <div className="flex-1">
                    <p className="font-medium text-slate-900">{item.name}</p>
                    <div className="mt-0.5 flex items-center gap-1 text-slate-500">
                      <span>$</span>
                      <input
                        type="number"
                        min={0}
                        step="0.01"
                        value={item.price}
                        onChange={(e) =>
                          updatePrice(item.productId, Number(e.target.value))
                        }
                        aria-label={`Price for ${item.name}`}
                        className="w-20 rounded border border-slate-200 px-1 py-0.5 text-xs focus:border-blue-500 focus:outline-none"
                      />
                      <span>each</span>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      onClick={() => updateQty(item.productId, item.qty - 1)}
                      className="flex h-7 w-7 items-center justify-center rounded-md border border-slate-300 text-slate-600 hover:bg-slate-50"
                    >
                      -
                    </button>
                    <span className="w-6 text-center">{item.qty}</span>
                    <button
                      type="button"
                      onClick={() => updateQty(item.productId, item.qty + 1)}
                      className="flex h-7 w-7 items-center justify-center rounded-md border border-slate-300 text-slate-600 hover:bg-slate-50"
                    >
                      +
                    </button>
                  </div>
                </li>
              ))}
            </ul>
          )}

          <div className="mt-6 border-t border-slate-100 pt-4">
            <div className="flex items-center justify-between text-base font-semibold text-slate-900">
              <span>Total</span>
              <span>${subtotal.toFixed(2)}</span>
            </div>
          </div>

          <button
            type="button"
            onClick={() => submitCart("sale")}
            disabled={!canSubmit}
            className="mt-6 w-full rounded-lg bg-blue-900 py-3 text-sm font-semibold text-white transition hover:bg-blue-800 disabled:opacity-50"
          >
            {submitting ? "Recording..." : "Record Sale"}
          </button>
          <button
            type="button"
            onClick={() => submitCart("spoiled")}
            disabled={!canSubmit}
            className="mt-3 w-full rounded-lg border-2 border-dashed border-red-300 bg-red-50 py-3 text-sm font-semibold text-red-700 transition hover:bg-red-100 disabled:opacity-50"
          >
            Record as Spoiled Items
          </button>
        </div>
      </div>

      <Toast
        message={toast.message}
        type={toast.type}
        isOpen={toast.isOpen}
        onClose={closeToast}
      />
    </SidebarLayout>
  );
}
