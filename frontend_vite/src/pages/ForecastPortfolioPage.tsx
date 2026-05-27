import { useCallback, useEffect, useMemo, useState } from "react";
import { useAuth, API } from "../context/AuthContext";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Alert } from "@/components/ui/alert";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import {
  Brain, AlertTriangle, RefreshCw, Store, ShoppingCart,
  MapPin, Lightbulb, Package, TrendingUp, BarChart2, List, ChevronDown, ChevronRight, PackageCheck,
} from "lucide-react";
import {
  BarChart, Bar,
  AreaChart, Area,
  XAxis, YAxis, CartesianGrid, Tooltip as RTooltip, ResponsiveContainer,
  ScatterChart, Scatter, ZAxis, Legend, Cell,
} from "recharts";

// ── Helpers ───────────────────────────────────────────────────────────────────

function todayISO(): string {
  return new Date().toISOString().split("T")[0];
}

function plusDaysISO(days: number): string {
  return new Date(Date.now() + days * 86400000).toISOString().split("T")[0];
}

function fmtINR(v: number): string {
  return `₹${v.toLocaleString("en-IN", { maximumFractionDigits: 0 })}`;
}

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

// ── Outbound Forecast Interfaces (with valuation) ────────────────────────────

interface DayTotal {
  date: string;
  p10: number;
  p50: number;
  p90: number;
  value_p50: number;
}

interface BuyerForecastDay {
  date: string;
  p50: number;
  value: number;
}

interface BuyerForecast {
  buyer_id: number;
  buyer_name: string;
  city: string;
  state: string;
  total_p50: number;
  total_value: number;
  daily: BuyerForecastDay[];
}

interface LocationForecast {
  city: string;
  state: string;
  buyer_count: number;
  total_p50: number;
  total_value: number;
  daily: { date: string; p50: number; value: number }[];
}

interface ProductBuyerForecastBuyer {
  buyer_id: number;
  buyer_name: string;
  city: string;
  state: string;
  total_qty: number;
  total_value: number;
  daily: { date: string; qty: number; value: number }[];
}

interface ProductBuyerForecast {
  product_id: number;
  product_name: string;
  sku_code: string | null;
  uom: string;
  price: number;
  total_qty: number;
  total_value: number;
  buyers: ProductBuyerForecastBuyer[];
}

interface OutboundForecastData {
  start_date: string;
  end_date: string;
  daily_total: DayTotal[];
  by_buyer: BuyerForecast[];
  by_location: LocationForecast[];
  by_product_buyer: ProductBuyerForecast[];
}

// ── Inbound Forecast Interfaces ───────────────────────────────────────────────

interface InboundDayTotal {
  date: string;
  p10: number;
  p50: number;
  p90: number;
  value_p50: number;
}

interface SellerForecastDay { date: string; p50: number; value: number; }

interface SellerForecast {
  seller_id: number;
  seller_name: string;
  city: string;
  state: string;
  total_p50: number;
  total_value: number;
  daily: SellerForecastDay[];
}

interface InboundLocationForecast {
  city: string;
  state: string;
  seller_count: number;
  total_p50: number;
  total_value: number;
  daily: { date: string; p50: number; value: number }[];
}

interface ProductSellerForecastSeller {
  seller_id: number;
  seller_name: string;
  city: string;
  state: string;
  total_qty: number;
  total_value: number;
  daily: { date: string; qty: number; value: number }[];
}

interface ProductSellerForecast {
  product_id: number;
  product_name: string;
  sku_code: string | null;
  uom: string;
  avg_unit_cost: number;
  total_qty: number;
  total_value: number;
  sellers: ProductSellerForecastSeller[];
}

interface InboundForecastData {
  start_date: string;
  end_date: string;
  note: "historical_projection" | "no_history";
  daily_total: InboundDayTotal[];
  by_seller: SellerForecast[];
  by_location: InboundLocationForecast[];
  by_product_seller: ProductSellerForecast[];
}

// ── Page ─────────────────────────────────────────────────────────────────────

export default function ForecastPortfolioPage() {
  const { authFetch, effectiveCustomerId, selectedWarehouseId } = useAuth();
  const [periodDays, setPeriodDays] = useState<number>(90);
  const [summary, setSummary] = useState<PortfolioSummary | null>(null);
  const [insights, setInsights] = useState<Insight[]>([]);
  const [locations, setLocations] = useState<LocationRow[]>([]);
  const [locationMode, setLocationMode] = useState<"buyer" | "seller">("buyer");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [training, setTraining] = useState<TrainProgress | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [forecastData, setForecastData] = useState<OutboundForecastData | null>(null);
  const [forecastLoading, setForecastLoading] = useState(false);
  const [forecastStart, setForecastStart] = useState<string>(todayISO());
  const [forecastEnd,   setForecastEnd]   = useState<string>(plusDaysISO(30));
  const [inboundData,    setInboundData]    = useState<InboundForecastData | null>(null);
  const [inboundLoading, setInboundLoading] = useState(false);
  const [inboundStart,   setInboundStart]   = useState<string>(todayISO());
  const [inboundEnd,     setInboundEnd]     = useState<string>(plusDaysISO(30));

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
      setSummary(await s.json());
      if (i.ok) setInsights((await i.json()).insights || []);
      if (l.ok) setLocations((await l.json()).locations || []);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
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
      await authFetch(buildUrl("/forecast/portfolio/cache/refresh", { days_ahead: 60 }), { method: "POST" });
      await fetchAll();
    } finally {
      setRefreshing(false);
    }
  };

  const fetchForecast = useCallback(async (start: string, end: string) => {
    if (!scopeReady || !start || !end) return;
    setForecastLoading(true);
    try {
      const r = await authFetch(
        buildUrl("/forecast/portfolio/outbound-forecast", { start_date: start, end_date: end })
      );
      if (r.ok) setForecastData(await r.json());
    } finally {
      setForecastLoading(false);
    }
  }, [authFetch, buildUrl, scopeReady]);

  useEffect(() => { fetchForecast(forecastStart, forecastEnd); }, [fetchForecast, forecastStart, forecastEnd]);

  const fetchInboundForecast = useCallback(async (start: string, end: string) => {
    if (!scopeReady || !start || !end) return;
    setInboundLoading(true);
    try {
      const r = await authFetch(
        buildUrl("/forecast/portfolio/inbound-forecast", { start_date: start, end_date: end })
      );
      if (r.ok) setInboundData(await r.json());
    } finally {
      setInboundLoading(false);
    }
  }, [authFetch, buildUrl, scopeReady]);

  useEffect(() => { fetchInboundForecast(inboundStart, inboundEnd); }, [fetchInboundForecast, inboundStart, inboundEnd]);

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
          <TabsTrigger value="forecast"><TrendingUp className="h-4 w-4 mr-1" /> Outbound Forecast</TabsTrigger>
          <TabsTrigger value="inbound"><PackageCheck className="h-4 w-4 mr-1" /> Inbound Forecast</TabsTrigger>
        </TabsList>

        <TabsContent value="products">
          <ProductsTable products={summary?.products ?? []} loading={loading} />
        </TabsContent>

        <TabsContent value="sellers">
          <SellersPanel sellers={summary?.sellers ?? []} loading={loading} />
        </TabsContent>

        <TabsContent value="buyers">
          <BuyersPanel buyers={summary?.buyers ?? []} loading={loading} />
        </TabsContent>

        <TabsContent value="locations">
          <LocationsPanel
            locations={locations}
            mode={locationMode}
            onModeChange={setLocationMode}
            loading={loading}
          />
        </TabsContent>

        <TabsContent value="insights">
          <InsightsFeed insights={insights} loading={loading} />
        </TabsContent>

        <TabsContent value="forecast">
          <OutboundForecastPanel
            data={forecastData}
            loading={forecastLoading}
            startDate={forecastStart}
            endDate={forecastEnd}
            onStartChange={setForecastStart}
            onEndChange={setForecastEnd}
          />
        </TabsContent>

        <TabsContent value="inbound">
          <InboundForecastPanel
            data={inboundData}
            loading={inboundLoading}
            startDate={inboundStart}
            endDate={inboundEnd}
            onStartChange={setInboundStart}
            onEndChange={setInboundEnd}
          />
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

// ── Outbound Forecast Panel ──────────────────────────────────────────────────

const BUYER_COLORS = [
  "#2563eb", "#16a34a", "#dc2626", "#d97706", "#7c3aed",
  "#0891b2", "#db2777", "#65a30d", "#ea580c", "#4f46e5",
];

function fmtDate(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleDateString("en-IN", { month: "short", day: "numeric" });
}

function OutboundForecastPanel({
  data, loading, startDate, endDate, onStartChange, onEndChange,
}: {
  data: OutboundForecastData | null;
  loading: boolean;
  startDate: string;
  endDate: string;
  onStartChange: (d: string) => void;
  onEndChange: (d: string) => void;
}) {
  const [view, setView] = useState<"chart" | "table">("chart");
  const [section, setSection] = useState<"daily" | "buyer" | "location" | "product">("product");
  const today = todayISO();

  if (loading) return <Skeleton className="h-96 w-full" />;
  if (!data || (!data.daily_total.length && !data.by_buyer.length && !data.by_product_buyer.length)) {
    return (
      <div className="space-y-4">
        <DateRangeControls
          startDate={startDate} endDate={endDate} today={today}
          onStartChange={onStartChange} onEndChange={onEndChange}
        />
        <Card>
          <CardContent className="py-12 text-center text-muted-foreground">
            No forecast data available — train the global model and refresh the cache first.
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Controls */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <DateRangeControls
          startDate={startDate} endDate={endDate} today={today}
          onStartChange={onStartChange} onEndChange={onEndChange}
        />
        <div className="flex gap-2 flex-wrap">
          <Button size="sm" variant={section === "product" ? "default" : "outline"} onClick={() => setSection("product")}>
            <Package className="h-4 w-4 mr-1" /> By Product
          </Button>
          <Button size="sm" variant={section === "daily" ? "default" : "outline"} onClick={() => setSection("daily")}>
            <TrendingUp className="h-4 w-4 mr-1" /> Daily Total
          </Button>
          <Button size="sm" variant={section === "buyer" ? "default" : "outline"} onClick={() => setSection("buyer")}>
            <ShoppingCart className="h-4 w-4 mr-1" /> By Buyer
          </Button>
          <Button size="sm" variant={section === "location" ? "default" : "outline"} onClick={() => setSection("location")}>
            <MapPin className="h-4 w-4 mr-1" /> By Location
          </Button>
        </div>
        <div className="flex gap-1 border rounded-md overflow-hidden">
          <Button size="sm" variant={view === "chart" ? "default" : "ghost"} className="rounded-none" onClick={() => setView("chart")}>
            <BarChart2 className="h-4 w-4 mr-1" /> Chart
          </Button>
          <Button size="sm" variant={view === "table" ? "default" : "ghost"} className="rounded-none" onClick={() => setView("table")}>
            <List className="h-4 w-4 mr-1" /> Table
          </Button>
        </div>
      </div>

      {section === "product" && (
        data.by_product_buyer.length === 0
          ? <Card><CardContent className="py-12 text-center text-muted-foreground">No per-buyer product forecast data — refresh the cache.</CardContent></Card>
          : view === "chart"
            ? <ProductBuyerForecastChart products={data.by_product_buyer} />
            : <ProductBuyerForecastTable products={data.by_product_buyer} />
      )}

      {section === "daily" && (
        view === "chart"
          ? <DailyTotalChart data={data.daily_total} />
          : <DailyTotalTable data={data.daily_total} />
      )}

      {section === "buyer" && (
        view === "chart"
          ? <BuyerForecastChart buyers={data.by_buyer} />
          : <BuyerForecastTable buyers={data.by_buyer} />
      )}

      {section === "location" && (
        view === "chart"
          ? <LocationForecastChart locations={data.by_location} />
          : <LocationForecastTable locations={data.by_location} />
      )}
    </div>
  );
}

function DateRangeControls({
  startDate, endDate, today, onStartChange, onEndChange,
}: {
  startDate: string; endDate: string; today: string;
  onStartChange: (d: string) => void; onEndChange: (d: string) => void;
}) {
  return (
    <div className="flex items-center gap-2 flex-wrap">
      <Label className="text-xs text-muted-foreground">From</Label>
      <Input
        type="date"
        className="w-36 h-8"
        value={startDate}
        min={today}
        onChange={(e) => onStartChange(e.target.value)}
      />
      <Label className="text-xs text-muted-foreground">To</Label>
      <Input
        type="date"
        className="w-36 h-8"
        value={endDate}
        min={startDate}
        onChange={(e) => onEndChange(e.target.value)}
      />
    </div>
  );
}

// ── Product × Buyer components ───────────────────────────────────────────────

function ProductBuyerForecastChart({ products }: { products: ProductBuyerForecast[] }) {
  const barData = products.map((p) => ({
    name: p.sku_code ? `${p.sku_code}` : p.product_name,
    full_name: p.product_name,
    total_value: Math.round(p.total_value),
    total_qty: Math.round(p.total_qty),
    price: p.price,
    uom: p.uom,
  }));

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader><CardTitle>Forecasted value by product (₹)</CardTitle></CardHeader>
        <CardContent>
          <ResponsiveContainer width="100%" height={Math.max(260, products.length * 44)}>
            <BarChart data={barData} layout="vertical" margin={{ left: 100, right: 80 }}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis
                type="number"
                tick={{ fontSize: 11 }}
                tickFormatter={(v: number) => v >= 1000 ? `₹${(v / 1000).toFixed(0)}k` : `₹${v}`}
              />
              <YAxis type="category" dataKey="name" tick={{ fontSize: 11 }} width={100} />
              <RTooltip
                formatter={(v: number, _n, p) =>
                  [`${fmtINR(v)} · ${p.payload.total_qty} ${p.payload.uom} @ ₹${p.payload.price}`, p.payload.full_name]
                }
              />
              <Bar dataKey="total_value" fill="#2563eb" radius={[0, 4, 4, 0]}>
                {barData.map((_, i) => (
                  <Cell key={i} fill={BUYER_COLORS[i % BUYER_COLORS.length]} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </CardContent>
      </Card>
    </div>
  );
}

function ProductBuyerForecastTable({ products }: { products: ProductBuyerForecast[] }) {
  const [expanded, setExpanded] = useState<Set<number>>(new Set());
  const toggle = (id: number) =>
    setExpanded((prev) => {
      const s = new Set(prev);
      s.has(id) ? s.delete(id) : s.add(id);
      return s;
    });

  return (
    <Card>
      <CardHeader>
        <CardTitle>Forecasted value by product × buyer</CardTitle>
        <p className="text-xs text-muted-foreground">Click a product row to expand buyer breakdown.</p>
      </CardHeader>
      <CardContent className="overflow-x-auto">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-6"></TableHead>
              <TableHead>SKU</TableHead>
              <TableHead>Product</TableHead>
              <TableHead className="text-right">UOM</TableHead>
              <TableHead className="text-right">Unit Price</TableHead>
              <TableHead className="text-right">Fcst Qty (P50)</TableHead>
              <TableHead className="text-right">Fcst Value</TableHead>
              <TableHead className="text-right">Buyers</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {products.map((p) => (
              <>
                <TableRow
                  key={p.product_id}
                  className="cursor-pointer hover:bg-muted/50"
                  onClick={() => toggle(p.product_id)}
                >
                  <TableCell className="text-muted-foreground">
                    {expanded.has(p.product_id)
                      ? <ChevronDown className="h-3.5 w-3.5" />
                      : <ChevronRight className="h-3.5 w-3.5" />}
                  </TableCell>
                  <TableCell className="font-mono text-xs">{p.sku_code ?? "—"}</TableCell>
                  <TableCell className="font-medium">{p.product_name}</TableCell>
                  <TableCell className="text-right tabular-nums text-xs text-muted-foreground">{p.uom}</TableCell>
                  <TableCell className="text-right tabular-nums text-sm">₹{p.price.toFixed(2)}</TableCell>
                  <TableCell className="text-right tabular-nums">{p.total_qty.toFixed(0)} <span className="text-xs text-muted-foreground">{p.uom}</span></TableCell>
                  <TableCell className="text-right tabular-nums font-semibold">{fmtINR(p.total_value)}</TableCell>
                  <TableCell className="text-right tabular-nums">{p.buyers.length}</TableCell>
                </TableRow>
                {expanded.has(p.product_id) && p.buyers.map((b) => (
                  <TableRow key={`${p.product_id}-${b.buyer_id}`} className="bg-muted/20">
                    <TableCell />
                    <TableCell />
                    <TableCell className="pl-8 text-sm">
                      <span className="font-medium">{b.buyer_name}</span>
                      {(b.city || b.state) && (
                        <span className="ml-1.5 text-xs text-muted-foreground">
                          {[b.city, b.state].filter(Boolean).join(", ")}
                        </span>
                      )}
                    </TableCell>
                    <TableCell />
                    <TableCell className="text-right tabular-nums text-sm">{b.total_qty.toFixed(0)} <span className="text-xs text-muted-foreground">{p.uom}</span></TableCell>
                    <TableCell className="text-right tabular-nums text-sm">{fmtINR(b.total_value)}</TableCell>
                    <TableCell />
                  </TableRow>
                ))}
              </>
            ))}
            {products.length > 0 && (
              <TableRow className="font-bold bg-muted/40">
                <TableCell colSpan={4}>Total</TableCell>
                <TableCell className="text-right tabular-nums">
                  {products.reduce((s, p) => s + p.total_qty, 0).toFixed(0)}
                </TableCell>
                <TableCell className="text-right tabular-nums">
                  {fmtINR(products.reduce((s, p) => s + p.total_value, 0))}
                </TableCell>
                <TableCell />
              </TableRow>
            )}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}

// ── Daily Total chart / table ────────────────────────────────────────────────

function DailyTotalChart({ data }: { data: DayTotal[] }) {
  const chartData = data.map((d) => ({ ...d, date: fmtDate(d.date) }));
  const totalP50    = data.reduce((s, d) => s + d.p50,       0);
  const totalValue  = data.reduce((s, d) => s + d.value_p50, 0);
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Card><CardContent className="pt-5">
          <div className="text-xs text-muted-foreground uppercase">Expected total</div>
          <div className="text-2xl font-bold tabular-nums">{totalP50.toFixed(0)}</div>
          <div className="text-xs text-muted-foreground">units (P50)</div>
        </CardContent></Card>
        <Card><CardContent className="pt-5">
          <div className="text-xs text-muted-foreground uppercase">Low estimate</div>
          <div className="text-2xl font-bold tabular-nums">{data.reduce((s, d) => s + d.p10, 0).toFixed(0)}</div>
          <div className="text-xs text-muted-foreground">units (P10)</div>
        </CardContent></Card>
        <Card><CardContent className="pt-5">
          <div className="text-xs text-muted-foreground uppercase">High estimate</div>
          <div className="text-2xl font-bold tabular-nums">{data.reduce((s, d) => s + d.p90, 0).toFixed(0)}</div>
          <div className="text-xs text-muted-foreground">units (P90)</div>
        </CardContent></Card>
        <Card><CardContent className="pt-5">
          <div className="text-xs text-muted-foreground uppercase">Forecast value</div>
          <div className="text-2xl font-bold tabular-nums">{fmtINR(totalValue)}</div>
          <div className="text-xs text-muted-foreground">at P50 (est.)</div>
        </CardContent></Card>
      </div>
      <Card>
        <CardHeader><CardTitle>Day-wise outbound forecast (P10 / P50 / P90)</CardTitle></CardHeader>
        <CardContent>
          <ResponsiveContainer width="100%" height={320}>
            <AreaChart data={chartData} margin={{ top: 10, right: 20, left: 0, bottom: 0 }}>
              <defs>
                <linearGradient id="p90fill" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%"  stopColor="#2563eb" stopOpacity={0.15} />
                  <stop offset="95%" stopColor="#2563eb" stopOpacity={0.02} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="date" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} />
              <RTooltip formatter={(v: number) => v.toFixed(0)} />
              <Legend />
              <Area type="monotone" dataKey="p90" stroke="#93c5fd" fill="url(#p90fill)" name="P90 (high)" strokeWidth={1} dot={false} />
              <Area type="monotone" dataKey="p50" stroke="#2563eb" fill="none" name="P50 (expected)" strokeWidth={2} dot={false} />
              <Area type="monotone" dataKey="p10" stroke="#bfdbfe" fill="none" name="P10 (low)" strokeWidth={1} dot={false} strokeDasharray="4 3" />
            </AreaChart>
          </ResponsiveContainer>
        </CardContent>
      </Card>
    </div>
  );
}

function DailyTotalTable({ data }: { data: DayTotal[] }) {
  return (
    <Card>
      <CardHeader><CardTitle>Day-wise outbound forecast</CardTitle></CardHeader>
      <CardContent className="overflow-x-auto">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Date</TableHead>
              <TableHead className="text-right">P10 (low)</TableHead>
              <TableHead className="text-right">P50 (expected)</TableHead>
              <TableHead className="text-right">P90 (high)</TableHead>
              <TableHead className="text-right">Value P50</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {data.map((d) => (
              <TableRow key={d.date}>
                <TableCell className="font-medium">{fmtDate(d.date)}</TableCell>
                <TableCell className="text-right tabular-nums text-muted-foreground">{d.p10.toFixed(0)}</TableCell>
                <TableCell className="text-right tabular-nums font-semibold">{d.p50.toFixed(0)}</TableCell>
                <TableCell className="text-right tabular-nums text-muted-foreground">{d.p90.toFixed(0)}</TableCell>
                <TableCell className="text-right tabular-nums text-emerald-600">{fmtINR(d.value_p50)}</TableCell>
              </TableRow>
            ))}
            <TableRow className="font-bold bg-muted/40">
              <TableCell>Total</TableCell>
              <TableCell className="text-right tabular-nums">{data.reduce((s, d) => s + d.p10, 0).toFixed(0)}</TableCell>
              <TableCell className="text-right tabular-nums">{data.reduce((s, d) => s + d.p50, 0).toFixed(0)}</TableCell>
              <TableCell className="text-right tabular-nums">{data.reduce((s, d) => s + d.p90, 0).toFixed(0)}</TableCell>
              <TableCell className="text-right tabular-nums">{fmtINR(data.reduce((s, d) => s + d.value_p50, 0))}</TableCell>
            </TableRow>
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}

// ── By Buyer chart / table ───────────────────────────────────────────────────

function BuyerForecastChart({ buyers }: { buyers: BuyerForecast[] }) {
  const summaryData = buyers.map((b, i) => ({
    name: b.buyer_name,
    total_value: Math.round(b.total_value),
    total_qty: Math.round(b.total_p50),
    location: [b.city, b.state].filter(Boolean).join(", ") || "Unknown",
    color: BUYER_COLORS[i % BUYER_COLORS.length],
  }));

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader><CardTitle>Forecast value by buyer (₹)</CardTitle></CardHeader>
        <CardContent>
          <ResponsiveContainer width="100%" height={Math.max(260, buyers.length * 44)}>
            <BarChart data={summaryData} layout="vertical" margin={{ left: 140, right: 80 }}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis
                type="number"
                tick={{ fontSize: 11 }}
                tickFormatter={(v: number) => v >= 1000 ? `₹${(v / 1000).toFixed(0)}k` : `₹${v}`}
              />
              <YAxis type="category" dataKey="name" tick={{ fontSize: 11 }} width={140} />
              <RTooltip
                formatter={(v: number, _n, p) =>
                  [`${fmtINR(v)} · ${p.payload.total_qty} units`, p.payload.location]
                }
              />
              <Bar dataKey="total_value" radius={[0, 4, 4, 0]}>
                {summaryData.map((entry, i) => (
                  <Cell key={i} fill={entry.color} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </CardContent>
      </Card>
    </div>
  );
}

function BuyerForecastTable({ buyers }: { buyers: BuyerForecast[] }) {
  const allDates = buyers[0]?.daily.map((d) => d.date) ?? [];
  return (
    <Card>
      <CardHeader><CardTitle>Forecast value per buyer</CardTitle></CardHeader>
      <CardContent className="overflow-x-auto">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Buyer</TableHead>
              <TableHead>Location</TableHead>
              <TableHead className="text-right">Total Qty</TableHead>
              <TableHead className="text-right">Total Value</TableHead>
              {allDates.map((d) => (
                <TableHead key={d} className="text-right min-w-[80px]">{fmtDate(d)}</TableHead>
              ))}
            </TableRow>
          </TableHeader>
          <TableBody>
            {buyers.map((b, i) => (
              <TableRow key={b.buyer_id}>
                <TableCell className="font-medium">
                  <span className="inline-block w-2 h-2 rounded-full mr-2" style={{ backgroundColor: BUYER_COLORS[i % BUYER_COLORS.length] }} />
                  {b.buyer_name}
                </TableCell>
                <TableCell className="text-sm text-muted-foreground">
                  {[b.city, b.state].filter(Boolean).join(", ") || "—"}
                </TableCell>
                <TableCell className="text-right tabular-nums">{b.total_p50.toFixed(0)}</TableCell>
                <TableCell className="text-right tabular-nums font-semibold">{fmtINR(b.total_value)}</TableCell>
                {allDates.map((date) => {
                  const day = b.daily.find((d) => d.date === date);
                  return (
                    <TableCell key={date} className="text-right tabular-nums text-sm">
                      {day ? fmtINR(day.value) : "—"}
                    </TableCell>
                  );
                })}
              </TableRow>
            ))}
            <TableRow className="font-bold bg-muted/40">
              <TableCell colSpan={2}>Total</TableCell>
              <TableCell className="text-right tabular-nums">{buyers.reduce((s, b) => s + b.total_p50, 0).toFixed(0)}</TableCell>
              <TableCell className="text-right tabular-nums">{fmtINR(buyers.reduce((s, b) => s + b.total_value, 0))}</TableCell>
              {allDates.map((date) => (
                <TableCell key={date} className="text-right tabular-nums">
                  {fmtINR(buyers.reduce((s, b) => {
                    const d = b.daily.find((x) => x.date === date);
                    return s + (d?.value ?? 0);
                  }, 0))}
                </TableCell>
              ))}
            </TableRow>
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}

// ── By Location chart / table ────────────────────────────────────────────────

function LocationForecastChart({ locations }: { locations: LocationForecast[] }) {
  const barData = locations.map((l) => ({
    name: [l.city, l.state].filter(Boolean).join(", ") || "Unknown",
    total_value: Math.round(l.total_value),
    buyers: l.buyer_count,
  }));

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader><CardTitle>Forecast value by location (₹)</CardTitle></CardHeader>
        <CardContent>
          <ResponsiveContainer width="100%" height={280}>
            <BarChart data={barData} margin={{ top: 5, right: 20, left: 0, bottom: 40 }}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="name" tick={{ fontSize: 10 }} angle={-35} textAnchor="end" interval={0} />
              <YAxis
                tick={{ fontSize: 11 }}
                tickFormatter={(v: number) => v >= 1000 ? `₹${(v / 1000).toFixed(0)}k` : `₹${v}`}
              />
              <RTooltip formatter={(v: number, _n, p) => [`${fmtINR(v)} · ${p.payload.buyers} buyer(s)`, "Forecast value"]} />
              <Bar dataKey="total_value" radius={[4, 4, 0, 0]}>
                {barData.map((_, i) => (
                  <Cell key={i} fill={BUYER_COLORS[i % BUYER_COLORS.length]} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </CardContent>
      </Card>
    </div>
  );
}

function LocationForecastTable({ locations }: { locations: LocationForecast[] }) {
  return (
    <Card>
      <CardHeader><CardTitle>Forecast value by location</CardTitle></CardHeader>
      <CardContent className="overflow-x-auto">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>City</TableHead>
              <TableHead>State</TableHead>
              <TableHead className="text-right">Buyers</TableHead>
              <TableHead className="text-right">Total Qty</TableHead>
              <TableHead className="text-right">Total Value</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {locations.map((l, i) => (
              <TableRow key={`${l.city}-${l.state}`}>
                <TableCell className="font-medium">
                  <span className="inline-block w-2 h-2 rounded-full mr-2" style={{ backgroundColor: BUYER_COLORS[i % BUYER_COLORS.length] }} />
                  {l.city || "Unknown"}
                </TableCell>
                <TableCell className="text-sm text-muted-foreground">{l.state || "—"}</TableCell>
                <TableCell className="text-right tabular-nums">{l.buyer_count}</TableCell>
                <TableCell className="text-right tabular-nums">{l.total_p50.toFixed(0)}</TableCell>
                <TableCell className="text-right tabular-nums font-semibold">{fmtINR(l.total_value)}</TableCell>
              </TableRow>
            ))}
            <TableRow className="font-bold bg-muted/40">
              <TableCell colSpan={3}>Total</TableCell>
              <TableCell className="text-right tabular-nums">{locations.reduce((s, l) => s + l.total_p50, 0).toFixed(0)}</TableCell>
              <TableCell className="text-right tabular-nums">{fmtINR(locations.reduce((s, l) => s + l.total_value, 0))}</TableCell>
            </TableRow>
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}

// ── Inbound Forecast Panel ────────────────────────────────────────────────────

const SELLER_COLORS = [
  "#16a34a", "#0891b2", "#7c3aed", "#d97706", "#dc2626",
  "#4f46e5", "#db2777", "#65a30d", "#ea580c", "#2563eb",
];

function InboundForecastPanel({
  data, loading, startDate, endDate, onStartChange, onEndChange,
}: {
  data: InboundForecastData | null;
  loading: boolean;
  startDate: string;
  endDate: string;
  onStartChange: (d: string) => void;
  onEndChange: (d: string) => void;
}) {
  const [view, setView] = useState<"chart" | "table">("chart");
  const [section, setSection] = useState<"daily" | "seller" | "location" | "product">("product");
  const today = todayISO();

  if (loading) return <Skeleton className="h-96 w-full" />;

  const isEmpty = !data || data.note === "no_history" ||
    (!data.daily_total.length && !data.by_seller.length && !data.by_product_seller.length);

  const noHistoryMsg = data?.note === "no_history"
    ? "No delivery history found for this warehouse. Inbound forecast requires at least one recorded inbound delivery."
    : "No inbound forecast data available — record some inbound deliveries first.";

  return (
    <div className="space-y-4">
      {/* Controls */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-col gap-1">
          <DateRangeControls
            startDate={startDate} endDate={endDate} today={today}
            onStartChange={onStartChange} onEndChange={onEndChange}
          />
          <span className="text-xs text-muted-foreground pl-1">
            Based on historical delivery patterns (last 90 days)
          </span>
        </div>
        {!isEmpty && (
          <>
            <div className="flex gap-2 flex-wrap">
              <Button size="sm" variant={section === "product" ? "default" : "outline"} onClick={() => setSection("product")}>
                <Package className="h-4 w-4 mr-1" /> By Product
              </Button>
              <Button size="sm" variant={section === "daily" ? "default" : "outline"} onClick={() => setSection("daily")}>
                <TrendingUp className="h-4 w-4 mr-1" /> Daily Total
              </Button>
              <Button size="sm" variant={section === "seller" ? "default" : "outline"} onClick={() => setSection("seller")}>
                <Store className="h-4 w-4 mr-1" /> By Seller
              </Button>
              <Button size="sm" variant={section === "location" ? "default" : "outline"} onClick={() => setSection("location")}>
                <MapPin className="h-4 w-4 mr-1" /> By Location
              </Button>
            </div>
            <div className="flex gap-1 border rounded-md overflow-hidden">
              <Button size="sm" variant={view === "chart" ? "default" : "ghost"} className="rounded-none" onClick={() => setView("chart")}>
                <BarChart2 className="h-4 w-4 mr-1" /> Chart
              </Button>
              <Button size="sm" variant={view === "table" ? "default" : "ghost"} className="rounded-none" onClick={() => setView("table")}>
                <List className="h-4 w-4 mr-1" /> Table
              </Button>
            </div>
          </>
        )}
      </div>

      {isEmpty ? (
        <Card>
          <CardContent className="py-12 text-center text-muted-foreground">{noHistoryMsg}</CardContent>
        </Card>
      ) : (
        <>
          {section === "product" && (
            data.by_product_seller.length === 0
              ? <Card><CardContent className="py-12 text-center text-muted-foreground">No per-seller product data found.</CardContent></Card>
              : view === "chart"
                ? <ProductSellerForecastChart products={data.by_product_seller} />
                : <ProductSellerForecastTable products={data.by_product_seller} />
          )}

          {section === "daily" && (
            view === "chart"
              ? <InboundDailyTotalChart data={data.daily_total} />
              : <InboundDailyTotalTable data={data.daily_total} />
          )}

          {section === "seller" && (
            view === "chart"
              ? <SellerForecastChart sellers={data.by_seller} />
              : <SellerForecastTable sellers={data.by_seller} />
          )}

          {section === "location" && (
            view === "chart"
              ? <InboundLocationForecastChart locations={data.by_location} />
              : <InboundLocationForecastTable locations={data.by_location} />
          )}
        </>
      )}
    </div>
  );
}

// ── Inbound Daily Total ───────────────────────────────────────────────────────

function InboundDailyTotalChart({ data }: { data: InboundDayTotal[] }) {
  const chartData = data.map((d) => ({ ...d, date: fmtDate(d.date) }));
  const totalP50   = data.reduce((s, d) => s + d.p50,       0);
  const totalValue = data.reduce((s, d) => s + d.value_p50, 0);
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Card><CardContent className="pt-5">
          <div className="text-xs text-muted-foreground uppercase">Expected total</div>
          <div className="text-2xl font-bold tabular-nums">{totalP50.toFixed(0)}</div>
          <div className="text-xs text-muted-foreground">units (P50)</div>
        </CardContent></Card>
        <Card><CardContent className="pt-5">
          <div className="text-xs text-muted-foreground uppercase">Low estimate</div>
          <div className="text-2xl font-bold tabular-nums">{data.reduce((s, d) => s + d.p10, 0).toFixed(0)}</div>
          <div className="text-xs text-muted-foreground">units (P10)</div>
        </CardContent></Card>
        <Card><CardContent className="pt-5">
          <div className="text-xs text-muted-foreground uppercase">High estimate</div>
          <div className="text-2xl font-bold tabular-nums">{data.reduce((s, d) => s + d.p90, 0).toFixed(0)}</div>
          <div className="text-xs text-muted-foreground">units (P90)</div>
        </CardContent></Card>
        <Card><CardContent className="pt-5">
          <div className="text-xs text-muted-foreground uppercase">Est. purchase value</div>
          <div className="text-2xl font-bold tabular-nums text-green-700">{fmtINR(totalValue)}</div>
          <div className="text-xs text-muted-foreground">at P50 (avg cost)</div>
        </CardContent></Card>
      </div>
      <Card>
        <CardHeader><CardTitle>Day-wise inbound forecast (P10 / P50 / P90)</CardTitle></CardHeader>
        <CardContent>
          <ResponsiveContainer width="100%" height={320}>
            <AreaChart data={chartData} margin={{ top: 10, right: 20, left: 0, bottom: 0 }}>
              <defs>
                <linearGradient id="inp90fill" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%"  stopColor="#16a34a" stopOpacity={0.15} />
                  <stop offset="95%" stopColor="#16a34a" stopOpacity={0.02} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="date" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} />
              <RTooltip formatter={(v: number) => v.toFixed(0)} />
              <Legend />
              <Area type="monotone" dataKey="p90" stroke="#86efac" fill="url(#inp90fill)" name="P90 (high)" strokeWidth={1} dot={false} />
              <Area type="monotone" dataKey="p50" stroke="#16a34a" fill="none" name="P50 (expected)" strokeWidth={2} dot={false} />
              <Area type="monotone" dataKey="p10" stroke="#bbf7d0" fill="none" name="P10 (low)" strokeWidth={1} dot={false} strokeDasharray="4 3" />
            </AreaChart>
          </ResponsiveContainer>
        </CardContent>
      </Card>
    </div>
  );
}

function InboundDailyTotalTable({ data }: { data: InboundDayTotal[] }) {
  return (
    <Card>
      <CardHeader><CardTitle>Day-wise inbound forecast</CardTitle></CardHeader>
      <CardContent className="overflow-x-auto">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Date</TableHead>
              <TableHead className="text-right">P10 (low)</TableHead>
              <TableHead className="text-right">P50 (expected)</TableHead>
              <TableHead className="text-right">P90 (high)</TableHead>
              <TableHead className="text-right">Est. cost P50</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {data.map((d) => (
              <TableRow key={d.date}>
                <TableCell className="font-medium">{fmtDate(d.date)}</TableCell>
                <TableCell className="text-right tabular-nums text-muted-foreground">{d.p10.toFixed(0)}</TableCell>
                <TableCell className="text-right tabular-nums font-semibold">{d.p50.toFixed(0)}</TableCell>
                <TableCell className="text-right tabular-nums text-muted-foreground">{d.p90.toFixed(0)}</TableCell>
                <TableCell className="text-right tabular-nums text-green-700">{fmtINR(d.value_p50)}</TableCell>
              </TableRow>
            ))}
            <TableRow className="font-bold bg-muted/40">
              <TableCell>Total</TableCell>
              <TableCell className="text-right tabular-nums">{data.reduce((s, d) => s + d.p10, 0).toFixed(0)}</TableCell>
              <TableCell className="text-right tabular-nums">{data.reduce((s, d) => s + d.p50, 0).toFixed(0)}</TableCell>
              <TableCell className="text-right tabular-nums">{data.reduce((s, d) => s + d.p90, 0).toFixed(0)}</TableCell>
              <TableCell className="text-right tabular-nums">{fmtINR(data.reduce((s, d) => s + d.value_p50, 0))}</TableCell>
            </TableRow>
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}

// ── By Seller ─────────────────────────────────────────────────────────────────

function SellerForecastChart({ sellers }: { sellers: SellerForecast[] }) {
  const summaryData = sellers.map((s, i) => ({
    name: s.seller_name,
    total_value: Math.round(s.total_value),
    total_qty: Math.round(s.total_p50),
    location: [s.city, s.state].filter(Boolean).join(", ") || "Unknown",
    color: SELLER_COLORS[i % SELLER_COLORS.length],
  }));

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader><CardTitle>Est. purchase value by seller (₹)</CardTitle></CardHeader>
        <CardContent>
          <ResponsiveContainer width="100%" height={Math.max(260, sellers.length * 44)}>
            <BarChart data={summaryData} layout="vertical" margin={{ left: 140, right: 80 }}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis
                type="number"
                tick={{ fontSize: 11 }}
                tickFormatter={(v: number) => v >= 1000 ? `₹${(v / 1000).toFixed(0)}k` : `₹${v}`}
              />
              <YAxis type="category" dataKey="name" tick={{ fontSize: 11 }} width={140} />
              <RTooltip
                formatter={(v: number, _n, p) =>
                  [`${fmtINR(v)} · ${p.payload.total_qty} units`, p.payload.location]
                }
              />
              <Bar dataKey="total_value" radius={[0, 4, 4, 0]}>
                {summaryData.map((entry, i) => (
                  <Cell key={i} fill={entry.color} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </CardContent>
      </Card>
    </div>
  );
}

function SellerForecastTable({ sellers }: { sellers: SellerForecast[] }) {
  const nDays = sellers[0]?.daily.length || 1;
  return (
    <Card>
      <CardHeader><CardTitle>Est. purchase value per seller</CardTitle></CardHeader>
      <CardContent className="overflow-x-auto">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Seller</TableHead>
              <TableHead>Location</TableHead>
              <TableHead className="text-right">Avg daily P50</TableHead>
              <TableHead className="text-right">Avg daily cost</TableHead>
              <TableHead className="text-right">Period total qty</TableHead>
              <TableHead className="text-right">Period total cost</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {sellers.map((s, i) => (
              <TableRow key={s.seller_id}>
                <TableCell className="font-medium">
                  <span className="inline-block w-2 h-2 rounded-full mr-2" style={{ backgroundColor: SELLER_COLORS[i % SELLER_COLORS.length] }} />
                  {s.seller_name}
                </TableCell>
                <TableCell className="text-sm text-muted-foreground">
                  {[s.city, s.state].filter(Boolean).join(", ") || "—"}
                </TableCell>
                <TableCell className="text-right tabular-nums">{(s.total_p50 / nDays).toFixed(1)}</TableCell>
                <TableCell className="text-right tabular-nums">{fmtINR(s.total_value / nDays)}</TableCell>
                <TableCell className="text-right tabular-nums">{s.total_p50.toFixed(0)}</TableCell>
                <TableCell className="text-right tabular-nums font-semibold">{fmtINR(s.total_value)}</TableCell>
              </TableRow>
            ))}
            <TableRow className="font-bold bg-muted/40">
              <TableCell colSpan={4}>Total</TableCell>
              <TableCell className="text-right tabular-nums">{sellers.reduce((s, b) => s + b.total_p50, 0).toFixed(0)}</TableCell>
              <TableCell className="text-right tabular-nums">{fmtINR(sellers.reduce((s, b) => s + b.total_value, 0))}</TableCell>
            </TableRow>
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}

// ── Inbound By Location ───────────────────────────────────────────────────────

function InboundLocationForecastChart({ locations }: { locations: InboundLocationForecast[] }) {
  const barData = locations.map((l) => ({
    name: [l.city, l.state].filter(Boolean).join(", ") || "Unknown",
    total_value: Math.round(l.total_value),
    sellers: l.seller_count,
  }));

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader><CardTitle>Est. purchase value by location (₹)</CardTitle></CardHeader>
        <CardContent>
          <ResponsiveContainer width="100%" height={280}>
            <BarChart data={barData} margin={{ top: 5, right: 20, left: 0, bottom: 40 }}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="name" tick={{ fontSize: 10 }} angle={-35} textAnchor="end" interval={0} />
              <YAxis
                tick={{ fontSize: 11 }}
                tickFormatter={(v: number) => v >= 1000 ? `₹${(v / 1000).toFixed(0)}k` : `₹${v}`}
              />
              <RTooltip formatter={(v: number, _n, p) => [`${fmtINR(v)} · ${p.payload.sellers} seller(s)`, "Est. purchase value"]} />
              <Bar dataKey="total_value" radius={[4, 4, 0, 0]}>
                {barData.map((_, i) => (
                  <Cell key={i} fill={SELLER_COLORS[i % SELLER_COLORS.length]} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </CardContent>
      </Card>
    </div>
  );
}

function InboundLocationForecastTable({ locations }: { locations: InboundLocationForecast[] }) {
  return (
    <Card>
      <CardHeader><CardTitle>Est. purchase value by location</CardTitle></CardHeader>
      <CardContent className="overflow-x-auto">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>City</TableHead>
              <TableHead>State</TableHead>
              <TableHead className="text-right">Sellers</TableHead>
              <TableHead className="text-right">Total Qty</TableHead>
              <TableHead className="text-right">Est. Cost</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {locations.map((l, i) => (
              <TableRow key={`${l.city}-${l.state}`}>
                <TableCell className="font-medium">
                  <span className="inline-block w-2 h-2 rounded-full mr-2" style={{ backgroundColor: SELLER_COLORS[i % SELLER_COLORS.length] }} />
                  {l.city || "Unknown"}
                </TableCell>
                <TableCell className="text-sm text-muted-foreground">{l.state || "—"}</TableCell>
                <TableCell className="text-right tabular-nums">{l.seller_count}</TableCell>
                <TableCell className="text-right tabular-nums">{l.total_p50.toFixed(0)}</TableCell>
                <TableCell className="text-right tabular-nums font-semibold">{fmtINR(l.total_value)}</TableCell>
              </TableRow>
            ))}
            <TableRow className="font-bold bg-muted/40">
              <TableCell colSpan={3}>Total</TableCell>
              <TableCell className="text-right tabular-nums">{locations.reduce((s, l) => s + l.total_p50, 0).toFixed(0)}</TableCell>
              <TableCell className="text-right tabular-nums">{fmtINR(locations.reduce((s, l) => s + l.total_value, 0))}</TableCell>
            </TableRow>
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}

// ── Product × Seller components ───────────────────────────────────────────────

function ProductSellerForecastChart({ products }: { products: ProductSellerForecast[] }) {
  const barData = products.map((p) => ({
    name: p.sku_code ?? p.product_name,
    full_name: p.product_name,
    total_value: Math.round(p.total_value),
    total_qty: Math.round(p.total_qty),
    avg_unit_cost: p.avg_unit_cost,
    uom: p.uom,
  }));

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader><CardTitle>Est. purchase cost by product (₹)</CardTitle></CardHeader>
        <CardContent>
          <ResponsiveContainer width="100%" height={Math.max(260, products.length * 44)}>
            <BarChart data={barData} layout="vertical" margin={{ left: 100, right: 80 }}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis
                type="number"
                tick={{ fontSize: 11 }}
                tickFormatter={(v: number) => v >= 1000 ? `₹${(v / 1000).toFixed(0)}k` : `₹${v}`}
              />
              <YAxis type="category" dataKey="name" tick={{ fontSize: 11 }} width={100} />
              <RTooltip
                formatter={(v: number, _n, p) =>
                  [`${fmtINR(v)} · ${p.payload.total_qty} ${p.payload.uom} @ ₹${p.payload.avg_unit_cost.toFixed(2)}/unit`, p.payload.full_name]
                }
              />
              <Bar dataKey="total_value" radius={[0, 4, 4, 0]}>
                {barData.map((_, i) => (
                  <Cell key={i} fill={SELLER_COLORS[i % SELLER_COLORS.length]} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </CardContent>
      </Card>
    </div>
  );
}

function ProductSellerForecastTable({ products }: { products: ProductSellerForecast[] }) {
  const [expanded, setExpanded] = useState<Set<number>>(new Set());
  const toggle = (id: number) =>
    setExpanded((prev) => {
      const s = new Set(prev);
      s.has(id) ? s.delete(id) : s.add(id);
      return s;
    });

  return (
    <Card>
      <CardHeader>
        <CardTitle>Est. purchase cost by product × seller</CardTitle>
        <p className="text-xs text-muted-foreground">Click a product row to expand seller breakdown.</p>
      </CardHeader>
      <CardContent className="overflow-x-auto">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-6"></TableHead>
              <TableHead>SKU</TableHead>
              <TableHead>Product</TableHead>
              <TableHead className="text-right">UOM</TableHead>
              <TableHead className="text-right">Avg cost/unit</TableHead>
              <TableHead className="text-right">Fcst Qty (P50)</TableHead>
              <TableHead className="text-right">Est. Cost</TableHead>
              <TableHead className="text-right">Sellers</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {products.map((p) => (
              <>
                <TableRow
                  key={p.product_id}
                  className="cursor-pointer hover:bg-muted/50"
                  onClick={() => toggle(p.product_id)}
                >
                  <TableCell className="text-muted-foreground">
                    {expanded.has(p.product_id)
                      ? <ChevronDown className="h-3.5 w-3.5" />
                      : <ChevronRight className="h-3.5 w-3.5" />}
                  </TableCell>
                  <TableCell className="font-mono text-xs">{p.sku_code ?? "—"}</TableCell>
                  <TableCell className="font-medium">{p.product_name}</TableCell>
                  <TableCell className="text-right tabular-nums text-xs text-muted-foreground">{p.uom}</TableCell>
                  <TableCell className="text-right tabular-nums text-sm">₹{p.avg_unit_cost.toFixed(2)}</TableCell>
                  <TableCell className="text-right tabular-nums">{p.total_qty.toFixed(0)} <span className="text-xs text-muted-foreground">{p.uom}</span></TableCell>
                  <TableCell className="text-right tabular-nums font-semibold text-green-700">{fmtINR(p.total_value)}</TableCell>
                  <TableCell className="text-right tabular-nums">{p.sellers.length}</TableCell>
                </TableRow>
                {expanded.has(p.product_id) && p.sellers.map((s) => (
                  <TableRow key={`${p.product_id}-${s.seller_id}`} className="bg-muted/20">
                    <TableCell />
                    <TableCell />
                    <TableCell className="pl-8 text-sm">
                      <span className="font-medium">{s.seller_name}</span>
                      {(s.city || s.state) && (
                        <span className="ml-1.5 text-xs text-muted-foreground">
                          {[s.city, s.state].filter(Boolean).join(", ")}
                        </span>
                      )}
                    </TableCell>
                    <TableCell />
                    <TableCell />
                    <TableCell className="text-right tabular-nums text-sm">{s.total_qty.toFixed(0)} <span className="text-xs text-muted-foreground">{p.uom}</span></TableCell>
                    <TableCell className="text-right tabular-nums text-sm text-green-700">{fmtINR(s.total_value)}</TableCell>
                    <TableCell />
                  </TableRow>
                ))}
              </>
            ))}
            {products.length > 0 && (
              <TableRow className="font-bold bg-muted/40">
                <TableCell colSpan={5}>Total</TableCell>
                <TableCell className="text-right tabular-nums">
                  {products.reduce((s, p) => s + p.total_qty, 0).toFixed(0)}
                </TableCell>
                <TableCell className="text-right tabular-nums">
                  {fmtINR(products.reduce((s, p) => s + p.total_value, 0))}
                </TableCell>
                <TableCell />
              </TableRow>
            )}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}
