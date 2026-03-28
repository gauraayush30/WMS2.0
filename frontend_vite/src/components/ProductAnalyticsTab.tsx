import { useEffect, useState, useMemo } from "react";
import { useAuth, API } from "../context/AuthContext";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Select } from "@/components/ui/select";
import {
  TrendingUp,
  ArrowUpDown,
  Package,
  Activity,
  Calendar,
  BarChart3,
  ArrowDownToLine,
  ArrowUpFromLine,
  Minus,
  RefreshCw,
} from "lucide-react";
import {
  AreaChart,
  Area,
  BarChart,
  Bar,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip as RTooltip,
  ResponsiveContainer,
  ReferenceLine,
  ComposedChart,
  Legend,
  Cell,
  PieChart,
  Pie,
} from "recharts";
import { motion } from "framer-motion";

/* ─────────────────────────── Types ──────────────────────────── */

interface DailyData {
  date: string;
  inbound: number;
  outbound: number;
  net_change: number;
  closing_stock: number;
  tx_count: number;
  stock_in_qty: number;
  stock_out_qty: number;
  return_qty: number;
  damage_qty: number;
  adjustment_qty: number;
}

interface Summary {
  total_transactions: number;
  total_inbound: number;
  total_outbound: number;
  first_transaction: string | null;
  last_transaction: string | null;
  active_days: number;
}

interface ReasonBreakdown {
  reason: string;
  count: number;
  total_qty: number;
}

interface AnalyticsData {
  daily: DailyData[];
  summary: Summary;
  reasons: ReasonBreakdown[];
}

interface ProductInfo {
  reorder_point?: number;
  safety_stock?: number;
  par_level?: number;
  stock_at_warehouse?: number;
}

const REASON_COLORS: Record<string, string> = {
  stock_in: "#22c55e",
  stock_out: "#ef4444",
  delivery: "#3b82f6",
  shipment: "#f59e0b",
  return: "#8b5cf6",
  damage: "#ec4899",
  adjustment: "#6b7280",
  transfer: "#14b8a6",
  uploaded_history: "#a78bfa",
};

const REASON_LABELS: Record<string, string> = {
  stock_in: "Stock In",
  stock_out: "Stock Out",
  delivery: "Delivery",
  shipment: "Shipment",
  return: "Return",
  damage: "Damage",
  adjustment: "Adjustment",
  transfer: "Transfer",
  uploaded_history: "Uploaded History",
};

const shortDate = (d: string) => {
  const dt = new Date(d);
  return dt.toLocaleDateString("en-IN", { day: "numeric", month: "short" });
};

/* ─────────────────────────── Component ──────────────────────── */

export default function ProductAnalyticsTab({
  productId,
  product,
}: {
  productId: string;
  product: ProductInfo;
}) {
  const { authFetch } = useAuth();
  const [data, setData] = useState<AnalyticsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [days, setDays] = useState("90");

  const fetchAnalytics = (d: string) => {
    setLoading(true);
    setError("");
    authFetch(`${API}/products/${productId}/analytics?days=${d}`)
      .then((r) => {
        if (!r.ok) throw new Error("Failed to load analytics");
        return r.json();
      })
      .then((json) => setData(json))
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    fetchAnalytics(days);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [productId]);

  const handleDaysChange = (val: string) => {
    setDays(val);
    fetchAnalytics(val);
  };

  /* ── Derived data ────────────────────────────────────────────── */

  const movingAverage = useMemo(() => {
    if (!data?.daily?.length) return [];
    const window = 7;
    return data.daily.map((d, i) => {
      const start = Math.max(0, i - window + 1);
      const slice = data.daily.slice(start, i + 1);
      const avgOut = slice.reduce((s, x) => s + x.outbound, 0) / slice.length;
      const avgIn = slice.reduce((s, x) => s + x.inbound, 0) / slice.length;
      return {
        date: d.date,
        outbound: d.outbound,
        inbound: d.inbound,
        ma_outbound: Math.round(avgOut * 10) / 10,
        ma_inbound: Math.round(avgIn * 10) / 10,
      };
    });
  }, [data]);

  const cumulativeFlow = useMemo(() => {
    if (!data?.daily?.length) return [];
    let cumIn = 0;
    let cumOut = 0;
    return data.daily.map((d) => {
      cumIn += d.inbound;
      cumOut += d.outbound;
      return {
        date: d.date,
        cumulative_inbound: cumIn,
        cumulative_outbound: cumOut,
      };
    });
  }, [data]);

  const weeklyData = useMemo(() => {
    if (!data?.daily?.length) return [];
    const weeks: Record<
      string,
      { inbound: number; outbound: number; start: string; end: string }
    > = {};
    data.daily.forEach((d) => {
      const dt = new Date(d.date);
      const weekStart = new Date(dt);
      weekStart.setDate(dt.getDate() - dt.getDay());
      const key = weekStart.toISOString().slice(0, 10);
      if (!weeks[key])
        weeks[key] = { inbound: 0, outbound: 0, start: d.date, end: d.date };
      weeks[key].inbound += d.inbound;
      weeks[key].outbound += d.outbound;
      weeks[key].end = d.date;
    });
    return Object.entries(weeks).map(([, v]) => ({
      week: `${shortDate(v.start)} - ${shortDate(v.end)}`,
      inbound: v.inbound,
      outbound: v.outbound,
    }));
  }, [data]);

  const pieData = useMemo(() => {
    if (!data?.reasons?.length) return [];
    return data.reasons.map((r) => ({
      name: REASON_LABELS[r.reason] || r.reason,
      value: r.total_qty,
      color: REASON_COLORS[r.reason] || "#94a3b8",
    }));
  }, [data]);

  /* ── KPI stats ───────────────────────────────────────────────── */

  const avgDailyOut = data?.summary
    ? data.summary.active_days > 0
      ? Math.round(data.summary.total_outbound / data.summary.active_days)
      : 0
    : 0;
  const avgDailyIn = data?.summary
    ? data.summary.active_days > 0
      ? Math.round(data.summary.total_inbound / data.summary.active_days)
      : 0
    : 0;
  const daysOfStock =
    avgDailyOut > 0 && product.stock_at_warehouse
      ? Math.round(product.stock_at_warehouse / avgDailyOut)
      : null;

  /* ── Render ──────────────────────────────────────────────────── */

  if (loading) {
    return (
      <div className="space-y-4">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {[...Array(4)].map((_, i) => (
            <Skeleton key={i} className="h-24 rounded-xl" />
          ))}
        </div>
        <Skeleton className="h-72 rounded-xl" />
        <Skeleton className="h-64 rounded-xl" />
      </div>
    );
  }

  if (error) {
    return (
      <Card>
        <CardContent className="py-10 text-center">
          <p className="text-destructive mb-3">{error}</p>
          <Button size="sm" onClick={() => fetchAnalytics(days)}>
            <RefreshCw size={14} /> Retry
          </Button>
        </CardContent>
      </Card>
    );
  }

  if (!data || !data.daily.length) {
    return (
      <Card>
        <CardContent className="py-16 text-center space-y-3">
          <BarChart3 size={40} className="mx-auto text-muted-foreground/40" />
          <p className="text-muted-foreground">
            No transaction data yet. Start recording inventory movements to see
            analytics here.
          </p>
        </CardContent>
      </Card>
    );
  }

  const kpis = [
    {
      label: "Total Inbound",
      value: data.summary.total_inbound.toLocaleString(),
      icon: ArrowDownToLine,
      color: "text-emerald-600",
      bg: "bg-emerald-50",
      sub: `~${avgDailyIn}/day`,
    },
    {
      label: "Total Outbound",
      value: data.summary.total_outbound.toLocaleString(),
      icon: ArrowUpFromLine,
      color: "text-red-500",
      bg: "bg-red-50",
      sub: `~${avgDailyOut}/day`,
    },
    {
      label: "Transactions",
      value: data.summary.total_transactions.toLocaleString(),
      icon: Activity,
      color: "text-blue-600",
      bg: "bg-blue-50",
      sub: `${data.summary.active_days} active days`,
    },
    {
      label: "Days of Stock",
      value: daysOfStock !== null ? `${daysOfStock}` : "—",
      icon: Calendar,
      color:
        daysOfStock !== null && daysOfStock < 14
          ? "text-amber-600"
          : "text-purple-600",
      bg:
        daysOfStock !== null && daysOfStock < 14
          ? "bg-amber-50"
          : "bg-purple-50",
      sub:
        daysOfStock !== null && daysOfStock < 14
          ? "Low — reorder soon"
          : "At current rate",
    },
  ];

  const CustomTooltip = ({ active, payload, label }: any) => {
    if (!active || !payload?.length) return null;
    return (
      <div className="bg-popover border rounded-lg shadow-lg p-3 text-xs">
        <p className="font-semibold mb-1.5">{shortDate(label)}</p>
        {payload.map((p: any, i: number) => (
          <div key={i} className="flex items-center gap-2">
            <span
              className="w-2 h-2 rounded-full"
              style={{ background: p.color }}
            />
            <span className="text-muted-foreground">{p.name}:</span>
            <span className="font-medium">{p.value}</span>
          </div>
        ))}
      </div>
    );
  };

  return (
    <div className="space-y-6">
      {/* ── Header with Range Selector ─────────────────────────── */}
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <div className="flex items-center gap-2">
          <BarChart3 size={18} className="text-primary" />
          <h3 className="text-base font-semibold">Inventory Analytics</h3>
          <Badge variant="secondary" className="text-[10px]">
            {data.daily.length} days of data
          </Badge>
        </div>
        <div className="flex items-center gap-2">
          <Select
            className="w-35 h-8 text-xs"
            value={days}
            onChange={(e) => handleDaysChange(e.target.value)}
          >
            <option value="30">Last 30 days</option>
            <option value="60">Last 60 days</option>
            <option value="90">Last 90 days</option>
            <option value="180">Last 6 months</option>
            <option value="365">Last year</option>
          </Select>
          <Button
            variant="outline"
            size="icon"
            className="h-8 w-8"
            onClick={() => fetchAnalytics(days)}
          >
            <RefreshCw size={14} />
          </Button>
        </div>
      </div>

      {/* ── KPI Cards ──────────────────────────────────────────── */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {kpis.map((k, i) => (
          <motion.div
            key={k.label}
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.06 }}
          >
            <Card className="relative overflow-hidden">
              <CardContent className="p-4">
                <div className="flex items-start justify-between">
                  <div className="space-y-1">
                    <p className="text-[11px] font-medium text-muted-foreground uppercase tracking-wider">
                      {k.label}
                    </p>
                    <p className="text-2xl font-bold tracking-tight">
                      {k.value}
                    </p>
                    <p className="text-[11px] text-muted-foreground">{k.sub}</p>
                  </div>
                  <div
                    className={`flex h-9 w-9 items-center justify-center rounded-lg ${k.bg}`}
                  >
                    <k.icon size={18} className={k.color} />
                  </div>
                </div>
              </CardContent>
            </Card>
          </motion.div>
        ))}
      </div>

      {/* ── 1. Stock Level Journey ─────────────────────────────── */}
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.15 }}
      >
        <Card>
          <CardHeader className="pb-2">
            <div className="flex items-center gap-2">
              <Package size={16} className="text-primary" />
              <CardTitle className="text-sm font-semibold">
                Stock Level Over Time
              </CardTitle>
            </div>
            <p className="text-xs text-muted-foreground">
              Daily closing stock with inventory management thresholds
            </p>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={300}>
              <AreaChart
                data={data.daily}
                margin={{ top: 10, right: 10, left: 0, bottom: 0 }}
              >
                <defs>
                  <linearGradient
                    id="stockGradient"
                    x1="0"
                    y1="0"
                    x2="0"
                    y2="1"
                  >
                    <stop offset="0%" stopColor="#3b82f6" stopOpacity={0.3} />
                    <stop
                      offset="100%"
                      stopColor="#3b82f6"
                      stopOpacity={0.02}
                    />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" className="opacity-30" />
                <XAxis
                  dataKey="date"
                  tickFormatter={shortDate}
                  fontSize={11}
                  tick={{ fill: "#94a3b8" }}
                  tickLine={false}
                  axisLine={false}
                />
                <YAxis
                  fontSize={11}
                  tick={{ fill: "#94a3b8" }}
                  tickLine={false}
                  axisLine={false}
                  width={45}
                />
                <RTooltip content={<CustomTooltip />} />
                {product.reorder_point ? (
                  <ReferenceLine
                    y={product.reorder_point}
                    stroke="#f59e0b"
                    strokeDasharray="6 3"
                    label={{
                      value: "Reorder",
                      position: "insideTopRight",
                      fontSize: 10,
                      fill: "#f59e0b",
                    }}
                  />
                ) : null}
                {product.safety_stock ? (
                  <ReferenceLine
                    y={product.safety_stock}
                    stroke="#ef4444"
                    strokeDasharray="6 3"
                    label={{
                      value: "Safety",
                      position: "insideTopRight",
                      fontSize: 10,
                      fill: "#ef4444",
                    }}
                  />
                ) : null}
                <Area
                  type="monotone"
                  dataKey="closing_stock"
                  stroke="#3b82f6"
                  strokeWidth={2}
                  fill="url(#stockGradient)"
                  name="Stock Level"
                  dot={false}
                  activeDot={{ r: 4, strokeWidth: 2 }}
                />
              </AreaChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      </motion.div>

      {/* ── 2. Daily Inbound vs Outbound ───────────────────────── */}
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.2 }}
      >
        <Card>
          <CardHeader className="pb-2">
            <div className="flex items-center gap-2">
              <ArrowUpDown size={16} className="text-primary" />
              <CardTitle className="text-sm font-semibold">
                Daily Inbound vs Outbound
              </CardTitle>
            </div>
            <p className="text-xs text-muted-foreground">
              Side-by-side comparison of daily stock movements
            </p>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={260}>
              <BarChart
                data={data.daily}
                margin={{ top: 10, right: 10, left: 0, bottom: 0 }}
              >
                <CartesianGrid strokeDasharray="3 3" className="opacity-30" />
                <XAxis
                  dataKey="date"
                  tickFormatter={shortDate}
                  fontSize={11}
                  tick={{ fill: "#94a3b8" }}
                  tickLine={false}
                  axisLine={false}
                />
                <YAxis
                  fontSize={11}
                  tick={{ fill: "#94a3b8" }}
                  tickLine={false}
                  axisLine={false}
                  width={45}
                />
                <RTooltip content={<CustomTooltip />} />
                <Legend
                  wrapperStyle={{ fontSize: "12px", paddingTop: "8px" }}
                />
                <Bar
                  dataKey="inbound"
                  name="Inbound"
                  fill="#22c55e"
                  radius={[3, 3, 0, 0]}
                  maxBarSize={18}
                />
                <Bar
                  dataKey="outbound"
                  name="Outbound"
                  fill="#ef4444"
                  radius={[3, 3, 0, 0]}
                  maxBarSize={18}
                />
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      </motion.div>

      {/* ── 3. Trend Line (7-day MA) + 4. Reason Breakdown ─────── */}
      <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
        {/* Trend Chart — 3 cols */}
        <motion.div
          className="lg:col-span-3"
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.25 }}
        >
          <Card className="h-full">
            <CardHeader className="pb-2">
              <div className="flex items-center gap-2">
                <TrendingUp size={16} className="text-primary" />
                <CardTitle className="text-sm font-semibold">
                  Movement Trend
                </CardTitle>
              </div>
              <p className="text-xs text-muted-foreground">
                7-day moving average of inbound & outbound
              </p>
            </CardHeader>
            <CardContent>
              <ResponsiveContainer width="100%" height={250}>
                <ComposedChart
                  data={movingAverage}
                  margin={{ top: 10, right: 10, left: 0, bottom: 0 }}
                >
                  <CartesianGrid strokeDasharray="3 3" className="opacity-30" />
                  <XAxis
                    dataKey="date"
                    tickFormatter={shortDate}
                    fontSize={11}
                    tick={{ fill: "#94a3b8" }}
                    tickLine={false}
                    axisLine={false}
                  />
                  <YAxis
                    fontSize={11}
                    tick={{ fill: "#94a3b8" }}
                    tickLine={false}
                    axisLine={false}
                    width={45}
                  />
                  <RTooltip content={<CustomTooltip />} />
                  <Legend
                    wrapperStyle={{ fontSize: "11px", paddingTop: "8px" }}
                  />
                  <Bar
                    dataKey="outbound"
                    name="Daily Outbound"
                    fill="#fecaca"
                    maxBarSize={10}
                    radius={[2, 2, 0, 0]}
                  />
                  <Line
                    type="monotone"
                    dataKey="ma_outbound"
                    name="Outbound MA(7)"
                    stroke="#ef4444"
                    strokeWidth={2.5}
                    dot={false}
                  />
                  <Line
                    type="monotone"
                    dataKey="ma_inbound"
                    name="Inbound MA(7)"
                    stroke="#22c55e"
                    strokeWidth={2.5}
                    dot={false}
                    strokeDasharray="6 3"
                  />
                </ComposedChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        </motion.div>

        {/* Reason Breakdown — 2 cols */}
        <motion.div
          className="lg:col-span-2"
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.3 }}
        >
          <Card className="h-full">
            <CardHeader className="pb-2">
              <div className="flex items-center gap-2">
                <Activity size={16} className="text-primary" />
                <CardTitle className="text-sm font-semibold">
                  By Reason
                </CardTitle>
              </div>
              <p className="text-xs text-muted-foreground">
                Breakdown of movements by type
              </p>
            </CardHeader>
            <CardContent>
              {pieData.length > 0 ? (
                <div className="flex flex-col items-center gap-4">
                  <ResponsiveContainer width="100%" height={160}>
                    <PieChart>
                      <Pie
                        data={pieData}
                        cx="50%"
                        cy="50%"
                        innerRadius={42}
                        outerRadius={70}
                        paddingAngle={3}
                        dataKey="value"
                        strokeWidth={0}
                      >
                        {pieData.map((entry, i) => (
                          <Cell key={i} fill={entry.color} />
                        ))}
                      </Pie>
                      <RTooltip
                        formatter={(v: any) => [v, "Qty"]}
                        contentStyle={{
                          fontSize: "12px",
                          borderRadius: "8px",
                        }}
                      />
                    </PieChart>
                  </ResponsiveContainer>
                  <div className="flex flex-wrap justify-center gap-x-4 gap-y-1.5">
                    {pieData.map((p) => (
                      <div
                        key={p.name}
                        className="flex items-center gap-1.5 text-xs"
                      >
                        <span
                          className="w-2.5 h-2.5 rounded-sm"
                          style={{ background: p.color }}
                        />
                        <span className="text-muted-foreground">{p.name}</span>
                        <span className="font-medium">{p.value}</span>
                      </div>
                    ))}
                  </div>
                </div>
              ) : (
                <p className="text-xs text-muted-foreground text-center py-8">
                  No data
                </p>
              )}
            </CardContent>
          </Card>
        </motion.div>
      </div>

      {/* ── 5. Cumulative Flow ─────────────────────────────────── */}
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.35 }}
      >
        <Card>
          <CardHeader className="pb-2">
            <div className="flex items-center gap-2">
              <TrendingUp size={16} className="text-primary" />
              <CardTitle className="text-sm font-semibold">
                Cumulative Flow
              </CardTitle>
            </div>
            <p className="text-xs text-muted-foreground">
              Running total of inbound and outbound over time — the gap shows
              net stock contribution
            </p>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={260}>
              <AreaChart
                data={cumulativeFlow}
                margin={{ top: 10, right: 10, left: 0, bottom: 0 }}
              >
                <defs>
                  <linearGradient id="cumInGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#22c55e" stopOpacity={0.25} />
                    <stop
                      offset="100%"
                      stopColor="#22c55e"
                      stopOpacity={0.02}
                    />
                  </linearGradient>
                  <linearGradient id="cumOutGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#ef4444" stopOpacity={0.2} />
                    <stop
                      offset="100%"
                      stopColor="#ef4444"
                      stopOpacity={0.02}
                    />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" className="opacity-30" />
                <XAxis
                  dataKey="date"
                  tickFormatter={shortDate}
                  fontSize={11}
                  tick={{ fill: "#94a3b8" }}
                  tickLine={false}
                  axisLine={false}
                />
                <YAxis
                  fontSize={11}
                  tick={{ fill: "#94a3b8" }}
                  tickLine={false}
                  axisLine={false}
                  width={50}
                />
                <RTooltip content={<CustomTooltip />} />
                <Legend
                  wrapperStyle={{ fontSize: "12px", paddingTop: "8px" }}
                />
                <Area
                  type="monotone"
                  dataKey="cumulative_inbound"
                  stroke="#22c55e"
                  strokeWidth={2}
                  fill="url(#cumInGrad)"
                  name="Cumulative Inbound"
                  dot={false}
                />
                <Area
                  type="monotone"
                  dataKey="cumulative_outbound"
                  stroke="#ef4444"
                  strokeWidth={2}
                  fill="url(#cumOutGrad)"
                  name="Cumulative Outbound"
                  dot={false}
                />
              </AreaChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      </motion.div>

      {/* ── 6. Weekly Volume ────────────────────────────────────── */}
      {weeklyData.length > 1 && (
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.4 }}
        >
          <Card>
            <CardHeader className="pb-2">
              <div className="flex items-center gap-2">
                <Calendar size={16} className="text-primary" />
                <CardTitle className="text-sm font-semibold">
                  Weekly Volume
                </CardTitle>
              </div>
              <p className="text-xs text-muted-foreground">
                Aggregated weekly inbound & outbound to spot seasonal patterns
              </p>
            </CardHeader>
            <CardContent>
              <ResponsiveContainer width="100%" height={220}>
                <BarChart
                  data={weeklyData}
                  margin={{ top: 10, right: 10, left: 0, bottom: 0 }}
                >
                  <CartesianGrid strokeDasharray="3 3" className="opacity-30" />
                  <XAxis
                    dataKey="week"
                    fontSize={10}
                    tick={{ fill: "#94a3b8" }}
                    tickLine={false}
                    axisLine={false}
                    interval={0}
                    angle={-30}
                    textAnchor="end"
                    height={50}
                  />
                  <YAxis
                    fontSize={11}
                    tick={{ fill: "#94a3b8" }}
                    tickLine={false}
                    axisLine={false}
                    width={45}
                  />
                  <RTooltip
                    contentStyle={{
                      fontSize: "12px",
                      borderRadius: "8px",
                    }}
                  />
                  <Legend
                    wrapperStyle={{ fontSize: "12px", paddingTop: "8px" }}
                  />
                  <Bar
                    dataKey="inbound"
                    name="Inbound"
                    fill="#22c55e"
                    radius={[4, 4, 0, 0]}
                    maxBarSize={28}
                  />
                  <Bar
                    dataKey="outbound"
                    name="Outbound"
                    fill="#ef4444"
                    radius={[4, 4, 0, 0]}
                    maxBarSize={28}
                  />
                </BarChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        </motion.div>
      )}

      {/* ── 7. Net Flow Chart ─────────────────────────────────── */}
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.45 }}
      >
        <Card>
          <CardHeader className="pb-2">
            <div className="flex items-center gap-2">
              <Minus size={16} className="text-primary" />
              <CardTitle className="text-sm font-semibold">
                Net Stock Flow
              </CardTitle>
            </div>
            <p className="text-xs text-muted-foreground">
              Daily net change (inbound − outbound). Positive = stock growing,
              Negative = stock depleting
            </p>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={220}>
              <BarChart
                data={data.daily}
                margin={{ top: 10, right: 10, left: 0, bottom: 0 }}
              >
                <CartesianGrid strokeDasharray="3 3" className="opacity-30" />
                <XAxis
                  dataKey="date"
                  tickFormatter={shortDate}
                  fontSize={11}
                  tick={{ fill: "#94a3b8" }}
                  tickLine={false}
                  axisLine={false}
                />
                <YAxis
                  fontSize={11}
                  tick={{ fill: "#94a3b8" }}
                  tickLine={false}
                  axisLine={false}
                  width={45}
                />
                <RTooltip content={<CustomTooltip />} />
                <ReferenceLine y={0} stroke="#94a3b8" strokeWidth={1} />
                <Bar
                  dataKey="net_change"
                  name="Net Change"
                  maxBarSize={14}
                  radius={[3, 3, 3, 3]}
                >
                  {data.daily.map((d, i) => (
                    <Cell
                      key={i}
                      fill={d.net_change >= 0 ? "#22c55e" : "#ef4444"}
                      fillOpacity={0.8}
                    />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      </motion.div>
    </div>
  );
}
