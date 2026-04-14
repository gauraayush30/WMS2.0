import { useEffect, useState, useCallback, useRef, useMemo } from "react";
import { useAuth, API } from "../../context/AuthContext";
import {
  ArrowDownToLine,
  ArrowUpFromLine,
  ArrowUpDown,
  Package,
  Download,
  Search,
  X,
  BarChart3,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip as RTooltip,
  ResponsiveContainer,
  Legend,
  AreaChart,
  Area,
} from "recharts";
import { motion } from "framer-motion";

/* ─────────────────────────── Types ──────────────────────────── */

interface ProductRanking {
  product_id: number;
  product_name: string;
  sku_code: string;
  total_inbound: number;
  total_outbound: number;
  current_stock: number;
}

interface ProductOption {
  id: number;
  name: string;
  sku_code: string;
}

interface TimelinePoint {
  date: string;
  inbound: number;
  outbound: number;
}

interface ReportSummary {
  total_inbound: number;
  total_outbound: number;
  total_products: number;
  net_flow: number;
}

interface ReportData {
  days: number;
  summary: ReportSummary;
  top_inbound: ProductRanking[];
  top_outbound: ProductRanking[];
  product_list: ProductOption[];
  timeline: TimelinePoint[];
  selected_product_id: number | null;
}

/* ─────────────────────────── Helpers ────────────────────────── */

const fadeUp = {
  hidden: { opacity: 0, y: 12 },
  show: (i: number) => ({
    opacity: 1,
    y: 0,
    transition: { delay: i * 0.05, duration: 0.35 },
  }),
};

const shortDate = (d: string) => {
  const dt = new Date(d);
  return dt.toLocaleDateString("en-IN", { day: "numeric", month: "short" });
};

const INBOUND_COLOR = "#22c55e";
const OUTBOUND_COLOR = "#ef4444";

/* ─────────────────────────── Component ──────────────────────── */

export default function InboundOutboundPage() {
  const { authFetch } = useAuth();
  const [data, setData] = useState<ReportData | null>(null);
  const [loading, setLoading] = useState(true);
  const [days, setDays] = useState("30");
  const [selectedProduct, setSelectedProduct] = useState<ProductOption | null>(
    null,
  );

  // Dropdown search
  const [productSearch, setProductSearch] = useState("");
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Close dropdown on click outside
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (
        dropdownRef.current &&
        !dropdownRef.current.contains(e.target as Node)
      ) {
        setDropdownOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  const fetchReport = useCallback(
    (productId?: number | null) => {
      setLoading(true);
      let url = `${API}/reports/inbound-outbound?days=${days}`;
      if (productId) url += `&product_id=${productId}`;
      authFetch(url)
        .then((r) => r.json())
        .then((d) => setData(d))
        .catch(console.error)
        .finally(() => setLoading(false));
    },
    [authFetch, days],
  );

  useEffect(() => {
    fetchReport(selectedProduct?.id);
  }, [fetchReport, selectedProduct]);

  // Filtered dropdown options
  const filteredProducts = useMemo(() => {
    if (!data?.product_list) return [];
    if (!productSearch.trim()) return data.product_list.slice(0, 20);
    const q = productSearch.toLowerCase();
    return data.product_list
      .filter(
        (p) =>
          p.name.toLowerCase().includes(q) ||
          p.sku_code.toLowerCase().includes(q),
      )
      .slice(0, 20);
  }, [data?.product_list, productSearch]);

  const handleSelectProduct = (p: ProductOption) => {
    setSelectedProduct(p);
    setProductSearch("");
    setDropdownOpen(false);
  };

  const handleClearProduct = () => {
    setSelectedProduct(null);
    setProductSearch("");
  };

  const exportCSV = () => {
    if (!data) return;
    const headers = [
      "Date",
      "Inbound",
      "Outbound",
    ];
    const rows = data.timeline.map((t) => [t.date, t.inbound, t.outbound]);
    const csv = [headers, ...rows].map((r) => r.join(",")).join("\n");
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `inbound-outbound-${days}d${selectedProduct ? `-${selectedProduct.sku_code}` : ""}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  /* ── Custom tooltip ─────────────────────────────────────────── */
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
            <span className="font-medium">
              {Number(p.value).toLocaleString()}
            </span>
          </div>
        ))}
      </div>
    );
  };

  /* ── Loading ────────────────────────────────────────────────── */
  if (loading && !data) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-8 w-80" />
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {[...Array(4)].map((_, i) => (
            <Skeleton key={i} className="h-28 rounded-xl" />
          ))}
        </div>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <Skeleton className="h-72 rounded-xl" />
          <Skeleton className="h-72 rounded-xl" />
        </div>
        <Skeleton className="h-80 rounded-xl" />
      </div>
    );
  }

  const summary = data?.summary ?? {
    total_inbound: 0,
    total_outbound: 0,
    total_products: 0,
    net_flow: 0,
  };

  const kpis = [
    {
      label: "Total Inbound",
      value: summary.total_inbound.toLocaleString(),
      icon: ArrowDownToLine,
      color: "text-emerald-600",
      bg: "bg-emerald-50",
    },
    {
      label: "Total Outbound",
      value: summary.total_outbound.toLocaleString(),
      icon: ArrowUpFromLine,
      color: "text-red-500",
      bg: "bg-red-50",
    },
    {
      label: "Net Flow",
      value: summary.net_flow.toLocaleString(),
      icon: ArrowUpDown,
      color: summary.net_flow >= 0 ? "text-emerald-600" : "text-red-500",
      bg: summary.net_flow >= 0 ? "bg-emerald-50" : "bg-red-50",
    },
    {
      label: "Active Products",
      value: summary.total_products.toLocaleString(),
      icon: Package,
      color: "text-blue-600",
      bg: "bg-blue-50",
    },
  ];

  return (
    <div className="space-y-6">
      {/* ── Header ────────────────────────────────────────────── */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">
            Inbound vs Outbound
          </h2>
          <p className="text-sm text-muted-foreground mt-1">
            Product-wise inbound & outbound analysis over the last{" "}
            <span className="font-medium">{days} days</span>
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Select
            value={days}
            onChange={(e) => setDays(e.target.value)}
            className="w-35"
          >
            <option value="7">Last 7 days</option>
            <option value="14">Last 14 days</option>
            <option value="30">Last 30 days</option>
            <option value="60">Last 60 days</option>
            <option value="90">Last 90 days</option>
            <option value="180">Last 180 days</option>
            <option value="365">Last 365 days</option>
          </Select>
          <Button variant="outline" size="sm" onClick={exportCSV}>
            <Download size={16} className="mr-1.5" />
            Export
          </Button>
        </div>
      </div>

      {/* ── KPI Cards ────────────────────────────────────────── */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {kpis.map((k, i) => {
          const Icon = k.icon;
          return (
            <motion.div
              key={k.label}
              custom={i}
              initial="hidden"
              animate="show"
              variants={fadeUp}
            >
              <Card>
                <CardContent className="flex items-center gap-4 p-5">
                  <div
                    className={`flex items-center justify-center h-12 w-12 rounded-lg ${k.bg}`}
                  >
                    <Icon size={22} className={k.color} />
                  </div>
                  <div>
                    <p className="text-sm text-muted-foreground">{k.label}</p>
                    <p className="text-2xl font-bold">{k.value}</p>
                  </div>
                </CardContent>
              </Card>
            </motion.div>
          );
        })}
      </div>

      {/* ── Top 5 Charts ─────────────────────────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Top 5 Inbound */}
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.15 }}
        >
          <Card className="h-full">
            <CardHeader className="pb-2">
              <div className="flex items-center gap-2">
                <ArrowDownToLine size={16} className="text-emerald-600" />
                <CardTitle className="text-sm font-semibold">
                  Top 5 Inbound Products
                </CardTitle>
              </div>
              <p className="text-xs text-muted-foreground">
                Highest received quantities in the period
              </p>
            </CardHeader>
            <CardContent>
              {(data?.top_inbound ?? []).length > 0 ? (
                <ResponsiveContainer width="100%" height={260}>
                  <BarChart
                    data={data?.top_inbound}
                    layout="vertical"
                    margin={{ top: 5, right: 20, left: 10, bottom: 5 }}
                  >
                    <CartesianGrid
                      strokeDasharray="3 3"
                      className="opacity-30"
                      horizontal={false}
                    />
                    <XAxis
                      type="number"
                      fontSize={11}
                      tick={{ fill: "#94a3b8" }}
                      tickLine={false}
                      axisLine={false}
                    />
                    <YAxis
                      type="category"
                      dataKey="product_name"
                      width={120}
                      fontSize={11}
                      tick={{ fill: "#64748b" }}
                      tickLine={false}
                      axisLine={false}
                      tickFormatter={(v: string) =>
                        v.length > 18 ? v.slice(0, 16) + "…" : v
                      }
                    />
                    <RTooltip
                      contentStyle={{
                        fontSize: "12px",
                        borderRadius: "8px",
                      }}
                      formatter={(val: any) => [
                        Number(val).toLocaleString(),
                        "Qty",
                      ]}
                    />
                    <Bar
                      dataKey="total_inbound"
                      name="Inbound"
                      fill={INBOUND_COLOR}
                      radius={[0, 4, 4, 0]}
                      maxBarSize={28}
                    />
                  </BarChart>
                </ResponsiveContainer>
              ) : (
                <p className="text-sm text-muted-foreground py-16 text-center">
                  No inbound data for this period
                </p>
              )}
            </CardContent>
          </Card>
        </motion.div>

        {/* Top 5 Outbound */}
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
        >
          <Card className="h-full">
            <CardHeader className="pb-2">
              <div className="flex items-center gap-2">
                <ArrowUpFromLine size={16} className="text-red-500" />
                <CardTitle className="text-sm font-semibold">
                  Top 5 Outbound Products
                </CardTitle>
              </div>
              <p className="text-xs text-muted-foreground">
                Highest dispatched quantities in the period
              </p>
            </CardHeader>
            <CardContent>
              {(data?.top_outbound ?? []).length > 0 ? (
                <ResponsiveContainer width="100%" height={260}>
                  <BarChart
                    data={data?.top_outbound}
                    layout="vertical"
                    margin={{ top: 5, right: 20, left: 10, bottom: 5 }}
                  >
                    <CartesianGrid
                      strokeDasharray="3 3"
                      className="opacity-30"
                      horizontal={false}
                    />
                    <XAxis
                      type="number"
                      fontSize={11}
                      tick={{ fill: "#94a3b8" }}
                      tickLine={false}
                      axisLine={false}
                    />
                    <YAxis
                      type="category"
                      dataKey="product_name"
                      width={120}
                      fontSize={11}
                      tick={{ fill: "#64748b" }}
                      tickLine={false}
                      axisLine={false}
                      tickFormatter={(v: string) =>
                        v.length > 18 ? v.slice(0, 16) + "…" : v
                      }
                    />
                    <RTooltip
                      contentStyle={{
                        fontSize: "12px",
                        borderRadius: "8px",
                      }}
                      formatter={(val: any) => [
                        Number(val).toLocaleString(),
                        "Qty",
                      ]}
                    />
                    <Bar
                      dataKey="total_outbound"
                      name="Outbound"
                      fill={OUTBOUND_COLOR}
                      radius={[0, 4, 4, 0]}
                      maxBarSize={28}
                    />
                  </BarChart>
                </ResponsiveContainer>
              ) : (
                <p className="text-sm text-muted-foreground py-16 text-center">
                  No outbound data for this period
                </p>
              )}
            </CardContent>
          </Card>
        </motion.div>
      </div>

      {/* ── Product-wise Time-series Graph ────────────────────── */}
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.25 }}
      >
        <Card>
          <CardHeader className="pb-2">
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
              <div>
                <div className="flex items-center gap-2">
                  <BarChart3 size={16} className="text-primary" />
                  <CardTitle className="text-sm font-semibold">
                    Inbound vs Outbound Over Time
                  </CardTitle>
                </div>
                <p className="text-xs text-muted-foreground mt-0.5">
                  {selectedProduct
                    ? `Showing data for ${selectedProduct.name} (${selectedProduct.sku_code})`
                    : "Select a product to view its individual trend, or view the aggregate"}
                </p>
              </div>

              {/* ── Product Search Dropdown ──────────────────── */}
              <div className="relative" ref={dropdownRef}>
                <div className="flex items-center gap-1.5">
                  <div className="relative">
                    <Search
                      size={14}
                      className="absolute left-2.5 top-1/2 -translate-y-1/2 text-muted-foreground"
                    />
                    <Input
                      placeholder="Search products..."
                      value={
                        selectedProduct
                          ? `${selectedProduct.name} (${selectedProduct.sku_code})`
                          : productSearch
                      }
                      onChange={(e) => {
                        setProductSearch(e.target.value);
                        setDropdownOpen(true);
                        if (selectedProduct) setSelectedProduct(null);
                      }}
                      onFocus={() => {
                        setDropdownOpen(true);
                        if (selectedProduct) {
                          setProductSearch("");
                          setSelectedProduct(null);
                        }
                      }}
                      className="w-64 pl-8 h-8 text-xs"
                    />
                  </div>
                  {selectedProduct && (
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-8 w-8 shrink-0"
                      onClick={handleClearProduct}
                    >
                      <X size={14} />
                    </Button>
                  )}
                </div>

                {/* Dropdown list */}
                {dropdownOpen && !selectedProduct && (
                  <div className="absolute z-50 right-0 mt-1 w-72 max-h-64 overflow-auto bg-popover border rounded-lg shadow-lg">
                    {filteredProducts.length === 0 ? (
                      <p className="text-xs text-muted-foreground p-3 text-center">
                        No products found
                      </p>
                    ) : (
                      filteredProducts.map((p) => (
                        <button
                          key={p.id}
                          className="w-full flex items-center gap-3 px-3 py-2.5 text-left hover:bg-muted/50 transition-colors cursor-pointer"
                          onClick={() => handleSelectProduct(p)}
                        >
                          <div className="flex items-center justify-center h-7 w-7 rounded bg-blue-50 text-blue-600 shrink-0">
                            <Package size={14} />
                          </div>
                          <div className="min-w-0">
                            <p className="text-xs font-medium truncate">
                              {p.name}
                            </p>
                            <p className="text-[10px] text-muted-foreground">
                              {p.sku_code}
                            </p>
                          </div>
                        </button>
                      ))
                    )}
                  </div>
                )}
              </div>
            </div>
          </CardHeader>
          <CardContent>
            {(data?.timeline ?? []).length > 0 ? (
              <ResponsiveContainer width="100%" height={320}>
                <AreaChart
                  data={data?.timeline}
                  margin={{ top: 10, right: 10, left: 0, bottom: 0 }}
                >
                  <defs>
                    <linearGradient
                      id="inboundGrad"
                      x1="0"
                      y1="0"
                      x2="0"
                      y2="1"
                    >
                      <stop
                        offset="0%"
                        stopColor={INBOUND_COLOR}
                        stopOpacity={0.25}
                      />
                      <stop
                        offset="100%"
                        stopColor={INBOUND_COLOR}
                        stopOpacity={0.02}
                      />
                    </linearGradient>
                    <linearGradient
                      id="outboundGrad"
                      x1="0"
                      y1="0"
                      x2="0"
                      y2="1"
                    >
                      <stop
                        offset="0%"
                        stopColor={OUTBOUND_COLOR}
                        stopOpacity={0.25}
                      />
                      <stop
                        offset="100%"
                        stopColor={OUTBOUND_COLOR}
                        stopOpacity={0.02}
                      />
                    </linearGradient>
                  </defs>
                  <CartesianGrid
                    strokeDasharray="3 3"
                    className="opacity-30"
                  />
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
                  <Area
                    type="monotone"
                    dataKey="inbound"
                    name="Inbound"
                    stroke={INBOUND_COLOR}
                    strokeWidth={2}
                    fill="url(#inboundGrad)"
                    dot={false}
                    activeDot={{ r: 4, strokeWidth: 2 }}
                  />
                  <Area
                    type="monotone"
                    dataKey="outbound"
                    name="Outbound"
                    stroke={OUTBOUND_COLOR}
                    strokeWidth={2}
                    fill="url(#outboundGrad)"
                    dot={false}
                    activeDot={{ r: 4, strokeWidth: 2 }}
                  />
                </AreaChart>
              </ResponsiveContainer>
            ) : (
              <div className="py-16 text-center">
                <BarChart3
                  size={40}
                  className="mx-auto text-muted-foreground/40 mb-3"
                />
                <p className="text-sm text-muted-foreground">
                  No timeline data available for this period
                </p>
              </div>
            )}
          </CardContent>
        </Card>
      </motion.div>

      {/* ── All Products Table ────────────────────────────────── */}
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.3 }}
      >
        <Card>
          <CardHeader className="pb-2">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Package size={16} className="text-primary" />
                <CardTitle className="text-sm font-semibold">
                  All Products — Inbound vs Outbound
                </CardTitle>
              </div>
              <Badge variant="outline" className="text-xs">
                {data?.product_list?.length ?? 0} products
              </Badge>
            </div>
          </CardHeader>
          <CardContent className="p-0">
            {(data?.top_inbound ?? []).length === 0 &&
            (data?.top_outbound ?? []).length === 0 ? (
              <div className="py-12 text-center text-muted-foreground">
                No product data found for the selected period.
              </div>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-[30%]">Product</TableHead>
                    <TableHead className="text-right">Inbound</TableHead>
                    <TableHead className="text-right">Outbound</TableHead>
                    <TableHead className="text-right">Net Flow</TableHead>
                    <TableHead className="text-right">Current Stock</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {(data?.product_list ?? [])
                    .map((p) => {
                      // Find full data from ranking lists
                      const full =
                        [
                          ...(data?.top_inbound ?? []),
                          ...(data?.top_outbound ?? []),
                        ].find((r) => r.product_id === p.id) ?? null;
                      return {
                        ...p,
                        total_inbound: full?.total_inbound ?? 0,
                        total_outbound: full?.total_outbound ?? 0,
                        current_stock: full?.current_stock ?? 0,
                      };
                    })
                    .sort(
                      (a, b) =>
                        b.total_inbound +
                        b.total_outbound -
                        (a.total_inbound + a.total_outbound),
                    )
                    .slice(0, 20)
                    .map((item) => {
                      const net = item.total_inbound - item.total_outbound;
                      return (
                        <TableRow
                          key={item.id}
                          className={`cursor-pointer transition-colors ${selectedProduct?.id === item.id ? "bg-muted/50" : "hover:bg-muted/30"}`}
                          onClick={() =>
                            handleSelectProduct({
                              id: item.id,
                              name: item.name,
                              sku_code: item.sku_code,
                            })
                          }
                        >
                          <TableCell>
                            <div>
                              <p className="font-medium">{item.name}</p>
                              <p className="text-xs text-muted-foreground">
                                {item.sku_code}
                              </p>
                            </div>
                          </TableCell>
                          <TableCell className="text-right font-medium text-emerald-600">
                            {item.total_inbound.toLocaleString()}
                          </TableCell>
                          <TableCell className="text-right font-medium text-red-500">
                            {item.total_outbound.toLocaleString()}
                          </TableCell>
                          <TableCell
                            className={`text-right font-medium ${net >= 0 ? "text-emerald-600" : "text-red-500"}`}
                          >
                            {net >= 0 ? "+" : ""}
                            {net.toLocaleString()}
                          </TableCell>
                          <TableCell className="text-right">
                            {item.current_stock.toLocaleString()}
                          </TableCell>
                        </TableRow>
                      );
                    })}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>
      </motion.div>
    </div>
  );
}
