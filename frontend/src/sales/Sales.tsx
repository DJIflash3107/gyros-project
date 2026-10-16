import { useState } from "react";
import SidebarLayout from "../components/SidebarLayout";
import Modal from "../components/Modal";
import {
  BanknotesIcon,
  FireIcon,
  ChartBarIcon,
  ExclamationTriangleIcon,
  PrinterIcon,
} from "@heroicons/react/24/solid";

interface Sale {
  id: string;
  time: string;
  paymentMethod: string;
  items: { name: string; qty: number; price: number }[];
}

const sales: Sale[] = [
  {
    id: "#1042",
    time: "2026-10-16T09:42:00",
    paymentMethod: "Cash",
    items: [
      { name: "Chicken Gyro", qty: 2, price: 12.0 },
      { name: "Tzatziki Dip", qty: 1, price: 4.5 },
    ],
  },
  {
    id: "#1041",
    time: "2026-10-16T09:28:00",
    paymentMethod: "Card",
    items: [{ name: "Falafel Bowl", qty: 1, price: 12.5 }],
  },
  {
    id: "#1040",
    time: "2026-10-16T09:10:00",
    paymentMethod: "Cash",
    items: [
      { name: "Lamb Gyro", qty: 2, price: 13.75 },
      { name: "Greek Salad", qty: 1, price: 9.0 },
      { name: "Hummus & Pita", qty: 1, price: 7.0 },
    ],
  },
  {
    id: "#1039",
    time: "2026-10-16T08:55:00",
    paymentMethod: "Card",
    items: [{ name: "Hummus & Pita", qty: 1, price: 7.0 }],
  },
  {
    id: "#1038",
    time: "2026-10-16T08:31:00",
    paymentMethod: "Cash",
    items: [
      { name: "Greek Salad", qty: 2, price: 9.0 },
      { name: "Chicken Gyro", qty: 1, price: 12.0 },
    ],
  },
];

const topItems = [
  { name: "Chicken Gyro", sold: 45 },
  { name: "Lamb Gyro", sold: 38 },
  { name: "Greek Salad", sold: 32 },
];
const monthlySales = [
  { day: "1", amount: 320 },
  { day: "5", amount: 450 },
  { day: "10", amount: 390 },
  { day: "15", amount: 520 },
  { day: "20", amount: 610 },
  { day: "25", amount: 480 },
  { day: "30", amount: 560 },
];
const lowStock = [
  { name: "Lamb", left: 12 },
  { name: "Tomatoes", left: 8 },
  { name: "Onions", left: 4 },
];

function formatDateTime(value: string) {
  return new Date(value).toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default function Sales() {
  const [selectedSale, setSelectedSale] = useState<Sale | null>(null);

  const totalRevenue = sales.reduce(
    (sum, sale) =>
      sum + sale.items.reduce((itemSum, item) => itemSum + item.price * item.qty, 0),
    0
  );
  const maxMonthly = Math.max(...monthlySales.map((s) => s.amount));
  const orderTotal = selectedSale
    ? selectedSale.items.reduce((sum, item) => sum + item.price * item.qty, 0)
    : 0;

  return (
    <SidebarLayout>
      <h2 className="text-2xl font-bold text-blue-950">Sales</h2>
      <p className="mt-1 text-slate-600">Sales performance and transactions.</p>

      <div className="mt-6 grid gap-4 xl:grid-cols-4">
        <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-5 shadow-sm">
          <div className="flex items-start justify-between">
            <div>
              <p className="text-sm font-medium text-emerald-700">Sales Today</p>
              <p className="mt-2 text-3xl font-bold text-emerald-900">
                ${totalRevenue.toFixed(2)}
              </p>
              <p className="mt-1 text-xs text-emerald-600">Revenue</p>
            </div>
            <div className="rounded-lg bg-emerald-100 p-2 text-emerald-700">
              <BanknotesIcon className="h-6 w-6" />
            </div>
          </div>
        </div>

        <div className="rounded-xl border border-amber-200 bg-amber-50 p-5 shadow-sm">
          <div className="flex items-start justify-between">
            <div>
              <p className="text-sm font-medium text-amber-700">Top Items This Month</p>
              <ol className="mt-2 list-decimal space-y-1 pl-4 text-sm text-amber-900">
                {topItems.map((item) => (
                  <li key={item.name}>
                    {item.name} — {item.sold} sold
                  </li>
                ))}
              </ol>
            </div>
            <div className="rounded-lg bg-amber-100 p-2 text-amber-700">
              <FireIcon className="h-6 w-6" />
            </div>
          </div>
        </div>

        <div className="rounded-xl border border-blue-200 bg-blue-50 p-5 shadow-sm xl:col-span-1">
          <div className="flex items-start justify-between">
            <p className="text-sm font-medium text-blue-700">Sales This Month</p>
            <div className="rounded-lg bg-blue-100 p-2 text-blue-700">
              <ChartBarIcon className="h-6 w-6" />
            </div>
          </div>
          <div className="mt-4 h-24 w-full">
            <svg className="h-full w-full" preserveAspectRatio="none">
              <polyline
                fill="none"
                stroke="#3b82f6"
                strokeWidth="2"
                points={monthlySales
                  .map((point, index) => {
                    const x = (index / (monthlySales.length - 1)) * 100;
                    const y = 100 - (point.amount / maxMonthly) * 80;
                    return `${x},${y}`;
                  })
                  .join(" ")}
              />
              {monthlySales.map((point, index) => {
                const x = (index / (monthlySales.length - 1)) * 100;
                const y = 100 - (point.amount / maxMonthly) * 80;
                return (
                  <g key={point.day}>
                    <circle cx={`${x}%`} cy={`${y}%`} r="3" fill="#3b82f6" />
                    <text
                      x={`${x}%`}
                      y="98%"
                      textAnchor="middle"
                      className="fill-blue-600 text-[8px]"
                    >
                      {point.day}
                    </text>
                  </g>
                );
              })}
            </svg>
          </div>
        </div>

        <div className="rounded-xl border border-rose-200 bg-rose-50 p-5 shadow-sm">
          <div className="flex items-start justify-between">
            <div>
              <p className="text-sm font-medium text-rose-700">Low in Stock</p>
              <ul className="mt-2 space-y-1 text-sm text-rose-900">
                {lowStock.map((item) => (
                  <li key={item.name}>
                    {item.name} — {item.left} left
                  </li>
                ))}
              </ul>
            </div>
            <div className="rounded-lg bg-rose-100 p-2 text-rose-700">
              <ExclamationTriangleIcon className="h-6 w-6" />
            </div>
          </div>
        </div>
      </div>

      <h3 className="mt-8 text-lg font-semibold text-blue-950">Today&apos;s Orders</h3>
      <div className="mt-4 overflow-x-auto rounded-xl border border-slate-200 bg-white shadow-sm">
        <table className="w-full min-w-[44rem] text-left text-sm">
          <thead className="bg-blue-950 text-white">
            <tr>
              <th className="px-6 py-3 font-medium">Order</th>
              <th className="px-6 py-3 font-medium">Time</th>
              <th className="px-6 py-3 font-medium">Items</th>
              <th className="px-6 py-3 font-medium">Payment</th>
              <th className="px-6 py-3 font-medium">Total</th>
              <th className="px-6 py-3 font-medium">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {sales.map((sale) => {
              const orderTotal = sale.items.reduce(
                (sum, item) => sum + item.price * item.qty,
                0
              );
              return (
                <tr key={sale.id} className="hover:bg-slate-50">
                  <td className="px-6 py-3 font-medium text-blue-900">{sale.id}</td>
                  <td className="px-6 py-3 text-slate-700">{formatDateTime(sale.time)}</td>
                  <td className="px-6 py-3 text-slate-700">
                    <ul className="space-y-0.5">
                      {sale.items.map((item, index) => (
                        <li key={index}>
                          {item.name} x{item.qty}
                        </li>
                      ))}
                    </ul>
                  </td>
                  <td className="px-6 py-3 text-slate-700">{sale.paymentMethod}</td>
                  <td className="px-6 py-3 font-medium text-slate-900">
                    ${orderTotal.toFixed(2)}
                  </td>
                  <td className="px-6 py-3">
                    <button
                      type="button"
                      onClick={() => setSelectedSale(sale)}
                      className="text-sm font-medium text-blue-700 hover:text-blue-900"
                    >
                      View
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <Modal
        isOpen={selectedSale !== null}
        onClose={() => setSelectedSale(null)}
        title={`Order ${selectedSale?.id ?? ""}`}
      >
        {selectedSale && (
          <div className="space-y-4 text-sm text-slate-700">
            <div className="flex items-center justify-between rounded-lg bg-slate-50 p-3">
              <span className="text-slate-500">Date & Time</span>
              <span className="font-medium text-slate-900">
                {formatDateTime(selectedSale.time)}
              </span>
            </div>
            <div className="flex items-center justify-between rounded-lg bg-slate-50 p-3">
              <span className="text-slate-500">Payment</span>
              <span className="font-medium text-slate-900">
                {selectedSale.paymentMethod}
              </span>
            </div>
            <div>
              <p className="mb-2 font-medium text-slate-900">Items</p>
              <ul className="divide-y divide-slate-100 rounded-lg border border-slate-100">
                {selectedSale.items.map((item, index) => (
                  <li
                    key={index}
                    className="flex items-center justify-between px-3 py-2"
                  >
                    <span>
                      {item.name} x{item.qty}
                    </span>
                    <span className="font-medium text-slate-900">
                      ${(item.price * item.qty).toFixed(2)}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
            <div className="flex items-center justify-between rounded-lg bg-blue-50 p-3">
              <span className="font-medium text-blue-900">Total</span>
              <span className="text-lg font-bold text-blue-900">
                ${orderTotal.toFixed(2)}
              </span>
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <button
                type="button"
                onClick={() => setSelectedSale(null)}
                className="rounded-lg border border-slate-200 px-4 py-2 text-slate-700 hover:bg-slate-50"
              >
                Close
              </button>
              <button
                type="button"
                onClick={() => alert("Print receipt (mock)")}
                className="flex items-center gap-2 rounded-lg bg-blue-950 px-4 py-2 text-white hover:bg-blue-900"
              >
                <PrinterIcon className="h-4 w-4" />
                Print
              </button>
            </div>
          </div>
        )}
      </Modal>
    </SidebarLayout>
  );
}
