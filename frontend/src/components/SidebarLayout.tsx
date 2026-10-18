import { useEffect, useState } from "react";
import { NavLink, useLocation, useNavigate } from "react-router-dom";
import {
  HomeIcon,
  ShoppingCartIcon,
  ClipboardDocumentListIcon,
  QueueListIcon,
  Bars3CenterLeftIcon,
  Bars3Icon,
  CalendarIcon,
  ShieldCheckIcon,
  TagIcon,
} from "@heroicons/react/24/outline";
import { useBusiness } from "../context/BusinessContext";
import { clearToken } from "../services/apiClient";
import AgentChatWidget from "./AgentChatWidget";

const nav = [
  { path: "/overview", label: "Overview", Icon: HomeIcon },
  { path: "/daily-record", label: "Daily Record", Icon: CalendarIcon },
  { path: "/inventory", label: "Inventory & Stocks", Icon: ClipboardDocumentListIcon },
  { path: "/sales", label: "Sales", Icon: ShoppingCartIcon },
  { path: "/prep-planner", label: "Prep Planner", Icon: QueueListIcon },
  { path: "/promotions", label: "Promotions", Icon: TagIcon },
  { path: "/data-validation", label: "Data Validation", Icon: ShieldCheckIcon },
];

function getPageTitle(pathname: string) {
  const match = nav.find((item) => item.path === pathname);
  return match?.label ?? "Dashboard";
}

export default function SidebarLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const [isOpen, setIsOpen] = useState(() => {
    const saved = localStorage.getItem("sidebarOpen");
    return saved === null ? true : saved === "true";
  });
  const { pathname } = useLocation();
  const navigate = useNavigate();
  const pageTitle = getPageTitle(pathname);
  const { businesses, activeBusiness, setActiveBusiness, clear } =
    useBusiness();

  const handleLogout = () => {
    clearToken();
    clear();
    navigate("/login");
  };

  const handleBusinessChange = (event: React.ChangeEvent<HTMLSelectElement>) => {
    const value = event.target.value;
    if (value === "new") {
      navigate("/businesses/new");
      return;
    }
    const next = businesses.find((b) => b.id === Number(value));
    if (next) {
      setActiveBusiness(next);
    }
  };

  useEffect(() => {
    localStorage.setItem("sidebarOpen", String(isOpen));
  }, [isOpen]);

  return (
    <div className="flex h-screen overflow-hidden bg-slate-50 text-slate-900">
      <aside
        className={`flex h-full flex-none flex-col bg-blue-950 text-white transition-all duration-300 ${
          isOpen ? "w-64" : "w-20"
        }`}
      >
        <div className={`flex items-center border-b border-blue-900 p-4 ${isOpen ? "justify-between" : "justify-center"}`}>
          {isOpen && (
            <div className="flex items-center gap-3 overflow-hidden">
              <img
                src="/logo.svg"
                alt="GyrosProject"
                className="h-9 w-9 shrink-0"
              />
              <span className="whitespace-nowrap text-lg font-bold tracking-wide">
                GyrosProject
              </span>
            </div>
          )}
          <button
            type="button"
            onClick={() => setIsOpen((prev) => !prev)}
            className="shrink-0 rounded-md p-1 text-blue-200 hover:bg-blue-900 hover:text-white"
            aria-label={isOpen ? "Collapse sidebar" : "Expand sidebar"}
          >
            {isOpen ? (
              <Bars3CenterLeftIcon className="h-5 w-5" />
            ) : (
              <Bars3Icon className="h-5 w-5" />
            )}
          </button>
        </div>
        <nav className={`flex-1 space-y-1 ${isOpen ? "p-3" : "p-2"}`}>
          {nav.map((item) => (
            <NavLink
              key={item.path}
              to={item.path}
              end={item.path === "/"}
              className={({ isActive }) =>
                `flex items-center rounded-lg py-2.5 text-sm font-medium transition-colors ${
                  isOpen ? "gap-3 px-3" : "justify-center px-2"
                } ${
                  isActive
                    ? "bg-blue-800 text-white"
                    : "text-blue-100 hover:bg-blue-900 hover:text-white"
                }`
              }
            >
              <item.Icon className="h-5 w-5 shrink-0" />
              {isOpen && (
                <span className="whitespace-nowrap">
                  {item.label}
                </span>
              )}
            </NavLink>
          ))}
        </nav>
        <div className={`border-t border-blue-900 ${isOpen ? "p-3" : "p-2"}`}>
          {isOpen && (
            <select
              value={activeBusiness?.id ?? ""}
              onChange={handleBusinessChange}
              className="mb-3 w-full rounded-lg border border-blue-800 bg-blue-900 px-2 py-1.5 text-sm text-white focus:outline-none"
            >
              {businesses.map((b) => (
                <option key={b.id} value={b.id}>
                  {b.name}
                </option>
              ))}
              <option value="new">+ New business</option>
            </select>
          )}
          <div className={`flex items-center overflow-hidden ${isOpen ? "gap-3" : "justify-center"}`}>
            <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-blue-800 font-semibold text-sm">
              JD
            </div>
            {isOpen && (
              <div className="min-w-0 flex-1 whitespace-nowrap">
                <p className="truncate text-sm font-medium">John Doe</p>
                <p className="truncate text-xs text-blue-300">Manager</p>
              </div>
            )}
          </div>
        </div>
      </aside>
      <div className="flex h-full flex-1 min-w-0 flex-col overflow-hidden">
        <header className="flex items-center justify-between border-b border-slate-200 bg-white px-8 py-4">
          <h2 className="text-lg font-semibold text-blue-950">{pageTitle}</h2>
          <button
            type="button"
            onClick={handleLogout}
            className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 transition-colors hover:bg-slate-50"
          >
            Log out
          </button>
        </header>
        <main className="flex-1 overflow-y-auto p-8">{children}</main>
      </div>
      <AgentChatWidget />
    </div>
  );
}
