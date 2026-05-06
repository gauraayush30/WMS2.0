import { useEffect, useState } from "react";

import { API, useAuth } from "../context/AuthContext";
import WarehouseDashboard from "./dashboard/WarehouseDashboard";
import CustomerDashboard from "./dashboard/CustomerDashboard";
import { Skeleton } from "@/components/ui/skeleton";

interface CustomerLite {
  id: number;
  name: string;
  code: string;
}

/**
 * Role-aware dashboard router:
 *
 *   warehouse_*    → WarehouseDashboard (cross-customer)
 *      ↳ + selectedCustomerId set → CustomerDashboard (drill-in view)
 *   customer_*     → CustomerDashboard scoped to ctx.customer_id
 */
export default function DashboardPage() {
  const {
    authFetch,
    isWarehouse,
    isCustomer,
    user,
    selectedCustomerId,
  } = useAuth();
  const [customers, setCustomers] = useState<CustomerLite[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let mounted = true;
    authFetch(`${API}/customers`)
      .then((r) => (r.ok ? r.json() : { customers: [] }))
      .then((d) => {
        if (mounted) setCustomers(d.customers || []);
      })
      .finally(() => mounted && setLoading(false));
    return () => {
      mounted = false;
    };
  }, [authFetch]);

  if (loading) {
    return (
      <div className="space-y-6 p-6">
        <Skeleton className="h-8 w-64" />
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {Array.from({ length: 8 }).map((_, i) => (
            <Skeleton key={i} className="h-24" />
          ))}
        </div>
      </div>
    );
  }

  if (isCustomer && user?.customer_id) {
    const c = customers.find((x) => x.id === user.customer_id);
    return (
      <CustomerDashboard
        customerId={user.customer_id}
        label={c ? `${c.name} (${c.code})` : "My dashboard"}
      />
    );
  }

  if (isWarehouse) {
    if (selectedCustomerId !== null) {
      const c = customers.find((x) => x.id === selectedCustomerId);
      return (
        <CustomerDashboard
          customerId={selectedCustomerId}
          label={c ? `${c.name} (${c.code})` : `Customer #${selectedCustomerId}`}
        />
      );
    }
    return <WarehouseDashboard />;
  }

  return (
    <div className="p-6 text-sm text-muted-foreground">
      No dashboard available for this role.
    </div>
  );
}
