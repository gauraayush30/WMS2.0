import { useCallback, useEffect, useMemo, useState } from "react";
import { useAuth, API } from "../context/AuthContext";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Alert } from "@/components/ui/alert";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import {
  Brain, AlertTriangle, RefreshCw, Store, ShoppingCart,
  MapPin, Lightbulb, Package,
} from "lucide-react";
import {
  BarChart, Bar,
  XAxis, YAxis, CartesianGrid, Tooltip as RTooltip, ResponsiveContainer,
  ScatterChart, Scatter, ZAxis,
} from "recharts";

// ── Types ────────────────────────────────────────────────────────────────────

interface KPIs {
  total_products: number;
  products_with_model: number;
  active_sellers: number;
  active_buyers: number;
  stockout_risk_count: number;
  total_inbound_qty: number;
  total_outbound_qty: number;
  insights_count: number;
}

interface ProductRow {
  id: number;
  name: string;
  sku_code: string | null;
  stock_at_warehouse: number;
  has_model: boolean;
  model_status: string | null;
  trained_at: string | null;
  cv_mae: number | null;
  cv_mape: number | null;
  forecast_7d: number;
  forecast_30d: number;
  stockout_date: string | null;
  days_of_supply: number | null;
  period_outbound: number;
  period_inbound: number;
  top_seller_name: string | null;
  top_buyer_name: string | null;
}

interface SellerRow {
  id: number; name: string; city: string | null; state: string | null;
  inbound_qty_period: number; share_pct: number;
  product_count: number; concentration_index: number;
  last_delivery: string | null;
}

interface BuyerRow {
  id: number; name: string; city: string | null; state: string | null;
  outbound_qty_period: number; share_pct: number;
  product_count: number; concentration_index: number;
  last_order: string | null;
}

interface PortfolioSummary {
  business_id: number;
  customer_id: number;
  warehouse_id: number;
  period_days: number;
  global_model: {
    trained: boolean;
    status: string | null;
    trained_at: string | null;
    cv_mae: number | null;
    cv_mape: number | null;
    n_products: number;
    n_buyers: number;
  };
  kpis: KPIs;
  products: ProductRow[];
  sellers: SellerRow[];
  buyers: BuyerRow[];
}

interface Insight {
  insight_type: string;
  severity: "critical" | "warning" | "info";
  product_id: number | null;
  entity_type: string | null;
  entity_id: number | null;
  message: string;
  value: number | null;
  threshold: number | null;
  meta: Record<string, unknown>;
  computed_at: string;
}

interface LocationRow {
  city: string; state: string;
  qty: number; entity_count: number; product_count: number;
}

interface TrainProgress {
  status: string;
  phase: string;
  phase_detail: string;
  elapsed_seconds: number;
  result: unknown;
  error: string | null;
}

// ── Page ─────────────────────────────────────────────────────────────────────

export default function ForecastPortfolioPage() {
  const { authFetch, effectiveCustomerId, selectedWarehouseId } = useAuth();
  console.log("effectiveCustomerId", effectiveCustomerId, "selectedWarehouseId", selectedWarehouseId);
  const [periodDays, setPeriodDays] = useState<number>(90);
  const [summary, setSummary] = useState<PortfolioSummary | null>(null);
  const [insights, setInsights] = useState<Insight[]>([]);
  const [locations, setLocations] = useState<LocationRow[]>([]);
  const [locationMode, setLocationMode] = useState<"buyer" | "seller">("buyer");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [training, setTraining] = useState<TrainProgress | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  const scopeReady = effectiveCustomerId != null && selectedWarehouseId != null;

  const buildUrl = useCallback(
    (path: string, extra: Record<string, string | number> = {}) => {
      const qp = new URLSearchParams({
        customer_id: String(effectiveCustomerId),
        warehouse_id: String(selectedWarehouseId),
        ...Object.fromEntries(Object.entries(extra).map(([k, v]) => [k, String(v)])),
      });
      return `${API}${path}?${qp.toString()}`;
    },
    [effectiveCustomerId, selectedWarehouseId],
  );

  const fetchAll = useCallback(async () => {
    if (!scopeReady) return;
    setLoading(true);
    setError(null);
    try {
      const [s, i, l] = await Promise.all([
        authFetch(buildUrl("/forecast/portfolio/summary", { period_days: periodDays })),
        authFetch(buildUrl("/forecast/portfolio/insights")),
        authFetch(buildUrl("/forecast/portfolio/location-heatmap", { mode: locationMode, period_days: periodDays })),
      ]);
      if (!s.ok) throw new Error(`summary failed (${s.status})`);
      const sj = await s.json();
      setSummary(sj);
      if (i.ok) {
        const ij = await i.json();
        setInsights(ij.insights || []);
      }
      if (l.ok) {
        const lj = await l.json();
        setLocations(lj.locations || []);
      }
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e);
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, [authFetch, buildUrl, periodDays, locationMode, scopeReady]);

  useEffect(() => { fetchAll(); }, [fetchAll]);

  // ── Training control ──────────────────────────────────────────────────
  const startTraining = async () => {
    if (!scopeReady) return;
    setTraining({ status: "training", phase: "starting", phase_detail: "", elapsed_seconds: 0, result: null, error: null });
    const r = await authFetch(buildUrl("/forecast/portfolio/train"), { method: "POST" });
    if (!r.ok) {
      const text = await r.text();
      setTraining({ status: "failed", phase: "failed", phase_detail: text, elapsed_seconds: 0, result: null, error: text });
      return;
    }
    pollTraining();
  };

  const pollTraining = useCallback(() => {
    if (!scopeReady) return;
    const tick = async () => {
      const r = await authFetch(buildUrl("/forecast/portfolio/train-progress"));
      if (!r.ok) return;
      const j: TrainProgress = await r.json();
      setTraining(j);
      if (j.status === "training") setTimeout(tick, 2000);
      else if (j.status === "ready") {
        await refreshCache();
        await fetchAll();
      }
    };
    tick();
  }, [authFetch, buildUrl, scopeReady, fetchAll]);

  const refreshCache = async () => {
    if (!scopeReady) return;
    setRefreshing(true);
    try {
      await authFetch(buildUrl("/forecast/portfolio/cache/refresh", { days_ahead: 30 }), { method: "POST" });
      await fetchAll();
    } finally {
      setRefreshing(false);
    }
  };

  // ── Render guards ────────────────────────────────────────────────────
  if (!scopeReady) {
    return (
      <div className="p-6">
        <Alert>
          <AlertTriangle className="h-4 w-4" />
          Select a customer and warehouse to view the portfolio.
        </Alert>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Brain className="h-6 w-6" /> Portfolio Intelligence
          </h1>
          <p className="text-sm text-muted-foreground">
            Global model, forecasts, seller & buyer behaviour.
          </p>
        </div>
        <div className="flex items-center gap-2">
          {[7, 30, 90, 180].map((d) => (
            <Button
              key={d}
              variant={periodDays === d ? "default" : "outline"}
              size="sm"
              onClick={() => setPeriodDays(d)}
            >
              {d}d
            </Button>
          ))}
          <Button variant="outline" size="sm" onClick={refreshCache} disabled={refreshing}>
            <RefreshCw className={"h-4 w-4 mr-1" + (refreshing ? " animate-spin" : "")} /> Refresh cache
          </Button>
          <Button size="sm" onClick={startTraining} disabled={training?.status === "training"}>
            <Brain className="h-4 w-4 mr-1" />
            {training?.status === "training" ? "Training…" : "Train global model"}
          </Button>
        </div>
      </div>

      {/* Errors / training banner */}
      {error && <Alert><AlertTriangle className="h-4 w-4" /> {error}</Alert>}
      {training?.status === "training" && (
        <Alert>
          <Brain className="h-4 w-4" />
          Training in progress — {training.phase}{training.phase_detail ? `: ${training.phase_detail}` : ""}
          {" ("}{training.elapsed_seconds.toFixed(0)}s)
        </Alert>
      )}
      {training?.status === "failed" && (
        <Alert variant="destructive"><AlertTriangle className="h-4 w-4" /> Training failed: {training.error}</Alert>
      )}

      {/* KPI ribbon */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <KPICard label="Products" value={summary?.kpis.total_products ?? 0} hint={`${summary?.kpis.products_with_model ?? 0} with model`} loading={loading} />
        <KPICard label="Sellers" value={summary?.kpis.active_sellers ?? 0} hint={`${summary?.kpis.total_inbound_qty ?? 0} inbound`} loading={loading} />
        <KPICard label="Buyers" value={summary?.kpis.active_buyers ?? 0} hint={`${summary?.kpis.total_outbound_qty ?? 0} outbound`} loading={loading} />
        <KPICard
          label="Insights"
          value={summary?.kpis.insights_count ?? 0}
          hint={summary?.kpis.stockout_risk_count ? `${summary.kpis.stockout_risk_count} stockout risk` : "no critical"}
          loading={loading}
        />
      </div>

      {/* Sub-tabs */}
      <Tabs defaultValue="products" className="w-full">
        <TabsList>
          <TabsTrigger value="products"><Package className="h-4 w-4 mr-1" /> Products</TabsTrigger>
          <TabsTrigger value="sellers"><Store className="h-4 w-4 mr-1" /> Sellers</TabsTrigger>
          <TabsTrigger value="buyers"><ShoppingCart className="h-4 w-4 mr-1" /> Buyers</TabsTrigger>
          <TabsTrigger value="locations"><MapPin className="h-4 w-4 mr-1" /> Locations</TabsTrigger>
          <TabsTrigger value="insights"><Lightbulb className="h-4 w-4 mr-1" /> Insights</TabsTrigger>
        </TabsList>

        {/* PRODUCTS */}
        <TabsContent value="products">
          <ProductsTable products={summary?.products ?? []} loading={loading} />
        </TabsContent>

        {/* SELLERS */}
        <TabsContent value="sellers">
          <SellersPanel sellers={summary?.sellers ?? []} loading={loading} />
        </TabsContent>

        {/* BUYERS */}
        <TabsContent value="buyers">
          <BuyersPanel buyers={summary?.buyers ?? []} loading={loading} />
        </TabsContent>

        {/* LOCATIONS */}
        <TabsContent value="locations">
          <LocationsPanel
            locations={locations}
            mode={locationMode}
            onModeChange={setLocationMode}
            loading={loading}
          />
        </TabsContent>

        {/* INSIGHTS */}
        <TabsContent value="insights">
          <InsightsFeed insights={insights} loading={loading} />
        </TabsContent>
      </Tabs>
    </div>
  );
}

// ── Sub-components ───────────────────────────────────────────────────────────

function KPICard({ label, value, hint, loading }: { label: string; value: number; hint: string; loading: boolean }) {
  return (
    <Card>
      <CardContent className="pt-6">
        <div className="text-xs text-muted-foreground uppercase tracking-wide">{label}</div>
        {loading ? (
          <Skeleton className="h-8 w-16 mt-1" />
        ) : (
          <div className="text-3xl font-bold tabular-nums">{value.toLocaleString()}</div>
        )}
        <div className="text-xs text-muted-foreground mt-1">{hint}</div>
      </CardContent>
    </Card>
  );
}

function ProductsTable({ products, loading }: { products: ProductRow[]; loading: boolean }) {
  if (loading) return <Skeleton className="h-64 w-full" />;
  if (!products.length) {
    return <Card><CardContent className="py-12 text-center text-muted-foreground">No products in scope.</CardContent></Card>;
  }
  return (
    <Card>
      <CardHeader><CardTitle>Products</CardTitle></CardHeader>
      <CardContent className="overflow-x-auto">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>SKU</TableHead>
              <TableHead>Name</TableHead>
              <TableHead className="text-right">Stock</TableHead>
              <TableHead className="text-right">7d fcst</TableHead>
              <TableHead className="text-right">30d fcst</TableHead>
              <TableHead className="text-right">DoS</TableHead>
              <TableHead className="text-right">MAE</TableHead>
              <TableHead>Top buyer</TableHead>
              <TableHead>Risk</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {products.map((p) => {
              const risky = p.days_of_supply != null && p.days_of_supply <= 14;
              return (
                <TableRow key={p.id}>
                  <TableCell className="font-mono text-xs">{p.sku_code ?? "-"}</TableCell>
                  <TableCell className="font-medium">{p.name}</TableCell>
                  <TableCell className="text-right tabular-nums">{p.stock_at_warehouse}</TableCell>
                  <TableCell className="text-right tabular-nums">{p.forecast_7d.toFixed(0)}</TableCell>
                  <TableCell className="text-right tabular-nums">{p.forecast_30d.toFixed(0)}</TableCell>
                  <TableCell className="text-right tabular-nums">
                    {p.days_of_supply != null ? `${p.days_of_supply}d` : "—"}
                  </TableCell>
                  <TableCell className="text-right tabular-nums">
                    {p.cv_mae != null ? p.cv_mae.toFixed(1) : "—"}
                  </TableCell>
                  <TableCell className="text-sm">{p.top_buyer_name ?? "—"}</TableCell>
                  <TableCell>
                    {risky ? (
                      <Badge variant="destructive">{p.stockout_date}</Badge>
                    ) : p.has_model ? (
                      <Badge variant="default">healthy</Badge>
                    ) : (
                      <Badge variant="secondary">no model</Badge>
                    )}
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}

function SellersPanel({ sellers, loading }: { sellers: SellerRow[]; loading: boolean }) {
  if (loading) return <Skeleton className="h-64 w-full" />;
  if (!sellers.length) {
    return <Card><CardContent className="py-12 text-center text-muted-foreground">No suppliers in scope.</CardContent></Card>;
  }
  const top = sellers.slice(0, 6);
  return (
    <div className="space-y-4">
      <Card>
        <CardHeader><CardTitle>Inbound by seller</CardTitle></CardHeader>
        <CardContent>
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={top}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="name" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} />
              <RTooltip />
              <Bar dataKey="inbound_qty_period" fill="#2563eb" />
            </BarChart>
          </ResponsiveContainer>
        </CardContent>
      </Card>
      <Card>
        <CardHeader><CardTitle>All sellers</CardTitle></CardHeader>
        <CardContent className="overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Seller</TableHead>
                <TableHead>City</TableHead>
                <TableHead className="text-right">Inbound</TableHead>
                <TableHead className="text-right">Share</TableHead>
                <TableHead className="text-right">Products</TableHead>
                <TableHead className="text-right">Concentration</TableHead>
                <TableHead>Last delivery</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {sellers.map((s) => (
                <TableRow key={s.id}>
                  <TableCell className="font-medium">{s.name}</TableCell>
                  <TableCell className="text-sm">{s.city ?? "—"}</TableCell>
                  <TableCell className="text-right tabular-nums">{s.inbound_qty_period}</TableCell>
                  <TableCell className="text-right tabular-nums">{s.share_pct.toFixed(1)}%</TableCell>
                  <TableCell className="text-right tabular-nums">{s.product_count}</TableCell>
                  <TableCell className="text-right tabular-nums">
                    {s.concentration_index.toFixed(2)}
                    {s.concentration_index > 0.5 && <Badge className="ml-1" variant="destructive">high</Badge>}
                  </TableCell>
                  <TableCell className="text-sm">{s.last_delivery ?? "—"}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}

function BuyersPanel({ buyers, loading }: { buyers: BuyerRow[]; loading: boolean }) {
  if (loading) return <Skeleton className="h-64 w-full" />;
  if (!buyers.length) {
    return <Card><CardContent className="py-12 text-center text-muted-foreground">No buyers in scope.</CardContent></Card>;
  }
  const top = buyers.slice(0, 6);
  return (
    <div className="space-y-4">
      <Card>
        <CardHeader><CardTitle>Outbound by buyer</CardTitle></CardHeader>
        <CardContent>
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={top}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="name" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} />
              <RTooltip />
              <Bar dataKey="outbound_qty_period" fill="#16a34a" />
            </BarChart>
          </ResponsiveContainer>
        </CardContent>
      </Card>
      <Card>
        <CardHeader><CardTitle>All buyers</CardTitle></CardHeader>
        <CardContent className="overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Buyer</TableHead>
                <TableHead>City</TableHead>
                <TableHead className="text-right">Outbound</TableHead>
                <TableHead className="text-right">Share</TableHead>
                <TableHead className="text-right">Products</TableHead>
                <TableHead className="text-right">Concentration</TableHead>
                <TableHead>Last order</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {buyers.map((b) => (
                <TableRow key={b.id}>
                  <TableCell className="font-medium">{b.name}</TableCell>
                  <TableCell className="text-sm">{b.city ?? "—"}</TableCell>
                  <TableCell className="text-right tabular-nums">{b.outbound_qty_period}</TableCell>
                  <TableCell className="text-right tabular-nums">{b.share_pct.toFixed(1)}%</TableCell>
                  <TableCell className="text-right tabular-nums">{b.product_count}</TableCell>
                  <TableCell className="text-right tabular-nums">
                    {b.concentration_index.toFixed(2)}
                    {b.concentration_index > 0.5 && <Badge className="ml-1" variant="destructive">high</Badge>}
                  </TableCell>
                  <TableCell className="text-sm">{b.last_order ?? "—"}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}

function LocationsPanel({
  locations, mode, onModeChange, loading,
}: {
  locations: LocationRow[]; mode: "buyer" | "seller";
  onModeChange: (m: "buyer" | "seller") => void; loading: boolean;
}) {
  const stateAgg = useMemo(() => {
    const m = new Map<string, { state: string; qty: number; cities: Set<string>; entities: number }>();
    for (const l of locations) {
      const key = l.state || "Unknown";
      const slot = m.get(key) ?? { state: key, qty: 0, cities: new Set(), entities: 0 };
      slot.qty += l.qty;
      slot.cities.add(l.city);
      slot.entities += l.entity_count;
      m.set(key, slot);
    }
    return [...m.values()].sort((a, b) => b.qty - a.qty);
  }, [locations]);

  if (loading) return <Skeleton className="h-64 w-full" />;

  return (
    <div className="space-y-4">
      <div className="flex gap-2">
        <Button size="sm" variant={mode === "buyer" ? "default" : "outline"} onClick={() => onModeChange("buyer")}>Buyer destinations</Button>
        <Button size="sm" variant={mode === "seller" ? "default" : "outline"} onClick={() => onModeChange("seller")}>Seller origins</Button>
      </div>
      <Card>
        <CardHeader><CardTitle>Top cities</CardTitle></CardHeader>
        <CardContent>
          <ResponsiveContainer width="100%" height={300}>
            <ScatterChart>
              <CartesianGrid />
              <XAxis dataKey="city" tick={{ fontSize: 11 }} name="City" />
              <YAxis dataKey="qty" tick={{ fontSize: 11 }} name="Volume" />
              <ZAxis dataKey="qty" range={[60, 800]} />
              <RTooltip />
              <Scatter data={locations.slice(0, 30)} fill="#7c3aed" />
            </ScatterChart>
          </ResponsiveContainer>
        </CardContent>
      </Card>
      <Card>
        <CardHeader><CardTitle>States</CardTitle></CardHeader>
        <CardContent className="overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>State</TableHead>
                <TableHead className="text-right">Cities</TableHead>
                <TableHead className="text-right">Entities</TableHead>
                <TableHead className="text-right">Volume</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {stateAgg.map((s) => (
                <TableRow key={s.state}>
                  <TableCell className="font-medium">{s.state}</TableCell>
                  <TableCell className="text-right tabular-nums">{s.cities.size}</TableCell>
                  <TableCell className="text-right tabular-nums">{s.entities}</TableCell>
                  <TableCell className="text-right tabular-nums">{s.qty}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}

function InsightsFeed({ insights, loading }: { insights: Insight[]; loading: boolean }) {
  if (loading) return <Skeleton className="h-64 w-full" />;
  if (!insights.length) {
    return <Card><CardContent className="py-12 text-center text-muted-foreground">No insights — train the global model and refresh the cache.</CardContent></Card>;
  }
  const sevColor = {
    critical: "destructive" as const,
    warning: "secondary" as const,
    info: "outline" as const,
  };
  return (
    <div className="space-y-2">
      {insights.map((i, idx) => (
        <Card key={idx}>
          <CardContent className="py-4 flex items-start gap-3">
            <div>
              <Badge variant={sevColor[i.severity]}>{i.severity}</Badge>
            </div>
            <div className="flex-1">
              <div className="flex items-center gap-2 mb-1">
                <span className="text-xs font-mono uppercase text-muted-foreground">{i.insight_type}</span>
              </div>
              <div className="text-sm">{i.message}</div>
              {i.value != null && i.threshold != null && (
                <div className="text-xs text-muted-foreground mt-1">
                  value {i.value.toFixed(2)} vs threshold {i.threshold.toFixed(2)}
                </div>
              )}
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
