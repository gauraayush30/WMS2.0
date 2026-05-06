import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  Briefcase,
  Building2,
  Package,
  IndianRupee,
  PackageCheck,
  PackageX,
  ArrowDownToLine,
  ArrowUpFromLine,
  AlertTriangle,
} from "lucide-react";

import { API, useAuth } from "../../context/AuthContext";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";

interface WarehouseStats {
  total_customers: number;
  active_customers: number;
  active_warehouses: number;
  total_skus: number;
  total_units: number;
  total_stock_value: number;
  today_inbound_qty: number;
  today_outbound_qty: number;
  pending_inbounds: number;
  pending_outbounds: number;
}

interface CustomerRow {
  customer_id: number;
  customer_name: string;
  customer_code: string;
  is_active: boolean;
  sku_count: number;
  total_units: number;
  stock_value: number;
  low_stock_count: number;
  out_of_stock_count: number;
  today_inbound_qty: number;
  today_outbound_qty: number;
}

const fmtINR = (n: number) =>
  "₹" + Number(n || 0).toLocaleString("en-IN", { maximumFractionDigits: 0 });

function StatCard({
  icon: Icon,
  label,
  value,
  hint,
}: {
  icon: typeof Package;
  label: string;
  value: string | number;
  hint?: string;
}) {
  return (
    <Card>
      <CardContent className="p-4 flex items-start gap-3">
        <div className="rounded-md bg-muted p-2 text-muted-foreground">
          <Icon size={18} />
        </div>
        <div className="space-y-0.5">
          <div className="text-xs uppercase tracking-wider text-muted-foreground">
            {label}
          </div>
          <div className="text-2xl font-semibold leading-none">{value}</div>
          {hint && <div className="text-xs text-muted-foreground">{hint}</div>}
        </div>
      </CardContent>
    </Card>
  );
}

export default function WarehouseDashboard() {
  const { authFetch, setSelectedCustomerId } = useAuth();
  const [stats, setStats] = useState<WarehouseStats | null>(null);
  const [customers, setCustomers] = useState<CustomerRow[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    authFetch(`${API}/dashboard/warehouse-stats`)
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => {
        if (!d) return;
        setStats(d.stats);
        setCustomers(d.customer_breakdown || []);
      })
      .finally(() => setLoading(false));
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
        <Skeleton className="h-72" />
      </div>
    );
  }

  if (!stats) {
    return <div className="p-6 text-sm text-muted-foreground">No data.</div>;
  }

  return (
    <div className="space-y-6 p-6">
      <div>
        <h1 className="text-2xl font-semibold">Warehouse dashboard</h1>
        <p className="text-sm text-muted-foreground">
          Cross-customer view across {stats.active_warehouses} warehouse
          {stats.active_warehouses === 1 ? "" : "s"}.
        </p>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <StatCard
          icon={Briefcase}
          label="Customers"
          value={stats.active_customers}
          hint={`${stats.total_customers} total`}
        />
        <StatCard
          icon={Building2}
          label="Warehouses"
          value={stats.active_warehouses}
        />
        <StatCard icon={Package} label="SKUs" value={stats.total_skus} />
        <StatCard
          icon={IndianRupee}
          label="Stock value"
          value={fmtINR(stats.total_stock_value)}
          hint={`${Number(stats.total_units).toLocaleString("en-IN")} units`}
        />
        <StatCard
          icon={ArrowDownToLine}
          label="Today inbound"
          value={Number(stats.today_inbound_qty).toLocaleString("en-IN")}
          hint={`${stats.pending_inbounds} pending`}
        />
        <StatCard
          icon={ArrowUpFromLine}
          label="Today outbound"
          value={Number(stats.today_outbound_qty).toLocaleString("en-IN")}
          hint={`${stats.pending_outbounds} pending`}
        />
        <StatCard
          icon={PackageCheck}
          label="Pending inbounds"
          value={stats.pending_inbounds}
        />
        <StatCard
          icon={PackageX}
          label="Pending outbounds"
          value={stats.pending_outbounds}
        />
      </div>

      <div>
        <h2 className="text-sm font-semibold mb-3 flex items-center gap-2">
          <Briefcase size={14} /> Customer breakdown
        </h2>
        {customers.length === 0 ? (
          <Card>
            <CardContent className="p-6 text-sm text-muted-foreground">
              No customers yet. <Link to="/customers" className="underline">Add one →</Link>
            </CardContent>
          </Card>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {customers.map((c) => (
              <Card
                key={c.customer_id}
                className="cursor-pointer hover:shadow-sm transition"
                onClick={() => setSelectedCustomerId(c.customer_id)}
              >
                <CardContent className="p-4 space-y-2">
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="font-medium">{c.customer_name}</div>
                      <div className="text-xs text-muted-foreground font-mono">
                        {c.customer_code}
                      </div>
                    </div>
                    <Badge variant={c.is_active ? "default" : "secondary"}>
                      {c.is_active ? "active" : "inactive"}
                    </Badge>
                  </div>
                  <div className="grid grid-cols-3 gap-2 text-xs">
                    <div>
                      <div className="text-muted-foreground">SKUs</div>
                      <div className="text-base font-semibold">{c.sku_count}</div>
                    </div>
                    <div>
                      <div className="text-muted-foreground">Units</div>
                      <div className="text-base font-semibold">
                        {Number(c.total_units).toLocaleString("en-IN")}
                      </div>
                    </div>
                    <div>
                      <div className="text-muted-foreground">Stock value</div>
                      <div className="text-base font-semibold">
                        {fmtINR(c.stock_value)}
                      </div>
                    </div>
                  </div>
                  <div className="grid grid-cols-2 gap-2 text-xs">
                    <div className="flex items-center gap-1">
                      <ArrowDownToLine size={12} className="text-muted-foreground" />
                      <span className="text-muted-foreground">In today:</span>
                      <span className="font-medium">{c.today_inbound_qty}</span>
                    </div>
                    <div className="flex items-center gap-1">
                      <ArrowUpFromLine size={12} className="text-muted-foreground" />
                      <span className="text-muted-foreground">Out today:</span>
                      <span className="font-medium">{c.today_outbound_qty}</span>
                    </div>
                  </div>
                  {(c.low_stock_count > 0 || c.out_of_stock_count > 0) && (
                    <div className="flex items-center gap-1 text-xs text-amber-600">
                      <AlertTriangle size={12} />
                      <span>
                        {c.out_of_stock_count} out of stock ·{" "}
                        {c.low_stock_count} low
                      </span>
                    </div>
                  )}
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
