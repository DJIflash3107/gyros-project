import { useParams } from "react-router-dom";
import Breadcrumbs from "../components/Breadcrumbs";
import SidebarLayout from "../components/SidebarLayout";

const orders = [
  {
    id: "#1042",
    items: [
      { name: "Chicken Gyro", qty: 2, total: 24.0 },
      { name: "Tzatziki Dip", qty: 1, total: 4.5 },
    ],
    time: "09:42",
  },
  {
    id: "#1041",
    items: [{ name: "Falafel Bowl", qty: 1, total: 12.5 }],
    time: "09:28",
  },
  {
    id: "#1040",
    items: [
      { name: "Lamb Gyro", qty: 2, total: 27.5 },
      { name: "Greek Salad", qty: 1, total: 9.0 },
      { name: "Hummus & Pita", qty: 1, total: 7.0 },
    ],
    time: "09:10",
  },
  {
    id: "#1039",
    items: [{ name: "Hummus & Pita", qty: 1, total: 7.0 }],
    time: "08:55",
  },
  {
    id: "#1038",
    items: [
      { name: "Greek Salad", qty: 2, total: 18.0 },
      { name: "Chicken Gyro", qty: 1, total: 12.0 },
    ],
    time: "08:31",
  },
];

export default function SalesOrderDetail() {
  const { id } = useParams<{ id: string }>();
  const order = orders.find((o) => o.id === id);

  if (!order) {
    return (
      <SidebarLayout>
        <h2 className="text-2xl font-bold text-blue-950">Order Not Found</h2>
        <p className="mt-1 text-slate-600">The requested order does not exist.</p>
      </SidebarLayout>
    );
  }

  const orderTotal = order.items.reduce((sum, item) => sum + item.total, 0);

  return (
    <SidebarLayout>
      <h2 className="text-2xl font-bold text-blue-950">{order.id}</h2>
      <Breadcrumbs
        items={[
          { label: "Sales", to: "/sales" },
          { label: order.id },
        ]}
      />
      <p className="mt-3 text-slate-600">Order details at {order.time}.</p>

      <div className="mt-6 overflow-x-auto rounded-xl border border-slate-200 bg-white shadow-sm">
        <table className="w-full min-w-[28rem] text-left text-sm">
          <thead className="bg-blue-950 text-white">
            <tr>
              <th className="px-6 py-3 font-medium">Item</th>
              <th className="px-6 py-3 font-medium">Quantity</th>
              <th className="px-6 py-3 font-medium">Total</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {order.items.map((item, index) => (
              <tr key={index} className="hover:bg-slate-50">
                <td className="px-6 py-3 text-slate-700">{item.name}</td>
                <td className="px-6 py-3 text-slate-700">{item.qty}</td>
                <td className="px-6 py-3 text-slate-700">
                  ${item.total.toFixed(2)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="mt-6 rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
        <p className="text-sm font-medium text-slate-500">Order Total</p>
        <p className="mt-1 text-3xl font-bold text-blue-900">
          ${orderTotal.toFixed(2)}
        </p>
      </div>
    </SidebarLayout>
  );
}
