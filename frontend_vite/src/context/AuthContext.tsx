import {
  createContext,
  useContext,
  useState,
  useCallback,
  useEffect,
  type ReactNode,
} from "react";

interface User {
  id: number | string;
  username: string;
  name: string;
  email: string;
  business_id: number | null;
  customer_id: number | null;
  role: string; // warehouse_admin | warehouse_staff | customer_admin | customer_staff
}

export type Role =
  | "warehouse_admin"
  | "warehouse_staff"
  | "customer_admin"
  | "customer_staff";

interface AuthContextType {
  user: User | null;
  token: string | null;
  authLoading: boolean;
  /** Selected customer_id filter for warehouse roles. null = all customers. */
  selectedCustomerId: number | null;
  setSelectedCustomerId: (id: number | null) => void;
  /** Selected warehouse_id filter. null = all warehouses. */
  selectedWarehouseId: number | null;
  setSelectedWarehouseId: (id: number | null) => void;
  /** Convenience: the customer_id to apply to data queries (forced for customer roles). */
  effectiveCustomerId: number | null;
  isWarehouse: boolean;
  isCustomer: boolean;
  isWarehouseAdmin: boolean;
  isCustomerAdmin: boolean;
  login: (email: string, password: string) => Promise<User>;
  register: (
    username: string,
    name: string,
    email: string,
    password: string,
    businessName?: string,
    businessLocation?: string,
  ) => Promise<User>;
  logout: () => void;
  authFetch: (url: string, options?: RequestInit) => Promise<Response>;
  updateUser: (u: User) => void;
}

const AuthContext = createContext<AuthContextType | null>(null);

const API = "http://127.0.0.1:8000";

export { API };

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(() => {
    const saved = localStorage.getItem("wms_user");
    return saved ? (JSON.parse(saved) as User) : null;
  });
  const [token, setToken] = useState<string | null>(() =>
    localStorage.getItem("wms_token"),
  );
  const [authLoading] = useState(false);

  const [selectedCustomerId, setSelectedCustomerIdState] = useState<number | null>(() => {
    const v = localStorage.getItem("wms_selected_customer_id");
    return v ? Number(v) : null;
  });
  const setSelectedCustomerId = useCallback((id: number | null) => {
    if (id === null) localStorage.removeItem("wms_selected_customer_id");
    else localStorage.setItem("wms_selected_customer_id", String(id));
    setSelectedCustomerIdState(id);
  }, []);

  const [selectedWarehouseId, setSelectedWarehouseIdState] = useState<number | null>(() => {
    const v = localStorage.getItem("wms_selected_warehouse_id");
    return v ? Number(v) : null;
  });
  const setSelectedWarehouseId = useCallback((id: number | null) => {
    if (id === null) localStorage.removeItem("wms_selected_warehouse_id");
    else localStorage.setItem("wms_selected_warehouse_id", String(id));
    setSelectedWarehouseIdState(id);
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const res = await fetch(`${API}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || "Login failed");
    }
    const data = await res.json();
    localStorage.setItem("wms_token", data.access_token);
    localStorage.setItem("wms_user", JSON.stringify(data.user));
    setToken(data.access_token);
    setUser(data.user);
    return data.user;
  }, []);

  const register = useCallback(
    async (
      username: string,
      name: string,
      email: string,
      password: string,
      businessName = "",
      businessLocation = "",
    ) => {
      const res = await fetch(`${API}/auth/register`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          username,
          name,
          email,
          password,
          business_name: businessName,
          business_location: businessLocation,
        }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || "Registration failed");
      }
      const data = await res.json();
      localStorage.setItem("wms_token", data.access_token);
      localStorage.setItem("wms_user", JSON.stringify(data.user));
      setToken(data.access_token);
      setUser(data.user);
      return data.user;
    },
    [],
  );

  const logout = useCallback(() => {
    localStorage.removeItem("wms_token");
    localStorage.removeItem("wms_user");
    setToken(null);
    setUser(null);
  }, []);

  const authFetch = useCallback(
    async (url: string, options: RequestInit = {}) => {
      const res = await fetch(url, {
        ...options,
        headers: {
          "Content-Type": "application/json",
          ...((options.headers as Record<string, string>) || {}),
          Authorization: `Bearer ${token}`,
        },
      });
      if (res.status === 401) {
        localStorage.removeItem("wms_token");
        localStorage.removeItem("wms_user");
        setToken(null);
        setUser(null);
      }
      return res;
    },
    [token],
  );

  const updateUser = useCallback((u: User) => {
    localStorage.setItem("wms_user", JSON.stringify(u));
    setUser(u);
  }, []);

  /* Refresh user data from server on mount to keep role/business_id in sync */
  useEffect(() => {
    if (!token) return;
    fetch(`${API}/auth/me`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((r) => {
        if (!r.ok) throw new Error("Unauthorized");
        return r.json();
      })
      .then((freshUser: User) => {
        localStorage.setItem("wms_user", JSON.stringify(freshUser));
        setUser(freshUser);
      })
      .catch(() => {
        /* token expired or invalid – leave as-is, will 401 on next authFetch */
      });
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const role = (user?.role || "") as Role | "";
  const isWarehouse = role === "warehouse_admin" || role === "warehouse_staff";
  const isCustomer = role === "customer_admin" || role === "customer_staff";
  const isWarehouseAdmin = role === "warehouse_admin";
  const isCustomerAdmin = role === "customer_admin";

  // Customer users can never override the customer filter — it is forced to
  // their own customer_id by the backend, but we mirror it here so UI
  // components that read effectiveCustomerId don't need to know the role.
  const effectiveCustomerId = isCustomer ? (user?.customer_id ?? null) : selectedCustomerId;

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        authLoading,
        selectedCustomerId,
        setSelectedCustomerId,
        selectedWarehouseId,
        setSelectedWarehouseId,
        effectiveCustomerId,
        isWarehouse,
        isCustomer,
        isWarehouseAdmin,
        isCustomerAdmin,
        login,
        register,
        logout,
        authFetch,
        updateUser,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
