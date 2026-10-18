import { useCallback, useEffect, useState } from "react";
import SidebarLayout from "../components/SidebarLayout";
import Toast, { type ToastType } from "../components/Toast";
import { useBusiness } from "../context/BusinessContext";
import { ApiError } from "../services/apiClient";
import {
  getRun,
  listRuns,
  predict,
  sufficiency,
} from "../services/forecasting";
import { listProducts } from "../services/products";
import type {
  DataSufficiency,
  ForecastRun,
  Product,
} from "../services/types";

function formatDate(value: string) {
  return new Date(value).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
  });
}

function formatDateTime(value: string) {
  return new Date(value).toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default function PrepPlanner() {
  const { activeBusiness, branches } = useBusiness();
  const [products, setProducts] = useState<Product[]>([]);
  const [branchId, setBranchId] = useState<number | "">("");
  const [productId, setProductId] = useState<number | "">("");
  const [horizonDays, setHorizonDays] = useState(7);
  const [sufficiencyData, setSufficiencyData] =
    useState<DataSufficiency | null>(null);
  const [sufficiencyError, setSufficiencyError] = useState<string | null>(null);
  const [forecast, setForecast] = useState<ForecastRun | null>(null);
  const [runs, setRuns] = useState<ForecastRun[]>([]);
  const [running, setRunning] = useState(false);
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

  useEffect(() => {
    queueMicrotask(() => {
      if (!activeBusiness) return;
      listProducts(activeBusiness.id, { isActive: true })
        .then(setProducts)
        .catch(() => setProducts([]));
    });
  }, [activeBusiness]);

  const fetchRuns = useCallback(async () => {
    if (!activeBusiness) return;
    try {
      const list = await listRuns(activeBusiness.id, {
        branchId: branchId === "" ? undefined : branchId,
        productId: productId === "" ? undefined : productId,
        pageSize: 20,
      });
      setRuns(list);
    } catch {
      setRuns([]);
    }
  }, [activeBusiness, branchId, productId]);

  useEffect(() => {
    queueMicrotask(() => {
      void fetchRuns();
    });
  }, [fetchRuns]);

  useEffect(() => {
    queueMicrotask(() => {
      setForecast(null);
      setSufficiencyData(null);
      setSufficiencyError(null);
      if (!activeBusiness || branchId === "" || productId === "") return;
      sufficiency(activeBusiness.id, branchId, productId)
        .then(setSufficiencyData)
        .catch((err) =>
          setSufficiencyError(
            err instanceof ApiError
              ? err.message
              : "Failed to check data sufficiency",
          ),
        );
    });
  }, [activeBusiness, branchId, productId]);

  const handleRunForecast = async () => {
    if (!activeBusiness || branchId === "" || productId === "") return;
    setRunning(true);
    try {
      const run = await predict(activeBusiness.id, {
        branch_id: branchId,
        product_id: productId,
        horizon_days: horizonDays,
      });
      setForecast(run);
      showToast("Forecast generated");
      void fetchRuns();
    } catch (err) {
      showToast(
        err instanceof ApiError ? err.message : "Failed to run forecast",
        "error",
      );
    } finally {
      setRunning(false);
    }
  };

  const handleViewRun = async (runId: number) => {
    if (!activeBusiness) return;
    try {
      const run = await getRun(activeBusiness.id, runId);
      setForecast(run);
      window.scrollTo({ top: 0, behavior: "smooth" });
    } catch (err) {
      showToast(
        err instanceof ApiError ? err.message : "Failed to load run",
        "error",
      );
    }
  };

  const productName = (id: number) =>
    products.find((p) => p.id === id)?.name ?? `#${id}`;

  const totalPredicted = forecast
    ? forecast.predictions.reduce((sum, p) => sum + Number(p.predicted_qty), 0)
    : 0;

  return (
    <SidebarLayout>
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold text-blue-950">Prep Planner</h2>
          <p className="mt-1 text-slate-600">
            Forecast demand and plan preparation.
          </p>
        </div>
      </div>

      <div className="mt-6 rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
        <h3 className="text-lg font-semibold text-blue-950">Run a forecast</h3>
        <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <label className="block">
            <span className="text-sm font-medium text-slate-700">Branch</span>
            <select
              value={branchId}
              onChange={(e) =>
                setBranchId(e.target.value === "" ? "" : Number(e.target.value))
              }
              className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
            >
              <option value="">Select branch</option>
              {branches.map((b) => (
                <option key={b.id} value={b.id}>
                  {b.name}
                </option>
              ))}
            </select>
          </label>
          <label className="block">
            <span className="text-sm font-medium text-slate-700">Product</span>
            <select
              value={productId}
              onChange={(e) =>
                setProductId(
                  e.target.value === "" ? "" : Number(e.target.value),
                )
              }
              className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
            >
              <option value="">Select product</option>
              {products.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
          </label>
          <label className="block">
            <span className="text-sm font-medium text-slate-700">
              Horizon (days)
            </span>
            <input
              type="number"
              min={1}
              max={90}
              value={horizonDays}
              onChange={(e) =>
                setHorizonDays(Math.max(1, Number(e.target.value) || 1))
              }
              className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
            />
          </label>
          <div className="flex items-end">
            <button
              type="button"
              onClick={handleRunForecast}
              disabled={running || branchId === "" || productId === ""}
              className="w-full rounded-lg bg-blue-700 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-blue-800 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {running ? "Running…" : "Run forecast"}
            </button>
          </div>
        </div>

        {sufficiencyError && (
          <p className="mt-4 rounded-lg border border-rose-200 bg-rose-50 px-4 py-2 text-sm text-rose-700">
            {sufficiencyError}
          </p>
        )}
        {sufficiencyData && (
          <div
            className={`mt-4 rounded-lg border px-4 py-3 text-sm ${
              sufficiencyData.supports_baseline
                ? "border-emerald-200 bg-emerald-50 text-emerald-800"
                : "border-amber-200 bg-amber-50 text-amber-800"
            }`}
          >
            <p className="font-medium">
              {sufficiencyData.supports_baseline
                ? "Sufficient data"
                : "Insufficient data"}
            </p>
            <p className="mt-0.5">{sufficiencyData.message}</p>
            <p className="mt-1 text-xs opacity-80">
              {sufficiencyData.total_observations} observations ·{" "}
              {sufficiencyData.distinct_weekdays} distinct weekdays
              {sufficiencyData.supports_weekday
                ? " · weekday patterns supported"
                : ""}
            </p>
          </div>
        )}
      </div>

      {forecast && (
        <div className="mt-6 rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h3 className="text-lg font-semibold text-blue-950">
              Forecast: {productName(forecast.product_id)}
            </h3>
            <div className="flex items-center gap-2">
              {!forecast.is_reliable && (
                <span className="rounded-full bg-amber-100 px-3 py-1 text-xs font-medium text-amber-800">
                  Low reliability
                </span>
              )}
              <span className="rounded-full bg-blue-100 px-3 py-1 text-xs font-medium text-blue-800">
                Total: {totalPredicted.toFixed(1)}
              </span>
            </div>
          </div>
          {forecast.reliability_note && (
            <p className="mt-2 text-sm text-amber-700">
              {forecast.reliability_note}
            </p>
          )}
          <div className="mt-3 flex flex-wrap gap-4 text-xs text-slate-500">
            <span>Method: {forecast.method}</span>
            <span>{forecast.observations_used} observations used</span>
            {forecast.wape != null && (
              <span>WAPE: {(forecast.wape * 100).toFixed(1)}%</span>
            )}
            {forecast.mae != null && <span>MAE: {forecast.mae.toFixed(2)}</span>}
          </div>
          <div className="mt-4 overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-200 text-left text-xs uppercase tracking-wide text-slate-500">
                  <th className="py-2 pr-4">Date</th>
                  <th className="py-2 text-right">Predicted qty</th>
                </tr>
              </thead>
              <tbody>
                {forecast.predictions.map((p) => (
                  <tr
                    key={p.forecast_date}
                    className="border-b border-slate-100 last:border-0"
                  >
                    <td className="py-2 pr-4 text-slate-700">
                      {formatDate(p.forecast_date)}
                    </td>
                    <td className="py-2 text-right font-medium text-blue-950">
                      {Number(p.predicted_qty).toFixed(1)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      <div className="mt-6 rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
        <h3 className="text-lg font-semibold text-blue-950">Past runs</h3>
        {runs.length === 0 ? (
          <p className="mt-3 text-sm text-slate-500">No forecast runs yet.</p>
        ) : (
          <ul className="mt-3 divide-y divide-slate-100">
            {runs.map((run) => (
              <li key={run.id}>
                <button
                  type="button"
                  onClick={() => handleViewRun(run.id)}
                  className="flex w-full items-center justify-between gap-4 py-3 text-left hover:bg-slate-50"
                >
                  <div>
                    <p className="text-sm font-medium text-blue-950">
                      {productName(run.product_id)} · {run.horizon_days}-day
                      horizon
                    </p>
                    <p className="text-xs text-slate-500">
                      {formatDateTime(run.created_at)} · {run.method}
                    </p>
                  </div>
                  {!run.is_reliable && (
                    <span className="rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-800">
                      Low reliability
                    </span>
                  )}
                </button>
              </li>
            ))}
          </ul>
        )}
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
