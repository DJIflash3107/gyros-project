import { useState } from "react";
import SidebarLayout from "../components/SidebarLayout";
import Toast, { type ToastType } from "../components/Toast";

const products = [
  { id: 1, name: "Chicken Gyro", price: 12.0 },
  { id: 2, name: "Lamb Gyro", price: 13.75 },
  { id: 3, name: "Falafel Bowl", price: 12.5 },
  { id: 4, name: "Hummus & Pita", price: 7.0 },
  { id: 5, name: "Greek Salad", price: 9.0 },
  { id: 6, name: "Tzatziki Dip", price: 4.5 },
];

interface CartItem {
  productId: number;
  name: string;
  price: number;
  qty: number;
}

export default function DailyRecord() {
  const [cart, setCart] = useState<CartItem[]>([]);
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

  const addToCart = (product: (typeof products)[0]) => {
    setCart((prev) => {
      const existing = prev.find((item) => item.productId === product.id);
      if (existing) {
        return prev.map((item) =>
          item.productId === product.id
            ? { ...item, qty: item.qty + 1 }
            : item
        );
      }
      return [...prev, { productId: product.id, name: product.name, price: product.price, qty: 1 }];
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
      prev.map((item) => (item.productId === productId ? { ...item, qty } : item))
    );
  };

  const subtotal = cart.reduce((sum, item) => sum + item.price * item.qty, 0);

  const handleCheckout = () => {
    if (cart.length === 0) {
      showToast("Cart is empty", "error");
      return;
    }
    showToast(`Sale of $${subtotal.toFixed(2)} recorded successfully`);
    setCart([]);
  };

  const handleRecordSpoiled = () => {
    showToast("Spoiled items recorded successfully");
  };

  return (
    <SidebarLayout>
      <h2 className="text-2xl font-bold text-blue-950">Daily Record</h2>
      <p className="mt-1 text-slate-600">Point of sale for today&apos;s transactions.</p>

      <div className="mt-6 grid gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2 space-y-4">
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
                  ${product.price.toFixed(2)}
                </p>
              </button>
            ))}
          </div>

          <button
            type="button"
            onClick={handleRecordSpoiled}
            className="w-full rounded-lg border-2 border-dashed border-red-300 bg-red-50 py-4 text-sm font-semibold text-red-700 transition hover:bg-red-100"
          >
            Record Spoiled Items
          </button>
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
                  className="flex items-center justify-between text-sm"
                >
                  <div className="flex-1">
                    <p className="font-medium text-slate-900">{item.name}</p>
                    <p className="text-slate-500">${item.price.toFixed(2)} each</p>
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
            onClick={handleCheckout}
            className="mt-6 w-full rounded-lg bg-blue-900 py-3 text-sm font-semibold text-white transition hover:bg-blue-800"
          >
            Record Sale
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
