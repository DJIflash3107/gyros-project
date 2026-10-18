import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import SidebarLayout from "../components/SidebarLayout";
import Toast, { type ToastType } from "../components/Toast";
import { useBusiness } from "../context/BusinessContext";
import { ApiError } from "../services/apiClient";
import { generateReport } from "../services/artifacts";
import { deleteExpense, listExpenses } from "../services/expenses";
import { listSubmissions } from "../services/salesSubmissions";
import type { Expense, SalesReportSubmission, SubmissionStatus } from "../services/types";

const STATUS_OPTIONS: { value: "" | SubmissionStatus; label: string }[] = [
  { value: "", label: "All statuses" },
  { value: "pending", label: "Pending" },
  { value: "processing", label: "Processing" },
  { value: "reviewed", label: "Reviewed" },
  { value: "confirmed", label: "Confirmed" },
  { value: "rejected", label: "Rejected" },
  { value: "failed", label: "Failed" },
];

function statusBadge(status: string) {
  switch (status) {
    case "confirmed":
      return "bg-emerald-100 text-emerald-800";
    case "reviewed":
      return "bg-blue-100 text-blue-800";
    case "pending":
    case "processing":
      return "bg-amber-100 text-amber-800";
    case "rejected":
    case "failed":
      return "bg-red-100 text-red-800";
    default:
      return "bg-slate-200 text-slate-600";
  }
}

function formatDateTime(value: string) {
  return new Date(value).toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default function Sales() {
  const { activeBusiness, branches } = useBusiness();
  const [submissions, setSubmissions] = useState<SalesReportSubmission[]>([]);
  const [expenses, setExpenses] = useState<Expense[]>([]);
  const [statusFilter, setStatusFilter] = useState("");
  const [categoryFilter, setCategoryFilter] = useState("");
  const [loading, setLoading] = useState(true);
  const [exporting, setExporting] = useState(false);
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

  const branchName = useCallback(
    (branchId: number | null) =>
      branchId == null
        ? "—"
        : (branches.find((b) => b.id === branchId)?.name ?? `#${branchId}`),
    [branches],
  );

  const fetchAll = useCallback(async () => {
    if (!activeBusiness) return;
    try {
      const [{ submissions: submissionList }, expenseList] = await Promise.all([
        listSubmissions(activeBusiness.id, {
          status: statusFilter || undefined,
          pageSize: 100,
        }),
        listExpenses(activeBusiness.id, {
          category: categoryFilter || undefined,
        }),
      ]);
      setSubmissions(submissionList);
      setExpenses(expenseList);
    } catch (err) {
      showToast(
        err instanceof ApiError ? err.message : "Failed to load records",
        "error",
      );
    } finally {
      setLoading(false);
    }
  }, [activeBusiness, statusFilter, categoryFilter]);

  useEffect(() => {
    // Defer so no setState runs synchronously inside the effect body.
    queueMicrotask(() => {
      void fetchAll();
    });
  }, [fetchAll]);

  const expenseCategories = Array.from(
    new Set(expenses.map((e) => e.category)),
  ).sort();

  const handleDeleteExpense = async (expense: Expense) => {
    if (!activeBusiness) return;
    if (
      !window.confirm(
        `Delete expense "${expense.category}" of $${Number(expense.amount).toFixed(2)}?`,
      )
    )
      return;
    try {
      await deleteExpense(activeBusiness.id, expense.id);
      showToast("Expense deleted");
      await fetchAll();
    } catch (err) {
      showToast(
        err instanceof ApiError ? err.message : "Failed to delete expense",
        "error",
      );
    }
  };

  const handleExport = async () => {
    if (!activeBusiness) return;
    setExporting(true);
    try {
      await generateReport(activeBusiness.id, {
        report_type: "sales_summary",
        file_format: "xlsx",
      });
      showToast("Report generated — download it from Overview");
    } catch (err) {
      showToast(
        err instanceof ApiError ? err.message : "Failed to generate report",
        "error",
      );
    } finally {
      setExporting(false);
    }
  };

  return (
    <SidebarLayout>
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold text-blue-950">Sales</h2>
          <p className="mt-1 text-slate-600">
            Sales report submissions and expense records.
          </p>
        </div>
        <button
          type="button"
          onClick={handleExport}
          disabled={exporting}
          className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 transition-colors hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {exporting ? "Exporting…" : "Export report"}
        </button>
      </div>

      <div className="mt-6 flex items-center justify-between">
        <h3 className="text-lg font-semibold text-blue-950">
          Submission History
        </h3>
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
        >
          {STATUS_OPTIONS.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      </div>

      <div className="mt-4 overflow-x-auto rounded-xl border border-slate-200 bg-white shadow-sm">
        <table className="w-full min-w-[44rem] text-left text-sm">
          <thead className="bg-blue-950 text-white">
            <tr>
              <th className="px-6 py-3 font-medium">Submission</th>
              <th className="px-6 py-3 font-medium">Branch</th>
              <th className="px-6 py-3 font-medium">Period</th>
              <th className="px-6 py-3 font-medium">Input</th>
              <th className="px-6 py-3 font-medium">Rows</th>
              <th className="px-6 py-3 font-medium">Status</th>
              <th className="px-6 py-3 font-medium">Created</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {loading ? (
              <tr>
                <td colSpan={7} className="px-6 py-8 text-center text-slate-500">
                  Loading submissions...
                </td>
              </tr>
            ) : submissions.length === 0 ? (
              <tr>
                <td colSpan={7} className="px-6 py-8 text-center text-slate-500">
                  No submissions yet.
                </td>
              </tr>
            ) : (
              submissions.map((submission) => (
                <tr key={submission.id} className="hover:bg-slate-50">
                  <td className="px-6 py-3 font-medium text-blue-900">
                    <Link
                      to={`/data-validation?submission=${submission.id}`}
                      className="hover:underline"
                    >
                      #{submission.id}
                    </Link>
                  </td>
                  <td className="px-6 py-3 text-slate-700">
                    {branchName(submission.branch_id)}
                  </td>
                  <td className="px-6 py-3 text-slate-700 whitespace-nowrap">
                    {submission.coverage_start === submission.coverage_end
                      ? submission.coverage_start
                      : `${submission.coverage_start} → ${submission.coverage_end}`}
                  </td>
                  <td className="px-6 py-3 text-slate-700 capitalize">
                    {submission.input_method}
                  </td>
                  <td className="px-6 py-3 text-slate-700">
                    {submission.accepted_rows}/{submission.total_rows} accepted
                    {submission.rejected_rows > 0 &&
                      `, ${submission.rejected_rows} rejected`}
                  </td>
                  <td className="px-6 py-3">
                    <span
                      className={`inline-block rounded-full px-2.5 py-0.5 text-xs font-medium whitespace-nowrap capitalize ${statusBadge(submission.status)}`}
                    >
                      {submission.status}
                    </span>
                  </td>
                  <td className="px-6 py-3 text-slate-700 whitespace-nowrap">
                    {formatDateTime(submission.created_at)}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      <div className="mt-8 flex items-center justify-between">
        <h3 className="text-lg font-semibold text-blue-950">Expenses</h3>
        <select
          value={categoryFilter}
          onChange={(e) => setCategoryFilter(e.target.value)}
          className="rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
        >
          <option value="">All categories</option>
          {expenseCategories.map((category) => (
            <option key={category} value={category}>
              {category}
            </option>
          ))}
        </select>
      </div>

      <div className="mt-4 overflow-x-auto rounded-xl border border-slate-200 bg-white shadow-sm">
        <table className="w-full min-w-[40rem] text-left text-sm">
          <thead className="bg-blue-950 text-white">
            <tr>
              <th className="px-6 py-3 font-medium">Date</th>
              <th className="px-6 py-3 font-medium">Branch</th>
              <th className="px-6 py-3 font-medium">Category</th>
              <th className="px-6 py-3 font-medium">Description</th>
              <th className="px-6 py-3 font-medium">Amount</th>
              <th className="px-6 py-3 font-medium">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {loading ? (
              <tr>
                <td colSpan={6} className="px-6 py-8 text-center text-slate-500">
                  Loading expenses...
                </td>
              </tr>
            ) : expenses.length === 0 ? (
              <tr>
                <td colSpan={6} className="px-6 py-8 text-center text-slate-500">
                  No expenses recorded yet.
                </td>
              </tr>
            ) : (
              expenses.map((expense) => (
                <tr key={expense.id} className="hover:bg-slate-50">
                  <td className="px-6 py-3 text-slate-700 whitespace-nowrap">
                    {expense.expense_date}
                  </td>
                  <td className="px-6 py-3 text-slate-700">
                    {branchName(expense.branch_id)}
                  </td>
                  <td className="px-6 py-3 font-medium text-slate-900">
                    {expense.category}
                  </td>
                  <td className="px-6 py-3 text-slate-700">
                    {expense.description ?? "—"}
                  </td>
                  <td className="px-6 py-3 font-medium text-slate-900">
                    {expense.currency} {Number(expense.amount).toFixed(2)}
                  </td>
                  <td className="px-6 py-3">
                    <button
                      type="button"
                      onClick={() => handleDeleteExpense(expense)}
                      className="text-sm font-medium text-red-600 hover:text-red-800"
                    >
                      Delete
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
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
