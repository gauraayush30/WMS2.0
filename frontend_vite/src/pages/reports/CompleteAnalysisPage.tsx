import { useEffect, useMemo, useState } from "react";
import { LayoutGrid, IndianRupee, Package, RefreshCw } from "lucide-react";
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
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

const fmtINR = (n: number) =>
  "₹" + Number(n || 0).toLocaleString("en-IN", { maximumFractionDigits: 0 });

interface ProductLite {
  id: number;
  name: string;
  sku_code: string;
}

interface Analysis {
  product: { name: string; sku_code: string; stock_at_warehouse: number };
  inbounds: { grn_number: string; received_qty: number; unit_cost: number; received_at: string }[];
  outbounds: {
    shipment_number: string;
    picked_qty: number;
    unit_price: number;
    avg_cogs: number;
    line_amount: number;
    shipped_at: string;
  }[];
  ledger: { date: string; net_change: number }[];
  economics: {
    revenue: number;
    cogs: number;
    gross_margin: number;
    gross_margin_pct: number | null;
    units_sold: number;
    shipments: number;
    avg_daily_outbound: number;
    days_inventory_outstanding: number | null;
    inventory_turns: number | null;
    window_days: number;
  };
}

export default function CompleteAnalysisPage() {
  const { authFetch, effectiveCustomerId } = useAuth();
  const [products, setProducts] = useState<ProductLite[]>([]);
  const [productId, setProductId] = useState<number | "">("");
  const [data, setData] = useState<Analysis | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const params = new URLSearchParams({ per_page: "300" });
    if (effectiveCustomerId) params.set("customer_id", String(effectiveCustomerId));
    authFetch(`${API}/products?${params.toString()}`)
      .then((r) => (r.ok ? r.json() : { products: [] }))
      .then((d) => setProducts(d.products || []));
  }, [authFetch, effectiveCustomerId]);

  const fetchData = async () => {
    if (!productId) return;
    setLoading(true);
    const cs = effectiveCustomerId ? `&customer_id=${effectiveCustomerId}` : "";
    const r = await authFetch(
      `${API}/analytics/complete-analysis/${productId}?days=90${cs}`,
    );
    setLoading(false);
    if (r.ok) setData(await r.json());
  };

  useEffect(() => {
    if (productId) fetchData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [productId]);

  const stockCurve = useMemo(() => {
    if (!data) return null;
    const labels = data.ledger.map((l) => l.date);
    let running = data.product.stock_at_warehouse;
    // The ledger is ordered ascending; reconstruct an approximate stock curve
    // by working backwards from current stock.
    const totalNet = data.ledger.reduce((acc, x) => acc + x.net_change, 0);
    let starting = running - totalNet;
    const series: number[] = [];
    for (const x of data.ledger) {
      starting += x.net_change;
      series.push(starting);
    }
    return {
      labels,
      datasets: [
        {
          label: "Stock on hand",
          data: series,
          borderColor: "rgb(79, 70, 229)",
          backgroundColor: "rgba(79, 70, 229, 0.1)",
          fill: true,
          tension: 0.3,
          pointRadius: 0,
        },
      ],
    };
  }, [data]);

  return (
    <div className="space-y-6 p-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <LayoutGrid className="text-muted-foreground" />
          <h1 className="text-2xl font-semibold">Complete analysis</h1>
        </div>
        <div className="flex gap-2">
          <Select
            value={productId === "" ? "" : String(productId)}
            onValueChange={(v) => setProductId(Number(v))}
          >
            <SelectTrigger className="w-72">
              <SelectValue placeholder="Pick a product" />
            </SelectTrigger>
            <SelectContent>
              {products.map((p) => (
                <SelectItem key={p.id} value={String(p.id)}>
                  {p.sku_code} — {p.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Button variant="outline" onClick={fetchData} disabled={!productId}>
            <RefreshCw size={14} /> Refresh
          </Button>
        </div>
      </div>

      {!data && !loading && (
        <Card>
          <CardContent className="p-6 text-sm text-muted-foreground">
            Pick a product to view its 360° report (90-day window).
          </CardContent>
        </Card>
      )}

      {loading && <div className="text-sm">Loading…</div>}

      {data && (
        <>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <StatCard
              icon={IndianRupee}
              label="Revenue (90d)"
              value={fmtINR(data.economics.revenue)}
            />
            <StatCard
              icon={IndianRupee}
              label="COGS (90d)"
              value={fmtINR(data.economics.cogs)}
            />
            <StatCard
              icon={IndianRupee}
              label="Gross margin"
              value={fmtINR(data.economics.gross_margin)}
              hint={
                data.economics.gross_margin_pct !== null
                  ? `${data.economics.gross_margin_pct.toFixed(1)}%`
                  : undefined
              }
            />
            <StatCard
              icon={Package}
              label="Units sold"
              value={data.economics.units_sold}
              hint={`${data.economics.shipments} shipments`}
            />
            <StatCard
              icon={Package}
              label="Avg daily outbound"
              value={data.economics.avg_daily_outbound}
            />
            <StatCard
              icon={Package}
              label="DIO (days)"
              value={
                data.economics.days_inventory_outstanding !== null
                  ? data.economics.days_inventory_outstanding
                  : "—"
              }
            />
            <StatCard
              icon={Package}
              label="Inventory turns"
              value={
                data.economics.inventory_turns !== null
                  ? data.economics.inventory_turns
                  : "—"
              }
              hint="(annualised)"
            />
            <StatCard
              icon={Package}
              label="Stock on hand"
              value={data.product.stock_at_warehouse}
            />
          </div>

          {stockCurve && stockCurve.labels.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="text-sm">Stock curve (90d)</CardTitle>
              </CardHeader>
              <CardContent style={{ height: 280 }}>
                <Line
                  data={stockCurve}
                  options={{
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: { legend: { display: false } },
                    scales: { x: { ticks: { maxTicksLimit: 8 } }, y: { beginAtZero: true } },
                  }}
                />
              </CardContent>
            </Card>
          )}

          <Card>
            <CardHeader>
              <CardTitle className="text-sm">Inbound timeline</CardTitle>
            </CardHeader>
            <CardContent>
              {data.inbounds.length === 0 ? (
                <div className="text-sm text-muted-foreground">No inbounds in window.</div>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>GRN</TableHead>
                      <TableHead>Received</TableHead>
                      <TableHead>Qty</TableHead>
                      <TableHead>Unit cost</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {data.inbounds.map((i) => (
                      <TableRow key={i.grn_number}>
                        <TableCell className="font-mono text-xs">{i.grn_number}</TableCell>
                        <TableCell>{new Date(i.received_at).toLocaleDateString()}</TableCell>
                        <TableCell>{i.received_qty}</TableCell>
                        <TableCell>{Number(i.unit_cost).toFixed(2)}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-sm">Outbound timeline</CardTitle>
            </CardHeader>
            <CardContent>
              {data.outbounds.length === 0 ? (
                <div className="text-sm text-muted-foreground">No outbounds in window.</div>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Ship #</TableHead>
                      <TableHead>Shipped</TableHead>
                      <TableHead>Qty</TableHead>
                      <TableHead>Unit price</TableHead>
                      <TableHead>Avg COGS</TableHead>
                      <TableHead>Revenue</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {data.outbounds.map((o) => (
                      <TableRow key={o.shipment_number}>
                        <TableCell className="font-mono text-xs">{o.shipment_number}</TableCell>
                        <TableCell>{new Date(o.shipped_at).toLocaleDateString()}</TableCell>
                        <TableCell>{o.picked_qty}</TableCell>
                        <TableCell>{Number(o.unit_price).toFixed(2)}</TableCell>
                        <TableCell>{Number(o.avg_cogs).toFixed(2)}</TableCell>
                        <TableCell>{fmtINR(Number(o.line_amount))}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}

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
          <div className="text-xl font-semibold leading-none">{value}</div>
          {hint && <div className="text-xs text-muted-foreground">{hint}</div>}
        </div>
      </CardContent>
    </Card>
  );
}
