import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { PlusIcon, TrashIcon } from "@heroicons/react/24/outline";
import SidebarLayout from "../components/SidebarLayout";
import Breadcrumbs from "../components/Breadcrumbs";
import { useBusiness } from "../context/BusinessContext";
import { ApiError } from "../services/apiClient";
import { batchForm } from "../services/salesSubmissions";
import type {
  Granularity,
  ManualFormRowInput,
  ReportPeriodType,
} from "../services/types";

interface EntryRow {
  raw_product_name: string;
  sold_qty: string;
  recorded_revenue: string;
}

const EMPTY_ROW: EntryRow = {
  raw_product_name: "",
  sold_qty: "",
  recorded_revenue: "",
};

function firstDayOfCurrentMonth(): string {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-01`;
}

function today(): string {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`;
}

export default function ManualEntry() {
  const navigate = useNavigate();
  const { activeBusiness, branches } = useBusiness();
  const [branchId, setBranchId] = useState<string>("");
  const [periodType, setPeriodType] = useState<ReportPeriodType>("monthly");
  const [coverageStart, setCoverageStart] = useState(firstDayOfCurrentMonth());
  const [coverageEnd, setCoverageEnd] = useState(today());
  const [rows, setRows] = useState<EntryRow[]>([{ ...EMPTY_ROW }]);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const updateRow = (index: number, field: keyof EntryRow, value: string) => {
    setRows((prev) =>
      prev.map((row, i) => (i === index ? { ...row, [field]: value } : row)),
    );
  };

  const addRow = () => setRows((prev) => [...prev, { ...EMPTY_ROW }]);

  const removeRow = (index: number) =>
    setRows((prev) => prev.filter((_, i) => i !== index));

  const effectiveBranchId =
    branchId || (branches.length === 1 ? String(branches[0].id) : "");

  const handleSubmit = async () => {
    if (!activeBusiness) return;
    if (!effectiveBranchId) {
      setError("Select a branch.");
      return;
    }
    const filled = rows.filter((row) => row.raw_product_name.trim() !== "");
    if (filled.length === 0) {
      setError("Add at least one product row.");
      return;
    }

    setSubmitting(true);
    setError(null);
    try {
      const granularity: Granularity =
        periodType === "custom_range" ? "custom_range" : periodType;
      const payloadRows: ManualFormRowInput[] = filled.map((row) => ({
        raw_product_name: row.raw_product_name.trim(),
        branch_id: Number(effectiveBranchId),
        period_start: coverageStart,
        period_end: coverageEnd,
        granularity,
        sold_qty: row.sold_qty.trim() === "" ? null : Number(row.sold_qty),
        recorded_revenue:
          row.recorded_revenue.trim() === ""
            ? null
            : Number(row.recorded_revenue),
      }));

      const result = await batchForm(activeBusiness.id, {
        report_period_type: periodType,
        coverage_start: coverageStart,
        coverage_end: coverageEnd,
        branch_id: Number(effectiveBranchId),
        rows: payloadRows,
      });
      navigate(`/data-validation?submission=${result.submission.id}`);
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : "Failed to submit entries",
      );
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <SidebarLayout>
      <Breadcrumbs
        items={[
          { label: "Data Validation", to: "/data-validation" },
          { label: "Manual Entry" },
        ]}
      />
      <div className="mt-2">
        <h2 className="text-2xl font-bold text-blue-950">Manual Entry</h2>
        <p className="mt-1 text-slate-600">
          Enter sales rows manually; they are staged for review like file
          uploads.
        </p>
      </div>

      <div className="mt-6 rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="grid gap-4 sm:grid-cols-4">
          <label className="block text-sm">
            <span className="font-medium text-slate-700">Branch</span>
            <select
              value={effectiveBranchId}
              onChange={(e) => setBranchId(e.target.value)}
              className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
            >
              <option value="">Select branch…</option>
              {branches.map((branch) => (
                <option key={branch.id} value={branch.id}>
                  {branch.name}
                </option>
              ))}
            </select>
          </label>
          <label className="block text-sm">
            <span className="font-medium text-slate-700">Period type</span>
            <select
              value={periodType}
              onChange={(e) => setPeriodType(e.target.value as ReportPeriodType)}
              className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
            >
              <option value="daily">Daily</option>
              <option value="weekly">Weekly</option>
              <option value="monthly">Monthly</option>
              <option value="custom_range">Custom range</option>
            </select>
          </label>
          <label className="block text-sm">
            <span className="font-medium text-slate-700">Coverage start</span>
            <input
              type="date"
              value={coverageStart}
              onChange={(e) => setCoverageStart(e.target.value)}
              className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
            />
          </label>
          <label className="block text-sm">
            <span className="font-medium text-slate-700">Coverage end</span>
            <input
              type="date"
              value={coverageEnd}
              onChange={(e) => setCoverageEnd(e.target.value)}
              className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
            />
          </label>
        </div>
      </div>

      <div className="mt-6 rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold text-blue-950">Rows</h3>
          <button
            type="button"
            onClick={addRow}
            className="inline-flex items-center gap-1 rounded-lg bg-slate-100 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-200"
          >
            <PlusIcon className="h-4 w-4" />
            Add row
          </button>
        </div>
        <div className="mt-4 overflow-x-auto">
          <table className="w-full min-w-[36rem] text-left text-sm">
            <thead className="bg-slate-100 text-slate-700">
              <tr>
                <th className="px-3 py-2 font-medium">Product name</th>
                <th className="px-3 py-2 font-medium">Sold qty</th>
                <th className="px-3 py-2 font-medium">Revenue</th>
                <th className="px-3 py-2 font-medium" />
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {rows.map((row, index) => (
                <tr key={index}>
                  <td className="px-3 py-2">
                    <input
                      value={row.raw_product_name}
                      onChange={(e) =>
                        updateRow(index, "raw_product_name", e.target.value)
                      }
                      placeholder="e.g. Lamb Wrap"
                      className="w-full rounded border border-slate-200 px-2 py-1 focus:border-blue-500 focus:outline-none"
                    />
                  </td>
                  <td className="px-3 py-2">
                    <input
                      type="number"
                      value={row.sold_qty}
                      onChange={(e) =>
                        updateRow(index, "sold_qty", e.target.value)
                      }
                      className="w-24 rounded border border-slate-200 px-2 py-1 focus:border-blue-500 focus:outline-none"
                    />
                  </td>
                  <td className="px-3 py-2">
                    <input
                      type="number"
                      value={row.recorded_revenue}
                      onChange={(e) =>
                        updateRow(index, "recorded_revenue", e.target.value)
                      }
                      className="w-28 rounded border border-slate-200 px-2 py-1 focus:border-blue-500 focus:outline-none"
                    />
                  </td>
                  <td className="px-3 py-2">
                    <button
                      type="button"
                      onClick={() => removeRow(index)}
                      disabled={rows.length === 1}
                      className="text-rose-600 hover:text-rose-700 disabled:opacity-30"
                    >
                      <TrashIcon className="h-4 w-4" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {error && (
          <p className="mt-4 rounded-lg bg-rose-50 px-4 py-2 text-sm text-rose-700">
            {error}
          </p>
        )}

        <div className="mt-6 flex justify-end gap-2">
          <button
            type="button"
            onClick={() => navigate("/data-validation/upload")}
            className="rounded-lg bg-slate-100 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-200"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={handleSubmit}
            disabled={submitting || !activeBusiness}
            className="rounded-lg bg-blue-950 px-4 py-2 text-sm font-medium text-white hover:bg-blue-900 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {submitting ? "Submitting…" : "Submit for review"}
          </button>
        </div>
      </div>
    </SidebarLayout>
  );
}
