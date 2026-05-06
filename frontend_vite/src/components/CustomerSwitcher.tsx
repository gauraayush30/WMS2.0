import { useEffect, useState } from "react";
import { Users } from "lucide-react";

import { API, useAuth } from "../context/AuthContext";

interface Customer {
  id: number;
  name: string;
  code: string;
  is_active: boolean;
}

/**
 * Top-bar customer filter for warehouse roles. Customer roles never see this
 * — the backend forces their own customer_id regardless of the query param.
 */
export default function CustomerSwitcher() {
  const { authFetch, isWarehouse, selectedCustomerId, setSelectedCustomerId } =
    useAuth();
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!isWarehouse) return;
    let mounted = true;
    authFetch(`${API}/customers`)
      .then((r) => (r.ok ? r.json() : { customers: [] }))
      .then((data) => {
        if (!mounted) return;
        setCustomers(data.customers || []);
      })
      .finally(() => mounted && setLoading(false));
    return () => {
      mounted = false;
    };
  }, [authFetch, isWarehouse]);

  if (!isWarehouse) return null;

  return (
    <div className="flex items-center gap-2 text-sm">
      <Users size={14} className="text-muted-foreground" />
      <select
        className="flex h-8 w-44 rounded-md border border-input bg-transparent px-3 py-1 text-xs shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
        value={selectedCustomerId === null ? "ALL" : String(selectedCustomerId)}
        onChange={(e) =>
          setSelectedCustomerId(
            e.target.value === "ALL" ? null : Number(e.target.value)
          )
        }
      >
        <option value="ALL">All customers</option>
        {customers.map((c) => (
          <option key={c.id} value={String(c.id)}>
            {c.name} {c.code ? `(${c.code})` : ""}
          </option>
        ))}
        {!loading && customers.length === 0 && (
          <option disabled>No customers yet</option>
        )}
      </select>
    </div>
  );
}
