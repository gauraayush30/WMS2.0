import {
  createContext,
  useContext,
  useState,
  useCallback,
  type ReactNode,
} from "react";

interface User {
  id: number | string;
  name: string;
  email: string;
}

interface AuthContextType {
  user: User | null;
  token: string | null;
  authLoading: boolean;
  login: (email: string, password: string) => Promise<User>;
  register: (name: string, email: string, password: string) => Promise<User>;
  logout: () => void;
  authFetch: (url: string, options?: RequestInit) => Promise<Response>;
}

const AuthContext = createContext<AuthContextType | null>(null);

const API = "http://127.0.0.1:8000";

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(() => {
    const saved = localStorage.getItem("wms_user");
    return saved ? (JSON.parse(saved) as User) : null;
  });
  const [token, setToken] = useState<string | null>(() =>
    localStorage.getItem("wms_token"),
  );
  const [authLoading] = useState(false); // localStorage is synchronous

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
    async (name: string, email: string, password: string) => {
      const res = await fetch(`${API}/auth/register`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, email, password }),
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
    (url: string, options: RequestInit = {}) =>
      fetch(url, {
        ...options,
        headers: {
          "Content-Type": "application/json",
          ...((options.headers as Record<string, string>) || {}),
          Authorization: `Bearer ${token}`,
        },
      }),
    [token],
  );

  return (
    <AuthContext.Provider
      value={{ user, token, authLoading, login, register, logout, authFetch }}
    >
      {children}
    </AuthContext.Provider>
  );
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAuth() {
  return useContext(AuthContext);
}
