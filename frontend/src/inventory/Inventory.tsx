import { useState } from "react";
import Modal from "../components/Modal";
import SidebarLayout from "../components/SidebarLayout";
import Toast, { type ToastType } from "../components/Toast";

const inventory = [
  { id: 1, name: "Pita Bread", category: "Bakery", quantity: 120, price: 1.5, cost: 0.8, status: "In Stock" },
  { id: 2, name: "Chicken", category: "Protein", quantity: 35, price: 8.0, cost: 4.5, status: "In Stock" },
  { id: 3, name: "Lamb", category: "Protein", quantity: 12, price: 9.5, cost: 5.0, status: "Low Stock" },
  { id: 4, name: "Tzatziki", category: "Sauce", quantity: 10, price: 3.0, cost: 1.2, status: "In Stock" },
  { id: 5, name: "Tomatoes", category: "Produce", quantity: 8, price: 2.5, cost: 1.0, status: "Low Stock" },
  { id: 6, name: "Onions", category: "Produce", quantity: 4, price: 1.75, cost: 0.6, status: "Low Stock" },
  { id: 7, name: "Falafel Mix", category: "Dry Goods", quantity: 25, price: 5.0, cost: 2.0, status: "In Stock" },
  { id: 8, name: "Hummus", category: "Prepared", quantity: 18, price: 4.0, cost: 1.5, status: "In Stock" },
];

type ModalMode = "updateStock" | "addProduct" | "editProduct";

interface ProductFormData {
  name: string;
  category: string;
  quantity: string;
  price: string;
  cost: string;
}

export default function Inventory() {
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [modalMode, setModalMode] = useState<ModalMode>("updateStock");
  const [selectedProduct, setSelectedProduct] = useState<ProductFormData>({
    name: "",
    category: "",
    quantity: "",
    price: "",
    cost: "",
  });
  const [updateMode, setUpdateMode] = useState<"replace" | "add">("replace");
  const [stockValue, setStockValue] = useState("");
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

  const handleDelete = () => {
    showToast("Product deleted successfully");
  };

  const openUpdateStock = (name: string) => {
    setSelectedProduct({ name, category: "", quantity: "", price: "", cost: "" });
    setUpdateMode("replace");
    setStockValue("");
    setModalMode("updateStock");
    setIsModalOpen(true);
  };

  const openAddProduct = () => {
    setSelectedProduct({ name: "", category: "", quantity: "", price: "", cost: "" });
    setModalMode("addProduct");
    setIsModalOpen(true);
  };

  const openEditProduct = (item: (typeof inventory)[0]) => {
    setSelectedProduct({
      name: item.name,
      category: item.category,
      quantity: String(item.quantity),
      price: String(item.price),
      cost: String(item.cost),
    });
    setModalMode("editProduct");
    setIsModalOpen(true);
  };

  const handleUpdateStock = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    showToast(`Stock updated: ${selectedProduct.name} ${updateMode} ${stockValue} pcs`);
    setIsModalOpen(false);
  };

  const handleProductForm = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (modalMode === "addProduct") {
      showToast(`Added product: ${selectedProduct.name}`);
    } else {
      showToast(`Updated product: ${selectedProduct.name}`);
    }
    setIsModalOpen(false);
  };

  return (
    <SidebarLayout>
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-blue-950">Inventory & Stocks</h2>
          <p className="mt-1 text-slate-600">Current stock levels and status.</p>
        </div>
        <button
          type="button"
          onClick={openAddProduct}
          className="rounded-lg bg-blue-900 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-blue-800"
        >
          Add Product
        </button>
      </div>

      <div className="mt-6 overflow-x-auto rounded-xl border border-slate-200 bg-white shadow-sm">
        <table className="w-full min-w-[44rem] text-left text-sm">
          <thead className="bg-blue-950 text-white">
            <tr>
              <th className="px-6 py-3 font-medium">Product</th>
              <th className="px-6 py-3 font-medium">Category</th>
              <th className="px-6 py-3 font-medium">Quantity</th>
              <th className="px-6 py-3 font-medium">Price</th>
              <th className="px-6 py-3 font-medium">Profit</th>
              <th className="px-6 py-3 font-medium">Status</th>
              <th className="px-6 py-3 font-medium">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {inventory.map((item) => (
              <tr key={item.id} className="hover:bg-slate-50">
                <td className="px-6 py-3 font-medium text-blue-900">{item.name}</td>
                <td className="px-6 py-3 text-slate-700">{item.category}</td>
                <td className="px-6 py-3 text-slate-700">{item.quantity} pcs</td>
                <td className="px-6 py-3 text-slate-700">${item.price.toFixed(2)}</td>
                <td className="px-6 py-3 text-emerald-700">${(item.price - item.cost).toFixed(2)}</td>
                <td className="px-6 py-3">
                  <span
                    className={`inline-block rounded-full px-2.5 py-0.5 text-xs font-medium whitespace-nowrap ${
                      item.status === "In Stock"
                        ? "bg-emerald-100 text-emerald-800"
                        : "bg-amber-100 text-amber-800"
                    }`}
                  >
                    {item.status}
                  </span>
                </td>
                <td className="px-6 py-3">
                  <div className="flex items-center gap-3">
                    <button
                      type="button"
                      onClick={() => openUpdateStock(item.name)}
                      className="text-sm font-medium text-emerald-700 hover:text-emerald-900"
                    >
                      Update Stock
                    </button>
                    <button
                      type="button"
                      onClick={() => openEditProduct(item)}
                      className="text-sm font-medium text-blue-700 hover:text-blue-900"
                    >
                      Edit
                    </button>
                    <button
                      type="button"
                      onClick={handleDelete}
                      className="text-sm font-medium text-red-600 hover:text-red-800"
                    >
                      Delete
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <Modal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        title={
          modalMode === "updateStock"
            ? `Update Stock: ${selectedProduct.name}`
            : modalMode === "addProduct"
              ? "Add Product"
              : "Edit Product"
        }
      >
        {modalMode === "updateStock" ? (
          <form onSubmit={handleUpdateStock} className="space-y-4">
            <div className="flex rounded-lg border border-slate-200 p-1">
              <button
                type="button"
                onClick={() => setUpdateMode("replace")}
                className={`flex-1 rounded-md py-2 text-sm font-medium transition-colors ${
                  updateMode === "replace"
                    ? "bg-blue-900 text-white"
                    : "text-slate-600 hover:bg-slate-50"
                }`}
              >
                Replace
              </button>
              <button
                type="button"
                onClick={() => setUpdateMode("add")}
                className={`flex-1 rounded-md py-2 text-sm font-medium transition-colors ${
                  updateMode === "add"
                    ? "bg-blue-900 text-white"
                    : "text-slate-600 hover:bg-slate-50"
                }`}
              >
                Add
              </button>
            </div>
            <div>
              <label
                htmlFor="stockValue"
                className="block text-sm font-medium text-slate-700"
              >
                {updateMode === "replace" ? "New Stock Quantity" : "Quantity to Add"}
              </label>
              <input
                id="stockValue"
                type="number"
                min={0}
                required
                value={stockValue}
                onChange={(e) => setStockValue(e.target.value)}
                className="mt-1 block w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
              />
            </div>
            <div className="flex gap-3 pt-2">
              <button
                type="submit"
                className="rounded-lg bg-blue-900 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-blue-800"
              >
                Update Stock
              </button>
              <button
                type="button"
                onClick={() => setIsModalOpen(false)}
                className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 transition-colors hover:bg-slate-50"
              >
                Cancel
              </button>
            </div>
          </form>
        ) : (
          <form onSubmit={handleProductForm} className="space-y-4">
            <div>
              <label
                htmlFor="productName"
                className="block text-sm font-medium text-slate-700"
              >
                Product Name
              </label>
              <input
                id="productName"
                type="text"
                required
                value={selectedProduct.name}
                onChange={(e) =>
                  setSelectedProduct((prev) => ({ ...prev, name: e.target.value }))
                }
                className="mt-1 block w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
              />
            </div>
            <div>
              <label
                htmlFor="productCategory"
                className="block text-sm font-medium text-slate-700"
              >
                Category
              </label>
              <input
                id="productCategory"
                type="text"
                required
                value={selectedProduct.category}
                onChange={(e) =>
                  setSelectedProduct((prev) => ({ ...prev, category: e.target.value }))
                }
                className="mt-1 block w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
              />
            </div>
            {modalMode === "addProduct" && (
              <div>
                <label
                  htmlFor="productQuantity"
                  className="block text-sm font-medium text-slate-700"
                >
                  Quantity (pcs)
                </label>
                <input
                  id="productQuantity"
                  type="number"
                  min={0}
                  required
                  value={selectedProduct.quantity}
                  onChange={(e) =>
                    setSelectedProduct((prev) => ({ ...prev, quantity: e.target.value }))
                  }
                  className="mt-1 block w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
                />
              </div>
            )}
            <div>
              <label
                htmlFor="productPrice"
                className="block text-sm font-medium text-slate-700"
              >
                Selling Price
              </label>
              <input
                id="productPrice"
                type="number"
                min={0}
                step="0.01"
                required
                value={selectedProduct.price}
                onChange={(e) =>
                  setSelectedProduct((prev) => ({ ...prev, price: e.target.value }))
                }
                className="mt-1 block w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
              />
            </div>
            <div>
              <label
                htmlFor="productCost"
                className="block text-sm font-medium text-slate-700"
              >
                Cost Price
              </label>
              <input
                id="productCost"
                type="number"
                min={0}
                step="0.01"
                required
                value={selectedProduct.cost}
                onChange={(e) =>
                  setSelectedProduct((prev) => ({ ...prev, cost: e.target.value }))
                }
                className="mt-1 block w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
              />
            </div>
            <div className="flex gap-3 pt-2">
              <button
                type="submit"
                className="rounded-lg bg-blue-900 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-blue-800"
              >
                {modalMode === "addProduct" ? "Add Product" : "Save Changes"}
              </button>
              <button
                type="button"
                onClick={() => setIsModalOpen(false)}
                className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 transition-colors hover:bg-slate-50"
              >
                Cancel
              </button>
            </div>
          </form>
        )}
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
