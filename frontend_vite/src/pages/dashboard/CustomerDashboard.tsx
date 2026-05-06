import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  Package,
  IndianRupee,
  ArrowDownToLine,
  ArrowUpFromLine,
  AlertTriangle,
  ShoppingCart,
} from "lucide-react";
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler,
} from "chart.js";
import { Line } from "react-chartjs-2";

import { API, useAuth } from "../../context/AuthContext";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Button } from "@/components/ui/button";

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler,
);

interface CustomerStats {
  sku_count: number;
  total_units: number;
  stock_value: number;
  low_stock_count: number;
  out_of_stock_count: number;
  mtd_inbound_qty: number;
  mtd_outbound_qty: number;
  pending_inbounds: number;
  pending_outbounds: number;
}

interface TrendPoint {
  date: string;
  qty: number;
}

interface ReorderItem {
  product_id: number;
  customer_id: number;
  name: string;
  sku_code: string;
  stock_at_warehouse: number;
  reorder_point: number;
  max_stock_level: number;
  lead_time_days: number;
  suggested_qty: number;
}

const fmtINR = (n: number) =>
  "₹" + Number(n || 0).toLocaleString("en-IN", { maximumFractionDigits: 0 });

function StatCard({
  icon: Icon,
  label,
  value,
  hint,
  warn,
}: {
  icon: typeof Package;
  label: string;
  value: string | number;
  hint?: string;
  warn?: boolean;
}) {
  return (
    <Card>
      <CardContent className="p-4 flex items-start gap-3">
        <div
          className={`rounded-md p-2 ${
            warn
              ? "bg-amber-100 text-amber-700"
              : "bg-muted text-muted-foreground"
          }`}
        >
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

interface CustomerDashboardProps {
  customerId: number;
  /** Display label, e.g. customer name + code */
  label?: string;
}

export default function CustomerDashboard({
  customerId,
  label,
}: CustomerDashboardProps) {
  const { authFetch } = useAuth();
  const [stats, setStats] = useState<CustomerStats | null>(null);
  const [trend, setTrend] = useState<TrendPoint[]>([]);
  const [reorder, setReorder] = useState<ReorderItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    const sParam = `customer_id=${customerId}`;
    Promise.all([
      authFetch(`${API}/dashboard/customer-stats?${sParam}`).then((r) =>
        r.ok ? r.json() : null,
      ),
      authFetch(`${API}/dashboard/replenishment-now?${sParam}`).then((r) =>
        r.ok ? r.json() : { items: [] },
      ),
    ])
      .then(([cs, rep]) => {
        if (cs) {
          setStats(cs.stats || null);
          setTrend(cs.outbound_trend || []);
        }
        setReorder(rep.items || []);
      })
      .finally(() => setLoading(false));
  }, [authFetch, customerId]);

  const chartData = useMemo(() => {
    return {
      labels: trend.map((p) => p.date),
      datasets: [
        {
          label: "Outbound qty (last 90d)",
          data: trend.map((p) => p.qty),
          borderColor: "rgb(79, 70, 229)",
          backgroundColor: "rgba(79, 70, 229, 0.1)",
          fill: true,
          tension: 0.3,
          pointRadius: 0,
        },
      ],
    };
  }, [trend]);

  const chartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { display: false },
      tooltip: { mode: "index" as const, intersect: false },
    },
    scales: {
      x: { display: true, ticks: { maxTicksLimit: 8 } },
      y: { beginAtZero: true },
    },
  };

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
        <h1 className="text-2xl font-semibold">{label || "Customer dashboard"}</h1>
        <p className="text-sm text-muted-foreground">
          Stock, flow, and reorder recommendations.
        </p>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <StatCard icon={Package} label="SKUs" value={stats.sku_count} />
        <StatCard
          icon={IndianRupee}
          label="Stock value"
          value={fmtINR(stats.stock_value)}
          hint={`${Number(stats.total_units).toLocaleString("en-IN")} units`}
        />
        <StatCard
          icon={ArrowDownToLine}
          label="MTD inbound"
          value={Number(stats.mtd_inbound_qty).toLocaleString("en-IN")}
          hint={`${stats.pending_inbounds} pending`}
        />
        <StatCard
          icon={ArrowUpFromLine}
          label="MTD outbound"
          value={Number(stats.mtd_outbound_qty).toLocaleString("en-IN")}
          hint={`${stats.pending_outbounds} pending`}
        />
        <StatCard
          icon={AlertTriangle}
          label="Low stock"
          value={stats.low_stock_count}
          warn={stats.low_stock_count > 0}
        />
        <StatCard
          icon={AlertTriangle}
          label="Out of stock"
          value={stats.out_of_stock_count}
          warn={stats.out_of_stock_count > 0}
        />
        <StatCard
          icon={ShoppingCart}
          label="Reorder now"
          value={reorder.length}
          warn={reorder.length > 0}
        />
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-sm">Outbound trend (90d)</CardTitle>
        </CardHeader>
        <CardContent style={{ height: 280 }}>
          {trend.length === 0 ? (
            <div className="text-sm text-muted-foreground">
              No outbound activity in the last 90 days.
            </div>
          ) : (
            <Line data={chartData} options={chartOptions} />
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-sm flex items-center justify-between">
            <span>Reorder now</span>
            {reorder.length > 0 && (
              <Badge variant="secondary">{reorder.length} items</Badge>
            )}
          </CardTitle>
        </CardHeader>
        <CardContent>
          {reorder.length === 0 ? (
            <div className="text-sm text-muted-foreground">
              All products are above their reorder point. 👌
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>SKU</TableHead>
                  <TableHead>Name</TableHead>
                  <TableHead>Stock</TableHead>
                  <TableHead>Reorder pt</TableHead>
                  <TableHead>Lead (d)</TableHead>
                  <TableHead>Suggested order</TableHead>
                  <TableHead className="text-right">Action</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {reorder.map((r) => (
                  <TableRow key={r.product_id}>
                    <TableCell className="font-mono text-xs">
                      {r.sku_code}
                    </TableCell>
                    <TableCell>{r.name}</TableCell>
                    <TableCell>
                      <span
                        className={
                          r.stock_at_warehouse === 0
                            ? "text-destructive font-medium"
                            : "text-amber-700 font-medium"
                        }
                      >
                        {r.stock_at_warehouse}
                      </span>
                    </TableCell>
                    <TableCell>{r.reorder_point}</TableCell>
                    <TableCell>{r.lead_time_days || "—"}</TableCell>
                    <TableCell>{r.suggested_qty}</TableCell>
                    <TableCell className="text-right">
                      <Button variant="ghost" size="sm" asChild>
                        <Link to="/inbounds/new">Create inbound</Link>
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
