import { useParams } from "react-router-dom";
import Breadcrumbs from "../components/Breadcrumbs";
import SidebarLayout from "../components/SidebarLayout";

const inventory = [
  { id: 1, name: "Pita Bread", category: "Bakery", quantity: 120, unit: "pcs", status: "In Stock" },
  { id: 2, name: "Chicken", category: "Protein", quantity: 35, unit: "kg", status: "In Stock" },
  { id: 3, name: "Lamb", category: "Protein", quantity: 12, unit: "kg", status: "Low Stock" },
  { id: 4, name: "Tzatziki", category: "Sauce", quantity: 10, unit: "L", status: "In Stock" },
  { id: 5, name: "Tomatoes", category: "Produce", quantity: 8, unit: "kg", status: "Low Stock" },
  { id: 6, name: "Onions", category: "Produce", quantity: 4, unit: "kg", status: "Low Stock" },
  { id: 7, name: "Falafel Mix", category: "Dry Goods", quantity: 25, unit: "kg", status: "In Stock" },
  { id: 8, name: "Hummus", category: "Prepared", quantity: 18, unit: "kg", status: "In Stock" },
];

export default function InventoryDetail() {
  const { id } = useParams<{ id: string }>();
  const product = inventory.find((item) => item.id === Number(id));

  if (!product) {
    return (
      <SidebarLayout>
        <h2 className="text-2xl font-bold text-blue-950">Product Not Found</h2>
        <p className="mt-1 text-slate-600">The requested product does not exist.</p>
      </SidebarLayout>
    );
  }

  return (
    <SidebarLayout>
      <h2 className="text-2xl font-bold text-blue-950">{product.name}</h2>
      <Breadcrumbs
        items={[
          { label: "Inventory", to: "/inventory" },
          { label: product.name },
        ]}
      />
      <p className="mt-3 text-slate-600">Product details and stock information.</p>

      <div className="mt-6 max-w-xl rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
        <dl className="space-y-3 text-sm">
          <div className="flex justify-between border-b border-slate-100 pb-2">
            <dt className="text-slate-500">Category</dt>
            <dd className="font-medium text-slate-900">{product.category}</dd>
          </div>
          <div className="flex justify-between border-b border-slate-100 pb-2">
            <dt className="text-slate-500">Quantity</dt>
            <dd className="font-medium text-slate-900">
              {product.quantity} {product.unit}
            </dd>
          </div>
          <div className="flex justify-between">
            <dt className="text-slate-500">Status</dt>
            <dd>
              <span
                className={`inline-block rounded-full px-2.5 py-0.5 text-xs font-medium whitespace-nowrap ${
                  product.status === "In Stock"
                    ? "bg-emerald-100 text-emerald-800"
                    : "bg-amber-100 text-amber-800"
                }`}
              >
                {product.status}
              </span>
            </dd>
          </div>
        </dl>
      </div>
    </SidebarLayout>
  );
}
