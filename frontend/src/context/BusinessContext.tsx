import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
} from "react";
import { getToken } from "../services/apiClient";
import { listBranches } from "../services/branches";
import { listBusinesses } from "../services/businesses";
import type { Branch, Business } from "../services/types";

const BUSINESS_KEY = "gyros_business_id";

interface BusinessContextValue {
  businesses: Business[];
  branches: Branch[];
  activeBusiness: Business | null;
  loading: boolean;
  error: string | null;
  setActiveBusiness: (business: Business) => void;
  refresh: () => Promise<void>;
  clear: () => void;
}

const BusinessContext = createContext<BusinessContextValue | null>(null);

export function BusinessProvider({ children }: { children: React.ReactNode }) {
  const [businesses, setBusinesses] = useState<Business[]>([]);
  const [branches, setBranches] = useState<Branch[]>([]);
  const [activeBusiness, setActive] = useState<Business | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const list = await listBusinesses();
      setBusinesses(list);

      const savedId = Number(localStorage.getItem(BUSINESS_KEY));
      const active =
        list.find((b) => b.id === savedId) ?? list[0] ?? null;
      setActive(active);

      if (active) {
        localStorage.setItem(BUSINESS_KEY, String(active.id));
        const branchList = await listBranches(active.id);
        setBranches(branchList);
      } else {
        localStorage.removeItem(BUSINESS_KEY);
        setBranches([]);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load businesses");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    // Defer so no setState runs synchronously inside the effect body.
    queueMicrotask(() => {
      if (getToken()) {
        void refresh();
      } else {
        setLoading(false);
      }
    });
  }, [refresh]);

  const setActiveBusiness = useCallback((business: Business) => {
    setActive(business);
    localStorage.setItem(BUSINESS_KEY, String(business.id));
    listBranches(business.id)
      .then(setBranches)
      .catch(() => setBranches([]));
  }, []);

  const clear = useCallback(() => {
    setBusinesses([]);
    setBranches([]);
    setActive(null);
    setError(null);
    setLoading(false);
    localStorage.removeItem(BUSINESS_KEY);
  }, []);

  return (
    <BusinessContext.Provider
      value={{
        businesses,
        branches,
        activeBusiness,
        loading,
        error,
        setActiveBusiness,
        refresh,
        clear,
      }}
    >
      {children}
    </BusinessContext.Provider>
  );
}

// eslint-disable-next-line react-refresh/only-export-components
export function useBusiness(): BusinessContextValue {
  const ctx = useContext(BusinessContext);
  if (!ctx) {
    throw new Error("useBusiness must be used within BusinessProvider");
  }
  return ctx;
}
